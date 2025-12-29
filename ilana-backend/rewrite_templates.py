#!/usr/bin/env python3
"""
Rewrite Templates for Protocol Endpoints and Objectives

Provides structured templates for generating copy-paste-ready
endpoint and objective rewrites that comply with ICH E9 requirements.

Used by prompt_optimizer.py to guide LLM output format.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ============================================================================
# ENDPOINT REWRITE TEMPLATES
# ============================================================================

@dataclass
class EndpointTemplate:
    """Template for a complete endpoint definition."""
    name: str
    endpoint_type: str  # primary, secondary, exploratory
    definition: str
    timepoint: str
    measurement_method: str
    analysis_method: str
    population: str
    margin: Optional[str] = None  # For non-inferiority/superiority
    censoring: Optional[str] = None  # For time-to-event endpoints


ENDPOINT_REWRITE_TEMPLATES = {
    "primary_endpoint_survival": """
The primary endpoint is {endpoint_name}, defined as {definition}.
{endpoint_name} will be censored at {censoring_rule}.
Analysis will be performed using Kaplan-Meier methods with log-rank test
stratified by {stratification_factors}. Hazard ratio (HR) and 95% confidence
interval (CI) will be estimated using a Cox proportional hazards model.
The analysis will be conducted in the {population} population.
""",

    "primary_endpoint_response": """
The primary endpoint is {endpoint_name}, defined as {definition} per {criteria}.
{endpoint_name} will be assessed at {timepoint}.
The proportion of responders and corresponding 95% CI will be estimated using
the Clopper-Pearson exact method. Group comparisons will be performed using
{analysis_method}. The analysis will be conducted in the {population} population.
""",

    "primary_endpoint_continuous": """
The primary endpoint is {endpoint_name}, defined as change from baseline in
{measurement} at {timepoint}.
Analysis will be performed using {analysis_method} with {model_terms}.
The analysis will be conducted in the {population} population.
{margin_statement}
""",

    "secondary_endpoint_time_to_event": """
A secondary endpoint is {endpoint_name}, defined as {definition}.
{endpoint_name} will be censored at {censoring_rule}.
Analysis will be performed using Kaplan-Meier methods in the {population} population.
""",

    "secondary_endpoint_continuous": """
A secondary endpoint is {endpoint_name}, defined as change from baseline in
{measurement} at {timepoint}, analyzed using {analysis_method}
in the {population} population.
""",

    "secondary_endpoint_binary": """
A secondary endpoint is {endpoint_name}, defined as the proportion of
participants with {success_criterion} at {timepoint}.
Analysis will be performed using {analysis_method} with 95% CI
in the {population} population.
""",

    "exploratory_endpoint": """
An exploratory endpoint is {endpoint_name}, defined as {definition}
at {timepoint}. Descriptive statistics will be provided.
""",
}


# ============================================================================
# OBJECTIVE REWRITE TEMPLATES
# ============================================================================

OBJECTIVE_REWRITE_TEMPLATES = {
    "primary_objective_efficacy": """
The primary objective is to {action} of {intervention} compared to {comparator}
as measured by {endpoint} at {timepoint}.
""",

    "primary_objective_noninferiority": """
The primary objective is to demonstrate that {intervention} is non-inferior
to {comparator} with respect to {endpoint}, using a non-inferiority margin
of {margin}.
""",

    "secondary_objective_efficacy": """
A secondary objective is to {action}, measured by {endpoint} at {timepoint}.
""",

    "secondary_objective_safety": """
A secondary objective is to evaluate the safety and tolerability of {intervention},
assessed by the incidence of treatment-emergent adverse events (TEAEs),
serious adverse events (SAEs), and adverse events leading to discontinuation.
""",

    "secondary_objective_pk": """
A secondary objective is to characterize the pharmacokinetic profile of {intervention},
including {pk_parameters}, at {timepoints}.
""",

    "exploratory_objective": """
An exploratory objective is to {action}, assessed by {endpoint}.
""",
}


# ============================================================================
# THERAPEUTIC AREA-SPECIFIC TEMPLATES
# ============================================================================

TA_SPECIFIC_TEMPLATES = {
    "oncology": {
        "os_endpoint": """
The primary endpoint is overall survival (OS), defined as the time from
randomization to death from any cause. Participants without documented death
will be censored at the date last known alive.
OS will be analyzed using Kaplan-Meier methods. The stratified log-rank test
will be used for the primary comparison between treatment groups, stratified
by {stratification_factors}. Hazard ratio (HR) and 95% CI will be estimated
using a Cox proportional hazards model with the same stratification factors.
The analysis will be conducted in the intent-to-treat (ITT) population.
""",

        "pfs_endpoint": """
