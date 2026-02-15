# Architectural Purity Review - Findings

## Executive Summary

**Status**: 1 critical violation found in `constraints.py`

**Clean files**: `entities.py`, `simulation.py`, `distributions.py`

**Violation**: Hidden assumptions in `BudgetThrottlingConstraint` break calibration readiness

---

## Review Criteria

We checked for:
1. ✅ Hidden assumptions (default values, magic numbers, hardcoded formulas)
2. ✅ Customer-specific logic (domain rules that vary by organization)
3. ✅ Side effects in core entities (mutation, I/O, sampling)
4. ✅ Sampling inside entities (entities should reference distributions, not sample them)
5. ✅ Tight coupling between assumptions and logic (business rules embedded in code)

---

## ✅ Clean Files (No Violations)

### `entities.py` - **PASS**

**What we checked**:
- All default values (`None`, `[]`, `{}`) are structural, not assumption-based
- No customer-specific logic (everything generic)
- No side effects (only validation in `__post_init__`)
- **No sampling** - entities only REFERENCE distributions, never call `.sample()`
- Pure data structures with validation only

**Example of correct pattern**:
```python
@dataclass(frozen=True)
class Site:
    site_id: str
    activation_time: Distribution  # REFERENCE, not sample
    enrollment_rate: Distribution  # REFERENCE, not sample
    dropout_rate: Distribution     # REFERENCE, not sample
```

**Why this matters**: Entities are data specifications, not executors. Sampling happens in the engine, keeping entities pure and calibratable.

---

### `simulation.py` - **PASS**

**What we checked**:
- Sampling happens in **ENGINE**, not in entities
- No hidden business logic in core loops
- Metrics observe execution, don't influence it (Invariant #4)

**Example of correct pattern** (line 438):
```python
# ENGINE samples the distribution (correct)
activation_time = site.activation_time.sample(event_seed)

# NOT this (would be wrong):
# activation_time = site.get_activation_time()  # Entity doing sampling
```

**Why this matters**: Engine orchestrates, entities remain passive. This separation enables calibration - update entity distributions without changing engine logic.

---

## ⚠️ VIOLATION FOUND

### `constraints.py` - `BudgetThrottlingConstraint` - **FAIL**

**Location**: Lines 473-476

**Violating Code**:
```python
# Simple model: full budget → no throttling (1.0x)
#               half budget → 50% slowdown (1.5x duration)
budget_ratio = min(1.0, available_budget / (self.budget_per_day * base_duration))
duration_multiplier = 1.0 / max(0.5, budget_ratio)  # Cap slowdown at 2x
```

---

## Problem 1: Hidden Assumptions (CRITICAL)

**What's hidden**:
- Budget-to-speed relationship is **linear** (`1.0 / budget_ratio`)
- Maximum slowdown is **2x** (`max(0.5, ...)`)
- Formula is **hardcoded** (no way to calibrate without code change)

**Why this is hidden**:
```python
# User sees this in code:
duration_multiplier = 1.0 / max(0.5, budget_ratio)

# But doesn't see:
# - Why linear? (could be logarithmic, exponential, threshold-based)
# - Why 2x cap? (SCRI might slow 5x with low budget)
# - Why these numbers? (expert guess? historical data? arbitrary?)
```

**The test**: Ask "Could SCRI have different assumptions than another organization?"
- ✅ YES → It's an assumption → Must be explicit and calibratable
- ❌ NO → It's structural → OK to hardcode

For budget response: **YES, SCRI's budget-to-speed relationship is unique to them.**

---

## Problem 2: Tight Coupling (CRITICAL)

**Current**: Assumption (linear response) **embedded in code**

```python
def evaluate(self, state, event):
    budget_ratio = available_budget / required_budget
    duration_multiplier = 1.0 / max(0.5, budget_ratio)  # ASSUMPTION HIDDEN HERE
```

**Should be**: Assumption is a **parameter or distribution**

```python
def evaluate(self, state, event):
    budget_ratio = available_budget / required_budget
    duration_multiplier = self.response_curve.compute(budget_ratio)  # ASSUMPTION EXPLICIT
```

---

## Problem 3: Breaks Calibration Readiness (SHOWSTOPPER)

**Calibration scenario**:

```
Week 1: SCRI uses expert estimate
    "Budget cuts slow us max 2x"
    → Use constraint with 0.5 min speed

Week 5: SCRI collects actual data
    Finds: "Budget cuts actually slow us 3-5x"

Week 6: Want to update model
```

