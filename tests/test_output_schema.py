"""
Tests for simulation output schema.

Verifies:
- Distribution summary structure is flattened for easy access
- JSON serialization/deserialization works correctly
- Enhanced output contains all required components
- Provenance tracking captures execution context
"""

import pytest
import json
import tempfile
from seleensim.entities import Site, Trial, PatientFlow
from seleensim.distributions import Triangular, Gamma, Bernoulli
from seleensim.simulation import SimulationEngine
from seleensim.output_schema import (
    ProvenanceRecord,
    PercentileDistribution,
    InputSpecification,
    EnhancedSimulationOutput,
    AggregatedResults,
    create_enhanced_output
)


class TestDistributionSummaryStructure:
    """Test that distribution summary is correctly flattened."""

    @pytest.fixture
    def sample_trial(self):
        return Trial(
            trial_id="TEST_TRIAL",
            target_enrollment=100,
            sites=[
                Site(
                    site_id="SITE_001",
                    activation_time=Triangular(low=30, mode=45, high=90),
                    enrollment_rate=Gamma(shape=2, scale=1.5),
                    dropout_rate=Bernoulli(p=0.15)
                )
            ],
            activities=[],
            resources=[],
            patient_flow=PatientFlow(
                flow_id="STANDARD",
                states={"enrolled", "completed"},
                initial_state="enrolled",
                terminal_states={"completed"},
                transition_times={("enrolled", "completed"): Triangular(90, 180, 365)}
            )
        )

    def test_distribution_parameters_accessible_at_top_level(self, sample_trial):
        """Distribution parameters should be at top level, not nested under 'params'."""
        input_spec = InputSpecification.from_trial(sample_trial)
        dist_summary = input_spec.distribution_summary

        # Test Triangular distribution
        activation_dist = dist_summary["SITE_001.activation_time"]
        assert activation_dist["type"] == "Triangular"
        assert "low" in activation_dist  # Direct access, not activation_dist['params']['low']
        assert "mode" in activation_dist
        assert "high" in activation_dist
        assert activation_dist["low"] == 30
        assert activation_dist["mode"] == 45
        assert activation_dist["high"] == 90

    def test_gamma_distribution_parameters_flattened(self, sample_trial):
        """Gamma distribution parameters should be accessible at top level."""
        input_spec = InputSpecification.from_trial(sample_trial)
        dist_summary = input_spec.distribution_summary

        enrollment_dist = dist_summary["SITE_001.enrollment_rate"]
        assert enrollment_dist["type"] == "Gamma"
        assert "shape" in enrollment_dist
        assert "scale" in enrollment_dist
        assert enrollment_dist["shape"] == 2
        assert enrollment_dist["scale"] == 1.5

    def test_bernoulli_distribution_parameters_flattened(self, sample_trial):
        """Bernoulli distribution parameters should be accessible at top level."""
        input_spec = InputSpecification.from_trial(sample_trial)
        dist_summary = input_spec.distribution_summary

        dropout_dist = dist_summary["SITE_001.dropout_rate"]
        assert dropout_dist["type"] == "Bernoulli"
        assert "p" in dropout_dist
        assert dropout_dist["p"] == 0.15

    def test_params_key_not_present(self, sample_trial):
        """The old nested 'params' key should not be present."""
        input_spec = InputSpecification.from_trial(sample_trial)
        dist_summary = input_spec.distribution_summary

        # Check all distributions - none should have 'params' key
        for key, dist in dist_summary.items():
            assert "params" not in dist, f"Distribution {key} still has nested 'params' key"


class TestInputSpecification:
    """Test InputSpecification creation and serialization."""

    @pytest.fixture
    def sample_trial(self):
        return Trial(
            trial_id="TEST_TRIAL",
            target_enrollment=100,
            sites=[
                Site(
                    site_id="SITE_001",
                    activation_time=Triangular(low=30, mode=45, high=90),
                    enrollment_rate=Gamma(shape=2, scale=1.5),
                    dropout_rate=Bernoulli(p=0.15)
                )
            ],
            activities=[],
            resources=[],
            patient_flow=PatientFlow(
                flow_id="STANDARD",
                states={"enrolled", "completed"},
                initial_state="enrolled",
                terminal_states={"completed"},
                transition_times={("enrolled", "completed"): Triangular(90, 180, 365)}
            )
        )

    def test_from_trial_creates_input_specification(self, sample_trial):
        """InputSpecification.from_trial() should extract all trial metadata."""
        input_spec = InputSpecification.from_trial(sample_trial)

        assert input_spec.trial_id == "TEST_TRIAL"
        assert input_spec.scenario_id is None  # No scenario applied
        assert input_spec.scenario_profile is None
        assert len(input_spec.constraints) == 0  # No constraints

        # Check deterministic summary
        assert input_spec.deterministic_summary["target_enrollment"] == 100
        assert input_spec.deterministic_summary["num_sites"] == 1

        # Check distribution summary exists
        assert len(input_spec.distribution_summary) > 0

    def test_input_specification_serializable(self, sample_trial):
        """InputSpecification should serialize to JSON."""
        input_spec = InputSpecification.from_trial(sample_trial)
        data = input_spec.to_dict()

        # Should be JSON-serializable
        json_str = json.dumps(data)
        loaded = json.loads(json_str)

        assert loaded["trial_id"] == "TEST_TRIAL"
        assert "distribution_summary" in loaded
        assert "deterministic_summary" in loaded


