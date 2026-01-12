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
    minimal_fix: str = None  # Word-level replacement (e.g., "'may' → 'will'")


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

# Rule 5: Vague Endpoint Language (MAJOR → CRITICAL in endpoints section)
VAGUE_ENDPOINT_TOKENS = [
    # Generic vague measurement language
    r"endpoint will be measured",
    r"response will be assessed",
    r"outcome will be evaluated",
    r"efficacy will be determined",
    r"will be assessed",
    r"will be evaluated",
    r"will be analyzed",
    # Missing timepoint indicators
    r"change in .+ score(?! at)",  # "change in XYZ score" without "at Week X"
    r"change from baseline(?! at)",  # "change from baseline" without timepoint
    # Missing measurement method
    r"improvement in(?! [A-Z])",  # "improvement in" not followed by instrument name
    r"reduction in(?! [A-Z])",  # "reduction in" not followed by measurement
    # Ambiguous endpoint references
    r"as needed",
    r"as appropriate",
    r"when indicated",
    r"if clinically indicated",
]

# Rule 6: Incomplete Endpoint Definition (CRITICAL for primary, MAJOR for secondary)
INCOMPLETE_ENDPOINT_PATTERNS = {
    "missing_timepoint": [
        r"primary endpoint is (?:the )?(?:change|improvement|reduction)(?! .+ at (?:Week|Day|Month))",
        r"secondary endpoint is (?:the )?(?:change|improvement|reduction)(?! .+ at (?:Week|Day|Month))",
        r"endpoint is (?:the )?(?:change|improvement|reduction) (?:from baseline )?in .{5,50}(?! at (?:Week|Day|Month))",
    ],
    "missing_analysis_method": [
        r"primary endpoint .{5,100}(?! using | analyzed | analysis )",
        r"endpoint is .{10,80}\.(?<! ANCOVA| MMRM| Cox| Kaplan| log-rank| regression| t-test)",
    ],
    "missing_responder_definition": [
        r"responder(?! defined| is defined| ≥| >=| >)",
        r"clinical response(?! defined| is defined| ≥| >=| >| per )",
    ],
    "non_inferiority_missing_margin": [
        r"non-?inferiority(?! margin| with a margin| \(margin)",
        r"non-?inferior(?! margin| with margin| \(margin)",
    ],
}

# Rule 7: Missing Visit Windows (MAJOR)
VISIT_SCHEDULE_TOKENS = [
    r"visit.*as needed",
    r"week-of visits",
    r"approximately.*visit"
]

