"""
Example: Constraint Integration with Simulation Engine

Demonstrates:
1. Running simulations with constraints enabled
2. Validity constraints (temporal precedence)
3. Feasibility constraints (resource capacity, budget throttling)
4. How constraints affect simulation outcomes
5. Constraint impact on timelines and metrics
"""

from seleensim.entities import Site, Trial, PatientFlow
from seleensim.distributions import Triangular, Gamma, Bernoulli
from seleensim.simulation import SimulationEngine
from seleensim.constraints import (
    TemporalPrecedenceConstraint,
    ResourceCapacityConstraint,
    BudgetThrottlingConstraint,
    LinearResponseCurve
)


def demonstrate_without_constraints():
    """Baseline: Simulation without any constraints."""
    print("\n" + "=" * 80)
    print("BASELINE: SIMULATION WITHOUT CONSTRAINTS")
    print("=" * 80)
    print("\nNo constraint evaluation → events process immediately")

    # Build simple trial
    site = Site(
        site_id="SITE_001",
        activation_time=Triangular(low=30, mode=45, high=90),
        enrollment_rate=Gamma(shape=2, scale=1.5),
        dropout_rate=Bernoulli(p=0.15)
    )

    flow = PatientFlow(
        flow_id="STANDARD_FLOW",
        states={"enrolled", "completed"},
        initial_state="enrolled",
        terminal_states={"completed"},
        transition_times={(("enrolled", "completed")): Triangular(low=90, mode=180, high=365)}
    )

    trial = Trial(
        trial_id="BASELINE_TRIAL",
        target_enrollment=200,
        sites=[site],
        patient_flow=flow
    )

    # Engine without constraints
    engine = SimulationEngine(master_seed=42, constraints=None)
    results = engine.run(trial, num_runs=10)

    print(f"\nResults (10 runs):")
    print(f"  P10: {results.completion_time_p10:.1f} days")
    print(f"  P50: {results.completion_time_p50:.1f} days")
    print(f"  P90: {results.completion_time_p90:.1f} days")
    print(f"  Events rescheduled: {results.mean_events_rescheduled:.1f}")
    print(f"  Constraint violations: 0 (no constraints)")

    return results


def demonstrate_with_validity_constraints():
    """Simulation with validity constraints (temporal precedence)."""
    print("\n" + "=" * 80)
    print("WITH VALIDITY CONSTRAINTS")
    print("=" * 80)
    print("\nTemporal precedence: Enrollment requires site activation first")

    # Build trial
    site = Site(
        site_id="SITE_001",
        activation_time=Triangular(low=30, mode=45, high=90),
        enrollment_rate=Gamma(shape=2, scale=1.5),
        dropout_rate=Bernoulli(p=0.15)
    )

    flow = PatientFlow(
        flow_id="STANDARD_FLOW",
        states={"enrolled", "completed"},
        initial_state="enrolled",
        terminal_states={"completed"},
        transition_times={(("enrolled", "completed")): Triangular(low=90, mode=180, high=365)}
    )

    trial = Trial(
        trial_id="CONSTRAINED_TRIAL",
        target_enrollment=200,
        sites=[site],
        patient_flow=flow
    )

    # Define validity constraint
    constraints = [
        TemporalPrecedenceConstraint(
            predecessor_event_type="site_activation",
            dependent_event_type="enrollment"
        )
    ]

    # Engine with constraints
    engine = SimulationEngine(master_seed=42, constraints=constraints)
    results = engine.run(trial, num_runs=10)

    print(f"\nResults (10 runs):")
    print(f"  P10: {results.completion_time_p10:.1f} days")
    print(f"  P50: {results.completion_time_p50:.1f} days")
    print(f"  P90: {results.completion_time_p90:.1f} days")
    print(f"  Events rescheduled: {results.mean_events_rescheduled:.1f}")

    # Show timeline excerpt from one run
    run = results.get_run(0)
    print(f"\nTimeline excerpt (first 5 events):")
    for i, (time, event_type, entity_id, description) in enumerate(run.timeline[:5]):
        print(f"  T={time:6.1f}: {event_type:30s} - {description}")

    return results


