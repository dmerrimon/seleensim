"""
Cross-Section Consistency Engine for Hybrid Document Intelligence

Detects conflicts and inconsistencies between protocol sections:
- CS001: Eligibility-Endpoints alignment
- CS002: Objectives-Statistics consistency
- CS003: Safety-Schedule coverage
- CS004: Sample size-Endpoints match
- CS005: Primary endpoint clarity across sections
- CS006: Visit window completeness
- CS007: Population definition consistency

Conflicts are formatted as suggestion cards for display in the Add-in.
"""

import os
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class CrossSectionConflict:
    """Represents a cross-section consistency issue"""
    id: str
    check_id: str
    type: str
    severity: str  # critical, major, minor
    sections_involved: List[str]
    description: str
    original_text: str
    improved_text: str
    rationale: str
    confidence: float
    source: str = "cross_section_engine"


# Keyword patterns for entity extraction
ENDPOINT_PATTERNS = [
    r"(?i)(overall\s+survival|OS)",
    r"(?i)(progression[- ]free\s+survival|PFS)",
    r"(?i)(disease[- ]free\s+survival|DFS)",
    r"(?i)(objective\s+response\s+rate|ORR)",
    r"(?i)(complete\s+response|CR)",
    r"(?i)(partial\s+response|PR)",
    r"(?i)(duration\s+of\s+response|DOR)",
    r"(?i)(time\s+to\s+(?:progression|response|event))",
    r"(?i)(quality\s+of\s+life|QoL)",
    r"(?i)(adverse\s+events?|AE|SAE)",
]

POPULATION_PATTERNS = [
    r"(?i)(age[d]?\s*(?:>=?|<=?|between)?\s*\d+)",
    r"(?i)(adult[s]?|pediatric|elderly)",
    r"(?i)(male[s]?|female[s]?|both\s+sex(?:es)?)",
    r"(?i)(HER2[+-]?|EGFR|BRCA|ALK)[+-]?(?:\s+positive|\s+negative)?",
    r"(?i)(stage\s+[IV]+[ABC]?)",
    r"(?i)(metastatic|locally\s+advanced|early[- ]stage)",
    r"(?i)(treatment[- ]naive|previously\s+treated)",
]

STATISTICS_PATTERNS = [
    r"(?i)(superiority|non[- ]inferiority|equivalence)",
    r"(?i)(sample\s+size\s*(?:of)?\s*\d+)",
    r"(?i)(\d+%?\s*power)",
    r"(?i)(alpha\s*=?\s*0?\.\d+)",
    r"(?i)(intention[- ]to[- ]treat|ITT)",
    r"(?i)(per[- ]protocol|PP)",
    r"(?i)(interim\s+analysis)",
]

SAFETY_PATTERNS = [
    r"(?i)(24[- ]hour|within\s+24\s+hours?)",
    r"(?i)(serious\s+adverse\s+event|SAE)",
    r"(?i)(DSMB|data\s+safety)",
    r"(?i)(stopping\s+rule|futility)",
    r"(?i)(dose[- ]?limiting\s+toxicity|DLT)",
]


def extract_endpoints(text: str) -> List[str]:
    """Extract endpoint mentions from text"""
    endpoints = []
    for pattern in ENDPOINT_PATTERNS:
        matches = re.findall(pattern, text)
        endpoints.extend([m if isinstance(m, str) else m[0] for m in matches])
    return list(set(endpoints))


def extract_population_criteria(text: str) -> List[str]:
    """Extract population/eligibility criteria mentions"""
    criteria = []
    for pattern in POPULATION_PATTERNS:
        matches = re.findall(pattern, text)
        criteria.extend([m if isinstance(m, str) else m[0] for m in matches])
    return list(set(criteria))


def extract_statistical_methods(text: str) -> Dict[str, Any]:
    """Extract statistical methodology mentions"""
    methods = {
        "hypothesis_type": None,
        "sample_size": None,
        "power": None,
        "analysis_population": [],
    }

    text_lower = text.lower()

    # Hypothesis type
    if "superiority" in text_lower:
        methods["hypothesis_type"] = "superiority"
    elif "non-inferiority" in text_lower or "noninferiority" in text_lower:
        methods["hypothesis_type"] = "non-inferiority"
    elif "equivalence" in text_lower:
        methods["hypothesis_type"] = "equivalence"

    # Sample size
    sample_match = re.search(r"sample\s+size\s*(?:of)?\s*(\d+)", text_lower)
    if sample_match:
        methods["sample_size"] = int(sample_match.group(1))

    # Power
    power_match = re.search(r"(\d+)%?\s*power", text_lower)
    if power_match:
        methods["power"] = int(power_match.group(1))

    # Analysis populations
    if "intention-to-treat" in text_lower or "itt" in text_lower:
        methods["analysis_population"].append("ITT")
    if "per-protocol" in text_lower or "per protocol" in text_lower:
        methods["analysis_population"].append("per-protocol")

    return methods


