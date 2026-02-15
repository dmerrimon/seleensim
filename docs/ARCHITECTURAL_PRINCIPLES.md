# Architectural Principles

## Core Philosophy

SeleenSIM is built on **calibration readiness**: The ability to update assumptions based on real data without changing code.

This document defines the architectural rules that make calibration possible.

---

## The Ilana Law

### The Question

> **"Could this number be different for a different organization?"**

### The Rule

- **YES** → It's an **assumption** → Must be **parameterized**
- **NO** → It's **structural** → OK to **hardcode**

### Why This Matters

Hidden assumptions prevent calibration. If SCRI collects data showing "actually 5x slowdown, not 2x," they should update a parameter, not edit code.

**Before (Wrong)**:
```python
# Hidden assumption: 2x max slowdown
duration_multiplier = 1.0 / max(0.5, budget_ratio)  # Where does 0.5 come from?
```

**After (Correct)**:
```python
# Explicit assumption: User specifies response curve
duration_multiplier = self.response_curve.sample_multiplier(budget_ratio, seed)
```

---

## Architectural Guarantees

### 1. Entities Are Pure Data

**Rule**: Entities reference distributions but never sample them.

**Why**: Sampling is execution. Entities are specifications. Separation enables calibration.

✅ **Correct**:
```python
@dataclass(frozen=True)
class Site:
    activation_time: Distribution  # Reference only
    enrollment_rate: Distribution  # Reference only
```

❌ **Violation**:
```python
class Site:
    def get_activation_time(self):
        return self.activation_time.sample()  # Entity sampling (NO!)
```

**Test**: No entity method calls `.sample()`

---

### 2. All Uncertainty Is Explicit

**Rule**: If it varies, it must be a distribution or parameter. No hidden variance.

**Why**: Two organizations with same mean but different variance have different risk profiles.

✅ **Correct**:
```python
# Mean AND variance explicit
response_curve = StochasticLinearResponseCurve(
    mean_curve=LinearResponseCurve(min_speed_ratio=0.5),
    variance_distribution=Triangular(-0.3, 0, 0.3)  # ±30% variance
)
```

❌ **Violation**:
```python
# Only mean specified, variance hidden in code
multiplier = 1.0 / budget_ratio + random.random() * 0.5  # Hidden variance!
```

**Test**: All randomness uses explicit seed + distribution

---

### 3. Assumptions Are Parameters

**Rule**: Business rules that vary between organizations must be parameters, not code.

**Why**: Calibration means updating assumptions, not rewriting logic.

✅ **Correct**:
```python
constraint = BudgetThrottlingConstraint(
    budget_per_day=50000,
    response_curve=LinearResponseCurve(min_speed_ratio=0.5)  # Parameter
)
```

❌ **Violation**:
```python
def evaluate(self, ...):
    max_slowdown = 2.0  # Hardcoded assumption (NO!)
    multiplier = min(duration / baseline, max_slowdown)
```

**Test**: No magic numbers in constraint logic (see `test_calibration_readiness.py`)

---

### 4. Metrics Observe, Never Influence

**Rule**: Metrics are write-only during execution, read-only after.

**Why**: Reading metrics to adjust behavior = heuristic optimization, not simulation.

✅ **Correct**:
```python
state.metrics["events_rescheduled"] += 1  # Write only
# Later, after run: analyze run_result.metrics
```

❌ **Violation**:
```python
if state.metrics["events_rescheduled"] > 100:
    skip_constraint()  # Reading metrics to change behavior (NO!)
```

**Test**: Source code check for conditional reads of metrics

---

### 5. Scenarios Are Pre-Processing

**Rule**: Scenarios produce new trials via pure functions. Engine never sees scenarios.

**Why**: Keeps engine simple, scenarios version-controllable, calibration transparent.

✅ **Correct**:
```python
modified_trial = apply_scenario(base_trial, scenario)  # Pure function
results = engine.run(modified_trial)  # Engine sees trial only
```

❌ **Violation**:
```python
results = engine.run(trial, scenario=scenario)  # Engine coupled to scenarios (NO!)
```

**Test**: Engine signature accepts only `Trial`, not `Scenario`

