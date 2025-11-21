#!/usr/bin/env python3
"""
Suggestion Validator - Backend Validation Layer for Phase 2A

Validates LLM-generated suggestions BEFORE returning to user to prevent:
- Prohibited changes (numeric values, endpoints, dosing)
- Incomplete conditional language removal
- Low-confidence suggestions
- Endpoint/scientific claim modifications

This runs AFTER LLM but BEFORE returning suggestions to frontend.
"""

import re
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

# ============================================================================
# VALIDATION RULES
# ============================================================================

# Critical: No changes to these patterns
PROHIBITED_PATTERNS = {
    "numeric_values": r"\d+(\.\d+)?",  # Any numbers
    "dosing": r"\d+\s*(mg|g|ml|mcg|ug|IU|units?)",  # Dosing patterns
    "endpoints": [
        r"primary endpoint",
        r"secondary endpoint",
        r"overall survival",
        r"progression[- ]free survival",
        r"PFS",
        r"OS",
        r"viral load",
        r"disease progression"
    ],
    "safety": [
        r"SAE",
        r"serious adverse event",
        r"adverse event reporting",
        r"safety monitoring"
    ]
}

# Conditional language patterns that should be REMOVED
CONDITIONAL_PATTERNS = [
    r"\bmay\b",
    r"if deemed appropriate",
    r"as appropriate",
    r"as needed",
    r"if appropriate",
    r"if necessary",
    r"as required"
]

# Confidence thresholds
MIN_CONFIDENCE_ACCEPT = 0.4  # Below this = reject
MIN_CONFIDENCE_AUTO_APPLY = 0.85  # Above this = can auto-apply


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def extract_numbers(text: str) -> List[str]:
    """Extract all numeric values from text"""
    return re.findall(PROHIBITED_PATTERNS["numeric_values"], text)


def extract_dosing(text: str) -> List[str]:
    """Extract dosing patterns from text"""
    return re.findall(PROHIBITED_PATTERNS["dosing"], text, re.IGNORECASE)


def contains_pattern(text: str, patterns: List[str]) -> List[str]:
    """Check if text contains any of the patterns"""
    found = []
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            found.append(pattern)
    return found


def changes_numeric_values(original: str, improved: str) -> Tuple[bool, str]:
    """
    Check if improved text changes numeric values from original

    Returns:
        (has_changes, reason)
    """
    orig_nums = set(extract_numbers(original))
    imp_nums = set(extract_numbers(improved))

    if orig_nums != imp_nums:
        added = imp_nums - orig_nums
        removed = orig_nums - imp_nums
        reason = f"Numeric changes: removed={removed}, added={added}"
        return True, reason

    return False, ""


def changes_dosing(original: str, improved: str) -> Tuple[bool, str]:
    """Check if dosing values changed"""
    orig_dose = set(extract_dosing(original))
    imp_dose = set(extract_dosing(improved))

    if orig_dose != imp_dose:
        reason = f"Dosing changes: original={orig_dose}, improved={imp_dose}"
        return True, reason

    return False, ""


def changes_endpoints(original: str, improved: str) -> Tuple[bool, str]:
    """Check if endpoint language changed"""
    endpoint_patterns = PROHIBITED_PATTERNS["endpoints"]

    orig_endpoints = contains_pattern(original, endpoint_patterns)
    imp_endpoints = contains_pattern(improved, endpoint_patterns)

    # Check if endpoints were removed or significantly changed
    for ep in orig_endpoints:
        if ep not in orig_endpoints and ep not in improved.lower():
            return True, f"Endpoint removed or changed: {ep}"

    return False, ""


def changes_safety_language(original: str, improved: str) -> Tuple[bool, str]:
    """Check if safety reporting language was removed"""
    safety_patterns = PROHIBITED_PATTERNS["safety"]

    orig_safety = contains_pattern(original, safety_patterns)
    imp_safety = contains_pattern(improved, safety_patterns)

    # Safety language should not be removed
    for safety in orig_safety:
        if safety not in improved.lower():
            return True, f"Safety language removed: {safety}"

    return False, ""


def contains_conditional_language(text: str) -> bool:
    """Check if text contains conditional/ambiguous language"""
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in CONDITIONAL_PATTERNS)


def validates_conditional_removal(original: str, improved: str) -> Tuple[bool, str]:
    """
    Validate that conditional language was properly removed

    If original has conditional language, improved should either:
    1. Remove it entirely, OR
    2. Replace with pre-specified language

    Returns:
        (is_valid, reason)
    """
    orig_conditional = contains_conditional_language(original)
    imp_conditional = contains_conditional_language(improved)

    if orig_conditional and imp_conditional:
        return False, "Did not remove conditional language"

    # Check if replaced with pre-specification language
    prespec_indicators = [
        "pre-specified",
        "will be",
        "must be",
        "shall be",
        "SAP",
        "Statistical Analysis Plan"
    ]

    if orig_conditional and not imp_conditional:
        # Good - removed conditional. Check if added pre-spec
        has_prespec = any(indicator in improved for indicator in prespec_indicators)
        if not has_prespec:
            return False, "Removed conditional but did not add pre-specification language"

    return True, ""


def is_prohibited_change(original: str, improved: str) -> Tuple[bool, str]:
    """
    Master function: Check if suggestion makes prohibited changes

    Returns:
        (is_prohibited, reason)
    """
    # Check numeric changes
    changed, reason = changes_numeric_values(original, improved)
    if changed:
        return True, f"PROHIBITED: {reason}"

    # Check dosing changes
    changed, reason = changes_dosing(original, improved)
    if changed:
        return True, f"PROHIBITED: {reason}"

    # Check endpoint changes
    changed, reason = changes_endpoints(original, improved)
    if changed:
        return True, f"PROHIBITED: {reason}"

    # Check safety language removal
    changed, reason = changes_safety_language(original, improved)
    if changed:
        return True, f"PROHIBITED: {reason}"

    return False, ""


