#!/usr/bin/env python3
"""
Rule-Based Compliance Engine - Deterministic Regulatory Checks

Runs fast regex-based checks BEFORE LLM to catch common regulatory/clarity issues.
These rules provide a baseline layer of compliance detection (< 1ms per check).

Priority: Run these checks first, then supplement with LLM-based analysis.
"""

import re
import logging
from typing import List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ComplianceIssue:
    """Structured compliance issue from rule engine"""
    rule_id: str
    category: str
    severity: str
    short_description: str
    detail: str
    evidence: List[str]
    confidence: float = 1.0  # Rule-based checks are deterministic


# ============================================================================
# CANONICAL RULES (Priority Ordered)
# ============================================================================

# Rule 1: Conditional Language (CRITICAL)
CONDITIONAL_TOKENS = [
    r"\bmay\b",
    r"if deemed appropriate",
    r"as appropriate",
    r"as needed",
    r"as required",
    r"if appropriate",
    r"if necessary"
]

# Rule 2: Post-Enrollment Reassignment (MAJOR)
REASSIGNMENT_TOKENS = [
    r"reassign(ed)? to",
    r"may be reassigned",
    r"migrate to",
    r"move to the highest severity",
    r"crossing from one .* group to another"
]

# Rule 3: Safety Reporting (MAJOR)
SAFETY_TOKENS = [
    r"\bSAE\b",
    r"serious adverse event",
    r"report within",
    r"adverse event reporting"
]

# Rule 4: Terminology - Subjects vs Participants (MINOR)
SUBJECT_TERMINOLOGY = [
    r"\bsubject(s)?\b",
    r"\bpatient(s)?\b"  # In some contexts, should be "participants"
]

# Rule 5: Vague Endpoint Language (MAJOR)
VAGUE_ENDPOINT_TOKENS = [
    r"endpoint will be measured",
    r"response will be assessed",
    r"outcome will be evaluated",
    r"as needed"
]

# Rule 6: Missing Visit Windows (MAJOR)
VISIT_SCHEDULE_TOKENS = [
    r"visit.*as needed",
    r"week-of visits",
    r"approximately.*visit"
]


# ============================================================================
# RULE ENGINE FUNCTIONS
# ============================================================================

def find_matches(text: str, token_list: List[str]) -> List[str]:
    """
    Find all regex pattern matches in text

    Args:
        text: Protocol text to scan
        token_list: List of regex patterns

    Returns:
        List of matched patterns
    """
    matches = []
    for pattern in token_list:
        if re.search(pattern, text, re.IGNORECASE):
            matches.append(pattern)
    return matches


def check_conditional_language(text: str) -> ComplianceIssue:
    """
    Rule 1: Detect conditional/ambiguous language requiring pre-specification

    ADVISORY: Statistical analysis must be pre-specified (ICH E9)
    """
    evidence = find_matches(text, CONDITIONAL_TOKENS)

    if evidence:
        return ComplianceIssue(
            rule_id="COND_001",
            category="statistical",
            severity="minor",  # Downgraded from critical to advisory
            short_description="Conditional language in statistical analysis (advisory)",
            detail="Found conditional/ambiguous phrasing that requires pre-specification in Statistical Analysis Plan (SAP). Language like 'may', 'if deemed appropriate', 'as needed' creates risk of post-hoc analysis decisions and alpha inflation.",
            evidence=evidence[:3],  # Limit to first 3 matches
            confidence=0.6  # Lowered from 0.95 to allow LLM suggestions to take priority
        )
    return None


def check_reassignment(text: str) -> ComplianceIssue:
    """
    Rule 2: Detect post-enrollment reassignment without pre-specification

    ADVISORY: Risk of immortal time bias and selection bias
    """
    evidence = find_matches(text, REASSIGNMENT_TOKENS)

    if evidence:
        return ComplianceIssue(
            rule_id="REASS_001",
            category="analysis_population",
            severity="minor",  # Downgraded from major to advisory
            short_description="Post-enrollment reassignment described (advisory)",
            detail="Text implies reassignment of subjects post-enrollment. Must pre-specify: (1) ITT analysis by enrollment group, (2) handling of time-varying severity in SAP, (3) methods to mitigate immortal time bias (e.g., time-varying covariates, marginal structural models).",
            evidence=evidence[:3],
            confidence=0.6  # Lowered from 0.90 to allow LLM suggestions to take priority
        )
    return None


def check_safety_reporting(text: str) -> ComplianceIssue:
    """
    Rule 3: Detect safety reporting language and verify completeness

    MAJOR: Regulatory requirement for SAE reporting timelines
    """
    evidence = find_matches(text, SAFETY_TOKENS)

    if evidence:
        # Check if text includes "24 hours" or "24-hour" (required SAE timeline)
        has_timeline = bool(re.search(r"24[\s-]?hour", text, re.IGNORECASE))

        if not has_timeline:
            return ComplianceIssue(
                rule_id="SAFETY_001",
                category="safety",
                severity="minor",  # Downgraded from major to advisory
                short_description="SAE reporting timeline missing (advisory)",
                detail="Safety reporting language found but missing required 24-hour SAE reporting timeline. Regulatory requirement: investigators must report SAEs to sponsor within 24 hours of awareness.",
                evidence=evidence[:2],
                confidence=0.6  # Lowered from 0.85 to allow LLM suggestions to take priority
            )
    return None


