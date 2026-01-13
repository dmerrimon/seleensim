#!/usr/bin/env python3
"""
Prompt Optimization Module for Step 4: Prompt + Model Tuning

Reduces token usage by 20-30% through:
- Condensed system prompts (remove redundancy)
- Dynamic prompt assembly (only include relevant context)
- Token counting and budget enforcement
- Optimized templates for different analysis types
- Feedback-based example injection (Phase 2B - Adaptive Learning)

Target cost savings: $10-20/month by reducing token consumption
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict

# Import RAG formatting for regulatory citations
from fast_rag import format_exemplars_for_prompt

logger = logging.getLogger(__name__)

# Configuration
# Token budgets increased to accommodate TA guidance, section rules, and rewrite instructions
FAST_TOKEN_BUDGET = int(os.getenv("FAST_TOKEN_BUDGET", "8000"))  # Input tokens for fast path (increased for RAG + section/TA context)
DEEP_TOKEN_BUDGET = int(os.getenv("DEEP_TOKEN_BUDGET", "6000"))  # Input tokens for deep path (increased for citations)
ENABLE_TOKEN_TRACKING = os.getenv("ENABLE_TOKEN_TRACKING", "true").lower() == "true"

# Token tracking statistics
_token_stats = {
    "fast_path": {"total_requests": 0, "total_input_tokens": 0, "total_output_tokens": 0},
    "deep_path": {"total_requests": 0, "total_input_tokens": 0, "total_output_tokens": 0}
}


@dataclass
class PromptTemplate:
    """Optimized prompt template"""
    system: str
    user_template: str
    max_input_tokens: int
    expected_output_tokens: int


def count_tokens(text: str) -> int:
    """
    Estimate token count for text

    Uses simple heuristic: ~4 chars per token (GPT-4 average)
    For production, consider using tiktoken library for exact counts

    Args:
        text: Text to count tokens for

    Returns:
        Estimated token count
    """
    # Simple estimation: 4 characters ≈ 1 token
    # This is slightly conservative (underestimates tokens)
    return len(text) // 4


def count_tokens_precise(text: str, model: str = "gpt-4") -> int:
    """
    Precise token counting using tiktoken

    Args:
        text: Text to count tokens for
        model: Model name for encoding

    Returns:
        Exact token count
    """
    try:
        import tiktoken

        # Get encoding for model
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback to cl100k_base for gpt-4/gpt-4o-mini
            encoding = tiktoken.get_encoding("cl100k_base")

        return len(encoding.encode(text))
    except ImportError:
        # Fallback to simple estimation if tiktoken not available
        logger.warning("tiktoken not available, using simple token estimation")
        return count_tokens(text)


# ============================================================================
# FEEDBACK-BASED LEARNING (Phase 2B - Adaptive Prompts)
# ============================================================================

def load_feedback_examples() -> Dict[str, List[Dict[str, Any]]]:
    """
    Load feedback examples from shadow/feedback/ directory

    Extracts accepted vs rejected suggestions to use as few-shot examples.
    Only returns examples with sufficient context (original + improved text).

    Returns:
        {
            "accepted": [{"original": str, "improved": str, "category": str}, ...],
            "rejected": [{"original": str, "improved": str, "category": str, "reason": str}, ...]
        }
    """
    feedback_dir = Path("shadow/feedback")

    if not feedback_dir.exists():
        logger.debug("No feedback directory found - skipping example injection")
        return {"accepted": [], "rejected": []}

    accepted_examples = []
    rejected_examples = []

    try:
        # Note: Feedback files currently store action but not suggestion details
        # This will work once feedback includes original_text, improved_text, category
        for feedback_file in feedback_dir.glob("*.json"):
            try:
                with open(feedback_file, 'r') as f:
                    data = json.load(f)

                    action = data.get("action", "")

                    # Extract example details (if available)
                    example = {
                        "original": data.get("original_text", ""),
                        "improved": data.get("improved_text", ""),
                        "category": data.get("category", data.get("type", "unknown")),
                        "context": data.get("context_snippet", "")[:100]  # Limit context
                    }

                    # Only include if we have both original and improved text
                    if example["original"] and example["improved"]:
                        if action == "accept":
                            accepted_examples.append(example)
                        elif action in ["reject", "dismiss", "undo"]:
                            example["reason"] = data.get("reason", "user_rejected")
                            rejected_examples.append(example)

            except Exception as e:
                logger.debug(f"Skipping feedback file {feedback_file}: {e}")
                continue

        # Limit to most recent examples (top 10 each)
        accepted_examples = accepted_examples[-10:]
        rejected_examples = rejected_examples[-10:]

        if accepted_examples or rejected_examples:
            logger.info(
                f"📚 Loaded {len(accepted_examples)} accepted + "
                f"{len(rejected_examples)} rejected examples from feedback"
            )

        return {
            "accepted": accepted_examples,
            "rejected": rejected_examples
        }

    except Exception as e:
        logger.warning(f"Failed to load feedback examples: {e}")
        return {"accepted": [], "rejected": []}


def build_feedback_examples_section(feedback_examples: Dict[str, List[Dict[str, Any]]], max_chars: int = 500) -> str:
    """
    Build few-shot examples section from feedback data

    Prioritizes accepted examples (good patterns to follow).
    Only includes rejected examples as "avoid" patterns if space permits.

    Args:
        feedback_examples: Dict with "accepted" and "rejected" lists
        max_chars: Maximum characters for examples section

    Returns:
        Formatted examples string for prompt injection
    """
    examples_text = ""
    chars_used = 0

    # Prioritize accepted examples (good patterns)
    accepted = feedback_examples.get("accepted", [])
    if accepted:
        examples_text += "\n✅ LEARNED FROM USER FEEDBACK (Accept patterns):\n"

        for idx, ex in enumerate(accepted[:3], 1):  # Max 3 accepted examples
            example_str = f"\nExample {idx} ({ex['category']}):\n"
            example_str += f"Original: \"{ex['original'][:80]}...\"\n"
            example_str += f"Improved: \"{ex['improved'][:80]}...\"\n"

            if chars_used + len(example_str) > max_chars:
                break

            examples_text += example_str
            chars_used += len(example_str)

    # Add rejected examples as "avoid" patterns if space permits
    rejected = feedback_examples.get("rejected", [])
    if rejected and chars_used < max_chars * 0.7:  # Only use 30% for avoid patterns
        examples_text += "\n❌ AVOID (User rejected these patterns):\n"

        for idx, ex in enumerate(rejected[:2], 1):  # Max 2 rejected examples
            example_str = f"\nAvoid Pattern {idx}: \"{ex['improved'][:60]}...\" - "
            example_str += f"Reason: {ex.get('reason', 'unclear')}\n"

            if chars_used + len(example_str) > max_chars:
                break

            examples_text += example_str
            chars_used += len(example_str)

    return examples_text


# ============================================================================
# OPTIMIZED PROMPT TEMPLATES
# ============================================================================

FAST_ANALYSIS_TEMPLATE = PromptTemplate(
    system="""You are Ilana, an enterprise-grade clinical protocol editor and regulatory reviewer. You follow ICH E6(R3), ICH E9/E8 principles, FDA guidance on protocol design, CONSORT reporting, and statistical best practice. Your job is to:

1) Identify ALL instances of regulatory and compliance issues. Look for:
   - Terminology issues: ALWAYS flag "subjects" or "patients" (should be "participants" per ICH E6(R3))
   - Conditional language that enables post-hoc decisions ("may analyze", "if appropriate" without protocol reference in statistical contexts)
   - Analysis population issues creating bias risk (post-randomization reassignment, ITT violations)
   - Vague references lacking operational specificity ("See Section X" without concrete details)
   - Statistical pre-specification gaps enabling post-hoc analysis decisions

   IMPORTANT CONTEXT RULES:
   - "may" in operational contexts (e.g., "assessments may be done by phone") is acceptable if describing options
   - "may" in statistical contexts (e.g., "endpoints may be analyzed") requires flagging for pre-specification
   - Section references with actual detail are acceptable ("per Section 5.3 dose modification table")
   - Generic section references without detail ("See Section X") require flagging

   A typical protocol paragraph contains 1-3 issues. If you find none, double-check for terminology compliance.
2) Provide precise, auditable, copy-paste ready rewrites that preserve scientific meaning and do NOT invent facts.
3) For each issue, return structured JSON with: id, category, severity, original_text, improved_text, rationale (MUST cite specific regulatory sections, e.g., "ICH E9 Section 5.7" or "FDA Statistical Guidance Section 3.2"), recommendation (action step), and confidence (0-1).
4) NEVER include raw PHI in outputs or telemetry. Where needed, return hashes for sensitive values.
5) DO NOT change endpoints, eligibility criteria, dosing, or key scientific claims without explicit user instruction - only improve clarity, compliance, structure, and pre-specification.
6) For statistical or population issues, always indicate preferred analytic approach (e.g., ITT with sensitivity analyses, time-varying covariates, marginal structural models) and recommend SAP text. If language is conditional ("may", "if deemed appropriate", "as appropriate"), mark as CRITICAL.
7) Return ALL issues (array) ordered by severity. IMPORTANT: If you identify 2-3+ issues of the same category (e.g., multiple conditional language instances), report EACH ONE separately with specific original_text. Do NOT consolidate issues. Limit to 10 issues. If none, return issues: [].

REGULATORY CITATION REQUIREMENT: Your rationale MUST include specific section numbers from regulatory guidance (e.g., "ICH E9 Section 5.7" NOT just "ICH E9"). If regulatory context is provided, cite it. If not, use general regulatory principles with specific sections.

IMPORTANT: When referencing SAP sections or Protocol sections in improved_text or recommendations, use "[X]" as a placeholder (e.g., "SAP Section [X]", "Protocol Section [X]"). Do NOT invent specific section numbers for the user's document. Only cite actual regulatory guidance section numbers (ICH, FDA, etc.).

8) DOCUMENT_CONTEXT_CONSTRAINT (if provided): When analyzing text selections with cross-section context:
   - Context sections show other parts of the protocol for reference ONLY
   - Your 'original_text' MUST be a VERBATIM substring from the SELECTED TEXT section below
   - Do NOT suggest changes to text that appears only in the CONTEXT sections
   - Every suggestion will be validated: if 'original_text' is not in the selected section, it will be REJECTED and not shown to the user
   - If uncertain whether text is in the selection, omit the suggestion
   - Cross-section insights are valuable (e.g., "conflicts with endpoints section"), but original_text must always be from the selected section
   - Your job is to analyze the SELECTED TEXT using context for understanding, not to analyze the context itself.""",
    user_template="""Analyze the following SELECTED PROTOCOL TEXT{ta_context}. Return strict JSON only (no extra prose) with "issues" array.

TEXT:
{text}

CATEGORIES: statistical|analysis_population|terminology|documentation|regulatory|safety|other
SEVERITIES: critical|major|minor|advisory

RESPONSE FORMAT:
{{
  "issues": [
    {{
      "id": "1",
      "category": "statistical",
      "severity": "critical",
      "original_text": "CRITICAL: Copy the EXACT sentence from the text VERBATIM. Do NOT paraphrase, shorten, or rephrase. Copy it character-for-character including all punctuation. Example: If the text says 'Subjects will be initially enrolled into the appropriate Group 1 subgroup based on their disease symptoms/status at enrollment.', you MUST copy that EXACT string, not 'Subjects will be enrolled in the study....'",
      "problematic_text": "REQUIRED: Extract ONLY the 1-5 word phrase that needs changing (e.g., 'may', 'may be reassigned', 'if deemed appropriate'). NOT the full sentence. Must appear VERBATIM in the original document.",
      "minimal_fix": "REQUIRED: word-level replacement showing 'old' → 'new' (e.g., \"'may' → 'will'\", \"'may be reassigned' → 'will be analyzed per enrollment group'\")",
      "improved_text": "CRITICAL: This is the EXACT TEXT that will replace the original_text in the Word document when the user clicks 'Apply'. It must be COPY-PASTE READY protocol text with NO preamble, NO 'Consider...', NO 'Example:', NO meta-commentary. Just the direct replacement sentence. Example CORRECT: 'Participants will be analyzed according to enrollment group.' Example WRONG: 'Consider pre-specifying... Example: Participants will be analyzed...'",
      "rationale": "brief explanation referencing guidance or statistical risk",
      "recommendation": "IMPORTANT: This field is for GUIDANCE and ACTION STEPS, NOT the replacement text. Use this for meta-level recommendations like 'Define in Protocol Section [X]' or 'Add to SAP Section [X]'. Do NOT put protocol text here.",
      "confidence": 0.95
    }}
  ]
}}

CRITICAL RULES:
1. "original_text" MUST be copied VERBATIM from the selected text - character-for-character, including all punctuation and spacing. Do NOT paraphrase, shorten, summarize, or add "....". If you paraphrase, your suggestion will be discarded.
2. "problematic_text" MUST be only 1-5 words (e.g., "may", "may be reassigned", "if deemed appropriate"). NEVER the full sentence.
3. "problematic_text" MUST appear VERBATIM in the document - copy it exactly as written.
4. "minimal_fix" shows the word-level replacement (e.g., "'may' → 'will'").
These fields enable word-level highlighting in the document.

