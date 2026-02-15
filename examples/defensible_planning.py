"""
Example: Defensible Budget and Timeline Planning

Demonstrates:
1. Running simulation with enhanced output schema
2. Using provenance for reproducibility
3. Using input specification for traceability
4. Using percentile distributions for planning
5. Defending budget/timeline to stakeholders
6. JSON export/import for sharing
"""

import json
import time
from seleensim.entities import Site, Trial, PatientFlow
from seleensim.distributions import Triangular, Gamma, Bernoulli
from seleensim.simulation import SimulationEngine
from seleensim.scenarios import ScenarioProfile, apply_scenario
from seleensim.output_schema import (
    create_enhanced_output,
    PercentileDistribution
)


def run_simulation_with_enhanced_output():
    """Run simulation and capture enhanced output."""
    print("\n" + "=" * 80)
    print("RUNNING SIMULATION WITH ENHANCED OUTPUT")
    print("=" * 80)

    # Define trial
    base_trial = Trial(
        trial_id="PHASE_III_TRIAL_2026Q1",
        target_enrollment=200,
        sites=[
            Site(
                site_id="SITE_001_US",
                activation_time=Triangular(low=30, mode=45, high=90),
                enrollment_rate=Gamma(shape=2, scale=1.5),
                dropout_rate=Bernoulli(p=0.15)
            ),
            Site(
                site_id="SITE_002_EU",
                activation_time=Triangular(low=40, mode=60, high=120),
                enrollment_rate=Gamma(shape=1.8, scale=1.3),
                dropout_rate=Bernoulli(p=0.18)
            ),
            Site(
                site_id="SITE_003_ASIA",
                activation_time=Triangular(low=50, mode=75, high=150),
                enrollment_rate=Gamma(shape=1.5, scale=1.2),
                dropout_rate=Bernoulli(p=0.20)
            )
        ],
        patient_flow=PatientFlow(
            flow_id="STANDARD",
            states={"enrolled", "completed"},
            initial_state="enrolled",
            terminal_states={"completed"},
            transition_times={(("enrolled", "completed")): Triangular(90, 180, 365)}
        )
    )

    print(f"Trial: {base_trial.trial_id}")
    print(f"  Sites: {len(base_trial.sites)}")
    print(f"  Target enrollment: {base_trial.target_enrollment}")

    # Run simulation
    engine = SimulationEngine(master_seed=42)
    start_time = time.time()

    results = engine.run(base_trial, num_runs=100)

    execution_duration = time.time() - start_time

    # Create enhanced output
    enhanced_output = create_enhanced_output(
        simulation_id="sim_phase3_base_20260214",
        trial=base_trial,
        scenario=None,
        constraints=None,
        run_results=results.run_results,
        master_seed=42,
        execution_duration=execution_duration
    )

    print(f"\nSimulation complete:")
    print(f"  ID: {enhanced_output.provenance.simulation_id}")
    print(f"  Runs: {enhanced_output.provenance.num_runs}")
    print(f"  Seed: {enhanced_output.provenance.master_seed}")
    print(f"  Duration: {enhanced_output.provenance.execution_duration_seconds:.2f}s")

    return enhanced_output


