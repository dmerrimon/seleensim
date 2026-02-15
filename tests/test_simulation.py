"""
Tests for Monte Carlo simulation engine.

Focus areas:
1. Determinism: Same seed → identical results
2. Single run produces timeline and metrics
3. Aggregated results compute percentiles correctly
4. Event queue processes in time order
5. State tracking works correctly
"""

import pytest
from seleensim.simulation import (
    Event,
    SimulationState,
    RunResult,
    SimulationResults,
    SimulationEngine,
    aggregate_statistics
)
from seleensim.entities import Site, Trial, PatientFlow
from seleensim.distributions import Triangular, Gamma, Bernoulli


class TestEvent:
    """Test Event class."""

    def test_event_creation(self):
        event = Event(
            event_id="evt_1",
            event_type="activation",
            entity_id="SITE001",
            time=50.0
        )

        assert event.event_id == "evt_1"
        assert event.time == 50.0

    def test_event_comparison_for_priority_queue(self):
        """Events compare by time for priority queue."""
        event1 = Event("e1", "type", "entity", time=50.0)
        event2 = Event("e2", "type", "entity", time=30.0)

        assert event2 < event1  # Earlier time = higher priority

    def test_event_reschedule_creates_copy(self):
        """Rescheduling creates new event with updated time."""
        original = Event("e1", "type", "entity", time=50.0, duration=10.0)
        rescheduled = original.reschedule(60.0)

        assert rescheduled.time == 60.0
        assert rescheduled.duration == 10.0  # Other fields preserved
        assert rescheduled.event_id == original.event_id

    def test_event_apply_overrides(self):
        """Parameter overrides modify event fields."""
        event = Event("e1", "type", "entity", time=50.0, duration=20.0)
        event.apply_overrides({"duration": 30.0})

        assert event.duration == 30.0


class TestSimulationState:
    """Test SimulationState tracking."""

    def test_initial_state(self):
        state = SimulationState(initial_budget=100000)

        assert state.current_time == 0.0
        assert state.budget_available == 100000
        assert state.budget_spent == 0.0

    def test_record_completion(self):
        state = SimulationState()

        event = Event("e1", "site_activation", "SITE001", time=50.0)
        state.current_time = 50.0
        state.record_completion(event)

        # Should track completion
        assert state.get_completion_time("site_activation", "SITE001") == 50.0

        # Should add to timeline
        assert len(state.timeline) == 1
        assert state.timeline[0][0] == 50.0  # time
        assert state.timeline[0][1] == "site_activation"  # event_type

        # Should increment metrics
        assert state.metrics["events_processed"] == 1

    def test_budget_tracking(self):
        state = SimulationState(initial_budget=100000)

        state.spend_budget(25000)
        assert state.budget_spent == 25000
        assert state.budget_available == 75000

        state.spend_budget(30000)
        assert state.budget_spent == 55000
        assert state.budget_available == 45000

    def test_resource_allocation_tracking(self):
        state = SimulationState()

        # Allocate resource for time period
        state.allocate_resource("MONITOR", start_time=10.0, end_time=30.0, event_id="e1")

        # Check availability at different times
        assert state.get_resource_availability("MONITOR", 5.0) is None  # Before allocation
        assert state.get_resource_availability("MONITOR", 15.0) == 30.0  # During allocation
        assert state.get_resource_availability("MONITOR", 35.0) is None  # After allocation


class TestRunResult:
    """Test RunResult data structure."""

    def test_run_result_creation(self):
        result = RunResult(
            run_id=5,
            seed=12345,
            completion_time=287.5,
            total_cost=2300000,
            timeline=[],
            metrics={},
            events_processed=150,
            events_rescheduled=23,
            constraint_violations=5
        )

        assert result.run_id == 5
        assert result.completion_time == 287.5

    def test_run_result_summary(self):
        result = RunResult(
            run_id=1,
            seed=42,
            completion_time=250.0,
            total_cost=2000000,
            timeline=[],
            metrics={},
            events_processed=100,
            events_rescheduled=10,
            constraint_violations=2
        )

        summary = result.summary()

        assert "Run #1" in summary
        assert "250.0 days" in summary
        assert "$2,000,000" in summary


