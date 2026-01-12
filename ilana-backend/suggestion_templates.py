#!/usr/bin/env python3
"""
Suggestion Templates System

Provides fillable templates for common amendment patterns to guide specific,
protocol-aware suggestions. Templates are based on historical amendment frequency
data from amendment_risk_patterns.json.

Templates help convert generic suggestions like "clarify procedures" into specific
suggestions like "specify visits on Day 2 and Day 8 after missed vaccination with
Grade 3+ AE criteria per MOP Section 6.2.4".

Usage:
    from suggestion_templates import find_applicable_templates, format_template_context

    entities = {
        "timepoints": ["Day 2", "Day 8"],
        "safety_thresholds": ["Grade 3+ AE"],
        "document_refs": ["MOP Section 6.2.4"]
    }

    text = "Visits will not be conducted unless safety concern"
    templates = find_applicable_templates(text, entities)
    context = format_template_context(templates)

Author: Ilana AI Team
Date: 2026-01-11
Week: 4 (Template System)
"""

import re
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# TEMPLATE LIBRARY
# =============================================================================

TEMPLATES = {
    "conditional_visit_undefined": {
        "template_id": "conditional_visit_undefined",
        "name": "Conditional Visit Undefined",
        "description": "Visits conditional on vague criteria like 'safety concern' or 'discretion'",
        "amendment_rate": 0.78,  # 78% amendment rate from historical data
        "pattern": r"(?:unless|if)\s+(?:there\s+is\s+)?(?:a\s+)?(safety\s+concern|participant\s+safety|investigator(?:'?s)?\s+discretion|clinical(?:ly)?\s+indicated|deemed\s+necessary)",
        "template": {
            "improved_text": "Define '{trigger}' with objective criteria: (1) {threshold_1}, (2) {threshold_2}, or (3) clinical symptom requiring medical evaluation per {document_ref}. {visit_context} visit will be conducted if any criteria met.",
            "recommendation": "Add specific definition of '{trigger}' including: {threshold_list} and reference {document_ref} for detailed criteria.",
            "required_entities": ["threshold_1"],
            "optional_entities": ["threshold_2", "visit_name", "timepoint_1", "document_ref"]
        },
        "example": {
            "before": "Visits will not be conducted unless safety concern",
            "after": "Define 'safety concern' with objective criteria: (1) Grade 3+ treatment-related AE, (2) ALT >2.5x ULN, or (3) clinical symptom requiring medical evaluation per MOP Section 6.2.4. Day 8 visit will be conducted if any criteria met."
        }
    },

    "missed_vaccination_visits": {
        "template_id": "missed_vaccination_visits",
        "name": "Missed Vaccination Visits",
        "description": "Visit schedule after missed vaccination/dose not specified",
        "amendment_rate": 0.72,  # Estimated from discontinuation amendments
        "pattern": r"after\s+(?:the\s+)?missed\s+(vaccination|dose|treatment|study\s+product)",
        "template": {
            "improved_text": "Visits on {timepoint_1} and {timepoint_2} after the missed {item} will not be conducted unless there is {condition} (defined as {threshold_1} or {threshold_2} per {document_ref}).",
            "recommendation": "Specify which visits are skipped after missed {item} ({timepoint_1}, {timepoint_2}) and define exception criteria ({threshold_1}, {threshold_2}) in {document_ref}.",
            "required_entities": ["timepoint_1"],
            "optional_entities": ["timepoint_2", "threshold_1", "threshold_2", "document_ref"]
        },
        "example": {
            "before": "Follow-up after missed vaccination(s)",
            "after": "Visits on Day 2 and Day 8 after the missed vaccination will not be conducted unless there is safety concern (defined as Grade 3+ AE or ALT >2.5x ULN per MOP Section 6.2.4)."
        }
    },

    "assessment_timing_vague": {
        "template_id": "assessment_timing_vague",
        "name": "Assessment Timing Vague",
        "description": "Assessment timepoint mentioned without specific timing or window",
        "amendment_rate": 0.79,  # 79% amendment rate from historical data
        "pattern": r"(assessment|lab|vital\s+sign|ECG|imaging)(?:s)?\s+(?:at|during|for)\s+(?:the\s+)?(\w+\s+\d+|\w+)",
        "template": {
            "improved_text": "Conduct {assessment_1} and {assessment_2} at {timepoint_1} (±{window} window) and {timepoint_2} (±{window} window). See {document_ref} for detailed procedures.",
            "recommendation": "Add specific timing windows for {assessment_1} at {timepoint_list} with ±{window} windows. Reference {document_ref} for procedure details.",
            "required_entities": ["assessment_1", "timepoint_1"],
            "optional_entities": ["assessment_2", "timepoint_2", "visit_name", "document_ref"]
        },
        "example": {
            "before": "Safety assessment at baseline",
            "after": "Conduct safety labs and vital signs at Baseline (±3 day window) and Week 4 (±7 day window). See MOP Chapter 4 for detailed procedures."
        }
    },

    "safety_labs_as_indicated": {
        "template_id": "safety_labs_as_indicated",
        "name": "Safety Labs As Indicated",
        "description": "Safety labs mentioned as 'clinically indicated' without specific criteria",
        "amendment_rate": 0.63,  # 63% amendment rate from historical data
        "pattern": r"(safety\s+lab|laboratory|assessment|monitoring)(?:s)?\s+as\s+(clinically\s+indicated|needed|appropriate|deemed\s+necessary)",
        "template": {
            "improved_text": "Safety labs as clinically indicated include: {assessment_1}, {assessment_2}, and additional labs for Grade 3+ abnormalities per {document_ref}. Required if {threshold_1} or {threshold_2} observed.",
            "recommendation": "Define 'clinically indicated' criteria for safety labs: {threshold_list}. List specific labs ({assessment_list}) and reference {document_ref} for abnormality thresholds.",
            "required_entities": ["assessment_1"],
            "optional_entities": ["assessment_2", "threshold_1", "threshold_2", "document_ref"]
        },
        "example": {
            "before": "Safety labs as clinically indicated per protocol",
            "after": "Safety labs as clinically indicated include: CBC, CMP, LFTs, and additional labs for Grade 3+ abnormalities per Table 5. Required if ALT >2.5x ULN or ANC <1000 cells/μL observed."
        }
    },

    "document_reference_missing": {
        "template_id": "document_reference_missing",
        "name": "Document Reference Missing",
        "description": "Procedures mentioned but not cross-referenced to specific document section",
        "amendment_rate": 0.68,  # Estimated from documentation amendments
        "pattern": r"(procedure|protocol|plan|assessment|criteria|guideline)(?:s)?\s+(?:described|outlined|detailed|specified|defined)(?:\s+in\s+(?:the\s+)?(?:protocol|study|document))?(?!\s+(?:in|per)\s+\w+)",
        "template": {
            "improved_text": "{original_phrase} in {document_ref}. See {document_ref} for: (1) {detail_1}, (2) {detail_2}, and (3) {detail_3}.",
            "recommendation": "Add specific document reference for {procedure}: cite {document_ref} with section number and key details ({detail_list}).",
            "required_entities": ["document_ref"],
            "optional_entities": ["assessment_1", "threshold_1", "timepoint_1"]
        },
        "example": {
            "before": "Procedures described in protocol",
            "after": "Procedures described in MOP Chapter 3. See MOP Section 3.2 for: (1) discontinuation criteria, (2) follow-up schedule, and (3) safety monitoring requirements."
        }
    }
}


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def find_applicable_templates(
    text: str,
    entities: Optional[Dict[str, List[str]]] = None
) -> List[Dict[str, Any]]:
    """
    Find templates that match patterns in the text

    Args:
        text: Protocol text to analyze for template patterns
        entities: Extracted protocol entities (optional, used for entity availability check)

    Returns:
        List of applicable templates with matched patterns:
        [
            {
                "template_id": "conditional_visit_undefined",
                "name": "Conditional Visit Undefined",
                "pattern": "unless safety concern",
                "matched_text": "unless safety concern",
                "match_position": (45, 67),
                "template": {...},
                "available_entities": {...}
            },
            ...
        ]

    Example:
        >>> text = "Visits will not be conducted unless safety concern"
        >>> templates = find_applicable_templates(text)
        >>> len(templates)
        1
        >>> templates[0]["template_id"]
        'conditional_visit_undefined'
    """
    if not text:
        return []

    applicable = []

    for template_id, template_data in TEMPLATES.items():
        pattern = template_data.get("pattern")
        if not pattern:
            continue

        try:
            # Search for pattern in text (case insensitive)
            matches = list(re.finditer(pattern, text, re.IGNORECASE))

            if matches:
                for match in matches:
                    # Determine which entities are available for this template
                    available_entities = {}
                    if entities:
                        available_entities = _get_available_entities_for_template(
                            template_data,
                            entities
                        )

                    applicable.append({
                        "template_id": template_id,
                        "name": template_data.get("name", template_id),
                        "description": template_data.get("description", ""),
                        "amendment_rate": template_data.get("amendment_rate", 0.0),
                        "pattern": pattern,
                        "matched_text": match.group(0),
                        "match_position": match.span(),
                        "template": template_data.get("template", {}),
                        "example": template_data.get("example", {}),
                        "available_entities": available_entities
                    })

                    logger.info(
                        f"Template match: {template_id} at position {match.span()}, "
                        f"text: '{match.group(0)}', entities available: {len(available_entities)}"
                    )

        except re.error as e:
            logger.error(f"Invalid regex pattern in template {template_id}: {e}")
            continue

    # Sort by amendment rate (highest first) then by position in text
    applicable.sort(key=lambda t: (-t["amendment_rate"], t["match_position"][0]))

    logger.info(f"Found {len(applicable)} applicable template(s) in text")

    return applicable