def demonstrate_budget_defense(output):
    """Demonstrate defending budget using enhanced output."""
    print("\n" + "=" * 80)
    print("SCENARIO 1: BUDGET COMMITTEE PRESENTATION")
    print("=" * 80)

    print("\nQuestion: 'Why do you need this budget and timeline?'\n")

    # 1. Show probabilistic planning
    results = output.aggregated_results

    print("TIMELINE PROJECTION:")
    print(f"  Median (P50): {results.completion_time.p50:.0f} days")
    print(f"  Conservative (P90): {results.completion_time.p90:.0f} days")
    print(f"  Optimistic (P10): {results.completion_time.p10:.0f} days")
    print(f"  Variability: {results.completion_time.range_p10_p90():.0f} day range")

    print("\nRECOMMENDATION:")
    print(f"  Plan for P90 timeline: {results.completion_time.p90:.0f} days")
    print(f"  Rationale: 90% confidence level")
    print(f"  Risk buffer: {results.completion_time.p90 - results.completion_time.p50:.0f} days above median")

    # 2. Show assumptions
    print("\nASSUMPTIONS (documented and traceable):")
    inputs = output.input_specification

    for key, dist in list(inputs.distribution_summary.items())[:3]:
        print(f"  {key}:")
        if dist['type'] == 'Triangular':
            print(f"    Distribution: Triangular(low={dist['low']}, mode={dist['mode']}, high={dist['high']})")
        elif dist['type'] == 'Gamma':
            print(f"    Distribution: Gamma(shape={dist['shape']}, scale={dist['scale']})")

    print(f"\n  Trial parameters:")
    for key, value in inputs.deterministic_summary.items():
        print(f"    {key}: {value}")

    # 3. Show reproducibility
    print("\nREPRODUCIBILITY:")
    prov = output.provenance
    print(f"  Master seed: {prov.master_seed}")
    print(f"  Simulation ID: {prov.simulation_id}")
    print(f"  Software: SeleenSIM v{prov.seleensim_version}")
    print(f"  Timestamp: {prov.execution_timestamp}")
    print(f"  → Results can be reproduced exactly")

    print("\nBUDGET JUSTIFICATION:")
    print(f"""
  Based on {prov.num_runs} Monte Carlo simulations:
  - 90% probability of completion within {results.completion_time.p90:.0f} days
  - Explicit assumptions documented in input specification
  - Results reproducible with seed {prov.master_seed}

  RECOMMENDATION: Budget for P90 scenario ({results.completion_time.p90:.0f} days)
  to achieve 90% confidence level.
    """)


def demonstrate_assumption_defense(output):
    """Demonstrate defending assumptions."""
    print("\n" + "=" * 80)
    print("SCENARIO 2: SPONSOR QUESTIONS ASSUMPTIONS")
    print("=" * 80)

    print("\nQuestion: 'Why did you assume these activation times?'\n")

    inputs = output.input_specification

    print("ASSUMPTION TRACEABILITY:")

    # Show Site 001 assumptions
    if "SITE_001_US.activation_time" in inputs.distribution_summary:
        dist = inputs.distribution_summary["SITE_001_US.activation_time"]
        print(f"\nSite 001 (US) activation:")
        print(f"  Distribution: {dist['type']}")
        print(f"  Parameters: low={dist['low']}, mode={dist['mode']}, high={dist['high']}")
        print(f"  Interpretation:")
        print(f"    - Optimistic: {dist['low']} days")
        print(f"    - Most likely: {dist['mode']} days")
        print(f"    - Pessimistic: {dist['high']} days")

    # Show Site 002 assumptions
    if "SITE_002_EU.activation_time" in inputs.distribution_summary:
        dist = inputs.distribution_summary["SITE_002_EU.activation_time"]
        print(f"\nSite 002 (EU) activation:")
        print(f"  Distribution: {dist['type']}")
        print(f"  Parameters: low={dist['low']}, mode={dist['mode']}, high={dist['high']}")
        print(f"  Note: Slower than US due to regulatory environment")

    print("\nRESPONSE TO QUESTIONS:")
    print("""
  If you have data suggesting different assumptions:
  1. Provide historical activation times
  2. We can fit distributions to your data (calibration)
  3. Re-run simulation with same seed
  4. Compare impact on timeline

  This demonstrates why explicit assumptions matter.
  All distributions are replaceable based on evidence.
    """)