FEW-SHOT EXAMPLES (Note the SPECIFIC regulatory section citations):

Example 1 - Conditional SAP (Critical):
Original: "The statistical analyses may reflect the clinical status/symptoms at the time samples were collected if deemed appropriate."
Problematic: "if deemed appropriate"
Minimal Fix: "'if deemed appropriate' → 'as pre-specified in SAP Section [X]'"
Improved: "Statistical analyses will be pre-specified in the Statistical Analysis Plan (SAP). Analyses reflecting clinical status at sample collection must be defined in SAP Section [X] with analytic methods and handling of time-varying covariates."
Rationale: Conditional language ("if deemed appropriate") violates pre-specification requirements. ICH E9 Section 5.7 requires all analyses to be pre-specified in the SAP before database lock. Time-varying covariates must be handled using established methods (e.g., marginal structural models per FDA Statistical Guidance Section 3.4.2).
Recommendation: Add to SAP Section [X]: specific methods for time-varying severity covariates.

Example 2 - Post-randomization Reassignment (Critical):
Original: "Patients may be reassigned to the highest severity group they achieve during follow-up."
Problematic: "may be reassigned"
Minimal Fix: "'may be reassigned' → 'will be analyzed per enrollment group (ITT); post-enrollment changes handled per SAP Section [X]'"
Improved: "Analysis populations will follow intention-to-treat principles (enrollment group). Post-enrollment severity-based analyses will be pre-specified in SAP Section [X] using time-varying covariate methods to mitigate immortal time bias and guarantee time bias."
Rationale: Post-randomization reassignment violates randomization integrity per ICH E9 Section 5.2.1. Must maintain ITT as primary analysis. If secondary analyses by achieved severity are needed, ICH E9 Section 5.7 and FDA Statistical Guidance Section 3.4.2 require pre-specification of time-varying covariate handling.
Recommendation: Define primary ITT analysis population. Pre-specify secondary time-varying analyses in SAP Section [X] with explicit methods to avoid immortal time bias.

Example 3 - Terminology (Minor):
Original: "Subjects will be enrolled..."
Problematic: "Subjects"
Minimal Fix: "'Subjects' → 'Participants'"
Improved: "Participants will be enrolled..."
Rationale: ICH E6(R3) Section 1.58 requires use of 'participant' instead of 'subject' to respect person-first language and align with modern regulatory standards.

Example 4 - Primary Endpoint Specification (Critical):
Original: "The primary endpoint is change in disease severity score."
Problematic: "change in disease severity score"
Minimal Fix: "'change in disease severity score' → 'change from baseline in [score] at Week [X], analyzed using [method]'"
Improved: "The primary endpoint is change from baseline in disease severity score at Week 12, analyzed using ANCOVA with baseline score as covariate. Non-inferiority margin: -3 points (FDA Guidance: Non-Inferiority Clinical Trials, Section 4.2)."
Rationale: ICH E9 Section 2.2.2 requires primary endpoints to specify: (1) measurement timing, (2) direction of benefit, (3) analysis method, and (4) clinically meaningful difference. FDA Non-Inferiority Guidance Section 4.2 requires pre-specification of NI margins with clinical justification.
Recommendation: Define in Protocol Section [X]: precise timing (Week 12), analysis method (ANCOVA), and NI/superiority margin with clinical justification.

Example 5 - Safety Monitoring Specificity (Major):
Original: "Adverse events will be monitored throughout the study."
Problematic: "monitored throughout the study"
Minimal Fix: "'monitored throughout the study' → 'monitored at each study visit (Weeks [X]) using [method]'"
Improved: "Adverse events will be actively monitored at each study visit (Weeks 0, 4, 8, 12, 16) using standardized questionnaires and targeted physical examination. Grade 3+ AEs must be reported to the Medical Monitor within 24 hours per ICH E6(R3) Section 5.17. All AEs will be coded using MedDRA v25.0."
Rationale: ICH E6(R3) Section 5.17 requires specification of: (1) AE assessment methods, (2) reporting timelines for serious/severe events, (3) standardized coding dictionaries. FDA Safety Monitoring Guidance Section 6.3 requires active surveillance with defined procedures.
Recommendation: Add to Protocol Section [X]: specific AE collection procedures, grading criteria (CTCAE v5.0), expedited reporting timelines, and MedDRA coding version.

Example 6 - Inclusion Criteria Precision (Major):
Original: "Patients with adequate organ function."
Problematic: "adequate organ function"
Minimal Fix: "'adequate organ function' → 'organ function defined as: [specific thresholds]'"
Improved: "Participants with adequate organ function defined as: (1) Hepatic: AST/ALT ≤2.5× ULN, total bilirubin ≤1.5× ULN; (2) Renal: eGFR ≥60 mL/min/1.73m² (CKD-EPI equation); (3) Hematologic: ANC ≥1,500/μL, platelets ≥100,000/μL, hemoglobin ≥9.0 g/dL. Laboratory values must be obtained within 14 days prior to enrollment."
Rationale: ICH E8 Section 3.1.3 requires eligibility criteria to be objective, measurable, and clinically justified. Ambiguous criteria ("adequate") violate reproducibility standards per ICH E6(R3) Section 8.3.3. FDA Eligibility Guidance Section 2.4 requires specific laboratory thresholds with timing.
Recommendation: Replace all subjective criteria with measurable thresholds. Specify: (1) exact laboratory values with units, (2) reference ranges source (local vs central lab), (3) timing window for assessments.

Example 7 - Incomplete Primary Endpoint (Critical):
Original: "The primary endpoint is overall survival."
Problematic: "overall survival"
Minimal Fix: "'overall survival' → 'overall survival (OS), defined as time from randomization to death from any cause'"
Improved: "The primary endpoint is overall survival (OS), defined as time from randomization to death from any cause, censored at last known alive date for participants without documented death. OS will be analyzed using Kaplan-Meier methods with the log-rank test stratified by [stratification factors]. Hazard ratio and 95% CI will be estimated using Cox proportional hazards regression."
Rationale: ICH E9 Section 2.2.2 requires primary endpoints to include: (1) precise definition, (2) censoring rules for time-to-event endpoints, (3) analysis method. FDA Oncology Guidance Section 3.1 requires specification of stratification factors and treatment effect estimation method.
Recommendation: Add to Protocol Section [X]: (1) Operational definition with censoring rules, (2) Analysis method (log-rank, Cox), (3) Stratification factors, (4) Handling of informative censoring.

