#!/usr/bin/env python3
"""
Therapeutic Area (TA) Specific Endpoint Guidance

Provides TA-specific guidance for endpoint validation including:
- Standard endpoint definitions for each TA
- Common issues to flag
- Regulatory references
- Recommended analysis methods

Used by prompt_optimizer.py to inject TA-specific context into LLM prompts.
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# ============================================================================
# THERAPEUTIC AREA ENDPOINT GUIDANCE
# ============================================================================

TA_ENDPOINT_GUIDANCE: Dict[str, Dict[str, Any]] = {
    "oncology": {
        "primary_endpoints": [
            {
                "name": "Overall Survival (OS)",
                "definition": "Time from randomization to death from any cause",
                "censoring": "Censored at last known alive date for participants without documented death",
                "analysis": "Kaplan-Meier, log-rank test stratified by [factors], Cox regression for HR with 95% CI",
                "regulatory": "FDA Oncology Guidance (2007), ICH E9 Section 2.2",
                "required_elements": ["Censoring rules", "Stratification factors", "HR estimation method"]
            },
            {
                "name": "Progression-Free Survival (PFS)",
                "definition": "Time from randomization to documented disease progression (per RECIST 1.1) or death from any cause, whichever occurs first",
                "censoring": "Censored at date of last tumor assessment for participants without progression or death",
                "analysis": "Kaplan-Meier with IRC confirmation for registration-enabling trials",
                "regulatory": "FDA PFS Guidance (2007), FDA Clinical Trial Endpoints for Oncology (2018)",
                "required_elements": ["RECIST version", "IRC vs investigator assessment", "Censoring rules", "Assessment schedule"]
            },
            {
                "name": "Objective Response Rate (ORR)",
                "definition": "Proportion of participants with confirmed complete response (CR) or partial response (PR) per RECIST 1.1",
                "analysis": "Two-sided 95% Clopper-Pearson exact CI; Cochran-Mantel-Haenszel for group comparisons",
                "regulatory": "FDA Clinical Trial Endpoints for Oncology (2018)",
                "required_elements": ["Response criteria version (RECIST 1.1)", "Confirmation requirement", "Assessment timing"]
            },
        ],
        "common_issues": [
            "Missing RECIST version specification (must state 'RECIST 1.1' or 'iRECIST' explicitly)",
            "No IRC vs investigator assessment specification for registration trials",
            "Missing censoring rules for PFS/OS endpoints",
            "Assessment schedule not aligned with imaging intervals",
            "Missing definition of evaluable population for response endpoints"
        ],
        "validation_prompt": """
ONCOLOGY-SPECIFIC ENDPOINT CHECKS:
1. Survival endpoints (OS, PFS): MUST include censoring rules and analysis method (log-rank, Cox)
2. Response endpoints (ORR, CR rate): MUST specify RECIST version (1.1 or iRECIST)
3. For registration trials: IRC assessment required for primary efficacy
4. Assessment schedule: Verify imaging intervals support endpoint assessment
5. Duration of response (DOR): Must define start (first response) and end (progression/death)
"""
    },

    "cardiovascular": {
        "primary_endpoints": [
            {
                "name": "MACE (Major Adverse Cardiovascular Events)",
                "definition": "Composite of cardiovascular death, non-fatal myocardial infarction, and non-fatal stroke",
                "analysis": "Time-to-first-event using Kaplan-Meier, log-rank test, Cox regression",
                "adjudication": "All events adjudicated by blinded Clinical Events Committee (CEC)",
                "regulatory": "FDA Cardiovascular Guidance (2008), ICH E14",
                "required_elements": ["Component definitions", "CEC adjudication", "MI/stroke diagnostic criteria"]
            },
            {
                "name": "CV Death",
                "definition": "Death from cardiovascular causes as adjudicated by CEC",
                "analysis": "Time-to-event using Kaplan-Meier, Cox regression",
                "regulatory": "FDA Cardiovascular Guidance (2008)",
                "required_elements": ["CV death classification criteria", "Unknown cause handling"]
            },
        ],
        "common_issues": [
            "Incomplete MACE component definitions (must define each: CV death, MI, stroke)",
            "Missing Clinical Events Committee (CEC) specification",
            "MI definition not specified (Type 1 vs Type 2, diagnostic criteria)",
            "Stroke definition missing (ischemic vs hemorrhagic, TIA handling)",
            "Unknown cause of death not addressed in CV death definition"
        ],
        "validation_prompt": """