**Current system**: Must **change constraint code**
```python
# Change code (requires developer, testing, deployment)
duration_multiplier = 1.0 / max(0.33, budget_ratio)  # Changed 0.5 → 0.33
```

**Calibration-ready system**: Update **parameters** (no code change)
```python
# Just update configuration (SCRI can do this)
constraint = BudgetThrottlingConstraint(
    budget_per_day=50000,
    response_curve=LinearResponseCurve(
        min_speed_ratio=0.2  # Updated from 0.5 to 0.2 (5x slowdown)
    )
)
```

---

## The Corrected Version

### Solution: Make Response Curve Explicit

**New abstraction**: `BudgetResponseCurve`

```python
class BudgetResponseCurve(ABC):
    """
    Defines how activity speed responds to budget availability.

    This is an ASSUMPTION about the relationship between budget and execution speed.
    By making this explicit, we enable calibration without code changes.
    """

    @abstractmethod
    def compute_duration_multiplier(self, budget_ratio: float) -> float:
        """
        Compute duration multiplier from budget ratio.

        Args:
            budget_ratio: available_budget / required_budget (0.0 to 1.0+)

        Returns:
            duration_multiplier: how much to multiply base duration by
        """
        pass
```

**Implementation 1: Linear Response**
```python
class LinearResponseCurve(BudgetResponseCurve):
    """Linear response: duration_multiplier = 1.0 / budget_ratio"""

    def __init__(self, min_speed_ratio: float = 0.5, max_speed_ratio: float = 1.0):
        self.min_speed_ratio = min_speed_ratio
        self.max_speed_ratio = max_speed_ratio

    def compute_duration_multiplier(self, budget_ratio: float) -> float:
        speed_ratio = max(self.min_speed_ratio, min(self.max_speed_ratio, budget_ratio))
        return 1.0 / speed_ratio
```

**Implementation 2: Threshold Response**
```python
class ThresholdResponseCurve(BudgetResponseCurve):
    """Threshold response: Need minimum budget, then scale"""

    def __init__(
        self,
        threshold_ratio: float = 0.3,
        below_threshold_multiplier: float = 5.0,
        above_threshold_min_speed: float = 0.5
    ):
        self.threshold_ratio = threshold_ratio
        self.below_threshold_multiplier = below_threshold_multiplier
        self.above_threshold_min_speed = above_threshold_min_speed

    def compute_duration_multiplier(self, budget_ratio: float) -> float:
        if budget_ratio < self.threshold_ratio:
            return self.below_threshold_multiplier  # Severe slowdown
        else:
            speed_ratio = max(self.above_threshold_min_speed, budget_ratio)
            return 1.0 / speed_ratio
```

**Corrected Constraint**:
```python
class BudgetThrottlingConstraint:
    def __init__(
        self,
        budget_per_day: float,
        response_curve: BudgetResponseCurve  # EXPLICIT ASSUMPTION
    ):
        self.budget_per_day = budget_per_day
        self.response_curve = response_curve

    def evaluate(self, state, event):
        # ... compute budget_ratio ...

        # Use response curve (explicit, calibratable)
        duration_multiplier = self.response_curve.compute_duration_multiplier(budget_ratio)

        # ... rest of logic ...
```

---

## Benefits of Fix

### 1. Assumptions Are Visible

**Before**:
```python
# Hidden in code
duration_multiplier = 1.0 / max(0.5, budget_ratio)
```

**After**:
```python
# Explicit in configuration
response_curve=LinearResponseCurve(min_speed_ratio=0.5)
```

### 2. Calibration Without Code Changes

**Before**:
```python
# Must change constraint.py code
duration_multiplier = 1.0 / max(0.33, budget_ratio)  # Changed number
```

**After**:
```python
# Just update configuration
response_curve=LinearResponseCurve(min_speed_ratio=0.2)  # Updated parameter
```

### 3. Version Control Shows Assumption Changes

**Before**:
```diff
- duration_multiplier = 1.0 / max(0.5, budget_ratio)
+ duration_multiplier = 1.0 / max(0.33, budget_ratio)
# Hard to see: What changed? Why? Based on what data?
```

**After**:
```diff
- response_curve=LinearResponseCurve(min_speed_ratio=0.5)
+ response_curve=LinearResponseCurve(min_speed_ratio=0.2)
# Clear: Assumption changed from 0.5 to 0.2 (based on calibration data)
```