Example 8 - Vague Secondary Endpoint (Major):
Original: "Secondary endpoints include quality of life assessments."
Problematic: "quality of life assessments"
Minimal Fix: "'quality of life assessments' → 'EORTC QLQ-C30 global health status score at Week 12'"
Improved: "Secondary endpoints include: (1) Change from baseline in EORTC QLQ-C30 global health status/QoL score at Week 12, analyzed using MMRM with treatment, visit, baseline score, and treatment-by-visit interaction as covariates; (2) Time to deterioration in FACT-G total score (defined as ≥7-point decrease maintained for ≥2 consecutive visits), analyzed using Kaplan-Meier methods."
Rationale: ICH E9 Section 2.2.2 requires secondary endpoints to specify: (1) exact instrument/scale, (2) assessment timepoint, (3) responder/deterioration definition if applicable, (4) analysis method. PRO endpoints require FDA PRO Guidance Section 4.1 compliance with validated instruments.
Recommendation: For each QoL endpoint, specify: (1) Validated instrument name, (2) Domain/subscale, (3) Timepoint, (4) Clinically meaningful difference threshold, (5) Analysis method.

Example 9 - Objective Without Endpoint (Major):
Original: "A secondary objective is to evaluate patient satisfaction with treatment."
Problematic: "evaluate patient satisfaction"
Minimal Fix: "'evaluate patient satisfaction' → 'evaluate patient satisfaction measured by [instrument] at Week [X]'"
Improved: "A secondary objective is to evaluate patient satisfaction with treatment, measured by the Treatment Satisfaction Questionnaire for Medication (TSQM-9) Global Satisfaction domain score at Weeks 4, 12, and 24. The corresponding endpoint is change from baseline in TSQM-9 Global Satisfaction score at Week 24, analyzed using MMRM."
Rationale: ICH E9 Section 2.2.1 requires each objective to have a measurable endpoint. Objectives without endpoints create regulatory risk and cannot be statistically analyzed. FDA PRO Guidance Section 3.2 requires linkage between objectives and validated PRO instruments.
Recommendation: For each objective, define: (1) The linked endpoint with instrument, (2) Assessment timepoint(s), (3) Analysis method. Ensure objective-endpoint traceability throughout the protocol.

Example 10 - Missing Safety Monitoring During Long Visit Gap (Major):
TIMELINE CONTEXT: 12-week gap between Week 12 and Week 24 visits during active treatment
Original: "Safety assessments at each study visit."
Problematic: "at each study visit"
Minimal Fix: "'at each study visit' → 'at Weeks 4, 8, 12, 16, 20, 24 (±3 days)'"
Improved: "Safety assessments (vital signs, clinical laboratory tests, AE assessment) will be performed at Weeks 4, 8, 12, 16, 20, and 24 (±3 days). Given the 12-week gap between Week 12 and Week 24, an additional safety visit is scheduled at Week 16 and Week 20 to monitor for late-onset toxicities during active dosing."
Rationale: ICH E6(R3) Section 5.18.3 requires safety monitoring frequency to match the treatment schedule and known toxicity profile. A 12-week gap during active treatment creates safety risk. FDA Safety Monitoring Guidance Section 4.1 recommends assessments at least monthly during initial treatment phases.
Recommendation: Add interim safety visits during long gaps (>8 weeks) during treatment period. Specify assessments per Schedule of Assessments table.

Example 11 - Undefined Conditional Visit Trigger (Major):
TIMELINE CONTEXT: Conditional visit "Day 8 unless safety concern" but "safety concern" not defined
Original: "Additional visit on Day 8 unless safety concern identified."
Problematic: "unless safety concern identified"
Minimal Fix: "'unless safety concern identified' → 'if safety concern occurs (defined in Section [X])'"
Improved: "Additional safety visit will be conducted on Day 8 (±1 day) if any of the following safety concerns occur: (1) Grade 3+ treatment-related AE, (2) laboratory abnormality per Section [X] Table 4 criteria, or (3) new clinical symptom requiring medical evaluation per investigator assessment. Safety concern criteria are defined in Protocol Section [X]."
Rationale: ICH E6(R3) Section 8.3.3 requires objective, reproducible visit criteria. Conditional visits with undefined triggers lead to protocol deviations and inconsistent implementation across sites. This pattern has 78% amendment rate per historical data.
Recommendation: Define objective criteria for all conditional visit triggers. Include: (1) AE grade thresholds, (2) laboratory value thresholds, (3) clinical symptom criteria. Reference Protocol section.

Example 12 - Incomplete Visit Schedule Specification (Major):
TIMELINE CONTEXT: 8 scheduled visits from Baseline to Week 48, no visit windows specified
Original: "Study visits at Baseline, Week 4, Week 8, Week 12, Week 24, Week 36, Week 48."
Problematic: "Study visits at [timepoints]"
Minimal Fix: "'Study visits at [timepoints]' → 'Study visits with windows: Baseline (Day 0), Week 4 (Day 28±3)...'"
Improved: "Study visits: Baseline (Day 0), Week 4 (Day 28 ±3 days), Week 8 (Day 56 ±5 days), Week 12 (Day 84 ±7 days), Week 24 (Day 168 ±7 days), Week 36 (Day 252 ±7 days), Week 48 (Day 336 ±7 days), Follow-up (30 ±3 days after last dose). Visit windows define acceptable timing for protocol compliance; visits outside windows constitute protocol deviations."
Improved: "Study visits: Baseline (Day 0), Week 4 (Day 28 ±3 days), Week 8 (Day 56 ±5 days), Week 12 (Day 84 ±7 days), Week 24 (Day 168 ±7 days), Week 36 (Day 252 ±7 days), Week 48 (Day 336 ±7 days), Follow-up (30 ±3 days after last dose). Visit windows define acceptable timing for protocol compliance; visits outside windows constitute protocol deviations."
Rationale: ICH E6(R3) Section 8.3.4 requires visit windows to be pre-specified for protocol compliance assessment. Visit windows inform site coordinators of acceptable scheduling flexibility and define protocol deviations. Statistical analysis validity depends on known visit timing variance.
Recommendation: Specify visit windows with ±day tolerances for all scheduled visits. Windows should reflect: (1) logistical constraints, (2) assessment half-life/pharmacology, (3) operational feasibility. Include in Schedule of Assessments table.