def instantiate_template(
    template: Dict[str, Any],
    entities: Dict[str, List[str]],
    matched_text: str = ""
) -> Dict[str, Any]:
    """
    Fill template placeholders with actual protocol entities

    Args:
        template: Template dict with "template" key containing improved_text, recommendation
        entities: Extracted protocol entities
        matched_text: The actual text that matched the pattern (optional)

    Returns:
        {
            "improved_text": "filled template text",
            "recommendation": "filled recommendation text",
            "entities_used": ["Day 2", "Grade 3+ AE", ...],
            "placeholders_filled": ["timepoint_1", "threshold_1", ...],
            "placeholders_missing": ["timepoint_2", ...],
            "template_id": "conditional_visit_undefined"
        }

    Example:
        >>> template = TEMPLATES["missed_vaccination_visits"]
        >>> entities = {
        ...     "timepoints": ["Day 2", "Day 8"],
        ...     "safety_thresholds": ["Grade 3+ AE"]
        ... }
        >>> result = instantiate_template(template, entities)
        >>> "Day 2" in result["improved_text"]
        True
    """
    if not template or not isinstance(template, dict):
        logger.warning("Invalid template provided to instantiate_template")
        return {
            "improved_text": "",
            "recommendation": "",
            "entities_used": [],
            "placeholders_filled": [],
            "placeholders_missing": [],
            "error": "Invalid template"
        }

    template_content = template.get("template", {})
    template_id = template.get("template_id", "unknown")

    improved_text = template_content.get("improved_text", "")
    recommendation = template_content.get("recommendation", "")

    # Track what we fill and what we can't
    entities_used = []
    placeholders_filled = []
    placeholders_missing = []

    # Build entity mapping (placeholder -> entity value)
    entity_mapping = _build_entity_mapping(entities, matched_text)

    # Find all placeholders in improved_text and recommendation
    all_text = improved_text + " " + recommendation
    placeholders = re.findall(r'\{(\w+)\}', all_text)

    # Fill placeholders
    for placeholder in set(placeholders):
        if placeholder in entity_mapping:
            value = entity_mapping[placeholder]
            improved_text = improved_text.replace(f"{{{placeholder}}}", value)
            recommendation = recommendation.replace(f"{{{placeholder}}}", value)
            entities_used.append(value)
            placeholders_filled.append(placeholder)
        else:
            placeholders_missing.append(placeholder)

    # Remove any remaining unfilled placeholders (replace with generic text)
    improved_text = re.sub(r'\{(\w+)\}', r'[\1]', improved_text)
    recommendation = re.sub(r'\{(\w+)\}', r'[\1]', recommendation)

    # Clean up any double spaces or awkward punctuation
    improved_text = re.sub(r'\s+', ' ', improved_text).strip()
    recommendation = re.sub(r'\s+', ' ', recommendation).strip()

    result = {
        "improved_text": improved_text,
        "recommendation": recommendation,
        "entities_used": list(set(entities_used)),  # deduplicate
        "placeholders_filled": placeholders_filled,
        "placeholders_missing": placeholders_missing,
        "template_id": template_id,
        "completeness": len(placeholders_filled) / len(placeholders) if placeholders else 0.0
    }

    logger.info(
        f"Instantiated template {template_id}: "
        f"{len(placeholders_filled)}/{len(placeholders)} placeholders filled, "
        f"{len(entities_used)} entities used"
    )

    return result