---

### 6. Determinism Is Sacred

**Rule**: Same seed + same inputs → identical outputs. Always.

**Why**: Reproducibility enables validation, debugging, and trust.

✅ **Correct**:
```python
engine = SimulationEngine(master_seed=42)
results1 = engine.run(trial, num_runs=100)
results2 = engine.run(trial, num_runs=100)
assert results1.completion_time_p50 == results2.completion_time_p50  # Identical
```

❌ **Violation**:
```python
# Using system time or unseeded random
import time
delay = random.random() * time.time()  # Non-deterministic (NO!)
```

**Test**: Run twice with same seed, assert identical results

---

### 7. Outputs Reference Inputs

**Rule**: Simulation outputs must contain or reference all inputs that produced them.

**Why**: Defensibility requires traceability. "P90 is 119 days" needs "because these assumptions."

✅ **Correct**:
```python
output = EnhancedSimulationOutput(
    provenance=ProvenanceRecord(simulation_id, seed, ...),
    input_specification=InputSpecification.from_trial(trial, scenario),
    aggregated_results=AggregatedResults(...)
)
```

**Test**: Can reconstruct simulation from output.input_specification

---

## Examples: Applying The Ilana Law

### Example 1: Maximum Slowdown

**Question**: "Could max slowdown be different for a different organization?"

**Answer**: YES - Some orgs slow 2x with budget cuts, others 10x

**Conclusion**: Assumption → Parameter

**Before**:
```python
multiplier = 1.0 / max(0.5, budget_ratio)  # Hidden 2x cap
```

**After**:
```python
response_curve = LinearResponseCurve(min_speed_ratio=0.5)  # Explicit 2x cap
```

---

### Example 2: Time Negativity

**Question**: "Could time negativity be different for a different organization?"

**Answer**: NO - Time cannot be negative (universal physical law)

**Conclusion**: Structural → OK to hardcode

**Correct**:
```python
if time < 0:
    raise ValueError("Time cannot be negative")  # Structural check (OK)
```

---

### Example 3: Default Target Enrollment

**Question**: "Could default target enrollment be different for a different organization?"

**Answer**: YES - Trials range from 10 patients to 10,000

**Conclusion**: Assumption → Must be explicit (no default)

**Wrong**:
```python
@dataclass
class Trial:
    target_enrollment: int = 100  # Hidden assumption (NO!)
```

**Correct**:
```python
@dataclass
class Trial:
    target_enrollment: int  # Required, no default (YES!)
```

---

### Example 4: Triangular Distribution Shape

**Question**: "Could triangular shape be different for a different organization?"

**Answer**: NO - Triangular is a mathematical form (low, mode, high)

**Conclusion**: Structural → Parameters are explicit, formula is not

**Correct**:
```python
class Triangular(Distribution):
    def sample(self, seed):
        # Formula is structural (universal math)
        return scipy.stats.triang(...).rvs(random_state=seed)
```

---

## Anti-Patterns

### Anti-Pattern 1: Hidden Business Logic

**Symptom**: Numeric literals in constraint logic

**Example**:
```python
if budget_ratio < 0.3:  # Why 0.3? (hidden threshold)
    return blocked()
```

**Fix**: Extract to parameter
```python
if budget_ratio < self.minimum_viable_ratio:  # Explicit parameter
    return blocked()
```

---

### Anti-Pattern 2: Sampling in Entities

**Symptom**: Entity methods call `distribution.sample()`

**Example**:
```python
class Site:
    def get_activation_time(self):
        return self.activation_time.sample()  # Entity executing (NO!)
```

**Fix**: Engine samples, entity holds reference
```python
# In engine:
activation_time = site.activation_time.sample(event_seed)
```

---

### Anti-Pattern 3: Implicit Defaults

**Symptom**: Optional parameters with assumption-based defaults

**Example**:
```python
def __init__(self, max_slowdown: float = 2.0):  # Hidden assumption (NO!)
```

**Fix**: Make behavior explicit
```python
def __init__(self, response_curve: BudgetResponseCurve):  # Explicit behavior (YES!)
```

---

### Anti-Pattern 4: Customer-Specific Logic

