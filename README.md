# SeleenSIM

A calibration-ready, probabilistic simulation engine for clinical trial planning.

## Design Principles

### The Ilana Law

> **"Could this number be different for a different organization?"**
>
> **YES** → It's an **assumption** → Must be **parameterized**
> **NO** → It's **structural** → OK to **hardcode**

This single question enforces calibration readiness. If SCRI collects data showing "actually 5x slowdown, not 2x," they should update a **parameter**, not edit **code**.

### Core Principles

- **No hardcoded assumptions**: No real-world defaults or customer-specific logic
- **Explicit uncertainty**: All uncertainty modeled as probability distributions
- **Calibration-ready**: Architecture supports recalibration without refactor
- **Explainable**: Every output traceable to inputs
- **Clarity over performance**: Correctness and maintainability first

**Critical documents**:
- `ARCHITECTURE_LOCK.md` - **Defines what can/cannot change** (boundary enforcement)
- `docs/ARCHITECTURAL_PRINCIPLES.md` - The Ilana Law and core guarantees
- `docs/GUARDRAILS.md` - How architecture is protected by CI
- `docs/SCRI_CALIBRATION_PREP.md` - **Next step: validate with real users**

### Guardrail Enforcement

**Automated architectural tests** enforce The Ilana Law via CI:

- **Calibration readiness tests** detect hardcoded assumptions in constraints
- **Anti-behavior tests** prevent entities from sampling or computing
- **CI blocks PRs** if guardrail tests fail (treated as architecture regressions)

Example guardrail:
```python
def test_budget_constraint_has_no_hardcoded_response_logic():
    """Verify no patterns like: 1.0 / max(0.5, budget_ratio)"""
    source = inspect.getsource(BudgetThrottlingConstraint.evaluate)
    assert 'max(0.5' not in source  # Blocks hardcoded assumptions
```

See `docs/GUARDRAILS.md` for complete enforcement policy and examples.

## Current Status

**Implemented**:
- Core probability distribution framework (4 distributions, 40 tests)
- Entity models for trial specifications (5 entities, 38 tests)
- Constraint evaluation system (4 constraint types, 63 tests)
  - BudgetThrottlingConstraint with injectable response curves ✓
  - ResourceCapacityConstraint with injectable response curves ✓
- Monte Carlo simulation engine with constraint integration (20 tests)
- Scenario system for assumption overrides (15 tests)
- Output schema and provenance tracking (12 tests)
- Calibration readiness guardrails (8 tests)
- Anti-behavior guardrails (20 tests)
- **216 tests passing** - Calibration-ready with automated guardrails

## Distribution Framework

### Interface

All distributions implement:

```python
class Distribution(ABC):
    def sample(seed: int) -> float
    def mean() -> float
    def percentile(p: float) -> float
    def to_dict() -> Dict[str, Any]
```

**Key features**:
- Stateless sampling with explicit seeds for reproducibility
- Optional bounds enforcement via rejection sampling
- JSON serialization for calibration workflows
- No fitted state or hidden assumptions

### Supported Distributions

#### Triangular(low, mode, high)
For expert elicitation using three-point estimates.

```python
from seleensim.distributions import Triangular

dist = Triangular(low=10, mode=30, high=60, bounds=(15, 55))
sample = dist.sample(seed=42)
mean = dist.mean()
p90 = dist.percentile(90)
```

**Parameters**:
- `low`: Pessimistic scenario
- `mode`: Most likely value
- `high`: Optimistic scenario

#### LogNormal(mean, cv)
For right-skewed positive quantities.

```python
from seleensim.distributions import LogNormal

dist = LogNormal(mean=50, cv=0.3, bounds=(20, 100))
```

**Parameters**:
- `mean`: Expected value
- `cv`: Coefficient of variation (std/mean)

#### Gamma(shape, scale)
For flexible positive quantities with controllable skew.

```python
from seleensim.distributions import Gamma

dist = Gamma(shape=2, scale=5, bounds=(5, 30))
```

**Parameters**:
- `shape`: Controls skewness (α)
- `scale`: Controls spread (θ)
- Mean = shape × scale

#### Bernoulli(p)
For binary events.

```python
from seleensim.distributions import Bernoulli

dist = Bernoulli(p=0.7)
```

**Parameters**:
- `p`: Probability of success (returns 1)

### Serialization

Distributions serialize to/from JSON for calibration workflows:

```python
import json
from seleensim.distributions import Triangular, from_dict

# Serialize
dist = Triangular(low=10, mode=30, high=60)
data = dist.to_dict()
json_str = json.dumps(data)

# Deserialize
loaded = json.loads(json_str)
reconstructed = from_dict(loaded)

# Produces identical samples
assert dist.sample(seed=42) == reconstructed.sample(seed=42)
```

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Entity Models

Trial specifications are built from immutable entities that reference distributions but never sample them.

### Core Entities

**Site** - Enrollment location
```python
from seleensim.entities import Site
from seleensim.distributions import Triangular, Gamma, Bernoulli

site = Site(
    site_id="SITE_001",
    activation_time=Triangular(30, 45, 90),  # Stochastic: uncertain timing
    enrollment_rate=Gamma(2, 1.5),            # Stochastic: uncertain rate
    dropout_rate=Bernoulli(0.15),             # Stochastic: uncertain probability
    max_capacity=50                           # Deterministic: hard constraint
)
```

**Activity** - Task with dependencies and duration
```python
from seleensim.entities import Activity

activity = Activity(
    activity_id="SITE_ACTIVATION",
    duration=LogNormal(30, 0.2),              # Stochastic: uncertain duration
    dependencies={"IRB_APPROVAL"},            # Deterministic: known dependencies
    required_resources={"MONITOR"},           # Deterministic: known requirements
    success_probability=Bernoulli(0.95)       # Stochastic: uncertain success
)
```

**Resource** - Constrained resource
```python
from seleensim.entities import Resource

resource = Resource(
    resource_id="MONITOR",
    resource_type="staff",                    # Deterministic: categorization
    capacity=5,                               # Deterministic: hard limit
    availability=Bernoulli(0.90),             # Stochastic: uncertain availability
    utilization_rate=Gamma(3, 15)             # Stochastic: uncertain consumption
)
```

**PatientFlow** - State machine for entity transitions
```python
from seleensim.entities import PatientFlow

flow = PatientFlow(
    flow_id="STANDARD",
    states={"enrolled", "active", "completed"},           # Deterministic: state space
    initial_state="enrolled",                             # Deterministic: start state
    terminal_states={"completed"},                        # Deterministic: end states
    transition_times={                                    # Stochastic: uncertain timing
        ("enrolled", "active"): Triangular(7, 14, 30),
        ("active", "completed"): LogNormal(180, 0.3)
    }
)
```

**Trial** - Top-level container
```python
from seleensim.entities import Trial

trial = Trial(
    trial_id="TRIAL_001",
    target_enrollment=200,                    # Deterministic: goal
    sites=[site1, site2, site3],              # Deterministic: which sites
    patient_flow=flow,                        # Stochastic structure
    activities=[act1, act2],                  # Optional
    resources=[res1, res2]                    # Optional
)
```

### Deterministic vs Stochastic Fields

**Deterministic** (structure, known at design time):
- Entity IDs and relationships
- Target enrollment, capacity limits
- Dependency graphs, state machine structure
- Resource types and categorizations

**Stochastic** (uncertainty, modeled as distributions):
- Activation times, durations
- Enrollment rates, dropout probabilities
- Resource availability and utilization
- Transition timing and probabilities

### Key Design Constraints

✅ **Immutable**: Entities are frozen dataclasses, cannot be modified after creation
✅ **Reference-only**: Entities hold Distribution objects, never sample them
✅ **No business logic**: Entities are pure data holders, no methods like `enroll()` or `activate()`
✅ **No defaults**: All parameters must be explicitly provided
✅ **Fail loudly**: Validation errors raised at construction time
✅ **Serializable**: All entities support `to_dict()` for JSON export

See `examples/trial_specification.py` for a complete working example.

## Constraint Evaluation System

Constraints define rules that simulation events must satisfy. The system separates **validity** (hard gates) from **feasibility** (soft modifiers).

### Two-Layer Architecture

**Validity Constraints** answer: "Can this event occur at all at time T?"
- Returns: `is_valid`, `earliest_valid_time`
- Examples: Temporal precedence, activity dependencies
- Blocks invalid events, reschedules to earliest valid time

**Feasibility Constraints** answer: "How efficiently can this event occur?"
- Returns: `delay`, `parameter_overrides`
- Examples: Resource capacity, budget throttling
- Modifies execution parameters or delays until resources available

### Constraint Types

