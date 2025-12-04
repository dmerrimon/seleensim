"""
Section-Aware Rules (Layer 2: Semantic Understanding)

This module provides section-specific severity/confidence overrides
for ICH-GCP compliance rules. Different protocol sections have different
regulatory requirements and tolerance for certain issues.

Example: Conditional language ("may", "as appropriate") is critical in
statistics sections but only advisory in objectives sections.
"""

from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Section-specific rule overrides
# Format: {section: {rule_id: {severity: str, confidence: float}}}
SECTION_RULE_OVERRIDES: Dict[str, Dict[str, Dict[str, Any]]] = {
    "statistics": {
        # Statistics section: No conditional language allowed
        "check_conditional_language": {
            "severity": "critical",
            "confidence": 1.0,
            "rationale_suffix": " This is critical in the statistics section where all methods must be pre-specified per ICH E9."
        },
        "check_vague_endpoints": {
            "severity": "critical",
            "confidence": 0.95,
            "rationale_suffix": " Statistical methods require precisely defined endpoints."
        },
    },
    "safety": {
        # Safety section: SAE reporting and monitoring are critical
        "check_safety_reporting": {
            "severity": "critical",
            "confidence": 0.95,
            "rationale_suffix": " Safety reporting requirements are critical per ICH E6(R2) Section 4.11."
        },
        "check_conditional_language": {
            "severity": "major",
            "confidence": 0.9,
            "rationale_suffix": " Safety monitoring procedures should be clearly specified."
        },
    },
    "endpoints": {
        # Endpoints section: Precise definitions required
        "check_vague_endpoints": {
            "severity": "critical",
            "confidence": 1.0,
            "rationale_suffix": " Endpoint definitions must include measurement method, timepoint, and analysis approach per ICH E9 Section 2.2."
        },
        "check_conditional_language": {
            "severity": "major",
            "confidence": 0.9,
        },
    },
    "eligibility": {
        # Eligibility section: No subjective terms
        "check_subjective_criteria": {
            "severity": "major",
            "confidence": 0.9,
            "rationale_suffix": " Eligibility criteria must use objective, measurable thresholds to ensure consistent patient selection."
        },
        "check_conditional_language": {
            "severity": "major",
            "confidence": 0.85,
        },
    },
    "objectives": {
        # Objectives section: Primary/secondary labeling required
        "check_conditional_language": {
            "severity": "minor",
            "confidence": 0.7,
            "rationale_suffix": " Consider using more definitive language for clarity."
        },
    },
    "schedule": {
        # Visit schedule: Tolerances and windows required
        "check_conditional_language": {
            "severity": "major",
            "confidence": 0.85,
            "rationale_suffix": " Visit windows should include explicit tolerances (e.g., +/- 3 days)."
        },
    },
    "demographics": {
        # Demographics section: Lower priority
        "check_conditional_language": {
            "severity": "minor",
            "confidence": 0.6,
        },
    },
    "general": {
        # Default rules - no overrides
    }
}