def demonstrate_with_feasibility_constraints():
    """Simulation with feasibility constraints (resource capacity, budget throttling)."""
    print("\n" + "=" * 80)
    print("WITH FEASIBILITY CONSTRAINTS")
    print("=" * 80)
    print("\nResource capacity: Monitor availability limits concurrent activities")
    print("Budget throttling: Limited budget slows down execution")

    # Build trial
    site = Site(
        site_id="SITE_001",
        activation_time=Triangular(low=30, mode=45, high=90),
        enrollment_rate=Gamma(shape=2, scale=1.5),
        dropout_rate=Bernoulli(p=0.15)
    )

    flow = PatientFlow(
        flow_id="STANDARD_FLOW",
        states={"enrolled", "completed"},
        initial_state="enrolled",
        terminal_states={"completed"},
        transition_times={(("enrolled", "completed")): Triangular(low=90, mode=180, high=365)}
    )

    trial = Trial(
        trial_id="RESOURCE_CONSTRAINED_TRIAL",
        target_enrollment=200,
        sites=[site],
        patient_flow=flow
    )

    # Define feasibility constraints
    constraints = [
        ResourceCapacityConstraint(
            resource_id="MONITOR"
        ),
        BudgetThrottlingConstraint(
            budget_per_day=5000.0,  # Limited budget → slower execution
            response_curve=LinearResponseCurve(min_speed_ratio=0.5)
        )
    ]

    # Engine with constraints
    engine = SimulationEngine(master_seed=42, constraints=constraints)
    results = engine.run(trial, num_runs=10)

    print(f"\nResults (10 runs):")
    print(f"  P10: {results.completion_time_p10:.1f} days")
    print(f"  P50: {results.completion_time_p50:.1f} days")
    print(f"  P90: {results.completion_time_p90:.1f} days")
    print(f"  Events rescheduled: {results.mean_events_rescheduled:.1f}")

    # Show timeline with constraint effects
    run = results.get_run(0)
    print(f"\nTimeline showing constraint effects:")
    for time, event_type, entity_id, description in run.timeline[:8]:
        if "rescheduled" in event_type or "modified" in event_type:
            print(f"  T={time:6.1f}: {event_type:30s} - {description}")

    return results


def demonstrate_multiple_constraints():
    """Simulation with both validity AND feasibility constraints."""
    print("\n" + "=" * 80)
    print("COMBINED: VALIDITY + FEASIBILITY CONSTRAINTS")
    print("=" * 80)
    print("\nMultiple constraints compose via AND/MAX/MERGE rules")

    # Build trial
    site = Site(
        site_id="SITE_001",
        activation_time=Triangular(low=30, mode=45, high=90),
        enrollment_rate=Gamma(shape=2, scale=1.5),
        dropout_rate=Bernoulli(p=0.15)
    )

    flow = PatientFlow(
        flow_id="STANDARD_FLOW",
        states={"enrolled", "completed"},
        initial_state="enrolled",
        terminal_states={"completed"},
        transition_times={(("enrolled", "completed")): Triangular(low=90, mode=180, high=365)}
    )

    trial = Trial(
        trial_id="FULLY_CONSTRAINED_TRIAL",
        target_enrollment=200,
        sites=[site],
        patient_flow=flow
    )

    # Define all constraint types
    constraints = [
        TemporalPrecedenceConstraint(
            predecessor_event_type="site_activation",
            dependent_event_type="enrollment"
        ),
        ResourceCapacityConstraint(
            resource_id="MONITOR"
        ),
        BudgetThrottlingConstraint(
            budget_per_day=5000.0,
            response_curve=LinearResponseCurve(min_speed_ratio=0.5)
        )
    ]

    # Engine with all constraints
    engine = SimulationEngine(master_seed=42, constraints=constraints)
    results = engine.run(trial, num_runs=10)

    print(f"\nResults (10 runs):")
    print(f"  P10: {results.completion_time_p10:.1f} days")
    print(f"  P50: {results.completion_time_p50:.1f} days")
    print(f"  P90: {results.completion_time_p90:.1f} days")
    print(f"  Events rescheduled: {results.mean_events_rescheduled:.1f}")

    # Analyze constraint impact
    run = results.get_run(0)
    rescheduled = sum(1 for _, event_type, _, _ in run.timeline if "rescheduled" in event_type)
    modified = sum(1 for _, event_type, _, _ in run.timeline if "modified" in event_type)

    print(f"\nConstraint impact:")
    print(f"  Events rescheduled: {rescheduled}")
    print(f"  Events modified: {modified}")
    print(f"  Constraint violations: {run.constraint_violations}")

    return results


