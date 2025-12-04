"""
Amendment Risk Predictor (Layer 3: Risk Prediction)

Real-time prediction of amendment risk based on historical patterns.
Analyzes incoming text and flags language that historically leads to amendments.

Usage:
    from amendment_risk import predict_amendment_risk

    risks = predict_amendment_risk(
        text="Patients with adequate liver function are eligible",
        section="eligibility"
    )
"""

import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Default path to risk patterns
PATTERNS_FILE = Path(__file__).parent / "amendment_risk_patterns.json"

# Global patterns cache
_patterns_cache: Optional[Dict] = None


@dataclass
class RiskPrediction:
    """A predicted amendment risk"""
    risk_level: str           # high, medium, low
    pattern_readable: str     # Human-readable pattern description
    matched_text: str         # Actual text that matched
    category: str             # eligibility, dosing, endpoints, etc.
    amendment_probability: float  # Historical amendment frequency (0-1)
    typical_change: str       # What typically gets changed
    recommendation: str       # Suggested fix
    example_original: str     # Example from historical data
    example_amended: str      # How it was amended
    confidence: float         # Confidence in the prediction


def load_patterns() -> Dict:
    """Load risk patterns from JSON file"""
    global _patterns_cache

    if _patterns_cache is not None:
        return _patterns_cache

    if not PATTERNS_FILE.exists():
        logger.warning(f"Risk patterns file not found: {PATTERNS_FILE}")
        return {"high_risk_patterns": [], "medium_risk_patterns": [], "low_risk_patterns": []}

    try:
        with open(PATTERNS_FILE) as f:
            _patterns_cache = json.load(f)
            logger.info(f"Loaded {len(_patterns_cache.get('high_risk_patterns', []))} high-risk patterns")
            return _patterns_cache
    except Exception as e:
        logger.error(f"Failed to load risk patterns: {e}")
        return {"high_risk_patterns": [], "medium_risk_patterns": [], "low_risk_patterns": []}


def predict_amendment_risk(
    text: str,
    section: Optional[str] = None,
    min_risk_level: str = "medium",
    max_results: int = 5
) -> List[RiskPrediction]:
    """
    Predict amendment risk for given text based on historical patterns.

    Args:
        text: Protocol text to analyze
        section: Optional protocol section (eligibility, endpoints, etc.)
                 If provided, prioritizes patterns matching this section
        min_risk_level: Minimum risk level to return ("high", "medium", "low")
        max_results: Maximum number of predictions to return

    Returns:
        List of RiskPrediction objects sorted by risk level and relevance
    """
    patterns = load_patterns()

    if not patterns:
        return []

    predictions = []

    # Determine which pattern lists to check
    pattern_lists = []
    if min_risk_level in ["high", "medium", "low"]:
        pattern_lists.append(("high", patterns.get("high_risk_patterns", [])))
    if min_risk_level in ["medium", "low"]:
        pattern_lists.append(("medium", patterns.get("medium_risk_patterns", [])))
    if min_risk_level == "low":
        pattern_lists.append(("low", patterns.get("low_risk_patterns", [])))

    # Check each pattern
    for risk_level, pattern_list in pattern_lists:
        for pattern_info in pattern_list:
            try:
                pattern = pattern_info["pattern"]
                match = re.search(pattern, text, re.IGNORECASE)

                if match:
                    matched_text = match.group(0)

                    # Calculate confidence based on section match and pattern specificity
                    confidence = pattern_info["amendment_frequency"]
                    if section and pattern_info["category"] == section:
                        confidence = min(1.0, confidence * 1.2)  # Boost for section match

                    # Generate recommendation based on typical change
                    recommendation = _generate_recommendation(
                        pattern_info["pattern_readable"],
                        pattern_info["typical_change"],
                        pattern_info.get("examples", [])
                    )

                    # Get example if available
                    example_original = ""
                    example_amended = ""
                    if pattern_info.get("examples"):
                        example = pattern_info["examples"][0]
                        example_original = example.get("context", "")[:200]

                    prediction = RiskPrediction(
                        risk_level=risk_level,
                        pattern_readable=pattern_info["pattern_readable"],
                        matched_text=matched_text,
                        category=pattern_info["category"],
                        amendment_probability=pattern_info["amendment_frequency"],
                        typical_change=pattern_info["typical_change"],
                        recommendation=recommendation,
                        example_original=example_original,
                        example_amended=pattern_info["typical_change"],
                        confidence=confidence
                    )
                    predictions.append(prediction)

            except re.error as e:
                logger.warning(f"Invalid regex pattern: {pattern_info.get('pattern')}: {e}")
            except Exception as e:
                logger.error(f"Error checking pattern: {e}")

    # Sort by risk level (high first) and confidence
    risk_order = {"high": 0, "medium": 1, "low": 2}
    predictions.sort(key=lambda p: (risk_order.get(p.risk_level, 3), -p.confidence))

    # Deduplicate by pattern (keep highest risk)
    seen_patterns = set()
    unique_predictions = []
    for pred in predictions:
        if pred.pattern_readable not in seen_patterns:
            seen_patterns.add(pred.pattern_readable)
            unique_predictions.append(pred)

    return unique_predictions[:max_results]