CARDIOVASCULAR-SPECIFIC ENDPOINT CHECKS:
1. MACE composite: MUST define each component (CV death, MI, stroke) with diagnostic criteria
2. Adjudication: CEC required for all CV events in registration trials
3. MI: Specify type (Type 1, 2) and diagnostic criteria (troponin thresholds, symptoms)
4. Stroke: Define ischemic vs hemorrhagic, TIA inclusion/exclusion
5. CV death: Include handling of unknown/undetermined cause of death
"""
    },

    "neurology": {
        "primary_endpoints": [
            {
                "name": "Cognitive Function (ADAS-Cog)",
                "definition": "Change from baseline in ADAS-Cog 11 or 13 total score at [timepoint]",
                "analysis": "MMRM with treatment, visit, baseline score, and treatment-by-visit interaction",
                "regulatory": "FDA Alzheimer's Guidance (2018)",
                "required_elements": ["ADAS-Cog version (11 vs 13)", "Assessment timepoint", "MCID threshold"]
            },
            {
                "name": "Disability Progression (EDSS)",
                "definition": "Time to 3-month confirmed disability progression defined as EDSS increase of ≥1.5 points if baseline EDSS 0, ≥1.0 points if baseline EDSS 1.0-5.5, or ≥0.5 points if baseline EDSS ≥6.0",
                "analysis": "Kaplan-Meier, log-rank test, Cox regression",
                "regulatory": "FDA MS Guidance, EMA MS Guidance",
                "required_elements": ["Confirmation period (3 or 6 months)", "Progression thresholds by baseline"]
            },
        ],
        "common_issues": [
            "Missing clinically meaningful difference (MCID) threshold for cognitive scales",
            "Confirmation period not specified for disability progression",
            "Baseline EDSS-dependent progression thresholds not specified",
            "Rater training/certification requirements not mentioned",
            "Missing timing of assessments relative to relapses"
        ],
        "validation_prompt": """
NEUROLOGY-SPECIFIC ENDPOINT CHECKS:
1. Cognitive scales: Specify version, MCID, rater training requirements
2. EDSS progression: Define thresholds by baseline EDSS, confirmation period (3 or 6 months)
3. Relapse assessment: Define relapse criteria, assessment timing relative to acute events
4. Functional outcomes: Specify validated instrument, assessment schedule
5. Consider fatigue, depression as confounders for cognitive/functional measures
"""
    },

    "immunology_rheumatology": {
        "primary_endpoints": [
            {
                "name": "ACR20/50/70 Response",
                "definition": "Proportion of participants achieving ≥20%/50%/70% improvement in ACR criteria at [timepoint]",
                "analysis": "Non-responder imputation for missing data; CMH test or logistic regression",
                "regulatory": "FDA RA Guidance, ACR/EULAR Response Criteria",
                "required_elements": ["ACR level (20/50/70)", "Assessment timepoint", "Missing data handling"]
            },
            {
                "name": "DAS28 Remission",
                "definition": "Proportion achieving DAS28-CRP <2.6 or DAS28-ESR <2.6 at [timepoint]",
                "analysis": "Non-responder imputation; logistic regression with baseline DAS28 as covariate",
                "regulatory": "FDA RA Guidance, EULAR Response Criteria",
                "required_elements": ["DAS28 version (CRP vs ESR)", "Remission threshold", "Missing data handling"]
            },
        ],
        "common_issues": [
            "ACR response level (20/50/70) not specified",
            "DAS28 version (CRP vs ESR) not specified",
            "Missing data handling not defined (NRI vs other methods)",
            "Rescue medication impact on response assessment not addressed",
            "Imaging endpoints (X-ray, MRI) missing scoring system specification"
        ],
        "validation_prompt": """
