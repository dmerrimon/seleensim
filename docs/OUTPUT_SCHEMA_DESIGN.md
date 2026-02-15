# Simulation Output Schema Design

## Overview

Simulation outputs must be **defensible, traceable, and reproducible**. Every result must link back to the inputs that produced it.

**Key Principle**: Outputs are structured data for analysis, not UI components.

## Design Requirements

1. **Input Traceability**: Every output references the inputs that influenced it
2. **Percentile Results**: P10/P50/P90 (and arbitrary percentiles)
3. **Variance Attribution**: Identify which inputs drive variability
4. **Determinism**: Same inputs + seed → identical outputs
5. **Structured Data**: JSON-serializable, no UI logic
6. **Provenance**: Track what/when/how simulation ran

## Core Output Schema

```python
@dataclass
class SimulationOutput:
    """
    Complete simulation output with full traceability.

    This is the top-level output structure returned to users.
    Contains everything needed to defend results and reproduce them.
    """
    # === Provenance ===
    provenance: ProvenanceRecord
    # Who/what/when/how this simulation ran

    # === Input References ===
    input_specification: InputSpecification
    # Complete snapshot of inputs (trial, scenario, constraints)

    # === Results ===
    aggregated_results: AggregatedResults
    # Percentile statistics across all runs

    single_run_results: List[SingleRunResult]
    # Individual run details (for debugging/understanding)

    # === Variance Analysis ===
    variance_attribution: VarianceAttribution
    # Which inputs drive the most variability

    # === Comparison (optional) ===
    comparison_baseline: Optional[str] = None
    # If this is a scenario, reference to base simulation
```

### 1. Provenance Record

**Purpose**: Track execution context for reproducibility and audit.

```python
@dataclass
class ProvenanceRecord:
    """
    Execution context for reproducibility.

    Answers: "How was this simulation produced?"
    """
    # Execution identity
    simulation_id: str  # Unique ID for this simulation run
    execution_timestamp: str  # ISO 8601: "2026-02-14T10:30:00Z"

    # Software versions
    seleensim_version: str  # "0.1.0"
    python_version: str  # "3.13.7"

    # Configuration
    num_runs: int  # 100
    master_seed: int  # 42
    initial_budget: float  # inf

    # Runtime
    execution_duration_seconds: float  # 2.34

    # Environment (optional)
    hostname: Optional[str] = None
    user: Optional[str] = None
```

**Use Case**: Reproducibility
```python
# Someone questions results 6 months later
provenance = output.provenance

print(f"Simulation ID: {provenance.simulation_id}")
print(f"Executed: {provenance.execution_timestamp}")
print(f"SeleenSIM version: {provenance.seleensim_version}")
print(f"Master seed: {provenance.master_seed}")
print(f"Runs: {provenance.num_runs}")

# Can reproduce exactly:
# 1. Use same seleensim version
# 2. Use same master seed
# 3. Use same input specification
# → Get identical results
```

### 2. Input Specification

**Purpose**: Snapshot of ALL inputs that influenced this simulation.

```python
@dataclass
class InputSpecification:
    """
    Complete snapshot of simulation inputs.

    Answers: "What assumptions produced these results?"
    """
    # Trial specification
    trial_spec: Dict[str, Any]  # Trial.to_dict() snapshot

    # Scenario applied (if any)
    scenario_profile: Optional[Dict[str, Any]] = None  # ScenarioProfile.to_dict()

    # Constraints used
    constraints: List[Dict[str, Any]] = field(default_factory=list)
    # [constraint.to_dict() for constraint in constraints]

    # Distribution parameters (extracted for quick reference)
    distribution_summary: Dict[str, Any] = field(default_factory=dict)
    # {
    #     "SITE_001.activation_time": {"type": "Triangular", "low": 30, "mode": 45, "high": 90},
    #     "SITE_001.enrollment_rate": {"type": "Gamma", "shape": 2, "scale": 1.5},
    #     ...
    # }

    # Deterministic parameters (for quick reference)
    deterministic_summary: Dict[str, Any] = field(default_factory=dict)
    # {
    #     "target_enrollment": 200,
    #     "num_sites": 3,
    #     "MONITOR.capacity": 5,
    #     ...
    # }
```