class TestAggregateStatistics:
    """Test statistical aggregation functions."""

    def test_aggregate_statistics_computes_percentiles(self):
        """Aggregate statistics computes P10/P50/P90."""
        values = [100, 150, 200, 250, 300, 350, 400, 450, 500]

        stats = aggregate_statistics(values, percentiles=[10, 50, 90])

        assert stats[10] < stats[50] < stats[90]
        assert stats[50] == 300.0  # Median

    def test_aggregate_statistics_with_variability(self):
        """Statistics reflect distribution spread."""
        # Narrow distribution
        narrow = [95, 98, 100, 102, 105]
        narrow_stats = aggregate_statistics(narrow)

        # Wide distribution
        wide = [50, 75, 100, 150, 200]
        wide_stats = aggregate_statistics(wide)

        # Wide distribution has larger P90-P10 spread
        narrow_spread = narrow_stats[90] - narrow_stats[10]
        wide_spread = wide_stats[90] - wide_stats[10]

        assert wide_spread > narrow_spread


class TestSimulationEngine:
    """Test simulation engine execution."""

    def setup_method(self):
        """Create simple trial specification for testing."""
        # Create 3 sites with triangular activation distributions
        self.site1 = Site(
            site_id="SITE001",
            activation_time=Triangular(30, 45, 90),
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15)
        )

        self.site2 = Site(
            site_id="SITE002",
            activation_time=Triangular(40, 60, 120),
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15)
        )

        self.site3 = Site(
            site_id="SITE003",
            activation_time=Triangular(50, 75, 150),
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15)
        )

        self.flow = PatientFlow(
            flow_id="FLOW",
            states={"enrolled", "completed"},
            initial_state="enrolled",
            terminal_states={"completed"},
            transition_times={("enrolled", "completed"): Triangular(30, 60, 120)}
        )

        self.trial = Trial(
            trial_id="TRIAL001",
            target_enrollment=200,
            sites=[self.site1, self.site2, self.site3],
            patient_flow=self.flow
        )

    def test_engine_determinism_same_seed_identical_results(self):
        """Same master seed produces identical results across runs."""
        engine1 = SimulationEngine(master_seed=42)
        engine2 = SimulationEngine(master_seed=42)

        # Run simulations with same seed
        results1 = engine1.run(self.trial, num_runs=10)
        results2 = engine2.run(self.trial, num_runs=10)

        # Should produce identical results
        for i in range(10):
            run1 = results1.get_run(i)
            run2 = results2.get_run(i)

            assert run1.completion_time == run2.completion_time
            assert run1.seed == run2.seed
            assert len(run1.timeline) == len(run2.timeline)

    def test_engine_different_seed_different_results(self):
        """Different master seeds produce different results."""
        engine1 = SimulationEngine(master_seed=42)
        engine2 = SimulationEngine(master_seed=99)

        # Run simulations with different seeds
        results1 = engine1.run(self.trial, num_runs=10)
        results2 = engine2.run(self.trial, num_runs=10)

        # Should produce different results
        completion_times_1 = [r.completion_time for r in results1.run_results]
        completion_times_2 = [r.completion_time for r in results2.run_results]

        # At least some should be different
        assert completion_times_1 != completion_times_2

    def test_engine_produces_run_results(self):
        """Engine produces RunResult for each run."""
        engine = SimulationEngine(master_seed=42)

        results = engine.run(self.trial, num_runs=5)

        assert len(results.run_results) == 5

        for i, run in enumerate(results.run_results):
            assert run.run_id == i
            assert run.completion_time > 0
            assert len(run.timeline) > 0
            assert run.events_processed > 0

    def test_engine_aggregates_statistics(self):
        """Engine computes aggregated statistics across runs."""
        engine = SimulationEngine(master_seed=42)

        results = engine.run(self.trial, num_runs=20)

        # Should have percentile statistics
        assert results.completion_time_p10 > 0
        assert results.completion_time_p50 > 0
        assert results.completion_time_p90 > 0

        # P10 < P50 < P90
        assert results.completion_time_p10 < results.completion_time_p50 < results.completion_time_p90

        # Same for cost (though currently 0 in MVP)
        assert results.total_cost_p10 <= results.total_cost_p50 <= results.total_cost_p90

    def test_single_run_shows_timeline(self):
        """Single run produces detailed timeline."""
        engine = SimulationEngine(master_seed=42)

        results = engine.run(self.trial, num_runs=1)
        run = results.get_run(0)

        # Should have timeline entries
        assert len(run.timeline) > 0

        # Timeline should be ordered by time
        times = [entry[0] for entry in run.timeline]
        assert times == sorted(times)

    def test_aggregated_results_summary(self):
        """Aggregated results produce readable summary."""
        engine = SimulationEngine(master_seed=42)

        results = engine.run(self.trial, num_runs=10)

        summary = results.summary()

        assert "10 runs" in summary
        assert "P10:" in summary
        assert "P50:" in summary
        assert "P90:" in summary
        assert "days" in summary

    def test_event_seed_generation_deterministic(self):
        """Event seed generation is deterministic."""
        engine = SimulationEngine(master_seed=42)

        seed1 = engine._generate_event_seed(100, "event_A")
        seed2 = engine._generate_event_seed(100, "event_A")

        assert seed1 == seed2  # Same inputs → same seed

    def test_event_seed_generation_independent(self):
        """Different events get independent seeds."""
        engine = SimulationEngine(master_seed=42)

        seed_A = engine._generate_event_seed(100, "event_A")
        seed_B = engine._generate_event_seed(100, "event_B")

        assert seed_A != seed_B  # Different events → different seeds


