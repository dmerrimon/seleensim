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
    improved_text: str  # Actual rewrite suggestion (copy-paste ready)
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
    Find all regex pattern matches in text and return the actual matched text

    Args:
        text: Protocol text to scan
        token_list: List of regex patterns

    Returns:
        List of actual matched text snippets (not the regex patterns)
    """
    matches = []
    for pattern in token_list:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Extract the actual matched text, not the pattern
            matched_text = match.group(0)
            matches.append(matched_text)
    return matches


def extract_sentence_with_match(text: str, token_list: List[str]) -> str:
    """
    Extract the sentence containing the first matched token.

    Args:
        text: Protocol text to scan
        token_list: List of regex patterns

    Returns:
        Full sentence containing the match, or the first 200 chars if no sentence boundary found
    """
    for pattern in token_list:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Find sentence boundaries around the match
            start_pos = match.start()
            end_pos = match.end()

            # Look backwards for sentence start (period, exclamation, question mark, or start of text)
            sentence_start = 0
            for i in range(start_pos - 1, -1, -1):
                if text[i] in '.!?\n' and i > 0:
                    sentence_start = i + 1
                    break

            # Look forwards for sentence end
            sentence_end = len(text)
            for i in range(end_pos, len(text)):
                if text[i] in '.!?' and i < len(text) - 1:
                    sentence_end = i + 1
                    break

            # Extract and clean the sentence
            sentence = text[sentence_start:sentence_end].strip()

            # If sentence is too long (> 300 chars), truncate around the match
            if len(sentence) > 300:
                # Extract 150 chars before and after the match
                match_in_sentence = start_pos - sentence_start
                excerpt_start = max(0, match_in_sentence - 150)
                excerpt_end = min(len(sentence), match_in_sentence + 150)
                sentence = "..." + sentence[excerpt_start:excerpt_end].strip() + "..."

            return sentence

    # Fallback: return first 200 chars if no match found
    return text[:200].strip() + "..."


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
            short_description="Conditional language detected (advisory)",
            detail="Found conditional/ambiguous phrasing that requires pre-specification in Statistical Analysis Plan (SAP). Language like 'may', 'if deemed appropriate', 'as needed' creates risk of post-hoc analysis decisions and alpha inflation.",
            improved_text="Consider revising to pre-specify statistical methods in the SAP. Example: 'All analytic methods, including handling of missing data and sensitivity analyses, will be pre-specified in the Statistical Analysis Plan prior to database lock.'",
            evidence=evidence[:3],  # Limit to first 3 matches
            confidence=0.5  # Lowered to make this truly advisory
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
            improved_text="Consider pre-specifying how post-enrollment reassignments will be analyzed. Example: 'Participants will be analyzed according to their initial enrollment group (intention-to-treat principle). Post-enrollment disease severity changes will be handled as time-varying covariates in statistical models as detailed in the SAP (Section 9.3).'",
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
                improved_text="Consider adding the required 24-hour SAE reporting timeline. Example: 'Serious Adverse Events (SAEs) must be reported to the sponsor Medical Monitor within 24 hours of the investigator becoming aware of the event. All SAEs will be documented using standardized case report forms and followed until resolution.'",
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
                improved_text="Consider updating terminology to align with ICH-GCP E6(R3). Replace 'subjects' or 'patients' with 'participants' throughout the protocol for modern regulatory standards.",
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
            improved_text="Consider specifying endpoint details more precisely. Include: (1) exact measurement instrument/scale, (2) specific timepoint (e.g., Day 28, Week 12), and (3) missing data handling method (e.g., multiple imputation, LOCF) with reference to SAP section.",
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
            improved_text="Consider defining explicit visit windows with allowed deviation ranges. Example: 'Study visits will occur at Screening (Day -14 to Day -1), Baseline (Day 0), Week 4 (±3 days), Week 8 (±3 days), Week 12 (±7 days), and End of Study (Week 24 ±7 days). See Schedule of Activities in Protocol Section 2, Table 1.'",
            evidence=evidence[:2],
            confidence=0.6  # Lowered from 0.80 to allow LLM suggestions to take priority
        )
    return None


# ============================================================================
# MAIN ENGINE
# ============================================================================

def get_token_list_for_check(check_func_name: str) -> List[str]:
    """
    Map check function names to their corresponding token lists.

    Args:
        check_func_name: Name of the check function

    Returns:
        List of regex patterns for that check
    """
    mapping = {
        "check_conditional_language": CONDITIONAL_TOKENS,
        "check_reassignment": REASSIGNMENT_TOKENS,
        "check_safety_reporting": SAFETY_TOKENS,
        "check_terminology": SUBJECT_TERMINOLOGY,
        "check_vague_endpoints": VAGUE_ENDPOINT_TOKENS,
        "check_visit_schedule": VISIT_SCHEDULE_TOKENS
    }
    return mapping.get(check_func_name, [])


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
                # Extract the full sentence containing the matched keywords
                # This extracts the actual text from the document that should be replaced
                token_list = get_token_list_for_check(check_func.__name__)
                original_text_sentence = extract_sentence_with_match(text, token_list) if token_list else ', '.join(issue.evidence)

                # Convert to frontend format
                issues.append({
                    "id": issue.rule_id,
                    "category": issue.category,
                    "severity": issue.severity,
                    "original_text": original_text_sentence,  # Full sentence from document
                    "improved_text": issue.improved_text,  # Copy-paste ready rewrite
                    "rationale": issue.detail,  # Explanation of why this is an issue
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
