# Scenario System Design

## Overview

A **scenario** is an explicit, declarative override profile that produces a modified trial specification without mutating the base.

**Key principle**: Scenarios are pure data transformations, not runtime state.

## Architecture

```
Base Trial Specification
    ↓
Scenario Override Profile (explicit modifications)
    ↓
apply_scenario(base, scenario) → Modified Trial Specification
    ↓
Simulation Engine (unchanged)
```

### Not This (Mutation)
```python
❌ scenario.apply(trial)  # Mutates trial
❌ trial.with_scenario(scenario)  # Hidden mutation
❌ engine.run(trial, scenario=scenario)  # Runtime merging
```

### This (Pure Function)
```python
✅ modified_trial = apply_scenario(base_trial, scenario)
✅ results = engine.run(modified_trial, num_runs=100)
```

## Core Design

### 1. ScenarioProfile (Explicit Override Map)

```python
@dataclass(frozen=True)
class ScenarioProfile:
    """
    Declarative override profile for trial specifications.

    Architectural Guarantees:
    - Immutable (frozen dataclass)
    - No execution logic
    - JSON-serializable
    - Explicit overrides only (no implicit inheritance)
    - Inspectable (all changes visible)

    Overrides are organized by entity type and ID.
    """
    scenario_id: str
    description: str
    version: str

    # Explicit override maps
    site_overrides: Dict[str, Dict[str, Any]]
    activity_overrides: Dict[str, Dict[str, Any]]
    resource_overrides: Dict[str, Dict[str, Any]]
    flow_overrides: Dict[str, Dict[str, Any]]
    trial_overrides: Dict[str, Any]

    # Metadata for comparison
    created_at: str
    based_on_scenario: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON for version control."""
        return {
            "scenario_id": self.scenario_id,
            "description": self.description,
            "version": self.version,
            "site_overrides": self.site_overrides,
            "activity_overrides": self.activity_overrides,
            "resource_overrides": self.resource_overrides,
            "flow_overrides": self.flow_overrides,
            "trial_overrides": self.trial_overrides,
            "created_at": self.created_at,
            "based_on_scenario": self.based_on_scenario
        }
```

### 2. Override Specification Format

Overrides specify **what** to change, **how** to change it, and **why**.

```python
# Example: Site activation delays increase 20%
site_overrides = {
    "SITE_001": {
        "activation_time": {
            "type": "distribution_scale",
            "parameters": {"scale_factor": 1.2},
            "reason": "Regulatory delays in EU region"
        }
    }
}

# Example: Resource capacity reduction
resource_overrides = {
    "MONITOR": {
        "capacity": {
            "type": "direct_value",
            "value": 3,  # Down from 5
            "reason": "Budget constraints"
        }
    }
}

# Example: Trial-level change
trial_overrides = {
    "target_enrollment": {
        "type": "direct_value",
        "value": 150,  # Down from 200
        "reason": "Revised enrollment target"
    }
}
```

### 3. Override Types (Explicit Transformations)

```python
class OverrideType(Enum):
    """Explicit types of overrides supported."""

    DIRECT_VALUE = "direct_value"
    # Replace deterministic value: capacity=5 → capacity=3

    DISTRIBUTION_REPLACE = "distribution_replace"
    # Replace entire distribution: Triangular(30,45,90) → LogNormal(mean=50, cv=0.3)

    DISTRIBUTION_SCALE = "distribution_scale"
    # Scale distribution parameters: Triangular(30,45,90) → Triangular(36,54,108) [1.2x]

    DISTRIBUTION_SHIFT = "distribution_shift"
    # Shift distribution: Triangular(30,45,90) → Triangular(40,55,100) [+10]

    DISTRIBUTION_PARAM = "distribution_param"
    # Modify specific parameter: Triangular(low=30, mode=45, high=90) → (low=25, ...)
```

### 4. apply_scenario() - Pure Function

