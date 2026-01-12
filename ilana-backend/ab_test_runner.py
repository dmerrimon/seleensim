#!/usr/bin/env python3
"""
A/B Testing Runner for Template System Evaluation

Runs parallel analyses with and without templates to measure effectiveness.
Compares specificity scores, template usage, and suggestion quality.

Author: Ilana AI Team
Date: 2026-01-11
Week: 5 (Template Refinement & Testing)
"""

from typing import Dict, Any, Optional, List
import logging
from fast_analysis import analyze_fast

logger = logging.getLogger(__name__)


async def run_ab_test(
    text: str,
    section: Optional[str] = None,
    ta: Optional[str] = None,
    document_namespace: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run parallel analysis with and without templates

    Args:
        text: Protocol text to analyze
        section: Protocol section name
        ta: Therapeutic area
        document_namespace: Optional Pinecone namespace for document context

    Returns:
        {
            "variant_a": {  # With templates
                "suggestions": [...],
                "metadata": {
                    "specificity": {...},
                    "templates_matched": [...],
                    "templates_used": [...]
                }
            },
            "variant_b": {  # Without templates
                "suggestions": [...],
                "metadata": {
                    "specificity": {...}
                }
            },
            "comparison": {
                "specificity_delta": float,
                "improvement_pct": float,
                "highly_specific_delta": int,
                "templates_matched": int,
                "templates_list": [...]
            }
        }
    """
    logger.info("Running A/B test: with templates vs without templates")

    # Variant A: WITH templates (current behavior)
    try:
        result_a = await analyze_fast(
            text=text,
            section=section,
            ta=ta,
            document_namespace=document_namespace,
            use_templates=True  # NEW PARAMETER
        )
        variant_a = {
            "suggestions": result_a.get("suggestions", []),
            "metadata": result_a.get("metadata", {})
        }
        logger.info(f"Variant A (with templates): {len(variant_a['suggestions'])} suggestions")
    except Exception as e:
        logger.error(f"Error running variant A (with templates): {e}")
        variant_a = {"suggestions": [], "metadata": {}, "error": str(e)}

    # Variant B: WITHOUT templates
    try:
        result_b = await analyze_fast(
            text=text,
            section=section,
            ta=ta,
            document_namespace=document_namespace,
            use_templates=False  # DISABLE TEMPLATES
        )
        variant_b = {
            "suggestions": result_b.get("suggestions", []),
            "metadata": result_b.get("metadata", {})
        }
        logger.info(f"Variant B (without templates): {len(variant_b['suggestions'])} suggestions")
    except Exception as e:
        logger.error(f"Error running variant B (without templates): {e}")
        variant_b = {"suggestions": [], "metadata": {}, "error": str(e)}

    # Calculate comparison metrics
    comparison = _calculate_comparison(variant_a, variant_b)

    return {
        "variant_a": variant_a,
        "variant_b": variant_b,
        "comparison": comparison
    }


def _calculate_comparison(variant_a: Dict, variant_b: Dict) -> Dict[str, Any]:
    """
    Calculate comparison metrics between variants

    Args:
        variant_a: Results with templates
        variant_b: Results without templates

    Returns:
        Comparison metrics dict
    """
    comparison = {
        "specificity_delta": 0.0,
        "improvement_pct": 0.0,
        "highly_specific_delta": 0,
        "partially_specific_delta": 0,
        "generic_delta": 0,
        "templates_matched": 0,
        "templates_list": []
    }

    # Extract specificity metrics (handle None values)
    spec_a = variant_a.get("metadata", {}).get("specificity") or {}
    spec_b = variant_b.get("metadata", {}).get("specificity") or {}

    avg_score_a = spec_a.get("avg_score", 0.0) if spec_a else 0.0
    avg_score_b = spec_b.get("avg_score", 0.0) if spec_b else 0.0

    # Calculate deltas
    comparison["specificity_delta"] = avg_score_a - avg_score_b

    if avg_score_b > 0:
        comparison["improvement_pct"] = (
            (avg_score_a - avg_score_b) / avg_score_b * 100
        )

    comparison["highly_specific_delta"] = (
        spec_a.get("highly_specific_count", 0) -
        spec_b.get("highly_specific_count", 0)
    )

    comparison["partially_specific_delta"] = (
        spec_a.get("partially_specific_count", 0) -
        spec_b.get("partially_specific_count", 0)
    )

    comparison["generic_delta"] = (
        spec_a.get("generic_count", 0) -
        spec_b.get("generic_count", 0)
    )

    # Template usage (only in variant A)
    templates_matched = variant_a.get("metadata", {}).get("templates_matched", [])
    comparison["templates_matched"] = len(templates_matched)
    comparison["templates_list"] = templates_matched

    return comparison


async def run_ab_test_batch(
    test_cases: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Run A/B tests on multiple protocol selections

    Args:
        test_cases: List of test case dicts with keys:
            - text: str
            - section: Optional[str]
            - ta: Optional[str]
            - document_namespace: Optional[str]

    Returns:
        {
            "test_cases": [
                {
                    "case_id": int,
                    "variant_a": {...},
                    "variant_b": {...},
                    "comparison": {...}
                },
                ...
            ],
            "aggregate_metrics": {
                "avg_specificity_delta": float,
                "avg_improvement_pct": float,
                "total_templates_matched": int,
                "template_match_rate": float,
                "cases_with_improvement": int,
                "cases_with_degradation": int
            }
        }
    """
    logger.info(f"Running A/B test batch on {len(test_cases)} cases")

    results = []
    for i, case in enumerate(test_cases):
        logger.info(f"Running A/B test {i+1}/{len(test_cases)}")

        test_result = await run_ab_test(
            text=case.get("text", ""),
            section=case.get("section"),
            ta=case.get("ta"),
            document_namespace=case.get("document_namespace")
        )

        results.append({
            "case_id": i,
            **test_result
        })

    # Calculate aggregate metrics
    aggregate_metrics = _calculate_aggregate_metrics(results)

    return {
        "test_cases": results,
        "aggregate_metrics": aggregate_metrics
    }


def _calculate_aggregate_metrics(results: List[Dict]) -> Dict[str, Any]:
    """
    Calculate aggregate metrics across all test cases

    Args:
        results: List of A/B test results

    Returns:
        Aggregate metrics dict
    """
    if not results:
        return {}

    specificity_deltas = []
    improvement_pcts = []
    templates_matched_counts = []
    cases_with_improvement = 0
    cases_with_degradation = 0

    for result in results:
        comparison = result.get("comparison", {})

        delta = comparison.get("specificity_delta", 0.0)
        specificity_deltas.append(delta)

        if delta > 0:
            cases_with_improvement += 1
        elif delta < 0:
            cases_with_degradation += 1

        improvement_pcts.append(comparison.get("improvement_pct", 0.0))
        templates_matched_counts.append(comparison.get("templates_matched", 0))

    avg_specificity_delta = sum(specificity_deltas) / len(specificity_deltas)
    avg_improvement_pct = sum(improvement_pcts) / len(improvement_pcts)
    total_templates_matched = sum(templates_matched_counts)

    cases_with_at_least_one_template = sum(1 for c in templates_matched_counts if c > 0)
    template_match_rate = cases_with_at_least_one_template / len(results) * 100

    return {
        "avg_specificity_delta": round(avg_specificity_delta, 3),
        "avg_improvement_pct": round(avg_improvement_pct, 2),
        "total_templates_matched": total_templates_matched,
        "template_match_rate": round(template_match_rate, 2),
        "cases_with_improvement": cases_with_improvement,
        "cases_with_degradation": cases_with_degradation,
        "total_cases": len(results)
    }


# Module self-test
if __name__ == "__main__":
    import asyncio

    print("=" * 80)
    print("A/B TEST RUNNER - MODULE SELF-TEST")
    print("=" * 80)

    # Test case: discontinuation text with template patterns
    test_text = """
    Those participants who received at least one dose but chose not to receive
    subsequent doses will be asked to remain for follow-up safety and immunogenicity
    assessments. Visits will not be conducted unless safety concern. Safety labs
    as clinically indicated per protocol.
    """

    async def test_ab_runner():
        print("\n📋 Test 1: Single A/B Test")
        result = await run_ab_test(text=test_text, section="discontinuation")

        print(f"Variant A (with templates): {len(result['variant_a']['suggestions'])} suggestions")
        print(f"Variant B (without templates): {len(result['variant_b']['suggestions'])} suggestions")
        print(f"\nComparison:")
        print(f"  Specificity delta: {result['comparison']['specificity_delta']:.3f}")
        print(f"  Improvement: {result['comparison']['improvement_pct']:.1f}%")
        print(f"  Templates matched: {result['comparison']['templates_matched']}")

        if result['comparison']['templates_list']:
            print(f"  Template IDs: {result['comparison']['templates_list']}")

        print("\n✅ Self-test complete")

    asyncio.run(test_ab_runner())