RHEUMATOLOGY-SPECIFIC ENDPOINT CHECKS:
1. ACR response: Specify level (20/50/70), timepoint, rescue medication handling
2. DAS28: Specify version (CRP vs ESR), remission threshold (2.6 vs 3.2)
3. Missing data: NRI is standard; specify imputation method for all binary endpoints
4. Rescue medication: Define impact on response (NRI after rescue?)
5. Imaging: Specify scoring method (mTSS, Sharp-van der Heijde), reader training
"""
    },

    "respiratory": {
        "primary_endpoints": [
            {
                "name": "FEV1 Change from Baseline",
                "definition": "Change from baseline in pre-bronchodilator FEV1 (L) at [timepoint]",
                "analysis": "MMRM with treatment, visit, baseline FEV1, and treatment-by-visit interaction",
                "regulatory": "FDA COPD Guidance, EMA COPD Guidance",
                "required_elements": ["Pre- vs post-bronchodilator", "Timepoint", "MCID (~100mL)"]
            },
            {
                "name": "Annualized Exacerbation Rate",
                "definition": "Rate of moderate-to-severe COPD exacerbations per patient-year",
                "analysis": "Negative binomial regression with log(time on study) offset",
                "regulatory": "FDA COPD Guidance",
                "required_elements": ["Exacerbation definition (moderate vs severe)", "Analysis offset for exposure time"]
            },
        ],
        "common_issues": [
            "Pre- vs post-bronchodilator FEV1 not specified",
            "Exacerbation severity definition missing (moderate: steroids/antibiotics; severe: hospitalization)",
            "Assessment timing relative to bronchodilator use not specified",
            "Spirometry quality control/training not mentioned",
            "Seasonal variation not addressed in study design"
        ],
        "validation_prompt": """
RESPIRATORY-SPECIFIC ENDPOINT CHECKS:
1. FEV1: Specify pre- vs post-bronchodilator, MCID (~100mL for COPD)
2. Exacerbations: Define severity criteria (moderate vs severe), include exposure offset
3. Spirometry: Specify ATS/ERS standards compliance, quality control
4. Assessment timing: Define washout from rescue medication, time of day
5. Consider seasonal variation impact on study design and timing
"""
    },

    "psychiatry": {
        "primary_endpoints": [
            {
                "name": "Depression Severity (MADRS/HAM-D)",
                "definition": "Change from baseline in MADRS or HAM-D-17 total score at [timepoint]",
                "analysis": "MMRM with treatment, visit, baseline score, and treatment-by-visit interaction",
                "regulatory": "FDA Antidepressant Guidance",
                "required_elements": ["Scale version (MADRS vs HAM-D)", "Timepoint", "Rater training", "Response threshold"]
            },
            {
                "name": "Depression Response",
                "definition": "Proportion of participants with ≥50% reduction in MADRS/HAM-D score from baseline at [timepoint]",
                "analysis": "NRI for missing data; logistic regression with baseline score as covariate",
                "regulatory": "FDA Antidepressant Guidance",
                "required_elements": ["Response threshold (50%)", "Remission threshold (if applicable)", "Missing data handling"]
            },
        ],
        "common_issues": [
            "Clinician-rated vs patient-rated scale not specified",
            "Rater training and inter-rater reliability requirements missing",
            "Placebo response mitigation strategies not addressed",
            "Response (50%) vs remission (score threshold) definitions missing",
            "Assessment timing relative to drug levels not specified"
        ],
        "validation_prompt": """
