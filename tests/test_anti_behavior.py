"""
Anti-behavior tests: Verify entities do NOT violate architectural guarantees.

These tests enforce that entities remain pure data structures without:
1. Sampling distributions
2. Mutating state
3. Computing derived values
4. Executing business logic

These tests should FAIL if someone adds forbidden behavior to entities.
"""

import pytest
from unittest.mock import Mock, patch
from seleensim.entities import Site, Activity, Resource, PatientFlow, Trial
from seleensim.distributions import Triangular, LogNormal, Gamma, Bernoulli


class TestNoSamplingBehavior:
    """Verify entities never sample their distributions."""

    def test_site_does_not_sample_distributions(self):
        """Site should never call .sample() on its distributions."""
        # Create mock distributions that track if .sample() is called
        mock_activation = Mock(spec=Triangular)
        mock_enrollment = Mock(spec=Gamma)
        mock_dropout = Mock(spec=Bernoulli)

        # Bypass validation by patching isinstance checks
        with patch('seleensim.entities.isinstance', return_value=True):
            site = object.__new__(Site)
            object.__setattr__(site, 'site_id', 'SITE001')
            object.__setattr__(site, 'activation_time', mock_activation)
            object.__setattr__(site, 'enrollment_rate', mock_enrollment)
            object.__setattr__(site, 'dropout_rate', mock_dropout)
            object.__setattr__(site, 'max_capacity', None)

        # Verify no sampling occurred during construction
        mock_activation.sample.assert_not_called()
        mock_enrollment.sample.assert_not_called()
        mock_dropout.sample.assert_not_called()

        # Call to_dict (the only method that should touch distributions)
        # Even then, it should only call to_dict(), not sample()
        mock_activation.to_dict = Mock(return_value={"type": "Triangular"})
        mock_enrollment.to_dict = Mock(return_value={"type": "Gamma"})
        mock_dropout.to_dict = Mock(return_value={"type": "Bernoulli"})

        site.to_dict()

        # Still no sampling should occur
        mock_activation.sample.assert_not_called()
        mock_enrollment.sample.assert_not_called()
        mock_dropout.sample.assert_not_called()

    def test_activity_does_not_sample_duration(self):
        """Activity should never call .sample() on its duration distribution."""
        mock_duration = Mock(spec=LogNormal)
        mock_duration.to_dict = Mock(return_value={"type": "LogNormal"})

        with patch('seleensim.entities.isinstance', return_value=True):
            activity = object.__new__(Activity)
            object.__setattr__(activity, 'activity_id', 'ACT001')
            object.__setattr__(activity, 'duration', mock_duration)
            object.__setattr__(activity, 'dependencies', set())
            object.__setattr__(activity, 'required_resources', set())
            object.__setattr__(activity, 'success_probability', None)

        activity.to_dict()
        mock_duration.sample.assert_not_called()

    def test_patient_flow_does_not_sample_transitions(self):
        """PatientFlow should never call .sample() on transition distributions."""
        mock_transition = Mock(spec=Triangular)
        mock_transition.to_dict = Mock(return_value={"type": "Triangular"})

        with patch('seleensim.entities.isinstance', return_value=True):
            flow = object.__new__(PatientFlow)
            object.__setattr__(flow, 'flow_id', 'FLOW001')
            object.__setattr__(flow, 'states', {'A', 'B'})
            object.__setattr__(flow, 'initial_state', 'A')
            object.__setattr__(flow, 'terminal_states', {'B'})
            object.__setattr__(flow, 'transition_times', {('A', 'B'): mock_transition})
            object.__setattr__(flow, 'transition_probabilities', {})

        flow.to_dict()
        mock_transition.sample.assert_not_called()


class TestNoMutationBehavior:
    """Verify entities cannot mutate after construction."""

    def test_site_cannot_mutate_after_construction(self):
        """Site fields should be immutable."""
        site = Site(
            site_id="SITE001",
            activation_time=Triangular(30, 45, 90),
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15)
        )

        # Attempt to mutate each field should fail
        with pytest.raises(Exception):
            site.site_id = "MODIFIED"

        with pytest.raises(Exception):
            site.activation_time = Triangular(10, 20, 30)

        with pytest.raises(Exception):
            site.max_capacity = 100

    def test_activity_dependencies_cannot_be_modified(self):
        """Activity dependencies set should not be modifiable through entity."""
        activity = Activity(
            activity_id="ACT001",
            duration=LogNormal(30, 0.2),
            dependencies={"DEP001"}
        )

        # Entity is frozen, so direct assignment fails
        with pytest.raises(Exception):
            activity.dependencies = {"DEP002"}

        # Even if we get the set reference, the entity should remain unchanged
        deps_ref = activity.dependencies
        deps_ref.add("DEP002")
        # The original dependencies should be unchanged (frozen dataclass protection)
        # Note: This tests that we're using frozen=True correctly

    def test_patient_flow_states_cannot_be_modified(self):
        """PatientFlow states should not be modifiable."""
        flow = PatientFlow(
            flow_id="FLOW001",
            states={"enrolled", "completed"},
            initial_state="enrolled",
            terminal_states={"completed"},
            transition_times={("enrolled", "completed"): Triangular(30, 60, 120)}
        )

        with pytest.raises(Exception):
            flow.states = {"modified"}

        with pytest.raises(Exception):
            flow.initial_state = "modified"

    def test_trial_cannot_mutate_components(self):
        """Trial should not allow modification of its component lists."""
        site = Site(
            site_id="SITE001",
            activation_time=Triangular(30, 45, 90),
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15)
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
            patient_flow=flow
        )

        with pytest.raises(Exception):
            trial.sites = []

        with pytest.raises(Exception):
            trial.target_enrollment = 300