async def check_eligibility_endpoints_alignment(
    sections: Dict[str, List[str]],
    section_summaries: Dict[str, str],
) -> List[CrossSectionConflict]:
    """
    CS001: Check if eligibility criteria support endpoint measurement

    Example conflict:
    - Eligibility excludes patients with measurable disease
    - Endpoint requires tumor response measurement
    """
    conflicts = []

    eligibility_text = " ".join(sections.get("eligibility", []))
    endpoints_text = " ".join(sections.get("endpoints", []))

    if not eligibility_text or not endpoints_text:
        return conflicts

    eligibility_lower = eligibility_text.lower()
    endpoints_lower = endpoints_text.lower()

    # Check for measurable disease requirement
    if "measurable disease" in endpoints_lower or "tumor response" in endpoints_lower:
        if "non-measurable" in eligibility_lower or "not measurable" in eligibility_lower:
            conflicts.append(CrossSectionConflict(
                id="cs001_measurable_001",
                check_id="CS001",
                type="eligibility_endpoints_mismatch",
                severity="major",
                sections_involved=["eligibility", "endpoints"],
                description="Endpoints require measurable disease assessment but eligibility may include non-measurable disease patients",
                original_text="Eligibility allows non-measurable disease",
                improved_text="Consider requiring measurable disease per RECIST 1.1 in eligibility criteria, or revise endpoints to include non-measurable disease outcomes",
                rationale="ICH E9 requires endpoints to be measurable in the enrolled population. If tumor response is a primary/secondary endpoint, patients must have measurable disease at baseline.",
                confidence=0.85,
            ))

    # Check for prior treatment conflicts
    endpoint_mentions = extract_endpoints(endpoints_text)
    if any("time to progression" in e.lower() for e in endpoint_mentions):
        if "treatment-naive" in eligibility_lower or "treatment naive" in eligibility_lower:
            # This is actually fine - just noting the check
            pass
        elif "no prior" not in eligibility_lower and "previously untreated" not in eligibility_lower:
            conflicts.append(CrossSectionConflict(
                id="cs001_prior_treatment_001",
                check_id="CS001",
                type="eligibility_endpoints_mismatch",
                severity="minor",
                sections_involved=["eligibility", "endpoints"],
                description="Time to progression endpoint may be affected by heterogeneous prior treatment history",
                original_text="Prior treatment requirements not clearly specified in eligibility",
                improved_text="Consider stratifying by prior treatment lines or specifying treatment history requirements in eligibility criteria",
                rationale="FDA recommends stratification or restriction by prior therapy when measuring time-based endpoints to reduce confounding.",
                confidence=0.7,
            ))

    return conflicts


async def check_objectives_statistics_consistency(
    sections: Dict[str, List[str]],
    section_summaries: Dict[str, str],
) -> List[CrossSectionConflict]:
    """
    CS002: Check if statistical methods align with stated objectives

    Example conflict:
    - Objective: "Demonstrate superiority"
    - Statistics: "Non-inferiority analysis"
    """
    conflicts = []

    objectives_text = " ".join(sections.get("objectives", []))
    statistics_text = " ".join(sections.get("statistics", []))

    if not objectives_text or not statistics_text:
        return conflicts

    objectives_lower = objectives_text.lower()
    statistics_lower = statistics_text.lower()

    # Extract hypothesis types
    obj_superior = "superiority" in objectives_lower or "superior" in objectives_lower
    obj_noninf = "non-inferiority" in objectives_lower or "noninferiority" in objectives_lower

    stat_superior = "superiority" in statistics_lower
    stat_noninf = "non-inferiority" in statistics_lower or "noninferiority" in statistics_lower

    # Check for mismatch
    if obj_superior and stat_noninf and not stat_superior:
        conflicts.append(CrossSectionConflict(
            id="cs002_hypothesis_001",
            check_id="CS002",
            type="objective_statistics_mismatch",
            severity="critical",
            sections_involved=["objectives", "statistics"],
            description="Objectives state superiority goal but statistical methods describe non-inferiority analysis",
            original_text="Objective: demonstrate superiority; Statistics: non-inferiority design",
            improved_text="Align statistical hypothesis with study objectives. If testing superiority, use superiority analysis. If non-inferiority is acceptable, update objectives accordingly.",
            rationale="ICH E9 Section 2.2.2: The statistical hypothesis must be consistent with the clinical objective. Superiority claims require superiority testing.",
            confidence=0.95,
        ))

    if obj_noninf and stat_superior and not stat_noninf:
        conflicts.append(CrossSectionConflict(
            id="cs002_hypothesis_002",
            check_id="CS002",
            type="objective_statistics_mismatch",
            severity="major",
            sections_involved=["objectives", "statistics"],
            description="Objectives mention non-inferiority but statistical methods only describe superiority testing",
            original_text="Objective: non-inferiority; Statistics: superiority analysis only",
            improved_text="Include non-inferiority margin and analysis methods in statistical section if non-inferiority is the primary objective",
            rationale="Non-inferiority trials require pre-specified margins and specific analysis approaches per FDA guidance.",
            confidence=0.85,
        ))

    return conflicts