**Symptom**: Code that only makes sense for one organization

**Example**:
```python
if trial.trial_id.startswith("SCRI_"):  # Customer-specific logic (NO!)
    apply_special_rules()
```

**Fix**: Make rules parametric
```python
if trial.special_rules:  # General mechanism (YES!)
    apply_rules(trial.special_rules)
```

---

## Enforcement Strategy

### 1. Automated Tests

**File**: `tests/test_calibration_readiness.py`

Tests check:
- No magic numbers in constraint logic
- Constraints accept behavior objects, not literals
- No hardcoded response formulas
- Structural checks only (no assumption-based conditionals)

**When they fail**: Extract assumption to parameter or update architectural rule

---

### 2. Code Review Checklist

Before merging new constraints or entities:

- [ ] Apply The Ilana Law to every numeric literal
- [ ] Check: Does this vary between organizations?
- [ ] If YES: Extract to parameter/distribution
- [ ] If NO: Document why it's structural
- [ ] Run `pytest tests/test_calibration_readiness.py`

---

### 3. Documentation Requirements

Every parameter that represents an assumption must document:

- **What it controls**: "Maximum slowdown under budget pressure"
- **Why it varies**: "Different organizations have different resource flexibility"
- **How to calibrate**: "Collect historical budget vs duration data, fit curve"
- **Default rationale**: "Expert estimate: 2x slowdown typical for clinical trials"

---

## Calibration Workflow

This architecture enables a clean calibration workflow:

### Week 1: Initial Simulation (Expert Estimates)
```python
# Use conservative assumptions
constraint = BudgetThrottlingConstraint(
    budget_per_day=50000,
    response_curve=LinearResponseCurve(min_speed_ratio=0.5)  # Expert: 2x max
)
results_v1 = engine.run(trial, constraints=[constraint])
```

### Week 5: Data Collection
```
SCRI collects actual data:
- 20 historical trials
- Budget cuts vs actual duration
- Finds: Mean 3x slowdown, high variance
```

### Week 6: Model Update (NO CODE CHANGE)
```python
from seleensim.distributions import Triangular

# Calibrated model: 3x mean, ±50% variance
mean_curve = LinearResponseCurve(min_speed_ratio=0.33)  # 3x max
variance_dist = Triangular(low=-0.5, mode=0.0, high=0.5)  # ±50%

constraint_v2 = BudgetThrottlingConstraint(
    budget_per_day=50000,
    response_curve=StochasticLinearResponseCurve(mean_curve, variance_dist)
)

results_v2 = engine.run(trial, constraints=[constraint_v2])
```

### Week 7: Impact Analysis
```python
print(f"Expert model P90: {results_v1.completion_time_p90} days")
print(f"Calibrated model P90: {results_v2.completion_time_p90} days")
print(f"Impact: {results_v2.completion_time_p90 - results_v1.completion_time_p90:+.0f} days")
```

**Key point**: Assumptions updated, code unchanged. That's calibration readiness.

---

## Summary

### The Core Rules

1. **The Ilana Law**: "Could this be different for another org?" → YES = parameter, NO = hardcode
2. **All uncertainty explicit**: If it varies, it's a distribution
3. **Entities are data**: No sampling, no business logic
4. **Metrics observe only**: Never influence execution
5. **Determinism is sacred**: Same seed = identical results
6. **Outputs reference inputs**: Full traceability

### The Test

**Can SCRI update assumptions without editing Python files?**

If NO: Architecture violation. Fix it.

If YES: Calibration-ready. Ship it.

---

## Version History

- **v1.0** (2026-02-14): Initial architectural principles
  - The Ilana Law formalized
  - Seven core guarantees defined
  - Anti-patterns documented
  - Enforcement strategy specified

---

## References

- `docs/ARCHITECTURAL_REVIEW_FINDINGS.md` - Detailed analysis of violation found
- `tests/test_calibration_readiness.py` - Automated enforcement tests
- `constraint_fix_v2_stochastic.py` - Example of correct architecture
- `docs/METRICS_INVARIANT.md` - Metrics principle details
- `docs/ENGINE_ORCHESTRATION.md` - Engine invariants
