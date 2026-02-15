"""
Tests for constraint evaluation system.

Focus areas:
1. Validity vs Feasibility separation
2. Composition rules (max delays, merge overrides)
3. Idempotent throttling via execution_parameters
4. Explainability (every result has explanation)
5. Domain-agnostic design (no clinical trial specifics in constraints)
"""

import pytest
from seleensim.constraints import (
    ConstraintResult,
    TemporalPrecedenceConstraint,
    PredecessorConstraint,
    ResourceCapacityConstraint,
    BudgetThrottlingConstraint,
    LinearResponseCurve,
    NoCapacityDegradation,
    LinearCapacityDegradation,
    compose_constraint_results
)


# =============================================================================
# Mock State and Events for Testing
# =============================================================================


class MockSimulationState:
    """Mock simulation state for constraint testing."""

    def __init__(self):
        self._completion_times = {}  # (event_type, entity_id) -> time
        self._activity_completions = {}  # activity_id -> time
        self._resource_availability = {}  # resource_id -> next_available_time
        self._budget = 100000  # Default budget

    def set_completion_time(self, event_type, entity_id, time):
        self._completion_times[(event_type, entity_id)] = time

    def get_completion_time(self, event_type, entity_id):
        return self._completion_times.get((event_type, entity_id))

    def set_activity_completion_time(self, activity_id, time):
        self._activity_completions[activity_id] = time

    def get_activity_completion_time(self, activity_id):
        return self._activity_completions.get(activity_id)

    def set_resource_availability(self, resource_id, time):
        self._resource_availability[resource_id] = time

    def get_resource_availability(self, resource_id, current_time):
        available_time = self._resource_availability.get(resource_id)
        if available_time is None or available_time <= current_time:
            return None  # Available now
        return available_time

    def get_available_budget(self, time):
        return self._budget

    def set_available_budget(self, budget):
        self._budget = budget


class MockEvent:
    """Mock event for constraint testing."""

    def __init__(self, event_id, event_type, entity_id, time, **kwargs):
        self.event_id = event_id
        self.event_type = event_type
        self.entity_id = entity_id
        self.time = time
        self.execution_parameters = {}

        # Optional attributes
        for key, value in kwargs.items():
            setattr(self, key, value)


# =============================================================================
# Test ConstraintResult Factories
# =============================================================================


class TestConstraintResultFactories:
    """Test ConstraintResult factory methods."""

    def test_satisfied_factory(self):
        result = ConstraintResult.satisfied("All good")
        assert result.is_valid is True
        assert result.earliest_valid_time is None
        assert result.delay == 0.0
        assert result.parameter_overrides == {}
        assert "All good" in result.explanation

    def test_invalid_until_factory(self):
        result = ConstraintResult.invalid_until(50.0, "Must wait")
        assert result.is_valid is False
        assert result.earliest_valid_time == 50.0
        assert result.delay == 0.0
        assert result.parameter_overrides == {}
        assert "Must wait" in result.explanation

    def test_delayed_by_factory(self):
        result = ConstraintResult.delayed_by(10.0, "Resource busy")
        assert result.is_valid is True
        assert result.earliest_valid_time is None
        assert result.delay == 10.0
        assert result.parameter_overrides == {}
        assert "Resource busy" in result.explanation

    def test_modified_factory(self):
        result = ConstraintResult.modified({"duration": 30}, "Throttled")
        assert result.is_valid is True
        assert result.earliest_valid_time is None
        assert result.delay == 0.0
        assert result.parameter_overrides == {"duration": 30}
        assert "Throttled" in result.explanation


# =============================================================================
# Test Temporal Precedence Constraint (Validity)
# =============================================================================