def check_terminology(text: str) -> ComplianceIssue:
    """
    Rule 4: Check for outdated terminology (subjects → participants)

    MINOR: ICH-GCP E6(R3) recommends 'participants' instead of 'subjects'
    """
    evidence = find_matches(text, SUBJECT_TERMINOLOGY)

    if evidence:
        # Check if text is specifically about "participants" already
        has_participants = bool(re.search(r"\bparticipant(s)?\b", text, re.IGNORECASE))

        if not has_participants:
            return ComplianceIssue(
                rule_id="TERM_001",
                category="terminology",
                severity="minor",  # Already minor, now advisory
                short_description="Outdated terminology: 'subjects' or 'patients' (advisory)",
                detail="ICH-GCP E6(R3) recommends using 'participants' instead of 'subjects' or 'patients' in clinical protocols. Update terminology for regulatory alignment.",
                evidence=evidence[:2],
                confidence=0.6  # Lowered from 0.75 to allow LLM suggestions to take priority
            )
    return None


def check_vague_endpoints(text: str) -> ComplianceIssue:
    """
    Rule 5: Detect vague endpoint language

    MAJOR: Endpoints must specify measurement, timepoint, and missing data handling
    """
    evidence = find_matches(text, VAGUE_ENDPOINT_TOKENS)

    if evidence:
        return ComplianceIssue(
            rule_id="ENDPT_001",
            category="documentation",
            severity="minor",  # Downgraded from major to advisory
            short_description="Vague endpoint language (advisory)",
            detail="Endpoint description lacks specificity. Must include: (1) exact measurement/instrument, (2) timepoint, (3) missing data handling. Example: 'Clinical response defined as ≥50% reduction in XYZ score from baseline at Day 28 using ABC instrument; missing data handled via multiple imputation per SAP Section 9.'",
            evidence=evidence[:2],
            confidence=0.6  # Lowered from 0.80 to allow LLM suggestions to take priority
        )
    return None


def check_visit_schedule(text: str) -> ComplianceIssue:
    """
    Rule 6: Detect vague visit schedule language

    ADVISORY: Visit windows must be explicitly defined
    """
    evidence = find_matches(text, VISIT_SCHEDULE_TOKENS)

    if evidence:
        return ComplianceIssue(
            rule_id="VISIT_001",
            category="documentation",
            severity="minor",  # Downgraded from major to advisory
            short_description="Vague visit schedule (advisory)",
            detail="Visit schedule lacks explicit windows. Specify exact windows: e.g., 'Day 0 ± 2 days, Day 7 ± 3 days, Day 28 ± 4 days' with reference to visit schedule table.",
            evidence=evidence[:2],
            confidence=0.6  # Lowered from 0.80 to allow LLM suggestions to take priority
        )
    return None


# ============================================================================
# MAIN ENGINE
# ============================================================================

def run_compliance_checks(text: str) -> List[Dict[str, Any]]:
    """
    Run all compliance rules on protocol text

    Args:
        text: Protocol text to analyze

    Returns:
        List of issues found (formatted for frontend)
    """
    issues = []

    # Run all rules (order by priority)
    checks = [
        check_conditional_language,
        check_reassignment,
        check_safety_reporting,
        check_terminology,
        check_vague_endpoints,
        check_visit_schedule
    ]

    for check_func in checks:
        try:
            issue = check_func(text)
            if issue:
                # Convert to frontend format
                issues.append({
                    "id": issue.rule_id,
                    "category": issue.category,
                    "severity": issue.severity,
                    "original_text": f"[Rule-based detection: {', '.join(issue.evidence)}]",
                    "improved_text": f"[{issue.short_description}] {issue.detail}",
                    "rationale": issue.detail,
                    "recommendation": f"Review and address {issue.short_description.lower()}",
                    "confidence": issue.confidence,
                    "source": "rule_engine"
                })
        except Exception as e:
            logger.error(f"❌ Compliance check {check_func.__name__} failed: {e}")

    return issues


def get_rule_stats() -> Dict[str, Any]:
    """Get statistics about rule engine"""
    return {
        "total_rules": 6,
        "critical_rules": 1,
        "major_rules": 4,
        "minor_rules": 1,
        "categories": ["statistical", "analysis_population", "safety", "terminology", "documentation"]
    }


# Log configuration on import
logger.info("✅ Compliance rule engine loaded")
logger.info(f"   - Total rules: {get_rule_stats()['total_rules']}")
logger.info(f"   - Critical: {get_rule_stats()['critical_rules']}, Major: {get_rule_stats()['major_rules']}, Minor: {get_rule_stats()['minor_rules']}")


__all__ = [
    "run_compliance_checks",
    "get_rule_stats",
    "ComplianceIssue"
]