PSYCHIATRY-SPECIFIC ENDPOINT CHECKS:
1. Rating scales: Specify version (MADRS, HAM-D-17), rater training requirements
2. Response vs remission: Define both (response = 50% reduction; remission = score threshold)
3. Placebo response: Consider mitigation strategies in design
4. Rater training: Specify inter-rater reliability requirements, blinding maintenance
5. Missing data: Define handling method (MMRM preferred for continuous, NRI for binary)
"""
    },

    "infectious_disease": {
        "primary_endpoints": [
            {
                "name": "Viral Load Reduction",
                "definition": "Proportion of participants with HIV-1 RNA <50 copies/mL at Week 48",
                "analysis": "FDA Snapshot algorithm; Cochran-Mantel-Haenszel test stratified by baseline viral load",
                "regulatory": "FDA HIV Guidance (2015)",
                "required_elements": ["Viral load threshold", "Time point", "Analysis algorithm (Snapshot vs TLOVR)"]
            },
            {
                "name": "Clinical Cure/Microbiological Eradication",
                "definition": "Resolution of signs/symptoms AND eradication of baseline pathogen at test-of-cure visit",
                "analysis": "Modified ITT (mITT) and microbiologically evaluable populations",
                "regulatory": "FDA Antibacterial Guidance (2019)",
                "required_elements": ["Cure definition", "TOC visit timing", "Analysis populations"]
            },
        ],
        "common_issues": [
            "Missing specification of viral load assay sensitivity threshold",
            "Test-of-cure visit timing not specified",
            "Snapshot vs TLOVR algorithm not specified for HIV",
            "Missing handling of missing data (FDA Snapshot = failure)",
            "Microbiological evaluable population not defined"
        ],
        "validation_prompt": """
INFECTIOUS DISEASE-SPECIFIC ENDPOINT CHECKS:
1. Viral load: Specify assay threshold (e.g., <50 copies/mL), analysis algorithm (FDA Snapshot)
2. Antibacterial: Define clinical cure criteria, test-of-cure timing, pathogen eradication
3. Analysis populations: mITT and microbiologically evaluable must be pre-defined
4. Missing data: Snapshot algorithm treats missing as failure
5. Resistance: Include emergence of resistance as secondary endpoint
"""
    },

    "dermatology": {
        "primary_endpoints": [
            {
                "name": "PASI 75/90/100 Response (Psoriasis)",
                "definition": "Proportion of participants achieving ≥75%/90%/100% improvement in PASI score from baseline at Week [X]",
                "analysis": "Non-responder imputation; CMH test or logistic regression",
                "regulatory": "FDA Psoriasis Guidance",
                "required_elements": ["PASI level (75/90/100)", "Timepoint", "Missing data handling (NRI)"]
            },
            {
                "name": "IGA Success (Clear/Almost Clear)",
                "definition": "Proportion achieving IGA score of 0 (clear) or 1 (almost clear) with ≥2-grade improvement at Week [X]",
                "analysis": "Non-responder imputation; logistic regression",
                "regulatory": "FDA Dermatology Guidance",
                "required_elements": ["IGA scale version", "Success definition", "Improvement requirement"]
            },
        ],
        "common_issues": [
            "PASI response level (75 vs 90 vs 100) not specified",
            "IGA scale version not specified (5-point vs other)",
            "Co-primary vs hierarchical testing not specified for IGA + PASI",
            "Missing data handling not defined (NRI standard)",
            "Assessment timing relative to treatment not specified"
        ],
        "validation_prompt": """
DERMATOLOGY-SPECIFIC ENDPOINT CHECKS:
1. PASI: Specify response level (75/90/100), timepoint, NRI for missing data
2. IGA: Specify scale version, success definition (0/1 with 2-grade improvement)
3. Co-primary: If PASI + IGA both primary, specify multiplicity adjustment
4. Atopic dermatitis: Use EASI-75, IGA, pruritus NRS with appropriate thresholds
5. Photographic assessment: Specify standardization if used
"""
    },

    "gastroenterology": {
        "primary_endpoints": [
            {
                "name": "Clinical Remission (IBD)",
                "definition": "Mayo score ≤2 with no individual subscore >1, or CDAI <150 for Crohn's",
                "analysis": "Non-responder imputation; CMH test stratified by prior biologic use",
                "regulatory": "FDA IBD Guidance (2022)",
                "required_elements": ["Remission definition (Mayo/CDAI)", "Timepoint", "Endoscopic component"]
            },
            {
                "name": "Endoscopic Improvement",
                "definition": "Mayo endoscopic subscore of 0 or 1, or SES-CD reduction ≥50% from baseline",
                "analysis": "Central reading; non-responder imputation",
                "regulatory": "FDA IBD Guidance (2022)",
                "required_elements": ["Endoscopic scoring system", "Central vs local reading", "Improvement threshold"]
            },
        ],
        "common_issues": [
            "Clinical vs endoscopic remission components not separated",
            "Central reading requirement not specified for endoscopy",
            "Mayo score version (full vs partial) not specified",
            "Steroid-free remission not included as key secondary",
            "Prior biologic failure stratification missing"
        ],
        "validation_prompt": """