**Use Case**: Traceability
```python
# Stakeholder asks: "Why did you assume 45 day activation?"
input_spec = output.input_specification

activation_dist = input_spec.distribution_summary["SITE_001.activation_time"]
print(f"Site activation: {activation_dist}")
# Output: {"type": "Triangular", "low": 30, "mode": 45, "high": 90}

# If scenario applied:
if input_spec.scenario_profile:
    print(f"Scenario: {input_spec.scenario_profile['scenario_id']}")
    print(f"Overrides: {input_spec.scenario_profile['site_overrides']}")

# Full trial spec available:
trial_data = input_spec.trial_spec
# Can deserialize: trial = Trial.from_dict(trial_data)
```

### 3. Aggregated Results

**Purpose**: Percentile statistics across all runs (for planning/budgeting).

```python
@dataclass
class AggregatedResults:
    """
    Statistical summary across N simulation runs.

    Answers: "What range of outcomes should we expect?"
    """
    # Sample size
    num_runs: int  # 100

    # Completion time percentiles (days)
    completion_time: PercentileDistribution
    # {
    #     "p10": 78.5,
    #     "p25": 92.3,
    #     "p50": 110.2,
    #     "p75": 128.7,
    #     "p90": 145.3,
    #     "p95": 158.9,
    #     "mean": 112.1,
    #     "std": 23.4,
    #     "min": 65.2,
    #     "max": 178.3
    # }

    # Cost percentiles (if tracked)
    total_cost: PercentileDistribution

    # Enrollment percentiles (if tracked)
    enrollment_duration: Optional[PercentileDistribution] = None

    # Site-level statistics
    site_results: Dict[str, SiteAggregatedResults] = field(default_factory=dict)
    # {
    #     "SITE_001": {
    #         "activation_time": PercentileDistribution(...),
    #         "enrollment_count": PercentileDistribution(...),
    #         "dropout_count": PercentileDistribution(...)
    #     },
    #     ...
    # }

    # Event statistics
    events_processed: PercentileDistribution
    events_rescheduled: PercentileDistribution
    constraint_violations: PercentileDistribution


@dataclass
class PercentileDistribution:
    """Standard statistical summary."""
    p10: float
    p25: float
    p50: float  # Median
    p75: float
    p90: float
    p95: float
    mean: float
    std: float
    min: float
    max: float

    def range_p10_p90(self) -> float:
        """Variability measure: P90 - P10."""
        return self.p90 - self.p10
```

**Use Case**: Budget Defense
```python
results = output.aggregated_results

# Conservative planning
p90_days = results.completion_time.p90
p90_cost = results.total_cost.p90

print(f"Timeline (90% confidence): {p90_days:.0f} days")
print(f"Budget (90% confidence): ${p90_cost:,.0f}")

# Variability quantification
variability = results.completion_time.range_p10_p90()
print(f"Variability (P10-P90 spread): {variability:.0f} days")

# Justification:
# "We ran 100 Monte Carlo simulations with these inputs [reference input_spec].
#  90% of scenarios complete within {p90_days} days.
#  We recommend budgeting for the P90 case: {p90_days} days, ${p90_cost:,.0f}."
```

### 4. Single Run Results

**Purpose**: Individual run details for understanding and debugging.

```python
@dataclass
class SingleRunResult:
    """
    One simulation run result.

    Answers: "How did THIS specific trial unfold?"
    """
    run_id: int  # 0-99
    seed: int  # Deterministic seed for this run

    # Final outcomes
    completion_time: float  # 127.3 days
    total_cost: float  # $2,150,000
    target_achieved: bool  # True

    # Timeline (causality)
    timeline: List[TimelineEntry]
    # [
    #     (time=0.0, event_type="simulation_start", entity_id="TRIAL", description="..."),
    #     (time=51.2, event_type="site_activation", entity_id="SITE_001", description="..."),
    #     (time=127.3, event_type="trial_completion", entity_id="TRIAL", description="..."),
    # ]

    # Metrics
    events_processed: int
    events_rescheduled: int
    constraint_violations: int

    # State snapshots (optional, for detailed analysis)
    final_state: Optional[Dict[str, Any]] = None


@dataclass
class TimelineEntry:
    """Event in simulation timeline."""
    time: float  # Absolute simulation time
    event_type: str  # "site_activation", "enrollment", etc.
    entity_id: str  # "SITE_001", "PATIENT_023", etc.
    description: str  # Human-readable description
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional context
```