# Section-specific validation instructions for prompts
SECTION_VALIDATION_FOCUS: Dict[str, str] = {
    "objectives": """
PROTOCOL SECTION: OBJECTIVES
Focus your analysis on:
- Ensure primary objective is explicitly labeled as such
- Each objective should have an associated endpoint
- Secondary objectives should support the primary objective
- Avoid vague goals without measurable outcomes
""",
    "endpoints": """
PROTOCOL SECTION: ENDPOINTS
Focus your analysis on:
- Each endpoint must specify the measurement method
- Timepoints for assessment must be clearly defined
- Statistical analysis method should be pre-specified
- Distinguish between primary, secondary, and exploratory endpoints
- ICH E9 Section 2.2 requires operational definitions
""",
    "statistics": """
PROTOCOL SECTION: STATISTICAL METHODS
Focus your analysis on:
- NO conditional language allowed ("may", "as appropriate", "if needed")
- All methods must be pre-specified (ICH E9)
- Sample size justification must be complete
- Analysis populations (ITT, Per-Protocol) must be defined
- Missing data handling must be specified
- Multiplicity adjustments for multiple endpoints
""",
    "eligibility": """
PROTOCOL SECTION: ELIGIBILITY CRITERIA
Focus your analysis on:
- NO subjective terms ("adequate", "appropriate", "normal", "acceptable")
- All thresholds must be specific and measurable
- Laboratory values need specific ranges
- Age criteria must be explicit
- Washout periods must be specified
- Contraindications must be listed explicitly
""",
    "safety": """
PROTOCOL SECTION: SAFETY
Focus your analysis on:
- SAE reporting within 24 hours (ICH E6(R2) Section 4.11)
- Specific monitoring procedures and frequencies
- Stopping rules must be explicit
- Safety laboratory assessments schedule
- Adverse event grading criteria (e.g., CTCAE)
- Data Safety Monitoring Board/Committee provisions
""",
    "schedule": """
PROTOCOL SECTION: STUDY SCHEDULE/VISITS
Focus your analysis on:
- Each visit must have explicit windows with tolerances
- Procedures at each visit should be comprehensive
- Missing visit procedures should be addressed
- Screening window defined
- End of treatment and follow-up clearly specified
""",
    "demographics": """
PROTOCOL SECTION: DEMOGRAPHICS/BASELINE
Focus your analysis on:
- Baseline characteristics to be collected
- Stratification factors if applicable
- Subgroup analyses planned
""",
    "general": """
GENERAL PROTOCOL TEXT
Apply standard ICH-GCP validation rules.
"""
}


def apply_section_overrides(issues: List[Dict[str, Any]], section: str) -> List[Dict[str, Any]]:
    """
    Apply section-specific severity/confidence overrides to compliance issues.

    Args:
        issues: List of compliance issues from rule engine
        section: Detected protocol section (eligibility, endpoints, statistics, etc.)

    Returns:
        Issues with updated severity/confidence based on section context
    """
    if not section or section not in SECTION_RULE_OVERRIDES:
        return issues

    overrides = SECTION_RULE_OVERRIDES.get(section, {})
    if not overrides:
        return issues

    modified_count = 0
    for issue in issues:
        rule_id = issue.get("id") or issue.get("rule_id")
        if rule_id and rule_id in overrides:
            override = overrides[rule_id]

            # Store original values for logging
            original_severity = issue.get("severity")
            original_confidence = issue.get("confidence")

            # Apply overrides
            if "severity" in override:
                issue["severity"] = override["severity"]
            if "confidence" in override:
                issue["confidence"] = override["confidence"]
            if "rationale_suffix" in override and issue.get("rationale"):
                issue["rationale"] = issue["rationale"] + override["rationale_suffix"]

            # Mark as section-adjusted
            issue["section_adjusted"] = True
            issue["section"] = section

            modified_count += 1
            logger.debug(
                f"Section override applied: {rule_id} in {section} section: "
                f"severity {original_severity} -> {issue.get('severity')}, "
                f"confidence {original_confidence} -> {issue.get('confidence')}"
            )

    if modified_count > 0:
        logger.info(f"Applied {modified_count} section-aware overrides for section: {section}")

    return issues


def get_section_validation_focus(section: str) -> Optional[str]:
    """
    Get section-specific validation instructions for prompt enhancement.

    Args:
        section: Detected protocol section

    Returns:
        Section-specific instructions string or None
    """
    return SECTION_VALIDATION_FOCUS.get(section or "general")


def get_section_severity_adjustment(section: str, rule_id: str) -> Optional[Dict[str, Any]]:
    """
    Get severity adjustment for a specific rule in a specific section.

    Args:
        section: Protocol section
        rule_id: Compliance rule identifier

    Returns:
        Override dict with severity/confidence or None
    """
    if section in SECTION_RULE_OVERRIDES:
        return SECTION_RULE_OVERRIDES[section].get(rule_id)
    return None
