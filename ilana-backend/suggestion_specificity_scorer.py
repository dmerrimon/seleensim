"""
Suggestion Specificity Scorer

Measures how specific protocol suggestions are based on entity usage and generic phrase detection.

Scoring System:
- 0.0-0.3: Generic ("clarify procedures")
- 0.4-0.6: Partially Specific ("specify visit windows")
- 0.7-1.0: Highly Specific ("add Day 2 and Day 8 visits with Grade 3+ AE criteria")

Author: Ilana AI Team
Date: 2026-01-11
"""

import re
from typing import Dict, List, Any


# Generic phrases that indicate non-specific suggestions
GENERIC_PHRASES = [
    r"\bclarif(?:y|ies|ied)\b",
    r"\badd more detail\b",
    r"\bspecif(?:y|ies|ied)\b(?! \w+(?:\s+\w+){0,2}\s+(?:Day|Week|Month|Grade|Table|Section|MOP))",  # Only generic "specify" without entities
    r"\bconsider adding\b",
    r"\bshould include\b",
    r"\bmore specific\b",
    r"\bprovide additional\b",
    r"\binclude information about\b",
    r"\badd information\b",
    r"\bdefine\b(?! \w+(?:\s+\w+){0,2}\s+(?:as|per|in))",  # Generic "define" without specifics
    r"\bexplain\b",
    r"\bdescribe\b(?! \w+(?:\s+\w+){0,2}\s+(?:in|as|per))",  # Generic "describe"
]


def detect_generic_phrases(text: str) -> List[str]:
    """
    Detect generic phrases in suggestion text

    Args:
        text: Suggestion text to analyze

    Returns:
        List of generic phrases found

    Examples:
        >>> detect_generic_phrases("Clarify the procedures and add more detail")
        ['Clarify', 'add more detail']

        >>> detect_generic_phrases("Add visits on Day 2 and Day 8")
        []  # Specific suggestion, no generic phrases
    """
    if not text:
        return []

    found_phrases = []
    text_lower = text.lower()

    for pattern in GENERIC_PHRASES:
        matches = re.finditer(pattern, text_lower, re.IGNORECASE)
        for match in matches:
            phrase = match.group(0)
            # Capitalize first letter for display
            phrase = phrase[0].upper() + phrase[1:] if phrase else phrase
            if phrase not in found_phrases:
                found_phrases.append(phrase)

    return found_phrases


def count_entity_references(text: str, entities: Dict[str, List[str]]) -> Dict[str, int]:
    """
    Count entity references in suggestion text by category

    Args:
        text: Suggestion text to analyze
        entities: Dictionary of protocol entities by type

    Returns:
        Dictionary with counts per entity type

    Example:
        >>> entities = {"timepoints": ["Day 2", "Day 8"], "thresholds": ["Grade 3+"]}
        >>> count_entity_references("Add Day 2 and Day 8 visits with Grade 3+ monitoring", entities)
        {'timepoints': 2, 'thresholds': 1, 'visits': 0, 'assessments': 0, 'documents': 0}
    """
    if not text or not entities:
        return {
            "visit_names": 0,
            "timepoints": 0,
            "assessment_types": 0,
            "safety_thresholds": 0,
            "document_refs": 0,
            "conditional_triggers": 0
        }

    text_lower = text.lower()
    counts = {
        "visit_names": 0,
        "timepoints": 0,
        "assessment_types": 0,
        "safety_thresholds": 0,
        "document_refs": 0,
        "conditional_triggers": 0
    }

    # Count references for each entity type
    for entity_type, entity_list in entities.items():
        if entity_type not in counts:
            counts[entity_type] = 0

        for entity in entity_list:
            # Case-insensitive exact match or word boundary match
            entity_lower = entity.lower()

            # For multi-word entities, check exact phrase
            if ' ' in entity_lower:
                if entity_lower in text_lower:
                    counts[entity_type] += 1
            else:
                # For single-word entities, use word boundaries
                pattern = r'\b' + re.escape(entity_lower) + r'\b'
                if re.search(pattern, text_lower):
                    counts[entity_type] += 1

    return counts