**Use Case**: Debugging Outliers
```python
# Why was run #47 so slow?
outlier_run = output.single_run_results[47]

print(f"Run #{outlier_run.run_id}")
print(f"  Completion: {outlier_run.completion_time:.1f} days")
print(f"  Seed: {outlier_run.seed}")

# Inspect timeline
print("\nTimeline (first 10 events):")
for entry in outlier_run.timeline[:10]:
    print(f"  T={entry.time:6.1f}: {entry.event_type:20s} {entry.entity_id}")

# Find bottleneck
activation_events = [e for e in outlier_run.timeline if e.event_type == "site_activation"]
print(f"\nSite activations:")
for event in activation_events:
    print(f"  {event.entity_id}: T={event.time:.1f}")

# Insight: "Site_003 activated unusually late (T=145), delaying everything downstream"
```

### 5. Variance Attribution

**Purpose**: Identify which inputs drive variability (sensitivity analysis).

```python
@dataclass
class VarianceAttribution:
    """
    Identifies which inputs contribute most to outcome variability.

    Answers: "What assumptions matter most?"

    Method: Computes correlation between input samples and output.
    High correlation → input is a variance driver.
    """
    # Overall variance
    outcome_variance: float  # Variance of completion_time across runs

    # Top drivers (sorted by contribution)
    drivers: List[VarianceDriver]
    # [
    #     VarianceDriver(
    #         input_name="SITE_001.activation_time",
    #         variance_contribution=0.45,  # 45% of total variance
    #         correlation=0.67,
    #         description="Site 001 activation timing"
    #     ),
    #     VarianceDriver(
    #         input_name="SITE_002.enrollment_rate",
    #         variance_contribution=0.23,  # 23% of total variance
    #         correlation=-0.48,
    #         description="Site 002 enrollment rate"
    #     ),
    #     ...
    # ]

    # Sensitivity summary (top N drivers account for X% of variance)
    top_n_coverage: Dict[int, float]
    # {
    #     3: 0.78,   # Top 3 drivers → 78% of variance
    #     5: 0.89,   # Top 5 drivers → 89% of variance
    #     10: 0.96   # Top 10 drivers → 96% of variance
    # }


@dataclass
class VarianceDriver:
    """Single input contributing to variance."""
    input_name: str  # "SITE_001.activation_time"
    input_type: str  # "distribution" or "deterministic"

    # Contribution to outcome variance
    variance_contribution: float  # 0.0 to 1.0 (45% = 0.45)
    correlation: float  # -1.0 to 1.0
    # Positive: higher input → higher completion time
    # Negative: higher input → lower completion time

    # Statistical significance
    p_value: float  # 0.001 (highly significant)

    # Human-readable
    description: str  # "Site 001 activation timing"
    impact_description: str  # "Longer activation → longer trial completion"
```

**Use Case**: Sensitivity Analysis
```python
variance = output.variance_attribution

print("Top Variance Drivers:")
for i, driver in enumerate(variance.drivers[:5], 1):
    print(f"{i}. {driver.input_name}")
    print(f"   Contribution: {driver.variance_contribution*100:.1f}%")
    print(f"   Correlation: {driver.correlation:+.2f}")
    print(f"   {driver.impact_description}")
    print()

# Insight for stakeholders:
print(f"Top 3 drivers account for {variance.top_n_coverage[3]*100:.0f}% of variability")

# Risk mitigation:
# "Site_001 activation timing drives 45% of trial duration variability.
#  To reduce risk, consider:
#  1. Starting Site_001 activation early
#  2. Adding backup sites
#  3. Improving Site_001 regulatory process"
```

### 6. Comparison Results (Optional)

**Purpose**: Compare scenario to baseline.

```python
@dataclass
class ComparisonResults:
    """
    Comparison between two simulations (e.g., base vs scenario).

    Answers: "What's the impact of this scenario?"
    """
    baseline_id: str  # "BASE_TRIAL_2026Q1"
    comparison_id: str  # "BASE_TRIAL_2026Q1__DELAYED_ACTIVATION"

    # Completion time comparison
    completion_time_delta: PercentileDistribution
    # {
    #     "p50": +12.3,  # Scenario adds 12.3 days at median
    #     "p90": +18.7,  # Scenario adds 18.7 days at P90
    #     ...
    # }

    # Relative change
    completion_time_pct_change: PercentileDistribution
    # {
    #     "p50": +11.2,  # 11.2% increase at median
    #     ...
    # }

    # Cost comparison (if applicable)
    cost_delta: Optional[PercentileDistribution] = None
    cost_pct_change: Optional[PercentileDistribution] = None

    # Scenario-specific insights
    scenario_impact_summary: str
    # "20% activation delay adds 12.3 days (11%) to median completion time"
```

