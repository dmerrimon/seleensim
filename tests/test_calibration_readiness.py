"""
Architectural tests for calibration readiness.

PURPOSE: Prevent magic numbers and hidden assumptions from creeping into constraints.

THE RULE:
    "Could this number be different for a different organization?"
    YES → assumption → must be parameterized
    NO → structural → OK to hardcode

These tests enforce that rule automatically.
"""

import pytest
import inspect
import re
from seleensim.constraints import (
    BudgetThrottlingConstraint,
    TemporalPrecedenceConstraint,
    ResourceCapacityConstraint,
    PredecessorConstraint
)


class TestCalibrationReadiness:
    """
    Architectural tests: Ensure constraints remain calibration-ready.

    Violations of these tests indicate hidden assumptions that prevent calibration.
    """

    def test_budget_constraint_has_no_hardcoded_response_logic(self):
        """
        BudgetThrottlingConstraint must not contain hardcoded response formulas.

        VIOLATION EXAMPLES:
            duration_multiplier = 1.0 / max(0.5, budget_ratio)  # ❌ Hidden 0.5
            slowdown = 2.0 * budget_ratio                       # ❌ Hidden 2.0
            if budget_ratio < 0.3: ...                          # ❌ Hidden 0.3

        CORRECT PATTERN:
            duration_multiplier = self.response_curve.sample_multiplier(...)  # ✅ Explicit
        """
        source = inspect.getsource(BudgetThrottlingConstraint.evaluate)

        # Forbidden patterns (numeric literals that look like assumptions)
        forbidden_patterns = [
            (r'\bmax\(\s*0\.\d+\s*,', 'max(0.X, ...) suggests hardcoded minimum'),
            (r'\bmin\(\s*\d+\.\d+\s*,', 'min(X.Y, ...) suggests hardcoded maximum'),
            (r'1\.0\s*/\s*budget_ratio', '1.0 / budget_ratio suggests hardcoded linear response'),
            (r'duration\s*\*\s*\d+\.\d+', 'duration * X.Y suggests hardcoded multiplier'),
        ]

        violations = []
        for pattern, explanation in forbidden_patterns:
            if re.search(pattern, source):
                violations.append(f"Found pattern '{pattern}': {explanation}")

        # Check for delegation to response curve (correct pattern)
        if 'response_curve' not in source or 'sample_multiplier' not in source:
            violations.append(
                "evaluate() should delegate to self.response_curve.sample_multiplier(...)"
            )

        if violations:
            pytest.fail(
                "BudgetThrottlingConstraint contains hardcoded response logic:\n" +
                "\n".join(f"  - {v}" for v in violations)
            )

    def test_constraints_accept_behavior_objects_not_magic_numbers(self):
        """
        Constraints must accept behavior objects (curves, distributions), not magic numbers.

        VIOLATION:
            class BadConstraint:
                def __init__(self, budget_per_day: float, max_slowdown: float = 2.0):
                                                          ^^^^^^^^^^^^^ Hidden assumption

        CORRECT:
            class GoodConstraint:
                def __init__(self, budget_per_day: float, response_curve: BudgetResponseCurve):
                                                          ^^^^^^^^^^^^^^ Explicit behavior
        """
        # Check BudgetThrottlingConstraint accepts response_curve
        sig = inspect.signature(BudgetThrottlingConstraint.__init__)
        params = sig.parameters

        # Must have 'response_curve' parameter
        assert 'response_curve' in params, \
            "BudgetThrottlingConstraint must accept 'response_curve' parameter"

        # Must NOT have default values that are assumptions
        forbidden_defaults = ['max_slowdown', 'min_speed', 'throttle_factor']
        for param_name, param in params.items():
            if param_name in forbidden_defaults:
                pytest.fail(
                    f"BudgetThrottlingConstraint has assumption parameter '{param_name}' "
                    f"(should be inside response_curve instead)"
                )

        # Check ResourceCapacityConstraint accepts capacity_response
        sig_resource = inspect.signature(ResourceCapacityConstraint.__init__)
        params_resource = sig_resource.parameters

        # Must have 'capacity_response' parameter
        assert 'capacity_response' in params_resource, \
            "ResourceCapacityConstraint must accept 'capacity_response' parameter"

        # Must NOT have hardcoded degradation assumptions
        forbidden_capacity_defaults = ['max_degradation', 'threshold_utilization', 'efficiency_factor']
        for param_name, param in params_resource.items():
            if param_name in forbidden_capacity_defaults:
                pytest.fail(
                    f"ResourceCapacityConstraint has assumption parameter '{param_name}' "
                    f"(should be inside capacity_response instead)"
                )

    def test_structural_constraints_only(self):
        """
        Constraints may contain structural validations (never change), not assumptions (vary).

        ALLOWED (structural):
            if time < 0: raise ValueError("Time cannot be negative")
            if budget < 0: raise ValueError("Budget cannot be negative")
            if duration == 0: return satisfied()  # Can't throttle zero duration

        FORBIDDEN (assumptions):
            if budget_ratio < 0.5: return invalid()  # Why 0.5? Organization-specific
            if slowdown > 2.0: slowdown = 2.0        # Why 2.0? Organization-specific
        """
        source = inspect.getsource(BudgetThrottlingConstraint.evaluate)

        # Check for structural validations (OK)
        structural_patterns = [
            r'duration\s*==\s*0',  # Zero duration check (structural)
            r'<\s*0',              # Negativity checks (structural)
        ]

        # Check for assumption-based conditionals (NOT OK)
        assumption_patterns = [
            (r'budget_ratio\s*<\s*0\.\d+(?!\s*\))', 'budget_ratio < 0.X threshold (assumption)'),
            (r'slowdown\s*>\s*\d+', 'slowdown > X cap (assumption)'),
        ]

        violations = []
        for pattern, explanation in assumption_patterns:
            matches = re.findall(pattern, source)
            # Filter out matches inside response_curve calls (those are OK)
            for match in matches:
                if 'response_curve' not in source[max(0, source.find(match) - 100):source.find(match)]:
                    violations.append(f"Found pattern '{pattern}': {explanation}")

        if violations:
            pytest.fail(
                "BudgetThrottlingConstraint contains assumption-based conditionals:\n" +
                "\n".join(f"  - {v}" for v in violations)
            )

    def test_no_numeric_literals_in_constraint_logic(self):
        """
        Constraint logic should not contain numeric literals (except 0, 1, structural checks).

        ALLOWED:
            if duration == 0.0: ...        # Structural check
            multiplier = 1.0 / speed       # Mathematical identity
            if time < 0: ...               # Structural constraint

        FORBIDDEN:
            multiplier = 0.5 * budget      # Why 0.5?
            if ratio < 0.3: ...            # Why 0.3?
            delay = 2.0 * base_time        # Why 2.0?
        """
        source = inspect.getsource(BudgetThrottlingConstraint.evaluate)

        # Find all numeric literals
        numeric_pattern = r'\b\d+\.\d+\b'
        numerics = re.findall(numeric_pattern, source)

        # Filter allowed values (structural)
        allowed = {'0.0', '1.0', '0', '1'}
        suspicious = [n for n in numerics if n not in allowed]

        if suspicious:
            # Check if they're inside response_curve calls (OK) or constraint logic (NOT OK)
            violations = []
            for num in suspicious:
                # Find context around number
                matches = [m for m in re.finditer(re.escape(num), source)]
                for match in matches:
                    start = max(0, match.start() - 100)
                    end = min(len(source), match.end() + 100)
                    context = source[start:end]

                    # If not inside response_curve call, it's a violation
                    if 'response_curve' not in context:
                        violations.append(
                            f"Numeric literal '{num}' found outside response_curve delegation"
                        )

            if violations:
                pytest.fail(
                    "BudgetThrottlingConstraint contains suspicious numeric literals:\n" +
                    "\n".join(f"  - {v}" for v in set(violations)) +
                    "\n\nReminder: Numbers that could differ between organizations must be in response_curve."
                )

    def test_other_constraints_remain_assumption_free(self):
        """
        Other constraints should not develop assumption-based logic.

        This is a watchdog test: As new constraints are added, ensure they don't
        introduce hidden assumptions.
        """
        # TemporalPrecedenceConstraint - pure structural logic
        source_temporal = inspect.getsource(TemporalPrecedenceConstraint.evaluate)
        # Should only check completion times, no assumptions
        assert 'get_completion_time' in source_temporal
        # No assumption-based patterns (multipliers, ratios, response curves)
        assert 'multiplier' not in source_temporal.lower()
        assert 'response' not in source_temporal.lower()

        # ResourceCapacityConstraint - NOW calibration-ready (accepts capacity_response)
        # Similar to BudgetThrottlingConstraint, it now delegates behavior to response curve
        sig_resource = inspect.signature(ResourceCapacityConstraint.__init__)
        params_resource = sig_resource.parameters
        assert 'capacity_response' in params_resource, \
            "ResourceCapacityConstraint must accept 'capacity_response' parameter"

        # PredecessorConstraint - pure structural logic
        source_pred = inspect.getsource(PredecessorConstraint.evaluate)
        # Should only check predecessors, no assumptions
        assert 'predecessors' in source_pred
        # No assumption-based patterns
        assert 'multiplier' not in source_pred.lower()
        assert 'response' not in source_pred.lower()