```python
def apply_scenario(
    base_trial: Trial,
    scenario: ScenarioProfile
) -> Trial:
    """
    Apply scenario overrides to base trial specification.

    Pure function:
    - Does NOT mutate base_trial
    - Returns NEW Trial with overrides applied
    - Deterministic: same inputs → same output
    - No side effects

    Args:
        base_trial: Immutable base specification
        scenario: Explicit override profile

    Returns:
        New Trial specification with overrides applied

    Example:
        base = Trial(...)
        scenario = ScenarioProfile(
            scenario_id="DELAYED_ACTIVATION",
            site_overrides={"SITE_001": {"activation_time": {...}}}
        )

        modified = apply_scenario(base, scenario)

        # base is unchanged
        assert base.sites[0].activation_time == original_dist

        # modified has overrides
        assert modified.sites[0].activation_time == scaled_dist
    """
    # Apply overrides by constructing new entities
    modified_sites = _apply_site_overrides(base_trial.sites, scenario.site_overrides)
    modified_activities = _apply_activity_overrides(base_trial.activities, scenario.activity_overrides)
    modified_resources = _apply_resource_overrides(base_trial.resources, scenario.resource_overrides)
    modified_flow = _apply_flow_overrides(base_trial.patient_flow, scenario.flow_overrides)

    # Construct new Trial (immutable)
    modified_trial = Trial(
        trial_id=f"{base_trial.trial_id}__{scenario.scenario_id}",
        target_enrollment=_apply_trial_override(
            base_trial.target_enrollment,
            scenario.trial_overrides.get("target_enrollment")
        ),
        sites=modified_sites,
        patient_flow=modified_flow,
        activities=modified_activities,
        resources=modified_resources
    )

    return modified_trial
```

## Usage Patterns

### 1. Base + Scenario

```python
# Define base trial (best current estimates)
base_trial = Trial(
    trial_id="BASE_TRIAL_2026Q1",
    target_enrollment=200,
    sites=[
        Site(
            site_id="SITE_001",
            activation_time=Triangular(low=30, mode=45, high=90),
            enrollment_rate=Gamma(shape=2, scale=1.5),
            dropout_rate=Bernoulli(p=0.15)
        )
    ],
    patient_flow=flow
)

# Define scenario (what-if analysis)
delayed_activation = ScenarioProfile(
    scenario_id="DELAYED_ACTIVATION",
    description="EU regulatory delays extend activation by 20%",
    version="1.0.0",
    site_overrides={
        "SITE_001": {
            "activation_time": {
                "type": "distribution_scale",
                "parameters": {"scale_factor": 1.2},
                "reason": "EU regulatory environment"
            }
        }
    },
    activity_overrides={},
    resource_overrides={},
    flow_overrides={},
    trial_overrides={},
    created_at="2026-02-14T10:00:00Z"
)

# Apply scenario (pure function, no mutation)
modified_trial = apply_scenario(base_trial, delayed_activation)

# Run simulations
base_results = engine.run(base_trial, num_runs=100)
scenario_results = engine.run(modified_trial, num_runs=100)

# Compare
print(f"Base P50: {base_results.completion_time_p50:.1f} days")
print(f"Scenario P50: {scenario_results.completion_time_p50:.1f} days")
print(f"Impact: {scenario_results.completion_time_p50 - base_results.completion_time_p50:+.1f} days")
```

### 2. Multiple Scenarios (Comparable)

```python
scenarios = [
    ScenarioProfile(
        scenario_id="OPTIMISTIC",
        description="Fast activation, high enrollment",
        site_overrides={
            "SITE_001": {
                "activation_time": {
                    "type": "distribution_scale",
                    "parameters": {"scale_factor": 0.8}  # 20% faster
                }
            }
        },
        ...
    ),
    ScenarioProfile(
        scenario_id="PESSIMISTIC",
        description="Slow activation, low enrollment",
        site_overrides={
            "SITE_001": {
                "activation_time": {
                    "type": "distribution_scale",
                    "parameters": {"scale_factor": 1.3}  # 30% slower
                }
            }
        },
        ...
    ),
    ScenarioProfile(
        scenario_id="REDUCED_CAPACITY",
        description="Budget cuts reduce monitor capacity",
        resource_overrides={
            "MONITOR": {
                "capacity": {
                    "type": "direct_value",
                    "value": 3  # Down from 5
                }
            }
        },
        ...
    )
]

# Run all scenarios
results = {}
results["BASE"] = engine.run(base_trial, num_runs=100)

for scenario in scenarios:
    modified_trial = apply_scenario(base_trial, scenario)
    results[scenario.scenario_id] = engine.run(modified_trial, num_runs=100)

# Compare all
import pandas as pd
comparison = pd.DataFrame({
    scenario_id: {
        "P10": res.completion_time_p10,
        "P50": res.completion_time_p50,
        "P90": res.completion_time_p90
    }
    for scenario_id, res in results.items()
}).T

print(comparison)
```