class TestTemporalPrecedenceConstraint:
    """Test temporal precedence constraint (validity layer)."""

    def test_predecessor_completes_before_event_valid(self):
        """Event valid if predecessor completes before event time."""
        constraint = TemporalPrecedenceConstraint(
            predecessor_event_type="site_activation",
            dependent_event_type="enrollment"
        )

        state = MockSimulationState()
        state.set_completion_time("site_activation", "SITE001", 40.0)

        event = MockEvent(
            event_id="enrollment_1",
            event_type="enrollment",
            entity_id="SITE001",
            time=50.0
        )

        result = constraint.evaluate(state, event)

        assert result.is_valid is True
        assert result.earliest_valid_time is None
        assert "completed at T=40" in result.explanation

    def test_predecessor_completes_after_event_invalid(self):
        """Event invalid if predecessor completes after event time."""
        constraint = TemporalPrecedenceConstraint(
            predecessor_event_type="site_activation",
            dependent_event_type="enrollment"
        )

        state = MockSimulationState()
        state.set_completion_time("site_activation", "SITE001", 60.0)

        event = MockEvent(
            event_id="enrollment_1",
            event_type="enrollment",
            entity_id="SITE001",
            time=50.0
        )

        result = constraint.evaluate(state, event)

        assert result.is_valid is False
        assert result.earliest_valid_time == 60.0
        assert "cannot occur before" in result.explanation

    def test_predecessor_not_scheduled_invalid(self):
        """Event invalid if predecessor not scheduled yet."""
        constraint = TemporalPrecedenceConstraint(
            predecessor_event_type="site_activation",
            dependent_event_type="enrollment"
        )

        state = MockSimulationState()
        # Predecessor not set

        event = MockEvent(
            event_id="enrollment_1",
            event_type="enrollment",
            entity_id="SITE001",
            time=50.0
        )

        result = constraint.evaluate(state, event)

        assert result.is_valid is False
        assert result.earliest_valid_time == float('inf')
        assert "not scheduled" in result.explanation

    def test_not_applicable_to_other_event_types(self):
        """Constraint only applies to dependent event type."""
        constraint = TemporalPrecedenceConstraint(
            predecessor_event_type="site_activation",
            dependent_event_type="enrollment"
        )

        state = MockSimulationState()

        event = MockEvent(
            event_id="other_1",
            event_type="monitoring",
            entity_id="SITE001",
            time=50.0
        )

        result = constraint.evaluate(state, event)

        assert result.is_valid is True
        assert "Not applicable" in result.explanation


# =============================================================================
# Test Predecessor Constraint (Activity Dependencies - Validity)
# =============================================================================


class TestPredecessorConstraint:
    """Test predecessor constraint for activity dependencies."""

    def test_no_predecessors_valid(self):
        """Activity with no predecessors is always valid."""
        constraint = PredecessorConstraint()

        state = MockSimulationState()

        event = MockEvent(
            event_id="act_1",
            event_type="activity",
            entity_id="SITE001",
            time=50.0,
            activity_id="ACT001",
            predecessors=set()
        )

        result = constraint.evaluate(state, event)

        assert result.is_valid is True
        assert "No predecessors" in result.explanation

    def test_all_predecessors_complete_valid(self):
        """Activity valid if all predecessors completed."""
        constraint = PredecessorConstraint()

        state = MockSimulationState()
        state.set_activity_completion_time("ACT000", 40.0)
        state.set_activity_completion_time("ACT001", 45.0)

        event = MockEvent(
            event_id="act_2",
            event_type="activity",
            entity_id="SITE001",
            time=50.0,
            activity_id="ACT002",
            predecessors={"ACT000", "ACT001"}
        )

        result = constraint.evaluate(state, event)

        assert result.is_valid is True
        assert "completed by T=45" in result.explanation

    def test_predecessor_completes_after_invalid(self):
        """Activity invalid if any predecessor completes after event time."""
        constraint = PredecessorConstraint()

        state = MockSimulationState()
        state.set_activity_completion_time("ACT000", 40.0)
        state.set_activity_completion_time("ACT001", 60.0)  # After event

        event = MockEvent(
            event_id="act_2",
            event_type="activity",
            entity_id="SITE001",
            time=50.0,
            activity_id="ACT002",
            predecessors={"ACT000", "ACT001"}
        )

        result = constraint.evaluate(state, event)

        assert result.is_valid is False
        assert result.earliest_valid_time == 60.0
        assert "completes at T=60" in result.explanation

    def test_predecessor_not_scheduled_invalid(self):
        """Activity invalid if any predecessor not scheduled."""
        constraint = PredecessorConstraint()

        state = MockSimulationState()
        state.set_activity_completion_time("ACT000", 40.0)
        # ACT001 not scheduled

        event = MockEvent(
            event_id="act_2",
            event_type="activity",
            entity_id="SITE001",
            time=50.0,
            activity_id="ACT002",
            predecessors={"ACT000", "ACT001"}
        )

        result = constraint.evaluate(state, event)

        assert result.is_valid is False
        assert result.earliest_valid_time == float('inf')
        assert "ACT001" in result.explanation
        assert "not scheduled" in result.explanation