GASTROENTEROLOGY-SPECIFIC ENDPOINT CHECKS:
1. IBD remission: Specify clinical (Mayo/CDAI) AND endoscopic components separately
2. Endoscopy: Central reading required for registration; specify scoring system
3. Steroid-free: Include corticosteroid-free remission as secondary endpoint
4. Crohn's: Use CDAI <150 or PRO2 remission per FDA guidance
5. Stratification: Include prior biologic exposure as stratification factor
"""
    },

    "endocrinology": {
        "primary_endpoints": [
            {
                "name": "HbA1c Change (Diabetes)",
                "definition": "Change from baseline in HbA1c (%) at Week 24/26",
                "analysis": "MMRM with baseline HbA1c, treatment, visit, treatment-by-visit interaction",
                "regulatory": "FDA Diabetes Guidance (2008)",
                "required_elements": ["Timepoint (24-26 weeks minimum)", "Baseline HbA1c", "Rescue medication handling"]
            },
            {
                "name": "Body Weight Change (Obesity)",
                "definition": "Percent change from baseline in body weight at Week 52/68",
                "analysis": "MMRM; co-primary with categorical ≥5% weight loss",
                "regulatory": "FDA Obesity Guidance (2007)",
                "required_elements": ["Timepoint", "Percent vs absolute", "Categorical threshold (5%/10%)"]
            },
        ],
        "common_issues": [
            "Rescue medication handling not specified (treat as failure vs censor)",
            "HbA1c assay standardization (NGSP/DCCT) not specified",
            "Obesity requires BOTH continuous AND categorical endpoints",
            "CV safety assessment not addressed for diabetes drugs",
            "Missing hypoglycemia definition and severity grading"
        ],
        "validation_prompt": """
ENDOCRINOLOGY-SPECIFIC ENDPOINT CHECKS:
1. Diabetes: HbA1c change at 24-26 weeks minimum; specify rescue medication handling
2. Hypoglycemia: Define severity levels (glucose thresholds, symptoms, assistance needed)
3. Obesity: MUST have both continuous (% change) AND categorical (≥5% responders) endpoints
4. CV safety: Address MACE for diabetes drugs per FDA requirements
5. Assay: Specify HbA1c standardization method (NGSP-certified)
"""
    },

    "ophthalmology": {
        "primary_endpoints": [
            {
                "name": "BCVA Change (Visual Acuity)",
                "definition": "Mean change from baseline in BCVA (ETDRS letters) at Month 12",
                "analysis": "MMRM with baseline BCVA, treatment, visit, treatment-by-visit; LOCF sensitivity",
                "regulatory": "FDA Ophthalmology Guidance",
                "required_elements": ["ETDRS letter score", "Timepoint", "Certified examiner requirement"]
            },
            {
                "name": "Anatomic Outcome (OCT)",
                "definition": "Change from baseline in central subfield thickness (CST) by SD-OCT at Month 12",
                "analysis": "MMRM; central reading center for OCT",
                "regulatory": "FDA AMD/DME Guidance",
                "required_elements": ["OCT platform specification", "Central reading", "CST measurement"]
            },
        ],
        "common_issues": [
            "ETDRS chart and certified examiner requirements not specified",
            "OCT central reading center not specified",
            "Missing fellow eye analysis for bilateral disease",
            "Rescue treatment criteria and handling not defined",
            "Anti-VEGF injection frequency/PRN criteria not specified"
        ],
        "validation_prompt": """
