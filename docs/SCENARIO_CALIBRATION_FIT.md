# How Scenarios Support Calibration Without Breaking Architecture

## The Challenge

**Problem**: We want to support "what-if" analysis (scenarios) AND iterative calibration (better distributions over time), while maintaining:
- Entity immutability
- No runtime state
- Explicit uncertainty
- Reproducibility

**Why This Is Hard**:
- Scenarios need to override assumptions
- Calibration updates assumptions
- Both need to coexist without creating mutable state or implicit behavior

## The Solution: Scenarios as Pre-Processing Layer

### Core Insight

**Scenarios are not runtime state. They're declarative transformations that produce trial specifications.**

```
Conceptual Layers:
┌─────────────────────────────────────────────────────────────┐
│ User Layer: Define scenarios (JSON, version controlled)     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Pre-Processing: apply_scenario(base, scenario) → trial      │
│ (Pure function, no mutation)                                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Simulation Layer: engine.run(trial) → results               │
│ (Engine never sees scenarios)                                │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

**1. Scenarios Produce New Trials (No Mutation)**

```python
# ✅ Correct: Pure function
modified_trial = apply_scenario(base_trial, scenario)

# base_trial unchanged
# modified_trial is NEW object
# Engine runs on modified_trial (standard Trial entity)
```

```python
# ❌ Wrong: Mutation or runtime state
engine.run(trial, scenario=scenario)  # NO - engine shouldn't know about scenarios
trial.apply_scenario(scenario)        # NO - trials don't have methods
scenario.apply_to(trial)              # NO - scenarios don't mutate
```

**2. Scenarios Reference Base, Don't Inherit From It**

```python
# Scenario doesn't contain full specification
# Just overrides (explicit deltas)

scenario = ScenarioProfile(
    scenario_id="DELAYED",
    site_overrides={
        "SITE_001": {
            "activation_time": {
                "type": "distribution_scale",
                "parameters": {"scale_factor": 1.2},
                "reason": "EU regulatory delays"
            }
        }
    }
    # Rest of trial comes from base
)

# apply_scenario() merges base + overrides → new trial
```

**3. Overrides Are Explicit and Inspectable**

```python
# Every override has:
# - Type (scale, shift, replace, etc.)
# - Parameters (scale_factor=1.2)
# - Reason (documentation)

scenario.to_dict()  # Full override map visible
diff_scenarios(scenario_a, scenario_b)  # Can compare
```

## How This Supports Calibration

### The Calibration Cycle

```
Week 1: Expert Estimates
├─ Base trial with expert distributions
├─ Define scenarios (relative adjustments)
└─ Run simulations

Week 2-4: Collect Data
├─ Historical activation times
├─ Historical enrollment rates
└─ Actual dropout rates

Week 5: Calibration
├─ Fit distributions to historical data
├─ Update base trial with calibrated distributions
├─ Scenarios REMAIN UNCHANGED (same relative adjustments)
└─ Apply scenarios to calibrated base

Week 6: Analysis
├─ Compare: Old base vs new base (calibration impact)
├─ Compare: Scenario impact on old vs new base
└─ Validate: Are scenario adjustments still realistic?
```

### Example Workflow

**Week 1: Initial Setup**

```python
# Base trial: Expert estimate activation mode=45 days
base_v1 = Trial(
    trial_id="BASE_v1.0",
    sites=[
        Site(
            site_id="SITE_001",
            activation_time=Triangular(low=30, mode=45, high=90)  # Expert
        )
    ]
)

# Scenario: "What if 20% slower?"
delayed_scenario = ScenarioProfile(
    scenario_id="DELAYED_ACTIVATION",
    version="1.0.0",
    site_overrides={
        "SITE_001": {
            "activation_time": {
                "type": "distribution_scale",
                "parameters": {"scale_factor": 1.2}  # 20% slower
            }
        }
    }
)

# Run simulations
base_results_v1 = engine.run(base_v1, num_runs=100)
delayed_results_v1 = engine.run(
    apply_scenario(base_v1, delayed_scenario),
    num_runs=100
)

# Results:
# Base P50: 52.1 days
# Delayed P50: 62.5 days
# Impact: +10.4 days (20% scenario adds ~10 days)
```

**Week 5: After Calibration**

```python
# Historical data collected: [52, 48, 61, 55, 59, 50, 67, 53]
# Actual mean activation: ~56 days (slower than expert estimate of 45)

# Fit distribution to data
from seleensim.calibration import fit_distribution
calibrated_dist = fit_distribution(
    data=[52, 48, 61, 55, 59, 50, 67, 53],
    distribution_type="triangular"
)
# Returns: Triangular(low=48, mode=56, high=67)

# Create calibrated base
base_v2 = Trial(
    trial_id="BASE_v2.0_CALIBRATED",
    sites=[
        Site(
            site_id="SITE_001",
            activation_time=calibrated_dist  # Calibrated: mode=56
        )
    ]
)

# Apply SAME scenario to calibrated base
delayed_results_v2 = engine.run(
    apply_scenario(base_v2, delayed_scenario),  # Same scenario!
    num_runs=100
)

# Results:
# Base P50: 61.3 days (was 52.1)
# Delayed P50: 73.5 days (was 62.5)
# Impact: +12.2 days (was +10.4)
```

**Week 6: Analysis**

```python
# Calibration changed base estimate
print("Base trial evolution:")
print(f"  v1 (expert): mode=45 days → P50=52.1 days")
print(f"  v2 (calibrated): mode=56 days → P50=61.3 days")
print(f"  Calibration impact: +9.2 days")

# Scenario impact evolved
print("\nScenario (20% delay) impact evolution:")
print(f"  On v1 base: +10.4 days")
print(f"  On v2 base: +12.2 days")
print(f"  Change: +1.8 days")