# =============================================================================
# Test Resource Capacity Constraint (Feasibility)
# =============================================================================


class TestResourceCapacityConstraint:
    """Test resource capacity constraint (feasibility layer)."""

    def test_resource_available_feasible(self):
        """Event feasible if resource available."""
        constraint = ResourceCapacityConstraint(resource_id="MONITOR")

        state = MockSimulationState()
        # Resource available (not set = available)

        event = MockEvent(
            event_id="act_1",
            event_type="activity",
            entity_id="SITE001",
            time=50.0,
            required_resources={"MONITOR"}
        )

        result = constraint.evaluate(state, event)

        assert result.is_valid is True
        assert result.delay == 0.0
        assert "available" in result.explanation

    def test_resource_busy_delayed(self):
        """Event delayed if resource not available until later."""
        constraint = ResourceCapacityConstraint(resource_id="MONITOR")

        state = MockSimulationState()
        state.set_resource_availability("MONITOR", 60.0)  # Available at T=60

        event = MockEvent(
            event_id="act_1",
            event_type="activity",
            entity_id="SITE001",
            time=50.0,
            required_resources={"MONITOR"}
        )

        result = constraint.evaluate(state, event)

        assert result.is_valid is True  # Still valid, just delayed
        assert result.delay == 10.0  # 60 - 50
        assert "at capacity" in result.explanation
        assert "T=60" in result.explanation

    def test_not_applicable_without_resources(self):
        """Constraint not applicable if event doesn't require resources."""
        constraint = ResourceCapacityConstraint(resource_id="MONITOR")

        state = MockSimulationState()

        event = MockEvent(
            event_id="act_1",
            event_type="activity",
            entity_id="SITE001",
            time=50.0
            # No required_resources attribute
        )

        result = constraint.evaluate(state, event)

        assert result.is_valid is True
        assert result.delay == 0.0
        assert "No resources required" in result.explanation

    def test_not_applicable_to_different_resource(self):
        """Constraint not applicable if event requires different resource."""
        constraint = ResourceCapacityConstraint(resource_id="MONITOR")

        state = MockSimulationState()

        event = MockEvent(
            event_id="act_1",
            event_type="activity",
            entity_id="SITE001",
            time=50.0,
            required_resources={"COORDINATOR"}  # Different resource
        )

        result = constraint.evaluate(state, event)

        assert result.is_valid is True
        assert result.delay == 0.0
        assert "Does not require MONITOR" in result.explanation


# =============================================================================
# Test Capacity Response Curves (Calibration-Ready Degradation)
# =============================================================================