async def check_safety_schedule_coverage(
    sections: Dict[str, List[str]],
    section_summaries: Dict[str, str],
    timeline: Optional[Any] = None,  # NEW: Timeline object
) -> List[CrossSectionConflict]:
    """
    CS003: Check if safety monitoring has adequate visit schedule coverage

    ENHANCED with timeline intelligence:
    - Validates safety labs scheduled at appropriate visits
    - Checks inter-visit gaps vs SAE reporting requirements
    - Validates conditional safety visits have defined triggers
    """
    conflicts = []

    safety_text = " ".join(sections.get("safety", []))
    schedule_text = " ".join(sections.get("schedule", []))

    if not safety_text or not schedule_text:
        return conflicts

    safety_lower = safety_text.lower()
    schedule_lower = schedule_text.lower()

    # EXISTING CHECK 1: 24-hour SAE reporting requirement
    if "24 hour" in safety_lower or "24-hour" in safety_lower:
        if "24 hour" not in schedule_lower and "24-hour" not in schedule_lower:
            if "contact" not in schedule_lower and "phone" not in schedule_lower:
                conflicts.append(CrossSectionConflict(
                    id="cs003_sae_reporting_001",
                    check_id="CS003",
                    type="safety_schedule_gap",
                    severity="major",
                    sections_involved=["safety", "schedule"],
                    description="Safety requires 24-hour SAE reporting but schedule doesn't specify how patients report between visits",
                    original_text="24-hour SAE reporting required",
                    improved_text="Add inter-visit contact procedures (e.g., 24-hour study hotline, patient diary, scheduled phone calls) to ensure 24-hour SAE reporting capability",
                    rationale="ICH E2A requires expedited reporting of serious adverse events. Protocol must specify mechanism for patients to report SAEs between scheduled visits.",
                    confidence=0.8,
                ))

    # EXISTING CHECK 2: DSMB/interim analysis
    if "dsmb" in safety_lower or "data safety monitoring" in safety_lower:
        statistics_text = " ".join(sections.get("statistics", []))
        if "dsmb" not in statistics_text.lower() and "interim" not in statistics_text.lower():
            conflicts.append(CrossSectionConflict(
                id="cs003_dsmb_001",
                check_id="CS003",
                type="safety_schedule_gap",
                severity="minor",
                sections_involved=["safety", "statistics"],
                description="Safety mentions DSMB but statistical section doesn't describe interim analysis procedures",
                original_text="DSMB mentioned in safety",
                improved_text="Add interim analysis timing, stopping boundaries, and DSMB charter reference to statistical methods section",
                rationale="FDA requires pre-specification of interim analysis timing and stopping rules when DSMB is employed.",
                confidence=0.75,
            ))

    # ========================================================================
    # NEW TIMELINE-AWARE CHECKS (only if timeline is available)
    # ========================================================================

    if timeline and hasattr(timeline, 'visits') and hasattr(timeline, 'assessment_schedule'):

        # NEW CHECK 3: Inter-visit gap vs SAE reporting
        if ("24 hour" in safety_lower or "24-hour" in safety_lower) and len(timeline.visits) > 1:
            # Calculate maximum inter-visit gap
            sorted_visits = sorted([v for v in timeline.visits if not v.is_conditional],
                                   key=lambda v: v.window.nominal_days)
            max_gap_days = 0
            gap_visits = None

            for i in range(len(sorted_visits) - 1):
                v1, v2 = sorted_visits[i], sorted_visits[i + 1]
                gap = v2.window.nominal_days - v1.window.nominal_days
                if gap > max_gap_days:
                    max_gap_days = gap
                    gap_visits = (v1.visit_id, v2.visit_id)

            # Flag if gap > 7 days and no contact mechanism
            if max_gap_days > 7:
                if "contact" not in schedule_lower and "phone" not in schedule_lower and "hotline" not in schedule_lower:
                    conflicts.append(CrossSectionConflict(
                        id="cs003_inter_visit_gap_001",
                        check_id="CS003",
                        type="safety_schedule_gap",
                        severity="major",
                        sections_involved=["safety", "schedule"],
                        description=f"Longest inter-visit interval is {max_gap_days} days ({gap_visits[0]} to {gap_visits[1]}), but no mechanism specified for 24-hour SAE reporting between visits",
                        original_text=f"Visit gap: {gap_visits[0]} to {gap_visits[1]} ({max_gap_days} days)",
                        improved_text=f"Add inter-visit contact mechanism (24-hour hotline or weekly phone calls) to enable SAE reporting during {max_gap_days}-day interval between {gap_visits[0]} and {gap_visits[1]}",
                        rationale="ICH E2A requires immediate reporting of SAEs. With visit intervals >7 days, protocol must specify inter-visit contact procedures.",
                        confidence=0.85,
                    ))

        # NEW CHECK 4: Safety assessment coverage ("CBC at each visit" vs actual schedule)
        safety_assessment_patterns = {
            "CBC": r"(?i)\bCBC\b.*(?:each|every)\s+visit",
            "Chemistry": r"(?i)(?:chemistry|CMP|metabolic\s+panel).*(?:each|every)\s+visit",
            "Vital Signs": r"(?i)vital\s+signs?.*(?:each|every)\s+visit",
            "ECG": r"(?i)(?:ECG|EKG).*(?:each|every)\s+visit",
        }

        for assessment_name, pattern in safety_assessment_patterns.items():
            if re.search(pattern, safety_text):
                # Safety says this assessment should be at each visit
                # Check if it's actually scheduled at each visit in the timeline
                scheduled_visits = timeline.assessment_schedule.get(assessment_name, [])
                all_regular_visits = [v.visit_id for v in timeline.visits if not v.is_conditional and v.window.nominal_days >= 0]

                missing_visits = set(all_regular_visits) - set(scheduled_visits)

                if missing_visits and len(missing_visits) / len(all_regular_visits) > 0.2:  # >20% missing
                    missing_list = ", ".join(sorted(list(missing_visits))[:5])
                    if len(missing_visits) > 5:
                        missing_list += f" ... and {len(missing_visits) - 5} more"

                    conflicts.append(CrossSectionConflict(
                        id=f"cs003_missing_{assessment_name.lower().replace(' ', '_')}_001",
                        check_id="CS003",
                        type="safety_schedule_mismatch",
                        severity="major",
                        sections_involved=["safety", "schedule"],
                        description=f"Safety section requires {assessment_name} at each visit, but Schedule of Activities is missing {assessment_name} at {len(missing_visits)} visits: {missing_list}",
                        original_text=f"{assessment_name} required at each visit (Safety section)",
                        improved_text=f"Add {assessment_name} to Schedule of Activities for visits: {missing_list}",
                        rationale=f"Safety monitoring plan requires {assessment_name} at each visit for participant safety. Schedule must reflect this requirement.",
                        confidence=0.80,
                    ))

    return conflicts