def validate_suggestion(suggestion: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a single suggestion

    Args:
        suggestion: Suggestion dict with original_text, improved_text, confidence, etc.

    Returns:
        {
            "valid": bool,
            "reason": str (if invalid),
            "confidence_tier": "auto_apply" | "requires_review" | "reject",
            "warnings": List[str]
        }
    """
    warnings = []

    # Extract fields
    original = suggestion.get("text", suggestion.get("original_text", ""))
    improved = suggestion.get("suggestion", suggestion.get("improved_text", ""))
    confidence = suggestion.get("confidence", 0.0)

    # Validation checks
    result = {
        "valid": True,
        "reason": "",
        "confidence_tier": "requires_review",
        "warnings": []
    }

    # 1. Check for missing fields
    if not improved:
        return {
            "valid": False,
            "reason": "Missing improved_text",
            "confidence_tier": "reject",
            "warnings": []
        }

    # 2. Check confidence threshold
    if confidence < MIN_CONFIDENCE_ACCEPT:
        return {
            "valid": False,
            "reason": f"Low confidence: {confidence} < {MIN_CONFIDENCE_ACCEPT}",
            "confidence_tier": "reject",
            "warnings": []
        }

    # Set confidence tier
    if confidence >= MIN_CONFIDENCE_AUTO_APPLY:
        result["confidence_tier"] = "auto_apply"
    elif confidence >= MIN_CONFIDENCE_ACCEPT:
        result["confidence_tier"] = "requires_review"
    else:
        result["confidence_tier"] = "reject"

    # 3. Check prohibited changes
    prohibited, reason = is_prohibited_change(original, improved)
    if prohibited:
        return {
            "valid": False,
            "reason": reason,
            "confidence_tier": "reject",
            "warnings": []
        }

    # 4. Check conditional language removal (warning, not rejection)
    if original:  # Only check if we have original text
        valid_conditional, reason = validates_conditional_removal(original, improved)
        if not valid_conditional:
            warnings.append(f"CONDITIONAL: {reason}")
            # Downgrade confidence tier
            if result["confidence_tier"] == "auto_apply":
                result["confidence_tier"] = "requires_review"

    result["warnings"] = warnings
    return result


def validate_suggestions_batch(suggestions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate a batch of suggestions

    Args:
        suggestions: List of suggestion dicts

    Returns:
        {
            "accepted": List[Dict],  # Valid suggestions
            "rejected": List[Dict],  # Invalid suggestions with rejection_reason
            "warnings": List[str],   # Overall warnings
            "stats": {
                "total": int,
                "accepted": int,
                "rejected": int,
                "auto_apply_count": int,
                "requires_review_count": int
            }
        }
    """
    accepted = []
    rejected = []
    overall_warnings = []

    stats = {
        "total": len(suggestions),
        "accepted": 0,
        "rejected": 0,
        "auto_apply_count": 0,
        "requires_review_count": 0
    }

    for suggestion in suggestions:
        try:
            validation = validate_suggestion(suggestion)

            if validation["valid"]:
                # Add validation metadata to suggestion
                suggestion["_validation"] = {
                    "confidence_tier": validation["confidence_tier"],
                    "warnings": validation["warnings"]
                }
                accepted.append(suggestion)
                stats["accepted"] += 1

                if validation["confidence_tier"] == "auto_apply":
                    stats["auto_apply_count"] += 1
                elif validation["confidence_tier"] == "requires_review":
                    stats["requires_review_count"] += 1

                # Collect warnings
                overall_warnings.extend(validation["warnings"])

            else:
                # Add rejection reason
                suggestion["_rejection_reason"] = validation["reason"]
                suggestion["_confidence_tier"] = validation["confidence_tier"]
                rejected.append(suggestion)
                stats["rejected"] += 1

        except Exception as e:
            logger.error(f"❌ Validation error for suggestion: {e}")
            suggestion["_rejection_reason"] = f"Validation exception: {str(e)}"
            rejected.append(suggestion)
            stats["rejected"] += 1

    return {
        "accepted": accepted,
        "rejected": rejected,
        "warnings": list(set(overall_warnings)),  # Deduplicate
        "stats": stats
    }


def get_validator_stats() -> Dict[str, Any]:
    """Get statistics about validator configuration"""
    return {
        "confidence_thresholds": {
            "min_accept": MIN_CONFIDENCE_ACCEPT,
            "min_auto_apply": MIN_CONFIDENCE_AUTO_APPLY
        },
        "prohibited_checks": [
            "numeric_values",
            "dosing",
            "endpoints",
            "safety_language"
        ],
        "conditional_patterns": len(CONDITIONAL_PATTERNS)
    }


# Log configuration on import
logger.info("✅ Suggestion validator loaded (Phase 2A)")
logger.info(f"   - Min confidence (accept): {MIN_CONFIDENCE_ACCEPT}")
logger.info(f"   - Min confidence (auto-apply): {MIN_CONFIDENCE_AUTO_APPLY}")
logger.info(f"   - Prohibited checks: 4 types")


__all__ = [
    "validate_suggestion",
    "validate_suggestions_batch",
    "get_validator_stats",
    "MIN_CONFIDENCE_ACCEPT",
    "MIN_CONFIDENCE_AUTO_APPLY"
]
