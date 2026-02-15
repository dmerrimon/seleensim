"""
Deterministic Monte Carlo simulation engine.

Design Principles:
- Deterministic: Same seed → identical results
- Forward propagation: Events processed in time order
- No optimization: Pure simulation of trial dynamics
- Clarity over performance: Readable implementation
- Separation: Single run results vs aggregated statistics

Single Run vs Aggregated:
- Single run: ONE realization showing HOW events unfold (causality, timeline)
- Aggregated: DISTRIBUTION of outcomes showing RANGE of possibilities (risk, uncertainty)
- Both needed: Single runs for debugging/understanding, aggregated for planning/decisions
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict
import heapq
import hashlib
import numpy as np

from seleensim.constraints import (
    Constraint,
    ConstraintResult,
    compose_constraint_results
)


@dataclass
class Event:
    """
    Simulation event to be processed at specific time.

    Events are processed in time order. Each event may generate downstream events.

    Attributes:
        event_id: Unique identifier
        event_type: Type of event (e.g., "site_activation", "enrollment")
        entity_id: ID of entity this event affects
        time: Absolute simulation time when event occurs
        duration: How long event takes (for activities)
        execution_parameters: Cached throttling/modifications (idempotent)
        required_resources: Resources needed for this event
        predecessors: Event IDs that must complete before this
        metadata: Additional event-specific data
    """
    event_id: str
    event_type: str
    entity_id: str
    time: float
    duration: float = 0.0
    execution_parameters: Dict[str, Any] = field(default_factory=dict)
    required_resources: Set[str] = field(default_factory=set)
    predecessors: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other):
        """Priority queue comparison (earlier time = higher priority)."""
        return self.time < other.time

    def reschedule(self, new_time: float) -> "Event":
        """Create rescheduled copy of event (immutable pattern)."""
        return Event(
            event_id=self.event_id,
            event_type=self.event_type,
            entity_id=self.entity_id,
            time=new_time,
            duration=self.duration,
            execution_parameters=self.execution_parameters.copy(),
            required_resources=self.required_resources.copy(),
            predecessors=self.predecessors.copy(),
            metadata=self.metadata.copy()
        )

    def apply_overrides(self, overrides: Dict[str, Any]):
        """Apply parameter overrides (throttling)."""
        for key, value in overrides.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                self.metadata[key] = value


class SimulationState:
    """
    Tracks current state of simulation run.

    Maintains:
    - Current simulation time
    - Event completions (for constraint evaluation)
    - Resource allocations and availability
    - Budget spent
    - Timeline of events

    Pure data structure - no business logic.
    """

    def __init__(self, initial_budget: float = float('inf')):
        self.current_time: float = 0.0
        self.budget_spent: float = 0.0
        self.budget_available: float = initial_budget

        # Event completions: (event_type, entity_id) -> completion_time
        self._completion_times: Dict[tuple, float] = {}

        # Activity completions: activity_id -> completion_time
        self._activity_completions: Dict[str, float] = {}

        # Resource allocations: resource_id -> [(start_time, end_time, event_id), ...]
        self._resource_allocations: Dict[str, List[tuple]] = defaultdict(list)

        # Timeline: list of (time, event_type, entity_id, description)
        self.timeline: List[tuple] = []

        # Metrics tracking
        self.metrics: Dict[str, Any] = {
            "events_processed": 0,
            "events_rescheduled": 0,
            "constraint_violations": 0
        }

    def record_completion(self, event: Event):
        """Record event completion."""
        self._completion_times[(event.event_type, event.entity_id)] = self.current_time

        # Also track as activity if applicable
        if hasattr(event, 'activity_id'):
            activity_id = getattr(event, 'activity_id', event.event_id)
            self._activity_completions[activity_id] = self.current_time

        # Add to timeline
        self.timeline.append((
            self.current_time,
            event.event_type,
            event.entity_id,
            f"{event.event_type} completed"
        ))

        self.metrics["events_processed"] += 1

    def get_completion_time(self, event_type: str, entity_id: str) -> Optional[float]:
        """Get completion time for event type + entity."""
        return self._completion_times.get((event_type, entity_id))

    def get_activity_completion_time(self, activity_id: str) -> Optional[float]:
        """Get completion time for activity."""
        return self._activity_completions.get(activity_id)

    def allocate_resource(self, resource_id: str, start_time: float, end_time: float, event_id: str):
        """Allocate resource for time period."""
        self._resource_allocations[resource_id].append((start_time, end_time, event_id))

    def get_resource_availability(self, resource_id: str, requested_time: float) -> Optional[float]:
        """
        Get next time when resource becomes available.

        Returns:
            None if available immediately at requested_time
            float (future time) if resource busy
        """
        allocations = self._resource_allocations.get(resource_id, [])

        # Check if any allocation overlaps with requested_time
        for start, end, _ in allocations:
            if start <= requested_time < end:
                # Resource busy, find earliest end time after requested_time
                future_allocations = [end for s, e, _ in allocations if s <= requested_time < e]
                return max(future_allocations) if future_allocations else None

        # Available immediately
        return None

    def spend_budget(self, amount: float):
        """Spend budget."""
        self.budget_spent += amount
        self.budget_available -= amount

    def get_available_budget(self, time: float) -> float:
        """Get available budget at time (for throttling constraints)."""
        return self.budget_available


@dataclass
class RunResult:
    """
    Result of a single simulation run.

    Captures:
    - Run identity (seed)
    - Timeline of events
    - Final metrics (time, cost, etc.)
    - Constraint violations
    - Resource utilization

    This is ONE realization showing HOW the trial unfolded.
    """
    run_id: int
    seed: int
    completion_time: float
    total_cost: float
    timeline: List[tuple]
    metrics: Dict[str, Any]

    # Additional tracking
    events_processed: int
    events_rescheduled: int
    constraint_violations: int

    def summary(self) -> str:
        """Human-readable summary of this run."""
        return (
            f"Run #{self.run_id} (seed={self.seed}):\n"
            f"  Completion time: {self.completion_time:.1f} days\n"
            f"  Total cost: ${self.total_cost:,.0f}\n"
            f"  Events processed: {self.events_processed}\n"
            f"  Events rescheduled: {self.events_rescheduled}\n"
            f"  Constraint violations: {self.constraint_violations}"
        )


@dataclass
class SimulationResults:
    """
    Aggregated results across N simulation runs.

    Captures:
    - All individual run results (for inspection)
    - Aggregated statistics (P10/P50/P90)
    - Summary metrics

    This shows the DISTRIBUTION of outcomes across uncertainty space.
    """
    num_runs: int
    master_seed: int
    run_results: List[RunResult]

    # Aggregated statistics
    completion_time_p10: float
    completion_time_p50: float
    completion_time_p90: float

    total_cost_p10: float
    total_cost_p50: float
    total_cost_p90: float

    mean_events_processed: float
    mean_events_rescheduled: float

    def summary(self) -> str:
        """Human-readable summary of aggregated results."""
        return (
            f"Simulation Results ({self.num_runs} runs, seed={self.master_seed}):\n"
            f"\n"
            f"Completion Time:\n"
            f"  P10: {self.completion_time_p10:.1f} days (optimistic)\n"
            f"  P50: {self.completion_time_p50:.1f} days (median)\n"
            f"  P90: {self.completion_time_p90:.1f} days (pessimistic)\n"
            f"\n"
            f"Total Cost:\n"
            f"  P10: ${self.total_cost_p10:,.0f}\n"
            f"  P50: ${self.total_cost_p50:,.0f}\n"
            f"  P90: ${self.total_cost_p90:,.0f}\n"
            f"\n"
            f"Average Events:\n"
            f"  Processed: {self.mean_events_processed:.1f}\n"
            f"  Rescheduled: {self.mean_events_rescheduled:.1f}"
        )

    def get_run(self, run_id: int) -> Optional[RunResult]:
        """Get specific run result for inspection."""
        for run in self.run_results:
            if run.run_id == run_id:
                return run
        return None


class SimulationEngine:
    """
    Deterministic Monte Carlo simulation engine.

    Orchestrates:
    - N independent simulation runs
    - Deterministic seeding (same master seed → identical results)
    - Event processing with constraint evaluation
    - State tracking and timeline generation
    - Result aggregation

    Design:
    - Each run is independent (no shared mutable state)
    - Forward time propagation (events processed in time order)
    - Constraint-driven scheduling (validity gates, feasibility delays)
    - No optimization or learning
    """

    def __init__(self, master_seed: int = 42, constraints: Optional[List[Constraint]] = None):
        """
        Initialize simulation engine.

        Args:
            master_seed: Master random seed for deterministic execution
                        Each run gets seed: master_seed + run_id
            constraints: List of constraints to evaluate during simulation
                        If None, no constraint evaluation performed (MVP mode)
        """
        self.master_seed = master_seed
        self.constraints = constraints or []

    def run(self, trial_spec: Any, num_runs: int = 100, initial_budget: float = float('inf')) -> SimulationResults:
        """
        Execute N Monte Carlo simulation runs.

        Args:
            trial_spec: Trial specification (Trial entity)
            num_runs: Number of simulation runs
            initial_budget: Starting budget for each run

        Returns:
            SimulationResults with individual runs and aggregated statistics
        """
        print(f"Starting {num_runs} simulation runs (master_seed={self.master_seed})...")

        # Run N independent simulations
        run_results = []
        for run_id in range(num_runs):
            run_seed = self.master_seed + run_id
            result = self._execute_single_run(trial_spec, run_id, run_seed, initial_budget)
            run_results.append(result)

            if (run_id + 1) % 10 == 0:
                print(f"  Completed {run_id + 1}/{num_runs} runs...")

        print(f"All runs complete. Aggregating results...")

        # Aggregate statistics
        completion_times = [r.completion_time for r in run_results]
        total_costs = [r.total_cost for r in run_results]

        results = SimulationResults(
            num_runs=num_runs,
            master_seed=self.master_seed,
            run_results=run_results,
            completion_time_p10=float(np.percentile(completion_times, 10)),
            completion_time_p50=float(np.percentile(completion_times, 50)),
            completion_time_p90=float(np.percentile(completion_times, 90)),
            total_cost_p10=float(np.percentile(total_costs, 10)),
            total_cost_p50=float(np.percentile(total_costs, 50)),
            total_cost_p90=float(np.percentile(total_costs, 90)),
            mean_events_processed=float(np.mean([r.events_processed for r in run_results])),
            mean_events_rescheduled=float(np.mean([r.events_rescheduled for r in run_results]))
        )

        return results

    def _execute_single_run(
        self,
        trial_spec: Any,
        run_id: int,
        run_seed: int,
        initial_budget: float
    ) -> RunResult:
        """
        Execute one simulation run.

        Process:
        1. Initialize state and event queue
        2. Generate initial events from trial spec
        3. Process events in time order
        4. Apply constraints
        5. Update state
        6. Generate downstream events
        7. Return RunResult

        Args:
            trial_spec: Trial specification
            run_id: Run identifier
            run_seed: Random seed for this run
            initial_budget: Starting budget

        Returns:
            RunResult capturing timeline and metrics
        """
        # Initialize state
        state = SimulationState(initial_budget=initial_budget)

        # Initialize event queue (priority queue by time)
        event_queue = []

        # Generate initial events from trial specification
        # For MVP: Simple site activation events
        self._generate_initial_events(trial_spec, run_seed, event_queue)

        # Process events until queue empty or time limit reached
        max_time = 10000  # Safety limit
        while event_queue and state.current_time < max_time:
            # Pop next event (earliest time)
            event = heapq.heappop(event_queue)

            # Advance simulation time
            state.current_time = event.time

            # Process event (with constraint evaluation, etc.)
            self._process_event(event, state, event_queue)

        # Create run result
        result = RunResult(
            run_id=run_id,
            seed=run_seed,
            completion_time=state.current_time,
            total_cost=state.budget_spent,
            timeline=state.timeline,
            metrics=state.metrics.copy(),
            events_processed=state.metrics["events_processed"],
            events_rescheduled=state.metrics["events_rescheduled"],
            constraint_violations=state.metrics["constraint_violations"]
        )

        return result

    def _generate_initial_events(self, trial_spec: Any, run_seed: int, event_queue: List[Event]):
        """
        Generate initial simulation events from trial specification.

        For MVP: Generate site activation events with stochastic timing.

        Args:
            trial_spec: Trial specification
            run_seed: Random seed for deterministic sampling
            event_queue: Event queue to populate
        """
        # Sample site activation times using deterministic seeds
        for idx, site in enumerate(trial_spec.sites):
            # Deterministic per-event seed
            event_seed = self._generate_event_seed(run_seed, f"site_activation_{site.site_id}")

            # Sample activation time from distribution
            activation_time = site.activation_time.sample(event_seed)

            # Create activation event
            event = Event(
                event_id=f"activation_{site.site_id}",
                event_type="site_activation",
                entity_id=site.site_id,
                time=activation_time,
                duration=0.0,
                metadata={"site": site}
            )

            heapq.heappush(event_queue, event)

    def _process_event(self, event: Event, state: SimulationState, event_queue: List[Event]):
        """
        Process single event following canonical orchestration loop.

        Implements the event processing loop from ENGINE_ORCHESTRATION.md:
        1. Evaluate all applicable constraints
        2. Compose results (AND, MAX, MERGE)
        3. Compute new event time (validity + feasibility)
        4. Reschedule if needed, else execute
        5. Generate downstream events
        6. Update state

        Args:
            event: Event to process
            state: Current simulation state
            event_queue: Event queue for downstream events
        """
        # Step 1: Evaluate all applicable constraints
        if self.constraints:
            constraint_results = []
            for constraint in self.constraints:
                result = constraint.evaluate(state, event)
                constraint_results.append(result)

            # Step 2: Compose results
            combined = compose_constraint_results(constraint_results)

            # Step 3: Aggregate effects
            earliest_valid_time = combined.earliest_valid_time
            delay = combined.delay
            parameter_overrides = combined.parameter_overrides

            # Step 4: Compute new event time
            if earliest_valid_time is not None:
                # Validity constraint violated
                new_time = earliest_valid_time
            else:
                # Valid, but may have feasibility delay
                new_time = event.time + delay

            # Step 5: Decision logic
            if new_time > event.time:
                # Event must be rescheduled
                event_rescheduled = event.reschedule(new_time)
                heapq.heappush(event_queue, event_rescheduled)

                # Track rescheduling
                state.metrics["events_rescheduled"] += 1

                # Log reschedule to timeline
                state.timeline.append((
                    state.current_time,
                    f"{event.event_type}_rescheduled",
                    event.entity_id,
                    f"Rescheduled to {new_time:.1f}: {combined.explanation}"
                ))

                # Track constraint violations if validity failed
                if earliest_valid_time is not None:
                    state.metrics["constraint_violations"] += 1

                return  # Do NOT execute

            # Step 6: Apply parameter modifications
            if parameter_overrides:
                event.apply_overrides(parameter_overrides)

                # Log modifications to timeline
                state.timeline.append((
                    state.current_time,
                    f"{event.event_type}_modified",
                    event.entity_id,
                    f"Parameters modified: {combined.explanation}"
                ))

        # Step 7: Execute event (record completion)
        state.record_completion(event)

        # Step 8: Generate downstream events based on event type
        if event.event_type == "site_activation":
            # Site activated → can now enroll patients
            # For MVP: No downstream events yet (enrollment not implemented)
            pass

        # Step 9: Update state (already done in record_completion)

    def _generate_event_seed(self, run_seed: int, event_id: str) -> int:
        """
        Generate deterministic seed for specific event.

        Uses hash of run_seed + event_id to ensure:
        - Same run_seed + event_id → same event_seed
        - Different event_ids → independent seeds

        Args:
            run_seed: Seed for this run
            event_id: Unique event identifier

        Returns:
            Deterministic integer seed for this event
        """
        # Combine run_seed and event_id deterministically
        combined = f"{run_seed}:{event_id}"
        hash_bytes = hashlib.sha256(combined.encode()).digest()
        # Convert first 4 bytes to integer
        seed = int.from_bytes(hash_bytes[:4], byteorder='big')
        return seed


def aggregate_statistics(values: List[float], percentiles: List[int] = [10, 50, 90]) -> Dict[int, float]:
    """
    Compute percentile statistics from list of values.

    Args:
        values: List of numeric values (e.g., completion times across runs)
        percentiles: Percentiles to compute (default P10, P50, P90)

    Returns:
        Dict mapping percentile -> value

    Example:
        completion_times = [250, 275, 290, 310, 350]
        stats = aggregate_statistics(completion_times)
        # {10: 255.0, 50: 290.0, 90: 342.0}
    """
    return {p: float(np.percentile(values, p)) for p in percentiles}