async def check_primary_endpoint_consistency(
    sections: Dict[str, List[str]],
    section_summaries: Dict[str, str],
) -> List[CrossSectionConflict]:
    """
    CS005: Check if primary endpoint is consistently described across sections
    """
    conflicts = []

    objectives_text = " ".join(sections.get("objectives", []))
    endpoints_text = " ".join(sections.get("endpoints", []))
    statistics_text = " ".join(sections.get("statistics", []))

    # Extract primary endpoint mentions from each section
    obj_endpoints = extract_endpoints(objectives_text)
    endpt_endpoints = extract_endpoints(endpoints_text)
    stat_endpoints = extract_endpoints(statistics_text)

    # Normalize endpoint names for comparison
    def normalize_endpoint(e: str) -> str:
        e = e.lower().strip()
        e = re.sub(r'[^a-z0-9]', '', e)
        # Common abbreviation mappings
        mappings = {
            "os": "overallsurvival",
            "pfs": "progressionfreesurvival",
            "dfs": "diseasefreesurvival",
            "orr": "objectiveresponserate",
        }
        return mappings.get(e, e)

    obj_normalized = set(normalize_endpoint(e) for e in obj_endpoints)
    endpt_normalized = set(normalize_endpoint(e) for e in endpt_endpoints)
    stat_normalized = set(normalize_endpoint(e) for e in stat_endpoints)

    # Check for discrepancies
    if obj_normalized and endpt_normalized:
        if not obj_normalized.intersection(endpt_normalized):
            # No overlap - potential mismatch
            conflicts.append(CrossSectionConflict(
                id="cs005_endpoint_mismatch_001",
                check_id="CS005",
                type="primary_endpoint_inconsistency",
                severity="critical",
                sections_involved=["objectives", "endpoints"],
                description=f"Primary endpoint in Objectives ({', '.join(obj_endpoints)}) may not match Endpoints section ({', '.join(endpt_endpoints)})",
                original_text=f"Objectives: {', '.join(obj_endpoints)}; Endpoints: {', '.join(endpt_endpoints)}",
                improved_text="Ensure primary endpoint is consistently named across Objectives, Endpoints, and Statistical sections",
                rationale="FDA requires clear and consistent identification of the primary endpoint throughout the protocol. Inconsistent naming can lead to ambiguity in regulatory review.",
                confidence=0.8,
            ))

    return conflicts


