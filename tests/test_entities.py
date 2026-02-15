"""
Unit tests for entity models.

Focus areas:
1. Immutability: Entities cannot be modified after creation
2. Validation: Invalid parameters fail loudly at construction
3. Type safety: Distributions must be Distribution type, not raw values
4. Structural integrity: References (dependencies, resources) must be valid
5. Serialization: Entities can be serialized to dict
6. No business logic: Entities are pure data holders
"""

import pytest
from seleensim.entities import Site, Activity, Resource, PatientFlow, Trial
from seleensim.distributions import Triangular, LogNormal, Gamma, Bernoulli


class TestSiteEntity:
    """Test Site entity validation and immutability."""

    def test_site_creation_valid(self):
        """Valid site should be created successfully."""
        site = Site(
            site_id="SITE001",
            activation_time=Triangular(30, 45, 90),
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15)
        )
        assert site.site_id == "SITE001"
        assert isinstance(site.activation_time, Triangular)
        assert site.max_capacity is None

    def test_site_with_capacity(self):
        """Site with max_capacity should be created successfully."""
        site = Site(
            site_id="SITE002",
            activation_time=Triangular(30, 45, 90),
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15),
            max_capacity=50
        )
        assert site.max_capacity == 50

    def test_site_immutable(self):
        """Site should be immutable after creation."""
        site = Site(
            site_id="SITE001",
            activation_time=Triangular(30, 45, 90),
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15)
        )
        with pytest.raises(Exception):  # FrozenInstanceError in dataclasses
            site.site_id = "MODIFIED"

    def test_site_empty_id_fails(self):
        """Site with empty site_id should fail."""
        with pytest.raises(ValueError, match="site_id cannot be empty"):
            Site(
                site_id="",
                activation_time=Triangular(30, 45, 90),
                enrollment_rate=Gamma(2, 1.5),
                dropout_rate=Bernoulli(0.15)
            )

    def test_site_non_distribution_fails(self):
        """Site with non-Distribution field should fail."""
        with pytest.raises(TypeError, match="activation_time must be Distribution"):
            Site(
                site_id="SITE001",
                activation_time=45,  # Not a Distribution!
                enrollment_rate=Gamma(2, 1.5),
                dropout_rate=Bernoulli(0.15)
            )

    def test_site_negative_capacity_fails(self):
        """Site with negative max_capacity should fail."""
        with pytest.raises(ValueError, match="max_capacity must be >= 0"):
            Site(
                site_id="SITE001",
                activation_time=Triangular(30, 45, 90),
                enrollment_rate=Gamma(2, 1.5),
                dropout_rate=Bernoulli(0.15),
                max_capacity=-5
            )

    def test_site_serialization(self):
        """Site should serialize to dict."""
        site = Site(
            site_id="SITE001",
            activation_time=Triangular(30, 45, 90),
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15),
            max_capacity=100
        )
        data = site.to_dict()

        assert data["type"] == "Site"
        assert data["site_id"] == "SITE001"
        assert data["activation_time"]["type"] == "Triangular"
        assert data["max_capacity"] == 100


class TestActivityEntity:
    """Test Activity entity validation and immutability."""

    def test_activity_creation_valid(self):
        """Valid activity should be created successfully."""
        activity = Activity(
            activity_id="ACT001",
            duration=LogNormal(30, 0.2),
            dependencies={"ACT000"},
            required_resources={"RES001"}
        )
        assert activity.activity_id == "ACT001"
        assert "ACT000" in activity.dependencies
        assert "RES001" in activity.required_resources

    def test_activity_no_dependencies(self):
        """Activity with no dependencies should work."""
        activity = Activity(
            activity_id="ACT001",
            duration=LogNormal(30, 0.2)
        )
        assert len(activity.dependencies) == 0
        assert len(activity.required_resources) == 0

    def test_activity_with_success_probability(self):
        """Activity with success_probability should be created."""
        activity = Activity(
            activity_id="ACT001",
            duration=LogNormal(30, 0.2),
            success_probability=Bernoulli(0.9)
        )
        assert isinstance(activity.success_probability, Bernoulli)

    def test_activity_immutable(self):
        """Activity should be immutable after creation."""
        activity = Activity(
            activity_id="ACT001",
            duration=LogNormal(30, 0.2)
        )
        with pytest.raises(Exception):
            activity.activity_id = "MODIFIED"

    def test_activity_self_dependency_fails(self):
        """Activity cannot depend on itself."""
        with pytest.raises(ValueError, match="cannot depend on itself"):
            Activity(
                activity_id="ACT001",
                duration=LogNormal(30, 0.2),
                dependencies={"ACT001"}  # Self-dependency!
            )

    def test_activity_empty_id_fails(self):
        """Activity with empty activity_id should fail."""
        with pytest.raises(ValueError, match="activity_id cannot be empty"):
            Activity(
                activity_id="",
                duration=LogNormal(30, 0.2)
            )

    def test_activity_non_distribution_duration_fails(self):
        """Activity with non-Distribution duration should fail."""
        with pytest.raises(TypeError, match="duration must be Distribution"):
            Activity(
                activity_id="ACT001",
                duration=30  # Not a Distribution!
            )

    def test_activity_serialization(self):
        """Activity should serialize to dict."""
        activity = Activity(
            activity_id="ACT001",
            duration=LogNormal(30, 0.2),
            dependencies={"ACT000"},
            success_probability=Bernoulli(0.85)
        )
        data = activity.to_dict()

        assert data["type"] == "Activity"
        assert data["activity_id"] == "ACT001"
        assert "ACT000" in data["dependencies"]
        assert data["success_probability"]["type"] == "Bernoulli"