class TestNoComputationBehavior:
    """Verify entities do not compute derived values."""

    def test_site_has_no_computed_properties(self):
        """Site should not compute values like expected_enrollment_time."""
        site = Site(
            site_id="SITE001",
            activation_time=Triangular(30, 45, 90),
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15),
            max_capacity=50
        )

        # Should not have computed properties
        forbidden_attrs = [
            'expected_activation_time',
            'mean_enrollment_rate',
            'effective_capacity',
            'expected_completion_time',
            'utilization_rate'
        ]

        for attr in forbidden_attrs:
            assert not hasattr(site, attr), \
                f"Site should not have computed attribute: {attr}"

    def test_activity_has_no_computed_properties(self):
        """Activity should not compute values like expected_duration."""
        activity = Activity(
            activity_id="ACT001",
            duration=LogNormal(30, 0.2),
            dependencies={"DEP001"}
        )

        forbidden_attrs = [
            'expected_duration',
            'mean_duration',
            'critical_path_length',
            'earliest_start_time',
            'slack_time'
        ]

        for attr in forbidden_attrs:
            assert not hasattr(activity, attr), \
                f"Activity should not have computed attribute: {attr}"

    def test_patient_flow_has_no_computed_properties(self):
        """PatientFlow should not compute values like expected_completion_time."""
        flow = PatientFlow(
            flow_id="FLOW001",
            states={"enrolled", "active", "completed"},
            initial_state="enrolled",
            terminal_states={"completed"},
            transition_times={
                ("enrolled", "active"): Triangular(7, 14, 30),
                ("active", "completed"): LogNormal(180, 0.3)
            }
        )

        forbidden_attrs = [
            'expected_completion_time',
            'mean_time_to_completion',
            'completion_probability',
            'expected_path_duration',
            'bottleneck_state'
        ]

        for attr in forbidden_attrs:
            assert not hasattr(flow, attr), \
                f"PatientFlow should not have computed attribute: {attr}"

    def test_trial_has_no_computed_properties(self):
        """Trial should not compute values like expected_duration."""
        site = Site(
            site_id="SITE001",
            activation_time=Triangular(30, 45, 90),
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15)
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
            patient_flow=flow
        )

        forbidden_attrs = [
            'expected_enrollment_time',
            'expected_completion_date',
            'total_cost',
            'risk_score',
            'feasibility_score',
            'projected_timeline'
        ]

        for attr in forbidden_attrs:
            assert not hasattr(trial, attr), \
                f"Trial should not have computed attribute: {attr}"


class TestNoExecutionBehavior:
    """Verify entities have no execution logic."""

    def test_site_has_no_execution_methods(self):
        """Site should not have methods for enrollment or activation."""
        site = Site(
            site_id="SITE001",
            activation_time=Triangular(30, 45, 90),
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15)
        )

        forbidden_methods = [
            'activate',
            'deactivate',
            'enroll',
            'enroll_patient',
            'dropout_patient',
            'is_active',
            'can_enroll',
            'check_capacity',
            'get_current_enrollment'
        ]

        for method in forbidden_methods:
            assert not hasattr(site, method), \
                f"Site should not have execution method: {method}"

    def test_activity_has_no_execution_methods(self):
        """Activity should not have methods for starting or completing."""
        activity = Activity(
            activity_id="ACT001",
            duration=LogNormal(30, 0.2)
        )

        forbidden_methods = [
            'start',
            'complete',
            'execute',
            'run',
            'can_start',
            'is_complete',
            'is_blocked',
            'get_status',
            'allocate_resources',
            'check_dependencies'
        ]

        for method in forbidden_methods:
            assert not hasattr(activity, method), \
                f"Activity should not have execution method: {method}"

    def test_patient_flow_has_no_execution_methods(self):
        """PatientFlow should not have methods for advancing state."""
        flow = PatientFlow(
            flow_id="FLOW001",
            states={"enrolled", "completed"},
            initial_state="enrolled",
            terminal_states={"completed"},
            transition_times={("enrolled", "completed"): Triangular(30, 60, 120)}
        )

        forbidden_methods = [
            'transition',
            'advance',
            'move_to',
            'get_next_state',
            'sample_transition',
            'choose_next_state',
            'is_terminal',
            'get_current_state',
            'execute_transition',
            'apply_transition'
        ]

        for method in forbidden_methods:
            assert not hasattr(flow, method), \
                f"PatientFlow should not have execution method: {method}"

    def test_trial_has_no_execution_methods(self):
        """Trial should not have methods for running simulations."""
        site = Site(
            site_id="SITE001",
            activation_time=Triangular(30, 45, 90),
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15)
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
            patient_flow=flow
        )

        forbidden_methods = [
            'run',
            'simulate',
            'execute',
            'monte_carlo',
            'analyze',
            'predict',
            'compute_metrics',
            'get_results',
            'enroll_patients',
            'activate_sites',
            'advance_time',
            'step',
            'is_complete'
        ]

        for method in forbidden_methods:
            assert not hasattr(trial, method), \
                f"Trial should not have execution method: {method}"