OPHTHALMOLOGY-SPECIFIC ENDPOINT CHECKS:
1. Visual acuity: ETDRS letters, certified examiners, specify chart and distance
2. OCT: Central reading center required; specify platform and measurement location
3. AMD/DME: Include both functional (BCVA) and anatomic (OCT) endpoints
4. Rescue: Define rescue treatment criteria and analysis handling
5. Bilateral: Specify analysis approach for fellow eye (independence assumption)
"""
    },

    "hematology": {
        "primary_endpoints": [
            {
                "name": "Hemoglobin Response (Anemia)",
                "definition": "Proportion achieving hemoglobin ≥10 g/dL or ≥1 g/dL increase from baseline without transfusion",
                "analysis": "Logistic regression; Kaplan-Meier for time to response",
                "regulatory": "FDA Anemia Guidance",
                "required_elements": ["Hgb threshold", "Transfusion-free requirement", "Response duration"]
            },
            {
                "name": "Transfusion Independence",
                "definition": "Proportion achieving ≥8 consecutive weeks without RBC transfusion",
                "analysis": "Proportion with 95% CI; duration of transfusion independence",
                "regulatory": "FDA Hematology Guidance",
                "required_elements": ["Duration threshold (8+ weeks)", "RBC vs all transfusions", "Baseline transfusion burden"]
            },
        ],
        "common_issues": [
            "Transfusion-free period duration not specified",
            "Hemoglobin response threshold not defined",
            "Baseline transfusion burden assessment period not specified",
            "Missing durability of response assessment",
            "Thrombotic event monitoring not addressed for ESAs"
        ],
        "validation_prompt": """
HEMATOLOGY-SPECIFIC ENDPOINT CHECKS:
1. Anemia: Specify Hgb threshold AND transfusion-free requirement
2. Transfusion independence: Define minimum duration (typically ≥8 weeks)
3. Baseline: Specify transfusion burden assessment period (e.g., 8 weeks pre-treatment)
4. Durability: Include duration of response as key secondary
5. Safety: Address thrombotic risk for erythropoiesis-stimulating agents
"""
    },

    "vaccines": {
        "primary_endpoints": [
            {
                "name": "Seroconversion Rate",
                "definition": "Proportion achieving ≥4-fold rise in antibody titer from baseline at Day 28/56",
                "analysis": "Proportion with 95% CI; comparison to control/comparator vaccine",
                "regulatory": "FDA Vaccines Guidance (2021)",
                "required_elements": ["Seroconversion definition (4-fold rise)", "Timepoint", "Assay specification"]
            },
            {
                "name": "Geometric Mean Titer (GMT)",
                "definition": "GMT of neutralizing antibodies at Day 28/56 post-vaccination",
                "analysis": "GMT ratio with 95% CI; non-inferiority margin for comparisons",
                "regulatory": "FDA Vaccines Guidance",
                "required_elements": ["Antibody type (neutralizing/binding)", "Assay and lab", "Non-inferiority margin"]
            },
        ],
        "common_issues": [
            "Seroconversion threshold (4-fold) not specified",
            "Assay validation and central lab requirement not specified",
            "Non-inferiority margin for immunobridging not defined",
            "Reactogenicity assessment period not specified",
            "Correlate of protection assumption not justified"
        ],
        "validation_prompt": """