### 3. Scenario Composition (Explicit)

```python
# Not automatic inheritance - explicit composition
def compose_scenarios(
    base: ScenarioProfile,
    overlay: ScenarioProfile
) -> ScenarioProfile:
    """
    Explicitly compose two scenarios.

    NOT automatic inheritance. User must call this explicitly.
    Returns NEW scenario with merged overrides.
    """
    return ScenarioProfile(
        scenario_id=f"{base.scenario_id}__AND__{overlay.scenario_id}",
        description=f"{base.description} + {overlay.description}",
        version=f"{base.version}+{overlay.version}",
        site_overrides={**base.site_overrides, **overlay.site_overrides},
        activity_overrides={**base.activity_overrides, **overlay.activity_overrides},
        resource_overrides={**base.resource_overrides, **overlay.resource_overrides},
        flow_overrides={**base.flow_overrides, **overlay.flow_overrides},
        trial_overrides={**base.trial_overrides, **overlay.trial_overrides},
        created_at=datetime.now().isoformat(),
        based_on_scenario=base.scenario_id
    )

# Explicit composition
delayed = ScenarioProfile(scenario_id="DELAYED", ...)
reduced_capacity = ScenarioProfile(scenario_id="REDUCED_CAPACITY", ...)

# User explicitly composes
combined = compose_scenarios(delayed, reduced_capacity)

# Result is inspectable
print(combined.scenario_id)  # "DELAYED__AND__REDUCED_CAPACITY"
print(combined.site_overrides)  # Merged overrides visible
```

## Version Control & Comparison

### 1. JSON Serialization

```python
# Serialize scenario to JSON
scenario_json = scenario.to_dict()
with open("scenarios/delayed_activation_v1.0.json", "w") as f:
    json.dump(scenario_json, f, indent=2)

# Version control friendly
# git add scenarios/delayed_activation_v1.0.json
# git commit -m "Add EU regulatory delay scenario"
```

### 2. Scenario Diffing

```python
def diff_scenarios(
    scenario_a: ScenarioProfile,
    scenario_b: ScenarioProfile
) -> Dict[str, Any]:
    """
    Compare two scenarios and return differences.

    Returns:
        Dict with added/removed/modified overrides
    """
    diff = {
        "scenario_a": scenario_a.scenario_id,
        "scenario_b": scenario_b.scenario_id,
        "site_changes": _diff_dicts(
            scenario_a.site_overrides,
            scenario_b.site_overrides
        ),
        "activity_changes": _diff_dicts(
            scenario_a.activity_overrides,
            scenario_b.activity_overrides
        ),
        # ... etc
    }
    return diff

# Compare scenarios
diff = diff_scenarios(optimistic, pessimistic)
print(json.dumps(diff, indent=2))
```

### 3. Scenario Evolution Tracking

```python
# Track how scenario impacts change over time as base calibrates

# Week 1: Initial base estimates
base_v1 = Trial(...)
scenario = ScenarioProfile(...)
modified_v1 = apply_scenario(base_v1, scenario)
results_v1 = engine.run(modified_v1, num_runs=100)

# Week 5: Calibrated base (better distributions from historical data)
base_v2 = Trial(...)  # Updated distributions
# Scenario definition UNCHANGED
modified_v2 = apply_scenario(base_v2, scenario)
results_v2 = engine.run(modified_v2, num_runs=100)

# Compare: How does same scenario affect calibrated vs initial base?
print("Impact of scenario on initial base:")
print(f"  P50: {results_v1.completion_time_p50:.1f} days")

print("Impact of scenario on calibrated base:")
print(f"  P50: {results_v2.completion_time_p50:.1f} days")

print("Change in scenario impact after calibration:")
print(f"  {results_v2.completion_time_p50 - results_v1.completion_time_p50:+.1f} days")
```