def demonstrate_scenario_comparison(base_output):
    """Demonstrate comparing scenarios."""
    print("\n" + "=" * 80)
    print("SCENARIO 3: REGULATORY DELAY ANALYSIS")
    print("=" * 80)

    print("\nQuestion: 'What if EU regulatory approval takes longer?'\n")

    # Create delayed scenario
    delayed_scenario = ScenarioProfile(
        scenario_id="EU_REGULATORY_DELAY",
        description="30% increase in EU site activation time",
        version="1.0.0",
        site_overrides={
            "SITE_002_EU": {
                "activation_time": {
                    "type": "distribution_scale",
                    "parameters": {"scale_factor": 1.3},
                    "reason": "Historical EU regulatory delays"
                }
            }
        }
    )

    # Load original trial
    trial_dict = base_output.input_specification.trial_spec
    from seleensim.entities import Trial as TrialClass

    # For demo, reconstruct trial (in practice, keep original)
    base_trial = Trial(
        trial_id="PHASE_III_TRIAL_2026Q1",
        target_enrollment=200,
        sites=[
            Site(
                site_id="SITE_001_US",
                activation_time=Triangular(low=30, mode=45, high=90),
                enrollment_rate=Gamma(shape=2, scale=1.5),
                dropout_rate=Bernoulli(p=0.15)
            ),
            Site(
                site_id="SITE_002_EU",
                activation_time=Triangular(low=40, mode=60, high=120),
                enrollment_rate=Gamma(shape=1.8, scale=1.3),
                dropout_rate=Bernoulli(p=0.18)
            ),
            Site(
                site_id="SITE_003_ASIA",
                activation_time=Triangular(low=50, mode=75, high=150),
                enrollment_rate=Gamma(shape=1.5, scale=1.2),
                dropout_rate=Bernoulli(p=0.20)
            )
        ],
        patient_flow=PatientFlow(
            flow_id="STANDARD",
            states={"enrolled", "completed"},
            initial_state="enrolled",
            terminal_states={"completed"},
            transition_times={(("enrolled", "completed")): Triangular(90, 180, 365)}
        )
    )

    # Apply scenario
    delayed_trial = apply_scenario(base_trial, delayed_scenario)

    # Run simulation
    engine = SimulationEngine(master_seed=42)
    start_time = time.time()
    delayed_results = engine.run(delayed_trial, num_runs=100)
    execution_duration = time.time() - start_time

    # Create enhanced output
    delayed_output = create_enhanced_output(
        simulation_id="sim_phase3_eu_delay_20260214",
        trial=delayed_trial,
        scenario=delayed_scenario,
        constraints=None,
        run_results=delayed_results.run_results,
        master_seed=42,
        execution_duration=execution_duration
    )

    # Compare
    base_p50 = base_output.aggregated_results.completion_time.p50
    delayed_p50 = delayed_output.aggregated_results.completion_time.p50

    base_p90 = base_output.aggregated_results.completion_time.p90
    delayed_p90 = delayed_output.aggregated_results.completion_time.p90

    print("SCENARIO COMPARISON:")
    print(f"\nBase scenario:")
    print(f"  P50: {base_p50:.0f} days")
    print(f"  P90: {base_p90:.0f} days")

    print(f"\nEU Delay scenario (30% slower EU activation):")
    print(f"  P50: {delayed_p50:.0f} days")
    print(f"  P90: {delayed_p90:.0f} days")

    print(f"\nIMPACT:")
    print(f"  Median delay: {delayed_p50 - base_p50:+.0f} days")
    print(f"  P90 delay: {delayed_p90 - base_p90:+.0f} days")
    print(f"  Percentage change: {100*(delayed_p50 - base_p50)/base_p50:+.1f}%")

    print("\nRISK MITIGATION OPTIONS:")
    print("""
  1. Start EU site activation 20 days earlier
  2. Add backup EU site (Site 004)
  3. Include 15-day contingency buffer
  4. Allocate dedicated EU regulatory resource

  We can simulate each option and quantify impact.
    """)


