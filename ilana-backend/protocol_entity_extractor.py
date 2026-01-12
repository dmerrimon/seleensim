"""
Protocol Entity Extractor for Contextual Intelligence

Extracts protocol-specific entities from text to enable specific, context-aware suggestions.

Entities extracted:
- Visit names (Baseline, Week 4, Follow-up)
- Assessment types (safety labs, vital signs, immunogenicity)
- Timepoints (Day 2, Day 8, Week 12)
- Safety thresholds (Grade 3+ AE, ALT >2.5x ULN)
- Document references (SAP Section 3.2, MOP, Table 5)
- Conditional triggers (unless safety concern, after missed vaccination)

Usage:
    from protocol_entity_extractor import extract_protocol_entities

    entities = extract_protocol_entities(text, timeline)
    # Returns: {
    #     "visit_names": ["Baseline", "Week 4"],
    #     "assessment_types": ["safety labs", "vital signs"],
    #     "timepoints": ["Day 2", "Day 8"],
    #     "safety_thresholds": ["Grade 3+ AE"],
    #     "document_refs": ["SAP Section 3.2", "MOP"],
    #     "conditional_triggers": ["safety concern"]
    # }
"""

import re
import logging
from typing import List, Dict, Optional, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import Timeline from timeline_parser, fallback to Any if not available
try:
    from timeline_parser import Timeline, Visit
except ImportError:
    Timeline = None
    Visit = None
    logger.warning("timeline_parser not available, timeline integration disabled")


# ============================================================================
# EXTRACTION PATTERN LIBRARIES
# ============================================================================

# Visit name patterns (in addition to timeline data)
VISIT_NAME_PATTERNS = [
    r"\b(?:Baseline|Screening|Enrollment)\b",
    r"\b(?:Follow-up|Follow up|End of Study|EOS|Final Visit)\b",
    r"\bDay\s+\d+(?:\s+visit)?\b",
    r"\bWeek\s+\d+(?:\s+visit)?\b",
    r"\bMonth\s+\d+(?:\s+visit)?\b",
    r"\bVisit\s+\d+\b",
    r"\b[Cc]\d+[Dd]\d+\b",  # Oncology cycle notation: C1D1, C2D15
]

# Assessment type patterns
ASSESSMENT_TYPE_PATTERNS = {
    "safety labs": r"\b(?:safety\s+)?(?:laboratory|lab|labs)(?:\s+assessments?|s)?\b",
    "vital signs": r"\bvital\s+signs?\b",
    "physical exam": r"\bphysical\s+exam(?:ination)?\b",
    "ECG": r"\b(?:ECG|electrocardiogram|EKG)\b",
    "immunogenicity": r"\bimmunogenicity(?:\s+assessments?|s|samples?)?\b",
    "PK": r"\b(?:PK|pharmacokinetic)(?:\s+samples?|assessments?)?\b",
    "PD": r"\b(?:PD|pharmacodynamic)(?:\s+samples?|assessments?)?\b",
    "biomarkers": r"\bbiomarkers?\b",
    "imaging": r"\b(?:imaging|MRI|CT|PET|X-ray)\b",
    "tumor assessment": r"\btumor\s+(?:assessment|evaluation|measurement)\b",
    "RECIST": r"\bRECIST(?:\s+1\.1)?\b",
    "EORTC QLQ": r"\bEORTC\s+QLQ\b",
    "adverse events": r"\b(?:adverse\s+events?|AEs?)\b",
    "concomitant meds": r"\b(?:concomitant\s+medications?|conmeds?)\b",
}

# Timepoint patterns (Day N, Week N, Month N, cycle notation, DPO, hours)
TIMEPOINT_PATTERNS = [
    r"\bDay\s+\d+\b",
    r"\bWeek\s+\d+\b",
    r"\bMonth\s+\d+\b",
    r"\b[Cc]\d+[Dd]\d+\b",  # C1D1, C2D15
    r"\bDPO\s+\d+\b",  # Days post-onset (COVID-19, infectious disease trials)
    r"\b\d+(?:\s*-\s*\d+)?\s*(?:hours?|hrs?|h)\b",  # 48 hours, 72h, 48-72 hours (PK studies, early phase)
]

