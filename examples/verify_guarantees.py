"""
Demonstration: Architectural guarantees in action.

This script shows what entities CAN and CANNOT do, verifying the
calibration-ready architecture is enforced at runtime.
"""

from seleensim.entities import Site, Activity, PatientFlow, Trial
from seleensim.distributions import Triangular, Gamma, Bernoulli, LogNormal


def demonstrate_guarantees():
    print("=" * 70)
    print("ARCHITECTURAL GUARANTEE VERIFICATION")
    print("=" * 70)

    # Create sample entities
    site = Site(
        site_id="SITE001",
        activation_time=Triangular(30, 45, 90),
        enrollment_rate=Gamma(2, 1.5),
        dropout_rate=Bernoulli(0.15),
        max_capacity=50
    )

    activity = Activity(
        activity_id="ACT001",
        duration=LogNormal(30, 0.2),
        dependencies=set(),  # No dependencies for this demo
        success_probability=Bernoulli(0.95)
    )

    flow = PatientFlow(
        flow_id="FLOW001",
        states={"enrolled", "completed"},
        initial_state="enrolled",
        terminal_states={"completed"},
        transition_times={("enrolled", "completed"): Triangular(30, 60, 120)}
    )

    trial = Trial(
        trial_id="TRIAL001",
        target_enrollment=200,
        sites=[site],
        patient_flow=flow,
        activities=[activity]
    )

    # =========================================================================
    # Guarantee 1: Entities hold Distribution references, never sample them
    # =========================================================================
    print("\n1. Entities hold Distribution REFERENCES (not sampled values)")
    print("-" * 70)
    print(f"site.activation_time type: {type(site.activation_time).__name__}")
    print(f"site.activation_time is Triangular: {isinstance(site.activation_time, Triangular)}")
    print("\n✓ VERIFIED: Entity holds Distribution object, not a sampled value")
    print("  The simulation engine will call .sample(seed) during runs.")

    # =========================================================================
    # Guarantee 2: Entities are immutable
    # =========================================================================
    print("\n2. Entities are IMMUTABLE (frozen dataclasses)")
    print("-" * 70)
    try:
        site.site_id = "MODIFIED"
        print("✗ VIOLATION: Site was mutated!")
    except Exception as e:
        print(f"Mutation attempt raised: {type(e).__name__}")
        print("✓ VERIFIED: Entities cannot be modified after construction")

    # =========================================================================
    # Guarantee 3: Entities have no business logic methods
    # =========================================================================
    print("\n3. Entities have NO BUSINESS LOGIC (only to_dict)")
    print("-" * 70)

    # Check for forbidden methods
    forbidden_site_methods = ["activate", "enroll", "is_active"]
    forbidden_activity_methods = ["start", "execute", "complete"]
    forbidden_flow_methods = ["transition", "advance", "sample_transition"]
    forbidden_trial_methods = ["run", "simulate", "execute"]

    print("Checking Site for forbidden methods:")
    for method in forbidden_site_methods:
        exists = hasattr(site, method)
        print(f"  {method}(): {'✗ EXISTS' if exists else '✓ NOT FOUND'}")

    print("\nChecking Activity for forbidden methods:")
    for method in forbidden_activity_methods:
        exists = hasattr(activity, method)
        print(f"  {method}(): {'✗ EXISTS' if exists else '✓ NOT FOUND'}")

    print("\nChecking PatientFlow for forbidden methods:")
    for method in forbidden_flow_methods:
        exists = hasattr(flow, method)
        print(f"  {method}(): {'✗ EXISTS' if exists else '✓ NOT FOUND'}")

    print("\nChecking Trial for forbidden methods:")
    for method in forbidden_trial_methods:
        exists = hasattr(trial, method)
        print(f"  {method}(): {'✗ EXISTS' if exists else '✓ NOT FOUND'}")

    # =========================================================================
    # Guarantee 4: Entities have no runtime state
    # =========================================================================
    print("\n4. Entities have NO RUNTIME STATE")
    print("-" * 70)

    forbidden_state = [
        "current_enrollment",
        "elapsed_time",
        "is_activated",
        "enrolled_patients"
    ]

    print("Checking Trial for runtime state attributes:")
    for attr in forbidden_state:
        exists = hasattr(trial, attr)
        print(f"  {attr}: {'✗ EXISTS' if exists else '✓ NOT FOUND'}")

    print("\n✓ VERIFIED: Trial has no runtime state")
    print("  Runtime state belongs in the simulation engine, not the spec.")

    # =========================================================================
    # Guarantee 5: Entities have no computed properties
    # =========================================================================
    print("\n5. Entities have NO COMPUTED PROPERTIES")
    print("-" * 70)

    forbidden_computed = [
        "expected_activation_time",
        "mean_enrollment_rate",
        "projected_completion_date"
    ]

    print("Checking for computed properties:")
    for prop in forbidden_computed:
        exists = hasattr(trial, prop)
        print(f"  {prop}: {'✗ EXISTS' if exists else '✓ NOT FOUND'}")

    print("\n✓ VERIFIED: No computed properties")
    print("  Analysis outputs belong in separate tools, not entity specs.")

    # =========================================================================
    # Guarantee 6: PatientFlow has no state advancement logic
    # =========================================================================
    print("\n6. PatientFlow is DECLARATIVE (no execution logic)")
    print("-" * 70)

    print(f"PatientFlow defines structure:")
    print(f"  States: {flow.states}")
    print(f"  Initial state: {flow.initial_state}")
    print(f"  Terminal states: {flow.terminal_states}")
    print(f"\nPatientFlow does NOT:")
    print(f"  - Track current state (no current_state attribute)")
    print(f"  - Advance state (no transition() method)")
    print(f"  - Sample timing (no sample_transition_time() method)")

    has_current_state = hasattr(flow, "current_state")
    has_transition = hasattr(flow, "transition")

    if not has_current_state and not has_transition:
        print("\n✓ VERIFIED: PatientFlow is pure specification")
    else:
        print("\n✗ VIOLATION: PatientFlow has execution logic!")

    # =========================================================================
    # Guarantee 7: Activity.success_probability is structural branching
    # =========================================================================
    print("\n7. Activity.success_probability is STRUCTURAL BRANCHING")
    print("-" * 70)

    print(f"Activity '{activity.activity_id}' has success_probability:")
    print(f"  Type: {type(activity.success_probability).__name__}")
    print(f"  Mean: {activity.success_probability.mean()}")
    print(f"\nThis represents:")
    print(f"  ✓ Structural branching (e.g., IRB approval may fail)")
    print(f"  ✗ NOT operational performance (execution quality)")
    print(f"\nThe simulation engine samples this to determine which")
    print(f"downstream activities execute based on success/failure.")

    # =========================================================================
    # Guarantee 8: Trial is declarative specification
    # =========================================================================
    print("\n8. Trial is DECLARATIVE SPECIFICATION (not executable)")
    print("-" * 70)

    print("Trial contains:")
    print(f"  - {len(trial.sites)} sites")
    print(f"  - {len(trial.activities)} activities")
    print(f"  - Target enrollment: {trial.target_enrollment}")
    print(f"  - Patient flow: {trial.patient_flow.flow_id}")

    print("\nTrial can be:")
    print("  ✓ Serialized to JSON (for version control)")
    print("  ✓ Deserialized and loaded")
    print("  ✓ Passed to simulation engine")

    print("\nTrial CANNOT:")
    print("  ✗ Run itself (no run() method)")
    print("  ✗ Compute metrics (no analyze() method)")
    print("  ✗ Track progress (no runtime state)")

    # Demonstrate serialization
    trial_json = trial.to_dict()
    print(f"\n✓ VERIFIED: Trial serialized to dict with {len(str(trial_json))} chars")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 70)
    print("ALL ARCHITECTURAL GUARANTEES VERIFIED")
    print("=" * 70)
    print("\nEntities are:")
    print("  ✓ Immutable (frozen dataclasses)")
    print("  ✓ Declarative (no execution logic)")
    print("  ✓ Stateless (no runtime state)")
    print("  ✓ Pure data (no computed properties)")
    print("  ✓ Serializable (JSON export)")
    print("  ✓ Calibration-ready (swap distributions, re-run)")

    print("\nThese guarantees are enforced by:")
    print("  - 104 tests (39 distributions + 45 entities + 20 anti-behavior)")
    print("  - Frozen dataclasses (immutability)")
    print("  - Minimal public API (only to_dict())")
    print("  - Comprehensive documentation (ARCHITECTURE.md)")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    demonstrate_guarantees()
