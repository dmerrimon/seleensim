"""
Example: Scenario System Usage

Demonstrates:
1. Creating base trial specification
2. Defining scenario overrides (explicit, inspectable)
3. Applying scenarios (pure function, no mutation)
4. Comparing scenario outcomes
5. Scenario composition
6. Version control patterns
7. Calibration workflow (base improves, scenarios stay relative)
"""

import json
from seleensim.entities import Site, Trial, PatientFlow
from seleensim.distributions import Triangular, Gamma, Bernoulli
from seleensim.scenarios import (
    ScenarioProfile,
    apply_scenario,
    compose_scenarios,
    diff_scenarios
)
from seleensim.simulation import SimulationEngine


def demonstrate_base_plus_scenario():
    """Basic usage: base trial + scenario override."""
    print("\n" + "=" * 80)
    print("BASIC USAGE: BASE + SCENARIO")
    print("=" * 80)

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
        patient_flow=PatientFlow(
            flow_id="STANDARD",
            states={"enrolled", "completed"},
            initial_state="enrolled",
            terminal_states={"completed"},
            transition_times={(("enrolled", "completed")): Triangular(90, 180, 365)}
        )
    )

    print(f"\nBase trial: {base_trial.trial_id}")
    print(f"  Sites: {len(base_trial.sites)}")
    print(f"  Target enrollment: {base_trial.target_enrollment}")
    print(f"  Site activation (mode): {base_trial.sites[0].activation_time.mode} days")

    # Define scenario: 20% activation delay
    delayed_scenario = ScenarioProfile(
        scenario_id="DELAYED_ACTIVATION",
        description="EU regulatory delays extend activation by 20%",
        version="1.0.0",
        site_overrides={
            "SITE_001": {
                "activation_time": {
                    "type": "distribution_scale",
                    "parameters": {"scale_factor": 1.2},
                    "reason": "EU regulatory environment adds review steps"
                }
            }
        }
    )

    print(f"\nScenario: {delayed_scenario.scenario_id}")
    print(f"  Description: {delayed_scenario.description}")
    print(f"  Overrides: {len(delayed_scenario.site_overrides)} sites")

    # Apply scenario (pure function - no mutation)
    modified_trial = apply_scenario(base_trial, delayed_scenario)

    print(f"\nModified trial: {modified_trial.trial_id}")
    print(f"  Site activation (mode): {modified_trial.sites[0].activation_time.mode} days")

    # Verify base unchanged
    print(f"\nBase trial unchanged:")
    print(f"  Site activation (mode): {base_trial.sites[0].activation_time.mode} days")
    print(f"  ✓ No mutation occurred")

    # Run simulations
    engine = SimulationEngine(master_seed=42)
    base_results = engine.run(base_trial, num_runs=20)
    scenario_results = engine.run(modified_trial, num_runs=20)

    print(f"\nSimulation results:")
    print(f"  Base P50: {base_results.completion_time_p50:.1f} days")
    print(f"  Scenario P50: {scenario_results.completion_time_p50:.1f} days")
    print(f"  Impact: {scenario_results.completion_time_p50 - base_results.completion_time_p50:+.1f} days")


def demonstrate_multiple_scenarios():
    """Compare multiple scenarios."""
    print("\n" + "=" * 80)
    print("COMPARING MULTIPLE SCENARIOS")
    print("=" * 80)

    # Base trial
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
        patient_flow=PatientFlow(
            flow_id="STANDARD",
            states={"enrolled", "completed"},
            initial_state="enrolled",
            terminal_states={"completed"},
            transition_times={(("enrolled", "completed")): Triangular(90, 180, 365)}
        )
    )

    # Define scenarios
    scenarios = [
        ScenarioProfile(
            scenario_id="OPTIMISTIC",
            description="Fast activation, high enrollment",
            version="1.0.0",
            site_overrides={
                "SITE_001": {
                    "activation_time": {
                        "type": "distribution_scale",
                        "parameters": {"scale_factor": 0.8},
                        "reason": "Expedited regulatory review"
                    },
                    "enrollment_rate": {
                        "type": "distribution_scale",
                        "parameters": {"scale_factor": 1.3},
                        "reason": "Strong patient population"
                    }
                }
            }
        ),
        ScenarioProfile(
            scenario_id="PESSIMISTIC",
            description="Slow activation, low enrollment",
            version="1.0.0",
            site_overrides={
                "SITE_001": {
                    "activation_time": {
                        "type": "distribution_scale",
                        "parameters": {"scale_factor": 1.3},
                        "reason": "Regulatory delays"
                    },
                    "enrollment_rate": {
                        "type": "distribution_scale",
                        "parameters": {"scale_factor": 0.7},
                        "reason": "Competitive trials in area"
                    }
                }
            }
        ),
        ScenarioProfile(
            scenario_id="REDUCED_TARGET",
            description="Lower enrollment target",
            version="1.0.0",
            trial_overrides={
                "target_enrollment": {
                    "type": "direct_value",
                    "value": 150,
                    "reason": "Protocol amendment reduces sample size"
                }
            }
        )
    ]

    # Run all scenarios
    engine = SimulationEngine(master_seed=42)
    results = {}
    results["BASE"] = engine.run(base_trial, num_runs=20)

    for scenario in scenarios:
        modified_trial = apply_scenario(base_trial, scenario)
        results[scenario.scenario_id] = engine.run(modified_trial, num_runs=20)

    # Compare
    print("\nScenario comparison:")
    print(f"{'Scenario':<20} {'P10':>8} {'P50':>8} {'P90':>8} {'Impact (vs base)':>20}")
    print("-" * 80)

    base_p50 = results["BASE"].completion_time_p50

    for scenario_id, res in results.items():
        impact = res.completion_time_p50 - base_p50 if scenario_id != "BASE" else 0
        print(
            f"{scenario_id:<20} "
            f"{res.completion_time_p10:>8.1f} "
            f"{res.completion_time_p50:>8.1f} "
            f"{res.completion_time_p90:>8.1f} "
            f"{impact:>+20.1f}"
        )