def score_suggestion_specificity(
    suggestion: Dict[str, Any],
    entities: Dict[str, List[str]]
) -> float:
    """
    Score suggestion specificity based on entity usage

    Scoring Criteria (additive, max 1.0):
    - References specific visits/timepoints: +0.2
    - References specific assessments: +0.2
    - References specific thresholds: +0.2
    - References specific documents: +0.2
    - Contains specific values/numbers: +0.2
    - Penalize generic phrases: -0.1 per phrase (min 0.0)

    Args:
        suggestion: Suggestion dictionary with 'improved_text' or 'text' field
        entities: Dictionary of protocol entities by type

    Returns:
        Specificity score (0.0-1.0)

    Examples:
        >>> suggestion = {"improved_text": "Clarify discontinuation procedures"}
        >>> entities = {"timepoints": ["Day 2"]}
        >>> score_suggestion_specificity(suggestion, entities)
        0.1  # Generic phrases detected, no entities

        >>> suggestion = {"improved_text": "Add Day 2 and Day 8 visits with Grade 3+ AE monitoring per MOP"}
        >>> entities = {"timepoints": ["Day 2", "Day 8"], "thresholds": ["Grade 3+"], "documents": ["MOP"]}
        >>> score_suggestion_specificity(suggestion, entities)
        0.8  # Multiple entity categories referenced
    """
    # Extract text from suggestion
    text = suggestion.get("improved_text") or suggestion.get("text", "")
    if not text:
        return 0.0

    score = 0.0

    # Count entity references
    entity_counts = count_entity_references(text, entities)

    # Award points for each entity category that has ≥1 reference
    # Visits/Timepoints
    if entity_counts.get("visit_names", 0) > 0 or entity_counts.get("timepoints", 0) > 0:
        score += 0.2

    # Assessments
    if entity_counts.get("assessment_types", 0) > 0:
        score += 0.2

    # Safety thresholds
    if entity_counts.get("safety_thresholds", 0) > 0:
        score += 0.2

    # Document references
    if entity_counts.get("document_refs", 0) > 0:
        score += 0.2

    # Check for specific numeric values (in case entities didn't capture them)
    # Look for patterns like: "Day 2", "Week 4", "Grade 3+", "ALT >2.5x", ">75,000", etc.
    numeric_patterns = [
        r"\b(?:Day|Week|Month|Visit|Cycle|Hour)\s+\d+",
        r"\bGrade\s+\d+",
        r"\b(?:ALT|AST|ANC|platelet|hemoglobin)\s*[><=]+\s*[\d.]+",
        r"[><=]+\s*[\d,]+\s*(?:cells|units|mg|ULN)",
        r"\d+\s*(?:hours?|days?|weeks?|months?)",
    ]

    has_numeric_specifics = False
    for pattern in numeric_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            has_numeric_specifics = True
            break

    if has_numeric_specifics:
        score += 0.2

    # Penalize generic phrases (-0.1 per phrase, minimum score 0.0)
    generic_phrases = detect_generic_phrases(text)
    penalty = len(generic_phrases) * 0.1
    score = max(0.0, score - penalty)

    # Cap at 1.0
    return min(1.0, score)


def classify_specificity(score: float) -> str:
    """
    Classify specificity level based on score

    Args:
        score: Specificity score (0.0-1.0)

    Returns:
        Classification: "generic", "partially_specific", or "highly_specific"

    Classification Ranges:
        - 0.0-0.3: generic
        - 0.4-0.6: partially_specific
        - 0.7-1.0: highly_specific

    Examples:
        >>> classify_specificity(0.2)
        'generic'

        >>> classify_specificity(0.5)
        'partially_specific'

        >>> classify_specificity(0.8)
        'highly_specific'
    """
    if score <= 0.3:
        return "generic"
    elif score <= 0.6:
        return "partially_specific"
    else:
        return "highly_specific"


# For testing purposes
if __name__ == "__main__":
    # Test Case 1: Generic suggestion
    generic_suggestion = {
        "improved_text": "Clarify discontinuation procedures and add more detail."
    }
    entities = {
        "timepoints": ["Day 2", "Day 8"],
        "safety_thresholds": ["Grade 3+"],
        "document_refs": ["MOP"]
    }

    score1 = score_suggestion_specificity(generic_suggestion, entities)
    level1 = classify_specificity(score1)
    phrases1 = detect_generic_phrases(generic_suggestion["improved_text"])

    print("Test 1: Generic Suggestion")
    print(f"  Text: {generic_suggestion['improved_text']}")
    print(f"  Score: {score1:.3f}")
    print(f"  Level: {level1}")
    print(f"  Generic phrases: {phrases1}")
    print()

    # Test Case 2: Highly specific suggestion
    specific_suggestion = {
        "improved_text": "Add visits on Day 2 and Day 8 after missed vaccination. Define safety concern as Grade 3+ AE per MOP Section 6.2.4."
    }

    score2 = score_suggestion_specificity(specific_suggestion, entities)
    level2 = classify_specificity(score2)
    entity_refs = count_entity_references(specific_suggestion["improved_text"], entities)

    print("Test 2: Highly Specific Suggestion")
    print(f"  Text: {specific_suggestion['improved_text']}")
    print(f"  Score: {score2:.3f}")
    print(f"  Level: {level2}")
    print(f"  Entity references: {entity_refs}")
    print()

    print("✅ Module loaded successfully")