class TestResourceEntity:
    """Test Resource entity validation and immutability."""

    def test_resource_creation_valid(self):
        """Valid resource should be created successfully."""
        resource = Resource(
            resource_id="RES001",
            resource_type="staff",
            capacity=10
        )
        assert resource.resource_id == "RES001"
        assert resource.resource_type == "staff"
        assert resource.capacity == 10

    def test_resource_with_availability(self):
        """Resource with availability distribution should work."""
        resource = Resource(
            resource_id="RES001",
            resource_type="equipment",
            availability=Bernoulli(0.95)
        )
        assert isinstance(resource.availability, Bernoulli)

    def test_resource_with_utilization_rate(self):
        """Resource with utilization_rate should work."""
        resource = Resource(
            resource_id="RES001",
            resource_type="budget",
            utilization_rate=Gamma(3, 1000)
        )
        assert isinstance(resource.utilization_rate, Gamma)

    def test_resource_immutable(self):
        """Resource should be immutable after creation."""
        resource = Resource(
            resource_id="RES001",
            resource_type="staff"
        )
        with pytest.raises(Exception):
            resource.resource_id = "MODIFIED"

    def test_resource_empty_id_fails(self):
        """Resource with empty resource_id should fail."""
        with pytest.raises(ValueError, match="resource_id cannot be empty"):
            Resource(resource_id="", resource_type="staff")

    def test_resource_empty_type_fails(self):
        """Resource with empty resource_type should fail."""
        with pytest.raises(ValueError, match="resource_type cannot be empty"):
            Resource(resource_id="RES001", resource_type="")

    def test_resource_zero_capacity_fails(self):
        """Resource with zero capacity should fail."""
        with pytest.raises(ValueError, match="capacity must be > 0"):
            Resource(
                resource_id="RES001",
                resource_type="staff",
                capacity=0
            )

    def test_resource_serialization(self):
        """Resource should serialize to dict."""
        resource = Resource(
            resource_id="RES001",
            resource_type="staff",
            capacity=5,
            availability=Bernoulli(0.9)
        )
        data = resource.to_dict()

        assert data["type"] == "Resource"
        assert data["resource_id"] == "RES001"
        assert data["resource_type"] == "staff"
        assert data["availability"]["type"] == "Bernoulli"