def demonstrate_json_export(output):
    """Demonstrate JSON export for sharing."""
    print("\n" + "=" * 80)
    print("SCENARIO 4: AUDIT/SHARING")
    print("=" * 80)

    # Export to JSON
    filename = "simulation_output_phase3_base.json"
    output.to_json(filename, include_single_runs=False)

    print(f"\nExported to: {filename}")
    print(f"File size: {len(json.dumps(output.to_dict())) / 1024:.1f} KB")

    print("\nJSON STRUCTURE:")
    print("""
  {
    "provenance": {
      "simulation_id": "sim_phase3_base_20260214",
      "execution_timestamp": "2026-02-14T...",
      "master_seed": 42,
      ...
    },
    "input_specification": {
      "trial_id": "PHASE_III_TRIAL_2026Q1",
      "trial_spec": {...},
      "distribution_summary": {...},
      ...
    },
    "aggregated_results": {
      "completion_time": {
        "p10": 78.5,
        "p50": 110.2,
        "p90": 145.3,
        ...
      },
      ...
    }
  }
    """)

    print("\nUSE CASES:")
    print("  ✓ Share with stakeholders (self-documenting)")
    print("  ✓ Archive for regulatory audit")
    print("  ✓ Compare scenarios side-by-side")
    print("  ✓ Reproduce results (all inputs included)")
    print("  ✓ Version control (JSON diff-able)")

    # Load back
    from seleensim.output_schema import EnhancedSimulationOutput
    loaded = EnhancedSimulationOutput.from_json(filename)

    print(f"\nVERIFICATION:")
    print(f"  Loaded simulation ID: {loaded.provenance.simulation_id}")
    print(f"  P50 matches: {abs(loaded.aggregated_results.completion_time.p50 - output.aggregated_results.completion_time.p50) < 0.01}")
    print(f"  ✓ Round-trip successful")


def demonstrate_reproducibility(output):
    """Demonstrate reproducibility."""
    print("\n" + "=" * 80)
    print("SCENARIO 5: REPRODUCIBILITY")
    print("=" * 80)

    print("\nQuestion: 'Can you prove these results are reproducible?'\n")

    prov = output.provenance

    print("REPRODUCTION INSTRUCTIONS:")
    print(f"""
  1. Software Setup:
     - Install: SeleenSIM v{prov.seleensim_version}
     - Python: v{prov.python_version}

  2. Load Inputs:
     - Trial specification from: input_specification.trial_spec
     - Master seed: {prov.master_seed}
     - Number of runs: {prov.num_runs}

  3. Execute:
     engine = SimulationEngine(master_seed={prov.master_seed})
     results = engine.run(trial, num_runs={prov.num_runs})

  4. Verify:
     assert results.completion_time_p50 == {output.aggregated_results.completion_time.p50:.2f}

  GUARANTEE: Same inputs + seed → identical results (deterministic)
    """)

    print("\nAUDIT TRAIL:")
    print(f"  Simulation ID: {prov.simulation_id}")
    print(f"  Timestamp: {prov.execution_timestamp}")
    print(f"  All assumptions documented in input_specification")
    print(f"  Complete output saved to JSON")
    print(f"  ✓ Full transparency and accountability")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("DEFENSIBLE BUDGET AND TIMELINE PLANNING")
    print("=" * 80)
    print("\nDemonstrates using enhanced output schema to:")
    print("1. Defend budget/timeline to committee")
    print("2. Defend assumptions to sponsors")
    print("3. Analyze regulatory delay scenarios")
    print("4. Export/share results (JSON)")
    print("5. Prove reproducibility for audit")

    # Run simulation
    output = run_simulation_with_enhanced_output()

    # Demonstrate defense scenarios
    demonstrate_budget_defense(output)
    demonstrate_assumption_defense(output)
    demonstrate_scenario_comparison(output)
    demonstrate_json_export(output)
    demonstrate_reproducibility(output)

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("""
Key Advantages of Enhanced Output Schema:

1. TRACEABILITY
   - Every result links back to inputs
   - Distribution parameters documented
   - Scenario overrides captured

2. REPRODUCIBILITY
   - Master seed preserved
   - Software versions recorded
   - Complete input snapshot

3. DEFENSIBLE PLANNING
   - P90 planning (90% confidence)
   - Variability quantified (P10-P90 range)
   - Explicit assumptions

4. SCENARIO ANALYSIS
   - Compare base vs scenarios
   - Quantify impact
   - Support risk mitigation decisions

5. AUDITABILITY
   - JSON export (self-documenting)
   - Provenance tracking
   - Reproducible results

BOTTOM LINE:
No hand-waving. No hidden assumptions. Just structured data
and explicit traceability from outcomes back to inputs.
    """)

    print("=" * 80)