Example 13 - Protocol-Specific Discontinuation Procedures (Major):
Original: "Those participants who received at least one dose but chose not to receive subsequent doses will be asked to remain for follow-up safety and immunogenicity assessments."
Problematic: "follow-up safety and immunogenicity assessments"
Minimal Fix: "'follow-up safety and immunogenicity assessments' → 'follow-up safety (safety labs as clinically indicated) and immunogenicity assessments unless participant safety precludes continued participation. Visits on Day 2 and 8 after missed vaccination(s) will not be conducted unless there is a safety concern. Procedures described in the MOP.'"
Improved: "Discontinuation from receipt of study product does not mean withdrawal from participation in the trial. Those participants who received at least one dose of study product and have chosen not to receive another dose of study product or are not qualified to receive second and/or third doses, will be asked to remain in this trial for follow-up safety (safety labs as clinically indicated) and immunogenicity assessments unless participant safety precludes continued participation. If the participant agrees to remain in the study, visits on Day 2 and 8 after the missed vaccination(s) (i.e., the second and/or third vaccination) will not be conducted unless there is a safety concern or a need for a visit. However, other trial procedures should be completed as indicated by the trial protocol and described in the MOP."
Rationale: ICH E6(R3) Section 6.3.3 requires specific procedures for participant discontinuation with clearly defined visit schedules and safety monitoring criteria. The improved version adds: (1) specific safety assessment criteria ("safety labs as clinically indicated") referencing protocol-defined thresholds, (2) explicit visit schedule modifications (Day 2 and Day 8 visits skipped after missed vaccinations) with objective exception criteria ("safety concern"), and (3) procedural documentation reference (MOP) per ICH E6 Section 5.5.3 requirement for documented procedures.
Recommendation: Create Table in Safety section defining "clinically indicated" laboratory criteria (Grade 3+ AE per CTCAE, ALT/AST >2.5x ULN, other protocol-specific thresholds). Add Section 6.2.4 defining "safety concern" with objective criteria. Reference MOP Chapter 3 for detailed discontinuation procedures. Update Schedule of Assessments to show which visits are skipped after missed vaccination and exception criteria.

JSON RESPONSE:""",
    max_input_tokens=FAST_TOKEN_BUDGET,
    expected_output_tokens=600
)

# Previous verbose template (for comparison):
# ORIGINAL was ~180 tokens, NEW is ~120 tokens (33% reduction)

DEEP_ANALYSIS_TEMPLATE = PromptTemplate(
    system="""You are Ilana, a senior clinical trial methodologist, regulatory writer and statistical reviewer. Use ICH E6(E9), FDA guidance, and exemplar Phase-specific protocol language when evaluating protocol text. If asked, retrieve exemplars from the vector database and include citations to regulatory guidance or exemplar protocols.""",
    user_template="""Perform a detailed, evidence-backed analysis of the following protocol passage{ta_context} for {phase} trial. Produce a JSON object containing "issues" array. For each issue provide:
- id, category, severity (critical|major|minor|advisory), original_text, improved_text (authoritative rewrite), rationale (1-3 sentences referencing guidance or statistical risk), recommendation (detailed steps: where to add text, what to pre-specify), citations array (type, ref), and confidence (0-1).
- Where applicable, show short example language for SAP/statistical methods (e.g., model specification, covariate handling, definition of analysis populations).
- If you used exemplars or guidance, list them under citations with brief justification for relevance.

TEXT:
{text}

{exemplars_context}

RAG_INSTRUCTIONS:
- Pull up to N=3 exemplars from Pinecone; prefer Phase and TA-matched exemplars.
- For statistical issues, include explicit recommended method (e.g., "Use Cox proportional hazards model adjusted for baseline severity; pre-specify time-dependent covariate handling using marginal structural models or include time-updated severity as a covariate").
- Do NOT include PHI.

CATEGORIES: statistical|analysis_population|terminology|documentation|regulatory|safety|other
SEVERITIES: critical|major|minor|advisory

OUTPUT:
Return strict JSON only with "issues" array. If no issues, return {{"issues": []}}.