class TestPatientFlowEntity:
    """Test PatientFlow entity validation and immutability."""

    def test_patient_flow_creation_valid(self):
        """Valid patient flow should be created successfully."""
        flow = PatientFlow(
            flow_id="FLOW001",
            states={"enrolled", "active", "completed", "dropout"},
            initial_state="enrolled",
            terminal_states={"completed", "dropout"},
            transition_times={
                ("enrolled", "active"): Triangular(7, 14, 30),
                ("active", "completed"): LogNormal(180, 0.3),
                ("active", "dropout"): LogNormal(90, 0.5)
            },
            transition_probabilities={
                ("active", "completed"): Bernoulli(0.85),
                ("active", "dropout"): Bernoulli(0.15)
            }
        )
        assert flow.flow_id == "FLOW001"
        assert "enrolled" in flow.states
        assert flow.initial_state == "enrolled"

    def test_patient_flow_immutable(self):
        """PatientFlow should be immutable after creation."""
        flow = PatientFlow(
            flow_id="FLOW001",
            states={"enrolled", "completed"},
            initial_state="enrolled",
            terminal_states={"completed"},
            transition_times={("enrolled", "completed"): Triangular(30, 60, 120)}
        )
        with pytest.raises(Exception):
            flow.flow_id = "MODIFIED"

    def test_patient_flow_empty_id_fails(self):
        """PatientFlow with empty flow_id should fail."""
        with pytest.raises(ValueError, match="flow_id cannot be empty"):
            PatientFlow(
                flow_id="",
                states={"enrolled", "completed"},
                initial_state="enrolled",
                terminal_states={"completed"},
                transition_times={("enrolled", "completed"): Triangular(30, 60, 120)}
            )

    def test_patient_flow_empty_states_fails(self):
        """PatientFlow with empty states should fail."""
        with pytest.raises(ValueError, match="states must be a non-empty set"):
            PatientFlow(
                flow_id="FLOW001",
                states=set(),
                initial_state="enrolled",
                terminal_states=set(),
                transition_times={}
            )

    def test_patient_flow_invalid_initial_state_fails(self):
        """PatientFlow with initial_state not in states should fail."""
        with pytest.raises(ValueError, match="initial_state .* not in states"):
            PatientFlow(
                flow_id="FLOW001",
                states={"enrolled", "completed"},
                initial_state="INVALID",
                terminal_states={"completed"},
                transition_times={("enrolled", "completed"): Triangular(30, 60, 120)}
            )

    def test_patient_flow_invalid_terminal_states_fails(self):
        """PatientFlow with terminal_states not in states should fail."""
        with pytest.raises(ValueError, match="terminal_states contains invalid states"):
            PatientFlow(
                flow_id="FLOW001",
                states={"enrolled", "completed"},
                initial_state="enrolled",
                terminal_states={"completed", "INVALID"},
                transition_times={("enrolled", "completed"): Triangular(30, 60, 120)}
            )

    def test_patient_flow_invalid_transition_fails(self):
        """PatientFlow with transition referencing invalid states should fail."""
        with pytest.raises(ValueError, match="transition_times contains invalid"):
            PatientFlow(
                flow_id="FLOW001",
                states={"enrolled", "completed"},
                initial_state="enrolled",
                terminal_states={"completed"},
                transition_times={("enrolled", "INVALID"): Triangular(30, 60, 120)}
            )

    def test_patient_flow_serialization(self):
        """PatientFlow should serialize to dict."""
        flow = PatientFlow(
            flow_id="FLOW001",
            states={"enrolled", "completed"},
            initial_state="enrolled",
            terminal_states={"completed"},
            transition_times={("enrolled", "completed"): Triangular(30, 60, 120)}
        )
        data = flow.to_dict()

        assert data["type"] == "PatientFlow"
        assert data["flow_id"] == "FLOW001"
        assert "enrolled" in data["states"]
        assert "enrolled->completed" in data["transition_times"]


