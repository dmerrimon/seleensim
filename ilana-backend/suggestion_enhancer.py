#!/usr/bin/env python3
"""
Suggestion Enhancer - Post-Processing Module

Week 7 Phase 1: Enhance generic suggestions with protocol-specific entities

Purpose:
    Replace generic phrases with entity-filled specific phrases to improve
    suggestion specificity without requiring LLM re-generation.

Example:
    Generic: "Clarify visit schedule"
    Enhanced: "Specify visits at Day 2, Day 8, and Week 12 (±7 days)"

Target:
    - Enhance 40%+ of generic suggestions (specificity < 0.4)
    - Improve avg specificity by 0.3+ (e.g., 0.2 → 0.5)
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


# Generic phrase patterns mapped to entity-filled replacements
GENERIC_PHRASE_MAP = {
    # Visit schedule patterns
    r"clarif(?:y|ied)\s+(?:the\s+)?visit\s+schedule": {
        "replacement": "specify visits at {visit_list} with {window} windows",
        "entities_needed": ["visit_names", "timepoints"],
        "priority": 1
    },
    r"add\s+(?:more\s+)?detail\s+about\s+visit": {
        "replacement": "specify which visits ({visit_list}) and timing windows",
        "entities_needed": ["visit_names", "timepoints"],
        "priority": 1
    },
    r"specify\s+visit\s+(?:timing|schedule|windows)": {
        "replacement": "define visits at {visit_list} with specific windows (e.g., ±7 days)",
        "entities_needed": ["visit_names", "timepoints"],
        "priority": 1
    },

    # Assessment patterns
    r"clarif(?:y|ied)\s+(?:which\s+)?assessment": {
        "replacement": "specify which assessments ({assessment_list})",
        "entities_needed": ["assessment_types"],
        "priority": 1
    },
    r"specify\s+assessments": {
        "replacement": "define assessments: {assessment_list}",
        "entities_needed": ["assessment_types"],
        "priority": 1
    },
    r"add\s+(?:more\s+)?detail\s+about\s+assessments": {
        "replacement": "specify assessment types ({assessment_list}) and timing",
        "entities_needed": ["assessment_types"],
        "priority": 1
    },

    # Timing patterns
    r"add\s+timing\s+(?:information|details)": {
        "replacement": "schedule at {timepoint_list}",
        "entities_needed": ["timepoints"],
        "priority": 2
    },
    r"clarif(?:y|ied)\s+timing": {
        "replacement": "specify timing: {timepoint_list}",
        "entities_needed": ["timepoints"],
        "priority": 2
    },

    # Document reference patterns
    r"reference\s+documentation": {
        "replacement": "reference {document_list}",
        "entities_needed": ["document_refs"],
        "priority": 2
    },
    r"add\s+(?:document\s+)?reference": {
        "replacement": "cite {document_list} for procedures",
        "entities_needed": ["document_refs"],
        "priority": 2
    },

    # Criteria/threshold patterns
    r"define\s+criteria": {
        "replacement": "define criteria using objective thresholds: {threshold_list}",
        "entities_needed": ["safety_thresholds"],
        "priority": 1
    },
    r"specify\s+(?:safety\s+)?criteria": {
        "replacement": "establish criteria: {threshold_list}",
        "entities_needed": ["safety_thresholds"],
        "priority": 1
    },
    r"add\s+(?:more\s+)?detail\s+about\s+(?:safety\s+)?criteria": {
        "replacement": "define specific safety criteria ({threshold_list})",
        "entities_needed": ["safety_thresholds"],
        "priority": 1
    },

    # Procedure patterns
    r"clarif(?:y|ied)\s+procedures": {
        "replacement": "specify procedures in {document_list} with {assessment_list}",
        "entities_needed": ["document_refs", "assessment_types"],
        "priority": 2
    },
    r"add\s+(?:more\s+)?detail\s+(?:about\s+)?procedures": {
        "replacement": "detail procedures including {assessment_list} per {document_list}",
        "entities_needed": ["assessment_types", "document_refs"],
        "priority": 2
    },

    # Discontinuation patterns
    r"clarif(?:y|ied)\s+discontinuation": {
        "replacement": "specify discontinuation criteria ({threshold_list}) and follow-up visits ({visit_list})",
        "entities_needed": ["safety_thresholds", "visit_names"],
        "priority": 1
    },

    # Window patterns
    r"add\s+(?:visit\s+)?window": {
        "replacement": "add visit windows (e.g., ±7 days for {timepoint_list})",
        "entities_needed": ["timepoints"],
        "priority": 2
    },

    # General "clarify" patterns (lowest priority)
    r"clarif(?:y|ied)\s+(?:the\s+)?procedures": {
        "replacement": "specify procedures with reference to {document_list}",
        "entities_needed": ["document_refs"],
        "priority": 3
    },
    r"add\s+more\s+detail": {
        "replacement": "provide specific details using protocol entities",
        "entities_needed": [],  # Can work without entities
        "priority": 3
    }
}


def enhance_suggestion_specificity(
    suggestion: Dict[str, Any],
    entities: Dict[str, List[str]]
) -> Tuple[Dict[str, Any], bool]:
    """
    Enhance generic suggestions with protocol-specific entities

    Args:
        suggestion: Suggestion dict with 'improved_text' and 'recommendation'
        entities: Protocol entities extracted from text

    Returns:
        (enhanced_suggestion, was_enhanced): Tuple of modified suggestion and enhancement flag

    Example:
        >>> suggestion = {"improved_text": "Clarify visit schedule"}
        >>> entities = {"visit_names": ["Baseline", "Week 4"], "timepoints": ["Day 2"]}
        >>> enhance_suggestion_specificity(suggestion, entities)
        {
            "improved_text": "Specify visits at Baseline, Week 4 with appropriate windows",
            "enhancement_applied": True,
            "original_text": "Clarify visit schedule"
        }
    """
    if not suggestion or not entities:
        return suggestion, False

    improved_text = suggestion.get("improved_text", "")
    recommendation = suggestion.get("recommendation", "")

    if not improved_text and not recommendation:
        return suggestion, False

    # Track if any enhancement made
    enhanced = False
    enhanced_text = improved_text
    enhanced_recommendation = recommendation
    enhancements = []

    # Lowercase for matching
    improved_text_lower = improved_text.lower()

    # Try each generic phrase pattern (sorted by priority)
    patterns = sorted(
        GENERIC_PHRASE_MAP.items(),
        key=lambda x: x[1].get("priority", 999)
    )

    for pattern, replacement_spec in patterns:
        # Check if pattern matches
        if re.search(pattern, improved_text_lower, re.IGNORECASE):
            # Check if we have required entities
            entities_needed = replacement_spec["entities_needed"]
            if not all(entities.get(e) for e in entities_needed):
                continue  # Skip if missing required entities

            # Build entity lists for replacement
            entity_values = _build_entity_values(entities, entities_needed)
            if not entity_values:
                continue

            # Perform replacement
            replacement_template = replacement_spec["replacement"]
            try:
                replacement_text = replacement_template.format(**entity_values)

                # Replace generic phrase with specific text
                improved_text = re.sub(
                    pattern,
                    replacement_text,
                    improved_text,
                    count=1,
                    flags=re.IGNORECASE
                )

                enhanced = True
                enhancements.append({
                    "pattern": pattern,
                    "original": re.search(pattern, improved_text_lower, re.IGNORECASE).group(),
                    "replacement": replacement_text,
                    "entities_used": list(entity_values.keys())
                })

                break  # Only enhance once per suggestion

            except KeyError as e:
                logger.warning(f"Template format error: {e}")
                continue

    # Update suggestion with enhanced text
    if enhanced:
        suggestion["improved_text"] = improved_text
        suggestion["enhancement_applied"] = True
        suggestion["enhancements"] = enhancements

        # Recalculate specificity score
        from suggestion_specificity_scorer import score_suggestion_specificity, classify_specificity
        new_score = score_suggestion_specificity(suggestion, entities)
        old_score = suggestion.get("specificity_score", 0.0)

        suggestion["specificity_score"] = new_score
        suggestion["specificity_level"] = classify_specificity(new_score)
        suggestion["specificity_improvement"] = new_score - old_score

        logger.info(
            f"Enhanced suggestion: {old_score:.3f} → {new_score:.3f} "
            f"(+{new_score - old_score:.3f})"
        )
    else:
        suggestion["enhancement_applied"] = False

    return suggestion, enhanced


def _build_entity_values(
    entities: Dict[str, List[str]],
    entities_needed: List[str]
) -> Dict[str, str]:
    """
    Build entity value strings for template replacement

    Args:
        entities: Dictionary of protocol entities
        entities_needed: List of entity types needed for template

    Returns:
        Dictionary with formatted entity strings

    Example:
        >>> entities = {"visit_names": ["Baseline", "Week 4", "Week 12"]}
        >>> _build_entity_values(entities, ["visit_names"])
        {"visit_list": "Baseline, Week 4, and Week 12"}
    """
    entity_values = {}

    for entity_type in entities_needed:
        entity_list = entities.get(entity_type, [])
        if not entity_list:
            continue

        # Format entity list for natural language
        if entity_type in ["visit_names", "timepoints"]:
            # Use "and" for last item
            if len(entity_list) == 1:
                formatted = entity_list[0]
            elif len(entity_list) == 2:
                formatted = f"{entity_list[0]} and {entity_list[1]}"
            else:
                formatted = ", ".join(entity_list[:-1]) + f", and {entity_list[-1]}"
            entity_values["visit_list"] = formatted
            entity_values["timepoint_list"] = formatted

        elif entity_type == "assessment_types":
            if len(entity_list) == 1:
                formatted = entity_list[0]
            elif len(entity_list) == 2:
                formatted = f"{entity_list[0]} and {entity_list[1]}"
            else:
                formatted = ", ".join(entity_list[:-1]) + f", and {entity_list[-1]}"
            entity_values["assessment_list"] = formatted

        elif entity_type == "safety_thresholds":
            # Join with semicolons for thresholds
            formatted = "; ".join(entity_list)
            entity_values["threshold_list"] = formatted

        elif entity_type == "document_refs":
            if len(entity_list) == 1:
                formatted = entity_list[0]
            else:
                formatted = " and ".join(entity_list)
            entity_values["document_list"] = formatted

        # Add default window if timepoints present
        if "timepoints" in entities_needed and entity_list:
            entity_values["window"] = "±7 days"  # Default protocol window

    return entity_values


def enhance_suggestions_batch(
    suggestions: List[Dict[str, Any]],
    entities: Dict[str, List[str]],
    threshold: float = 0.4
) -> Dict[str, Any]:
    """
    Enhance a batch of suggestions and return summary statistics

    Args:
        suggestions: List of suggestions to enhance
        entities: Protocol entities for enhancement
        threshold: Only enhance suggestions below this specificity score

    Returns:
        Dictionary with enhanced suggestions and statistics

    Example:
        >>> result = enhance_suggestions_batch(suggestions, entities)
        >>> print(f"Enhanced {result['stats']['enhanced_count']} suggestions")
    """
    enhanced_suggestions = []
    stats = {
        "total_count": len(suggestions),
        "enhanced_count": 0,
        "skipped_no_entities": 0,
        "skipped_already_specific": 0,
        "avg_improvement": 0.0,
        "improvements": []
    }

    for suggestion in suggestions:
        # Check if suggestion is already specific
        current_score = suggestion.get("specificity_score", 0.0)
        if current_score >= threshold:
            enhanced_suggestions.append(suggestion)
            stats["skipped_already_specific"] += 1
            continue

        # Enhance suggestion
        enhanced, was_enhanced = enhance_suggestion_specificity(suggestion, entities)
        enhanced_suggestions.append(enhanced)

        # Track statistics
        if was_enhanced:
            stats["enhanced_count"] += 1
            improvement = enhanced.get("specificity_improvement", 0.0)
            stats["improvements"].append(improvement)
        else:
            stats["skipped_no_entities"] += 1

    # Calculate average improvement
    if stats["improvements"]:
        stats["avg_improvement"] = sum(stats["improvements"]) / len(stats["improvements"])

    return {
        "suggestions": enhanced_suggestions,
        "stats": stats
    }


def get_enhancement_summary(stats: Dict[str, Any]) -> str:
    """
    Generate human-readable summary of enhancement results

    Args:
        stats: Statistics from enhance_suggestions_batch

    Returns:
        Formatted summary string
    """
    total = stats["total_count"]
    enhanced = stats["enhanced_count"]
    enhanced_pct = (enhanced / total * 100) if total > 0 else 0
    avg_improvement = stats["avg_improvement"]

    summary = f"""