def format_template_context(
    applicable_templates: List[Dict[str, Any]],
    max_templates: int = 2
) -> str:
    """
    Format templates for prompt injection

    Args:
        applicable_templates: List of applicable templates from find_applicable_templates()
        max_templates: Maximum number of templates to include in context (default: 2)

    Returns:
        Formatted string for prompt injection:

        APPLICABLE SUGGESTION TEMPLATES:

        Template 1: Conditional Visit Undefined (78% amendment rate)
        Pattern detected: "unless safety concern"

        Example transformation:
        BEFORE: "Visits will not be conducted unless safety concern"
        AFTER: "Define 'safety concern' with objective criteria: (1) Grade 3+ AE, ..."

        When making suggestions, use this template structure with protocol-specific entities.

    Example:
        >>> templates = find_applicable_templates("unless safety concern")
        >>> context = format_template_context(templates)
        >>> "Conditional Visit Undefined" in context
        True
    """
    if not applicable_templates:
        return ""

    # Limit to max_templates (top-ranked)
    templates_to_show = applicable_templates[:max_templates]

    lines = [
        "=" * 80,
        "APPLICABLE SUGGESTION TEMPLATES",
        "=" * 80,
        "",
        "The following templates match patterns in the selected text.",
        "Use these structures to create specific, protocol-aware suggestions.",
        ""
    ]

    for i, template in enumerate(templates_to_show, 1):
        template_id = template.get("template_id", "unknown")
        name = template.get("name", template_id)
        description = template.get("description", "")
        amendment_rate = template.get("amendment_rate", 0.0)
        matched_text = template.get("matched_text", "")
        example = template.get("example", {})

        lines.append(f"Template {i}: {name}")
        lines.append(f"Amendment Rate: {amendment_rate*100:.0f}% (high-priority pattern)")
        if description:
            lines.append(f"Description: {description}")
        if matched_text:
            lines.append(f"Detected pattern: \"{matched_text}\"")
        lines.append("")

        if example:
            before = example.get("before", "")
            after = example.get("after", "")
            if before and after:
                lines.append("Example transformation:")
                lines.append(f"  BEFORE: \"{before}\"")
                lines.append(f"  AFTER: \"{after}\"")
                lines.append("")

        # Show available entities for this template
        available = template.get("available_entities", {})
        if available:
            lines.append("Available protocol entities to use:")
            for entity_type, entity_list in available.items():
                if entity_list:
                    entity_str = ", ".join(entity_list[:3])  # Show first 3
                    if len(entity_list) > 3:
                        entity_str += f" (and {len(entity_list)-3} more)"
                    lines.append(f"  - {entity_type}: {entity_str}")
            lines.append("")

        lines.append("-" * 80)
        lines.append("")

    lines.append("INSTRUCTIONS:")
    lines.append("When making suggestions, follow the template structure above and fill with")
    lines.append("specific protocol entities (visits, timepoints, thresholds, documents).")
    lines.append("=" * 80)
    lines.append("")

    formatted = "\n".join(lines)

    logger.info(
        f"Formatted template context: {len(templates_to_show)} template(s), "
        f"{len(formatted)} chars"
    )

    return formatted


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_available_entities_for_template(
    template_data: Dict[str, Any],
    entities: Dict[str, List[str]]
) -> Dict[str, List[str]]:
    """
    Determine which entities are available for filling this template

    Args:
        template_data: Template definition
        entities: Extracted protocol entities

    Returns:
        Dict of entity_type -> list of values available for this template
    """
    if not entities:
        return {}

    # Map template placeholders to entity types
    placeholder_to_entity_type = {
        "timepoint_1": "timepoints",
        "timepoint_2": "timepoints",
        "visit_name": "visit_names",
        "assessment_1": "assessment_types",
        "assessment_2": "assessment_types",
        "threshold_1": "safety_thresholds",
        "threshold_2": "safety_thresholds",
        "document_ref": "document_refs",
        "condition": "conditional_triggers",
    }

    available = {}

    for entity_type in ["visit_names", "timepoints", "assessment_types",
                       "safety_thresholds", "document_refs", "conditional_triggers"]:
        if entity_type in entities and entities[entity_type]:
            available[entity_type] = entities[entity_type]

    return available