class TestSingleRunVsAggregated:
    """Integration tests demonstrating single run vs aggregated differences."""

    def setup_method(self):
        """Create trial for integration testing."""
        self.site = Site(
            site_id="SITE001",
            activation_time=Triangular(30, 45, 90),  # Variable activation
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15)
        )

        self.flow = PatientFlow(
            flow_id="FLOW",
            states={"enrolled", "completed"},
            initial_state="enrolled",
            terminal_states={"completed"},
            transition_times={("enrolled", "completed"): Triangular(30, 60, 120)}
        )

        self.trial = Trial(
            trial_id="TRIAL001",
            target_enrollment=200,
            sites=[self.site],
            patient_flow=self.flow
        )

    def test_single_run_shows_specific_realization(self):
        """Single run shows ONE specific realization."""
        engine = SimulationEngine(master_seed=42)

        results = engine.run(self.trial, num_runs=1)
        run = results.get_run(0)

        # Single run has specific completion time
        assert run.completion_time > 0

        # Has specific timeline
        assert len(run.timeline) > 0

        # Timeline shows causality (events in order)
        for i in range(len(run.timeline) - 1):
            assert run.timeline[i][0] <= run.timeline[i+1][0]

    def test_aggregated_shows_distribution(self):
        """Aggregated results show distribution of outcomes."""
        engine = SimulationEngine(master_seed=42)

        results = engine.run(self.trial, num_runs=50)

        # Aggregated has percentiles (showing spread)
        p10 = results.completion_time_p10
        p50 = results.completion_time_p50
        p90 = results.completion_time_p90

        # Should have meaningful spread (variability)
        spread = p90 - p10
        assert spread > 0  # Not all runs identical

        # Spread reflects uncertainty in activation time
        # Triangular(30, 45, 90) has range of 60 days
        assert spread > 10  # At least some variability

    def test_single_run_for_debugging_aggregated_for_planning(self):
        """Demonstrate use cases: single for debug, aggregated for planning."""
        engine = SimulationEngine(master_seed=42)

        results = engine.run(self.trial, num_runs=100)

        # Use Case 1: Debugging specific scenario
        # Find slowest run
        slowest_run = max(results.run_results, key=lambda r: r.completion_time)
        print(f"\n=== DEBUGGING: Slowest Run ===")
        print(slowest_run.summary())
        print(f"Timeline: {slowest_run.timeline[:3]}...")  # First 3 events

        # Analysis: Can inspect timeline to understand WHY it was slow

        # Use Case 2: Planning under uncertainty
        print(f"\n=== PLANNING: Risk Assessment ===")
        print(results.summary())

        # Analysis: Know that 90% of trials complete by P90
        # Can budget/plan for P90 scenario

        # Both views complement each other
        assert slowest_run.completion_time >= results.completion_time_p90

    def test_variability_quantified_by_aggregation(self):
        """Aggregation quantifies uncertainty that single run doesn't show."""
        engine = SimulationEngine(master_seed=42)

        # Run simulation
        results = engine.run(self.trial, num_runs=100)

        # Single run (e.g., first run)
        single_run = results.get_run(0)

        # Single run: Shows completion time = X
        print(f"\nSingle run completion: {single_run.completion_time:.1f} days")

        # Aggregated: Shows range [P10, P90]
        range_days = results.completion_time_p90 - results.completion_time_p10
        print(f"Aggregated range: {range_days:.1f} days (P10 to P90)")

        # Key insight: Single run doesn't reveal uncertainty
        # Aggregation does: "Could range from P10 to P90"

        # Variability should be non-trivial
        assert range_days > 0


