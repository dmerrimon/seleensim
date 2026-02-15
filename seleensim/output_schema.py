"""
Simulation output schema for traceability and defensibility.

Design Principles:
- All outputs reference inputs that influenced them
- Support percentile-based results
- Enable variance attribution (future)
- Pure structured data (no UI logic)
- Deterministic and reproducible

Key Guarantee: Outputs are defensible evidence, not just numbers.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import sys
import platform
import socket


@dataclass
class ProvenanceRecord:
    """
    Execution context for reproducibility and audit.

    Answers: "How was this simulation produced?"

    Contains everything needed to reproduce results exactly.
    """
    # Execution identity
    simulation_id: str  # Unique ID for this simulation run
    execution_timestamp: str  # ISO 8601: "2026-02-14T10:30:00Z"

    # Software versions
    seleensim_version: str  # "0.1.0"
    python_version: str  # "3.13.7"

    # Configuration
    num_runs: int  # 100
    master_seed: int  # 42
    initial_budget: float  # inf

    # Runtime
    execution_duration_seconds: float  # 2.34

    # Environment (optional, for audit trails)
    hostname: Optional[str] = None
    user: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON."""
        return asdict(self)

    @staticmethod
    def create(
        simulation_id: str,
        num_runs: int,
        master_seed: int,
        initial_budget: float,
        execution_duration_seconds: float,
        seleensim_version: str = "0.1.0",
        include_environment: bool = False
    ) -> "ProvenanceRecord":
        """
        Factory method to create provenance record.

        Args:
            simulation_id: Unique identifier
            num_runs: Number of simulation runs
            master_seed: Random seed used
            initial_budget: Starting budget
            execution_duration_seconds: Runtime
            seleensim_version: Software version
            include_environment: Whether to capture hostname/user

        Returns:
            ProvenanceRecord with captured metadata
        """
        hostname = None
        user = None

        if include_environment:
            try:
                hostname = socket.gethostname()
            except:
                hostname = "unknown"

            try:
                import os
                user = os.getenv("USER") or os.getenv("USERNAME") or "unknown"
            except:
                user = "unknown"

        return ProvenanceRecord(
            simulation_id=simulation_id,
            execution_timestamp=datetime.now().isoformat(),
            seleensim_version=seleensim_version,
            python_version=platform.python_version(),
            num_runs=num_runs,
            master_seed=master_seed,
            initial_budget=initial_budget,
            execution_duration_seconds=execution_duration_seconds,
            hostname=hostname,
            user=user
        )