class TestTrialEntity:
    """Test Trial entity validation and immutability."""

    def setup_method(self):
        """Create valid components for trial construction."""
        self.site1 = Site(
            site_id="SITE001",
            activation_time=Triangular(30, 45, 90),
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15)
        )
        self.site2 = Site(
            site_id="SITE002",
            activation_time=Triangular(40, 60, 120),
            enrollment_rate=Gamma(1.5, 2),
            dropout_rate=Bernoulli(0.1)
        )
        self.flow = PatientFlow(
            flow_id="FLOW001",
            states={"enrolled", "active", "completed"},
            initial_state="enrolled",
            terminal_states={"completed"},
            transition_times={
                ("enrolled", "active"): Triangular(7, 14, 30),
                ("active", "completed"): LogNormal(180, 0.3)
            }
        )

    def test_trial_creation_valid(self):
        """Valid trial should be created successfully."""
        trial = Trial(
            trial_id="TRIAL001",
            target_enrollment=200,
            sites=[self.site1, self.site2],
            patient_flow=self.flow
        )
        assert trial.trial_id == "TRIAL001"
        assert trial.target_enrollment == 200
        assert len(trial.sites) == 2

    def test_trial_with_activities_and_resources(self):
        """Trial with activities and resources should be created."""
        activity = Activity(
            activity_id="ACT001",
            duration=LogNormal(30, 0.2),
            required_resources={"RES001"}
        )
        resource = Resource(
            resource_id="RES001",
            resource_type="staff",
            capacity=10
        )
        trial = Trial(
            trial_id="TRIAL001",
            target_enrollment=200,
            sites=[self.site1],
            patient_flow=self.flow,
            activities=[activity],
            resources=[resource]
        )
        assert len(trial.activities) == 1
        assert len(trial.resources) == 1

    def test_trial_immutable(self):
        """Trial should be immutable after creation."""
        trial = Trial(
            trial_id="TRIAL001",
            target_enrollment=200,
            sites=[self.site1],
            patient_flow=self.flow
        )
        with pytest.raises(Exception):
            trial.trial_id = "MODIFIED"

    def test_trial_empty_id_fails(self):
        """Trial with empty trial_id should fail."""
        with pytest.raises(ValueError, match="trial_id cannot be empty"):
            Trial(
                trial_id="",
                target_enrollment=200,
                sites=[self.site1],
                patient_flow=self.flow
            )

    def test_trial_zero_enrollment_fails(self):
        """Trial with zero target_enrollment should fail."""
        with pytest.raises(ValueError, match="target_enrollment must be > 0"):
            Trial(
                trial_id="TRIAL001",
                target_enrollment=0,
                sites=[self.site1],
                patient_flow=self.flow
            )

    def test_trial_empty_sites_fails(self):
        """Trial with empty sites list should fail."""
        with pytest.raises(ValueError, match="sites must be a non-empty list"):
            Trial(
                trial_id="TRIAL001",
                target_enrollment=200,
                sites=[],
                patient_flow=self.flow
            )

    def test_trial_duplicate_site_ids_fails(self):
        """Trial with duplicate site IDs should fail."""
        site_duplicate = Site(
            site_id="SITE001",  # Duplicate!
            activation_time=Triangular(30, 45, 90),
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15)
        )
        with pytest.raises(ValueError, match="Duplicate site_ids"):
            Trial(
                trial_id="TRIAL001",
                target_enrollment=200,
                sites=[self.site1, site_duplicate],
                patient_flow=self.flow
            )

    def test_trial_invalid_activity_dependency_fails(self):
        """Trial with activity referencing non-existent dependency should fail."""
        activity = Activity(
            activity_id="ACT001",
            duration=LogNormal(30, 0.2),
            dependencies={"NONEXISTENT"}
        )
        with pytest.raises(ValueError, match="invalid dependencies"):
            Trial(
                trial_id="TRIAL001",
                target_enrollment=200,
                sites=[self.site1],
                patient_flow=self.flow,
                activities=[activity]
            )

    def test_trial_invalid_resource_reference_fails(self):
        """Trial with activity requiring non-existent resource should fail."""
        activity = Activity(
            activity_id="ACT001",
            duration=LogNormal(30, 0.2),
            required_resources={"NONEXISTENT"}
        )
        with pytest.raises(ValueError, match="non-existent resources"):
            Trial(
                trial_id="TRIAL001",
                target_enrollment=200,
                sites=[self.site1],
                patient_flow=self.flow,
                activities=[activity]
            )

    def test_trial_valid_activity_dependencies(self):
        """Trial with valid activity dependencies should succeed."""
        act1 = Activity(activity_id="ACT001", duration=LogNormal(30, 0.2))
        act2 = Activity(
            activity_id="ACT002",
            duration=LogNormal(20, 0.1),
            dependencies={"ACT001"}
        )
        trial = Trial(
            trial_id="TRIAL001",
            target_enrollment=200,
            sites=[self.site1],
            patient_flow=self.flow,
            activities=[act1, act2]
        )
        assert len(trial.activities) == 2

    def test_trial_serialization(self):
        """Trial should serialize to dict."""
        trial = Trial(
            trial_id="TRIAL001",
            target_enrollment=200,
            sites=[self.site1],
            patient_flow=self.flow
        )
        data = trial.to_dict()

        assert data["type"] == "Trial"
        assert data["trial_id"] == "TRIAL001"
        assert data["target_enrollment"] == 200
        assert len(data["sites"]) == 1
        assert data["patient_flow"]["type"] == "PatientFlow"


class TestEntityNoBusinessLogic:
    """Verify entities have no business logic methods."""

    def test_site_has_no_business_methods(self):
        """Site should have no business logic methods."""
        site = Site(
            site_id="SITE001",
            activation_time=Triangular(30, 45, 90),
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15)
        )
        # Should not have methods like enroll(), activate(), etc.
        assert not hasattr(site, "enroll")
        assert not hasattr(site, "activate")
        assert not hasattr(site, "is_active")

    def test_activity_has_no_business_methods(self):
        """Activity should have no business logic methods."""
        activity = Activity(
            activity_id="ACT001",
            duration=LogNormal(30, 0.2)
        )
        # Should not have methods like start(), complete(), execute(), etc.
        assert not hasattr(activity, "start")
        assert not hasattr(activity, "complete")
        assert not hasattr(activity, "execute")

    def test_entities_only_have_to_dict(self):
        """Entities should only have to_dict() as public method."""
        site = Site(
            site_id="SITE001",
            activation_time=Triangular(30, 45, 90),
            enrollment_rate=Gamma(2, 1.5),
            dropout_rate=Bernoulli(0.15)
        )
        # Get all public methods (not starting with _)
        public_methods = [
            m for m in dir(site)
            if callable(getattr(site, m)) and not m.startswith("_")
        ]
        # Should only have to_dict (and maybe some dataclass-generated methods)
        assert "to_dict" in public_methods
        # No business logic methods
        business_method_names = {
            "enroll", "activate", "deactivate", "start", "stop",
            "execute", "complete", "allocate", "consume"
        }
        for method in public_methods:
            assert method not in business_method_names