class TestCapacityResponseCurves:
    """Test capacity response curves for calibration readiness."""

    def test_no_capacity_degradation_always_returns_one(self):
        """NoCapacityDegradation always returns 1.0 (no efficiency penalty)."""
        curve = NoCapacityDegradation()

        assert curve.sample_efficiency_multiplier(0.5, seed=42) == 1.0
        assert curve.sample_efficiency_multiplier(1.0, seed=42) == 1.0
        assert curve.sample_efficiency_multiplier(1.5, seed=42) == 1.0
        assert curve.sample_efficiency_multiplier(2.0, seed=42) == 1.0

        assert curve.mean_efficiency_multiplier(1.5) == 1.0

    def test_linear_capacity_degradation_below_threshold(self):
        """LinearCapacityDegradation returns 1.0 below threshold."""
        curve = LinearCapacityDegradation(threshold=0.8, max_multiplier=2.0)

        assert curve.sample_efficiency_multiplier(0.5, seed=42) == 1.0
        assert curve.sample_efficiency_multiplier(0.8, seed=42) == 1.0
        assert curve.mean_efficiency_multiplier(0.7) == 1.0

    def test_linear_capacity_degradation_at_max(self):
        """LinearCapacityDegradation returns max_multiplier at max_utilization."""
        curve = LinearCapacityDegradation(
            threshold=0.8,
            max_multiplier=2.0,
            max_utilization=1.5
        )

        assert curve.sample_efficiency_multiplier(1.5, seed=42) == 2.0
        assert curve.sample_efficiency_multiplier(2.0, seed=42) == 2.0  # Capped
        assert curve.mean_efficiency_multiplier(1.5) == 2.0

    def test_linear_capacity_degradation_interpolates(self):
        """LinearCapacityDegradation interpolates between threshold and max."""
        curve = LinearCapacityDegradation(
            threshold=0.8,
            max_multiplier=2.0,
            max_utilization=1.5
        )

        # At utilization=1.0:
        # progress = (1.0 - 0.8) / (1.5 - 0.8) = 0.2 / 0.7 ≈ 0.286
        # multiplier = 1.0 + (2.0 - 1.0) * 0.286 ≈ 1.286
        multiplier = curve.sample_efficiency_multiplier(1.0, seed=42)
        assert abs(multiplier - 1.286) < 0.01

    def test_linear_capacity_degradation_parameter_validation(self):
        """LinearCapacityDegradation validates parameters."""
        # Negative threshold
        with pytest.raises(ValueError, match="threshold must be >= 0.0"):
            LinearCapacityDegradation(threshold=-0.1)

        # max_multiplier < 1.0
        with pytest.raises(ValueError, match="max_multiplier must be >= 1.0"):
            LinearCapacityDegradation(max_multiplier=0.5)

        # max_utilization <= threshold
        with pytest.raises(ValueError, match="max_utilization.*must be > threshold"):
            LinearCapacityDegradation(threshold=1.0, max_utilization=0.9)

    def test_capacity_degradation_calibration_example(self):
        """Example: Change degradation curve without code change."""
        # Week 1: Conservative estimate (2x max slowdown)
        curve_v1 = LinearCapacityDegradation(
            threshold=0.8,
            max_multiplier=2.0,
            max_utilization=1.5
        )

        # Week 6: Calibrated from data (3x max slowdown, starts earlier)
        curve_v2 = LinearCapacityDegradation(
            threshold=0.7,
            max_multiplier=3.0,
            max_utilization=1.5
        )

        # At utilization=1.3:
        # v1: moderate degradation
        # v2: higher degradation
        multiplier_v1 = curve_v1.mean_efficiency_multiplier(1.3)
        multiplier_v2 = curve_v2.mean_efficiency_multiplier(1.3)

        assert multiplier_v2 > multiplier_v1
        # This proves calibration-ready: behavior changed via parameters only


# =============================================================================
# Test Budget Throttling Constraint (Feasibility + Idempotency)
# =============================================================================