async def check_objective_endpoint_alignment(
    sections: Dict[str, List[str]],
    section_summaries: Dict[str, str],
) -> List[CrossSectionConflict]:
    """
    CS008: Check if each objective has a corresponding endpoint defined

    Example conflict:
    - Objective: "To evaluate patient-reported outcomes"
    - Missing: No PRO endpoint specified in endpoints section
    """
    conflicts = []

    objectives_text = " ".join(sections.get("objectives", []))
    endpoints_text = " ".join(sections.get("endpoints", []))

    if not objectives_text or not endpoints_text:
        return conflicts

    objectives_lower = objectives_text.lower()
    endpoints_lower = endpoints_text.lower()

    # Check for common objective-endpoint misalignments
    objective_endpoint_pairs = [
        ("quality of life", ["qol", "quality of life", "eortc", "fact-", "sf-36", "eq-5d"]),
        ("patient satisfaction", ["satisfaction", "tsqm", "patient satisfaction"]),
        ("patient-reported outcome", ["pro", "patient-reported", "proms"]),
        ("safety", ["adverse event", "ae", "sae", "toxicity", "safety"]),
        ("tolerability", ["tolerability", "discontinuation", "tolerability"]),
        ("pharmacokinetic", ["pk", "pharmacokinetic", "cmax", "auc", "half-life"]),
        ("biomarker", ["biomarker", "ctdna", "circulating tumor"]),
        ("survival", ["survival", "os", "pfs", "dfs"]),
        ("response", ["response", "orr", "cr", "pr", "recist"]),
        ("duration of response", ["dor", "duration of response"]),
    ]

    for objective_term, endpoint_terms in objective_endpoint_pairs:
        if objective_term in objectives_lower:
            # Check if any corresponding endpoint term exists
            has_endpoint = any(term in endpoints_lower for term in endpoint_terms)
            if not has_endpoint:
                conflicts.append(CrossSectionConflict(
                    id=f"cs008_{objective_term.replace(' ', '_')}_001",
                    check_id="CS008",
                    type="objective_endpoint_gap",
                    severity="major",
                    sections_involved=["objectives", "endpoints"],
                    description=f"Objective mentions '{objective_term}' but no corresponding endpoint is defined in the endpoints section",
                    original_text=f"Objective: '{objective_term}' assessment mentioned",
                    improved_text=f"Add endpoint for '{objective_term}'. Example: 'The [primary/secondary] endpoint for {objective_term} assessment is [specific instrument/measure] at [timepoint], analyzed using [method].'",
                    rationale=f"ICH E9 Section 2.2.1 requires each objective to have a measurable endpoint. '{objective_term.title()}' objective needs a linked endpoint with instrument, timepoint, and analysis method.",
                    confidence=0.85,
                ))

    # Check for primary objective without primary endpoint
    if "primary objective" in objectives_lower:
        if "primary endpoint" not in endpoints_lower:
            conflicts.append(CrossSectionConflict(
                id="cs008_primary_001",
                check_id="CS008",
                type="objective_endpoint_gap",
                severity="critical",
                sections_involved=["objectives", "endpoints"],
                description="Primary objective stated but 'primary endpoint' is not explicitly labeled in endpoints section",
                original_text="Primary objective exists but primary endpoint label missing",
                improved_text="Clearly label the primary endpoint. Example: 'The PRIMARY ENDPOINT is [endpoint name], defined as [definition] at [timepoint].'",
                rationale="FDA requires clear identification of the primary endpoint that directly addresses the primary objective. Missing or ambiguous primary endpoint labeling is a common regulatory issue.",
                confidence=0.9,
            ))

    return conflicts