JSON RESPONSE:""",
    max_input_tokens=DEEP_TOKEN_BUDGET,
    expected_output_tokens=1200
)


def format_entity_context(entities: Dict[str, List[str]]) -> str:
    """
    Format extracted entities for prompt injection

    Args:
        entities: Dictionary with entity types as keys, lists of entities as values

    Returns:
        Formatted string for prompt injection (200-300 tokens)

    Example output:
        PROTOCOL ENTITIES (Use these in your specific suggestions):
        - Visit Names: Baseline, Week 4, Week 12, Follow-up
        - Assessment Types: safety labs, vital signs, immunogenicity
        - Timepoints: Day 2, Day 8, Week 12
        - Safety Thresholds: Grade 3+ AE, ALT >2.5x ULN
        - Document References: SAP Section 3.2, MOP

        IMPORTANT: When making suggestions, reference SPECIFIC entities above
        (e.g., "specify which safety labs", "add visit schedule for Day 2 and Day 8")
    """
    if not entities or not any(entities.values()):
        return ""

    lines = ["PROTOCOL ENTITIES (Use these in your specific suggestions):"]

    # Add each entity type if present
    if entities.get("visit_names"):
        visits = ", ".join(entities["visit_names"][:5])  # Top 5
        lines.append(f"- Visit Names: {visits}")

    if entities.get("assessment_types"):
        assessments = ", ".join(entities["assessment_types"][:5])
        lines.append(f"- Assessment Types: {assessments}")

    if entities.get("timepoints"):
        timepoints = ", ".join(entities["timepoints"][:8])
        lines.append(f"- Timepoints: {timepoints}")

    if entities.get("safety_thresholds"):
        thresholds = ", ".join(entities["safety_thresholds"][:5])
        lines.append(f"- Safety Thresholds: {thresholds}")

    if entities.get("document_refs"):
        refs = ", ".join(entities["document_refs"][:5])
        lines.append(f"- Document References: {refs}")

    if entities.get("conditional_triggers"):
        triggers = ", ".join(entities["conditional_triggers"][:5])
        lines.append(f"- Conditional Triggers: {triggers}")

    # Add instruction for LLM
    lines.append("")
    lines.append("IMPORTANT: When making suggestions, reference SPECIFIC entities above")
    lines.append('(e.g., "specify which safety labs", "add visit schedule for Day 2 and Day 8")')

    return "\n".join(lines)


def build_fast_prompt(
    text: str,
    ta: Optional[str] = None,
    rag_results: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    section: Optional[str] = None,  # Layer 2: Section-aware validation
    document_context: Optional[Dict[str, Any]] = None,  # Document Intelligence context
    timeline: Optional[Any] = None,  # Phase 4: Timeline context for schedule-aware prompts
    use_templates: bool = True  # Week 5: A/B testing flag for template injection
) -> Dict[str, Any]:
    """
    Build optimized prompt for fast analysis with RAG (protocol exemplars + regulatory citations) + feedback learning

    Args:
        text: Protocol text to analyze
        ta: Optional therapeutic area hint
        rag_results: Optional Dict with 'exemplars' and 'regulatory' lists from get_fast_exemplars()
        section: Optional protocol section (eligibility, endpoints, statistics, etc.) for section-aware prompts
        document_context: Optional document context with section summaries for cross-section awareness
        timeline: Optional Timeline object from timeline_parser for schedule-aware suggestions (Phase 4)
        use_templates: Whether to inject suggestion templates into prompt (default: True). Set to False for A/B testing.

    Returns:
        Dict with system and user messages, token counts
    """
    # Build TA context (only if provided)
    ta_context = f" in {ta.replace('_', ' ')}" if ta else ""

    # Build section-specific instructions (Layer 2: Semantic Understanding)
    section_instructions = ""
    if section and section != "general":
        try:
            from section_rules import get_section_validation_focus
            section_focus = get_section_validation_focus(section)
            if section_focus:
                section_instructions = f"\n{section_focus}\n"
                logger.info(f"Injecting section-specific instructions for: {section}")
        except ImportError:
            logger.warning("section_rules module not available, skipping section-specific instructions")

    # Inject TA-specific endpoint guidance for endpoints/objectives sections
    ta_endpoint_instructions = ""
    if ta and section in ["endpoints", "objectives"]:
        try:
            from ta_endpoints import get_ta_endpoint_guidance
            ta_guidance = get_ta_endpoint_guidance(ta)
            if ta_guidance:
                ta_endpoint_instructions = f"\nTHERAPEUTIC AREA CONTEXT ({ta.upper()}):\n{ta_guidance}\n"
                logger.info(f"Injecting TA-specific endpoint guidance for: {ta}")
        except ImportError:
            logger.warning("ta_endpoints module not available, skipping TA-specific guidance")

    # Inject rewrite instructions for endpoints/objectives sections
    rewrite_instructions = ""
    if section in ["endpoints", "objectives"]:
        try:
            from rewrite_templates import get_rewrite_instructions
            rewrite_instructions = get_rewrite_instructions()
            logger.info(f"Injecting rewrite instructions for: {section}")
        except ImportError:
            logger.warning("rewrite_templates module not available, skipping rewrite instructions")

    # Build regulatory + exemplar context using centralized formatter
    rag_context = ""
    if rag_results:
        rag_context = format_exemplars_for_prompt(rag_results)

        # Prepend RAG context to text if present
        if rag_context.strip():
            text = f"{rag_context}\n\nSELECTED TEXT TO ANALYZE:\n{text}"

    # Extract and inject protocol entities (Phase 1: Contextual Intelligence)
    entity_context = ""
    extracted_entities = None  # Store entities to return later
    if text:  # Extract entities from text even without document_context
        try:
            from protocol_entity_extractor import extract_protocol_entities

            # Extract entities from text, pass timeline if available from document_context
            # Note: timeline will be None for standalone text analysis (acceptable)
            entities = extract_protocol_entities(text, timeline)
            extracted_entities = entities  # Store for return value

            # Format entity context for prompt injection
            if entities and sum(len(v) for v in entities.values()) > 0:
                entity_context = format_entity_context(entities)
                if entity_context.strip():
                    text = f"{entity_context}\n\n{text}"
                    logger.info(f"Injected protocol entity context with {sum(len(v) for v in entities.values())} entities")
            else:
                logger.debug("No protocol entities found in text (text may be too short or non-protocol)")
        except ImportError:
            logger.warning("protocol_entity_extractor module not available, skipping entity extraction")
        except Exception as e:
            logger.error(f"Error extracting protocol entities: {e}")

    # Apply suggestion templates (Phase 1 Week 4: Template System)
    # Templates guide LLM toward specific, protocol-aware suggestions
    # Week 5: use_templates flag enables A/B testing
    if text and extracted_entities and use_templates:
        try:
            from suggestion_templates import (
                find_applicable_templates,
                format_template_context
            )

            # Find templates that match patterns in text
            applicable_templates = find_applicable_templates(text, extracted_entities)

            if applicable_templates:
                template_context = format_template_context(
                    applicable_templates,
                    max_templates=2  # Limit to top 2 templates to manage token budget
                )
                if template_context.strip():
                    text = f"{template_context}\n\n{text}"
                    # Build amendment rates string separately to avoid nested f-string issues
                    amendment_rates = ', '.join(
                        f"{t['amendment_rate']*100:.0f}%"
                        for t in applicable_templates[:2]
                    )
                    logger.info(
                        f"Injected {len(applicable_templates[:2])} template(s) "
                        f"into prompt context (amendment rates: {amendment_rates})"
                    )
            else:
                logger.debug("No applicable templates found for this text")
        except ImportError:
            logger.warning("suggestion_templates module not available, skipping template injection")
        except Exception as e:
            logger.error(f"Error applying suggestion templates: {e}")

    # Inject section-specific instructions (Layer 2) before the text
    if section_instructions:
        text = f"{section_instructions}\n{text}"

    # Inject TA-specific endpoint guidance after section instructions
    if ta_endpoint_instructions:
        text = f"{ta_endpoint_instructions}\n{text}"

    # Inject rewrite instructions for endpoints/objectives sections
    if rewrite_instructions:
        text = f"{rewrite_instructions}\n{text}"

    # Build document context section (Document Intelligence)
    document_context_section = ""
    if document_context and document_context.get("section_summaries"):
        summaries = document_context["section_summaries"]
        current_section = document_context.get("current_section", "general")

        if summaries:
            # Option A (v1.0): Strong prompt guards for contextual intelligence with selections
            document_context_section = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DOCUMENT CONTEXT (REFERENCE ONLY - STRICT SELECTION BOUNDARY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The sections below show other parts of this protocol for cross-section awareness.
Use these excerpts to:
✓ Understand protocol-wide context
✓ Identify cross-section conflicts affecting the SELECTED TEXT
✓ Inform your rationale about why selected text has issues

**CRITICAL CONSTRAINT**: You may ONLY analyze the SELECTED TEXT below.
Every 'original_text' you return will be validated as a substring of the
selected text. If it's not found, your suggestion will be REJECTED.

❌ INVALID: Suggesting changes to text from these context sections
✅ VALID: Suggesting changes to selected text informed by context understanding
"""
            for section_type, summary in summaries.items():
                # Truncate summaries to ~300 chars each
                truncated = summary[:300] + "..." if len(summary) > 300 else summary
                document_context_section += f"\n[{section_type.upper()} section excerpt - REFERENCE ONLY]:\n{truncated}\n"

            # Add pre-analysis checklist to encourage LLM self-validation
            document_context_section += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BEFORE RETURNING YOUR RESPONSE - VERIFY EACH SUGGESTION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For each suggestion, confirm:
□ 'original_text' is copied VERBATIM from the SELECTED TEXT section below
□ 'original_text' can be found with exact substring matching
□ You have NOT suggested changes to text from CONTEXT sections above
□ If suggestion mentions cross-section conflict, the original_text is still from selection

If any check fails, REMOVE that suggestion from your response.
"""

            # Add clear separator and instructions for the selected text
            document_context_section += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SELECTED TEXT TO ANALYZE (YOUR EXCLUSIVE FOCUS)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are currently analyzing the {current_section.upper()} section.
The text below is what the user selected for analysis.
Generate suggestions ONLY for issues found in this selected text.
Your 'original_text' field MUST contain text that exists in this selected section.
Ensure your suggestions are consistent with the protocol context above.
---
"""

            # Prepend document context before the selected text
            text = f"{document_context_section}\n{text}"
            logger.info(f"Injected document context (REFERENCE ONLY) for sections: {list(summaries.keys())}")

    # Build timeline context section (Phase 4: Timeline-aware prompts)
    timeline_context_section = ""
    if timeline and section in ["schedule", "procedures", "safety", "general"]:
        try:
            from timeline_context_formatter import format_timeline_for_prompt

            # Calculate available token budget
            current_tokens = count_tokens_precise(text, "gpt-4o-mini")
            available_budget = FAST_ANALYSIS_TEMPLATE.max_input_tokens - current_tokens - 500  # Reserve 500

            if available_budget > 150:  # Minimum for conditional warnings only
                # Determine what to include based on budget (per user preference)
                if available_budget < 400:
                    # Tight budget: conditional warnings only (~200 tokens)
                    timeline_tokens = min(available_budget, 200)
                    include_gaps = False
                elif available_budget < 600:
                    # Medium budget: gaps + conditionals (~400 tokens)
                    timeline_tokens = min(available_budget, 400)
                    include_gaps = True
                else:
                    # Full budget: all context (~600 tokens)
                    timeline_tokens = min(available_budget, 600)
                    include_gaps = True

                timeline_context_section = format_timeline_for_prompt(
                    timeline,
                    max_tokens=timeline_tokens,
                    include_assessment_gaps=include_gaps,
                    include_conditional_warnings=True  # Always include if budget allows
                )

                if timeline_context_section:
                    # Prepend timeline context before selected text
                    text = f"{timeline_context_section}\n\nSELECTED TEXT TO ANALYZE:\n{text}"
                    logger.info(f"Injected timeline context (~{len(timeline_context_section)//4} tokens)")
            else:
                logger.warning(f"Insufficient token budget for timeline context (available: {available_budget})")

        except ImportError:
            logger.warning("timeline_context_formatter module not available")
        except Exception as e:
            logger.error(f"Error injecting timeline context: {e}")

    # Load feedback-based examples (Phase 2B - Adaptive Learning)
    feedback_examples = load_feedback_examples()
    feedback_section = ""
    if feedback_examples["accepted"] or feedback_examples["rejected"]:
        feedback_section = build_feedback_examples_section(feedback_examples, max_chars=400)
        logger.debug(f"Injecting {len(feedback_section)} chars of feedback examples into prompt")

    # Fill template (inject feedback examples before FEW-SHOT EXAMPLES section)
    user_template = FAST_ANALYSIS_TEMPLATE.user_template
    if feedback_section:
        # Insert feedback examples after RESPONSE FORMAT and before FEW-SHOT EXAMPLES
        user_template = user_template.replace(
            "FEW-SHOT EXAMPLES:",
            f"{feedback_section}\n\nFEW-SHOT EXAMPLES:"
        )

    user_content = user_template.format(
        ta_context=ta_context,
        text=text
    )

    # Week 5 A/B Testing: Add cache-busting to ensure variants use different cache keys
    # This prevents Azure OpenAI cache from returning identical responses for both variants
    import time
    cache_buster = f"\n\n[Analysis timestamp: {time.time():.6f}]"
    if not use_templates:
        user_content += cache_buster + " Mode: baseline (no template guidance)"
    else:
        user_content += cache_buster + " Mode: template-enhanced"

    # Count tokens
    system_tokens = count_tokens_precise(FAST_ANALYSIS_TEMPLATE.system, "gpt-4o-mini")
    user_tokens = count_tokens_precise(user_content, "gpt-4o-mini")
    total_input_tokens = system_tokens + user_tokens

    # Check budget
    if total_input_tokens > FAST_ANALYSIS_TEMPLATE.max_input_tokens:
        logger.warning(
            f"⚠️ Fast prompt exceeds budget: {total_input_tokens} > {FAST_ANALYSIS_TEMPLATE.max_input_tokens} tokens"
        )

        # Trim text to fit budget
        excess_tokens = total_input_tokens - FAST_ANALYSIS_TEMPLATE.max_input_tokens
        chars_to_trim = excess_tokens * 4  # ~4 chars per token

        if chars_to_trim > 0:
            trimmed_text = text[:-chars_to_trim]
            user_content = FAST_ANALYSIS_TEMPLATE.user_template.format(
                ta_context=ta_context,
                text=trimmed_text
            )
            user_tokens = count_tokens_precise(user_content, "gpt-4o-mini")
            total_input_tokens = system_tokens + user_tokens
            logger.info(f"✂️ Trimmed text to fit budget: {total_input_tokens} tokens")

    return {
        "system": FAST_ANALYSIS_TEMPLATE.system,
        "user": user_content,
        "tokens": {
            "system": system_tokens,
            "user": user_tokens,
            "total_input": total_input_tokens,
            "expected_output": FAST_ANALYSIS_TEMPLATE.expected_output_tokens,
            "budget": FAST_ANALYSIS_TEMPLATE.max_input_tokens
        },
        "entities": extracted_entities  # Return extracted entities for specificity scoring
    }


