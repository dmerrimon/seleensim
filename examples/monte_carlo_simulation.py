"""
Example: Monte Carlo Simulation - Single Run vs Aggregated Outputs

Demonstrates:
1. Single simulation run shows ONE realization (timeline, causality)
2. Aggregated results show DISTRIBUTION of outcomes (P10/P50/P90)
3. Why both are needed for planning under uncertainty
4. Deterministic execution with seeds
"""

from seleensim.entities import Site, Trial, PatientFlow
from seleensim.distributions import Triangular, Gamma, Bernoulli
from seleensim.simulation import SimulationEngine


def build_example_trial():
    """Build simple trial with 3 sites having variable activation times."""

    # Site 1: Fast activation (optimistic)
    site1 = Site(
        site_id="SITE_001_FastTrack",
        activation_time=Triangular(low=25, mode=35, high=60),  # 35 days typical
        enrollment_rate=Gamma(shape=3, scale=2.5),
        dropout_rate=Bernoulli(p=0.12)
    )

    # Site 2: Medium activation
    site2 = Site(
        site_id="SITE_002_Standard",
        activation_time=Triangular(low=40, mode=60, high=100),  # 60 days typical
        enrollment_rate=Gamma(shape=2, scale=2.0),
        dropout_rate=Bernoulli(p=0.15)
    )

    # Site 3: Slow activation (regulatory delays possible)
    site3 = Site(
        site_id="SITE_003_Complex",
        activation_time=Triangular(low=60, mode=90, high=180),  # 90 days typical
        enrollment_rate=Gamma(shape=1.5, scale=1.5),
        dropout_rate=Bernoulli(p=0.20)
    )

    # Simple patient flow (for MVP)
    flow = PatientFlow(
        flow_id="STANDARD_FLOW",
        states={"enrolled", "completed"},
        initial_state="enrolled",
        terminal_states={"completed"},
        transition_times={
            ("enrolled", "completed"): Triangular(low=90, mode=180, high=365)
        }
    )

    trial = Trial(
        trial_id="MULTI_SITE_TRIAL",
        target_enrollment=200,
        sites=[site1, site2, site3],
        patient_flow=flow
    )

    return trial


def demonstrate_single_run():
    """Demonstrate single simulation run (ONE realization)."""
    print("\n" + "=" * 80)
    print("SINGLE SIMULATION RUN")
    print("=" * 80)
    print("\nQuestion: How does THIS specific trial unfold?")
    print("Answer: One timeline showing causality and specific outcomes\n")

    trial = build_example_trial()
    engine = SimulationEngine(master_seed=42)

    # Run single simulation
    results = engine.run(trial, num_runs=1)
    single_run = results.get_run(0)

    print(single_run.summary())
    print("\nTimeline (first 5 events):")
    for i, (time, event_type, entity_id, description) in enumerate(single_run.timeline[:5]):
        print(f"  Day {time:6.1f}: {entity_id:20s} - {description}")

    print("\nWhat this tells us:")
    print("  - Site_001_FastTrack activated first")
    print("  - Specific activation times for each site")
    print("  - Exact completion time for THIS realization")
    print("  - Can trace causality: Why did event X happen when it did?")

    print("\nUse cases:")
    print("  ✓ Debugging: Why did this run take longer than expected?")
    print("  ✓ Understanding: How do events cascade through time?")
    print("  ✓ Storytelling: Explain one possible scenario to stakeholders")

    print("\nWhat this DOESN'T tell us:")
    print("  ✗ How much could outcomes vary?")
    print("  ✗ What's the risk of delay?")
    print("  ✗ What should we budget/plan for?")

    return single_run


def demonstrate_aggregated_results():
    """Demonstrate aggregated results (DISTRIBUTION of outcomes)."""
    print("\n" + "=" * 80)
    print("AGGREGATED RESULTS (100 MONTE CARLO RUNS)")
    print("=" * 80)
    print("\nQuestion: What RANGE of outcomes should we expect?")
    print("Answer: Distribution showing P10/P50/P90 across uncertainty space\n")

    trial = build_example_trial()
    engine = SimulationEngine(master_seed=42)

    # Run 100 simulations
    results = engine.run(trial, num_runs=100)

    print(results.summary())

    print("\nWhat this tells us:")
    print(f"  - 10% of trials complete by {results.completion_time_p10:.1f} days (optimistic)")
    print(f"  - 50% of trials complete by {results.completion_time_p50:.1f} days (median)")
    print(f"  - 90% of trials complete by {results.completion_time_p90:.1f} days (pessimistic)")

    variability = results.completion_time_p90 - results.completion_time_p10
    print(f"  - Variability (P90-P10): {variability:.1f} days")

    print("\nUse cases:")
    print("  ✓ Risk assessment: 10% chance of exceeding P90 timeline")
    print("  ✓ Planning: Budget for P90 scenario (conservative)")
    print("  ✓ Decision making: Compare strategies (add site? increase budget?)")
    print("  ✓ Communication: 'We're 90% confident completion within X days'")

    print("\nWhat this DOESN'T tell us:")
    print("  ✗ Why specific runs were slow/fast")
    print("  ✗ Which events caused bottlenecks")
    print("  ✗ Detailed timeline of any specific realization")

    return results