def demonstrate_scenario_composition():
    """Explicitly compose scenarios."""
    print("\n" + "=" * 80)
    print("SCENARIO COMPOSITION (EXPLICIT)")
    print("=" * 80)

    # Define two scenarios
    delayed = ScenarioProfile(
        scenario_id="DELAYED",
        description="20% activation delay",
        version="1.0.0",
        site_overrides={
            "SITE_001": {
                "activation_time": {
                    "type": "distribution_scale",
                    "parameters": {"scale_factor": 1.2},
                    "reason": "Regulatory delays"
                }
            }
        }
    )

    reduced_target = ScenarioProfile(
        scenario_id="REDUCED_TARGET",
        description="Lower enrollment target",
        version="1.0.0",
        trial_overrides={
            "target_enrollment": {
                "type": "direct_value",
                "value": 150,
                "reason": "Protocol amendment"
            }
        }
    )

    print(f"Scenario 1: {delayed.scenario_id}")
    print(f"  Overrides: {list(delayed.site_overrides.keys())}")

    print(f"\nScenario 2: {reduced_target.scenario_id}")
    print(f"  Overrides: {list(reduced_target.trial_overrides.keys())}")

    # Explicit composition
    combined = compose_scenarios(delayed, reduced_target)

    print(f"\nCombined scenario: {combined.scenario_id}")
    print(f"  Description: {combined.description}")
    print(f"  Site overrides: {list(combined.site_overrides.keys())}")
    print(f"  Trial overrides: {list(combined.trial_overrides.keys())}")
    print(f"  Based on: {combined.based_on_scenario}")