# Rule 7: Subjective Eligibility Criteria (Layer 2: Section-Aware) (MAJOR in eligibility section)
SUBJECTIVE_CRITERIA_TOKENS = [
    r"\badequate\b",
    r"\bappropriate\b",
    r"\bnormal\b",
    r"\bacceptable\b",
    r"\bsufficient\b",
    r"\bsatisfactory\b",
    r"\bsuitable\b",
    r"\breasonable\b",
    r"\bclinically significant\b"
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
    # Skip participant rights language (e.g., "may withdraw", "may discontinue")
    text_lower = text.lower()
    if any(phrase in text_lower for phrase in ["may withdraw", "may discontinue", "participants may", "subjects may"]):
        return None

    evidence = find_matches(text, CONDITIONAL_TOKENS)

    if evidence:
        # Generate minimal fix based on matched conditional token
        first_match = evidence[0].lower()
        minimal_fix_map = {
            "may": "'may' → 'will'",
            "if deemed appropriate": "'if deemed appropriate' → 'as pre-specified in SAP Section [X]'",
            "as appropriate": "'as appropriate' → 'as pre-specified in SAP Section [X]'",
            "as needed": "'as needed' → 'per protocol Section [X]'",
            "as required": "'as required' → 'per protocol Section [X]'",
            "if appropriate": "'if appropriate' → 'as pre-specified in SAP Section [X]'",
            "if necessary": "'if necessary' → 'per protocol Section [X]'"
        }
        minimal_fix = minimal_fix_map.get(first_match, f"'{first_match}' → [pre-specify]")

        return ComplianceIssue(
            rule_id="COND_001",
            category="statistical",
            severity="minor",  # Downgraded from critical to advisory
            short_description="Conditional language detected (advisory)",
            detail="Found conditional/ambiguous phrasing that requires pre-specification in Statistical Analysis Plan (SAP). Language like 'may', 'if deemed appropriate', 'as needed' creates risk of post-hoc analysis decisions and alpha inflation.",
            improved_text="All analytic methods, including handling of missing data and sensitivity analyses, will be pre-specified in the Statistical Analysis Plan prior to database lock.",
            evidence=evidence[:3],  # Limit to first 3 matches
            confidence=0.5,  # Lowered to make this truly advisory
            minimal_fix=minimal_fix
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
            improved_text="Participants will be analyzed according to their initial enrollment group (intention-to-treat principle). Post-enrollment disease severity changes will be handled as time-varying covariates in statistical models as detailed in the SAP (Section [X]).",
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
                improved_text="Serious Adverse Events (SAEs) must be reported to the sponsor Medical Monitor within 24 hours of the investigator becoming aware of the event. All SAEs will be documented using standardized case report forms and followed until resolution.",
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
            # Extract the sentence containing the terminology issue
            original_sentence = extract_sentence_with_match(text, SUBJECT_TERMINOLOGY)

            # Replace terminology preserving capitalization
            improved_sentence = original_sentence
            improved_sentence = re.sub(r'\bsubjects\b', 'participants', improved_sentence)
            improved_sentence = re.sub(r'\bSubjects\b', 'Participants', improved_sentence)
            improved_sentence = re.sub(r'\bSUBJECTS\b', 'PARTICIPANTS', improved_sentence)
            improved_sentence = re.sub(r'\bpatients\b', 'participants', improved_sentence)
            improved_sentence = re.sub(r'\bPatients\b', 'Participants', improved_sentence)
            improved_sentence = re.sub(r'\bPATIENTS\b', 'PARTICIPANTS', improved_sentence)
            improved_sentence = re.sub(r'\bsubject\b', 'participant', improved_sentence)
            improved_sentence = re.sub(r'\bSubject\b', 'Participant', improved_sentence)
            improved_sentence = re.sub(r'\bSUBJECT\b', 'PARTICIPANT', improved_sentence)
            improved_sentence = re.sub(r'\bpatient\b', 'participant', improved_sentence)
            improved_sentence = re.sub(r'\bPatient\b', 'Participant', improved_sentence)
            improved_sentence = re.sub(r'\bPATIENT\b', 'PARTICIPANT', improved_sentence)

            return ComplianceIssue(
                rule_id="TERM_001",
                category="terminology",
                severity="minor",  # Already minor, now advisory
                short_description="Outdated terminology: 'subjects' or 'patients' (advisory)",
                detail="ICH-GCP E6(R3) recommends using 'participants' instead of 'subjects' or 'patients' in clinical protocols. Update terminology for regulatory alignment.",
                improved_text=improved_sentence,
                evidence=evidence[:2],
                confidence=0.6  # Lowered from 0.75 to allow LLM suggestions to take priority
            )
    return None


def check_vague_endpoints(text: str) -> ComplianceIssue:
    """
    Rule 5: Detect vague endpoint language

    MAJOR (CRITICAL in endpoints section): Endpoints must specify measurement,
    timepoint, analysis method, and missing data handling per ICH E9 Section 2.2
    """
    evidence = find_matches(text, VAGUE_ENDPOINT_TOKENS)

    if evidence:
        # Generate minimal fix based on matched token
        first_match = evidence[0].lower()
        if "change" in first_match or "improvement" in first_match or "reduction" in first_match:
            minimal_fix = f"Add timepoint: '{first_match}' → '{first_match} at Week [X]'"
        elif "will be" in first_match:
            minimal_fix = f"Specify method: '{first_match}' → '{first_match} using [instrument/method]'"
        else:
            minimal_fix = f"'{first_match}' → [pre-specify in SAP]"

        return ComplianceIssue(
            rule_id="ENDPT_001",
            category="endpoints",
            severity="major",  # Upgraded from minor; section_rules will make CRITICAL in endpoints section
            short_description="Incomplete endpoint specification",
            detail="Endpoint lacks required operational details per ICH E9 Section 2.2. Primary and secondary endpoints MUST specify: (1) exact measurement instrument/scale, (2) assessment timepoint, (3) responder definition if applicable, (4) analysis method, (5) analysis population. Vague endpoints create regulatory risk and statistical analysis ambiguity.",
            improved_text="The primary endpoint is change from baseline in [Instrument Name] total score at Week 12. Response is defined as ≥[X]% improvement. Analysis will use MMRM with baseline score, treatment, visit, and treatment-by-visit interaction as covariates in the ITT population. Missing data will be handled using multiple imputation as detailed in SAP Section [X].",
            evidence=evidence[:3],
            confidence=0.9,  # High confidence - vague endpoints are a real issue
            minimal_fix=minimal_fix
        )
    return None


def check_endpoint_completeness(text: str) -> ComplianceIssue:
    """
    Rule 6: Detect incomplete endpoint definitions

    CRITICAL for primary endpoints, MAJOR for secondary endpoints.
    Checks for missing: timepoint, analysis method, responder definition, NI margin.
    """
    issues_found = []
    is_primary = bool(re.search(r"primary endpoint", text, re.IGNORECASE))

    # Check each category of incompleteness
    for issue_type, patterns in INCOMPLETE_ENDPOINT_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                issues_found.append((issue_type, match.group(0)))
                break  # Only one match per category

    if not issues_found:
        return None

    # Generate specific feedback based on what's missing
    issue_type, matched_text = issues_found[0]

    issue_details = {
        "missing_timepoint": {
            "short": "Endpoint missing timepoint",
            "detail": "Endpoint definition lacks a specific assessment timepoint. ICH E9 requires endpoints to specify WHEN they are measured (e.g., 'at Week 12', 'at Day 28'). Without a timepoint, the endpoint is not operationally defined.",
            "fix": "Add timepoint: e.g., 'at Week 12' or 'at Day 28 ± 3 days'",
            "rewrite": "Add the assessment timepoint. Example: 'The primary endpoint is change from baseline in [Score] at Week 12.'",
        },
        "missing_analysis_method": {
            "short": "Endpoint missing analysis method",
            "detail": "Endpoint definition lacks the statistical analysis method. ICH E9 requires pre-specification of HOW endpoints will be analyzed (e.g., MMRM, ANCOVA, Cox regression, Kaplan-Meier).",
            "fix": "Add analysis method: e.g., 'analyzed using MMRM'",
            "rewrite": "Specify the analysis method. Example: 'Change from baseline will be analyzed using MMRM with treatment, visit, baseline score, and treatment-by-visit interaction as covariates.'",
        },
        "missing_responder_definition": {
            "short": "Responder endpoint lacks definition",
            "detail": "Clinical response or responder endpoint lacks a quantitative definition. What constitutes a 'responder'? Must specify threshold (e.g., '≥50% improvement', '≥2-point decrease').",
            "fix": "Define responder: e.g., 'responder defined as ≥50% reduction'",
            "rewrite": "Define the response threshold. Example: 'Clinical response is defined as ≥50% reduction in [Score] from baseline. Responder rate will be compared using Cochran-Mantel-Haenszel test stratified by [factors].'",
        },
        "non_inferiority_missing_margin": {
            "short": "Non-inferiority margin not specified",
            "detail": "Non-inferiority design mentioned but the margin is not specified. Regulatory requirement: must pre-specify the non-inferiority margin and justify its clinical relevance.",
            "fix": "Specify margin: e.g., 'non-inferiority margin of 10%'",
            "rewrite": "Specify the non-inferiority margin. Example: 'Non-inferiority will be concluded if the lower bound of the 95% CI for the treatment difference excludes -10% (non-inferiority margin). The margin of 10% is justified based on [historical data/clinical relevance].'",
        },
    }

    details = issue_details.get(issue_type, issue_details["missing_timepoint"])

    # Severity: CRITICAL for primary, MAJOR for secondary
    severity = "critical" if is_primary else "major"

    return ComplianceIssue(
        rule_id="ENDPT_002",
        category="endpoints",
        severity=severity,
        short_description=details["short"],
        detail=details["detail"],
        improved_text=details["rewrite"],
        evidence=[matched_text[:100]],  # Truncate long matches
        confidence=0.95,
        minimal_fix=details["fix"]
    )


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
            improved_text="Study visits will occur at Screening (Day -14 to Day -1), Baseline (Day 0), Week 4 (±3 days), Week 8 (±3 days), Week 12 (±7 days), and End of Study (Week 24 ±7 days). See Schedule of Activities in Protocol Section [X], Table [X].",
            evidence=evidence[:2],
            confidence=0.6  # Lowered from 0.80 to allow LLM suggestions to take priority
        )
    return None


def check_subjective_criteria(text: str) -> ComplianceIssue:
    """
    Rule 7: Detect subjective terms in eligibility criteria (Layer 2: Section-Aware)

    MAJOR (in eligibility section): Eligibility must use objective, measurable thresholds
    MINOR (in other sections): General advisory for precision
    """
    evidence = find_matches(text, SUBJECTIVE_CRITERIA_TOKENS)

    if evidence:
        return ComplianceIssue(
            rule_id="SUBJ_001",
            category="documentation",
            severity="minor",  # Default severity; upgraded to major in eligibility section by section_rules.py
            short_description="Subjective criteria detected",
            detail="Found subjective terms that lack measurable thresholds. In eligibility criteria, terms like 'adequate', 'normal', 'appropriate' create inconsistent patient selection. Replace with specific, quantifiable criteria.",
            improved_text="Participants must have eGFR ≥60 mL/min/1.73m² (for renal function criteria), AST/ALT ≤2.5× ULN (for liver function criteria), or adverse events Grade ≥2 per CTCAE v5.0 (for clinical significance thresholds).",
            evidence=evidence[:3],
            confidence=0.7  # Moderate confidence; section_rules.py may adjust based on section
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
        "check_visit_schedule": VISIT_SCHEDULE_TOKENS,
        "check_subjective_criteria": SUBJECTIVE_CRITERIA_TOKENS  # Layer 2
    }
    return mapping.get(check_func_name, [])


def run_compliance_checks(text: str, section: str = None) -> List[Dict[str, Any]]:
    """
    Run all compliance rules on protocol text with section-aware overrides (Layer 2)

    Args:
        text: Protocol text to analyze
        section: Optional protocol section (eligibility, endpoints, statistics, etc.)
                 for section-aware severity/confidence adjustments

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
        check_endpoint_completeness,  # New: checks for missing timepoint, analysis method, etc.
        check_visit_schedule,
        check_subjective_criteria  # Layer 2: Section-aware eligibility check
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
                    "original_text": original_text_sentence,  # Full sentence from document (for locate/highlight)
                    "problematic_text": issue.evidence[0] if issue.evidence else None,  # Exact matched phrase (for card display)
                    "minimal_fix": issue.minimal_fix,  # Word-level replacement (e.g., "'may' → 'will'")
                    "improved_text": issue.improved_text,  # Copy-paste ready rewrite
                    "rationale": issue.detail,  # Explanation of why this is an issue
                    "recommendation": f"Review and address {issue.short_description.lower()}",
                    "confidence": issue.confidence,
                    "source": "rule_engine"
                })
        except Exception as e:
            logger.error(f"❌ Compliance check {check_func.__name__} failed: {e}")

    # Apply section-specific overrides (Layer 2: Semantic Understanding)
    if section and section != "general":
        try:
            from section_rules import apply_section_overrides
            issues = apply_section_overrides(issues, section)
        except ImportError:
            logger.warning("section_rules module not available, skipping section overrides")

    return issues


def get_rule_stats() -> Dict[str, Any]:
    """Get statistics about rule engine"""
    return {
        "total_rules": 8,  # Including new endpoint completeness check
        "critical_rules": 2,  # ENDPT_001 (major->critical in section), ENDPT_002 (critical for primary)
        "major_rules": 4,
        "minor_rules": 2,
        "section_aware_rules": 2,  # Subjective criteria + endpoint checks
        "categories": ["statistical", "analysis_population", "safety", "terminology", "documentation", "endpoints"]
    }


# Log configuration on import
logger.info("✅ Compliance rule engine loaded (with Layer 2: Section-Aware)")
logger.info(f"   - Total rules: {get_rule_stats()['total_rules']}")
logger.info(f"   - Critical: {get_rule_stats()['critical_rules']}, Major: {get_rule_stats()['major_rules']}, Minor: {get_rule_stats()['minor_rules']}")
logger.info(f"   - Section-aware rules: {get_rule_stats()['section_aware_rules']}")


__all__ = [
    "run_compliance_checks",
    "get_rule_stats",
    "ComplianceIssue"
]