# Safety threshold patterns
SAFETY_THRESHOLD_PATTERNS = {
    "Grade": r"\bGrade\s+[1-5]\+?",
    "CTCAE": r"\bCTCAE\s+(?:Grade\s+)?[1-5]\+?",
    "ALT/AST": r"\b(?:ALT|AST)\s*[>≥]\s*\d+(?:\.\d+)?\s*[×x]\s*ULN\b",
    "Bilirubin": r"\bbilirubin\s*[>≥]\s*\d+(?:\.\d+)?\s*[×x]\s*ULN\b",
    "Creatinine": r"\bcreatinine\s*[>≥]\s*\d+(?:\.\d+)?(?:\s*mg/dL)?\b",
    "ANC": r"\bANC\s*[<≤]\s*\d+(?:,\d+)?\b",
    "Platelets": r"\bplatelets?\s*[<≤]\s*\d+(?:,\d+)?\b",
    "Hemoglobin": r"\bhemoglobin\s*[<≤]\s*\d+(?:\.\d+)?\b",
    "QTc": r"\bQTc(?:F|B)?\s*[>≥]\s*\d+\s*(?:ms|msec)?\b",
}

# Document reference patterns
DOCUMENT_REF_PATTERNS = {
    "SAP Section": r"\bSAP\s+Section\s+[\d.]+\b",
    "MOP": r"\bMOP(?:\s+(?:Chapter|Section)\s+[\d.]+)?\b",
    "Table": r"\bTable\s+[\d.]+\b",
    "Appendix": r"\bAppendix\s+[A-Z0-9]+\b",
    "Section": r"\bSection\s+[\d.]+\b",
    "Figure": r"\bFigure\s+[\d.]+\b",
    "Schedule": r"\bSchedule\s+of\s+(?:Activities|Assessments|Events)\b",
}

# Conditional trigger patterns
CONDITIONAL_TRIGGER_PATTERNS = {
    "safety concern": r"\b(?:unless|if)\s+(?:there\s+is\s+)?(?:a\s+)?safety\s+concern\b",
    "participant safety": r"\b(?:unless|if)\s+participant\s+safety\s+(?:precludes|requires)\b",
    "discretion": r"\bat\s+(?:the\s+)?discretion\s+of\s+(?:the\s+)?(?:investigator|PI|physician)\b",
    "missed vaccination": r"\bafter\s+(?:the\s+)?missed\s+(?:vaccination|dose|treatment|infusion)\b",
    "dose delay": r"\b(?:in\s+case\s+of|if)\s+dose\s+(?:delay|interruption)\b",
    "toxicity": r"\b(?:unless|if)\s+(?:unacceptable\s+)?toxicity\b",
    "progression": r"\b(?:unless|until)\s+(?:disease\s+)?progression\b",
}


# ============================================================================
# EXTRACTOR FUNCTIONS
# ============================================================================

def extract_visit_names(text: str, timeline: Optional['Timeline'] = None) -> List[str]:
    """
    Extract visit names from text and timeline

    Combines:
    1. Visit names from timeline (if available)
    2. Regex pattern matching in text

    Args:
        text: Protocol text to analyze
        timeline: Optional parsed timeline object

    Returns:
        List of unique visit names sorted by frequency
    """
    visits = set()

    # Extract from timeline if available
    if timeline and hasattr(timeline, 'visits'):
        for visit in timeline.visits:
            if hasattr(visit, 'visit_name'):
                visits.add(visit.visit_name)

    # Extract from text patterns
    for pattern in VISIT_NAME_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            visit_name = match.group(0).strip()
            visits.add(visit_name)

    # Return sorted by length (longer names first, more specific)
    return sorted(list(visits), key=len, reverse=True)[:10]  # Limit to top 10


def extract_assessment_types(text: str) -> List[str]:
    """
    Extract assessment types from text

    Args:
        text: Protocol text to analyze

    Returns:
        List of unique assessment types found
    """
    assessments = set()

    for assessment_name, pattern in ASSESSMENT_TYPE_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            assessments.add(assessment_name)

    return sorted(list(assessments))