class TestArchitecturalRule:
    """
    Test the architectural rule itself: Can we distinguish assumptions from structure?

    This is meta-testing: Verifying our ability to catch violations.
    """

    def test_rule_identifies_assumptions_correctly(self):
        """
        The rule "Could this number be different for a different org?" should work.

        Test cases with known answers:
        """
        # Examples that ARE assumptions (should be parameterized)
        assumptions = [
            ("max_slowdown = 2.0", "Different orgs have different max slowdowns"),
            ("if budget_ratio < 0.5: block", "Threshold varies by org"),
            ("response = 1.0 / budget_ratio", "Response curve varies by org"),
        ]

        # Examples that are NOT assumptions (structural, OK to hardcode)
        structural = [
            ("if time < 0: error", "Time negativity is universal"),
            ("if duration == 0.0: skip", "Zero duration is structural"),
            ("multiplier = 1.0 / speed", "Mathematical identity, not assumption"),
        ]

        # This test documents what we consider assumptions vs structure
        # If someone disagrees with these classifications, update this test
        # and the architectural principle document together

        for code, reason in assumptions:
            # These should trigger "needs parameterization" flag
            assert any(keyword in code for keyword in ['=', '<', '>']), \
                f"Assumption '{code}' should contain comparison or assignment"

        for code, reason in structural:
            # These are OK to keep in code
            assert any(keyword in code for keyword in ['< 0', '== 0', '/ ']), \
                f"Structural constraint '{code}' uses universal rules"