@dataclass
class PercentileDistribution:
    """
    Standard statistical summary with percentiles.

    Used for completion times, costs, and other outcomes.
    """
    p10: float
    p25: float
    p50: float  # Median
    p75: float
    p90: float
    p95: float
    mean: float
    std: float
    min: float
    max: float

    def range_p10_p90(self) -> float:
        """Variability measure: P90 - P10."""
        return self.p90 - self.p10

    def range_p25_p75(self) -> float:
        """Interquartile range: P75 - P25."""
        return self.p75 - self.p25

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON."""
        return asdict(self)

    @staticmethod
    def from_values(values: List[float]) -> "PercentileDistribution":
        """
        Compute percentile distribution from list of values.

        Args:
            values: List of outcomes (e.g., completion times across runs)

        Returns:
            PercentileDistribution with computed statistics
        """
        import numpy as np

        return PercentileDistribution(
            p10=float(np.percentile(values, 10)),
            p25=float(np.percentile(values, 25)),
            p50=float(np.percentile(values, 50)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            mean=float(np.mean(values)),
            std=float(np.std(values)),
            min=float(np.min(values)),
            max=float(np.max(values))
        )


@dataclass
class InputSpecification:
    """
    Snapshot of all inputs that influenced simulation.

    Answers: "What assumptions produced these results?"

    Enables full traceability from outputs back to inputs.
    """
    # Trial specification
    trial_id: str
    trial_spec: Dict[str, Any]  # Trial.to_dict() snapshot

    # Scenario applied (if any)
    scenario_id: Optional[str] = None
    scenario_profile: Optional[Dict[str, Any]] = None  # ScenarioProfile.to_dict()

    # Constraints used
    constraints: List[str] = field(default_factory=list)  # Constraint class names

    # Distribution summary (for quick reference)
    distribution_summary: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # {
    #     "SITE_001.activation_time": {"type": "Triangular", "low": 30, "mode": 45, "high": 90},
    #     "SITE_001.enrollment_rate": {"type": "Gamma", "shape": 2, "scale": 1.5},
    #     ...
    # }

    # Deterministic parameters (for quick reference)
    deterministic_summary: Dict[str, Any] = field(default_factory=dict)
    # {
    #     "target_enrollment": 200,
    #     "num_sites": 3,
    #     ...
    # }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON."""
        return asdict(self)

    @staticmethod
    def from_trial(
        trial: Any,
        scenario: Optional[Any] = None,
        constraints: Optional[List[Any]] = None
    ) -> "InputSpecification":
        """
        Create input specification from trial entity.

        Args:
            trial: Trial entity
            scenario: Optional ScenarioProfile
            constraints: Optional list of constraints

        Returns:
            InputSpecification with extracted metadata
        """
        trial_dict = trial.to_dict()

        # Extract distribution summary (flatten params for easy access)
        dist_summary = {}
        for site in trial.sites:
            site_id = site.site_id

            # Flatten distribution to include type + params at top level
            activation_dict = site.activation_time.to_dict()
            dist_summary[f"{site_id}.activation_time"] = {
                "type": activation_dict["type"],
                **activation_dict["params"]  # Flatten params to top level
            }

            enrollment_dict = site.enrollment_rate.to_dict()
            dist_summary[f"{site_id}.enrollment_rate"] = {
                "type": enrollment_dict["type"],
                **enrollment_dict["params"]  # Flatten params to top level
            }

            dropout_dict = site.dropout_rate.to_dict()
            dist_summary[f"{site_id}.dropout_rate"] = {
                "type": dropout_dict["type"],
                **dropout_dict["params"]  # Flatten params to top level
            }

        # Extract deterministic summary
        det_summary = {
            "target_enrollment": trial.target_enrollment,
            "num_sites": len(trial.sites),
            "num_activities": len(trial.activities),
            "num_resources": len(trial.resources)
        }

        return InputSpecification(
            trial_id=trial.trial_id,
            trial_spec=trial_dict,
            scenario_id=scenario.scenario_id if scenario else None,
            scenario_profile=scenario.to_dict() if scenario else None,
            constraints=[c.__class__.__name__ for c in constraints] if constraints else [],
            distribution_summary=dist_summary,
            deterministic_summary=det_summary
        )