VACCINE-SPECIFIC ENDPOINT CHECKS:
1. Immunogenicity: Specify seroconversion definition (≥4-fold rise), GMT, seroprotection
2. Assay: Central lab, validated assay, specify antibody type (neutralizing vs binding)
3. Non-inferiority: If immunobridging, specify NI margin based on known correlates
4. Safety: Solicited reactogenicity period (7 days local, 7-14 days systemic)
5. Timepoints: Day 28/56 for immune response; 6-12 months for persistence
"""
    },

    "rare_disease": {
        "primary_endpoints": [
            {
                "name": "Disease-Specific Functional Scale",
                "definition": "Change from baseline in [disease-specific scale] at Week/Month [X]",
                "analysis": "MMRM or rank-based methods for small samples; responder analysis",
                "regulatory": "FDA Rare Disease Guidance (2019)",
                "required_elements": ["Validated scale for disease", "MCID if established", "Natural history context"]
            },
            {
                "name": "Biomarker Endpoint",
                "definition": "Change from baseline in [biomarker] at Week/Month [X]",
                "analysis": "Percent change; correlation with clinical outcomes",
                "regulatory": "FDA Biomarker Guidance, Rare Disease Guidance",
                "required_elements": ["Biomarker validation status", "Relationship to clinical outcomes", "Assay specifications"]
            },
        ],
        "common_issues": [
            "Natural history data not referenced for context",
            "Scale not validated for specific rare disease population",
            "Small sample size statistical methods not appropriate",
            "Biomarker not qualified or relationship to outcomes not established",
            "Missing caregiver/observer-reported outcomes for pediatric populations"
        ],
        "validation_prompt": """