def compare_constrained_vs_unconstrained():
    """Compare outcomes with and without constraints."""
    print("\n" + "=" * 80)
    print("COMPARISON: UNCONSTRAINED vs CONSTRAINED")
    print("=" * 80)

    # Build trial
    site = Site(
        site_id="SITE_001",
        activation_time=Triangular(low=30, mode=45, high=90),
        enrollment_rate=Gamma(shape=2, scale=1.5),
        dropout_rate=Bernoulli(p=0.15)
    )

    flow = PatientFlow(
        flow_id="STANDARD_FLOW",
        states={"enrolled", "completed"},
        initial_state="enrolled",
        terminal_states={"completed"},
        transition_times={(("enrolled", "completed")): Triangular(low=90, mode=180, high=365)}
    )

    trial = Trial(
        trial_id="COMPARISON_TRIAL",
        target_enrollment=200,
        sites=[site],
        patient_flow=flow
    )

    # Unconstrained
    engine_unconstrained = SimulationEngine(master_seed=42, constraints=None)
    results_unconstrained = engine_unconstrained.run(trial, num_runs=20)

    # Constrained
    constraints = [
        TemporalPrecedenceConstraint("site_activation", "enrollment"),
        ResourceCapacityConstraint("MONITOR"),
        BudgetThrottlingConstraint(5000.0, LinearResponseCurve(min_speed_ratio=0.5))
    ]
    engine_constrained = SimulationEngine(master_seed=42, constraints=constraints)
    results_constrained = engine_constrained.run(trial, num_runs=20)

    # Compare
    print("\nUnconstrained:")
    print(f"  P50: {results_unconstrained.completion_time_p50:.1f} days")
    print(f"  P90: {results_unconstrained.completion_time_p90:.1f} days")

    print("\nConstrained:")
    print(f"  P50: {results_constrained.completion_time_p50:.1f} days")
    print(f"  P90: {results_constrained.completion_time_p90:.1f} days")

    print("\nImpact:")
    p50_increase = results_constrained.completion_time_p50 - results_unconstrained.completion_time_p50
    p90_increase = results_constrained.completion_time_p90 - results_unconstrained.completion_time_p90
    print(f"  P50 increase: {p50_increase:+.1f} days ({100*p50_increase/results_unconstrained.completion_time_p50:+.1f}%)")
    print(f"  P90 increase: {p90_increase:+.1f} days ({100*p90_increase/results_unconstrained.completion_time_p90:+.1f}%)")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("CONSTRAINT INTEGRATION DEMONSTRATION")
    print("=" * 80)
    print("\nDemonstrates how constraints integrate with the simulation engine:")
    print("1. Baseline (no constraints)")
    print("2. Validity constraints (temporal precedence)")
    print("3. Feasibility constraints (resource capacity, budget throttling)")
    print("4. Combined constraints (all together)")
    print("5. Comparison (constrained vs unconstrained)")

    # Run demonstrations
    demonstrate_without_constraints()
    demonstrate_with_validity_constraints()
    demonstrate_with_feasibility_constraints()
    demonstrate_multiple_constraints()
    compare_constrained_vs_unconstrained()

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("""
Key Insights:

1. Backward Compatibility
   - Engine works with or without constraints
   - constraints=None → MVP mode (no constraint evaluation)
   - constraints=[] → enabled but no constraints active

2. Constraint Types
   - Validity: Hard gates (must satisfy or reschedule)
   - Feasibility: Soft modifiers (delays, parameter changes)

3. Composition Rules
   - Multiple constraints combine via AND/MAX/MERGE
   - Engine orchestrates, constraints evaluate (pure functions)

4. Explainability
   - Timeline includes constraint explanations
   - Every reschedule/modification traceable to constraint

5. Determinism
   - Same seed → identical results (even with constraints)
   - Reproducible analyses and debugging

6. Impact Quantification
   - Compare constrained vs unconstrained outcomes
   - Measure P50/P90 shifts due to constraints
   - Identify bottlenecks and resource contention
""")

    print("=" * 80)