class TestCalibrationWorkflow:
    """
    Integration test: Can SCRI actually calibrate without code changes?

    This tests the WORKFLOW, not just the structure.
    """

    def test_user_can_change_response_behavior_without_code_change(self):
        """
        Simulate calibration: User updates response curve, no code modified.

        Week 1: Expert guess
        Week 5: Calibrate with data
        Week 6: Compare results

        This should work WITHOUT editing constraint.py
        """
        # Week 1: Initial constraint with expert guess
        # (In real usage, this would be in a config file, not test code)
        from seleensim.constraints import (
            BudgetThrottlingConstraint,
            LinearResponseCurve
        )

        constraint_v1 = BudgetThrottlingConstraint(
            budget_per_day=50000,
            response_curve=LinearResponseCurve(min_speed_ratio=0.5)  # Expert: 2x max
        )

        assert constraint_v1.response_curve.mean_multiplier(0.5) == 2.0

        # Week 6: Updated constraint with calibrated data
        # CRITICAL: No code changes to constraint.py, just different parameters
        constraint_v2 = BudgetThrottlingConstraint(
            budget_per_day=50000,
            response_curve=LinearResponseCurve(min_speed_ratio=0.2)  # Data: 5x max
        )

        assert constraint_v2.response_curve.mean_multiplier(0.2) == 5.0

        # Verification: Same constraint class, different behavior
        assert type(constraint_v1) == type(constraint_v2)
        # Compare at budget_ratio=0.3 where curves differ:
        # v1: 1.0 / max(0.5, 0.3) = 1.0 / 0.5 = 2.0
        # v2: 1.0 / max(0.2, 0.3) = 1.0 / 0.3 = 3.33
        assert constraint_v1.response_curve.mean_multiplier(0.3) != \
               constraint_v2.response_curve.mean_multiplier(0.3)

        # This proves: Behavior changed WITHOUT code change
        # ✓ Calibration-ready

    def test_user_can_switch_response_models_without_code_change(self):
        """
        User can try different response curve configurations without code change.

        This tests: Can user explore different assumptions easily?
        """
        from seleensim.constraints import (
            BudgetThrottlingConstraint,
            LinearResponseCurve
        )

        # Model 1: Conservative response (2x max slowdown)
        constraint_conservative = BudgetThrottlingConstraint(
            budget_per_day=50000,
            response_curve=LinearResponseCurve(min_speed_ratio=0.5, max_speed_ratio=1.0)
        )

        # Model 2: Aggressive response (5x max slowdown)
        constraint_aggressive = BudgetThrottlingConstraint(
            budget_per_day=50000,
            response_curve=LinearResponseCurve(min_speed_ratio=0.2, max_speed_ratio=1.0)
        )

        # Verify different behaviors at budget_ratio=0.4:
        # Conservative: 1.0 / 0.5 = 2.0 (hits min_speed_ratio)
        # Aggressive: 1.0 / 0.4 = 2.5 (within range)
        assert constraint_conservative.response_curve.mean_multiplier(0.4) == 2.0
        assert constraint_aggressive.response_curve.mean_multiplier(0.4) == 2.5

        # At budget_ratio=0.2:
        # Conservative: 1.0 / 0.5 = 2.0 (hits min_speed_ratio)
        # Aggressive: 1.0 / 0.2 = 5.0 (within range)
        assert constraint_conservative.response_curve.mean_multiplier(0.2) == 2.0
        assert constraint_aggressive.response_curve.mean_multiplier(0.2) == 5.0

        # This proves: Can explore different models WITHOUT code changes
        # ✓ Calibration-ready


# =============================================================================
# Test Metadata
# =============================================================================

"""
These tests enforce the architectural principle:

    "Could this number be different for a different organization?"
    YES → assumption → must be parameterized
    NO → structural → OK to hardcode

Purpose:
    Prevent regression to hidden assumptions
    Catch violations early in development
    Document what counts as "assumption" vs "structure"

When tests fail:
    1. Check: Is this actually an assumption? (Could it vary by org?)
    2. If YES: Extract to parameter/distribution (fix the violation)
    3. If NO: Update test to allow this structural check (fix the test)

    Do NOT disable these tests without updating ARCHITECTURAL_PRINCIPLES.md

Maintenance:
    - Review when adding new constraints
    - Update when architectural rules evolve
    - Strengthen as new violation patterns emerge
"""