**Use Case**: Scenario Impact
```python
comparison = output.comparison_results

print(f"Scenario: {comparison.comparison_id}")
print(f"Baseline: {comparison.baseline_id}")
print()

print("Impact on Completion Time:")
print(f"  P50: {comparison.completion_time_delta.p50:+.1f} days ({comparison.completion_time_pct_change.p50:+.1f}%)")
print(f"  P90: {comparison.completion_time_delta.p90:+.1f} days ({comparison.completion_time_pct_change.p90:+.1f}%)")
print()

print(f"Summary: {comparison.scenario_impact_summary}")

# Decision making:
# "This scenario adds 12 days to median timeline.
#  If regulatory delays materialize, expect +11% duration.
#  Budget should include contingency for this risk."
```

## Complete Output Example

```python
output = SimulationOutput(
    provenance=ProvenanceRecord(
        simulation_id="sim_abc123",
        execution_timestamp="2026-02-14T10:30:00Z",
        seleensim_version="0.1.0",
        python_version="3.13.7",
        num_runs=100,
        master_seed=42,
        initial_budget=float('inf'),
        execution_duration_seconds=2.34
    ),

    input_specification=InputSpecification(
        trial_spec={
            "trial_id": "BASE_TRIAL_2026Q1",
            "target_enrollment": 200,
            "sites": [...],
            ...
        },
        scenario_profile=None,  # No scenario
        constraints=[],
        distribution_summary={
            "SITE_001.activation_time": {"type": "Triangular", "low": 30, "mode": 45, "high": 90},
            "SITE_001.enrollment_rate": {"type": "Gamma", "shape": 2, "scale": 1.5},
        },
        deterministic_summary={
            "target_enrollment": 200,
            "num_sites": 3
        }
    ),

    aggregated_results=AggregatedResults(
        num_runs=100,
        completion_time=PercentileDistribution(
            p10=78.5, p25=92.3, p50=110.2, p75=128.7, p90=145.3, p95=158.9,
            mean=112.1, std=23.4, min=65.2, max=178.3
        ),
        total_cost=PercentileDistribution(...),
        events_processed=PercentileDistribution(...)
    ),

    single_run_results=[
        SingleRunResult(run_id=0, seed=42, completion_time=127.3, ...),
        SingleRunResult(run_id=1, seed=43, completion_time=98.7, ...),
        # ... 98 more
    ],

    variance_attribution=VarianceAttribution(
        outcome_variance=547.56,
        drivers=[
            VarianceDriver(
                input_name="SITE_001.activation_time",
                input_type="distribution",
                variance_contribution=0.45,
                correlation=0.67,
                p_value=0.001,
                description="Site 001 activation timing",
                impact_description="Longer activation → longer trial"
            ),
            VarianceDriver(
                input_name="SITE_002.enrollment_rate",
                input_type="distribution",
                variance_contribution=0.23,
                correlation=-0.48,
                p_value=0.003,
                description="Site 002 enrollment rate",
                impact_description="Higher enrollment → shorter trial"
            ),
            # ... more drivers
        ],
        top_n_coverage={3: 0.78, 5: 0.89, 10: 0.96}
    ),

    comparison_baseline=None  # Or "sim_xyz789" if comparing
)

# Serialize to JSON
output_json = output.to_dict()
with open("simulation_output_sim_abc123.json", "w") as f:
    json.dump(output_json, f, indent=2)
```

## Defending Budget/Timeline with These Outputs

### Scenario 1: Budget Committee Presentation

**Question**: "Why do you need $2.5M for this trial?"

**Answer Using Outputs**:

```python
output = load_simulation_output("sim_abc123.json")

# 1. Show probabilistic range
results = output.aggregated_results
print(f"Completion Time (90% confidence): {results.completion_time.p90:.0f} days")
print(f"Total Cost (90% confidence): ${results.total_cost.p90:,.0f}")

# 2. Reference inputs
inputs = output.input_specification
print(f"\nBased on {inputs.trial_spec['num_sites']} sites")
print(f"Target enrollment: {inputs.deterministic_summary['target_enrollment']}")
print(f"Site activation: {inputs.distribution_summary['SITE_001.activation_time']}")

# 3. Show provenance
prov = output.provenance
print(f"\n{prov.num_runs} Monte Carlo simulations")
print(f"Seed: {prov.master_seed} (reproducible)")

# 4. Identify risks
variance = output.variance_attribution
print(f"\nTop risk drivers:")
for driver in variance.drivers[:3]:
    print(f"  - {driver.description}: {driver.variance_contribution*100:.0f}% of variability")

# Budget justification:
# "Based on 100 Monte Carlo simulations of our trial design,
#  we are 90% confident completion within 145 days at $2.5M.
#  The top risk is Site_001 activation timing (45% of variability).
#  These assumptions are documented and reproducible (seed=42).
#  We recommend budgeting for P90 scenario to manage risk."
```

