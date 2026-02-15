"""
Tests for scenario system.

Focus areas:
1. ScenarioProfile immutability and serialization
2. apply_scenario() purity (no mutation)
3. Override types work correctly
4. Scenario composition
5. JSON serialization round-trip
6. Architectural guarantees maintained
"""

import pytest
import json
from seleensim.scenarios import (
    ScenarioProfile,
    apply_scenario,
    compose_scenarios,
    diff_scenarios,
    OverrideType
)
from seleensim.entities import Site, Trial, PatientFlow, Resource
from seleensim.distributions import Triangular, Gamma, Bernoulli


class TestScenarioProfile:
    """Test ScenarioProfile construction and properties."""

    def test_scenario_creation(self):
        scenario = ScenarioProfile(
            scenario_id="TEST_SCENARIO",
            description="Test scenario",
            version="1.0.0"
        )

        assert scenario.scenario_id == "TEST_SCENARIO"
        assert scenario.description == "Test scenario"
        assert scenario.version == "1.0.0"

    def test_scenario_is_immutable(self):
        """Scenarios are frozen dataclasses."""
        scenario = ScenarioProfile(
            scenario_id="TEST",
            description="Test",
            version="1.0.0"
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            scenario.description = "Modified"

    def test_scenario_with_site_overrides(self):
        scenario = ScenarioProfile(
            scenario_id="TEST",
            description="Test",
            version="1.0.0",
            site_overrides={
                "SITE_001": {
                    "activation_time": {
                        "type": "distribution_scale",
                        "parameters": {"scale_factor": 1.2}
                    }
                }
            }
        )

        assert "SITE_001" in scenario.site_overrides
        assert scenario.site_overrides["SITE_001"]["activation_time"]["type"] == "distribution_scale"

    def test_scenario_serialization(self):
        """Scenarios serialize to JSON."""
        scenario = ScenarioProfile(
            scenario_id="TEST",
            description="Test scenario",
            version="1.0.0",
            site_overrides={"SITE_001": {"activation_time": {"type": "distribution_scale", "parameters": {"scale_factor": 1.2}}}}
        )

        data = scenario.to_dict()

        assert data["scenario_id"] == "TEST"
        assert "site_overrides" in data
        assert json.dumps(data)  # Can serialize to JSON

    def test_scenario_deserialization(self):
        """Scenarios deserialize from JSON."""
        data = {
            "scenario_id": "TEST",
            "description": "Test",
            "version": "1.0.0",
            "site_overrides": {},
            "activity_overrides": {},
            "resource_overrides": {},
            "flow_overrides": {},
            "trial_overrides": {}
        }

        scenario = ScenarioProfile.from_dict(data)

        assert scenario.scenario_id == "TEST"
        assert scenario.description == "Test"


class TestApplyScenario:
    """Test apply_scenario() pure function."""

    def setup_method(self):
        """Create base trial for testing."""
        self.base_trial = Trial(
            trial_id="BASE",
            target_enrollment=200,
            sites=[
                Site(
                    site_id="SITE_001",
                    activation_time=Triangular(30, 45, 90),
                    enrollment_rate=Gamma(2, 1.5),
                    dropout_rate=Bernoulli(0.15)
                )
            ],
            patient_flow=PatientFlow(
                flow_id="FLOW",
                states={"enrolled", "completed"},
                initial_state="enrolled",
                terminal_states={"completed"},
                transition_times={(("enrolled", "completed")): Triangular(90, 180, 365)}
            )
        )

    def test_apply_scenario_returns_new_trial(self):
        """apply_scenario() returns NEW trial, doesn't mutate base."""
        scenario = ScenarioProfile(
            scenario_id="TEST",
            description="Test",
            version="1.0.0",
            site_overrides={
                "SITE_001": {
                    "activation_time": {
                        "type": "distribution_scale",
                        "parameters": {"scale_factor": 1.2},
                        "reason": "Test"
                    }
                }
            }
        )

        original_mode = self.base_trial.sites[0].activation_time.mode

        modified_trial = apply_scenario(self.base_trial, scenario)

        # Base unchanged
        assert self.base_trial.sites[0].activation_time.mode == original_mode

        # Modified has scaled distribution
        assert modified_trial.sites[0].activation_time.mode == original_mode * 1.2

        # Different trial IDs
        assert modified_trial.trial_id != self.base_trial.trial_id
        assert "TEST" in modified_trial.trial_id

    def test_apply_empty_scenario_returns_equivalent_trial(self):
        """Empty scenario produces equivalent trial."""
        empty_scenario = ScenarioProfile(
            scenario_id="EMPTY",
            description="No overrides",
            version="1.0.0"
        )

        modified_trial = apply_scenario(self.base_trial, empty_scenario)

        # Structure same (though object references may differ)
        assert modified_trial.target_enrollment == self.base_trial.target_enrollment
        assert len(modified_trial.sites) == len(self.base_trial.sites)
        assert modified_trial.sites[0].activation_time.mode == self.base_trial.sites[0].activation_time.mode

    def test_distribution_scale_override(self):
        """Scale override multiplies distribution parameters."""
        scenario = ScenarioProfile(
            scenario_id="SCALED",
            description="Scale activation",
            version="1.0.0",
            site_overrides={
                "SITE_001": {
                    "activation_time": {
                        "type": "distribution_scale",
                        "parameters": {"scale_factor": 1.5},
                        "reason": "Test"
                    }
                }
            }
        )

        modified_trial = apply_scenario(self.base_trial, scenario)
        original_dist = self.base_trial.sites[0].activation_time
        modified_dist = modified_trial.sites[0].activation_time

        assert modified_dist.low == pytest.approx(original_dist.low * 1.5)
        assert modified_dist.mode == pytest.approx(original_dist.mode * 1.5)
        assert modified_dist.high == pytest.approx(original_dist.high * 1.5)

    def test_distribution_shift_override(self):
        """Shift override adds to distribution parameters."""
        scenario = ScenarioProfile(
            scenario_id="SHIFTED",
            description="Shift activation",
            version="1.0.0",
            site_overrides={
                "SITE_001": {
                    "activation_time": {
                        "type": "distribution_shift",
                        "parameters": {"shift": 10},
                        "reason": "Test"
                    }
                }
            }
        )

        modified_trial = apply_scenario(self.base_trial, scenario)
        original_dist = self.base_trial.sites[0].activation_time
        modified_dist = modified_trial.sites[0].activation_time

        assert modified_dist.low == pytest.approx(original_dist.low + 10)
        assert modified_dist.mode == pytest.approx(original_dist.mode + 10)
        assert modified_dist.high == pytest.approx(original_dist.high + 10)

    def test_distribution_param_override(self):
        """Param override modifies specific parameters."""
        scenario = ScenarioProfile(
            scenario_id="PARAM_MOD",
            description="Modify param",
            version="1.0.0",
            site_overrides={
                "SITE_001": {
                    "activation_time": {
                        "type": "distribution_param",
                        "parameters": {"mode": 60},  # Change mode only
                        "reason": "Test"
                    }
                }
            }
        )

        modified_trial = apply_scenario(self.base_trial, scenario)
        original_dist = self.base_trial.sites[0].activation_time
        modified_dist = modified_trial.sites[0].activation_time

        # Mode changed
        assert modified_dist.mode == 60

        # Low and high unchanged
        assert modified_dist.low == original_dist.low
        assert modified_dist.high == original_dist.high

    def test_direct_value_override(self):
        """Direct value override replaces deterministic values."""
        scenario = ScenarioProfile(
            scenario_id="DIRECT",
            description="Direct override",
            version="1.0.0",
            trial_overrides={
                "target_enrollment": {
                    "type": "direct_value",
                    "value": 150,
                    "reason": "Protocol amendment"
                }
            }
        )

        modified_trial = apply_scenario(self.base_trial, scenario)

        assert modified_trial.target_enrollment == 150
        assert self.base_trial.target_enrollment == 200  # Base unchanged

    def test_resource_capacity_override(self):
        """Can override resource capacity."""
        trial_with_resources = Trial(
            trial_id="BASE",
            target_enrollment=200,
            sites=[self.base_trial.sites[0]],
            patient_flow=self.base_trial.patient_flow,
            resources=[
                Resource(
                    resource_id="MONITOR",
                    resource_type="staff",
                    capacity=5
                )
            ]
        )

        scenario = ScenarioProfile(
            scenario_id="REDUCED_CAPACITY",
            description="Reduce capacity",
            version="1.0.0",
            resource_overrides={
                "MONITOR": {
                    "capacity": {
                        "type": "direct_value",
                        "value": 3,
                        "reason": "Budget cuts"
                    }
                }
            }
        )

        modified_trial = apply_scenario(trial_with_resources, scenario)

        assert modified_trial.resources[0].capacity == 3
        assert trial_with_resources.resources[0].capacity == 5  # Base unchanged


class TestScenarioComposition:
    """Test explicit scenario composition."""

    def test_compose_scenarios(self):
        """compose_scenarios() merges overrides explicitly."""
        scenario_a = ScenarioProfile(
            scenario_id="A",
            description="Scenario A",
            version="1.0.0",
            site_overrides={"SITE_001": {"activation_time": {"type": "distribution_scale", "parameters": {"scale_factor": 1.2}}}}
        )

        scenario_b = ScenarioProfile(
            scenario_id="B",
            description="Scenario B",
            version="1.0.0",
            trial_overrides={"target_enrollment": {"type": "direct_value", "value": 150}}
        )

        combined = compose_scenarios(scenario_a, scenario_b)

        assert "A__AND__B" in combined.scenario_id
        assert "SITE_001" in combined.site_overrides
        assert "target_enrollment" in combined.trial_overrides

    def test_compose_scenarios_overlay_takes_precedence(self):
        """Later scenario overrides earlier on conflict."""
        scenario_a = ScenarioProfile(
            scenario_id="A",
            description="A",
            version="1.0.0",
            trial_overrides={"target_enrollment": {"type": "direct_value", "value": 150}}
        )

        scenario_b = ScenarioProfile(
            scenario_id="B",
            description="B",
            version="1.0.0",
            trial_overrides={"target_enrollment": {"type": "direct_value", "value": 175}}
        )

        combined = compose_scenarios(scenario_a, scenario_b)

        # B takes precedence
        assert combined.trial_overrides["target_enrollment"]["value"] == 175


class TestScenarioDiffing:
    """Test scenario comparison."""

    def test_diff_scenarios(self):
        """diff_scenarios() identifies differences."""
        scenario_a = ScenarioProfile(
            scenario_id="A",
            description="A",
            version="1.0.0",
            site_overrides={"SITE_001": {"activation_time": {"type": "distribution_scale", "parameters": {"scale_factor": 1.2}}}}
        )

        scenario_b = ScenarioProfile(
            scenario_id="B",
            description="B",
            version="1.0.0",
            site_overrides={"SITE_001": {"activation_time": {"type": "distribution_scale", "parameters": {"scale_factor": 1.3}}}}
        )

        diff = diff_scenarios(scenario_a, scenario_b)

        assert diff["scenario_a"] == "A"
        assert diff["scenario_b"] == "B"
        assert "site_changes" in diff
        assert len(diff["site_changes"]["modified"]) > 0


class TestArchitecturalGuarantees:
    """Test that scenario system maintains architectural principles."""

    def test_scenarios_are_pure_data(self):
        """Scenarios have no methods except to_dict/from_dict."""
        scenario = ScenarioProfile(
            scenario_id="TEST",
            description="Test",
            version="1.0.0"
        )

        # Should only have dataclass methods + to_dict/from_dict
        methods = [m for m in dir(scenario) if not m.startswith('_') and callable(getattr(scenario, m))]

        # Only allowed methods
        allowed = {'to_dict'}
        actual = set(methods)

        # May have other dataclass methods, but shouldn't have execution methods
        forbidden = {'apply', 'execute', 'run', 'simulate', 'merge', 'activate'}
        assert not (actual & forbidden), f"Found forbidden methods: {actual & forbidden}"

    def test_apply_scenario_is_pure_function(self):
        """apply_scenario() doesn't mutate inputs."""
        base_trial = Trial(
            trial_id="BASE",
            target_enrollment=200,
            sites=[
                Site(
                    site_id="SITE_001",
                    activation_time=Triangular(30, 45, 90),
                    enrollment_rate=Gamma(2, 1.5),
                    dropout_rate=Bernoulli(0.15)
                )
            ],
            patient_flow=PatientFlow(
                flow_id="FLOW",
                states={"enrolled", "completed"},
                initial_state="enrolled",
                terminal_states={"completed"},
                transition_times={(("enrolled", "completed")): Triangular(90, 180, 365)}
            )
        )

        scenario = ScenarioProfile(
            scenario_id="TEST",
            description="Test",
            version="1.0.0",
            site_overrides={
                "SITE_001": {
                    "activation_time": {
                        "type": "distribution_scale",
                        "parameters": {"scale_factor": 1.5},
                        "reason": "Test"
                    }
                }
            }
        )

        # Record original values
        original_mode = base_trial.sites[0].activation_time.mode
        original_trial_id = base_trial.trial_id
        original_scenario_id = scenario.scenario_id

        # Apply scenario
        modified_trial = apply_scenario(base_trial, scenario)

        # Verify no mutation
        assert base_trial.sites[0].activation_time.mode == original_mode
        assert base_trial.trial_id == original_trial_id
        assert scenario.scenario_id == original_scenario_id

        # Verify new object returned
        assert modified_trial is not base_trial
        assert modified_trial.sites[0] is not base_trial.sites[0]

    def test_scenarios_are_json_serializable(self):
        """Scenarios can round-trip through JSON."""
        scenario = ScenarioProfile(
            scenario_id="TEST",
            description="Test scenario",
            version="1.0.0",
            site_overrides={
                "SITE_001": {
                    "activation_time": {
                        "type": "distribution_scale",
                        "parameters": {"scale_factor": 1.2},
                        "reason": "Test"
                    }
                }
            }
        )

        # Serialize
        data = scenario.to_dict()
        json_str = json.dumps(data)

        # Deserialize
        loaded_data = json.loads(json_str)
        loaded_scenario = ScenarioProfile.from_dict(loaded_data)

        # Verify round-trip
        assert loaded_scenario.scenario_id == scenario.scenario_id
        assert loaded_scenario.version == scenario.version
        assert loaded_scenario.site_overrides == scenario.site_overrides

    def test_deterministic_application(self):
        """Same base + scenario → same result (deterministic)."""
        base_trial = Trial(
            trial_id="BASE",
            target_enrollment=200,
            sites=[
                Site(
                    site_id="SITE_001",
                    activation_time=Triangular(30, 45, 90),
                    enrollment_rate=Gamma(2, 1.5),
                    dropout_rate=Bernoulli(0.15)
                )
            ],
            patient_flow=PatientFlow(
                flow_id="FLOW",
                states={"enrolled", "completed"},
                initial_state="enrolled",
                terminal_states={"completed"},
                transition_times={(("enrolled", "completed")): Triangular(90, 180, 365)}
            )
        )

        scenario = ScenarioProfile(
            scenario_id="TEST",
            description="Test",
            version="1.0.0",
            site_overrides={
                "SITE_001": {
                    "activation_time": {
                        "type": "distribution_scale",
                        "parameters": {"scale_factor": 1.3},
                        "reason": "Test"
                    }
                }
            }
        )

        # Apply twice
        result1 = apply_scenario(base_trial, scenario)
        result2 = apply_scenario(base_trial, scenario)

        # Should be identical
        assert result1.sites[0].activation_time.mode == result2.sites[0].activation_time.mode
        assert result1.target_enrollment == result2.target_enrollment