RARE DISEASE-SPECIFIC ENDPOINT CHECKS:
1. Natural history: Reference natural history data to contextualize treatment effect
2. Endpoint validation: Confirm scale/biomarker validated in target population
3. Statistical methods: Consider rank-based or Bayesian methods for small samples
4. Biomarker: If primary, establish relationship to clinical outcomes
5. Pediatric: Include age-appropriate assessments and caregiver-reported outcomes
"""
    },
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_ta_endpoint_guidance(ta: str) -> Optional[str]:
    """
    Get therapeutic area-specific endpoint guidance for prompt injection.

    Args:
        ta: Therapeutic area identifier (e.g., 'oncology', 'cardiovascular')

    Returns:
        Formatted guidance string for prompt injection, or None if TA not found
    """
    # Normalize TA name
    ta_normalized = ta.lower().replace(" ", "_").replace("-", "_")

    # Map common variations
    ta_map = {
        # Cardiovascular
        "cardio": "cardiovascular",
        "cv": "cardiovascular",
        "heart": "cardiovascular",
        # Neurology
        "neuro": "neurology",
        "cns": "neurology",
        "alzheimer": "neurology",
        "parkinson": "neurology",
        "ms": "neurology",
        "multiple_sclerosis": "neurology",
        # Immunology/Rheumatology
        "rheum": "immunology_rheumatology",
        "rheumatology": "immunology_rheumatology",
        "immunology": "immunology_rheumatology",
        "ra": "immunology_rheumatology",
        "lupus": "immunology_rheumatology",
        # Respiratory
        "pulm": "respiratory",
        "pulmonary": "respiratory",
        "copd": "respiratory",
        "asthma": "respiratory",
        # Psychiatry
        "psych": "psychiatry",
        "depression": "psychiatry",
        "schizophrenia": "psychiatry",
        "anxiety": "psychiatry",
        # Infectious disease
        "infectious": "infectious_disease",
        "id": "infectious_disease",
        "hiv": "infectious_disease",
        "antibacterial": "infectious_disease",
        "antiviral": "infectious_disease",
        "antibiotic": "infectious_disease",
        # Dermatology
        "derm": "dermatology",
        "skin": "dermatology",
        "psoriasis": "dermatology",
        "atopic_dermatitis": "dermatology",
        "eczema": "dermatology",
        # Gastroenterology
        "gi": "gastroenterology",
        "gastro": "gastroenterology",
        "ibd": "gastroenterology",
        "crohns": "gastroenterology",
        "crohn": "gastroenterology",
        "ulcerative_colitis": "gastroenterology",
        "uc": "gastroenterology",
        # Endocrinology
        "endo": "endocrinology",
        "diabetes": "endocrinology",
        "obesity": "endocrinology",
        "metabolic": "endocrinology",
        # Ophthalmology
        "ophtho": "ophthalmology",
        "eye": "ophthalmology",
        "amd": "ophthalmology",
        "dme": "ophthalmology",
        "glaucoma": "ophthalmology",
        # Hematology
        "heme": "hematology",
        "blood": "hematology",
        "anemia": "hematology",
        # Vaccines
        "vaccine": "vaccines",
        "immunization": "vaccines",
        # Rare disease
        "rare": "rare_disease",
        "orphan": "rare_disease",
        "ultra_rare": "rare_disease",
    }

    ta_key = ta_map.get(ta_normalized, ta_normalized)

    if ta_key not in TA_ENDPOINT_GUIDANCE:
        logger.debug(f"No TA-specific guidance available for: {ta} (normalized: {ta_key})")
        return None

    guidance = TA_ENDPOINT_GUIDANCE[ta_key]

    # Build formatted guidance string
    result = f"\n{guidance.get('validation_prompt', '')}\n"

    # Add common issues
    common_issues = guidance.get("common_issues", [])
    if common_issues:
        result += "\nCOMMON ISSUES IN THIS THERAPEUTIC AREA:\n"
        for issue in common_issues[:5]:  # Limit to 5
            result += f"- {issue}\n"

    return result


def get_ta_primary_endpoints(ta: str) -> List[Dict[str, Any]]:
    """
    Get list of primary endpoints for a therapeutic area.

    Args:
        ta: Therapeutic area identifier

    Returns:
        List of primary endpoint definitions
    """
    ta_normalized = ta.lower().replace(" ", "_").replace("-", "_")

    ta_map = {
        "cardio": "cardiovascular",
        "cv": "cardiovascular",
        "neuro": "neurology",
        "rheum": "immunology_rheumatology",
        "pulm": "respiratory",
        "psych": "psychiatry",
    }

    ta_key = ta_map.get(ta_normalized, ta_normalized)

    if ta_key in TA_ENDPOINT_GUIDANCE:
        return TA_ENDPOINT_GUIDANCE[ta_key].get("primary_endpoints", [])

    return []


def validate_endpoint_for_ta(endpoint_text: str, ta: str) -> List[str]:
    """
    Validate an endpoint description against TA-specific requirements.

    Args:
        endpoint_text: The endpoint description to validate
        ta: Therapeutic area

    Returns:
        List of potential issues found
    """
    issues = []
    endpoint_lower = endpoint_text.lower()

    ta_normalized = ta.lower().replace(" ", "_")

    # Oncology-specific checks
    if ta_normalized == "oncology":
        if "pfs" in endpoint_lower or "progression" in endpoint_lower:
            if "recist" not in endpoint_lower:
                issues.append("PFS endpoint missing RECIST version specification")
            if "censoring" not in endpoint_lower and "censor" not in endpoint_lower:
                issues.append("PFS endpoint missing censoring rules")

        if "survival" in endpoint_lower or "os" in endpoint_lower:
            if "censor" not in endpoint_lower:
                issues.append("OS endpoint missing censoring rules")

        if "response" in endpoint_lower or "orr" in endpoint_lower:
            if "recist" not in endpoint_lower:
                issues.append("Response endpoint missing RECIST version")

    # Cardiovascular-specific checks
    elif ta_normalized == "cardiovascular" or ta_normalized == "cardio":
        if "mace" in endpoint_lower:
            has_components = all(term in endpoint_lower for term in ["death", "mi", "stroke"])
            if not has_components and "cv death" not in endpoint_lower:
                issues.append("MACE endpoint missing component definitions")
            if "cec" not in endpoint_lower and "adjudicat" not in endpoint_lower:
                issues.append("MACE endpoint missing CEC adjudication specification")

    # Add more TA-specific checks as needed...

    return issues


# Log configuration on import
logger.info("TA Endpoint Guidance loaded:")
logger.info(f"   - Available TAs: {list(TA_ENDPOINT_GUIDANCE.keys())}")


__all__ = [
    "TA_ENDPOINT_GUIDANCE",
    "get_ta_endpoint_guidance",
    "get_ta_primary_endpoints",
    "validate_endpoint_for_ta"
]
