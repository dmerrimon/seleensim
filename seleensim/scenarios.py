"""
Scenario system for assumption overrides.

Design Principles:
- Scenarios are pure data (immutable, serializable)
- apply_scenario() is pure function (no mutation)
- Explicit overrides only (no implicit inheritance)
- Version control friendly
- Supports calibration workflow (base improves, scenarios remain relative)

Key Guarantee: Scenarios are pre-processing layer. Engine never sees them.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import json
import copy

from seleensim.entities import Site, Trial, PatientFlow, Activity, Resource
from seleensim.distributions import (
    Distribution,
    Triangular,
    LogNormal,
    Gamma,
    Bernoulli,
    from_dict as dist_from_dict
)


class OverrideType(Enum):
    """Explicit types of overrides supported."""

    DIRECT_VALUE = "direct_value"
    # Replace deterministic value: capacity=5 → capacity=3

    DISTRIBUTION_REPLACE = "distribution_replace"
    # Replace entire distribution: Triangular(30,45,90) → LogNormal(mean=50, cv=0.3)

    DISTRIBUTION_SCALE = "distribution_scale"
    # Scale distribution parameters: Triangular(30,45,90) → Triangular(36,54,108) [1.2x]

    DISTRIBUTION_SHIFT = "distribution_shift"
    # Shift distribution: Triangular(30,45,90) → Triangular(40,55,100) [+10]

    DISTRIBUTION_PARAM = "distribution_param"
    # Modify specific parameter: Triangular(low=30, ...) → Triangular(low=25, ...)


@dataclass(frozen=True)
class ScenarioProfile:
    """
    Declarative override profile for trial specifications.

    Architectural Guarantees:
    - Immutable (frozen dataclass)
    - No execution logic
    - JSON-serializable
    - Explicit overrides only (no implicit inheritance)
    - Inspectable (all changes visible)

    Overrides are organized by entity type and ID.

    Example:
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
            },
            activity_overrides={},
            resource_overrides={},
            flow_overrides={},
            trial_overrides={},
            created_at="2026-02-14T10:00:00Z"
        )
    """
    scenario_id: str
    description: str
    version: str

    # Explicit override maps: entity_id → field_name → override_spec
    site_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    activity_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    resource_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    flow_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    trial_overrides: Dict[str, Any] = field(default_factory=dict)

    # Metadata for tracking
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    based_on_scenario: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON for version control."""
        return {
            "scenario_id": self.scenario_id,
            "description": self.description,
            "version": self.version,
            "site_overrides": self.site_overrides,
            "activity_overrides": self.activity_overrides,
            "resource_overrides": self.resource_overrides,
            "flow_overrides": self.flow_overrides,
            "trial_overrides": self.trial_overrides,
            "created_at": self.created_at,
            "based_on_scenario": self.based_on_scenario
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ScenarioProfile":
        """Deserialize from JSON."""
        return ScenarioProfile(
            scenario_id=data["scenario_id"],
            description=data["description"],
            version=data["version"],
            site_overrides=data.get("site_overrides", {}),
            activity_overrides=data.get("activity_overrides", {}),
            resource_overrides=data.get("resource_overrides", {}),
            flow_overrides=data.get("flow_overrides", {}),
            trial_overrides=data.get("trial_overrides", {}),
            created_at=data.get("created_at", datetime.now().isoformat()),
            based_on_scenario=data.get("based_on_scenario")
        )


def apply_scenario(base_trial: Trial, scenario: ScenarioProfile) -> Trial:
    """
    Apply scenario overrides to base trial specification.

    Pure function:
    - Does NOT mutate base_trial
    - Returns NEW Trial with overrides applied
    - Deterministic: same inputs → same output
    - No side effects

    Args:
        base_trial: Immutable base specification
        scenario: Explicit override profile

    Returns:
        New Trial specification with overrides applied

    Example:
        base = Trial(...)
        scenario = ScenarioProfile(
            scenario_id="DELAYED_ACTIVATION",
            site_overrides={"SITE_001": {"activation_time": {...}}}
        )

        modified = apply_scenario(base, scenario)

        # base is unchanged
        assert base.sites[0].activation_time == original_dist

        # modified has overrides
        assert modified.sites[0].activation_time == scaled_dist
    """
    # Apply overrides by constructing new entities
    modified_sites = _apply_site_overrides(base_trial.sites, scenario.site_overrides)
    modified_activities = _apply_activity_overrides(base_trial.activities, scenario.activity_overrides)
    modified_resources = _apply_resource_overrides(base_trial.resources, scenario.resource_overrides)
    modified_flow = _apply_flow_overrides(base_trial.patient_flow, scenario.flow_overrides)

    # Apply trial-level overrides
    target_enrollment = _apply_direct_override(
        base_trial.target_enrollment,
        scenario.trial_overrides.get("target_enrollment")
    )

    # Construct new Trial (immutable)
    modified_trial = Trial(
        trial_id=f"{base_trial.trial_id}__{scenario.scenario_id}",
        target_enrollment=target_enrollment,
        sites=modified_sites,
        patient_flow=modified_flow,
        activities=modified_activities,
        resources=modified_resources
    )

    return modified_trial


def _apply_site_overrides(
    base_sites: List[Site],
    overrides: Dict[str, Dict[str, Any]]
) -> List[Site]:
    """Apply overrides to site list, returning new list."""
    if not overrides:
        return base_sites

    modified_sites = []
    for site in base_sites:
        if site.site_id in overrides:
            # Apply overrides to this site
            site_overrides = overrides[site.site_id]

            # Build kwargs for new Site
            kwargs = {
                "site_id": site.site_id,
                "activation_time": _apply_field_override(
                    site.activation_time,
                    site_overrides.get("activation_time")
                ),
                "enrollment_rate": _apply_field_override(
                    site.enrollment_rate,
                    site_overrides.get("enrollment_rate")
                ),
                "dropout_rate": _apply_field_override(
                    site.dropout_rate,
                    site_overrides.get("dropout_rate")
                ),
                "max_capacity": _apply_direct_override(
                    site.max_capacity,
                    site_overrides.get("max_capacity")
                )
            }

            modified_sites.append(Site(**kwargs))
        else:
            # No overrides for this site
            modified_sites.append(site)

    return modified_sites


def _apply_activity_overrides(
    base_activities: List[Activity],
    overrides: Dict[str, Dict[str, Any]]
) -> List[Activity]:
    """Apply overrides to activity list, returning new list."""
    if not overrides:
        return base_activities

    modified_activities = []
    for activity in base_activities:
        if activity.activity_id in overrides:
            activity_overrides = overrides[activity.activity_id]

            kwargs = {
                "activity_id": activity.activity_id,
                "duration": _apply_field_override(
                    activity.duration,
                    activity_overrides.get("duration")
                ),
                "dependencies": activity.dependencies,  # Sets are immutable in frozen dataclass
                "required_resources": activity.required_resources,
                "success_probability": _apply_field_override(
                    activity.success_probability,
                    activity_overrides.get("success_probability")
                ) if activity.success_probability else None
            }

            modified_activities.append(Activity(**kwargs))
        else:
            modified_activities.append(activity)

    return modified_activities


def _apply_resource_overrides(
    base_resources: List[Resource],
    overrides: Dict[str, Dict[str, Any]]
) -> List[Resource]:
    """Apply overrides to resource list, returning new list."""
    if not overrides:
        return base_resources

    modified_resources = []
    for resource in base_resources:
        if resource.resource_id in overrides:
            resource_overrides = overrides[resource.resource_id]

            kwargs = {
                "resource_id": resource.resource_id,
                "resource_type": resource.resource_type,
                "capacity": _apply_direct_override(
                    resource.capacity,
                    resource_overrides.get("capacity")
                ),
                "availability": _apply_field_override(
                    resource.availability,
                    resource_overrides.get("availability")
                ) if resource.availability else None,
                "utilization_rate": _apply_field_override(
                    resource.utilization_rate,
                    resource_overrides.get("utilization_rate")
                ) if resource.utilization_rate else None
            }

            modified_resources.append(Resource(**kwargs))
        else:
            modified_resources.append(resource)

    return modified_resources


def _apply_flow_overrides(
    base_flow: PatientFlow,
    overrides: Dict[str, Any]
) -> PatientFlow:
    """Apply overrides to patient flow, returning new flow."""
    if not overrides:
        return base_flow

    # For MVP, patient flow overrides are minimal
    # In future: could override transition_times, transition_probabilities
    return base_flow


def _apply_field_override(base_value: Any, override_spec: Optional[Dict[str, Any]]) -> Any:
    """
    Apply override to a field (typically a distribution).

    Args:
        base_value: Original value (Distribution or other)
        override_spec: Override specification with type and parameters

    Returns:
        Modified value or original if no override
    """
    if override_spec is None:
        return base_value

    override_type = OverrideType(override_spec["type"])

    if override_type == OverrideType.DIRECT_VALUE:
        return override_spec["value"]

    elif override_type == OverrideType.DISTRIBUTION_REPLACE:
        # Replace entire distribution
        dist_spec = override_spec["distribution"]
        return dist_from_dict(dist_spec)

    elif override_type == OverrideType.DISTRIBUTION_SCALE:
        # Scale distribution parameters
        scale_factor = override_spec["parameters"]["scale_factor"]
        return _scale_distribution(base_value, scale_factor)

    elif override_type == OverrideType.DISTRIBUTION_SHIFT:
        # Shift distribution
        shift_amount = override_spec["parameters"]["shift"]
        return _shift_distribution(base_value, shift_amount)

    elif override_type == OverrideType.DISTRIBUTION_PARAM:
        # Modify specific parameter
        param_overrides = override_spec["parameters"]
        return _modify_distribution_params(base_value, param_overrides)

    else:
        raise ValueError(f"Unknown override type: {override_type}")


def _apply_direct_override(base_value: Any, override_spec: Optional[Dict[str, Any]]) -> Any:
    """Apply override to direct value (non-distribution)."""
    if override_spec is None:
        return base_value

    override_type = OverrideType(override_spec["type"])

    if override_type == OverrideType.DIRECT_VALUE:
        return override_spec["value"]
    else:
        raise ValueError(f"Override type {override_type} not applicable to direct value")


def _scale_distribution(dist: Distribution, scale_factor: float) -> Distribution:
    """Scale distribution parameters by factor."""
    if isinstance(dist, Triangular):
        return Triangular(
            low=dist.low * scale_factor,
            mode=dist.mode * scale_factor,
            high=dist.high * scale_factor,
            bounds=dist.bounds
        )
    elif isinstance(dist, LogNormal):
        # Scale mean, keep cv
        return LogNormal(
            mean=dist.mean * scale_factor,
            cv=dist.cv,
            bounds=dist.bounds
        )
    elif isinstance(dist, Gamma):
        # Scale scale parameter, keep shape
        return Gamma(
            shape=dist.shape,
            scale=dist.scale * scale_factor,
            bounds=dist.bounds
        )
    elif isinstance(dist, Bernoulli):
        # Can't scale probability - return unchanged
        return dist
    else:
        raise ValueError(f"Cannot scale distribution type: {type(dist)}")


def _shift_distribution(dist: Distribution, shift: float) -> Distribution:
    """Shift distribution by additive amount."""
    if isinstance(dist, Triangular):
        return Triangular(
            low=dist.low + shift,
            mode=dist.mode + shift,
            high=dist.high + shift,
            bounds=dist.bounds
        )
    elif isinstance(dist, LogNormal):
        # Shift mean, keep cv
        return LogNormal(
            mean=dist.mean + shift,
            cv=dist.cv,
            bounds=dist.bounds
        )
    elif isinstance(dist, Gamma):
        # For Gamma, shifting is tricky - could use location parameter
        # For MVP, raise error
        raise ValueError("Shifting Gamma distributions not supported in MVP")
    elif isinstance(dist, Bernoulli):
        # Can't shift probability
        raise ValueError("Shifting Bernoulli distributions not supported")
    else:
        raise ValueError(f"Cannot shift distribution type: {type(dist)}")


def _modify_distribution_params(dist: Distribution, param_overrides: Dict[str, Any]) -> Distribution:
    """Modify specific distribution parameters."""
    if isinstance(dist, Triangular):
        return Triangular(
            low=param_overrides.get("low", dist.low),
            mode=param_overrides.get("mode", dist.mode),
            high=param_overrides.get("high", dist.high),
            bounds=dist.bounds
        )
    elif isinstance(dist, LogNormal):
        return LogNormal(
            mean=param_overrides.get("mean", dist.mean),
            cv=param_overrides.get("cv", dist.cv),
            bounds=dist.bounds
        )
    elif isinstance(dist, Gamma):
        return Gamma(
            shape=param_overrides.get("shape", dist.shape),
            scale=param_overrides.get("scale", dist.scale),
            bounds=dist.bounds
        )
    elif isinstance(dist, Bernoulli):
        return Bernoulli(
            p=param_overrides.get("p", dist.p)
        )
    else:
        raise ValueError(f"Cannot modify params for distribution type: {type(dist)}")


def compose_scenarios(
    base: ScenarioProfile,
    overlay: ScenarioProfile
) -> ScenarioProfile:
    """
    Explicitly compose two scenarios.

    NOT automatic inheritance. User must call this explicitly.
    Returns NEW scenario with merged overrides.

    Later overrides take precedence on conflicts.

    Args:
        base: Base scenario
        overlay: Overlay scenario (takes precedence)

    Returns:
        New scenario with merged overrides

    Example:
        delayed = ScenarioProfile(scenario_id="DELAYED", ...)
        reduced_capacity = ScenarioProfile(scenario_id="REDUCED_CAPACITY", ...)

        # User explicitly composes
        combined = compose_scenarios(delayed, reduced_capacity)

        # Result is inspectable
        print(combined.scenario_id)  # "DELAYED__AND__REDUCED_CAPACITY"
    """
    return ScenarioProfile(
        scenario_id=f"{base.scenario_id}__AND__{overlay.scenario_id}",
        description=f"{base.description} + {overlay.description}",
        version=f"{base.version}+{overlay.version}",
        site_overrides={**base.site_overrides, **overlay.site_overrides},
        activity_overrides={**base.activity_overrides, **overlay.activity_overrides},
        resource_overrides={**base.resource_overrides, **overlay.resource_overrides},
        flow_overrides={**base.flow_overrides, **overlay.flow_overrides},
        trial_overrides={**base.trial_overrides, **overlay.trial_overrides},
        created_at=datetime.now().isoformat(),
        based_on_scenario=base.scenario_id
    )


def diff_scenarios(
    scenario_a: ScenarioProfile,
    scenario_b: ScenarioProfile
) -> Dict[str, Any]:
    """
    Compare two scenarios and return differences.

    Returns:
        Dict with added/removed/modified overrides
    """
    return {
        "scenario_a": scenario_a.scenario_id,
        "scenario_b": scenario_b.scenario_id,
        "site_changes": _diff_dicts(scenario_a.site_overrides, scenario_b.site_overrides),
        "activity_changes": _diff_dicts(scenario_a.activity_overrides, scenario_b.activity_overrides),
        "resource_changes": _diff_dicts(scenario_a.resource_overrides, scenario_b.resource_overrides),
        "flow_changes": _diff_dicts(scenario_a.flow_overrides, scenario_b.flow_overrides),
        "trial_changes": _diff_dicts(scenario_a.trial_overrides, scenario_b.trial_overrides)
    }


def _diff_dicts(dict_a: Dict, dict_b: Dict) -> Dict[str, Any]:
    """Helper to diff two dicts."""
    all_keys = set(dict_a.keys()) | set(dict_b.keys())

    diff = {
        "only_in_a": [k for k in all_keys if k in dict_a and k not in dict_b],
        "only_in_b": [k for k in all_keys if k in dict_b and k not in dict_a],
        "modified": []
    }

    for key in all_keys:
        if key in dict_a and key in dict_b:
            if dict_a[key] != dict_b[key]:
                diff["modified"].append({
                    "key": key,
                    "value_a": dict_a[key],
                    "value_b": dict_b[key]
                })

    return diff