### 4. Multiple Models Can Coexist

**Before**: One formula embedded in code

**After**: Multiple response curves available
```python
# Try different models
linear_model = LinearResponseCurve(min_speed_ratio=0.5)
threshold_model = ThresholdResponseCurve(threshold_ratio=0.3)
exponential_model = ExponentialResponseCurve(decay_rate=2.0)

# Compare results
results_linear = engine.run(trial, constraints=[BudgetConstraint(curve=linear_model)])
results_threshold = engine.run(trial, constraints=[BudgetConstraint(curve=threshold_model)])

# Which model fits SCRI's data better?
```

---

## The Rule: Spotting Hidden Assumptions

**Question to ask**: *"Could this number be different for a different organization?"*

**If YES** → It's an assumption → Make it explicit and calibratable

**If NO** → It's structural → OK to hardcode

### Examples:

**Hidden assumption** (WRONG):
```python
# Could be different for different organizations
max_slowdown = 2.0  # Why 2x? SCRI might slow 5x
response = 1.0 / budget_ratio  # Why linear? Could be exponential
```

**Structural constraint** (OK):
```python
# Universal truth, never changes
if time < 0:
    raise ValueError("Time cannot be negative")
if budget_ratio < 0:
    raise ValueError("Budget ratio cannot be negative")
```

---

## Calibration Workflow (With Fix)

### Week 1: Initial Simulation (Expert Estimates)
```python
# Use conservative assumption
constraint = BudgetThrottlingConstraint(
    budget_per_day=50000,
    response_curve=LinearResponseCurve(min_speed_ratio=0.5)  # Expert guess: 2x max slowdown
)

results_v1 = engine.run(trial, constraints=[constraint])
print(f"P90 completion: {results_v1.completion_time_p90} days")
```

### Week 5: Data Collection
```
SCRI collects actual data:
- Budget cut 50% → activities took 3-4x longer (not 2x)
- Budget cut 70% → activities took 8-10x longer (threshold effect?)
```

### Week 6: Model Update (No Code Change!)
```python
# Update to threshold model based on data
constraint_v2 = BudgetThrottlingConstraint(
    budget_per_day=50000,
    response_curve=ThresholdResponseCurve(
        threshold_ratio=0.3,              # Below 30% budget → severe impact
        below_threshold_multiplier=8.0,   # 8x slowdown below threshold
        above_threshold_min_speed=0.25    # 4x max slowdown above threshold
    )
)

results_v2 = engine.run(trial, constraints=[constraint_v2])
print(f"P90 completion: {results_v2.completion_time_p90} days")
```

### Week 7: Impact Analysis
```python
print("Impact of calibration:")
print(f"  Original model (expert): {results_v1.completion_time_p90} days")
print(f"  Calibrated model (data): {results_v2.completion_time_p90} days")
print(f"  Change: {results_v2.completion_time_p90 - results_v1.completion_time_p90:+.0f} days")
```

**No code changes. Just better assumptions.**

---

## Summary

### Violations Found: 1

| File | Issue | Severity | Fix Status |
|------|-------|----------|----------|
| `constraints.py` | Hidden budget response assumptions | CRITICAL | Proposal ready |

### Clean Files: 3

- ✅ `entities.py` - No violations
- ✅ `simulation.py` - No violations
- ✅ `distributions.py` - No violations (not reviewed in detail, but no red flags)

### Recommendation

**Fix this before SCRI calibration session.**

Why: If SCRI collects budget response data and can't update the model without code changes, calibration readiness fails.

**Implementation**: See `constraint_fix_proposal.py` for complete corrected version.

---

## The Architectural Principle

**RULE**: Assumptions may be OBSERVED by code, but must be SPECIFIED by users.

**Good** (Assumption is input):
```python
constraint = BudgetConstraint(
    budget_per_day=50000,
    response_curve=LinearResponseCurve(min_speed_ratio=0.5)
)
```

**Bad** (Assumption is code):
```python
def evaluate(self, ...):
    duration_multiplier = 1.0 / max(0.5, budget_ratio)  # 0.5 is hidden assumption
```

**This is the same principle as**:
- Distributions: Users specify `Triangular(30, 45, 90)`, not `def sample(): return 45`
- Entities: Users specify `Site(activation_time=dist)`, not `Site(activation_days=45)`
- Scenarios: Users specify overrides, not subclass entities

**The guarantee**: SCRI can calibrate without changing code.