class TestPercentileDistribution:
    """Test PercentileDistribution computation."""

    def test_from_values_computes_percentiles(self):
        """PercentileDistribution.from_values() should compute all statistics."""
        values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

        dist = PercentileDistribution.from_values(values)

        # Check percentiles are in correct order
        assert dist.p10 < dist.p25 < dist.p50 < dist.p75 < dist.p90 < dist.p95
        assert dist.p50 == pytest.approx(55.0, abs=5)  # Median around 55
        assert dist.mean == pytest.approx(55.0, abs=5)

    def test_range_methods(self):
        """Test convenience range methods."""
        values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        dist = PercentileDistribution.from_values(values)

        p10_p90_range = dist.range_p10_p90()
        assert p10_p90_range == dist.p90 - dist.p10
        assert p10_p90_range > 0

        iqr = dist.range_p25_p75()
        assert iqr == dist.p75 - dist.p25
        assert iqr > 0


class TestEnhancedSimulationOutput:
    """Test complete enhanced output creation and serialization."""

    @pytest.fixture
    def sample_trial(self):
        return Trial(
            trial_id="TEST_TRIAL",
            target_enrollment=10,  # Small for fast test
            sites=[
                Site(
                    site_id="SITE_001",
                    activation_time=Triangular(low=30, mode=45, high=90),
                    enrollment_rate=Gamma(shape=2, scale=1.5),
                    dropout_rate=Bernoulli(p=0.15)
                )
            ],
            activities=[],
            resources=[],
            patient_flow=PatientFlow(
                flow_id="STANDARD",
                states={"enrolled", "completed"},
                initial_state="enrolled",
                terminal_states={"completed"},
                transition_times={("enrolled", "completed"): Triangular(90, 180, 365)}
            )
        )

    def test_create_enhanced_output(self, sample_trial):
        """create_enhanced_output() should create complete output structure."""
        engine = SimulationEngine(master_seed=42)
        results = engine.run(sample_trial, num_runs=5)

        enhanced = create_enhanced_output(
            simulation_id="test_sim_001",
            trial=sample_trial,
            scenario=None,
            constraints=None,
            run_results=results.run_results,
            master_seed=42,
            execution_duration=1.23
        )

        # Check all components present
        assert enhanced.provenance.simulation_id == "test_sim_001"
        assert enhanced.provenance.master_seed == 42
        assert enhanced.provenance.num_runs == 5

        assert enhanced.input_specification.trial_id == "TEST_TRIAL"

        assert enhanced.aggregated_results.num_runs == 5
        assert enhanced.aggregated_results.completion_time.p50 > 0

    def test_json_round_trip(self, sample_trial):
        """EnhancedSimulationOutput should round-trip through JSON."""
        engine = SimulationEngine(master_seed=42)
        results = engine.run(sample_trial, num_runs=3)

        enhanced = create_enhanced_output(
            simulation_id="test_sim_002",
            trial=sample_trial,
            scenario=None,
            constraints=None,
            run_results=results.run_results,
            master_seed=42,
            execution_duration=1.0
        )

        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            enhanced.to_json(f.name, include_single_runs=True)
            filepath = f.name

        # Load back
        loaded = EnhancedSimulationOutput.from_json(filepath)

        # Verify key fields match
        assert loaded.provenance.simulation_id == enhanced.provenance.simulation_id
        assert loaded.provenance.master_seed == enhanced.provenance.master_seed
        assert loaded.input_specification.trial_id == enhanced.input_specification.trial_id

        # Verify statistics match (approximately - floating point precision)
        assert loaded.aggregated_results.completion_time.p50 == \
               pytest.approx(enhanced.aggregated_results.completion_time.p50, abs=0.01)

        # Clean up
        import os
        os.unlink(filepath)

    def test_json_export_without_single_runs(self, sample_trial):
        """JSON export should allow excluding single run details to save space."""
        engine = SimulationEngine(master_seed=42)
        results = engine.run(sample_trial, num_runs=3)

        enhanced = create_enhanced_output(
            simulation_id="test_sim_003",
            trial=sample_trial,
            scenario=None,
            constraints=None,
            run_results=results.run_results,
            master_seed=42,
            execution_duration=1.0
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            enhanced.to_json(f.name, include_single_runs=False)
            filepath = f.name

        # Load and verify single_run_results is None
        with open(filepath, 'r') as f:
            data = json.load(f)
            assert data["single_run_results"] is None

        # Clean up
        import os
        os.unlink(filepath)


class TestProvenanceRecord:
    """Test provenance tracking."""

    def test_provenance_captures_execution_context(self):
        """ProvenanceRecord should capture complete execution context."""
        provenance = ProvenanceRecord.create(
            simulation_id="test_001",
            num_runs=100,
            master_seed=42,
            initial_budget=float('inf'),
            execution_duration_seconds=12.34,
            include_environment=False
        )

        assert provenance.simulation_id == "test_001"
        assert provenance.num_runs == 100
        assert provenance.master_seed == 42
        assert provenance.execution_duration_seconds == 12.34
        assert provenance.seleensim_version == "0.1.0"
        assert provenance.python_version is not None
        assert provenance.execution_timestamp is not None

    def test_provenance_serializable(self):
        """ProvenanceRecord should serialize to JSON."""
        provenance = ProvenanceRecord.create(
            simulation_id="test_002",
            num_runs=50,
            master_seed=123,
            initial_budget=10000.0,
            execution_duration_seconds=5.67
        )

        data = provenance.to_dict()
        json_str = json.dumps(data)
        loaded = json.loads(json_str)

        assert loaded["simulation_id"] == "test_002"
        assert loaded["master_seed"] == 123