class TestBudgetThrottlingConstraint:
    """Test budget throttling constraint with idempotent caching."""

    def test_first_evaluation_computes_throttling(self):
        """First evaluation computes throttling and caches in execution_parameters."""
        constraint = BudgetThrottlingConstraint(
            budget_per_day=1000,
            response_curve=LinearResponseCurve(min_speed_ratio=0.5)
        )

        state = MockSimulationState()
        # Limited budget: only 60% of what's needed
        # Full speed needs: 20 days * 1000/day = 20000
        # Available: 12000 (60%)
        state.set_available_budget(12000)

        event = MockEvent(
            event_id="act_1",
            event_type="activity",
            entity_id="SITE001",
            time=50.0,
            duration=20.0
        )

        result = constraint.evaluate(state, event)

        assert result.is_valid is True
        assert result.delay == 0.0
        assert "duration" in result.parameter_overrides
        assert result.parameter_overrides["duration"] > 20.0  # Throttled

        # Check that execution_parameters cached
        assert "duration_multiplier" in event.execution_parameters
        assert "budget_applied" in event.execution_parameters

    def test_second_evaluation_uses_cached_throttling(self):
        """Second evaluation returns cached throttling (idempotent)."""
        constraint = BudgetThrottlingConstraint(
            budget_per_day=1000,
            response_curve=LinearResponseCurve(min_speed_ratio=0.5)
        )

        state = MockSimulationState()
        state.set_available_budget(30000)

        event = MockEvent(
            event_id="act_1",
            event_type="activity",
            entity_id="SITE001",
            time=50.0,
            duration=20.0
        )

        # First evaluation
        result1 = constraint.evaluate(state, event)
        throttled_duration_1 = result1.parameter_overrides["duration"]

        # Change budget (simulate different state)
        state.set_available_budget(50000)

        # Second evaluation - should return SAME throttling (cached)
        result2 = constraint.evaluate(state, event)
        throttled_duration_2 = result2.parameter_overrides["duration"]

        assert throttled_duration_1 == throttled_duration_2
        assert "cached" in result2.explanation.lower()

    def test_different_events_get_independent_throttling(self):
        """Different event IDs get independent throttling decisions."""
        constraint = BudgetThrottlingConstraint(
            budget_per_day=1000,
            response_curve=LinearResponseCurve(min_speed_ratio=0.5)
        )

        state = MockSimulationState()
        # Limited budget: only enough for partial acceleration
        state.set_available_budget(15000)

        event1 = MockEvent(
            event_id="act_1",
            event_type="activity",
            entity_id="SITE001",
            time=50.0,
            duration=20.0  # Needs 20000 for full speed
        )

        event2 = MockEvent(
            event_id="act_2",  # Different ID
            event_type="activity",
            entity_id="SITE002",
            time=50.0,
            duration=30.0  # Needs 30000 for full speed
        )

        # Evaluate both
        result1 = constraint.evaluate(state, event1)
        result2 = constraint.evaluate(state, event2)

        # Both should have throttling, but different values
        throttled1 = result1.parameter_overrides["duration"]
        throttled2 = result2.parameter_overrides["duration"]

        assert throttled1 > 20.0  # Throttled due to limited budget
        assert throttled2 > 30.0  # Throttled even more (needs more budget)
        assert throttled1 != throttled2

    def test_not_applicable_without_duration(self):
        """Constraint not applicable if event has no duration."""
        constraint = BudgetThrottlingConstraint(
            budget_per_day=1000,
            response_curve=LinearResponseCurve(min_speed_ratio=0.5)
        )

        state = MockSimulationState()

        event = MockEvent(
            event_id="act_1",
            event_type="event",
            entity_id="SITE001",
            time=50.0
            # No duration attribute
        )

        result = constraint.evaluate(state, event)

        assert result.is_valid is True
        assert result.delay == 0.0
        assert result.parameter_overrides == {}
        assert "No duration" in result.explanation


# =============================================================================
# Test Constraint Composition
# =============================================================================


class TestConstraintComposition:
    """Test composition of multiple constraint results."""

    def test_validity_composes_via_and(self):
        """Multiple validity constraints compose via AND."""
        results = [
            ConstraintResult.satisfied("OK 1"),
            ConstraintResult.invalid_until(50.0, "Invalid 2"),
            ConstraintResult.satisfied("OK 3")
        ]

        combined = compose_constraint_results(results)

        assert combined.is_valid is False  # Any false → false

    def test_earliest_valid_time_composes_via_max(self):
        """earliest_valid_time composes via MAX (most restrictive)."""
        results = [
            ConstraintResult.invalid_until(40.0, "Wait 1"),
            ConstraintResult.invalid_until(60.0, "Wait 2"),
            ConstraintResult.invalid_until(50.0, "Wait 3")
        ]

        combined = compose_constraint_results(results)

        assert combined.earliest_valid_time == 60.0  # MAX

    def test_delay_composes_via_max(self):
        """Delays compose via MAX (longest delay wins)."""
        results = [
            ConstraintResult.delayed_by(5.0, "Delay 1"),
            ConstraintResult.delayed_by(10.0, "Delay 2"),
            ConstraintResult.delayed_by(3.0, "Delay 3")
        ]

        combined = compose_constraint_results(results)

        assert combined.delay == 10.0  # MAX

    def test_parameter_overrides_merge(self):
        """Parameter overrides merge (later wins on conflict)."""
        results = [
            ConstraintResult.modified({"duration": 20, "cost": 5000}, "Mod 1"),
            ConstraintResult.modified({"duration": 30}, "Mod 2"),  # Overrides duration
            ConstraintResult.modified({"priority": "high"}, "Mod 3")
        ]

        combined = compose_constraint_results(results)

        assert combined.parameter_overrides["duration"] == 30  # Later wins
        assert combined.parameter_overrides["cost"] == 5000
        assert combined.parameter_overrides["priority"] == "high"

    def test_explanations_concatenate(self):
        """Explanations concatenate with separator."""
        results = [
            ConstraintResult.satisfied("Reason 1"),
            ConstraintResult.delayed_by(5.0, "Reason 2"),
            ConstraintResult.modified({}, "Reason 3")
        ]

        combined = compose_constraint_results(results)

        assert "Reason 1" in combined.explanation
        assert "Reason 2" in combined.explanation
        assert "Reason 3" in combined.explanation
        assert ";" in combined.explanation  # Separator

    def test_validity_and_feasibility_combine(self):
        """Validity constraints (hard) + feasibility constraints (soft) combine."""
        results = [
            ConstraintResult.invalid_until(50.0, "Must wait for predecessor"),
            ConstraintResult.delayed_by(10.0, "Resource busy"),
            ConstraintResult.modified({"duration": 30}, "Budget throttled")
        ]

        combined = compose_constraint_results(results)

        assert combined.is_valid is False  # Validity failed
        assert combined.earliest_valid_time == 50.0
        assert combined.delay == 10.0  # Feasibility delay still recorded
        assert combined.parameter_overrides["duration"] == 30  # Modification still applies


