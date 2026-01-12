"""
Timeline Context Formatter for LLM Prompts (Phase 4)

Converts Timeline objects from timeline_parser into compact, LLM-friendly context
for injection into prompts. Prioritizes conditional visit warnings and visit gaps
for schedule-aware suggestions.
"""

from typing import Optional, List, Dict, Any
from timeline_parser import Timeline, Visit
import logging

logger = logging.getLogger(__name__)


def format_timeline_for_prompt(
    timeline: Optional[Timeline],
    max_tokens: int = 500,
    include_assessment_gaps: bool = True,
    include_conditional_warnings: bool = True
) -> str:
    """
    Format timeline into compact prompt context

    Args:
        timeline: Timeline object from timeline_parser
        max_tokens: Token budget (~4 chars per token)
        include_assessment_gaps: Include missing assessment warnings
        include_conditional_warnings: Include conditional visit trigger warnings (PRIORITY)

    Returns:
        Formatted timeline string for prompt injection, or empty string if timeline unavailable
    """
    if not timeline or not timeline.visits:
        return ""

    max_chars = max_tokens * 4
    sections = []

    try:
        # 1. Study duration summary
        if timeline.baseline_visit and timeline.end_of_study_visit:
            baseline_time = timeline.baseline_visit.window.nominal_time or "Baseline"
            eos_time = timeline.end_of_study_visit.window.nominal_time or "End of Study"
            eos_days = timeline.end_of_study_visit.window.nominal_days
            duration_weeks = eos_days // 7

            sections.append(
                f"Study duration: {baseline_time} to {eos_time} (~{duration_weeks} weeks)"
            )

        # 2. Visit counts
        regular_visits = [v for v in timeline.visits if not v.is_conditional]
        sections.append(f"Scheduled visits: {len(regular_visits)}")

        if timeline.conditional_visits:
            sections.append(f"Conditional visits: {len(timeline.conditional_visits)}")

        # 3. Visit gaps >4 weeks (if token budget allows)
        if include_assessment_gaps:
            visit_gaps = _analyze_visit_gaps(regular_visits)
            if visit_gaps:
                gap_str = "Visit gaps >4 weeks:"
                for gap in visit_gaps[:3]:  # Limit to top 3 gaps
                    gap_str += f"\n  - {gap['from_visit']} → {gap['to_visit']} ({gap['gap_weeks']} weeks)"
                sections.append(gap_str)

        # 4. Conditional visit warnings (PRIORITY - always include if budget allows)
        if include_conditional_warnings and timeline.conditional_visits:
            warning_str = _format_conditional_warnings(timeline.conditional_visits)
            if warning_str:
                sections.append(warning_str)

        # Join sections with newlines
        full_context = "TIMELINE CONTEXT (from Schedule of Assessments):\n"
        full_context += "\n".join(sections)

        # Add recommendation if we have warnings
        if include_conditional_warnings and timeline.conditional_visits:
            full_context += "\n\nRecommendation: Define conditional criteria with objective thresholds."

        # Trim if exceeds budget
        if len(full_context) > max_chars:
            logger.warning(f"Timeline context exceeds budget ({len(full_context)} > {max_chars} chars), trimming")
            full_context = full_context[:max_chars-3] + "..."

        return full_context

    except Exception as e:
        logger.error(f"Error formatting timeline for prompt: {e}")
        return ""


def _analyze_visit_gaps(visits: List[Visit]) -> List[Dict]:
    """
    Find gaps >4 weeks (28 days) between consecutive visits

    Args:
        visits: List of Visit objects

    Returns:
        List of dicts with {from_visit, to_visit, gap_days, gap_weeks}
    """
    gaps = []

    try:
        # Sort visits by nominal_days
        sorted_visits = sorted(visits, key=lambda v: v.window.nominal_days)

        for i in range(len(sorted_visits) - 1):
            current = sorted_visits[i]
            next_visit = sorted_visits[i + 1]

            gap_days = next_visit.window.nominal_days - current.window.nominal_days
            gap_weeks = gap_days // 7

            # Flag gaps >4 weeks (28 days)
            if gap_weeks > 4:
                gaps.append({
                    "from_visit": current.window.nominal_time or current.visit_id,
                    "to_visit": next_visit.window.nominal_time or next_visit.visit_id,
                    "gap_days": gap_days,
                    "gap_weeks": gap_weeks
                })

    except Exception as e:
        logger.error(f"Error analyzing visit gaps: {e}")

    return gaps


def _format_conditional_warnings(conditional_visits: List[Visit]) -> str:
    """
    Format warnings about vague conditional visit triggers

    Checks for high-risk patterns from Phase 3:
    - "unless safety concern" (undefined)
    - "after missed" (no timing window)
    - "as clinically indicated" (vague trigger)
    - "at discretion" (subjective criteria)
    - "may opt" (consent implications)

    Args:
        conditional_visits: List of conditional Visit objects

    Returns:
        Formatted warning string with ⚠ prefix, or empty string
    """
    warnings = []

    try:
        # High-risk patterns from Phase 3 amendment risk patterns
        high_risk_patterns = [
            ("unless safety concern", "not defined in Safety section"),
            ("after missed", "no timing window defined"),
            ("as clinically indicated", "vague trigger"),
            ("at discretion", "subjective criteria"),
            ("may opt", "not in informed consent"),
        ]

        for visit in conditional_visits[:3]:  # Limit to 3 warnings
            if not visit.condition:
                continue

            condition_lower = visit.condition.lower()

            # Check for high-risk patterns
            for pattern, issue in high_risk_patterns:
                if pattern in condition_lower:
                    visit_name = visit.visit_name or visit.visit_id
                    warnings.append(
                        f"⚠ '{visit_name}' trigger: '{visit.condition}' - {issue}"
                    )
                    break  # Only flag first matching pattern per visit

    except Exception as e:
        logger.error(f"Error formatting conditional warnings: {e}")

    if warnings:
        return "Conditional visit triggers:\n  " + "\n  ".join(warnings)

    return ""


def get_timeline_context_stats(timeline: Optional[Timeline]) -> Dict[str, Any]:
    """
    Get summary statistics about timeline context

    Useful for debugging and monitoring timeline context injection

    Args:
        timeline: Timeline object

    Returns:
        Dict with stats: visit_count, conditional_count, gap_count, warning_count
    """
    if not timeline:
        return {
            "visit_count": 0,
            "conditional_count": 0,
            "gap_count": 0,
            "warning_count": 0
        }

    regular_visits = [v for v in timeline.visits if not v.is_conditional]
    gaps = _analyze_visit_gaps(regular_visits)
    warnings_str = _format_conditional_warnings(timeline.conditional_visits)
    warning_count = warnings_str.count("⚠") if warnings_str else 0

    return {
        "visit_count": len(regular_visits),
        "conditional_count": len(timeline.conditional_visits) if timeline.conditional_visits else 0,
        "gap_count": len(gaps),
        "warning_count": warning_count
    }