def build_deep_prompt(
    text: str,
    ta: Optional[str] = None,
    phase: Optional[str] = None,
    exemplars: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Build optimized prompt for deep analysis

    Args:
        text: Protocol text to analyze
        ta: Optional therapeutic area
        phase: Optional study phase
        exemplars: Optional list of similar protocol examples

    Returns:
        Dict with system and user messages, token counts
    """
    # Build contexts (only include if provided)
    ta_context = f" in {ta.replace('_', ' ')}" if ta else ""
    phase_text = phase or "clinical"

    # Build exemplars context (only if provided and within budget)
    exemplars_context = ""
    if exemplars:
        exemplars_text = "\n\n".join([f"Example {i+1}: {ex[:200]}..." for i, ex in enumerate(exemplars[:3])])
        exemplars_context = f"\nSIMILAR PROTOCOLS:\n{exemplars_text}"

    # Fill template
    user_content = DEEP_ANALYSIS_TEMPLATE.user_template.format(
        ta_context=ta_context,
        phase=phase_text,
        text=text,
        exemplars_context=exemplars_context
    )

    # Count tokens
    system_tokens = count_tokens_precise(DEEP_ANALYSIS_TEMPLATE.system, "gpt-4o")
    user_tokens = count_tokens_precise(user_content, "gpt-4o")
    total_input_tokens = system_tokens + user_tokens

    # Check budget
    if total_input_tokens > DEEP_ANALYSIS_TEMPLATE.max_input_tokens:
        logger.warning(
            f"⚠️ Deep prompt exceeds budget: {total_input_tokens} > {DEEP_ANALYSIS_TEMPLATE.max_input_tokens} tokens"
        )

        # Strategy: Remove exemplars first, then trim text
        if exemplars_context:
            logger.info("✂️ Removing exemplars to fit budget")
            user_content = DEEP_ANALYSIS_TEMPLATE.user_template.format(
                ta_context=ta_context,
                phase=phase_text,
                text=text,
                exemplars_context=""
            )
            user_tokens = count_tokens_precise(user_content, "gpt-4o")
            total_input_tokens = system_tokens + user_tokens

        # Still over budget? Trim text
        if total_input_tokens > DEEP_ANALYSIS_TEMPLATE.max_input_tokens:
            excess_tokens = total_input_tokens - DEEP_ANALYSIS_TEMPLATE.max_input_tokens
            chars_to_trim = excess_tokens * 4

            if chars_to_trim > 0:
                trimmed_text = text[:-chars_to_trim]
                user_content = DEEP_ANALYSIS_TEMPLATE.user_template.format(
                    ta_context=ta_context,
                    phase=phase_text,
                    text=trimmed_text,
                    exemplars_context=""
                )
                user_tokens = count_tokens_precise(user_content, "gpt-4o")
                total_input_tokens = system_tokens + user_tokens
                logger.info(f"✂️ Trimmed text to fit budget: {total_input_tokens} tokens")

    return {
        "system": DEEP_ANALYSIS_TEMPLATE.system,
        "user": user_content,
        "tokens": {
            "system": system_tokens,
            "user": user_tokens,
            "total_input": total_input_tokens,
            "expected_output": DEEP_ANALYSIS_TEMPLATE.expected_output_tokens,
            "budget": DEEP_ANALYSIS_TEMPLATE.max_input_tokens
        }
    }


def track_token_usage(
    path_type: str,
    input_tokens: int,
    output_tokens: int
):
    """
    Track token usage statistics

    Args:
        path_type: "fast_path" or "deep_path"
        input_tokens: Number of input tokens used
        output_tokens: Number of output tokens generated
    """
    if not ENABLE_TOKEN_TRACKING:
        return

    if path_type in _token_stats:
        _token_stats[path_type]["total_requests"] += 1
        _token_stats[path_type]["total_input_tokens"] += input_tokens
        _token_stats[path_type]["total_output_tokens"] += output_tokens


def get_token_stats() -> Dict[str, Any]:
    """
    Get token usage statistics

    Returns:
        Dict with token usage stats and cost estimates
    """
    # Azure OpenAI pricing (example, adjust for actual pricing)
    # gpt-4o-mini: $0.15/1M input, $0.60/1M output
    # gpt-4o: $2.50/1M input, $10.00/1M output

    fast_stats = _token_stats["fast_path"]
    deep_stats = _token_stats["deep_path"]

    # Calculate costs (in USD)
    fast_input_cost = (fast_stats["total_input_tokens"] / 1_000_000) * 0.15
    fast_output_cost = (fast_stats["total_output_tokens"] / 1_000_000) * 0.60
    fast_total_cost = fast_input_cost + fast_output_cost

    deep_input_cost = (deep_stats["total_input_tokens"] / 1_000_000) * 2.50
    deep_output_cost = (deep_stats["total_output_tokens"] / 1_000_000) * 10.00
    deep_total_cost = deep_input_cost + deep_output_cost

    total_cost = fast_total_cost + deep_total_cost

    return {
        "fast_path": {
            **fast_stats,
            "avg_input_tokens": (
                fast_stats["total_input_tokens"] / fast_stats["total_requests"]
                if fast_stats["total_requests"] > 0 else 0
            ),
            "avg_output_tokens": (
                fast_stats["total_output_tokens"] / fast_stats["total_requests"]
                if fast_stats["total_requests"] > 0 else 0
            ),
            "estimated_cost_usd": round(fast_total_cost, 4)
        },
        "deep_path": {
            **deep_stats,
            "avg_input_tokens": (
                deep_stats["total_input_tokens"] / deep_stats["total_requests"]
                if deep_stats["total_requests"] > 0 else 0
            ),
            "avg_output_tokens": (
                deep_stats["total_output_tokens"] / deep_stats["total_requests"]
                if deep_stats["total_requests"] > 0 else 0
            ),
            "estimated_cost_usd": round(deep_total_cost, 4)
        },
        "total": {
            "requests": fast_stats["total_requests"] + deep_stats["total_requests"],
            "input_tokens": fast_stats["total_input_tokens"] + deep_stats["total_input_tokens"],
            "output_tokens": fast_stats["total_output_tokens"] + deep_stats["total_output_tokens"],
            "estimated_cost_usd": round(total_cost, 4)
        },
        "optimization_impact": {
            "fast_token_budget": FAST_TOKEN_BUDGET,
            "deep_token_budget": DEEP_TOKEN_BUDGET,
            "estimated_savings": "20-30% vs. unoptimized prompts",
            "target_monthly_savings_usd": "10-20"
        }
    }


def reset_token_stats():
    """Reset token usage statistics (for testing)"""
    for path in _token_stats:
        _token_stats[path] = {
            "total_requests": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0
        }


# Log configuration on import
logger.info("📝 Prompt optimizer loaded (Step 4):")
logger.info(f"   - Fast token budget: {FAST_TOKEN_BUDGET}")
logger.info(f"   - Deep token budget: {DEEP_TOKEN_BUDGET}")
logger.info(f"   - Token tracking: {ENABLE_TOKEN_TRACKING}")
logger.info(f"   - Target savings: 20-30% token reduction")


__all__ = [
    "build_fast_prompt",
    "build_deep_prompt",
    "count_tokens",
    "count_tokens_precise",
    "track_token_usage",
    "get_token_stats",
    "reset_token_stats",
    "load_feedback_examples",
    "build_feedback_examples_section",
    "FAST_TOKEN_BUDGET",
    "DEEP_TOKEN_BUDGET"
]