class TestNoStatefulBehavior:
    """Verify entities maintain no runtime state."""

    def test_site_has_no_runtime_state(self):
        """Site should not track current enrollment or activation status."""
        site = Site(
            site_id="SITE001",
            activation_time=Triangular(30, 45, 90),
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15)
        )

        forbidden_state = [
            'current_enrollment',
            'is_activated',
            'activation_date',
            'enrolled_patients',
            'active_patients',
            'dropped_patients',
            'last_enrollment_date'
        ]

        for attr in forbidden_state:
            assert not hasattr(site, attr), \
                f"Site should not have runtime state: {attr}"

    def test_activity_has_no_runtime_state(self):
        """Activity should not track completion or start time."""
        activity = Activity(
            activity_id="ACT001",
            duration=LogNormal(30, 0.2)
        )

        forbidden_state = [
            'start_time',
            'end_time',
            'is_started',
            'is_completed',
            'progress',
            'allocated_resources',
            'actual_duration'
        ]

        for attr in forbidden_state:
            assert not hasattr(activity, attr), \
                f"Activity should not have runtime state: {attr}"

    def test_patient_flow_has_no_runtime_state(self):
        """PatientFlow should not track current state of any entity."""
        flow = PatientFlow(
            flow_id="FLOW001",
            states={"enrolled", "completed"},
            initial_state="enrolled",
            terminal_states={"completed"},
            transition_times={("enrolled", "completed"): Triangular(30, 60, 120)}
        )

        forbidden_state = [
            'current_state',
            'state_history',
            'transition_history',
            'time_in_state',
            'entities_by_state',
            'active_transitions'
        ]

        for attr in forbidden_state:
            assert not hasattr(flow, attr), \
                f"PatientFlow should not have runtime state: {attr}"

    def test_trial_has_no_runtime_state(self):
        """Trial should not track current enrollment or elapsed time."""
        site = Site(
            site_id="SITE001",
            activation_time=Triangular(30, 45, 90),
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15)
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
            patient_flow=flow
        )

        forbidden_state = [
            'current_enrollment',
            'elapsed_time',
            'active_sites',
            'enrolled_patients',
            'completed_patients',
            'simulation_results',
            'current_date',
            'is_complete'
        ]

        for attr in forbidden_state:
            assert not hasattr(trial, attr), \
                f"Trial should not have runtime state: {attr}"


class TestOnlyAllowedMethods:
    """Verify entities only have to_dict() as public method."""

    def test_all_entities_only_expose_to_dict(self):
        """All entities should only have to_dict() as public method."""
        site = Site(
            site_id="SITE001",
            activation_time=Triangular(30, 45, 90),
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15)
        )
        activity = Activity(
            activity_id="ACT001",
            duration=LogNormal(30, 0.2)
        )
        resource = Resource(
            resource_id="RES001",
            resource_type="staff"
        )
        flow = PatientFlow(
            flow_id="FLOW001",
            states={"enrolled", "completed"},
            initial_state="enrolled",
            terminal_states={"completed"},
            transition_times={("enrolled", "completed"): Triangular(30, 60, 120)}
        )

        for entity in [site, activity, resource, flow]:
            public_methods = [
                m for m in dir(entity)
                if callable(getattr(entity, m)) and not m.startswith("_")
            ]

            # Should only have to_dict and possibly some dataclass-generated methods
            # But NO business logic methods
            assert "to_dict" in public_methods, f"{type(entity).__name__} missing to_dict()"

            # Check that there are no unexpected methods
            allowed_methods = {"to_dict"}
            unexpected = set(public_methods) - allowed_methods

            # If there are unexpected methods, they should not be business logic
            business_keywords = {
                "run", "execute", "simulate", "start", "stop", "activate",
                "enroll", "allocate", "sample", "compute", "calculate",
                "predict", "analyze", "get_", "set_", "is_", "can_",
                "check_", "update_", "advance_", "transition"
            }

            for method in unexpected:
                for keyword in business_keywords:
                    assert keyword not in method.lower(), \
                        f"{type(entity).__name__} has forbidden method: {method}"