def extract_timepoints(text: str) -> List[str]:
    """
    Extract timepoints from text (Day N, Week N, Month N, cycle notation)

    Args:
        text: Protocol text to analyze

    Returns:
        List of unique timepoints sorted by nominal days
    """
    timepoints = set()

    # First pass: extract standard timepoint patterns
    for pattern in TIMEPOINT_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            timepoint = match.group(0).strip()
            # Normalize capitalization
            timepoint = timepoint.replace("day", "Day").replace("week", "Week").replace("month", "Month")
            timepoints.add(timepoint)

    # Second pass: handle abbreviated lists like "Day 2 and 8" or "Week 4, 8, and 12"
    # Pattern 1: "(Day|Week|Month|DPO) N and M" -> extracts M
    abbreviated_pattern = r'(Day|Week|Month|DPO)\s+\d+\s+and\s+(\d+)'
    for match in re.finditer(abbreviated_pattern, text, re.IGNORECASE):
        unit_type = match.group(1).upper() if match.group(1).upper() == "DPO" else match.group(1).capitalize()
        number = match.group(2)
        timepoint = f"{unit_type} {number}"
        timepoints.add(timepoint)

    # Pattern 2: "(Day|Week|Month|DPO) N, M, ... and P" -> extracts all numbers in comma-separated list
    # Example: "Week 4, 8, and 12" or "DPO 8, 15, 30, 90, 180, and 365"
    comma_list_pattern = r'(Day|Week|Month|DPO)\s+(\d+(?:\s*,\s*\d+)*(?:\s*,?\s*and\s+\d+)?)'
    for match in re.finditer(comma_list_pattern, text, re.IGNORECASE):
        unit_type = match.group(1).upper() if match.group(1).upper() == "DPO" else match.group(1).capitalize()
        number_list_str = match.group(2)

        # Extract all numbers from the comma-separated list
        numbers = re.findall(r'\d+', number_list_str)

        # If we have multiple numbers, add them all with the unit type
        if len(numbers) > 1:
            for number in numbers:
                timepoint = f"{unit_type} {number}"
                timepoints.add(timepoint)

    # Sort by type and number
    def timepoint_sort_key(tp: str) -> tuple:
        """Sort timepoints by days from baseline"""
        tp_lower = tp.lower()

        # Extract number
        num_match = re.search(r'\d+', tp)
        if not num_match:
            return (999999, tp)  # Unknown timepoints last

        num = int(num_match.group())

        # Convert to days for sorting
        if 'dpo' in tp_lower:
            days = num  # DPO = days post-onset
        elif 'day' in tp_lower or (tp_lower.startswith('c') and 'd' in tp_lower):
            days = num  # Day N or C1D1 notation
        elif 'week' in tp_lower:
            days = num * 7
        elif 'month' in tp_lower:
            days = num * 30
        else:  # Other notation
            days = num  # Treat as days

        return (days, tp)

    sorted_timepoints = sorted(list(timepoints), key=timepoint_sort_key)
    return sorted_timepoints[:15]  # Limit to top 15


def extract_safety_thresholds(text: str) -> List[str]:
    """
    Extract safety thresholds from text (Grade 3+, ALT >2.5x ULN, etc.)

    Args:
        text: Protocol text to analyze

    Returns:
        List of unique safety thresholds found
    """
    thresholds = set()

    for threshold_type, pattern in SAFETY_THRESHOLD_PATTERNS.items():
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            threshold = match.group(0).strip()
            # Normalize capitalization and spacing
            threshold = re.sub(r'\s+', ' ', threshold)
            thresholds.add(threshold)

    return sorted(list(thresholds))[:10]  # Limit to top 10


def extract_document_refs(text: str) -> List[str]:
    """
    Extract document references from text (SAP Section 3.2, MOP, Table 5, etc.)

    Args:
        text: Protocol text to analyze

    Returns:
        List of unique document references found
    """
    refs = set()

    for ref_type, pattern in DOCUMENT_REF_PATTERNS.items():
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            ref = match.group(0).strip()
            refs.add(ref)

    return sorted(list(refs))[:8]  # Limit to top 8