@dataclass
class EnhancedSimulationOutput:
    """
    Complete simulation output with full traceability.

    This is the top-level output structure.
    Contains everything needed to defend results and reproduce them.

    Enhances the basic SimulationResults with:
    - Provenance tracking
    - Input specification snapshot
    - Richer statistical summaries
    """
    # === Provenance ===
    provenance: ProvenanceRecord

    # === Input References ===
    input_specification: InputSpecification

    # === Results ===
    aggregated_results: "AggregatedResults"  # Enhanced with PercentileDistribution

    # === Raw Results (for detailed analysis) ===
    single_run_results: Optional[List[Dict[str, Any]]] = None  # Optional for large outputs

    def to_dict(self) -> Dict[str, Any]:
        """Serialize complete output to JSON."""
        return {
            "provenance": self.provenance.to_dict(),
            "input_specification": self.input_specification.to_dict(),
            "aggregated_results": self.aggregated_results.to_dict(),
            "single_run_results": self.single_run_results
        }

    def to_json(self, filepath: str, include_single_runs: bool = True):
        """
        Save output to JSON file.

        Args:
            filepath: Path to save JSON
            include_single_runs: Whether to include all run details
        """
        output_dict = self.to_dict()

        if not include_single_runs:
            output_dict["single_run_results"] = None

        with open(filepath, 'w') as f:
            json.dump(output_dict, f, indent=2)

    @staticmethod
    def from_json(filepath: str) -> "EnhancedSimulationOutput":
        """Load output from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)

        # Reconstruct objects
        provenance = ProvenanceRecord(**data["provenance"])
        input_spec = InputSpecification(**data["input_specification"])

        # Aggregated results
        agg_data = data["aggregated_results"]
        agg_results = AggregatedResults(
            num_runs=agg_data["num_runs"],
            completion_time=PercentileDistribution(**agg_data["completion_time"]),
            total_cost=PercentileDistribution(**agg_data["total_cost"]),
            events_processed=PercentileDistribution(**agg_data["events_processed"]),
            events_rescheduled=PercentileDistribution(**agg_data["events_rescheduled"]),
            constraint_violations=PercentileDistribution(**agg_data["constraint_violations"])
        )

        return EnhancedSimulationOutput(
            provenance=provenance,
            input_specification=input_spec,
            aggregated_results=agg_results,
            single_run_results=data.get("single_run_results")
        )


@dataclass
class AggregatedResults:
    """
    Statistical summary across N simulation runs.

    Answers: "What range of outcomes should we expect?"

    Uses PercentileDistribution for richer statistics.
    """
    # Sample size
    num_runs: int

    # Outcome distributions
    completion_time: PercentileDistribution  # Days
    total_cost: PercentileDistribution  # Dollars

    # Execution metrics
    events_processed: PercentileDistribution
    events_rescheduled: PercentileDistribution
    constraint_violations: PercentileDistribution

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON."""
        return {
            "num_runs": self.num_runs,
            "completion_time": self.completion_time.to_dict(),
            "total_cost": self.total_cost.to_dict(),
            "events_processed": self.events_processed.to_dict(),
            "events_rescheduled": self.events_rescheduled.to_dict(),
            "constraint_violations": self.constraint_violations.to_dict()
        }

    def summary(self) -> str:
        """Human-readable summary for reporting."""
        return (
            f"Simulation Results ({self.num_runs} runs):\n"
            f"\n"
            f"Completion Time:\n"
            f"  P10: {self.completion_time.p10:.1f} days (optimistic)\n"
            f"  P50: {self.completion_time.p50:.1f} days (median)\n"
            f"  P90: {self.completion_time.p90:.1f} days (conservative)\n"
            f"  Variability (P10-P90): {self.completion_time.range_p10_p90():.1f} days\n"
            f"\n"
            f"Total Cost:\n"
            f"  P10: ${self.total_cost.p10:,.0f}\n"
            f"  P50: ${self.total_cost.p50:,.0f}\n"
            f"  P90: ${self.total_cost.p90:,.0f}\n"
            f"\n"
            f"Execution Metrics:\n"
            f"  Events processed (avg): {self.events_processed.mean:.1f}\n"
            f"  Events rescheduled (avg): {self.events_rescheduled.mean:.1f}\n"
            f"  Constraint violations (avg): {self.constraint_violations.mean:.1f}"
        )


def create_enhanced_output(
    simulation_id: str,
    trial: Any,
    scenario: Optional[Any],
    constraints: Optional[List[Any]],
    run_results: List[Any],
    master_seed: int,
    execution_duration: float
) -> EnhancedSimulationOutput:
    """
    Create enhanced simulation output from basic results.

    Args:
        simulation_id: Unique identifier
        trial: Trial entity
        scenario: Optional scenario profile
        constraints: Optional constraints
        run_results: List of RunResult objects
        master_seed: Random seed
        execution_duration: Runtime in seconds

    Returns:
        EnhancedSimulationOutput with full traceability
    """
    # Create provenance
    provenance = ProvenanceRecord.create(
        simulation_id=simulation_id,
        num_runs=len(run_results),
        master_seed=master_seed,
        initial_budget=float('inf'),
        execution_duration_seconds=execution_duration,
        include_environment=False
    )

    # Create input specification
    input_spec = InputSpecification.from_trial(trial, scenario, constraints)

    # Extract values for percentile computation
    completion_times = [r.completion_time for r in run_results]
    total_costs = [r.total_cost for r in run_results]
    events_processed = [r.events_processed for r in run_results]
    events_rescheduled = [r.events_rescheduled for r in run_results]
    violations = [r.constraint_violations for r in run_results]

    # Create aggregated results
    aggregated = AggregatedResults(
        num_runs=len(run_results),
        completion_time=PercentileDistribution.from_values(completion_times),
        total_cost=PercentileDistribution.from_values(total_costs),
        events_processed=PercentileDistribution.from_values(events_processed),
        events_rescheduled=PercentileDistribution.from_values(events_rescheduled),
        constraint_violations=PercentileDistribution.from_values(violations)
    )

    # Optionally include single run details
    single_runs = [
        {
            "run_id": r.run_id,
            "seed": r.seed,
            "completion_time": r.completion_time,
            "total_cost": r.total_cost,
            "events_processed": r.events_processed,
            "events_rescheduled": r.events_rescheduled,
            "constraint_violations": r.constraint_violations
        }
        for r in run_results
    ]

    return EnhancedSimulationOutput(
        provenance=provenance,
        input_specification=input_spec,
        aggregated_results=aggregated,
        single_run_results=single_runs
    )