def _generate_recommendation(pattern_readable: str, typical_change: str, examples: List[Dict]) -> str:
    """Generate a specific recommendation based on the pattern and typical change"""

    recommendations = {
        "adequate [organ] function": (
            "Replace with specific numeric thresholds. Example: "
            "'eGFR ≥60 mL/min/1.73m²' instead of 'adequate renal function', "
            "'AST/ALT ≤2.5× ULN' instead of 'adequate liver function'"
        ),
        "acceptable [organ] function": (
            "Define measurable thresholds for organ function. Example: "
            "'Cardiac ejection fraction ≥50%' instead of 'acceptable cardiac function'"
        ),
        "normal [organ] function/values": (
            "Replace with specific reference ranges. Example: "
            "'Creatinine ≤1.5× ULN' instead of 'normal renal function'"
        ),
        "endpoint will be measured": (
            "Specify measurement method, instrument, and timepoint. Example: "
            "'Primary endpoint will be assessed using RECIST v1.1 at Week 12 (±7 days)'"
        ),
        "response will be assessed": (
            "Specify assessment criteria and timing. Example: "
            "'Tumor response per RECIST v1.1 at Week 8, 16, and every 8 weeks thereafter'"
        ),
        "dose may be adjusted": (
            "Pre-specify dose modification rules in protocol. Example: "
            "'Dose will be reduced by 25% for Grade 2 toxicity, held for Grade 3, "
            "discontinued for Grade 4 per protocol Section 6.5'"
        ),
        "as needed/required dosing": (
            "Replace with specific criteria. Example: "
            "'Supportive medications per institutional guidelines (see Section 6.4)' "
            "instead of 'as needed'"
        ),
        "if [deemed] appropriate": (
            "Remove conditional language and pre-specify approach. Example: "
            "'Sensitivity analyses will be performed as detailed in SAP Section 9.3' "
            "instead of 'if deemed appropriate'"
        ),
        "SAE reporting language": (
            "Add explicit 24-hour timeline and procedures. Example: "
            "'SAEs must be reported to the Sponsor within 24 hours of awareness "
            "using the SAE reporting form (Appendix B)'"
        ),
        "assessment timing": (
            "Add explicit visit windows. Example: "
            "'Assessments at Week 4 (±3 days), Week 8 (±5 days), Week 12 (±7 days)'"
        ),
        "life expectancy requirement": (
            "Clarify assessment method or consider removing. Example: "
            "'Estimated life expectancy ≥12 weeks per investigator assessment' "
            "or replace with performance status criteria"
        ),
        "starting dose specification": (
            "Consider adding weight-based dosing or dose range. Example: "
            "'Starting dose: 100 mg daily (may be adjusted to 75-150 mg based on tolerability)'"
        ),
        "monitoring language": (
            "Specify frequency and parameters. Example: "
            "'Safety monitoring includes CBC and CMP weekly for first 4 weeks, "
            "then every 2 weeks (see Schedule of Assessments, Table 1)'"
        ),
        "discontinuation criteria": (
            "Add specific toxicity grades and recovery requirements. Example: "
            "'Discontinue for Grade 4 hematologic toxicity or Grade 3 non-hematologic "
            "toxicity not resolving to Grade 1 within 14 days'"
        ),
        "sample size specification": (
            "Include power calculation assumptions. Example: "
            "'Sample size of 120 (60 per arm) provides 80% power to detect HR 0.65 "
            "with two-sided α=0.05, assuming 24-month accrual and 12-month follow-up'"
        ),
        "analysis method language": (
            "Pre-specify all methods in SAP reference. Example: "
            "'Analysis methods are pre-specified in SAP Section 9 and will not be "
            "modified after database lock'"
        ),
        "visit window specification": (
            "Add explicit tolerance ranges. Example: "
            "'Visit windows: Screening (Day -28 to -1), Baseline (Day 0), "
            "Week 4 (±3 days), Week 8 (±5 days)'"
        ),
    }

    # Try to find a matching recommendation
    for key, rec in recommendations.items():
        if key.lower() in pattern_readable.lower():
            return rec

    # Default recommendation based on typical change
    return f"Consider revising: {typical_change}"