async def check_endpoint_sample_size_alignment(
    sections: Dict[str, List[str]],
    section_summaries: Dict[str, str],
) -> List[CrossSectionConflict]:
    """
    CS009: Verify sample size calculation references the primary endpoint

    Example conflict:
    - Primary endpoint: "Overall Survival"
    - Sample size: "Based on response rate" (mismatch!)
    """
    conflicts = []

    endpoints_text = " ".join(sections.get("endpoints", []))
    statistics_text = " ".join(sections.get("statistics", []))

    if not endpoints_text or not statistics_text:
        return conflicts

    endpoints_lower = endpoints_text.lower()
    statistics_lower = statistics_text.lower()

    # Extract primary endpoint type
    primary_endpoint_types = {
        "survival": ["overall survival", "os", "progression-free survival", "pfs", "disease-free survival", "dfs"],
        "response": ["response rate", "orr", "objective response", "complete response", "cr rate"],
        "continuous": ["change from baseline", "mmrm", "continuous"],
        "time_to_event": ["time to", "kaplan-meier", "cox", "log-rank"],
        "binary": ["proportion", "responder rate", "binary"],
    }

    detected_primary_type = None
    for endpoint_type, keywords in primary_endpoint_types.items():
        if any(kw in endpoints_lower for kw in keywords):
            if "primary" in endpoints_lower:
                detected_primary_type = endpoint_type
                break

    # Check if sample size calculation mentions compatible endpoint type
    if detected_primary_type:
        sample_size_compatible = {
            "survival": ["survival", "kaplan", "log-rank", "cox", "hazard", "median", "event rate"],
            "response": ["response", "proportion", "rate", "binary"],
            "continuous": ["mean", "change", "difference", "standard deviation", "effect size"],
            "time_to_event": ["event", "hazard", "median", "kaplan", "survival"],
            "binary": ["proportion", "rate", "odds", "risk"],
        }

        compatible_terms = sample_size_compatible.get(detected_primary_type, [])

        if "sample size" in statistics_lower:
            has_compatible = any(term in statistics_lower for term in compatible_terms)
            if not has_compatible:
                conflicts.append(CrossSectionConflict(
                    id="cs009_sample_size_001",
                    check_id="CS009",
                    type="endpoint_sample_size_mismatch",
                    severity="critical",
                    sections_involved=["endpoints", "statistics"],
                    description=f"Primary endpoint appears to be {detected_primary_type}-type but sample size calculation may not reference compatible parameters",
                    original_text=f"Primary endpoint type: {detected_primary_type}",
                    improved_text=f"Ensure sample size calculation explicitly references the primary endpoint. For {detected_primary_type} endpoints, include: {', '.join(compatible_terms[:3])} parameters.",
                    rationale="ICH E9 Section 3.5 requires sample size calculation to be based on the primary endpoint. Misalignment between endpoint type and sample size assumptions is a critical regulatory finding.",
                    confidence=0.8,
                ))

    # Check for explicit primary endpoint reference in sample size
    if "sample size" in statistics_lower and "primary endpoint" not in statistics_lower:
        if "primary" not in statistics_lower:
            conflicts.append(CrossSectionConflict(
                id="cs009_sample_size_002",
                check_id="CS009",
                type="endpoint_sample_size_mismatch",
                severity="major",
                sections_involved=["endpoints", "statistics"],
                description="Sample size calculation does not explicitly reference the primary endpoint",
                original_text="Sample size section lacks 'primary endpoint' reference",
                improved_text="Add explicit reference: 'Sample size is based on the primary endpoint ([endpoint name]). Assuming [parameters], a sample size of N provides X% power to detect [effect] at alpha=0.05.'",
                rationale="FDA Statistical Guidance requires clear linkage between sample size calculation and the primary endpoint. This ensures the study is adequately powered for its primary objective.",
                confidence=0.85,
            ))

    return conflicts


async def check_population_consistency(
    sections: Dict[str, List[str]],
    section_summaries: Dict[str, str],
) -> List[CrossSectionConflict]:
    """
    CS007: Check if population definition is consistent across sections
    """
    conflicts = []

    eligibility_text = " ".join(sections.get("eligibility", []))
    statistics_text = " ".join(sections.get("statistics", []))
    objectives_text = " ".join(sections.get("objectives", []))

    # Extract age criteria
    age_patterns = re.findall(r"age[d]?\s*(?:>=?|<=?|≥|≤)?\s*(\d+)", eligibility_text.lower())
    stat_age_patterns = re.findall(r"age[d]?\s*(?:>=?|<=?|≥|≤)?\s*(\d+)", statistics_text.lower())

    if age_patterns and stat_age_patterns:
        elig_ages = set(age_patterns)
        stat_ages = set(stat_age_patterns)
        if elig_ages != stat_ages:
            conflicts.append(CrossSectionConflict(
                id="cs007_age_mismatch_001",
                check_id="CS007",
                type="population_inconsistency",
                severity="major",
                sections_involved=["eligibility", "statistics"],
                description=f"Age criteria in eligibility ({', '.join(elig_ages)}) differs from statistical section ({', '.join(stat_ages)})",
                original_text=f"Eligibility ages: {elig_ages}; Statistics ages: {stat_ages}",
                improved_text="Ensure age criteria are consistently specified across eligibility and statistical sections",
                rationale="Inconsistent population definitions can lead to protocol deviations and analysis complications.",
                confidence=0.75,
            ))

    return conflicts