def extract_conditional_triggers(text: str) -> List[str]:
    """
    Extract conditional triggers from text (unless safety concern, after missed vaccination, etc.)

    Args:
        text: Protocol text to analyze

    Returns:
        List of unique conditional triggers found
    """
    triggers = set()

    for trigger_name, pattern in CONDITIONAL_TRIGGER_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            triggers.add(trigger_name)

    return sorted(list(triggers))


# ============================================================================
# MAIN EXTRACTION FUNCTION
# ============================================================================

def extract_protocol_entities(text: str, timeline: Optional['Timeline'] = None) -> Dict[str, List[str]]:
    """
    Extract all protocol entities from text

    Main entry point for entity extraction. Extracts 6 types of entities:
    1. Visit names (from timeline and text)
    2. Assessment types (safety labs, vital signs, etc.)
    3. Timepoints (Day 2, Week 4, etc.)
    4. Safety thresholds (Grade 3+, ALT >2.5x ULN)
    5. Document references (SAP Section 3.2, MOP, Table 5)
    6. Conditional triggers (unless safety concern, after missed vaccination)

    Args:
        text: Protocol text to analyze
        timeline: Optional parsed Timeline object from timeline_parser

    Returns:
        Dictionary with 6 entity type keys, each containing list of extracted entities

    Example:
        >>> text = "Visits on Day 2 and Day 8 unless safety concern (Grade 3+ AE per SAP Section 3.2)"
        >>> entities = extract_protocol_entities(text)
        >>> entities
        {
            'visit_names': [],
            'assessment_types': [],
            'timepoints': ['Day 2', 'Day 8'],
            'safety_thresholds': ['Grade 3+'],
            'document_refs': ['SAP Section 3.2'],
            'conditional_triggers': ['safety concern']
        }
    """
    try:
        entities = {
            "visit_names": extract_visit_names(text, timeline),
            "assessment_types": extract_assessment_types(text),
            "timepoints": extract_timepoints(text),
            "safety_thresholds": extract_safety_thresholds(text),
            "document_refs": extract_document_refs(text),
            "conditional_triggers": extract_conditional_triggers(text),
        }

        # Log extraction summary
        total_entities = sum(len(v) for v in entities.values())
        logger.info(f"Extracted {total_entities} entities: "
                   f"{len(entities['visit_names'])} visits, "
                   f"{len(entities['assessment_types'])} assessments, "
                   f"{len(entities['timepoints'])} timepoints, "
                   f"{len(entities['safety_thresholds'])} thresholds, "
                   f"{len(entities['document_refs'])} refs, "
                   f"{len(entities['conditional_triggers'])} triggers")

        return entities

    except Exception as e:
        logger.error(f"Error extracting entities: {e}")
        # Return empty entities on error (graceful degradation)
        return {
            "visit_names": [],
            "assessment_types": [],
            "timepoints": [],
            "safety_thresholds": [],
            "document_refs": [],
            "conditional_triggers": [],
        }


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_entity_count(entities: Dict[str, List[str]]) -> int:
    """Get total count of all extracted entities"""
    return sum(len(v) for v in entities.values())


def has_entities(entities: Dict[str, List[str]]) -> bool:
    """Check if any entities were extracted"""
    return get_entity_count(entities) > 0


def get_high_value_entities(entities: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """
    Filter to only high-value entities (for token budget management)

    Priority order:
    1. Timepoints (most specific for suggestions)
    2. Safety thresholds (critical for safety)
    3. Visit names (context)
    4. Document refs (regulatory compliance)
    5. Assessment types (detail)
    6. Conditional triggers (edge cases)
    """
    return {
        "timepoints": entities.get("timepoints", [])[:5],  # Top 5 timepoints
        "safety_thresholds": entities.get("safety_thresholds", [])[:3],  # Top 3 thresholds
        "visit_names": entities.get("visit_names", [])[:3],  # Top 3 visits
        "document_refs": entities.get("document_refs", [])[:2],  # Top 2 refs
        "assessment_types": entities.get("assessment_types", [])[:3],  # Top 3 assessments
        "conditional_triggers": entities.get("conditional_triggers", [])[:2],  # Top 2 triggers
    }