def demonstrate_version_control():
    """Demonstrate JSON serialization for version control."""
    print("\n" + "=" * 80)
    print("VERSION CONTROL PATTERNS")
    print("=" * 80)

    # Create scenario
    scenario = ScenarioProfile(
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

    # Serialize to JSON
    scenario_json = scenario.to_dict()
    json_str = json.dumps(scenario_json, indent=2)

    print("Scenario serialized to JSON:")
    print(json_str[:300] + "...")

    # This can be saved to file and version controlled
    # with open("scenarios/delayed_activation_v1.0.json", "w") as f:
    #     json.dump(scenario_json, f, indent=2)

    # Deserialize
    loaded_scenario = ScenarioProfile.from_dict(json.loads(json_str))

    print(f"\nDeserialized scenario:")
    print(f"  ID: {loaded_scenario.scenario_id}")
    print(f"  Version: {loaded_scenario.version}")
    print(f"  ✓ Round-trip successful")


def demonstrate_scenario_diffing():
    """Compare two scenarios."""
    print("\n" + "=" * 80)
    print("SCENARIO DIFFING")
    print("=" * 80)

    scenario_v1 = ScenarioProfile(
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

    scenario_v2 = ScenarioProfile(
        scenario_id="DELAYED_ACTIVATION",
        description="EU regulatory delays extend activation by 30%",
        version="2.0.0",
        site_overrides={
            "SITE_001": {
                "activation_time": {
                    "type": "distribution_scale",
                    "parameters": {"scale_factor": 1.3},  # Increased
                    "reason": "EU regulatory environment worsened"
                }
            }
        }
    )

    diff = diff_scenarios(scenario_v1, scenario_v2)

    print("Comparing scenarios:")
    print(f"  v1: {scenario_v1.version} (scale_factor=1.2)")
    print(f"  v2: {scenario_v2.version} (scale_factor=1.3)")

    print(f"\nDifferences:")
    print(json.dumps(diff, indent=2))


def demonstrate_calibration_workflow():
    """
    Demonstrate how scenarios support calibration.

    Key insight: Base trial gets better distributions over time.
    Scenarios remain relative adjustments.
    """
    print("\n" + "=" * 80)
    print("CALIBRATION WORKFLOW")
    print("=" * 80)

    # === WEEK 1: Initial Setup (Expert Estimates) ===
    print("\n--- Week 1: Expert Estimates ---")

    base_trial_v1 = Trial(
        trial_id="BASE_v1.0",
        target_enrollment=200,
        sites=[
            Site(
                site_id="SITE_001",
                activation_time=Triangular(low=30, mode=45, high=90),  # Expert estimate
                enrollment_rate=Gamma(shape=2, scale=1.5),
                dropout_rate=Bernoulli(p=0.15)
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

    # Scenario: "What if activation takes 20% longer?"
    delayed_scenario = ScenarioProfile(
        scenario_id="DELAYED_ACTIVATION",
        description="20% longer activation",
        version="1.0.0",
        site_overrides={
            "SITE_001": {
                "activation_time": {
                    "type": "distribution_scale",
                    "parameters": {"scale_factor": 1.2},
                    "reason": "Regulatory delays"
                }
            }
        }
    )

    engine = SimulationEngine(master_seed=42)

    base_results_v1 = engine.run(base_trial_v1, num_runs=50)
    delayed_results_v1 = engine.run(apply_scenario(base_trial_v1, delayed_scenario), num_runs=50)

    print(f"Base P50: {base_results_v1.completion_time_p50:.1f} days")
    print(f"Delayed P50: {delayed_results_v1.completion_time_p50:.1f} days")
    print(f"Impact: {delayed_results_v1.completion_time_p50 - base_results_v1.completion_time_p50:+.1f} days")

    # === WEEK 5: Calibration (Historical Data Collected) ===
    print("\n--- Week 5: Calibrated with Historical Data ---")

    # Simulate: Historical data shows activation is actually faster than estimate
    # Expert estimated mode=45, but historical average is 40
    base_trial_v2 = Trial(
        trial_id="BASE_v2.0_CALIBRATED",
        target_enrollment=200,
        sites=[
            Site(
                site_id="SITE_001",
                activation_time=Triangular(low=28, mode=40, high=65),  # Calibrated
                enrollment_rate=Gamma(shape=2, scale=1.5),
                dropout_rate=Bernoulli(p=0.15)
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

    # Apply SAME scenario to calibrated base
    base_results_v2 = engine.run(base_trial_v2, num_runs=50)
    delayed_results_v2 = engine.run(apply_scenario(base_trial_v2, delayed_scenario), num_runs=50)

    print(f"Base P50: {base_results_v2.completion_time_p50:.1f} days")
    print(f"Delayed P50: {delayed_results_v2.completion_time_p50:.1f} days")
    print(f"Impact: {delayed_results_v2.completion_time_p50 - base_results_v2.completion_time_p50:+.1f} days")

    # === Analysis: How did calibration affect scenario? ===
    print("\n--- Calibration Impact Analysis ---")

    initial_impact = delayed_results_v1.completion_time_p50 - base_results_v1.completion_time_p50
    calibrated_impact = delayed_results_v2.completion_time_p50 - base_results_v2.completion_time_p50

    print(f"Scenario impact on initial base: +{initial_impact:.1f} days")
    print(f"Scenario impact on calibrated base: +{calibrated_impact:.1f} days")
    print(f"Change in scenario relevance: {calibrated_impact - initial_impact:+.1f} days")

    print("\n✓ Key insight: Same scenario definition, different base → different absolute impact")
    print("✓ Scenario remains 20% adjustment, but base improved with data")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("SCENARIO SYSTEM DEMONSTRATION")
    print("=" * 80)
    print("\nDemonstrates:")
    print("1. Base + scenario (pure function, no mutation)")
    print("2. Multiple scenario comparison")
    print("3. Explicit scenario composition")
    print("4. Version control (JSON serialization)")
    print("5. Scenario diffing")
    print("6. Calibration workflow (base improves, scenarios stay relative)")

    demonstrate_base_plus_scenario()
    demonstrate_multiple_scenarios()
    demonstrate_scenario_composition()
    demonstrate_version_control()
    demonstrate_scenario_diffing()
    demonstrate_calibration_workflow()

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("""
Key Principles Demonstrated:

1. Pure Functions
   - apply_scenario(base, scenario) → new trial
   - No mutation, deterministic

2. Explicit Overrides
   - All changes visible in scenario.to_dict()
   - Reason field documents assumptions

3. Version Control
   - JSON-serializable
   - Git-friendly diffs

4. Calibration Support
   - Base trial improves with data
   - Scenarios remain relative adjustments
   - Can track: "How does scenario impact evolve?"

5. Architectural Integrity
   - Entities remain immutable
   - No runtime state
   - Engine never sees scenarios (pre-processing only)
""")

    print("=" * 80)