# =============================================================================
# Integration Test: Event Lifecycle
# =============================================================================


class TestEventLifecycle:
    """Integration test showing how constraints work together in event lifecycle."""

    def test_event_reschedule_due_to_validity_constraint(self):
        """Event blocked by validity constraint, must reschedule."""
        # Temporal precedence: enrollment requires site activation
        constraint = TemporalPrecedenceConstraint(
            predecessor_event_type="site_activation",
            dependent_event_type="enrollment"
        )

        state = MockSimulationState()
        state.set_completion_time("site_activation", "SITE001", 60.0)

        # Enrollment proposed at T=50 (before activation)
        event = MockEvent(
            event_id="enrollment_1",
            event_type="enrollment",
            entity_id="SITE001",
            time=50.0
        )

        result = constraint.evaluate(state, event)

        # Engine should reschedule to T=60
        assert result.is_valid is False
        assert result.earliest_valid_time == 60.0

        # Simulate engine rescheduling
        event.time = result.earliest_valid_time

        # Re-evaluate at T=60
        result2 = constraint.evaluate(state, event)
        assert result2.is_valid is True  # Now valid

    def test_event_delayed_by_resource_constraint(self):
        """Event valid but delayed by resource availability."""
        constraint = ResourceCapacityConstraint(resource_id="MONITOR")

        state = MockSimulationState()
        state.set_resource_availability("MONITOR", 55.0)

        event = MockEvent(
            event_id="act_1",
            event_type="activity",
            entity_id="SITE001",
            time=50.0,
            required_resources={"MONITOR"}
        )

        result = constraint.evaluate(state, event)

        # Valid, but must delay
        assert result.is_valid is True
        assert result.delay == 5.0  # Wait until T=55

        # Engine computes: new_time = 50 + 5 = 55
        new_time = event.time + result.delay
        assert new_time == 55.0

    def test_event_throttled_idempotently(self):
        """Event throttled once, then cached on re-evaluation."""
        constraint = BudgetThrottlingConstraint(
            budget_per_day=1000,
            response_curve=LinearResponseCurve(min_speed_ratio=0.5)
        )

        state = MockSimulationState()
        state.set_available_budget(30000)

        event = MockEvent(
            event_id="act_1",
            event_type="activity",
            entity_id="SITE001",
            time=50.0,
            duration=20.0
        )

        # First evaluation: compute throttling
        result1 = constraint.evaluate(state, event)
        throttled_duration = result1.parameter_overrides["duration"]

        # Simulate engine rescheduling event due to other constraint
        event.time = 55.0

        # Second evaluation: should return cached throttling
        result2 = constraint.evaluate(state, event)

        assert result2.parameter_overrides["duration"] == throttled_duration
        assert "cached" in result2.explanation.lower()
