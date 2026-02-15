"""
Example: Defining a complete trial specification using entities.

This demonstrates:
1. Creating Sites with uncertainty distributions
2. Defining Activities with dependencies and resource requirements
3. Specifying Resources with availability constraints
4. Building a PatientFlow state machine
5. Assembling a complete Trial specification
6. Serializing to JSON for calibration workflows
"""

import json
from seleensim.entities import Site, Activity, Resource, PatientFlow, Trial
from seleensim.distributions import Triangular, LogNormal, Gamma, Bernoulli


def build_trial_specification():
    """
    Build a complete trial specification.

    Scenario: Multi-site trial with:
    - 3 sites with varying characteristics
    - Site activation activities
    - Monitoring resources
    - Patient flow: enrollment -> treatment -> completion/dropout
    """

    # =========================================================================
    # 1. Define Sites (enrollment locations)
    # =========================================================================
    print("1. Defining Sites with stochastic activation and enrollment...")

    # High-performing site: Fast activation, high enrollment
    site_1 = Site(
        site_id="SITE_001",
        activation_time=Triangular(low=30, mode=45, high=60),  # Days to activate
        enrollment_rate=Gamma(shape=3, scale=2.5),  # Patients/month once active
        dropout_rate=Bernoulli(p=0.10),  # 10% dropout probability
        max_capacity=50  # Can handle up to 50 concurrent patients
    )

    # Medium-performing site: Moderate activation, moderate enrollment
    site_2 = Site(
        site_id="SITE_002",
        activation_time=Triangular(low=45, mode=60, high=90),
        enrollment_rate=Gamma(shape=2, scale=2.0),  # Slightly lower rate
        dropout_rate=Bernoulli(p=0.15),  # 15% dropout probability
        max_capacity=30
    )

    # Slow-performing site: Delayed activation, lower enrollment
    site_3 = Site(
        site_id="SITE_003",
        activation_time=Triangular(low=60, mode=90, high=150),
        enrollment_rate=Gamma(shape=1.5, scale=1.5),  # Lower rate
        dropout_rate=Bernoulli(p=0.20),  # 20% dropout probability
        max_capacity=None  # No capacity limit (small site, unlikely to hit limits)
    )

    print(f"   Created {len([site_1, site_2, site_3])} sites")
    print(f"   - {site_1.site_id}: High performer (capacity={site_1.max_capacity})")
    print(f"   - {site_2.site_id}: Medium performer (capacity={site_2.max_capacity})")
    print(f"   - {site_3.site_id}: Slow performer (unlimited capacity)")

    # =========================================================================
    # 2. Define Activities (tasks with dependencies)
    # =========================================================================
    print("\n2. Defining Activities with dependencies...")

    # Site activation activities
    act_irb_approval = Activity(
        activity_id="IRB_APPROVAL",
        duration=LogNormal(mean=60, cv=0.4),  # 60 days average, high variance
        dependencies=set(),  # No dependencies (can start immediately)
        required_resources=set(),  # No resource constraints
        success_probability=Bernoulli(p=0.95)  # 95% chance of approval
    )

    act_staff_hiring = Activity(
        activity_id="STAFF_HIRING",
        duration=LogNormal(mean=45, cv=0.3),
        dependencies={"IRB_APPROVAL"},  # Must wait for IRB approval
        required_resources={"HIRING_COORDINATOR"},
        success_probability=Bernoulli(p=0.90)  # 90% success rate
    )

    act_site_activation = Activity(
        activity_id="SITE_ACTIVATION",
        duration=Triangular(low=7, mode=14, high=21),  # Final activation steps
        dependencies={"IRB_APPROVAL", "STAFF_HIRING"},  # Must complete both first
        required_resources={"SITE_MONITOR"},
        success_probability=None  # Deterministic success once dependencies met
    )

    # Monitoring activities (ongoing)
    act_site_monitoring = Activity(
        activity_id="SITE_MONITORING",
        duration=LogNormal(mean=30, cv=0.2),  # Monthly monitoring visits
        dependencies={"SITE_ACTIVATION"},  # Can only monitor active sites
        required_resources={"SITE_MONITOR"}
    )

    activities = [act_irb_approval, act_staff_hiring, act_site_activation, act_site_monitoring]
    print(f"   Created {len(activities)} activities")
    for act in activities:
        deps = f" (depends on: {act.dependencies})" if act.dependencies else " (no dependencies)"
        print(f"   - {act.activity_id}{deps}")

    # =========================================================================
    # 3. Define Resources (constrained capacities)
    # =========================================================================
    print("\n3. Defining Resources with availability constraints...")

    res_hiring_coordinator = Resource(
        resource_id="HIRING_COORDINATOR",
        resource_type="staff",
        capacity=2,  # Only 2 hiring coordinators available
        availability=Bernoulli(p=0.85),  # 85% availability (account for sick days, etc.)
        utilization_rate=Gamma(shape=2, scale=20)  # Hours per hiring task
    )

    res_site_monitor = Resource(
        resource_id="SITE_MONITOR",
        resource_type="staff",
        capacity=5,  # 5 site monitors available
        availability=Bernoulli(p=0.90),  # 90% availability
        utilization_rate=Gamma(shape=3, scale=15)  # Hours per monitoring visit
    )

    resources = [res_hiring_coordinator, res_site_monitor]
    print(f"   Created {len(resources)} resource types")
    for res in resources:
        print(f"   - {res.resource_id} ({res.resource_type}): capacity={res.capacity}")

    # =========================================================================
    # 4. Define PatientFlow (state machine)
    # =========================================================================
    print("\n4. Defining PatientFlow state machine...")

    patient_flow = PatientFlow(
        flow_id="STANDARD_FLOW",
        states={"enrolled", "screening", "randomized", "treatment", "completed", "dropout"},
        initial_state="enrolled",
        terminal_states={"completed", "dropout"},
        transition_times={
            # Time from enrolled to screening
            ("enrolled", "screening"): Triangular(low=3, mode=7, high=14),
            # Time from screening to randomized (some fail screening)
            ("screening", "randomized"): Triangular(low=1, mode=3, high=7),
            # Screening failure leads to dropout
            ("screening", "dropout"): Triangular(low=1, mode=2, high=5),
            # Time from randomization to treatment start
            ("randomized", "treatment"): Triangular(low=1, mode=3, high=7),
            # Treatment duration (main phase)
            ("treatment", "completed"): LogNormal(mean=180, cv=0.25),
            # Dropout during treatment
            ("treatment", "dropout"): LogNormal(mean=90, cv=0.4)
        },
        transition_probabilities={
            # 85% pass screening, 15% fail
            ("screening", "randomized"): Bernoulli(p=0.85),
            ("screening", "dropout"): Bernoulli(p=0.15),
            # 80% complete treatment, 20% drop out
            ("treatment", "completed"): Bernoulli(p=0.80),
            ("treatment", "dropout"): Bernoulli(p=0.20)
        }
    )

    print(f"   Flow: {patient_flow.flow_id}")
    print(f"   States: {len(patient_flow.states)} ({', '.join(sorted(patient_flow.states))})")
    print(f"   Transitions: {len(patient_flow.transition_times)} with timing distributions")

    # =========================================================================
    # 5. Assemble Trial
    # =========================================================================
    print("\n5. Assembling complete Trial specification...")

    trial = Trial(
        trial_id="TRIAL_2025_001",
        target_enrollment=200,  # Goal: enroll 200 patients
        sites=[site_1, site_2, site_3],
        patient_flow=patient_flow,
        activities=activities,
        resources=resources
    )

    print(f"   Trial ID: {trial.trial_id}")
    print(f"   Target enrollment: {trial.target_enrollment} patients")
    print(f"   Sites: {len(trial.sites)}")
    print(f"   Activities: {len(trial.activities)}")
    print(f"   Resources: {len(trial.resources)}")

    # =========================================================================
    # 6. Demonstrate Serialization
    # =========================================================================
    print("\n6. Serializing to JSON (for calibration workflows)...")

    trial_dict = trial.to_dict()
    json_str = json.dumps(trial_dict, indent=2)

    # Save to file
    output_path = "trial_spec_example.json"
    with open(output_path, "w") as f:
        f.write(json_str)

    print(f"   Serialized to: {output_path}")
    print(f"   JSON size: {len(json_str)} characters")

    # =========================================================================
    # 7. Demonstrate Deterministic vs Stochastic Fields
    # =========================================================================
    print("\n7. Deterministic vs Stochastic breakdown:")
    print("\n   DETERMINISTIC (known at design time):")
    print(f"   - Trial structure: {trial.trial_id}, target={trial.target_enrollment}")
    print(f"   - Site IDs: {[s.site_id for s in trial.sites]}")
    print(f"   - Activity dependencies: {[a.activity_id for a in trial.activities]}")
    print(f"   - State machine structure: {len(patient_flow.states)} states")

    print("\n   STOCHASTIC (uncertain, modeled as distributions):")
    print(f"   - Site activation times: Each site has Triangular distribution")
    print(f"   - Enrollment rates: Each site has Gamma distribution")
    print(f"   - Activity durations: LogNormal/Triangular distributions")
    print(f"   - Patient flow transitions: Bernoulli probabilities & timing distributions")

    print("\n" + "=" * 70)
    print("Trial specification complete and ready for simulation!")
    print("=" * 70)

    return trial


if __name__ == "__main__":
    trial_spec = build_trial_specification()

    # Additional validation: Verify immutability
    print("\n8. Verifying immutability...")
    try:
        trial_spec.trial_id = "MODIFIED"
        print("   ERROR: Trial was mutated! (This should not happen)")
    except Exception:
        print("   ✓ Trial is immutable (frozen dataclass)")

    # Verify no sampling occurs in entities
    print("\n9. Verifying entities don't sample distributions...")
    print("   Note: Entities hold Distribution REFERENCES, not sampled values.")
    print("   The simulation engine will sample these during Monte Carlo runs.")
    print("   This ensures trial specs are deterministic and reproducible.")

    site = trial_spec.sites[0]
    print(f"\n   Example - Site {site.site_id}:")
    print(f"   - activation_time is a {type(site.activation_time).__name__} object")
    print(f"   - NOT a sampled value (e.g., 45.3 days)")
    print(f"   - The engine will call site.activation_time.sample(seed=X) during simulation")