### Scenario 2: Sponsor Questions Assumptions

**Question**: "Why did you assume 45-day activation? That seems pessimistic."

**Answer Using Outputs**:

```python
# 1. Show exact assumption
inputs = output.input_specification
activation = inputs.distribution_summary["SITE_001.activation_time"]
print(f"Site activation assumption: {activation}")
# Output: {"type": "Triangular", "low": 30, "mode": 45, "high": 90}

# 2. Show sensitivity
variance = output.variance_attribution
activation_driver = [d for d in variance.drivers if "activation_time" in d.input_name][0]
print(f"\nActivation timing impact:")
print(f"  Variance contribution: {activation_driver.variance_contribution*100:.0f}%")
print(f"  Correlation: {activation_driver.correlation:+.2f}")

# 3. Show range of outcomes
results = output.aggregated_results
site_results = results.site_results["SITE_001"]
print(f"\nActual activation times in simulation:")
print(f"  P10: {site_results.activation_time.p10:.0f} days")
print(f"  P50: {site_results.activation_time.p50:.0f} days")
print(f"  P90: {site_results.activation_time.p90:.0f} days")

# Response:
# "We used Triangular(30, 45, 90) for activation timing.
#  This is a major driver (45% of trial duration variability).
#  In our simulations, 50% of runs had activation <50 days.
#
#  If you have data suggesting faster activation, we can:
#  1. Recalibrate the distribution (e.g., Triangular(25, 38, 70))
#  2. Re-run simulations with same seed
#  3. Compare impact on timeline and budget
#
#  This demonstrates why explicit assumptions matter."
```

### Scenario 3: Executive Review (Comparison)

**Question**: "What happens if Site_001 experiences regulatory delays?"

**Answer Using Outputs**:

```python
# Compare base vs delayed scenario
base_output = load_simulation_output("sim_base.json")
delayed_output = load_simulation_output("sim_delayed.json")

# Show comparison
comparison = delayed_output.comparison_results

print("Scenario: 20% Site_001 Activation Delay")
print(f"  Median impact: +{comparison.completion_time_delta.p50:.0f} days")
print(f"  P90 impact: +{comparison.completion_time_delta.p90:.0f} days")
print(f"  Cost impact: +${comparison.cost_delta.p50:,.0f}")

# Show inputs changed
delayed_scenario = delayed_output.input_specification.scenario_profile
print(f"\nScenario overrides:")
print(f"  {json.dumps(delayed_scenario['site_overrides'], indent=2)}")

# Decision support:
# "If Site_001 experiences 20% activation delay:
#  - Median completion extends by 12 days (11% increase)
#  - P90 completion extends by 19 days
#  - Additional cost: $230K
#
#  Risk mitigation options:
#  1. Start Site_001 activation earlier (reduce impact)
#  2. Add backup Site_004 (redundancy)
#  3. Include 20-day contingency in timeline
#
#  We can simulate each mitigation option and compare."
```

### Scenario 4: Audit/Regulatory Review

**Question**: "How did you arrive at these projections? Can you reproduce them?"

**Answer Using Outputs**:

```python
output = load_simulation_output("sim_abc123.json")

# 1. Full provenance
prov = output.provenance
print("Simulation Provenance:")
print(f"  ID: {prov.simulation_id}")
print(f"  Timestamp: {prov.execution_timestamp}")
print(f"  Software: SeleenSIM v{prov.seleensim_version}")
print(f"  Python: v{prov.python_version}")
print(f"  Seed: {prov.master_seed}")
print(f"  Runs: {prov.num_runs}")

# 2. Complete input snapshot
inputs = output.input_specification
print(f"\nInput Specification:")
print(f"  Trial: {inputs.trial_spec['trial_id']}")
print(f"  Distributions: {len(inputs.distribution_summary)} parameters")
print(f"  Scenario: {inputs.scenario_profile['scenario_id'] if inputs.scenario_profile else 'None'}")

# 3. Reproducibility instructions
print("\nTo Reproduce:")
print(f"  1. Install SeleenSIM v{prov.seleensim_version}")
print(f"  2. Load trial spec from: input_specification.trial_spec")
print(f"  3. Load scenario from: input_specification.scenario_profile")
print(f"  4. Run: engine.run(trial, num_runs={prov.num_runs}, master_seed={prov.master_seed})")
print(f"  5. Verify: output.aggregated_results.completion_time.p50 == {output.aggregated_results.completion_time.p50:.2f}")

# Audit compliance:
# "All simulation parameters are documented and version-controlled.
#  Using the provided seed ({prov.master_seed}), anyone can reproduce these results exactly.
#  The input specification is serialized in the output file.
#  This ensures transparency and auditability."
```