def format_risk_for_suggestion(prediction: RiskPrediction) -> Dict[str, Any]:
    """
    Format a risk prediction as a suggestion for the frontend.

    Returns:
        Dict compatible with fast_analysis suggestion format
    """
    severity_map = {
        "high": "major",
        "medium": "minor",
        "low": "advisory"
    }

    return {
        "id": f"amend_risk_{hash(prediction.pattern_readable) % 10000}",
        "type": "amendment_risk",
        "category": prediction.category,
        "severity": severity_map.get(prediction.risk_level, "advisory"),
        "original_text": prediction.matched_text,
        "improved_text": prediction.recommendation[:300],
        "rationale": (
            f"Historical data shows {prediction.amendment_probability*100:.0f}% of protocols "
            f"with '{prediction.pattern_readable}' language required amendments. "
            f"Typical change: {prediction.typical_change}"
        ),
        "recommendation": prediction.recommendation,
        "confidence": prediction.confidence,
        "source": "amendment_risk_layer3",
        "amendment_risk": {
            "risk_level": prediction.risk_level,
            "pattern": prediction.pattern_readable,
            "probability": prediction.amendment_probability,
            "category": prediction.category
        }
    }


def get_risk_statistics() -> Dict[str, Any]:
    """Get statistics about loaded risk patterns"""
    patterns = load_patterns()

    return {
        "patterns_loaded": True if patterns else False,
        "high_risk_count": len(patterns.get("high_risk_patterns", [])),
        "medium_risk_count": len(patterns.get("medium_risk_patterns", [])),
        "low_risk_count": len(patterns.get("low_risk_patterns", [])),
        "categories": patterns.get("categories", []),
        "metadata": patterns.get("metadata", {})
    }


# CLI for testing
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    # Test with sample text
    test_cases = [
        ("Patients with adequate liver function are eligible for enrollment", "eligibility"),
        ("The primary endpoint will be assessed at Week 12", "endpoints"),
        ("Dose may be adjusted based on tolerability", "dosing"),
        ("SAEs must be reported to the sponsor", "safety"),
        ("Analysis will be performed if deemed appropriate", "statistics"),
        ("Subjects with life expectancy of at least 3 months", "eligibility"),
    ]

    print("=== Amendment Risk Prediction Tests ===\n")

    stats = get_risk_statistics()
    print(f"Patterns loaded: {stats['high_risk_count']} high, "
          f"{stats['medium_risk_count']} medium, {stats['low_risk_count']} low\n")

    for text, section in test_cases:
        print(f"Text: \"{text}\"")
        print(f"Section: {section}")

        predictions = predict_amendment_risk(text, section=section)

        if predictions:
            for pred in predictions:
                print(f"  [{pred.risk_level.upper()}] {pred.pattern_readable}")
                print(f"    Matched: '{pred.matched_text}'")
                print(f"    Amendment probability: {pred.amendment_probability*100:.1f}%")
                print(f"    Recommendation: {pred.recommendation[:100]}...")
        else:
            print("  No risk patterns detected")

        print()