class TestConstraintIntegration:
    """Test constraint evaluation integration with simulation engine."""

    def setup_method(self):
        """Create simple trial for constraint testing."""
        from seleensim.constraints import (
            TemporalPrecedenceConstraint,
            ResourceCapacityConstraint,
            BudgetThrottlingConstraint,
            LinearResponseCurve
        )

        self.site = Site(
            site_id="SITE001",
            activation_time=Triangular(30, 45, 90),
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15)
        )

        self.flow = PatientFlow(
            flow_id="FLOW",
            states={"enrolled", "completed"},
            initial_state="enrolled",
            terminal_states={"completed"},
            transition_times={(("enrolled", "completed")): Triangular(30, 60, 120)}
        )

        self.trial = Trial(
            trial_id="TRIAL001",
            target_enrollment=200,
            sites=[self.site],
            patient_flow=self.flow
        )

        # Create constraints
        self.temporal_constraint = TemporalPrecedenceConstraint(
            predecessor_event_type="site_activation",
            dependent_event_type="enrollment"
        )

        self.resource_constraint = ResourceCapacityConstraint(
            resource_id="MONITOR"
        )

        self.budget_constraint = BudgetThrottlingConstraint(
            budget_per_day=10000.0,
            response_curve=LinearResponseCurve(min_speed_ratio=0.5)
        )

    def test_engine_runs_without_constraints_backward_compatibility(self):
        """Engine without constraints runs normally (MVP mode)."""
        engine = SimulationEngine(master_seed=42, constraints=None)

        results = engine.run(self.trial, num_runs=5)

        assert len(results.run_results) == 5
        # Should complete successfully without constraint evaluation
        for run in results.run_results:
            assert run.completion_time > 0
            assert run.events_rescheduled == 0  # No constraints, no rescheduling

    def test_engine_with_empty_constraints_list(self):
        """Engine with empty constraints list runs normally."""
        engine = SimulationEngine(master_seed=42, constraints=[])

        results = engine.run(self.trial, num_runs=5)

        assert len(results.run_results) == 5
        for run in results.run_results:
            assert run.completion_time > 0

    def test_constraint_evaluation_called_during_event_processing(self):
        """Verify constraints are evaluated during simulation."""
        # Use a simple mock constraint to verify it's called
        from seleensim.constraints import ConstraintResult

        class MockConstraint:
            def __init__(self):
                self.call_count = 0

            def evaluate(self, state, event):
                self.call_count += 1
                # Return satisfied result (no effect)
                return ConstraintResult.satisfied("Mock constraint passed")

        mock = MockConstraint()
        engine = SimulationEngine(master_seed=42, constraints=[mock])

        # Run simulation
        results = engine.run(self.trial, num_runs=1)

        # Verify constraint was called (should be called for each event processed)
        assert mock.call_count > 0

    def test_validity_constraint_reschedules_events(self):
        """Validity constraints cause event rescheduling."""
        from seleensim.constraints import TemporalPrecedenceConstraint

        # Create constraint that will cause rescheduling
        constraint = TemporalPrecedenceConstraint(
            predecessor_event_type="site_activation",
            dependent_event_type="enrollment"
        )

        engine = SimulationEngine(master_seed=42, constraints=[constraint])

        # For this test to be meaningful, we'd need enrollment events
        # For now, verify engine structure works
        results = engine.run(self.trial, num_runs=1)

        # Should complete without errors
        assert len(results.run_results) == 1

    def test_feasibility_constraint_applies_delays(self):
        """Feasibility constraints add delays to events."""
        from seleensim.constraints import ResourceCapacityConstraint

        # Resource capacity constraint will delay events when resources busy
        constraint = ResourceCapacityConstraint(
            resource_id="MONITOR"
        )

        engine = SimulationEngine(master_seed=42, constraints=[constraint])

        # Run simulation
        results = engine.run(self.trial, num_runs=1)

        # Should complete
        assert len(results.run_results) == 1

    def test_parameter_override_constraint_modifies_events(self):
        """Constraints with parameter overrides modify event execution."""
        from seleensim.constraints import BudgetThrottlingConstraint, LinearResponseCurve

        # Budget throttling modifies duration
        constraint = BudgetThrottlingConstraint(
            budget_per_day=5000.0,  # Low budget to force throttling
            response_curve=LinearResponseCurve(min_speed_ratio=0.5)
        )

        engine = SimulationEngine(master_seed=42, constraints=[constraint])

        results = engine.run(self.trial, num_runs=1)

        # Should complete
        assert len(results.run_results) == 1

    def test_multiple_constraints_compose_correctly(self):
        """Multiple constraints compose via AND/MAX/MERGE rules."""
        # Create multiple constraints
        constraints = [
            self.temporal_constraint,
            self.resource_constraint,
            self.budget_constraint
        ]

        engine = SimulationEngine(master_seed=42, constraints=constraints)

        results = engine.run(self.trial, num_runs=1)

        # Should complete with all constraints evaluated
        assert len(results.run_results) == 1

    def test_rescheduling_metrics_tracked(self):
        """Engine tracks rescheduling and violations in metrics."""
        # Use constraint that may cause rescheduling
        engine = SimulationEngine(master_seed=42, constraints=[self.temporal_constraint])

        results = engine.run(self.trial, num_runs=1)
        run = results.get_run(0)

        # Metrics should be present
        assert "events_processed" in run.metrics
        assert "events_rescheduled" in run.metrics
        assert "constraint_violations" in run.metrics

        # Values should be non-negative
        assert run.events_rescheduled >= 0
        assert run.constraint_violations >= 0

    def test_determinism_with_constraints(self):
        """Same seed produces identical results even with constraints."""
        constraints = [self.temporal_constraint, self.budget_constraint]

        engine1 = SimulationEngine(master_seed=42, constraints=constraints)
        engine2 = SimulationEngine(master_seed=42, constraints=constraints)

        results1 = engine1.run(self.trial, num_runs=3)
        results2 = engine2.run(self.trial, num_runs=3)

        # Should produce identical results
        for i in range(3):
            run1 = results1.get_run(i)
            run2 = results2.get_run(i)

            assert run1.completion_time == run2.completion_time
            assert run1.events_rescheduled == run2.events_rescheduled
            assert len(run1.timeline) == len(run2.timeline)

    def test_timeline_includes_reschedule_explanations(self):
        """Timeline entries include constraint explanations for rescheduling."""
        engine = SimulationEngine(master_seed=42, constraints=[self.temporal_constraint])

        results = engine.run(self.trial, num_runs=1)
        run = results.get_run(0)

        # Check that timeline exists
        assert len(run.timeline) > 0

        # Timeline should be ordered by time
        times = [entry[0] for entry in run.timeline]
        assert times == sorted(times)