def _build_entity_mapping(
    entities: Dict[str, List[str]],
    matched_text: str = ""
) -> Dict[str, str]:
    """
    Build a mapping of template placeholders to actual entity values

    Args:
        entities: Extracted protocol entities
        matched_text: The text that matched the pattern (used to extract trigger words)

    Returns:
        Dict mapping placeholder names to entity values:
        {
            "timepoint_1": "Day 2",
            "timepoint_2": "Day 8",
            "threshold_1": "Grade 3+ AE",
            ...
        }
    """
    mapping = {}

    if not entities:
        return mapping

    # Extract trigger word from matched text if available
    if matched_text:
        # Extract the trigger phrase (e.g., "safety concern" from "unless safety concern")
        trigger_match = re.search(
            r'(safety\s+concern|participant\s+safety|investigator(?:\'?s)?\s+discretion|'
            r'clinical(?:ly)?\s+indicated|deemed\s+necessary)',
            matched_text,
            re.IGNORECASE
        )
        if trigger_match:
            mapping["trigger"] = trigger_match.group(1)

        # Extract item type (vaccination, dose, treatment)
        item_match = re.search(
            r'(vaccination|dose|treatment|study\s+product)',
            matched_text,
            re.IGNORECASE
        )
        if item_match:
            mapping["item"] = item_match.group(1)

    # Map timepoints
    timepoints = entities.get("timepoints", [])
    if len(timepoints) >= 1:
        mapping["timepoint_1"] = timepoints[0]
    if len(timepoints) >= 2:
        mapping["timepoint_2"] = timepoints[1]
    if timepoints:
        mapping["timepoint_list"] = ", ".join(timepoints[:3])

    # Map visits
    visits = entities.get("visit_names", [])
    if len(visits) >= 1:
        mapping["visit_name"] = visits[0]
        mapping["visit_context"] = visits[0]
    if visits:
        mapping["visit_list"] = ", ".join(visits[:3])

    # Map assessments
    assessments = entities.get("assessment_types", [])
    if len(assessments) >= 1:
        mapping["assessment_1"] = assessments[0]
    if len(assessments) >= 2:
        mapping["assessment_2"] = assessments[1]
    if assessments:
        mapping["assessment_list"] = ", ".join(assessments[:3])

    # Map thresholds
    thresholds = entities.get("safety_thresholds", [])
    if len(thresholds) >= 1:
        mapping["threshold_1"] = thresholds[0]
    if len(thresholds) >= 2:
        mapping["threshold_2"] = thresholds[1]
    if len(thresholds) >= 3:
        mapping["threshold_3"] = thresholds[2]
    if thresholds:
        mapping["threshold_list"] = ", ".join(thresholds[:3])

    # Map documents
    documents = entities.get("document_refs", [])
    if len(documents) >= 1:
        mapping["document_ref"] = documents[0]
    if documents:
        mapping["document_list"] = ", ".join(documents[:3])

    # Map conditions/triggers
    conditions = entities.get("conditional_triggers", [])
    if len(conditions) >= 1:
        mapping["condition"] = conditions[0]

    # Default values for common placeholders
    mapping.setdefault("window", "7 day")
    mapping.setdefault("detail_1", "specific criteria")
    mapping.setdefault("detail_2", "procedure steps")
    mapping.setdefault("detail_3", "documentation requirements")

    if thresholds:
        mapping.setdefault("detail_list", ", ".join(thresholds[:2]))

    # Extract original phrase for document_reference_missing template
    if matched_text:
        phrase_match = re.search(
            r'(procedure|protocol|plan|assessment|criteria|guideline)(?:s)?\s+'
            r'(?:described|outlined|detailed|specified|defined)',
            matched_text,
            re.IGNORECASE
        )
        if phrase_match:
            mapping["original_phrase"] = phrase_match.group(0)
            mapping["procedure"] = phrase_match.group(1)

    return mapping


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_template_by_id(template_id: str) -> Optional[Dict[str, Any]]:
    """Get template definition by ID"""
    return TEMPLATES.get(template_id)