async def check_conditional_visit_logic(
    sections: Dict[str, List[str]],
    section_summaries: Dict[str, str],
    timeline: Optional[Any] = None,
) -> List[CrossSectionConflict]:
    """
    CS010: Validate conditional visit logic and triggers

    NEW CHECK - Validates:
    - Conditional visit triggers are defined in protocol
    - "Unless safety concern" has clear criteria
    - "After missed vaccination" procedures are specified
    - Conditional visits don't conflict with main schedule
    """
    conflicts = []

    # Get schedule text (needed for high-risk language check even if no timeline)
    schedule_text = " ".join(sections.get("schedule", []))
    safety_text = " ".join(sections.get("safety", []))
    procedures_text = " ".join(sections.get("procedures", []))

    # Check each conditional visit (only if timeline has conditional visits)
    if timeline and hasattr(timeline, 'conditional_visits') and timeline.conditional_visits:
        # Combine all text for trigger definition search
        all_text = schedule_text + " " + safety_text + " " + procedures_text

        for cond_visit in timeline.conditional_visits:
            if not cond_visit.condition:
                continue

            condition_lower = cond_visit.condition.lower()

            # Pattern 1: "safety concern" trigger - should be defined
            if "safety" in condition_lower and ("concern" in condition_lower or "issue" in condition_lower):
                # Look for safety concern definition
                safety_criteria_found = any([
                    "safety concern" in safety_text.lower() and ("defined as" in safety_text.lower() or "criteria" in safety_text.lower()),
                    "unacceptable toxicity" in safety_text.lower(),
                    "dlt" in safety_text.lower(),  # Dose-limiting toxicity
                ])

                if not safety_criteria_found:
                    conflicts.append(CrossSectionConflict(
                        id="cs010_undefined_safety_trigger_001",
                        check_id="CS010",
                        type="undefined_conditional_trigger",
                        severity="major",
                        sections_involved=["schedule", "safety"],
                        description=f"Conditional visit trigger 'safety concern' is mentioned but not clearly defined in Safety section",
                        original_text=f"Conditional: {cond_visit.condition}",
                        improved_text="Define specific criteria for 'safety concern' in Safety Monitoring section (e.g., Grade 3+ AE, specific lab abnormalities, or clinical symptoms requiring evaluation)",
                        rationale="Conditional visit triggers must have objective criteria to ensure consistent protocol implementation across sites.",
                        confidence=0.80,
                    ))

            # Pattern 2: "missed vaccination" or "missed dose" - procedures should be specified
            if "missed" in condition_lower and ("vaccination" in condition_lower or "dose" in condition_lower):
                # Look for missed dose procedures
                missed_dose_procedures_found = any([
                    "missed dose" in all_text.lower() and ("procedure" in all_text.lower() or "will" in all_text.lower()),
                    "catch-up" in all_text.lower(),
                    "make-up" in all_text.lower(),
                ])

                if not missed_dose_procedures_found:
                    conflicts.append(CrossSectionConflict(
                        id="cs010_undefined_missed_dose_001",
                        check_id="CS010",
                        type="undefined_conditional_trigger",
                        severity="major",
                        sections_involved=["schedule", "procedures"],
                        description=f"Conditional visit after 'missed vaccination' is mentioned but procedures for missed doses are not specified",
                        original_text=f"Conditional: {cond_visit.condition}",
                        improved_text="Add section describing procedures for missed vaccinations: visit timing windows, safety assessments required, and criteria for resuming dosing schedule",
                        rationale="Missed dose procedures must be pre-specified to maintain protocol integrity and participant safety.",
                        confidence=0.85,
                    ))

            # Pattern 3: "participant agrees" or "participant choice" - informed consent implications
            if "participant" in condition_lower and ("agree" in condition_lower or "choice" in condition_lower or "opt" in condition_lower):
                # Check if informed consent mentions this optional visit
                consent_text = " ".join(sections.get("informed_consent", []))
                optional_mentioned = "optional" in consent_text.lower() or "may choose" in consent_text.lower()

                if not optional_mentioned:
                    conflicts.append(CrossSectionConflict(
                        id="cs010_optional_visit_consent_001",
                        check_id="CS010",
                        type="conditional_visit_consent",
                        severity="minor",
                        sections_involved=["schedule", "informed_consent"],
                        description=f"Optional/conditional visit based on participant choice should be mentioned in informed consent",
                        original_text=f"Conditional: {cond_visit.condition}",
                        improved_text="Add language to informed consent describing optional visit procedures and participant's right to decline",
                        rationale="Informed consent must describe all optional procedures to ensure participants understand their choices.",
                        confidence=0.70,
                    ))

    # Check for high-risk conditional language patterns in schedule
    # Phase 3 Enhancement: Query amendment risk for historical amendment frequencies
    from amendment_risk import predict_amendment_risk

    high_risk_patterns = [
        (r"(?i)will\s+not\s+be\s+conducted\s+unless", "visits will not be conducted unless"),
        (r"(?i)as\s+clinically\s+indicated", "as clinically indicated"),
        (r"(?i)at\s+(?:the\s+)?discretion\s+of", "at discretion of investigator"),
    ]

    for pattern, pattern_name in high_risk_patterns:
        if re.search(pattern, schedule_text):
            # Query amendment risk for amendment frequency (Phase 3 integration)
            amendment_prob = 0.0
            try:
                risk_predictions = predict_amendment_risk(schedule_text, section="schedule", max_results=10)
                for pred in risk_predictions:
                    if pattern_name.lower() in pred.pattern_readable.lower():
                        amendment_prob = pred.amendment_probability
                        break
            except Exception as e:
                # If amendment_risk fails, continue with default severity
                pass

            # Upgrade severity to major if high amendment risk (≥70%)
            severity = "major" if amendment_prob >= 0.7 else "minor"

            # Build description with amendment frequency if available
            description = f"Schedule contains high-risk conditional language: '{pattern_name}'"
            if amendment_prob > 0:
                description += f" - {amendment_prob*100:.0f}% historical amendment rate"
            else:
                description += " - this pattern frequently requires protocol amendments for clarification"

            # Build rationale with amendment data
            rationale = (
                f"Conditional visit language with undefined triggers creates protocol ambiguity "
                f"and leads to inconsistent implementation across sites."
            )
            if amendment_prob > 0:
                rationale += f" Historical data shows {amendment_prob*100:.0f}% of protocols with this pattern require amendments."
            else:
                rationale += " Pre-specifying criteria reduces site confusion and protocol deviations."

            conflicts.append(CrossSectionConflict(
                id=f"cs010_high_risk_language_{pattern_name.replace(' ', '_').replace('/', '_')}",
                check_id="CS010",
                type="high_risk_conditional_language",
                severity=severity,
                sections_involved=["schedule"],
                description=description,
                original_text=f"Pattern detected: '{pattern_name}'",
                improved_text=f"Replace '{pattern_name}' with objective, pre-specified criteria per Protocol Section [X]",
                rationale=rationale,
                confidence=0.85 if amendment_prob >= 0.7 else 0.75,
            ))

    return conflicts


