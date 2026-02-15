"""
Constraint evaluation system for probabilistic simulation engine.

Design Principles:
1. Constraints are pure functions (evaluate state → return structured result)
2. Constraints are domain-agnostic (reason about time, resources, precedence)
3. Two-layer architecture: Validity (hard gates) vs Feasibility (soft modifiers)
4. Idempotent throttling via event execution_parameters
5. Extensible without refactoring engine

Validity vs Feasibility:
- Validity: "Can this event occur at all at time T?" → earliest_valid_time
- Feasibility: "How efficiently can this event occur?" → delay, parameter_overrides

Composition Rules (Sacred Engine Law):
- Delays compose via max(all delays)
- earliest_valid_time composes via max(all earliest_valid_times)
- Parameter overrides are merged
- Constraints never schedule events (engine does that)

Invariant: Constraints evaluate, engine orchestrates.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class ConstraintResult:
    """
    Result of evaluating a constraint against an event.

    Attributes:
        is_valid: Can this event occur at the proposed time? (hard gate)
        earliest_valid_time: Absolute time when event becomes valid (if not valid now)
        delay: Relative delay imposed beyond validity check (e.g., resource wait)
        parameter_overrides: Modifications to event parameters (e.g., throttled duration)
        explanation: Human-readable reason for constraint effect

    Composition:
        Engine computes: new_time = max(earliest_valid_time, proposed_time + delay)
        Multiple constraints → max delays, max earliest_valid_times, merged overrides

    Examples:
        # Validity constraint blocks event
        ConstraintResult(
            is_valid=False,
            earliest_valid_time=50.0,
            delay=0.0,
            parameter_overrides={},
            explanation="Site must activate before enrollment (activates at T=50)"
        )

        # Feasibility constraint delays event
        ConstraintResult(
            is_valid=True,
            earliest_valid_time=None,
            delay=10.0,
            parameter_overrides={},
            explanation="Resource MONITOR at capacity, available in 10 days"
        )

        # Feasibility constraint modifies parameters
        ConstraintResult(
            is_valid=True,
            earliest_valid_time=None,
            delay=0.0,
            parameter_overrides={"duration": 32.0},
            explanation="Budget limited to 60%, duration extended to 32 days"
        )
    """
    is_valid: bool
    earliest_valid_time: Optional[float]
    delay: float
    parameter_overrides: Dict[str, Any]
    explanation: str

    @staticmethod
    def satisfied(explanation: str = "Constraint satisfied") -> "ConstraintResult":
        """Factory for fully satisfied constraint (no effects)."""
        return ConstraintResult(
            is_valid=True,
            earliest_valid_time=None,
            delay=0.0,
            parameter_overrides={},
            explanation=explanation
        )

    @staticmethod
    def invalid_until(time: float, explanation: str) -> "ConstraintResult":
        """Factory for validity violation (hard gate)."""
        return ConstraintResult(
            is_valid=False,
            earliest_valid_time=time,
            delay=0.0,
            parameter_overrides={},
            explanation=explanation
        )

    @staticmethod
    def delayed_by(delay: float, explanation: str) -> "ConstraintResult":
        """Factory for feasibility delay (soft constraint)."""
        return ConstraintResult(
            is_valid=True,
            earliest_valid_time=None,
            delay=delay,
            parameter_overrides={},
            explanation=explanation
        )

    @staticmethod
    def modified(overrides: Dict[str, Any], explanation: str) -> "ConstraintResult":
        """Factory for parameter modification (throttling)."""
        return ConstraintResult(
            is_valid=True,
            earliest_valid_time=None,
            delay=0.0,
            parameter_overrides=overrides,
            explanation=explanation
        )


class Constraint(ABC):
    """
    Base class for all constraints.

    Constraints are pure functions: evaluate simulation state + proposed event,
    return ConstraintResult describing validity, delays, or modifications.

    Constraints DO NOT:
    - Mutate simulation state
    - Schedule events
    - Sample distributions
    - Store mutable state (except configuration)

    Constraints DO:
    - Read simulation state (current time, resource allocation, event history)
    - Evaluate event against rules
    - Return structured results with explanations
    """

    @abstractmethod
    def evaluate(self, state: Any, event: Any) -> ConstraintResult:
        """
        Evaluate constraint against proposed event in current simulation state.

        Args:
            state: Simulation state (current time, resources, event history, etc.)
            event: Proposed event to evaluate

        Returns:
            ConstraintResult describing validity, delays, modifications, explanation
        """
        pass


# =============================================================================
# Validity Constraints (Hard Gates)
# =============================================================================
# These answer: "Can this event occur at all at time T?"
# Output: is_valid, earliest_valid_time


class TemporalPrecedenceConstraint(Constraint):
    """
    Enforces that event B cannot occur before event A completes.

    Example: Enrollment cannot start before site activation completes.

    Validity Rule:
        Event B at time T is valid IFF predecessor A completes by time T.
        If A completes at T_a > T, then earliest_valid_time = T_a.

    Propagation:
        Delays in predecessor A cascade to all events that depend on it.
        This creates a critical path through temporal dependencies.
    """

    def __init__(self, predecessor_event_type: str, dependent_event_type: str):
        """
        Initialize temporal precedence constraint.

        Args:
            predecessor_event_type: Event type that must complete first
            dependent_event_type: Event type that depends on predecessor
        """
        self.predecessor_event_type = predecessor_event_type
        self.dependent_event_type = dependent_event_type

    def evaluate(self, state: Any, event: Any) -> ConstraintResult:
        """
        Check if predecessor has completed before dependent event.

        Args:
            state: Must have get_completion_time(event_type, entity_id) method
            event: Must have event_type, entity_id, time attributes

        Returns:
            ConstraintResult indicating validity and earliest valid time
        """
        # Only applies to dependent event type
        if event.event_type != self.dependent_event_type:
            return ConstraintResult.satisfied(f"Not applicable to {event.event_type}")

        # Check if predecessor completed
        predecessor_completion = state.get_completion_time(
            self.predecessor_event_type,
            event.entity_id
        )

        if predecessor_completion is None:
            # Predecessor not scheduled yet - invalid
            return ConstraintResult.invalid_until(
                time=float('inf'),  # Unknown when it will complete
                explanation=(
                    f"{self.dependent_event_type} requires {self.predecessor_event_type} "
                    f"for entity {event.entity_id}, but predecessor not scheduled"
                )
            )

        if predecessor_completion > event.time:
            # Predecessor completes after proposed event time - invalid
            return ConstraintResult.invalid_until(
                time=predecessor_completion,
                explanation=(
                    f"{self.dependent_event_type} cannot occur before "
                    f"{self.predecessor_event_type} completes "
                    f"(completes at T={predecessor_completion:.1f})"
                )
            )

        # Predecessor completed before event time - valid
        return ConstraintResult.satisfied(
            f"{self.predecessor_event_type} completed at T={predecessor_completion:.1f}"
        )


class PredecessorConstraint(Constraint):
    """
    Enforces activity dependency graph (DAG).

    Example: Site activation requires both IRB approval AND staff hiring.

    Validity Rule:
        Activity B at time T is valid IFF ALL predecessor activities have completed by T.
        earliest_valid_time = max(completion times of all predecessors)

    Propagation:
        Creates dependency chains and join points.
        Critical path = longest path through dependency graph.

    Note: Renamed from "DependencyConstraint" for clarity.
          "Predecessor" is unambiguous and DAG-friendly.
    """

    def evaluate(self, state: Any, event: Any) -> ConstraintResult:
        """
        Check if all predecessor activities have completed.

        Args:
            state: Must have get_activity_completion_time(activity_id) method
            event: Must have activity_id, predecessors, time attributes

        Returns:
            ConstraintResult indicating validity and earliest valid time
        """
        # Only applies to activities with predecessors
        if not hasattr(event, 'predecessors') or not event.predecessors:
            return ConstraintResult.satisfied("No predecessors to check")

        # Check completion time for all predecessors
        incomplete_predecessors = []
        predecessor_completions = []

        for pred_id in event.predecessors:
            pred_completion = state.get_activity_completion_time(pred_id)

            if pred_completion is None:
                # Predecessor not scheduled - invalid
                incomplete_predecessors.append(pred_id)
            else:
                predecessor_completions.append(pred_completion)

        if incomplete_predecessors:
            # Some predecessors not scheduled
            return ConstraintResult.invalid_until(
                time=float('inf'),
                explanation=(
                    f"Activity {event.activity_id} requires predecessors "
                    f"{incomplete_predecessors}, but they are not scheduled"
                )
            )

        # Find latest predecessor completion
        latest_completion = max(predecessor_completions) if predecessor_completions else event.time

        if latest_completion > event.time:
            # Some predecessor completes after proposed event time
            return ConstraintResult.invalid_until(
                time=latest_completion,
                explanation=(
                    f"Activity {event.activity_id} cannot start until all predecessors "
                    f"complete (latest completes at T={latest_completion:.1f})"
                )
            )

        # All predecessors completed before event time
        return ConstraintResult.satisfied(
            f"All predecessors completed by T={latest_completion:.1f}"
        )


# =============================================================================
# Feasibility Constraints (Soft Modifiers)
# =============================================================================
# These answer: "How efficiently can this event occur?"
# Output: delay, parameter_overrides


# =============================================================================
# Capacity Response Curves (ARCHITECTURAL FIX - Calibration Ready)
# =============================================================================

class CapacityResponseCurve(ABC):
    """
    Defines how work efficiency responds to resource utilization.

    ARCHITECTURAL PRINCIPLE:
    This separates STRUCTURE (resource tracking) from BEHAVIOR (how resource
    pressure affects work efficiency).

    The Ilana Law: "Could this number be different for another organization?"
    - Resource utilization threshold: YES → parameter
    - Efficiency degradation rate: YES → parameter
    - Max efficiency penalty: YES → parameter

    Example organizational differences:
    - Org A: 1 CRA per 5 sites → normal speed; 1 CRA per 10 sites → 2x slower
    - Org B: 1 CRA per 8 sites → normal speed; 1 CRA per 15 sites → 1.5x slower
    - Org C: Work efficiency unaffected by utilization (just queues if exceeded)

    Stochastic support (future):
    - Deterministic: Always same slowdown for given utilization
    - Stochastic: Same mean slowdown, but with variance (risk modeling)
    """

    @abstractmethod
    def sample_efficiency_multiplier(self, utilization_ratio: float, seed: int) -> float:
        """
        Sample work efficiency multiplier for given resource utilization.

        Args:
            utilization_ratio: current_load / capacity
                               1.0 = at capacity
                               1.5 = 150% utilization (overloaded)
                               0.5 = 50% utilization (underutilized)
            seed: Deterministic seed for stochastic curves

        Returns:
            efficiency_multiplier: How much work slows down
                                  1.0 = normal efficiency
                                  2.0 = work takes 2x as long
                                  0.5 = work is 2x faster (rare)

        Note: For deterministic curves, seed is ignored but kept for interface consistency.
        """
        pass

    @abstractmethod
    def mean_efficiency_multiplier(self, utilization_ratio: float) -> float:
        """
        Expected (mean) efficiency multiplier for given utilization.

        Used for:
        - Deterministic curves: Same as sampled value
        - Stochastic curves: Mean of distribution (variance captured in sample)

        Returns:
            mean_multiplier: Expected efficiency multiplier
        """
        pass


class NoCapacityDegradation(CapacityResponseCurve):
    """
    No efficiency degradation - work proceeds at normal speed regardless of utilization.

    Use when:
    - Resource is binary (available or not, no partial degradation)
    - Queueing model only (delay if unavailable, but no slowdown when available)
    - Conservative default (no assumptions about degradation)

    Example: Exclusive equipment access (MRI, lab, etc.) - either available or not.
    """

    def sample_efficiency_multiplier(self, utilization_ratio: float, seed: int) -> float:
        """Always 1.0 - no degradation."""
        return 1.0

    def mean_efficiency_multiplier(self, utilization_ratio: float) -> float:
        """Always 1.0 - no degradation."""
        return 1.0


class LinearCapacityDegradation(CapacityResponseCurve):
    """
    Linear efficiency degradation as utilization increases.

    Formula:
        efficiency_multiplier = 1.0 when utilization <= threshold
        efficiency_multiplier increases linearly from 1.0 to max_multiplier
                               as utilization goes from threshold to max_utilization

    Parameters (all calibratable):
        threshold: Utilization ratio where degradation starts
        max_multiplier: Maximum efficiency penalty (duration multiplier)
        max_utilization: Utilization ratio where max penalty occurs

    Example (conservative):
        threshold=0.8, max_multiplier=2.0, max_utilization=1.5
        - util=0.5 (50%) → 1.0x (no penalty)
        - util=0.8 (80%) → 1.0x (at threshold)
        - util=1.0 (100%) → 1.29x slower
        - util=1.5 (150%) → 2.0x slower (max penalty)

    Example (aggressive):
        threshold=1.0, max_multiplier=5.0, max_utilization=2.0
        - util=0.8 (80%) → 1.0x (below threshold)
        - util=1.0 (100%) → 1.0x (at threshold)
        - util=1.5 (150%) → 3.0x slower
        - util=2.0 (200%) → 5.0x slower (max penalty)
    """

    def __init__(
        self,
        threshold: float = 0.8,
        max_multiplier: float = 2.0,
        max_utilization: float = 1.5
    ):
        """
        Initialize linear capacity degradation curve.

        Args:
            threshold: Utilization ratio where degradation starts (0.0 to 1.0+)
            max_multiplier: Maximum efficiency penalty (1.0 = no penalty, 2.0 = 2x slower)
            max_utilization: Utilization ratio where max penalty occurs

        Raises:
            ValueError: If parameters are invalid
        """
        if threshold < 0.0:
            raise ValueError(f"threshold must be >= 0.0, got {threshold}")
        if max_multiplier < 1.0:
            raise ValueError(f"max_multiplier must be >= 1.0, got {max_multiplier}")
        if max_utilization <= threshold:
            raise ValueError(
                f"max_utilization ({max_utilization}) must be > threshold ({threshold})"
            )

        self.threshold = threshold
        self.max_multiplier = max_multiplier
        self.max_utilization = max_utilization

    def sample_efficiency_multiplier(self, utilization_ratio: float, seed: int) -> float:
        """Sample multiplier (deterministic - ignores seed)."""
        return self._compute_multiplier(utilization_ratio)

    def mean_efficiency_multiplier(self, utilization_ratio: float) -> float:
        """Mean multiplier (same as sampled for deterministic curve)."""
        return self._compute_multiplier(utilization_ratio)

    def _compute_multiplier(self, utilization_ratio: float) -> float:
        """Compute efficiency multiplier from utilization ratio."""
        # Below threshold: no degradation
        if utilization_ratio <= self.threshold:
            return 1.0

        # Above max_utilization: cap at max_multiplier
        if utilization_ratio >= self.max_utilization:
            return self.max_multiplier

        # Linear interpolation between threshold and max_utilization
        # progress: 0.0 at threshold, 1.0 at max_utilization
        progress = (utilization_ratio - self.threshold) / (
            self.max_utilization - self.threshold
        )

        # Interpolate from 1.0 to max_multiplier
        multiplier = 1.0 + (self.max_multiplier - 1.0) * progress

        return multiplier


class ResourceCapacityConstraint(Constraint):
    """
    Enforces resource capacity limits with optional efficiency degradation.

    ARCHITECTURAL FIX:
    - Resource utilization effects are now EXPLICIT (CapacityResponseCurve parameter)
    - Efficiency degradation is now CALIBRATABLE (change threshold/max_multiplier, not code)
    - Supports both QUEUEING (delay until free) and DEGRADATION (work slower when stretched)

    Example: Only 5 monitors available; 6th activity must wait (queueing).
             Or: 1 CRA for 8 sites → work 50% slower (degradation).

    Feasibility Rule:
        Activity requiring resource R at time T:
            1. Check if resource available (structural logic)
            2. If unavailable → delay until free (queueing)
            3. If available but stretched → work slower (degradation via response curve)

    Two modes of resource contention:
        1. Exclusive access (queueing): Resource busy → delay until free
        2. Shared/degradation: Resource stretched → work slower but proceed

    Propagation:
        - Queueing: Creates delays, serializes concurrent activities
        - Degradation: Increases duration, affects downstream timing
        - Combined: Both effects compound

    Note: This is a feasibility constraint (delays/modifies execution), not validity
          (unlike predecessors which gate whether event can occur at all).
    """

    def __init__(
        self,
        resource_id: str,
        capacity_response: CapacityResponseCurve = None
    ):
        """
        Initialize resource capacity constraint.

        Args:
            resource_id: Resource to monitor for capacity
            capacity_response: How resource utilization affects work efficiency.
                              None or NoCapacityDegradation = queueing only (default)
                              LinearCapacityDegradation = efficiency degrades when stretched

        Design note:
            Defaults to NoCapacityDegradation (backward compatible: queueing only).
            This preserves existing behavior while enabling calibration of degradation effects.
        """
        self.resource_id = resource_id
        self.capacity_response = capacity_response or NoCapacityDegradation()

    def evaluate(self, state: Any, event: Any) -> ConstraintResult:
        """
        Check if resource has sufficient capacity at event time.

        Current implementation: Queueing only (delays until resource free).
        Future enhancement: Apply efficiency degradation via capacity_response when
                           state supports get_resource_utilization().

        Args:
            state: Must have get_resource_availability(resource_id, time) method
            event: Must have required_resources, time, duration attributes

        Returns:
            ConstraintResult with delay if resource unavailable,
            or parameter override for duration if degradation applies
        """
        # Only applies to events requiring this resource
        if not hasattr(event, 'required_resources'):
            return ConstraintResult.satisfied("No resources required")

        if self.resource_id not in event.required_resources:
            return ConstraintResult.satisfied(f"Does not require {self.resource_id}")

        # Check resource availability at proposed time (queueing logic)
        available_time = state.get_resource_availability(self.resource_id, event.time)

        if available_time is None:
            # Resource available immediately
            # TODO: When state supports get_resource_utilization(), apply degradation here:
            #   utilization = state.get_resource_utilization(self.resource_id, event.time)
            #   if utilization > 0:
            #       multiplier = self.capacity_response.sample_efficiency_multiplier(
            #           utilization, seed
            #       )
            #       if multiplier > 1.0:
            #           return ConstraintResult.modified(
            #               overrides={"duration": event.duration * multiplier},
            #               explanation=f"{self.resource_id} at {utilization:.0%} utilization, "
            #                          f"work {multiplier:.1f}x slower"
            #           )
            return ConstraintResult.satisfied(f"{self.resource_id} available")

        if available_time <= event.time:
            # Resource becomes available before or at event time
            return ConstraintResult.satisfied(
                f"{self.resource_id} available at T={available_time:.1f}"
            )

        # Resource not available until later - impose delay
        delay = available_time - event.time
        return ConstraintResult.delayed_by(
            delay=delay,
            explanation=(
                f"Resource {self.resource_id} at capacity, "
                f"next available at T={available_time:.1f} "
                f"(delay of {delay:.1f})"
            )
        )


# =============================================================================
# Budget Response Curves (ARCHITECTURAL FIX - Calibration Ready)
# =============================================================================

class BudgetResponseCurve(ABC):
    """
    Defines how activity speed responds to budget availability.

    ARCHITECTURAL PRINCIPLE:
    This separates STRUCTURE (constraint exists) from BEHAVIOR (how budget affects speed).

    THE ILANA LAW APPLIED:
    "Could max slowdown be different for another organization?"
    YES → Therefore it's a parameter, not hardcoded.

    Stochastic Interface:
    - All curves implement sample_multiplier(budget_ratio, seed)
    - Deterministic curves ignore seed, return constant
    - Stochastic curves use seed for reproducible variance
    """

    @abstractmethod
    def sample_multiplier(self, budget_ratio: float, seed: int) -> float:
        """
        Sample duration multiplier from budget ratio.

        Args:
            budget_ratio: available_budget / required_budget (0.0 to 1.0+)
            seed: Random seed for reproducibility (ignored by deterministic curves)

        Returns:
            duration_multiplier: Factor to multiply base duration
                1.0 = baseline speed
                2.0 = half speed (50% slower)
                0.5 = double speed (100% faster)
        """
        pass

    @abstractmethod
    def mean_multiplier(self, budget_ratio: float) -> float:
        """Expected (mean) duration multiplier for given budget ratio."""
        pass


class LinearResponseCurve(BudgetResponseCurve):
    """
    Linear response: duration_multiplier = 1.0 / budget_ratio

    Deterministic (zero variance).

    Use when: Organization has predictable response to budget changes.
    """

    def __init__(self, min_speed_ratio: float = 0.5, max_speed_ratio: float = 1.0):
        """
        Initialize linear response curve.

        Args:
            min_speed_ratio: Minimum speed (0.5 = 50% speed = 2x duration max)
            max_speed_ratio: Maximum speed (1.0 = baseline, no acceleration)
        """
        if not 0 < min_speed_ratio <= 1.0:
            raise ValueError(f"min_speed_ratio must be in (0, 1.0], got {min_speed_ratio}")
        if max_speed_ratio < 1.0:
            raise ValueError(f"max_speed_ratio must be >= 1.0, got {max_speed_ratio}")

        self.min_speed_ratio = min_speed_ratio
        self.max_speed_ratio = max_speed_ratio

    def sample_multiplier(self, budget_ratio: float, seed: int) -> float:
        """Sample multiplier (deterministic - ignores seed)."""
        return self._compute_multiplier(budget_ratio)

    def mean_multiplier(self, budget_ratio: float) -> float:
        """Mean multiplier (same as sampled for deterministic curve)."""
        return self._compute_multiplier(budget_ratio)

    def _compute_multiplier(self, budget_ratio: float) -> float:
        """Compute duration multiplier from budget ratio."""
        # Clamp to prevent extreme values
        budget_ratio = max(0.0, min(2.0, budget_ratio))

        # Linear: speed proportional to budget
        speed_ratio = budget_ratio

        # Apply limits
        speed_ratio = max(self.min_speed_ratio, min(self.max_speed_ratio, speed_ratio))

        # Convert speed to duration multiplier
        return 1.0 / speed_ratio


class BudgetThrottlingConstraint(Constraint):
    """
    Throttles activity duration based on available budget.

    ARCHITECTURAL FIX:
    - Budget-to-speed relationship is now EXPLICIT (BudgetResponseCurve parameter)
    - "2x max slowdown" is now CALIBRATABLE (change min_speed_ratio, not code)
    - Supports STOCHASTIC response (same mean, different variance = different risk)

    Example: Activity can accelerate with budget, but limited budget forces slower execution.

    Feasibility Rule:
        Activity with base_duration D and available budget B:
            effective_duration = D * response_curve.sample_multiplier(B/required_B, seed)
        Throttling applied ONCE per event (stored in event.execution_parameters).

    Idempotency:
        First evaluation: Compute throttling, store in event.execution_parameters
        Subsequent evaluations: Return cached throttling from event.execution_parameters
        This prevents re-throttling when event is rescheduled due to other constraints.

    Propagation:
        Modifies duration → affects when resources free up → affects downstream timing.
        Cumulative: Multiple throttled activities compound delays.
        Non-blocking: Activities progress, just slower.

    Key Design:
        Throttling decisions stored in event.execution_parameters:
            {
                "duration_multiplier": 1.2,  # 20% slowdown
                "budget_applied": 20000
            }
        This ensures same event always gets same throttling, regardless of re-evaluation.

    Usage:
        # Conservative (2x max slowdown)
        constraint = BudgetThrottlingConstraint(
            budget_per_day=50000,
            response_curve=LinearResponseCurve(min_speed_ratio=0.5)
        )

        # Aggressive (5x max slowdown)
        constraint = BudgetThrottlingConstraint(
            budget_per_day=50000,
            response_curve=LinearResponseCurve(min_speed_ratio=0.2)
        )

    Calibration Workflow:
        Week 1: Use LinearResponseCurve(min_speed_ratio=0.5)  # Expert guess
        Week 5: Collect data on budget vs actual duration
        Week 6: Fit curve, update to LinearResponseCurve(min_speed_ratio=0.3)  # Calibrated
        Week 7: Compare results (NO CODE CHANGE)
    """

    def __init__(self, budget_per_day: float, response_curve: BudgetResponseCurve):
        """
        Initialize budget throttling constraint.

        Args:
            budget_per_day: Daily budget rate available
            response_curve: How budget availability affects execution speed
                (Linear, Threshold, Stochastic, etc.)
        """
        self.budget_per_day = budget_per_day
        self.response_curve = response_curve

    def evaluate(self, state: Any, event: Any) -> ConstraintResult:
        """
        Apply budget throttling to activity duration.

        Args:
            state: Must have get_available_budget(time) method
            event: Must have duration, time, event_id attributes
                   Must have execution_parameters dict for caching throttling

        Returns:
            ConstraintResult with parameter_overrides for throttled duration
        """
        # Only applies to events with duration
        if not hasattr(event, 'duration'):
            return ConstraintResult.satisfied("No duration to throttle")

        # Zero-duration events (like instantaneous activations) can't be throttled
        if event.duration == 0.0:
            return ConstraintResult.satisfied("Zero duration, no throttling needed")

        # Check if throttling already applied (idempotency check)
        if hasattr(event, 'execution_parameters') and event.execution_parameters:
            if 'duration_multiplier' in event.execution_parameters:
                # Already throttled, return cached value
                cached_multiplier = event.execution_parameters['duration_multiplier']
                throttled_duration = event.duration * cached_multiplier

                return ConstraintResult.modified(
                    overrides={"duration": throttled_duration},
                    explanation=(
                        f"Budget throttling applied (cached): "
                        f"duration={throttled_duration:.1f} "
                        f"(multiplier={cached_multiplier:.2f})"
                    )
                )

        # First evaluation: Compute throttling using response curve
        available_budget = state.get_available_budget(event.time)
        base_duration = event.duration

        # Compute budget ratio
        required_budget = self.budget_per_day * base_duration
        budget_ratio = available_budget / required_budget if required_budget > 0 else 1.0

        # Generate deterministic seed for this event+constraint combination
        # Use event_id to ensure same event gets same multiplier on re-evaluation
        import hashlib
        seed_string = f"{event.event_id}_budget_throttling"
        event_seed = int(hashlib.sha256(seed_string.encode()).hexdigest(), 16) % (2**31)

        # Sample duration multiplier from response curve
        # ARCHITECTURAL FIX: No hardcoded formula here, behavior is injected
        duration_multiplier = self.response_curve.sample_multiplier(budget_ratio, event_seed)

        throttled_duration = base_duration * duration_multiplier
        budget_consumed = min(available_budget, required_budget)

        # Store in event execution_parameters (idempotency cache)
        if not hasattr(event, 'execution_parameters'):
            event.execution_parameters = {}

        event.execution_parameters['duration_multiplier'] = duration_multiplier
        event.execution_parameters['budget_applied'] = budget_consumed

        # Return modified parameters
        return ConstraintResult.modified(
            overrides={"duration": throttled_duration},
            explanation=(
                f"Budget throttling applied: "
                f"duration={throttled_duration:.1f} days "
                f"(multiplier={duration_multiplier:.2f}, "
                f"budget_ratio={budget_ratio:.2f})"
            )
        )


# =============================================================================
# Constraint Composition
# =============================================================================


def compose_constraint_results(results: List[ConstraintResult]) -> ConstraintResult:
    """
    Compose multiple constraint results into single result.

    Composition Rules (Sacred Engine Law):
        1. is_valid = AND of all is_valid (any false → false)
        2. earliest_valid_time = MAX of all earliest_valid_times
        3. delay = MAX of all delays
        4. parameter_overrides = MERGE all overrides (later wins on conflict)
        5. explanation = CONCAT all explanations

    Args:
        results: List of ConstraintResults from different constraints

    Returns:
        Combined ConstraintResult

    Examples:
        # Validity constraint blocks + feasibility constraint delays
        results = [
            ConstraintResult(is_valid=False, earliest_valid_time=50, ...),
            ConstraintResult(is_valid=True, delay=10, ...)
        ]
        → Combined: is_valid=False, earliest_valid_time=50, delay=10

        # Multiple delays compose via max
        results = [
            ConstraintResult(is_valid=True, delay=5, ...),
            ConstraintResult(is_valid=True, delay=10, ...)
        ]
        → Combined: delay=10 (most restrictive)
    """
    if not results:
        return ConstraintResult.satisfied("No constraints evaluated")

    # Compose validity (AND operation)
    is_valid = all(r.is_valid for r in results)

    # Compose earliest_valid_time (MAX operation)
    valid_times = [r.earliest_valid_time for r in results if r.earliest_valid_time is not None]
    earliest_valid_time = max(valid_times) if valid_times else None

    # Compose delays (MAX operation)
    delay = max(r.delay for r in results)

    # Merge parameter overrides (later wins)
    parameter_overrides = {}
    for r in results:
        parameter_overrides.update(r.parameter_overrides)

    # Concatenate explanations
    explanations = [r.explanation for r in results if r.explanation]
    explanation = "; ".join(explanations) if explanations else "All constraints satisfied"

    return ConstraintResult(
        is_valid=is_valid,
        earliest_valid_time=earliest_valid_time,
        delay=delay,
        parameter_overrides=parameter_overrides,
        explanation=explanation
    )