## Calibration Workflow

### The Pattern

```
1. Initial State
   └─ Base trial (expert estimates)
   └─ Scenarios (relative adjustments)
   └─ Run simulations

2. Collect Historical Data
   └─ Actual activation times, enrollment rates, etc.

3. Calibration
   └─ Fit distributions to historical data
   └─ Update base trial with calibrated distributions
   └─ Scenarios remain unchanged (relative adjustments)

4. Re-evaluate
   └─ Apply same scenarios to calibrated base
   └─ Compare: How do scenario impacts change?
   └─ Validate: Do scenarios still represent intended adjustments?

5. Scenario Refinement (if needed)
   └─ Adjust scenario override magnitudes
   └─ Version control changes
   └─ Document reasoning
```

### Example: Calibration Cycle

```python
# === WEEK 1: Initial Setup ===

# Base trial with expert estimates
base_trial_v1 = Trial(
    trial_id="BASE_v1.0",
    sites=[
        Site(
            site_id="SITE_001",
            activation_time=Triangular(low=30, mode=45, high=90),  # Expert estimate
            ...
        )
    ]
)

# Scenario: "What if activation takes 20% longer?"
delayed_scenario = ScenarioProfile(
    scenario_id="DELAYED_ACTIVATION",
    version="1.0.0",
    site_overrides={
        "SITE_001": {
            "activation_time": {
                "type": "distribution_scale",
                "parameters": {"scale_factor": 1.2}
            }
        }
    }
)

# Run base + scenario
base_results_v1 = engine.run(base_trial_v1, num_runs=100)
delayed_results_v1 = engine.run(
    apply_scenario(base_trial_v1, delayed_scenario),
    num_runs=100
)

print("Week 1 (Expert Estimates):")
print(f"  Base P50: {base_results_v1.completion_time_p50:.1f} days")
print(f"  Delayed P50: {delayed_results_v1.completion_time_p50:.1f} days")


# === WEEK 5: Calibration with Historical Data ===

# Historical data collected
historical_activation_times = [52, 48, 61, 55, 59, 50, 67, 53]

# Fit distribution to historical data
from seleensim.calibration import fit_distribution
calibrated_dist = fit_distribution(
    data=historical_activation_times,
    distribution_type="triangular"
)
# Returns: Triangular(low=48, mode=55, high=67)

# Create calibrated base trial
base_trial_v2 = Trial(
    trial_id="BASE_v2.0_CALIBRATED",
    sites=[
        Site(
            site_id="SITE_001",
            activation_time=calibrated_dist,  # Calibrated from data
            ...
        )
    ]
)

# Apply SAME scenario to calibrated base
delayed_results_v2 = engine.run(
    apply_scenario(base_trial_v2, delayed_scenario),  # Same scenario!
    num_runs=100
)

print("\nWeek 5 (Calibrated):")
print(f"  Base P50: {base_results_v2.completion_time_p50:.1f} days")
print(f"  Delayed P50: {delayed_results_v2.completion_time_p50:.1f} days")

# Analysis: How did calibration affect scenario impact?
initial_impact = delayed_results_v1.completion_time_p50 - base_results_v1.completion_time_p50
calibrated_impact = delayed_results_v2.completion_time_p50 - base_results_v2.completion_time_p50

print("\nScenario Impact:")
print(f"  Initial: +{initial_impact:.1f} days")
print(f"  Calibrated: +{calibrated_impact:.1f} days")
print(f"  Change: {calibrated_impact - initial_impact:+.1f} days")
```

## Architectural Guarantees

### ✅ Maintained