The primary endpoint is progression-free survival (PFS), defined as the time
from randomization to first documented disease progression per RECIST 1.1
(assessed by {assessment_type}) or death from any cause, whichever occurs first.
Participants without documented progression or death will be censored at the
date of last adequate tumor assessment.
PFS will be analyzed using Kaplan-Meier methods with log-rank test stratified
by {stratification_factors}. HR and 95% CI will be estimated using Cox regression.
The analysis will be conducted in the ITT population.
""",

        "orr_endpoint": """
A secondary endpoint is objective response rate (ORR), defined as the proportion
of participants with confirmed complete response (CR) or partial response (PR)
per RECIST 1.1 as assessed by {assessment_type}.
ORR will be estimated with 95% CI using the Clopper-Pearson exact method.
The analysis will be conducted in the response-evaluable population
(participants with measurable disease at baseline and at least one post-baseline
tumor assessment).
""",

        "dor_endpoint": """
A secondary endpoint is duration of response (DOR), defined as the time from
first documented response (CR or PR) to first documented disease progression
per RECIST 1.1 or death from any cause, whichever occurs first.
DOR will be analyzed using Kaplan-Meier methods in the responder population.
""",
    },

    "cardiovascular": {
        "mace_endpoint": """
The primary endpoint is time to first occurrence of a major adverse cardiovascular
event (MACE), defined as the composite of:
- Cardiovascular death
- Non-fatal myocardial infarction (MI)
- Non-fatal stroke

All potential MACE events will be adjudicated by a blinded, independent Clinical
Events Committee (CEC). MI will be defined according to the Fourth Universal
Definition of Myocardial Infarction. Stroke will be defined as an acute episode
of focal or global neurological dysfunction caused by brain, spinal cord, or
retinal vascular injury.

MACE will be analyzed using Kaplan-Meier methods with stratified log-rank test.
HR and 95% CI will be estimated using Cox proportional hazards regression.
The analysis will be conducted in the ITT population.
""",

        "cv_death_endpoint": """
A secondary endpoint is time to cardiovascular death, defined as death resulting
from cardiovascular causes as adjudicated by the CEC. Deaths of unknown or
undetermined cause will be classified as cardiovascular deaths.
Analysis will use Kaplan-Meier methods in the ITT population.
""",
    },

    "neurology": {
        "cognitive_endpoint": """
The primary endpoint is change from baseline in {scale_name} total score at
Week {timepoint}.
All assessments will be performed by trained and certified raters.
Analysis will be performed using a mixed-effects model for repeated measures
(MMRM) including treatment, visit, treatment-by-visit interaction, baseline
score, and {stratification_factors} as covariates.
The analysis will be conducted in the modified intent-to-treat (mITT) population.
""",

        "disability_progression": """
A secondary endpoint is time to confirmed disability progression, defined as
an increase from baseline in Expanded Disability Status Scale (EDSS) score of:
- ≥1.5 points if baseline EDSS is 0
- ≥1.0 points if baseline EDSS is 1.0 to 5.5
- ≥0.5 points if baseline EDSS is ≥6.0

Progression must be confirmed at a scheduled visit at least 3 months later,
in the absence of relapse.
Analysis will use Kaplan-Meier methods in the ITT population.
""",
    },

    "rheumatology": {
        "acr_response": """
The primary endpoint is the proportion of participants achieving ACR{level}
response at Week {timepoint}.
ACR{level} response is defined as ≥{level}% improvement from baseline in both:
- Tender joint count (68 joints)
- Swollen joint count (66 joints)
AND ≥{level}% improvement in at least 3 of the following 5 measures:
- Patient global assessment (VAS)
- Physician global assessment (VAS)
- Patient pain assessment (VAS)
- HAQ-DI score
- Acute phase reactant (CRP or ESR)

Participants who discontinue early or receive rescue therapy will be classified
as non-responders (non-responder imputation).
The analysis will be conducted in the ITT population using logistic regression.
""",

        "das28_remission": """