Enhancement Summary:
  Total suggestions: {total}
  Enhanced: {enhanced} ({enhanced_pct:.1f}%)
  Already specific: {stats['skipped_already_specific']}
  No applicable entities: {stats['skipped_no_entities']}
  Average improvement: +{avg_improvement:.3f}
"""

    return summary.strip()


# Self-test
if __name__ == "__main__":
    print("=" * 80)
    print("SUGGESTION ENHANCER - MODULE SELF-TEST")
    print("=" * 80)

    # Test entities
    test_entities = {
        "visit_names": ["Baseline", "Week 4", "Week 12"],
        "timepoints": ["Day 2", "Day 8"],
        "assessment_types": ["safety labs", "vital signs", "ECG"],
        "safety_thresholds": ["Grade 3+ AE", "ALT >2.5x ULN"],
        "document_refs": ["MOP Section 6.2.4"],
        "conditional_triggers": []
    }

    # Test Case 1: Generic visit schedule suggestion
    print("\nTest 1: Enhance generic visit schedule suggestion")
    print("-" * 80)
    suggestion1 = {
        "improved_text": "Clarify visit schedule and add timing windows.",
        "recommendation": "Specify visit timing",
        "specificity_score": 0.2,
        "specificity_level": "generic"
    }

    enhanced1, was_enhanced1 = enhance_suggestion_specificity(suggestion1, test_entities)
    print(f"Original: {suggestion1['improved_text']}")
    print(f"Enhanced: {enhanced1['improved_text']}")
    print(f"Score: {suggestion1['specificity_score']:.3f} → {enhanced1['specificity_score']:.3f}")
    print(f"Applied: {was_enhanced1}")

    # Test Case 2: Generic assessment suggestion
    print("\nTest 2: Enhance generic assessment suggestion")
    print("-" * 80)
    suggestion2 = {
        "improved_text": "Specify assessments and clarify timing.",
        "recommendation": "Add assessment details",
        "specificity_score": 0.25,
        "specificity_level": "generic"
    }

    enhanced2, was_enhanced2 = enhance_suggestion_specificity(suggestion2, test_entities)
    print(f"Original: {suggestion2['improved_text']}")
    print(f"Enhanced: {enhanced2['improved_text']}")
    print(f"Score: {suggestion2['specificity_score']:.3f} → {enhanced2['specificity_score']:.3f}")
    print(f"Applied: {was_enhanced2}")

    # Test Case 3: Already specific (should not enhance)
    print("\nTest 3: Skip already specific suggestion")
    print("-" * 80)
    suggestion3 = {
        "improved_text": "Add visits at Baseline, Week 4, and Week 12 (±7 days) with safety labs and ECG.",
        "recommendation": "Reference MOP Section 6.2.4",
        "specificity_score": 0.85,
        "specificity_level": "highly_specific"
    }

    enhanced3, was_enhanced3 = enhance_suggestion_specificity(suggestion3, test_entities)
    print(f"Original: {suggestion3['improved_text']}")
    print(f"Enhanced: {enhanced3['improved_text']}")
    print(f"Score: {suggestion3['specificity_score']:.3f}")
    print(f"Applied: {was_enhanced3} (expected: False)")

    # Test Case 4: Batch enhancement
    print("\nTest 4: Batch enhancement")
    print("-" * 80)
    batch_suggestions = [suggestion1.copy(), suggestion2.copy(), suggestion3.copy()]
    result = enhance_suggestions_batch(batch_suggestions, test_entities, threshold=0.4)

    print(get_enhancement_summary(result["stats"]))

    print("\n" + "=" * 80)
    print("✅ MODULE SELF-TEST COMPLETE")
    print("=" * 80)