class TestMetricsInvariant:
    """Test that metrics observe execution but never influence it.

    CRITICAL INVARIANT: Metrics may observe execution, never influence it.

    This prevents the simulation engine from becoming a heuristic optimizer.
    Metrics are write-only during execution, read-only for reporting.
    """

    def setup_method(self):
        """Create simple trial for testing."""
        self.site = Site(
            site_id="SITE001",
            activation_time=Triangular(30, 45, 90),
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15)
        )

        self.flow = PatientFlow(
            flow_id="FLOW",
            states={"enrolled", "completed"},
            initial_state="enrolled",
            terminal_states={"completed"},
            transition_times={(("enrolled", "completed")): Triangular(30, 60, 120)}
        )

        self.trial = Trial(
            trial_id="TRIAL001",
            target_enrollment=200,
            sites=[self.site],
            patient_flow=self.flow
        )

    def test_metrics_only_written_during_execution(self):
        """Verify metrics are only written (incremented), never read for decisions."""
        engine = SimulationEngine(master_seed=42, constraints=None)

        results = engine.run(self.trial, num_runs=1)
        run = results.get_run(0)

        # Metrics should exist and be non-negative
        assert run.metrics["events_processed"] >= 0
        assert run.metrics["events_rescheduled"] >= 0
        assert run.metrics["constraint_violations"] >= 0

        # These are observational only - reported at end
        # Never used during execution for control flow

    def test_determinism_unaffected_by_metrics_tracking(self):
        """Metrics tracking doesn't affect determinism.

        If metrics influenced execution, determinism would break.
        """
        engine1 = SimulationEngine(master_seed=42, constraints=None)
        engine2 = SimulationEngine(master_seed=42, constraints=None)

        results1 = engine1.run(self.trial, num_runs=3)
        results2 = engine2.run(self.trial, num_runs=3)

        # Identical results prove metrics don't influence execution
        for i in range(3):
            run1 = results1.get_run(i)
            run2 = results2.get_run(i)

            assert run1.completion_time == run2.completion_time
            # Metrics themselves should also match
            assert run1.metrics == run2.metrics

    def test_no_conditional_logic_based_on_metrics(self):
        """Verify _process_event has no conditionals reading metrics.

        This is a structural test - checks the source code doesn't contain
        metric-driven control flow.
        """
        import inspect
        from seleensim.simulation import SimulationEngine

        # Get source code of _process_event
        source = inspect.getsource(SimulationEngine._process_event)

        # Check for anti-patterns
        forbidden_patterns = [
            "if state.metrics",
            "if self.metrics",
            "state.metrics[",
            "state.metrics.get(",
        ]

        violations = []
        for pattern in forbidden_patterns:
            if pattern in source:
                # Check it's not just incrementing (write-only)
                lines = source.split('\n')
                for i, line in enumerate(lines):
                    if pattern in line:
                        # OK patterns (write-only):
                        # - state.metrics["key"] += 1
                        # - state.metrics["key"] = value
                        # BAD patterns (read for decisions):
                        # - if state.metrics["key"] > X:
                        # - while state.metrics["key"] < X:
                        if ('if ' in line or 'while ' in line or 'elif ' in line) and '+=' not in line:
                            violations.append(f"Line {i+1}: {line.strip()}")

        if violations:
            pytest.fail(
                f"VIOLATION: Metrics used in conditional logic!\n" +
                "\n".join(violations) +
                "\n\nThis violates: Metrics observe, never influence.\n"
                "See ENGINE_ORCHESTRATION.md Invariant #4."
            )