### Scenario 5: Risk Management Discussion

**Question**: "What are the biggest risks to this timeline?"

**Answer Using Outputs**:

```python
variance = output.variance_attribution

print("Top Timeline Risks (Variance Drivers):")
for i, driver in enumerate(variance.drivers[:5], 1):
    print(f"\n{i}. {driver.description}")
    print(f"   Variance contribution: {driver.variance_contribution*100:.0f}%")
    print(f"   Impact: {driver.impact_description}")
    print(f"   Statistical significance: p={driver.p_value:.3f}")

print(f"\nTop 3 drivers account for {variance.top_n_coverage[3]*100:.0f}% of variability")

# Risk mitigation priorities:
risks_by_contribution = sorted(variance.drivers, key=lambda d: d.variance_contribution, reverse=True)

print("\nRecommended Risk Mitigation Focus:")
for i, risk in enumerate(risks_by_contribution[:3], 1):
    print(f"{i}. Address {risk.input_name} ({risk.variance_contribution*100:.0f}% impact)")

# Risk-based planning:
# "Site_001 activation timing is the #1 risk (45% of variability).
#  Mitigation options:
#  1. Start activation process 30 days earlier
#  2. Allocate dedicated regulatory resource
#  3. Add parallel site as backup
#
#  We can simulate each option and show impact on P90 completion time."
```

## Key Advantages of This Schema

### 1. Full Traceability

Every output traces to inputs:
```
Result → Input Specification → Trial Spec → Distributions → Parameters
```

Can answer: "Why did we get X?" with precise input references.

### 2. Reproducibility

Provenance record enables exact reproduction:
```python
# 6 months later, reproduce exactly:
output_old = load_simulation_output("sim_abc123.json")
trial = Trial.from_dict(output_old.input_specification.trial_spec)
engine = SimulationEngine(master_seed=output_old.provenance.master_seed)
output_new = engine.run(trial, num_runs=output_old.provenance.num_runs)

assert output_new.aggregated_results.completion_time.p50 == output_old.aggregated_results.completion_time.p50
```

### 3. Risk Quantification

Variance attribution identifies what matters:
- Focus mitigation on top drivers
- Ignore low-impact assumptions
- Prioritize calibration efforts

### 4. Scenario Analysis

Comparison results show:
- Delta between base and scenario
- Percentage change
- Impact on percentiles
- Cost of risk materialization

### 5. Defensible Estimates

P90 planning is defensible:
- "90% confidence" is meaningful (100 simulations)
- Explicit assumptions (input specification)
- Reproducible (provenance)
- Risk-adjusted (variance attribution)

## Implementation Notes

### Phase 1: Core Schema
- `ProvenanceRecord`
- `InputSpecification`
- `AggregatedResults` with `PercentileDistribution`
- Enhance existing `SimulationResults` class

### Phase 2: Variance Attribution
- Implement sensitivity analysis
- Correlate input samples with outcomes
- Rank variance drivers
- Statistical testing

### Phase 3: Comparison
- `ComparisonResults` for scenario vs base
- Delta computation
- Percentage change
- Impact summary generation

### Phase 4: Serialization
- JSON export/import
- Schema versioning
- Backward compatibility

## Summary

**The Schema Enables**:
- Budget defense: "90% confidence in $2.5M based on 100 simulations"
- Timeline defense: "145 days at P90, accounting for top risks"
- Assumption defense: "All inputs documented, reproducible with seed=42"
- Risk prioritization: "Site activation drives 45% of variability"
- Scenario analysis: "20% delay adds 12 days to median timeline"

**The Key**: Every number in the output links back to an assumption in the input.

No hand-waving. No hidden logic. Just structured data and explicit traceability.