```python
from seleensim.constraints import (
    TemporalPrecedenceConstraint,      # Validity: Event B requires Event A first
    PredecessorConstraint,              # Validity: Activity requires predecessors
    ResourceCapacityConstraint,         # Feasibility: Wait for resource availability
    BudgetThrottlingConstraint          # Feasibility: Throttle speed based on budget
)

# Example: Enrollment cannot start before site activation
constraint = TemporalPrecedenceConstraint(
    predecessor_event_type="site_activation",
    dependent_event_type="enrollment"
)

result = constraint.evaluate(state, event)
if not result.is_valid:
    # Engine reschedules to result.earliest_valid_time
    print(result.explanation)  # "Site must activate before enrollment..."
```

### Key Features

**✅ Explicit objects**: Constraints are first-class objects with clear interfaces
**✅ Explainable**: Every result includes human-readable explanation
**✅ Domain-agnostic**: Constraints reason about time, resources, dependencies (not trials)
**✅ Composable**: Multiple constraints combine via documented rules
**✅ Idempotent throttling**: Budget decisions cached in `event.execution_parameters`
**✅ Extensible**: New constraints follow same interface, no engine refactor

### Composition Rules

```python
# Engine computes combined effect:
new_time = max(earliest_valid_time, proposed_time + delay)

# Composition rules:
is_valid = AND(all validity constraints)
earliest_valid_time = MAX(all earliest_valid_times)
delay = MAX(all delays)
parameter_overrides = MERGE(all overrides)
```

See `ENGINE_ORCHESTRATION.md` for complete engine processing loop specification.

## Monte Carlo Simulation Engine

Deterministic simulation engine that integrates constraints with event processing.

### Core Design

**Single Run vs Aggregated Results**:
- **Single run**: ONE realization showing HOW events unfold (timeline, causality)
  - Use for: Debugging, understanding mechanisms, storytelling
- **Aggregated results**: DISTRIBUTION of outcomes showing RANGE (P10/P50/P90)
  - Use for: Risk assessment, planning, decision making
- **Both needed**: Single runs explain mechanisms, aggregated results quantify uncertainty

**Key Features**:
- ✅ Deterministic execution (same seed → identical results)
- ✅ Constraint integration following canonical orchestration loop
- ✅ Forward time propagation via priority queue
- ✅ Independent runs (no shared mutable state)
- ✅ Per-event deterministic seeding
- ✅ Backward compatible (works with or without constraints)

### Usage

```python
from seleensim.simulation import SimulationEngine
from seleensim.constraints import TemporalPrecedenceConstraint

# Create trial specification
trial = Trial(...)

# Engine without constraints (MVP mode)
engine = SimulationEngine(master_seed=42, constraints=None)
results = engine.run(trial, num_runs=100)

# Engine with constraints
constraints = [
    TemporalPrecedenceConstraint("site_activation", "enrollment")
]
engine = SimulationEngine(master_seed=42, constraints=constraints)
results = engine.run(trial, num_runs=100)

# Single run inspection
run = results.get_run(0)
print(f"Completion: {run.completion_time:.1f} days")
for time, event_type, entity_id, description in run.timeline[:5]:
    print(f"T={time:.1f}: {event_type} - {description}")

# Aggregated statistics
print(f"P10: {results.completion_time_p10:.1f} days")
print(f"P50: {results.completion_time_p50:.1f} days")
print(f"P90: {results.completion_time_p90:.1f} days")
```

See `examples/monte_carlo_simulation.py` for complete demonstration of single vs aggregated outputs.
See `examples/constraint_integration.py` for constraint usage patterns.

## Scenario System

Scenarios are explicit assumption override profiles that enable "what-if" analysis without mutating base specifications.

### Core Design

**Key Principle**: Scenarios are pure data transformations, not runtime state.

```
Base Trial → apply_scenario(base, scenario) → Modified Trial → Simulation
```

