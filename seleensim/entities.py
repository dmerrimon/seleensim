"""
Core entity models for probabilistic simulation engine.

Design principles:
- Entities are immutable after creation (frozen dataclasses)
- Entities reference distributions but never sample them
- No business logic inside entities (pure data holders)
- No default values that imply real-world assumptions
- Validation fails loudly if required distributions are missing

Deterministic vs Stochastic:
- Deterministic fields: Structure, IDs, hard constraints (known at design time)
- Stochastic fields: Distributions representing uncertainty (unknown until sampled)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple
from seleensim.distributions import Distribution


@dataclass(frozen=True)
class Site:
    """
    A location that enrolls participants.

    Deterministic fields:
    - site_id: Unique identifier (string)
    - max_capacity: Hard limit on concurrent enrollments (None = unlimited)

    Stochastic fields (as Distribution references):
    - activation_time: Time from trial start until site becomes operational
    - enrollment_rate: Rate of enrollment once site is active
    - dropout_rate: Probability of enrolled participant dropping out

    Rationale:
    - site_id is deterministic: we know which sites exist before trial starts
    - max_capacity is deterministic: physical/regulatory constraint
    - activation_time is stochastic: site startup depends on contracts, IRB, staff hiring
    - enrollment_rate is stochastic: patient availability, referral patterns vary
    - dropout_rate is stochastic: patient behavior is inherently uncertain
    """
    site_id: str
    activation_time: Distribution
    enrollment_rate: Distribution
    dropout_rate: Distribution
    max_capacity: Optional[int] = None

    def __post_init__(self):
        """Validate fields at construction time (fail fast)."""
        if not self.site_id:
            raise ValueError("site_id cannot be empty")

        if not isinstance(self.activation_time, Distribution):
            raise TypeError(
                f"activation_time must be Distribution, got {type(self.activation_time).__name__}"
            )

        if not isinstance(self.enrollment_rate, Distribution):
            raise TypeError(
                f"enrollment_rate must be Distribution, got {type(self.enrollment_rate).__name__}"
            )

        if not isinstance(self.dropout_rate, Distribution):
            raise TypeError(
                f"dropout_rate must be Distribution, got {type(self.dropout_rate).__name__}"
            )

        if self.max_capacity is not None and self.max_capacity < 0:
            raise ValueError(f"max_capacity must be >= 0 or None, got {self.max_capacity}")

    def to_dict(self) -> Dict:
        """Serialize to dict for JSON export."""
        return {
            "type": "Site",
            "site_id": self.site_id,
            "activation_time": self.activation_time.to_dict(),
            "enrollment_rate": self.enrollment_rate.to_dict(),
            "dropout_rate": self.dropout_rate.to_dict(),
            "max_capacity": self.max_capacity
        }


@dataclass(frozen=True)
class Activity:
    """
    A task that must be completed during trial execution.

    Examples: site activation, monitoring visit, data lock, interim analysis.

    Deterministic fields:
    - activity_id: Unique identifier
    - dependencies: Set of activity_ids that must complete before this starts
    - required_resources: Resource types needed (empty set = no requirements)

    Stochastic fields (as Distribution references):
    - duration: Time required to complete activity
    - success_probability: Optional distribution for whether activity succeeds
      (None = deterministic success)

    CLARIFICATION ON success_probability:
    This represents STRUCTURAL BRANCHING in the trial design, not operational performance.

    Examples of valid use:
    - IRB approval with 95% success rate (structural: some sites may fail approval)
    - Site activation with 90% success rate (structural: some sites may be rejected)

    NOT for modeling:
    - Operational efficiency ("this usually takes 90% of estimated time")
    - Execution quality ("this is done correctly 95% of the time")
    - Team performance ("this team succeeds 80% of the time")

    If success_probability is specified, the simulation engine will sample it to determine
    whether the activity succeeds or fails AS A STRUCTURAL BRANCH (success leads to
    different downstream activities than failure). This is NOT a quality metric.

    Rationale:
    - activity_id is deterministic: activities are defined in protocol
    - dependencies are deterministic: task ordering is known (e.g., "site visit requires site activation")
    - required_resources are deterministic: protocol specifies what's needed
    - duration is stochastic: actual time depends on workload, complexity, unforeseen issues
    - success_probability is stochastic: some activities can fail (e.g., site activation rejected)
    """
    activity_id: str
    duration: Distribution
    dependencies: Set[str] = field(default_factory=set)
    required_resources: Set[str] = field(default_factory=set)
    success_probability: Optional[Distribution] = None

    def __post_init__(self):
        """Validate fields at construction time."""
        if not self.activity_id:
            raise ValueError("activity_id cannot be empty")

        if not isinstance(self.duration, Distribution):
            raise TypeError(
                f"duration must be Distribution, got {type(self.duration).__name__}"
            )

        if not isinstance(self.dependencies, set):
            raise TypeError(f"dependencies must be set, got {type(self.dependencies).__name__}")

        if not isinstance(self.required_resources, set):
            raise TypeError(
                f"required_resources must be set, got {type(self.required_resources).__name__}"
            )

        if self.success_probability is not None and not isinstance(self.success_probability, Distribution):
            raise TypeError(
                f"success_probability must be Distribution or None, got {type(self.success_probability).__name__}"
            )

        # Check for self-dependency (common mistake)
        if self.activity_id in self.dependencies:
            raise ValueError(f"Activity {self.activity_id} cannot depend on itself")

    def to_dict(self) -> Dict:
        """Serialize to dict for JSON export."""
        return {
            "type": "Activity",
            "activity_id": self.activity_id,
            "duration": self.duration.to_dict(),
            "dependencies": list(self.dependencies),
            "required_resources": list(self.required_resources),
            "success_probability": self.success_probability.to_dict() if self.success_probability else None
        }


@dataclass(frozen=True)
class Resource:
    """
    A constrained resource required by activities.

    Examples: monitors, coordinators, budget, equipment.

    Deterministic fields:
    - resource_id: Unique identifier
    - resource_type: Category (e.g., "staff", "budget", "equipment")
    - capacity: Maximum simultaneous usage (None = unlimited)

    Stochastic fields (as Distribution references):
    - availability: Probability resource is available when requested
      (None = always available)
    - utilization_rate: Amount consumed per use
      (None = not applicable, e.g., for binary resources)

    Rationale:
    - resource_id is deterministic: resources are known in advance
    - resource_type is deterministic: categorization for reporting/grouping
    - capacity is deterministic: physical or policy limit
    - availability is stochastic: staff sick days, equipment downtime
    - utilization_rate is stochastic: actual consumption varies (e.g., monitor hours per site)
    """
    resource_id: str
    resource_type: str
    capacity: Optional[int] = None
    availability: Optional[Distribution] = None
    utilization_rate: Optional[Distribution] = None

    def __post_init__(self):
        """Validate fields at construction time."""
        if not self.resource_id:
            raise ValueError("resource_id cannot be empty")

        if not self.resource_type:
            raise ValueError("resource_type cannot be empty")

        if self.capacity is not None and self.capacity <= 0:
            raise ValueError(f"capacity must be > 0 or None, got {self.capacity}")

        if self.availability is not None and not isinstance(self.availability, Distribution):
            raise TypeError(
                f"availability must be Distribution or None, got {type(self.availability).__name__}"
            )

        if self.utilization_rate is not None and not isinstance(self.utilization_rate, Distribution):
            raise TypeError(
                f"utilization_rate must be Distribution or None, got {type(self.utilization_rate).__name__}"
            )

    def to_dict(self) -> Dict:
        """Serialize to dict for JSON export."""
        return {
            "type": "Resource",
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "capacity": self.capacity,
            "availability": self.availability.to_dict() if self.availability else None,
            "utilization_rate": self.utilization_rate.to_dict() if self.utilization_rate else None
        }


@dataclass(frozen=True)
class PatientFlow:
    """
    Defines how entities transition through states.

    ARCHITECTURAL GUARANTEE: This is a pure declarative specification of a state machine.
    It contains NO logic for:
    - Advancing state (no advance(), transition(), move_to() methods)
    - Sampling timing or probabilities (no sample_transition_time(), choose_next_state())
    - Triggering transitions (no execute(), apply(), run())
    - Computing derived values (no get_expected_duration(), calculate_completion_rate())

    The simulation engine is responsible for interpreting this specification and
    executing state transitions. This entity only defines the structure.

    Generic state machine for modeling flows (enrollment, treatment, follow-up).
    Despite the name, this is domain-agnostic and could model any process flow.

    Deterministic fields:
    - flow_id: Unique identifier
    - states: Set of valid state names
    - initial_state: Starting state
    - terminal_states: States that end the flow

    Stochastic fields (as Distribution references):
    - transition_times: Dict[(from_state, to_state)] -> Distribution of time to transition
    - transition_probabilities: Dict[(from_state, to_state)] -> Distribution of transition probability
      (For states with multiple possible next states)

    Rationale:
    - flow_id is deterministic: flow structure is designed in advance
    - states are deterministic: the state space is known (e.g., "enrolled", "active", "completed", "dropout")
    - initial_state is deterministic: all entities start in the same state
    - terminal_states are deterministic: which states are endpoints is known
    - transition_times are stochastic: actual durations vary (e.g., time from enrollment to first dose)
    - transition_probabilities are stochastic: which path is taken varies (e.g., complete vs dropout)
    """
    flow_id: str
    states: Set[str]
    initial_state: str
    terminal_states: Set[str]
    transition_times: Dict[Tuple[str, str], Distribution]
    transition_probabilities: Dict[Tuple[str, str], Distribution] = field(default_factory=dict)

    def __post_init__(self):
        """Validate fields at construction time."""
        if not self.flow_id:
            raise ValueError("flow_id cannot be empty")

        if not isinstance(self.states, set) or len(self.states) == 0:
            raise ValueError("states must be a non-empty set")

        if self.initial_state not in self.states:
            raise ValueError(f"initial_state '{self.initial_state}' not in states")

        if not isinstance(self.terminal_states, set):
            raise TypeError(f"terminal_states must be set, got {type(self.terminal_states).__name__}")

        if not self.terminal_states.issubset(self.states):
            invalid = self.terminal_states - self.states
            raise ValueError(f"terminal_states contains invalid states: {invalid}")

        # Validate transition_times
        if not isinstance(self.transition_times, dict):
            raise TypeError(
                f"transition_times must be dict, got {type(self.transition_times).__name__}"
            )

        for (from_state, to_state), dist in self.transition_times.items():
            if from_state not in self.states:
                raise ValueError(f"transition_times contains invalid from_state: {from_state}")
            if to_state not in self.states:
                raise ValueError(f"transition_times contains invalid to_state: {to_state}")
            if not isinstance(dist, Distribution):
                raise TypeError(
                    f"transition_times[({from_state}, {to_state})] must be Distribution"
                )

        # Validate transition_probabilities
        if not isinstance(self.transition_probabilities, dict):
            raise TypeError(
                f"transition_probabilities must be dict, got {type(self.transition_probabilities).__name__}"
            )

        for (from_state, to_state), dist in self.transition_probabilities.items():
            if from_state not in self.states:
                raise ValueError(
                    f"transition_probabilities contains invalid from_state: {from_state}"
                )
            if to_state not in self.states:
                raise ValueError(
                    f"transition_probabilities contains invalid to_state: {to_state}"
                )
            if not isinstance(dist, Distribution):
                raise TypeError(
                    f"transition_probabilities[({from_state}, {to_state})] must be Distribution"
                )

    def to_dict(self) -> Dict:
        """Serialize to dict for JSON export."""
        return {
            "type": "PatientFlow",
            "flow_id": self.flow_id,
            "states": list(self.states),
            "initial_state": self.initial_state,
            "terminal_states": list(self.terminal_states),
            "transition_times": {
                f"{from_s}->{to_s}": dist.to_dict()
                for (from_s, to_s), dist in self.transition_times.items()
            },
            "transition_probabilities": {
                f"{from_s}->{to_s}": dist.to_dict()
                for (from_s, to_s), dist in self.transition_probabilities.items()
            }
        }


@dataclass(frozen=True)
class Trial:
    """
    Top-level container for a trial simulation specification.

    ============================================================================
    ARCHITECTURAL GUARANTEE: This is a DECLARATIVE SPECIFICATION, not an
    executable or analytical object.
    ============================================================================

    A Trial is:
    - A pure data structure defining trial design
    - A serializable configuration for the simulation engine
    - A specification that can be versioned, diffed, and recalibrated

    A Trial is NOT:
    - An executable simulation (no run(), simulate(), execute() methods)
    - An analytical tool (no analyze(), compute_metrics(), predict() methods)
    - A stateful object (no current_enrollment, elapsed_time, active_sites)
    - A business logic container (no enroll_patient(), activate_site(), allocate_resource())

    The simulation engine interprets this specification to perform Monte Carlo runs.
    The Trial itself remains unchanged during simulation - it is read-only input.

    Deterministic fields:
    - trial_id: Unique identifier
    - target_enrollment: Enrollment goal (when to stop)
    - sites: List of Site objects
    - activities: List of Activity objects (optional, empty if no activities modeled)
    - resources: List of Resource objects (optional, empty if no resources modeled)
    - patient_flow: PatientFlow object defining enrollment/treatment/dropout logic

    Stochastic fields:
    - None at trial level (all uncertainty is in component entities)

    Rationale:
    - trial_id is deterministic: trial identifier is known
    - target_enrollment is deterministic: the GOAL is known, even though achievement is uncertain
    - sites/activities/resources are deterministic: the SET of entities is known, but their behavior is stochastic
    - patient_flow is deterministic structure with stochastic transitions
    - Trial is just a container - it holds the trial design but has no uncertainty of its own
    """
    trial_id: str
    target_enrollment: int
    sites: List[Site]
    patient_flow: PatientFlow
    activities: List[Activity] = field(default_factory=list)
    resources: List[Resource] = field(default_factory=list)

    def __post_init__(self):
        """Validate fields at construction time."""
        if not self.trial_id:
            raise ValueError("trial_id cannot be empty")

        if self.target_enrollment <= 0:
            raise ValueError(f"target_enrollment must be > 0, got {self.target_enrollment}")

        if not isinstance(self.sites, list) or len(self.sites) == 0:
            raise ValueError("sites must be a non-empty list")

        # Validate all sites are Site objects
        for i, site in enumerate(self.sites):
            if not isinstance(site, Site):
                raise TypeError(f"sites[{i}] must be Site, got {type(site).__name__}")

        # Validate unique site IDs
        site_ids = [s.site_id for s in self.sites]
        if len(site_ids) != len(set(site_ids)):
            duplicates = [sid for sid in site_ids if site_ids.count(sid) > 1]
            raise ValueError(f"Duplicate site_ids found: {set(duplicates)}")

        if not isinstance(self.patient_flow, PatientFlow):
            raise TypeError(
                f"patient_flow must be PatientFlow, got {type(self.patient_flow).__name__}"
            )

        # Validate activities
        if not isinstance(self.activities, list):
            raise TypeError(f"activities must be list, got {type(self.activities).__name__}")

        for i, activity in enumerate(self.activities):
            if not isinstance(activity, Activity):
                raise TypeError(f"activities[{i}] must be Activity, got {type(activity).__name__}")

        # Validate unique activity IDs
        if self.activities:
            activity_ids = [a.activity_id for a in self.activities]
            if len(activity_ids) != len(set(activity_ids)):
                duplicates = [aid for aid in activity_ids if activity_ids.count(aid) > 1]
                raise ValueError(f"Duplicate activity_ids found: {set(duplicates)}")

            # Validate activity dependencies reference existing activities
            all_activity_ids = set(activity_ids)
            for activity in self.activities:
                invalid_deps = activity.dependencies - all_activity_ids
                if invalid_deps:
                    raise ValueError(
                        f"Activity {activity.activity_id} has invalid dependencies: {invalid_deps}"
                    )

        # Validate resources
        if not isinstance(self.resources, list):
            raise TypeError(f"resources must be list, got {type(self.resources).__name__}")

        for i, resource in enumerate(self.resources):
            if not isinstance(resource, Resource):
                raise TypeError(f"resources[{i}] must be Resource, got {type(resource).__name__}")

        # Validate unique resource IDs
        resource_ids = [r.resource_id for r in self.resources]
        if self.resources and len(resource_ids) != len(set(resource_ids)):
            duplicates = [rid for rid in resource_ids if resource_ids.count(rid) > 1]
            raise ValueError(f"Duplicate resource_ids found: {set(duplicates)}")

        # Validate activity resource requirements reference existing resources
        all_resource_ids = set(resource_ids)
        for activity in self.activities:
            invalid_resources = activity.required_resources - all_resource_ids
            if invalid_resources:
                raise ValueError(
                    f"Activity {activity.activity_id} requires non-existent resources: {invalid_resources}"
                )

    def to_dict(self) -> Dict:
        """Serialize to dict for JSON export."""
        return {
            "type": "Trial",
            "trial_id": self.trial_id,
            "target_enrollment": self.target_enrollment,
            "sites": [s.to_dict() for s in self.sites],
            "patient_flow": self.patient_flow.to_dict(),
            "activities": [a.to_dict() for a in self.activities],
            "resources": [r.to_dict() for r in self.resources]
        }
