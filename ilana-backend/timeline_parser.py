"""
Timeline Parser for Clinical Protocol Schedules

Extracts visit schedules from protocol text into structured timeline graphs.

Functionality:
- Parse visit definitions (baseline, Day 1, Week 4, Month 6, End of Study)
- Extract visit windows and tolerances (Day 28 ±3 days)
- Identify conditional visits ("after missed vaccination", "unless safety concern")
- Build dependency graphs for visit sequences
- Normalize timepoints to days from baseline

Usage:
    from timeline_parser import parse_timeline

    schedule_text = "Visits: Baseline, Week 4 (±3 days), Week 12 (±7 days)"
    timeline = parse_timeline(schedule_text, "request_123")

    if timeline:
        print(f"Parsed {len(timeline.visits)} visits")
        for visit in timeline.visits:
            print(f"  {visit.visit_name}: Day {visit.window.nominal_days}")
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class VisitWindow:
    """Represents a visit window with tolerance"""
    nominal_time: str          # "Day 28", "Week 4", "Month 6"
    nominal_days: int          # Standardized to days from baseline
    tolerance_minus: int       # Days before nominal (e.g., -3)
    tolerance_plus: int        # Days after nominal (e.g., +7)

    def __repr__(self):
        if self.tolerance_minus or self.tolerance_plus:
            if self.tolerance_minus == self.tolerance_plus:
                return f"{self.nominal_time} (±{self.tolerance_plus} days)"
            else:
                return f"{self.nominal_time} (+{self.tolerance_plus}/-{abs(self.tolerance_minus)} days)"
        return self.nominal_time


@dataclass
class Visit:
    """Represents a protocol visit"""
    visit_id: str              # "V1", "Screening", "Week_4"
    visit_name: str            # "Week 4 Visit", "End of Study"
    window: VisitWindow
    assessments: List[str] = field(default_factory=list)  # ["safety labs", "vital signs", "ECG"]
    is_conditional: bool = False       # True if triggered by event
    condition: Optional[str] = None    # "after missed vaccination", "if safety concern"
    dependencies: List[str] = field(default_factory=list)  # Visit IDs this visit depends on

    def __repr__(self):
        cond_str = f" [Conditional: {self.condition}]" if self.is_conditional else ""
        return f"Visit({self.visit_name}, {self.window}{cond_str})"


@dataclass
class Timeline:
    """Complete protocol timeline graph"""
    visits: List[Visit] = field(default_factory=list)
    baseline_visit: Optional[Visit] = None
    end_of_study_visit: Optional[Visit] = None
    conditional_visits: List[Visit] = field(default_factory=list)
    assessment_schedule: Dict[str, List[str]] = field(default_factory=dict)  # assessment -> list of visit IDs
    parse_confidence: float = 1.0    # 0.0-1.0 confidence in parse quality
    warnings: List[str] = field(default_factory=list)  # Parse warnings/ambiguities

    def __repr__(self):
        return f"Timeline({len(self.visits)} visits, {len(self.conditional_visits)} conditional, confidence={self.parse_confidence:.2f})"


# ============================================================================
# REGEX PATTERN LIBRARY
# ============================================================================

# Visit definition patterns
VISIT_PATTERNS = [
    # ONCOLOGY CYCLE NOTATION (CxDy format) - HIGHEST PRIORITY
    # C1D1, C2D1, C1D15, C2D15, etc.
    r"(?i)\b[Cc](\d+)[Dd](\d+)\b",

    # Expanded cycle notation: "Cycle 1 Day 1", "Cycle 2, Day 15"
    r"(?i)\bcycle\s+(\d+)[,\s]+day\s+(\d+)\b",

    # Day/Week/Month + number with keywords
    r"(?i)(?:visit|assessment|evaluation)\s+(?:at|on)\s+(Day|Week|Month)\s+(\d+)",
    r"(?i)(Day|Week|Month)\s+(\d+)\s+(?:visit|assessment|evaluation)",

    # Day/Week/Month + number in list context (after bullet/dash)
    r"(?i)[-•]\s*(Day|Week|Month)\s+(\d+)",

    # Day/Week/Month + number standalone (permissive - use carefully)
    r"(?i)\b(Day|Week|Month)\s+(\d+)\b",

    # Special visits
    r"(?i)\b(baseline|screening|end\s+of\s+study|EOS|EOT|end\s+of\s+treatment)\b",
    r"(?i)\b(follow[- ]?up|safety\s+follow[- ]?up|LTFU|long[- ]?term\s+follow[- ]?up)\b",
    r"(?i)\b(early\s+termination|ET|discontinuation|unscheduled|ad\s+hoc)\b",

    # Visit numbers
    r"(?i)visit\s+(\d+)",
    r"(?i)V(\d+)\b",
]

# Dosing frequency patterns (Q3W = Every 3 weeks, etc.)
DOSING_FREQUENCY_PATTERNS = [
    # QxW = Every x weeks
    r"(?i)\bQ(\d+)W\b",
    # QxD = Every x days
    r"(?i)\bQ(\d+)D\b",
    # "every X weeks/days"
    r"(?i)every\s+(\d+)\s+(week|day)s?",
]

# Visit window patterns
WINDOW_PATTERNS = [
    # Symmetric tolerance: Day 28 (±3 days), C1D1 (±1 day)
    r"(?i)(Day|Week|Month|[Cc]\d+[Dd]\d+)\s+(\d+)?\s*\(\s*[±]\s*(\d+)\s*days?\s*\)",

    # Symmetric tolerance with +/-: Day 28 (+/-3 days)
    r"(?i)(Day|Week|Month|[Cc]\d+[Dd]\d+)\s+(\d+)?\s*\(\s*\+/-\s*(\d+)\s*days?\s*\)",

    # Asymmetric tolerance: Week 4 (+7/-3 days)
    r"(?i)(Day|Week|Month|[Cc]\d+[Dd]\d+)\s+(\d+)?\s*\(\s*\+(\d+)\s*/\s*-(\d+)\s*days?\s*\)",

    # "within X days" format
    r"(?i)within\s+(\d+)\s+days",

    # "within X hours" format
    r"(?i)within\s+(\d+)\s+hours?",
]

# Timing relative to dosing
DOSE_TIMING_PATTERNS = [
    # Pre-dose, predose
    r"(?i)\bpre[- ]?dose\b",

    # Post-dose with time: "2 hours post-dose", "post-dose (4 hours)"
    r"(?i)(\d+)\s+(?:hours?|minutes?)\s+post[- ]?dose",
    r"(?i)post[- ]?dose\s*\(\s*(\d+)\s+(?:hours?|minutes?)\s*\)",

    # End of infusion
    r"(?i)end\s+of\s+infusion",

    # Trough/Peak
    r"(?i)\b(trough|peak)\b",
]

# Conditional visit patterns
CONDITIONAL_PATTERNS = [
    # "Day 2 and 8 after missed vaccination"
    r"(?i)(Day|Week|Month)\s+(\d+)(?:\s+and\s+\d+)?\s+after\s+(.+?)(?:\s+will|\s+visit|\.|,|$)",

    # "if participant agrees"
    r"(?i)if\s+(.+?),?\s+(?:visit|assessment|will\s+(?:be\s+)?conducted?)",

    # "unless safety concern"
    r"(?i)unless\s+(.+?),?\s+(?:visit|assessment|will\s+(?:be\s+)?conducted?)",

    # "visits will not be conducted unless"
    r"(?i)visits?\s+(?:will\s+)?(?:not\s+be\s+)?conducted\s+unless\s+(.+?)(?:\.|,|$)",
]

# Assessment schedule patterns
ASSESSMENT_PATTERNS = [
    r"(?i)(.+?)\s+(?:will\s+be\s+)?(?:assessed|evaluated|measured|collected)\s+at\s+(.+?)(?:\.|,|;|$)",
    r"(?i)assessments?\s+include\s+(.+?)\s+at\s+(.+?)(?:\.|,|;|$)",
    r"(?i)at\s+each\s+visit[,:]?\s+(.+?)(?:\.|$)",
]

# Specific assessment type patterns (based on real SOA tables)
ASSESSMENT_TYPE_PATTERNS = {
    # Pharmacokinetic assessments
    "PK": [
        r"(?i)\bPK\s+(?:blood\s+)?(?:sample|collection|draw|sampling)",
        r"(?i)pharmacokinetic\s+(?:sample|assessment|blood)",
        r"(?i)(?:predose|pre-dose)\s+(?:PK|sample)",
        r"(?i)(?:post-dose|postdose)\s+(?:PK|sample)",
    ],

    # Safety laboratories
    "Hematology": [
        r"(?i)\bCBC\b",
        r"(?i)complete\s+blood\s+count",
        r"(?i)hematology",
        r"(?i)\bWBC\b.*\bdifferential\b",
        r"(?i)platelet\s+count",
    ],

    "Chemistry": [
        r"(?i)\bCMP\b",
        r"(?i)comprehensive\s+metabolic\s+panel",
        r"(?i)chemistry\s+panel",
        r"(?i)\b(?:ALT|AST|ALP)\b",
        r"(?i)liver\s+function",
        r"(?i)renal\s+function",
        r"(?i)\bcreatinine\b",
    ],

    "Urinalysis": [
        r"(?i)\burinalysis\b",
        r"(?i)urine\s+(?:dipstick|test|analysis)",
        r"(?i)\bUPCR\b",  # Urine protein-to-creatinine ratio
    ],

    # Vital signs
    "Vital Signs": [
        r"(?i)vital\s+signs?",
        r"(?i)\b(?:BP|blood\s+pressure)\b",
        r"(?i)\b(?:HR|heart\s+rate)\b",
        r"(?i)temperature",
        r"(?i)respiratory\s+rate",
        r"(?i)\bweight\b",
    ],

    # Cardiac assessments
    "ECG": [
        r"(?i)\b(?:ECG|EKG)\b",
        r"(?i)(?:12-lead|triplicate)\s+(?:ECG|EKG)",
        r"(?i)electrocardiogram",
    ],

    "Echocardiogram": [
        r"(?i)\b(?:ECHO|echocardiogram)\b",
        r"(?i)\bLVEF\b",  # Left ventricular ejection fraction
        r"(?i)\bMUGA\b",  # Multigated acquisition scan
    ],

    # Physical examination
    "Physical Exam": [
        r"(?i)physical\s+exam(?:ination)?",
        r"(?i)\b(?:PE|physical\s+assessment)\b",
        r"(?i)comprehensive\s+(?:PE|physical)",
        r"(?i)directed\s+(?:PE|physical)",
    ],

    # Imaging
    "CT Scan": [
        r"(?i)\bCT\s+(?:scan|imaging|of\s+)",
        r"(?i)computed\s+tomography",
    ],

    "MRI": [
        r"(?i)\bMRI\b",
        r"(?i)magnetic\s+resonance",
    ],

    "PET Scan": [
        r"(?i)\bPET\s+(?:scan|imaging)",
        r"(?i)positron\s+emission",
    ],

    "Tumor Assessment": [
        r"(?i)tumor\s+(?:assessment|evaluation|imaging|staging)",
        r"(?i)disease\s+(?:assessment|evaluation)",
        r"(?i)\bRECIST\b",
        r"(?i)target\s+lesion",
    ],

    # Biomarkers
    "Biomarkers": [
        r"(?i)biomarker\s+(?:sample|collection|assessment)",
        r"(?i)(?:plasma|serum)\s+biomarker",
        r"(?i)circulating\s+tumor",
        r"(?i)\bctDNA\b",
    ],

    # Immunogenicity
    "Immunogenicity": [
        r"(?i)immunogenicity",
        r"(?i)\bADA\b.*(?:sample|assessment)",  # Anti-drug antibodies
        r"(?i)anti-drug\s+antibod",
    ],

    # Pregnancy testing
    "Pregnancy Test": [
        r"(?i)pregnancy\s+test",
        r"(?i)\bWOCBP\b",  # Women of childbearing potential
        r"(?i)serum\s+(?:beta-)?hCG",
    ],

    # Performance status
    "Performance Status": [
        r"(?i)\bECOG\b.*(?:performance|status)",
        r"(?i)performance\s+status",
        r"(?i)\bKPS\b",  # Karnofsky Performance Status
    ],
}

# SOA table marker patterns (for parsing tables)
SOA_MARKER_PATTERNS = [
    r"\bX\b",  # Most common marker
    r"✓",      # Checkmark
    r"✔",      # Heavy checkmark
    r"•",      # Bullet point
    r"[Xx]",   # X or x
]

# Timing specification patterns for assessments
ASSESSMENT_TIMING_PATTERNS = [
    # "at C1D1, C2D1, C3D1"
    r"(?i)at\s+((?:[Cc]\d+[Dd]\d+(?:\s*,\s*)?)+)",

    # "every cycle" / "each cycle"
    r"(?i)(?:every|each)\s+cycle",

    # "every 3 cycles" / "every other cycle"
    r"(?i)every\s+(\d+|other)\s+cycle",

    # "at each visit"
    r"(?i)at\s+(?:each|every)\s+visit",

    # "Q9W" / "Q12W"
    r"(?i)\bQ(\d+)W\b",
]


# ============================================================================
# TIME NORMALIZATION
# ============================================================================

def normalize_timepoint(timepoint: str) -> int:
    """
    Convert timepoint string to days from baseline

    Args:
        timepoint: String like "Day 28", "Week 4", "Month 6", "C1D1", "Cycle 2 Day 15"

    Returns:
        Number of days from baseline

    Examples:
        >>> normalize_timepoint("Day 28")
        28
        >>> normalize_timepoint("Week 4")
        28
        >>> normalize_timepoint("Month 6")
        180
        >>> normalize_timepoint("C1D1")
        1
        >>> normalize_timepoint("C2D15")
        43
    """
    timepoint = timepoint.strip().lower()

    # Special cases
    if "baseline" in timepoint or "screening" in timepoint:
        return 0

    # Cycle notation: C1D1, C2D15, etc.
    match = re.search(r"[Cc](\d+)[Dd](\d+)", timepoint)
    if match:
        cycle_num = int(match.group(1))
        day_num = int(match.group(2))
        # Assuming 28-day cycles (standard in oncology)
        # Handle Cycle 0 as baseline (Day 0)
        if cycle_num == 0:
            return 0
        result = (cycle_num - 1) * 28 + day_num
        return max(0, result)  # Never return negative

    # Expanded cycle notation: "Cycle 2 Day 15"
    match = re.search(r"cycle\s+(\d+).*?day\s+(\d+)", timepoint)
    if match:
        cycle_num = int(match.group(1))
        day_num = int(match.group(2))
        if cycle_num == 0:
            return 0
        result = (cycle_num - 1) * 28 + day_num
        return max(0, result)  # Never return negative

    # Day N
    match = re.search(r"day\s+(\d+)", timepoint)
    if match:
        return int(match.group(1))

    # Week N (N * 7 days)
    match = re.search(r"week\s+(\d+)", timepoint)
    if match:
        return int(match.group(1)) * 7

    # Month N (N * 30 days - approximation)
    match = re.search(r"month\s+(\d+)", timepoint)
    if match:
        return int(match.group(1)) * 30

    # Year N (N * 365 days)
    match = re.search(r"year\s+(\d+)", timepoint)
    if match:
        return int(match.group(1)) * 365

    # Default: return 0 if can't parse
    logger.warning(f"Could not normalize timepoint: {timepoint}")
    return 0


# ============================================================================
# VISIT EXTRACTION
# ============================================================================

def extract_visits(text: str) -> List[Visit]:
    """
    Extract visit definitions from text using regex patterns

    Args:
        text: Protocol schedule section text

    Returns:
        List of Visit objects
    """
    visits = []
    visit_id_counter = 1
    seen_timepoints = set()  # Track to avoid duplicates

    # Pattern 0: CxDy format (C1D1, C2D1, etc.)
    cycle_pattern = VISIT_PATTERNS[0]
    matches = re.finditer(cycle_pattern, text)
    for match in matches:
        try:
            cycle_num = match.group(1)  # Cycle number
            day_num = match.group(2)  # Day number

            visit_id = f"C{cycle_num}D{day_num}"
            nominal_time = f"Cycle {cycle_num} Day {day_num}"

            # Skip duplicates
            if visit_id.lower() in seen_timepoints:
                continue
            seen_timepoints.add(visit_id.lower())

            # Calculate nominal days: (cycle-1) * 28 days + day_num
            # Assuming 28-day cycles (common in oncology)
            nominal_days = (int(cycle_num) - 1) * 28 + int(day_num)

            visit = Visit(
                visit_id=visit_id,
                visit_name=nominal_time,
                window=VisitWindow(
                    nominal_time=nominal_time,
                    nominal_days=nominal_days,
                    tolerance_minus=0,
                    tolerance_plus=0
                )
            )
            visits.append(visit)
            visit_id_counter += 1

        except (IndexError, ValueError) as e:
            logger.warning(f"Failed to parse cycle visit from match: {match.group(0)} - {e}")

    # Pattern 1: "Cycle X Day Y" expanded notation
    expanded_cycle_pattern = VISIT_PATTERNS[1]
    matches = re.finditer(expanded_cycle_pattern, text)
    for match in matches:
        try:
            cycle_num = match.group(1)
            day_num = match.group(2)

            visit_id = f"C{cycle_num}D{day_num}"
            nominal_time = f"Cycle {cycle_num} Day {day_num}"

            # Skip duplicates
            if visit_id.lower() in seen_timepoints:
                continue
            seen_timepoints.add(visit_id.lower())

            nominal_days = (int(cycle_num) - 1) * 28 + int(day_num)

            visit = Visit(
                visit_id=visit_id,
                visit_name=nominal_time,
                window=VisitWindow(
                    nominal_time=nominal_time,
                    nominal_days=nominal_days,
                    tolerance_minus=0,
                    tolerance_plus=0
                )
            )
            visits.append(visit)
            visit_id_counter += 1

        except (IndexError, ValueError) as e:
            logger.warning(f"Failed to parse expanded cycle visit from match: {match.group(0)} - {e}")

    # Patterns 2-5: Day/Week/Month patterns
    for pattern in VISIT_PATTERNS[2:6]:
        matches = re.finditer(pattern, text)
        for match in matches:
            try:
                time_unit = match.group(1)  # Day, Week, Month
                time_value = match.group(2)  # Number

                nominal_time = f"{time_unit} {time_value}"

                # Skip duplicates
                if nominal_time.lower() in seen_timepoints:
                    continue
                seen_timepoints.add(nominal_time.lower())

                nominal_days = normalize_timepoint(nominal_time)

                visit = Visit(
                    visit_id=f"V{visit_id_counter}",
                    visit_name=f"{time_unit} {time_value} Visit",
                    window=VisitWindow(
                        nominal_time=nominal_time,
                        nominal_days=nominal_days,
                        tolerance_minus=0,
                        tolerance_plus=0
                    )
                )
                visits.append(visit)
                visit_id_counter += 1

            except (IndexError, ValueError) as e:
                logger.warning(f"Failed to parse visit from match: {match.group(0)} - {e}")

    # Extract special visits (baseline, screening, EOS, EOT, follow-up, etc.)
    # Patterns 6, 7, 8 are all special visit types
    for special_pattern in VISIT_PATTERNS[6:9]:
        matches = re.finditer(special_pattern, text)
        for match in matches:
            try:
                visit_type = match.group(1).lower()

                # Map to standardized names
                if "baseline" in visit_type:
                    visit_name = "Baseline"
                    nominal_days = 0
                elif "screening" in visit_type:
                    visit_name = "Screening"
                    nominal_days = -7  # Typically before baseline
                elif "end" in visit_type or "eos" in visit_type or "eot" in visit_type:
                    visit_name = "End of Treatment" if "eot" in visit_type else "End of Study"
                    nominal_days = 9999  # Placeholder - will be adjusted based on context
                elif "follow" in visit_type or "ltfu" in visit_type:
                    visit_name = "Follow-Up"
                    nominal_days = 9000  # After EOS
                elif "unscheduled" in visit_type or "ad hoc" in visit_type:
                    visit_name = "Unscheduled Visit"
                    nominal_days = -1  # Special marker for unscheduled
                elif "termination" in visit_type or visit_type == "et":
                    visit_name = "Early Termination"
                    nominal_days = -1  # Variable timing
                else:
                    continue

                # Skip if already added (avoid duplicates)
                if visit_name.lower() in seen_timepoints:
                    continue
                seen_timepoints.add(visit_name.lower())

                visit = Visit(
                    visit_id=visit_type.replace(" ", "_").upper(),
                    visit_name=visit_name,
                    window=VisitWindow(
                        nominal_time=visit_name,
                        nominal_days=nominal_days,
                        tolerance_minus=0,
                        tolerance_plus=0
                    )
                )
                visits.append(visit)

            except (IndexError, ValueError) as e:
                logger.warning(f"Failed to parse special visit: {match.group(0)} - {e}")

    return visits


def extract_visit_windows(text: str, visits: List[Visit]) -> None:
    """
    Extract visit windows and update Visit objects in-place

    Args:
        text: Protocol schedule section text
        visits: List of Visit objects to update with window information
    """
    # Symmetric windows: Day 28 (±3 days)
    symmetric_pattern = WINDOW_PATTERNS[0]
    matches = re.finditer(symmetric_pattern, text)
    for match in matches:
        try:
            time_unit = match.group(1)
            time_value = match.group(2)
            tolerance = int(match.group(3))

            nominal_time = f"{time_unit} {time_value}"

            # Find matching visit
            for visit in visits:
                if nominal_time.lower() in visit.window.nominal_time.lower():
                    visit.window.tolerance_minus = -tolerance
                    visit.window.tolerance_plus = tolerance
                    break

        except (IndexError, ValueError) as e:
            logger.warning(f"Failed to parse symmetric window: {match.group(0)} - {e}")

    # Asymmetric windows: Week 4 (+7/-3 days)
    asymmetric_pattern = WINDOW_PATTERNS[1]
    matches = re.finditer(asymmetric_pattern, text)
    for match in matches:
        try:
            time_unit = match.group(1)
            time_value = match.group(2)
            tolerance_plus = int(match.group(3))
            tolerance_minus = int(match.group(4))

            nominal_time = f"{time_unit} {time_value}"

            # Find matching visit
            for visit in visits:
                if nominal_time.lower() in visit.window.nominal_time.lower():
                    visit.window.tolerance_minus = -tolerance_minus
                    visit.window.tolerance_plus = tolerance_plus
                    break

        except (IndexError, ValueError) as e:
            logger.warning(f"Failed to parse asymmetric window: {match.group(0)} - {e}")


def extract_conditional_visits(text: str) -> List[Visit]:
    """
    Extract conditional visit logic from text

    Args:
        text: Protocol schedule section text

    Returns:
        List of Visit objects with is_conditional=True
    """
    conditional_visits = []
    conditional_id_counter = 1

    # Pattern: "Day 2 and 8 after missed vaccination"
    pattern1 = CONDITIONAL_PATTERNS[0]
    matches = re.finditer(pattern1, text)
    for match in matches:
        try:
            time_unit = match.group(1)
            time_value = match.group(2)
            trigger = match.group(3).strip()

            nominal_time = f"{time_unit} {time_value}"
            nominal_days = normalize_timepoint(nominal_time)

            visit = Visit(
                visit_id=f"C{conditional_id_counter}",
                visit_name=f"{nominal_time} (Conditional)",
                window=VisitWindow(
                    nominal_time=nominal_time,
                    nominal_days=nominal_days,
                    tolerance_minus=0,
                    tolerance_plus=0
                ),
                is_conditional=True,
                condition=f"after {trigger}"
            )
            conditional_visits.append(visit)
            conditional_id_counter += 1

        except (IndexError, ValueError) as e:
            logger.warning(f"Failed to parse conditional visit: {match.group(0)} - {e}")

    # Pattern: "unless safety concern" / "if participant agrees"
    for pattern in CONDITIONAL_PATTERNS[1:]:
        matches = re.finditer(pattern, text)
        for match in matches:
            try:
                trigger = match.group(1).strip()

                # Create generic conditional visit
                visit = Visit(
                    visit_id=f"C{conditional_id_counter}",
                    visit_name=f"Conditional Visit ({trigger[:30]}...)",
                    window=VisitWindow(
                        nominal_time="Conditional",
                        nominal_days=-1,  # Unknown timing
                        tolerance_minus=0,
                        tolerance_plus=0
                    ),
                    is_conditional=True,
                    condition=trigger
                )
                conditional_visits.append(visit)
                conditional_id_counter += 1

            except (IndexError, ValueError) as e:
                logger.warning(f"Failed to parse conditional logic: {match.group(0)} - {e}")

    return conditional_visits


# ============================================================================
# ASSESSMENT EXTRACTION
# ============================================================================

def extract_assessment_types(text: str) -> Dict[str, List[str]]:
    """
    Extract assessment types mentioned in protocol text

    Args:
        text: Protocol text (schedule section or full protocol)

    Returns:
        Dictionary mapping assessment type -> list of text snippets where found

    Example:
        {"PK": ["PK sample collection at C1D1", "PK blood draw"],
         "CBC": ["CBC at each visit", "hematology panel"]}
    """
    found_assessments = {}

    for assessment_type, patterns in ASSESSMENT_TYPE_PATTERNS.items():
        matches = []
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                # Extract context around match (±50 chars)
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end].strip()
                matches.append(context)

        if matches:
            found_assessments[assessment_type] = matches

    return found_assessments


def extract_assessment_schedule(text: str, visits: List[Visit]) -> Dict[str, List[str]]:
    """
    Extract when each assessment type is scheduled

    Args:
        text: Protocol schedule text
        visits: List of parsed visits

    Returns:
        Dictionary mapping assessment type -> list of visit IDs when it's scheduled

    Example:
        {"PK": ["C1D1", "C1D15", "C2D1"],
         "CBC": ["SCREENING", "C1D1", "C2D1", "C3D1"],
         "ECG": ["SCREENING", "C1D1", "C2D1"]}
    """
    assessment_schedule = {}

    # Extract assessments mentioned in text
    found_assessments = extract_assessment_types(text)

    # For each assessment, try to find which visits it's scheduled for
    for assessment_type, contexts in found_assessments.items():
        scheduled_visits = set()

        for context in contexts:
            # Look for visit IDs in the context
            # Pattern 1: "at C1D1, C2D1, C3D1"
            cycle_visits = re.findall(r'\b[Cc](\d+)[Dd](\d+)\b', context)
            for cycle, day in cycle_visits:
                visit_id = f"C{cycle}D{day}"
                scheduled_visits.add(visit_id)

            # Pattern 2: "at each visit" / "every visit"
            if re.search(r'(?i)(?:at\s+)?(?:each|every)\s+visit', context):
                # Add all regular visits
                scheduled_visits.update([v.visit_id for v in visits if not v.is_conditional])

            # Pattern 3: "at baseline", "at screening"
            if re.search(r'(?i)at\s+(?:baseline|screening)', context):
                for visit in visits:
                    if "baseline" in visit.visit_name.lower() or "screening" in visit.visit_name.lower():
                        scheduled_visits.add(visit.visit_id)

            # Pattern 4: "every cycle" / "each cycle"
            if re.search(r'(?i)(?:every|each)\s+cycle', context):
                # Add C1D1, C2D1, C3D1, etc. (Day 1 of each cycle)
                cycle_day1_visits = [v for v in visits if re.match(r'C\d+D1', v.visit_id)]
                scheduled_visits.update([v.visit_id for v in cycle_day1_visits])

            # Pattern 5: "every 3 cycles"
            match = re.search(r'(?i)every\s+(\d+)\s+cycles?', context)
            if match:
                interval = int(match.group(1))
                cycle_day1_visits = [v for v in visits if re.match(r'C(\d+)D1', v.visit_id)]
                for v in cycle_day1_visits:
                    cycle_match = re.match(r'C(\d+)D1', v.visit_id)
                    if cycle_match:
                        cycle_num = int(cycle_match.group(1))
                        if cycle_num == 1 or (cycle_num - 1) % interval == 0:
                            scheduled_visits.add(v.visit_id)

        if scheduled_visits:
            assessment_schedule[assessment_type] = sorted(list(scheduled_visits))

    return assessment_schedule


def map_assessments_to_visits(visits: List[Visit], assessment_schedule: Dict[str, List[str]]) -> None:
    """
    Populate the assessments field for each Visit object

    Args:
        visits: List of Visit objects to update
        assessment_schedule: Dict mapping assessment type -> list of visit IDs

    Side effect:
        Updates visit.assessments field in-place
    """
    # Create reverse mapping: visit_id -> list of assessments
    visit_assessments = {}
    for assessment_type, visit_ids in assessment_schedule.items():
        for visit_id in visit_ids:
            if visit_id not in visit_assessments:
                visit_assessments[visit_id] = []
            visit_assessments[visit_id].append(assessment_type)

    # Update each visit
    for visit in visits:
        if visit.visit_id in visit_assessments:
            visit.assessments = sorted(visit_assessments[visit.visit_id])


# ============================================================================
# MAIN PARSING FUNCTION
# ============================================================================

def parse_timeline(schedule_text: str, request_id: str = "unknown") -> Optional[Timeline]:
    """
    Main entry point: Parse schedule text into Timeline object

    Args:
        schedule_text: Protocol schedule section text
        request_id: Request ID for logging

    Returns:
        Timeline object if parsing succeeds, None if parsing fails

    Example:
        >>> text = "Visits: Baseline, Week 4 (±3 days), Week 12 (±7 days)"
        >>> timeline = parse_timeline(text, "req_123")
        >>> print(timeline)
        Timeline(3 visits, 0 conditional, confidence=1.0)
    """
    if not schedule_text or len(schedule_text.strip()) < 10:
        logger.warning(f"[{request_id}] Schedule text too short or empty")
        return None

    try:
        # Step 1: Extract visits
        visits = extract_visits(schedule_text)

        if not visits:
            logger.info(f"[{request_id}] No visits found in schedule text")
            return None

        # Step 2: Extract visit windows
        extract_visit_windows(schedule_text, visits)

        # Step 3: Extract conditional visits
        conditional_visits = extract_conditional_visits(schedule_text)

        # Step 4: Sort visits by nominal days
        visits.sort(key=lambda v: v.window.nominal_days)

        # Step 5: Identify special visits
        baseline_visit = None
        end_of_study_visit = None

        for visit in visits:
            if visit.window.nominal_days == 0 or "baseline" in visit.visit_name.lower():
                baseline_visit = visit
            if "end of study" in visit.visit_name.lower() or "eos" in visit.visit_name.lower():
                end_of_study_visit = visit

        # Step 5a: Extract assessment schedule (NEW!)
        assessment_schedule = extract_assessment_schedule(schedule_text, visits)

        # Step 5b: Map assessments to visits (NEW!)
        map_assessments_to_visits(visits, assessment_schedule)

        logger.info(f"[{request_id}] Extracted {len(assessment_schedule)} assessment types")

        # Step 6: Build timeline object
        timeline = Timeline(
            visits=visits,
            baseline_visit=baseline_visit,
            end_of_study_visit=end_of_study_visit,
            conditional_visits=conditional_visits,
            assessment_schedule=assessment_schedule,  # NEW!
            parse_confidence=1.0,
            warnings=[]
        )

        # Step 7: Calculate parse confidence
        # Reduce confidence if:
        # - Few visits found (< 3)
        # - No baseline visit
        # - Many conditional visits (complexity)

        if len(visits) < 3:
            timeline.parse_confidence *= 0.8
            timeline.warnings.append("Few visits found (< 3)")

        if not baseline_visit:
            timeline.parse_confidence *= 0.9
            timeline.warnings.append("No baseline visit found")

        if len(conditional_visits) > len(visits) * 0.5:
            timeline.parse_confidence *= 0.85
            timeline.warnings.append("High proportion of conditional visits")

        logger.info(f"[{request_id}] Timeline parsed successfully: {timeline}")

        return timeline

    except Exception as e:
        logger.error(f"[{request_id}] Timeline parsing failed: {e}", exc_info=True)
        return None


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_visit_by_timepoint(timeline: Timeline, timepoint: str) -> Optional[Visit]:
    """
    Find a visit by timepoint string

    Args:
        timeline: Timeline object
        timepoint: Timepoint string like "Week 4", "Day 28"

    Returns:
        Visit object if found, None otherwise
    """
    timepoint_lower = timepoint.lower()
    for visit in timeline.visits:
        if timepoint_lower in visit.window.nominal_time.lower():
            return visit
    return None


def get_visits_in_range(timeline: Timeline, start_day: int, end_day: int) -> List[Visit]:
    """
    Get all visits within a day range

    Args:
        timeline: Timeline object
        start_day: Start day (inclusive)
        end_day: End day (inclusive)

    Returns:
        List of Visit objects in range
    """
    return [
        visit for visit in timeline.visits
        if start_day <= visit.window.nominal_days <= end_day
    ]


def format_timeline_summary(timeline: Timeline, max_visits: int = 10) -> str:
    """
    Format timeline as human-readable summary

    Args:
        timeline: Timeline object
        max_visits: Maximum number of visits to include (rest will be truncated)

    Returns:
        Formatted string summary
    """
    lines = [f"VISIT SCHEDULE ({len(timeline.visits)} visits):"]

    for i, visit in enumerate(timeline.visits[:max_visits]):
        window_str = str(visit.window)
        lines.append(f"  • {visit.visit_name} ({window_str})")

    if len(timeline.visits) > max_visits:
        lines.append(f"  • ... ({len(timeline.visits) - max_visits} more visits)")

    if timeline.conditional_visits:
        lines.append(f"\nCONDITIONAL VISITS ({len(timeline.conditional_visits)}):")
        for cond in timeline.conditional_visits[:5]:
            lines.append(f"  • {cond.visit_name}: {cond.condition}")

    return "\n".join(lines)