A secondary endpoint is the proportion of participants achieving clinical
remission (DAS28-{marker} <2.6) at Week {timepoint}.
Non-responder imputation will be used for missing data.
The analysis will be conducted in the ITT population.
""",
    },
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_endpoint_template(
    endpoint_type: str,
    therapeutic_area: Optional[str] = None,
    endpoint_category: Optional[str] = None
) -> Optional[str]:
    """
    Get appropriate rewrite template for an endpoint.

    Args:
        endpoint_type: primary, secondary, or exploratory
        therapeutic_area: Optional TA for specialized templates
        endpoint_category: Type of endpoint (survival, response, continuous, etc.)

    Returns:
        Template string or None
    """
    # Try TA-specific template first
    if therapeutic_area:
        ta_normalized = therapeutic_area.lower().replace(" ", "_")
        if ta_normalized in TA_SPECIFIC_TEMPLATES:
            ta_templates = TA_SPECIFIC_TEMPLATES[ta_normalized]
            if endpoint_category and endpoint_category in ta_templates:
                return ta_templates[endpoint_category]

    # Fall back to generic templates
    key = f"{endpoint_type}_endpoint_{endpoint_category}" if endpoint_category else None
    if key and key in ENDPOINT_REWRITE_TEMPLATES:
        return ENDPOINT_REWRITE_TEMPLATES[key]

    # Try simpler key
    if endpoint_type in ["primary", "secondary", "exploratory"]:
        for template_key, template in ENDPOINT_REWRITE_TEMPLATES.items():
            if template_key.startswith(endpoint_type):
                return template

    return None


def get_objective_template(
    objective_type: str,
    objective_category: Optional[str] = None
) -> Optional[str]:
    """
    Get appropriate rewrite template for an objective.

    Args:
        objective_type: primary, secondary, or exploratory
        objective_category: Type of objective (efficacy, safety, pk, etc.)

    Returns:
        Template string or None
    """
    key = f"{objective_type}_objective_{objective_category}" if objective_category else None
    if key and key in OBJECTIVE_REWRITE_TEMPLATES:
        return OBJECTIVE_REWRITE_TEMPLATES[key]

    # Try without category
    for template_key, template in OBJECTIVE_REWRITE_TEMPLATES.items():
        if template_key.startswith(objective_type):
            return template

    return None


def get_rewrite_instructions() -> str:
    """
    Get LLM instructions for generating endpoint/objective rewrites.

    Returns:
        Instruction string for prompt injection
    """
    return """
REWRITE INSTRUCTIONS FOR ENDPOINTS AND OBJECTIVES:

When generating an improved_text suggestion, use this structured format:

FOR PRIMARY ENDPOINTS, include ALL of these elements:
1. Endpoint name with explicit type label ("The primary endpoint is...")
2. Operational definition (what exactly is being measured)
3. Assessment timepoint(s) (when it is measured)
4. Measurement method/criteria (how it is measured, e.g., RECIST 1.1, ADAS-Cog)
5. Censoring rules (for time-to-event endpoints)
6. Statistical analysis method (Kaplan-Meier, MMRM, logistic regression, etc.)
7. Analysis population (ITT, mITT, Per-Protocol)
8. Non-inferiority/superiority margin if applicable

FOR SECONDARY ENDPOINTS, include:
1. Endpoint name with type label ("A secondary endpoint is...")
2. Operational definition
3. Assessment timepoint(s)
4. Analysis method (brief)
5. Analysis population

FOR OBJECTIVES, include:
1. Objective type label ("The primary objective is..." or "A secondary objective is...")
2. The action to be evaluated (compare, demonstrate, evaluate, assess)
3. The linked endpoint that will measure this objective
4. Assessment timepoint

FORMATTING RULES:
- Use complete sentences
- Be specific and measurable
- Avoid vague terms ("improvement", "change") without specifying criteria
- Include all statistical elements needed for pre-specification per ICH E9
- Make the text copy-paste ready for protocol insertion
"""


def apply_template(
    template: str,
    context: Dict[str, Any]
) -> str:
    """
    Apply context values to a template.

    Args:
        template: Template string with {placeholders}
        context: Dict of values to substitute

    Returns:
        Filled template string
    """
    try:
        # Handle optional fields
        if "{margin_statement}" in template:
            if context.get("margin"):
                context["margin_statement"] = (
                    f"Non-inferiority will be demonstrated if the lower bound of the "
                    f"95% CI for the treatment difference excludes {context['margin']}."
                )
            else:
                context["margin_statement"] = ""

        return template.format(**context)
    except KeyError as e:
        logger.warning(f"Missing template context key: {e}")
        return template


# Log configuration on import
logger.info("Rewrite Templates loaded:")
logger.info(f"   - Endpoint templates: {len(ENDPOINT_REWRITE_TEMPLATES)}")
logger.info(f"   - Objective templates: {len(OBJECTIVE_REWRITE_TEMPLATES)}")
logger.info(f"   - TA-specific templates: {list(TA_SPECIFIC_TEMPLATES.keys())}")


__all__ = [
    "ENDPOINT_REWRITE_TEMPLATES",
    "OBJECTIVE_REWRITE_TEMPLATES",
    "TA_SPECIFIC_TEMPLATES",
    "get_endpoint_template",
    "get_objective_template",
    "get_rewrite_instructions",
    "apply_template",
    "EndpointTemplate",
]