def list_all_templates() -> List[Dict[str, Any]]:
    """List all available templates sorted by amendment rate"""
    templates = [
        {
            "template_id": tid,
            "name": data.get("name", tid),
            "description": data.get("description", ""),
            "amendment_rate": data.get("amendment_rate", 0.0)
        }
        for tid, data in TEMPLATES.items()
    ]
    return sorted(templates, key=lambda t: -t["amendment_rate"])


# =============================================================================
# MODULE TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("SUGGESTION TEMPLATES MODULE TEST")
    print("=" * 80)

    # Test 1: Find templates
    print("\nTest 1: Template Matching")
    test_text = "Visits will not be conducted unless safety concern. Safety labs as clinically indicated."

    templates = find_applicable_templates(test_text)
    print(f"Found {len(templates)} template(s)")
    for t in templates:
        print(f"  - {t['name']} (matched: '{t['matched_text']}')")

    # Test 2: Instantiate template
    print("\nTest 2: Template Instantiation")
    test_entities = {
        "timepoints": ["Day 2", "Day 8"],
        "visit_names": ["Baseline", "Week 4"],
        "assessment_types": ["safety labs", "vital signs"],
        "safety_thresholds": ["Grade 3+ AE", "ALT >2.5x ULN"],
        "document_refs": ["MOP Section 6.2.4"]
    }

    if templates:
        result = instantiate_template(templates[0], test_entities, templates[0]['matched_text'])
        print(f"Completeness: {result['completeness']*100:.0f}%")
        print(f"Entities used: {result['entities_used']}")
        print(f"Improved text: {result['improved_text'][:100]}...")

    # Test 3: Format context
    print("\nTest 3: Format Template Context")
    context = format_template_context(templates, max_templates=1)
    print(f"Context length: {len(context)} chars")
    print(context[:300] + "...\n")

    print("=" * 80)
    print("✅ MODULE TEST COMPLETE")
    print("=" * 80)