async def analyze_cross_section_consistency(
    sections: Dict[str, List[str]],
    section_summaries: Dict[str, str],
    request_id: str = "unknown",
    timeline: Optional[Any] = None,  # NEW: Timeline object from timeline_parser
) -> List[Dict[str, Any]]:
    """
    Run all cross-section consistency checks

    Args:
        sections: Dict mapping section_type to list of text chunks
        section_summaries: Dict mapping section_type to summary text
        request_id: Request tracking ID
        timeline: Optional Timeline object with visit/assessment schedule

    Returns:
        List of conflicts formatted as suggestion card dicts
    """
    logger.info(f"[{request_id}] Running cross-section consistency analysis (timeline={'available' if timeline else 'N/A'})")

    all_conflicts: List[CrossSectionConflict] = []

    # Run all checks
    checks = [
        ("CS001", check_eligibility_endpoints_alignment, False),  # No timeline needed
        ("CS002", check_objectives_statistics_consistency, False),
        ("CS003", check_safety_schedule_coverage, True),  # ENHANCED: Timeline-aware
        ("CS005", check_primary_endpoint_consistency, False),
        ("CS007", check_population_consistency, False),
        ("CS008", check_objective_endpoint_alignment, False),
        ("CS009", check_endpoint_sample_size_alignment, False),
        ("CS010", check_conditional_visit_logic, True),  # NEW: Timeline-aware
    ]

    for check_id, check_func, needs_timeline in checks:
        try:
            # Pass timeline to checks that need it
            if needs_timeline:
                conflicts = await check_func(sections, section_summaries, timeline)
            else:
                conflicts = await check_func(sections, section_summaries)
            all_conflicts.extend(conflicts)
            if conflicts:
                logger.info(f"[{request_id}] {check_id}: Found {len(conflicts)} conflicts")
        except Exception as e:
            logger.error(f"[{request_id}] {check_id} failed: {e}")

    # Sort by severity: critical > major > minor
    severity_order = {"critical": 0, "major": 1, "minor": 2}
    all_conflicts.sort(key=lambda c: severity_order.get(c.severity, 99))

    # Convert to dict format for JSON serialization
    result = []
    for conflict in all_conflicts:
        result.append({
            "id": conflict.id,
            "type": "cross_section_conflict",
            "severity": conflict.severity,
            "original_text": conflict.original_text,
            "improved_text": conflict.improved_text,
            "rationale": conflict.rationale,
            "confidence": conflict.confidence,
            "source": conflict.source,
            "cross_section_metadata": {
                "check_id": conflict.check_id,
                "conflict_type": conflict.type,
                "sections_involved": conflict.sections_involved,
                "description": conflict.description,
            }
        })

    logger.info(f"[{request_id}] Cross-section analysis complete: {len(result)} conflicts found")
    return result


def get_relevant_conflicts(
    selection_section: str,
    all_conflicts: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Filter conflicts to those relevant to the selected section

    Used during selection analysis to show only applicable cross-section issues
    """
    relevant = []
    for conflict in all_conflicts:
        sections = conflict.get("cross_section_metadata", {}).get("sections_involved", [])
        if selection_section in sections:
            relevant.append(conflict)
    return relevant


# Export
__all__ = [
    "analyze_cross_section_consistency",
    "get_relevant_conflicts",
    "CrossSectionConflict",
]