# Validation question
print("\nValidation: Is 20% still the right scenario adjustment?")
print(f"  Historical data showed activation ~24% slower than expert estimate")
print(f"  Scenario assumes 20% delay")
print(f"  → Consider updating scenario to 25% for realism")
```

### Key Benefits

**1. Base Improves Over Time**
- Week 1: Expert estimates (uncertain)
- Week 5: Fitted to data (more accurate)
- Future: Continuous refinement

**2. Scenarios Remain Relative**
- Defined as "20% slower" not "activation=54 days"
- Apply to any base (initial or calibrated)
- Comparable across base versions

**3. Traceability**
- Can answer: "How did calibration affect scenario impact?"
- Version control: base_v1.json, base_v2.json, scenario_v1.json
- Git diff shows exactly what changed

**4. Validation Built-In**
- Compare scenario assumptions to calibrated base
- Example: "We assumed 20% delay, but data shows 24%"
- Update scenario: `scale_factor: 1.2 → 1.24`

## Architectural Integrity Maintained

### ✅ Entities Remain Immutable

```python
# Scenarios don't mutate trials
modified = apply_scenario(base, scenario)
assert base.sites[0].activation_time.mode == 45  # Unchanged

# Scenarios themselves are immutable
scenario = ScenarioProfile(...)  # frozen=True
scenario.site_overrides = {}  # ❌ Error: can't assign to frozen instance
```

### ✅ No Runtime State

```python
# Scenarios are pure data (dataclasses)
class ScenarioProfile:
    scenario_id: str
    site_overrides: Dict[str, Dict[str, Any]]
    # No methods except to_dict/from_dict
    # No hidden state
    # No execution logic

# apply_scenario is pure function
def apply_scenario(base: Trial, scenario: ScenarioProfile) -> Trial:
    # No side effects
    # Same inputs → same output
    # Deterministic
```

### ✅ Explicit Uncertainty

```python
# Every override documented
scenario = ScenarioProfile(
    site_overrides={
        "SITE_001": {
            "activation_time": {
                "type": "distribution_scale",
                "parameters": {"scale_factor": 1.2},
                "reason": "EU regulatory delays"  # Explicit reasoning
            }
        }
    }
)

# Can inspect: What assumptions does this scenario make?
print(json.dumps(scenario.to_dict(), indent=2))
```

### ✅ Serializable

```python
# Version control scenarios
scenario_json = scenario.to_dict()
with open("scenarios/delayed_v1.0.json", "w") as f:
    json.dump(scenario_json, f, indent=2)

# Git tracks changes
# git diff scenarios/delayed_v1.0.json
# Can see: scale_factor changed from 1.2 to 1.24
```

### ✅ Engine Remains Pure

```python
# Engine never sees scenarios
# Only sees Trial entities

# This is the ONLY interface:
results = engine.run(trial, num_runs=100)

# NOT this:
# results = engine.run(trial, scenario=scenario)  # ❌ NO
# results = engine.run_with_overrides(...)         # ❌ NO
```

## Anti-Patterns Prevented

### ❌ Runtime Scenario Switching

```python
# WRONG: Engine knows about scenarios
class BadEngine:
    def run(self, trial, scenario=None):
        if scenario:
            trial = self._merge_scenario(trial, scenario)  # Runtime merging
        # This couples engine to scenario system
```

### ❌ Implicit Inheritance

```python
# WRONG: Scenarios inherit from base automatically
class BadScenario(BaseTrial):
    def __init__(self, base):
        super().__init__(**base.__dict__)  # Copy everything
        self.activation_time *= 1.2  # Hidden modification

# Can't tell what changed without code inspection
```

### ❌ Scenario State

```python
# WRONG: Scenarios have runtime state
class BadScenario:
    def __init__(self):
        self.times_applied = 0  # State!
        self.current_base = None  # State!

    def apply(self, trial):
        self.times_applied += 1  # Mutation!
        self.current_base = trial  # Mutation!
```

### ❌ Magic Merging

```python
# WRONG: Unclear how overrides combine
base = Trial(...)
scenario1 = Scenario(...)
scenario2 = Scenario(...)

# How do these combine? Order matters? Hidden rules?
result = base + scenario1 + scenario2  # ❌ Magic

# Correct: Explicit composition
combined_scenario = compose_scenarios(scenario1, scenario2)
result = apply_scenario(base, combined_scenario)  # ✅ Clear
```

## Summary: The Fit

**Problem**: Support scenarios + calibration without breaking architecture

**Solution**: Scenarios as pre-processing layer
- Scenarios = pure data (frozen dataclasses)
- apply_scenario = pure function (no mutation)
- Engine = unchanged (only sees Trial entities)

**How Calibration Works**:
1. Base trial gets better distributions over time
2. Scenarios remain relative adjustments (20% slower, not absolute values)
3. Apply same scenarios to improved base
4. Compare: How do scenario impacts evolve?
5. Validate: Are scenario assumptions still realistic?

**Architectural Guarantees Maintained**:
- ✅ Entities immutable (frozen dataclasses)
- ✅ No runtime state (scenarios are data)
- ✅ Pure functions (apply_scenario)
- ✅ Explicit uncertainty (documented overrides)
- ✅ Serializable (JSON, version control)
- ✅ Engine unchanged (pre-processing layer)

**The Key Insight**:

Scenarios are NOT:
- Runtime parameters to the engine
- Mutable objects with state
- Inheritance hierarchies
- Magic merging rules

Scenarios ARE:
- Declarative override specifications
- Input to pure transformation function
- Version-controlled assumption profiles
- Pre-processing step before simulation

This keeps the architecture clean while enabling the workflows users need.