**Architectural Guarantees**:
- ✅ Immutable (frozen dataclasses)
- ✅ Pure functions (`apply_scenario` doesn't mutate)
- ✅ Explicit overrides only (no implicit inheritance)
- ✅ JSON-serializable (version control friendly)
- ✅ Supports calibration workflow

### Usage

```python
from seleensim.scenarios import ScenarioProfile, apply_scenario

# Define base trial (best current estimates)
base_trial = Trial(...)

# Define scenario (explicit overrides)
delayed_scenario = ScenarioProfile(
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
    }
)

# Apply scenario (pure function - no mutation)
modified_trial = apply_scenario(base_trial, delayed_scenario)

# Base unchanged
assert base_trial.sites[0].activation_time.mode == 45

# Modified has scaled distribution
assert modified_trial.sites[0].activation_time.mode == 54

# Run simulations
base_results = engine.run(base_trial, num_runs=100)
scenario_results = engine.run(modified_trial, num_runs=100)

# Compare
print(f"Base P50: {base_results.completion_time_p50:.1f} days")
print(f"Scenario P50: {scenario_results.completion_time_p50:.1f} days")
print(f"Impact: {scenario_results.completion_time_p50 - base_results.completion_time_p50:+.1f} days")
```

### Override Types

- **`distribution_scale`**: Multiply parameters by factor (e.g., 20% slower activation)
- **`distribution_shift`**: Add constant to parameters (e.g., +10 days)
- **`distribution_param`**: Modify specific parameters (e.g., change mode only)
- **`distribution_replace`**: Replace entire distribution
- **`direct_value`**: Replace deterministic value (e.g., capacity=3)

### Calibration Workflow

Scenarios support iterative calibration:

1. **Week 1**: Base trial with expert estimates, run scenarios
2. **Week 5**: Collect historical data, fit distributions
3. **Week 5**: Update base trial with calibrated distributions
4. **Week 5**: Apply *same scenarios* to calibrated base
5. **Analysis**: Compare how scenario impacts evolve

**Key Insight**: Base improves with data, scenarios remain relative adjustments.

```python
# Initial base (expert estimates)
base_v1 = Trial(
    sites=[Site(activation_time=Triangular(30, 45, 90))]  # Expert estimate
)

# After calibration (historical data)
base_v2 = Trial(
    sites=[Site(activation_time=Triangular(28, 40, 65))]  # Fitted from data
)

# Same scenario applied to both
scenario = ScenarioProfile(
    site_overrides={"SITE_001": {"activation_time": {"type": "distribution_scale", "parameters": {"scale_factor": 1.2}}}}
)

results_v1 = engine.run(apply_scenario(base_v1, scenario), num_runs=100)
results_v2 = engine.run(apply_scenario(base_v2, scenario), num_runs=100)

# Compare: How does scenario impact change after calibration?
```

See `docs/SCENARIO_DESIGN.md` for complete design specification.
See `examples/scenario_usage.py` for comprehensive examples including calibration workflow.

## Testing

```bash
source venv/bin/activate
pytest tests/ -v
```

**189 tests** covering:
- **Distributions** (39 tests): Determinism, bounds, parameter validation, serialization, statistical properties
- **Entities** (45 tests): Immutability, type safety, structural integrity, validation, no business logic
- **Anti-behavior** (20 tests): Enforce architectural guarantees
- **Constraints** (29 tests): Validity vs feasibility, composition, idempotent throttling, explainability
- **Simulation** (37 tests): Determinism, event processing, single vs aggregated results, constraint integration, metrics invariant
- **Scenarios** (19 tests): Immutability, pure functions, override types, composition, serialization, architectural guarantees

### Anti-Behavior Tests

These tests actively verify entities do NOT violate architectural constraints:
- ✅ No sampling of distributions
- ✅ No mutation after construction
- ✅ No computed properties
- ✅ No execution methods
- ✅ No runtime state
- ✅ Only `to_dict()` exposed as public method

**These tests fail if someone adds forbidden behavior.** See `ARCHITECTURE.md` for full details.

## Architecture

This codebase implements a **calibration-ready simulation engine** with four core layers:

1. **Distributions** - Stateless probability distributions with explicit seeding
2. **Entities** - Immutable trial specifications (no sampling, no execution)
3. **Constraints** - Pure evaluation functions (validity gates + feasibility modifiers)
4. **Simulation** - Deterministic Monte Carlo engine integrating constraints

### Design Discipline

Every component follows strict architectural rules:
- **No hardcoded assumptions** - No real-world defaults or customer logic
- **Explicit uncertainty** - All randomness modeled as distributions
- **Calibration-ready** - Architecture supports recalibration without refactor
- **Explainable** - Every output traceable to inputs
- **Clarity over performance** - Correctness and maintainability first

See `ARCHITECTURE.md` for complete architectural guarantees and enforcement strategy.
See `ENGINE_ORCHESTRATION.md` for canonical event processing loop specification.
See `METRICS_INVARIANT.md` for critical rule on metrics usage (observe, never influence).