1. **Entities remain immutable**
   - `apply_scenario()` creates NEW Trial, doesn't mutate
   - Base trial unchanged after scenario application

2. **No runtime state**
   - Scenarios are pure data (frozen dataclasses)
   - No execution logic in ScenarioProfile

3. **Explicit uncertainty**
   - All overrides visible and documented
   - No hidden assumptions or magic merging

4. **Calibration-ready**
   - Base trial gets better distributions over time
   - Scenarios remain relative adjustments
   - Can track scenario impact evolution

5. **Serializable**
   - Scenarios serialize to JSON
   - Version control friendly
   - Diff-able

6. **Explainable**
   - Every override has reason field
   - Can trace modified trial back to base + scenario
   - Inspectable via `to_dict()`

### ❌ Violations Prevented

```python
# ❌ Runtime scenario switching
engine.run(trial, scenario=scenario)  # NO - engine doesn't know about scenarios

# ❌ Implicit inheritance
scenario2 = scenario1.extend(...)  # NO - explicit composition only

# ❌ Mutation
scenario.apply(trial)  # NO - scenarios don't mutate
trial.activate_scenario(scenario)  # NO - trials don't have methods

# ❌ Hidden state
scenario.current_overrides  # NO - all state in constructor
scenario.merged_profile  # NO - merging is explicit via compose_scenarios()
```

## File Structure

```
seleensim/
  scenarios.py          # ScenarioProfile, apply_scenario(), compose_scenarios()
  scenario_overrides.py # Override type implementations

scenarios/              # Version-controlled scenario definitions
  base/
    base_trial_v1.0.json
    base_trial_v2.0_calibrated.json

  planning/
    optimistic_v1.0.json
    pessimistic_v1.0.json
    reduced_capacity_v1.0.json

  regulatory/
    eu_delays_v1.0.json
    fda_expedited_v1.0.json

examples/
  scenario_usage.py
  calibration_workflow.py
```

## Key Benefits

### 1. Separation of Concerns
- Base trial = "Best current estimates"
- Scenarios = "What-if adjustments"
- Calibration updates base, scenarios stay relative

### 2. Comparability
- All scenarios start from same base
- Overrides are explicit and bounded
- Can quantify: "20% slower activation adds X days to P50"

### 3. Version Control
- JSON-serializable
- Git-friendly diffs
- Track scenario evolution over time

### 4. Calibration Support
- Base improves with data
- Scenarios remain meaningful
- Can validate: "Is 20% still the right adjustment?"

### 5. No Magic
- Pure functions (apply_scenario)
- Explicit composition (compose_scenarios)
- Inspectable (to_dict, diff_scenarios)
- No implicit behavior

## Implementation Notes

### Phase 1: Core Infrastructure
- `ScenarioProfile` dataclass
- `apply_scenario()` pure function
- Override types enum
- JSON serialization

### Phase 2: Override Implementations
- `_apply_site_overrides()`
- `_apply_activity_overrides()`
- Distribution scaling/shifting logic
- Validation (catch invalid overrides)

### Phase 3: Composition & Comparison
- `compose_scenarios()`
- `diff_scenarios()`
- Scenario versioning utilities

### Phase 4: Examples & Documentation
- `examples/scenario_usage.py`
- `examples/calibration_workflow.py`
- Integration with existing examples

## Summary

**The Design:**
- Scenarios are explicit override maps (pure data)
- `apply_scenario(base, scenario)` is pure function
- Returns NEW trial specification (no mutation)
- Scenarios are JSON-serializable (version control)
- Explicit composition (no implicit inheritance)

**How This Supports Calibration:**
- Base trial holds "best current estimates"
- Calibration updates base distributions with fitted values
- Scenarios remain relative adjustments
- Can track: "How does 20% delay scenario change as base improves?"
- Validates: "After calibration, is 20% still realistic?"

**Architectural Integrity:**
- Entities remain immutable ✅
- No runtime state ✅
- Explicit uncertainty ✅
- Serializable ✅
- Explainable ✅
- Pure functions ✅

The scenario system is a **pre-processing layer** that produces trial specifications. The simulation engine remains unchanged.