def demonstrate_combining_insights():
    """Demonstrate using both single runs AND aggregated results."""
    print("\n" + "=" * 80)
    print("COMBINING INSIGHTS: Single Runs + Aggregated Results")
    print("=" * 80)
    print("\nPowerful analysis requires BOTH views:\n")

    trial = build_example_trial()
    engine = SimulationEngine(master_seed=42)

    # Run simulations
    results = engine.run(trial, num_runs=100)

    # Analysis 1: Identify outliers from aggregated view
    print("Step 1: Aggregated view identifies outliers")
    print(f"  P90 completion time: {results.completion_time_p90:.1f} days")

    # Analysis 2: Inspect specific outlier runs
    print("\nStep 2: Inspect slowest run to understand WHY")
    slowest_run = max(results.run_results, key=lambda r: r.completion_time)
    print(f"  Slowest run #{slowest_run.run_id}:")
    print(f"    Completion: {slowest_run.completion_time:.1f} days")
    print(f"    Timeline sample:")
    for time, event_type, entity_id, desc in slowest_run.timeline[:3]:
        print(f"      Day {time:6.1f}: {entity_id} - {desc}")

    # Analysis 3: Compare to fastest run
    print("\nStep 3: Compare to fastest run")
    fastest_run = min(results.run_results, key=lambda r: r.completion_time)
    print(f"  Fastest run #{fastest_run.run_id}:")
    print(f"    Completion: {fastest_run.completion_time:.1f} days")

    delta = slowest_run.completion_time - fastest_run.completion_time
    print(f"\n  Delta: {delta:.1f} days between fastest and slowest")

    # Key insight
    print("\nKey Insight:")
    print("  Aggregated: Quantifies variability (P10 to P90)")
    print("  Single runs: Explains what drives variability")
    print("  → Can identify: Site activation variability is main driver")

    print("\nDecision Example:")
    print("  Should we add backup Site_004?")
    print("  - Aggregated: Shows if P90 improves")
    print("  - Single runs: Shows if Site_004 actually gets used in slow scenarios")
    print("  - Combined: Make informed decision with confidence")


def demonstrate_determinism():
    """Demonstrate deterministic execution with seeds."""
    print("\n" + "=" * 80)
    print("DETERMINISTIC EXECUTION")
    print("=" * 80)
    print("\nSame seed → Identical results (reproducibility)\n")

    trial = build_example_trial()

    # Run 1: seed=42
    engine1 = SimulationEngine(master_seed=42)
    results1 = engine1.run(trial, num_runs=5)

    # Run 2: seed=42 (same)
    engine2 = SimulationEngine(master_seed=42)
    results2 = engine2.run(trial, num_runs=5)

    print("Engine 1 (seed=42):")
    for i in range(5):
        run = results1.get_run(i)
        print(f"  Run {i}: {run.completion_time:.2f} days (seed={run.seed})")

    print("\nEngine 2 (seed=42, SAME master seed):")
    for i in range(5):
        run = results2.get_run(i)
        print(f"  Run {i}: {run.completion_time:.2f} days (seed={run.seed})")

    # Verify identical
    print("\nVerification:")
    all_match = all(
        results1.get_run(i).completion_time == results2.get_run(i).completion_time
        for i in range(5)
    )
    print(f"  All runs identical: {all_match} ✓")

    print("\nWhy this matters:")
    print("  ✓ Reproducibility: Can regenerate exact results")
    print("  ✓ Debugging: Re-run specific scenarios")
    print("  ✓ Validation: Verify implementation correctness")
    print("  ✓ Collaboration: Share seeds to discuss specific runs")

    # Different seed
    print("\nEngine 3 (seed=99, DIFFERENT master seed):")
    engine3 = SimulationEngine(master_seed=99)
    results3 = engine3.run(trial, num_runs=5)

    for i in range(5):
        run = results3.get_run(i)
        print(f"  Run {i}: {run.completion_time:.2f} days (seed={run.seed})")

    print("\n  → Different results (explores different part of uncertainty space)")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("MONTE CARLO SIMULATION: Single Run vs Aggregated Outputs")
    print("=" * 80)

    # Demonstrate each concept
    single_run = demonstrate_single_run()
    aggregated = demonstrate_aggregated_results()
    demonstrate_combining_insights()
    demonstrate_determinism()

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("""
The simulation engine provides TWO complementary views:

1. SINGLE RUN (Microscope)
   - Shows HOW trial unfolds (timeline, causality)
   - Answers: "What happened and why?"
   - Use for: Debugging, understanding, storytelling

2. AGGREGATED RESULTS (Telescope)
   - Shows RANGE of outcomes (P10/P50/P90)
   - Answers: "What could happen and how likely?"
   - Use for: Risk assessment, planning, decisions

Both are needed:
- Single runs explain mechanisms
- Aggregated results quantify uncertainty
- Together: Understand AND plan under uncertainty

Deterministic execution ensures:
- Reproducible results (same seed → same output)
- Debuggable scenarios
- Sharable analyses
""")

    print("=" * 80)
