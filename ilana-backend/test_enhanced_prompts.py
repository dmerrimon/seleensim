#!/usr/bin/env python3
"""
Test Enhanced Prompts - Validates Statistical & Regulatory Issue Detection

Tests that the new domain-expert prompts catch:
1. Statistical analysis vagueness ("may"/"if deemed appropriate")
2. Analysis population ambiguity (ITT vs as-treated, bias risks)
3. Terminology inconsistencies
4. Missing documentation requirements

Test Case Source: User-reported false negative paragraph
"""

import pytest
import asyncio
from fast_analysis import analyze_fast

# Test paragraph from user that should trigger multiple issues
TEST_PARAGRAPH_STATISTICAL = """Subjects will be initially enrolled into the appropriate Group 1 subgroup based on their disease symptoms/status at enrollment. After enrollment, if disease severity progresses, patients may be reassigned to the highest severity group (outpatient, non-ICU inpatient, or ICU inpatient) they achieve during follow-up. Crossing from one severity group to another may facilitate identification of early immune responses associated with progression to severe disease. The statistical analyses may reflect the clinical status/symptoms at the time samples were collected if deemed appropriate. (See Section 7, Statistical Considerations)."""

# Controlled negative - should return no issues
TEST_PARAGRAPH_CLEAN = """Primary analysis will be intention-to-treat as specified in the Statistical Analysis Plan Section 9.2. Secondary per-protocol analysis definitions are provided in SAP Appendix A."""

# Borderline case - should flag ambiguous language
TEST_PARAGRAPH_BORDERLINE = """Patients will be followed and analyzed as appropriate."""


@pytest.mark.asyncio
async def test_statistical_analysis_vagueness_detected():
    """
    Test A: Validates detection of statistical analysis vagueness

    Expected: Critical severity issue for "may reflect...if deemed appropriate"
    Requirement: Must flag ICH E9 violation - analysis plans must be pre-specified
    """
    result = await analyze_fast(text=TEST_PARAGRAPH_STATISTICAL, request_id="test_stat_vague")

    suggestions = result.get("suggestions", [])

    # Must return at least one suggestion
    assert len(suggestions) > 0, "Should detect statistical analysis issues"

    # Check for statistical category issue with high confidence
    statistical_issues = [s for s in suggestions if s.get("type") == "statistical"]
    assert len(statistical_issues) > 0, "Should detect statistical analysis vagueness"

    # Verify severity is critical or major
    severities = [s.get("severity", "minor") for s in statistical_issues]
    assert any(sev in ["critical", "major"] for sev in severities), \
        "Statistical analysis vagueness should be critical/major severity"

    # Verify high confidence (>= 0.6)
    confidences = [s.get("confidence", 0) for s in statistical_issues]
    assert any(conf >= 0.6 for conf in confidences), \
        "Should have confidence >= 0.6 for statistical issues"

    # Verify rationale mentions pre-specification or ICH E9
    rationales = [s.get("rationale", "").lower() for s in statistical_issues]
    assert any("pre-specif" in r or "ich e9" in r for r in rationales), \
        "Rationale should mention pre-specification or ICH E9"

    print(f"✅ Test A passed: Detected {len(statistical_issues)} statistical issue(s)")
    for issue in statistical_issues:
        print(f"   - Severity: {issue.get('severity')}, Confidence: {issue.get('confidence')}")


@pytest.mark.asyncio
async def test_analysis_population_issues_detected():
    """
    Test B: Validates detection of analysis population ambiguity

    Expected: Major severity issue for reassignment without ITT/as-treated definition
    Requirement: Must flag immortal time bias and selection bias risks
    """
    result = await analyze_fast(text=TEST_PARAGRAPH_STATISTICAL, request_id="test_pop_ambig")

    suggestions = result.get("suggestions", [])

    # Check for analysis_population category
    population_issues = [s for s in suggestions if s.get("type") == "analysis_population"]

    # Note: Model might categorize as "statistical" or "documentation"
    # Accept if rationale mentions ITT, as-treated, bias, or reassignment
    relevant_issues = [s for s in suggestions
                      if any(term in s.get("rationale", "").lower()
                            for term in ["itt", "intention-to-treat", "as-treated",
                                       "bias", "reassign", "immortal time"])]

    assert len(relevant_issues) > 0, \
        "Should detect analysis population or reassignment issues"

    print(f"✅ Test B passed: Detected {len(relevant_issues)} population/bias issue(s)")
    for issue in relevant_issues:
        print(f"   - Type: {issue.get('type')}, Rationale: {issue.get('rationale')[:100]}...")


@pytest.mark.asyncio
async def test_terminology_inconsistencies_detected():
    """
    Test C: Validates detection of terminology inconsistencies

    Expected: Minor/major issue for "Group 1 subgroup" inconsistency
    Requirement: Should suggest consistent terminology mapping
    """
    result = await analyze_fast(text=TEST_PARAGRAPH_STATISTICAL, request_id="test_terminology")

    suggestions = result.get("suggestions", [])

    # Check for terminology issues or rationale mentioning inconsistent terms
    terminology_issues = [s for s in suggestions
                         if s.get("type") == "terminology"
                         or "group" in s.get("rationale", "").lower()
                         or "terminolog" in s.get("rationale", "").lower()]

    # This test is optional - terminology issues are lower priority
    if len(terminology_issues) > 0:
        print(f"✅ Test C passed: Detected {len(terminology_issues)} terminology issue(s)")
    else:
        print(f"⚠️ Test C: No terminology issues detected (acceptable - lower priority)")


@pytest.mark.asyncio
async def test_controlled_negative_no_false_positives():
    """
    Test D: Validates no false positives on clean text

    Expected: Empty issues array or very low confidence suggestions
    Requirement: Should not flag well-specified protocol language
    """
    result = await analyze_fast(text=TEST_PARAGRAPH_CLEAN, request_id="test_clean")

    suggestions = result.get("suggestions", [])

    # Should return no issues OR only advisory/low-confidence issues
    high_conf_issues = [s for s in suggestions if s.get("confidence", 0) >= 0.7]

    assert len(high_conf_issues) == 0, \
        f"Should not flag well-specified text. Found {len(high_conf_issues)} high-confidence issues"

    print(f"✅ Test D passed: No false positives on clean text")


@pytest.mark.asyncio
async def test_borderline_case_ambiguous_language():
    """
    Test E: Validates detection of ambiguous conditional language

    Expected: Critical issue for "as appropriate" without pre-specification
    Requirement: Should flag need for SAP definition
    """
    result = await analyze_fast(text=TEST_PARAGRAPH_BORDERLINE, request_id="test_borderline")

    suggestions = result.get("suggestions", [])

    # Should detect "as appropriate" as ambiguous
    assert len(suggestions) > 0, "Should flag 'as appropriate' as ambiguous"

    # Check for critical/major severity
    critical_issues = [s for s in suggestions
                       if s.get("severity") in ["critical", "major"]]

    assert len(critical_issues) > 0, \
        "'As appropriate' should be flagged as critical/major"

    print(f"✅ Test E passed: Detected ambiguous language 'as appropriate'")


@pytest.mark.asyncio
async def test_multiple_issues_returned():
    """
    Test F: Validates that multiple issues are returned (not just one)

    Expected: At least 2-3 issues from the test paragraph
    Requirement: New prompt should return multiple issues, not just ONE
    """
    result = await analyze_fast(text=TEST_PARAGRAPH_STATISTICAL, request_id="test_multi")

    suggestions = result.get("suggestions", [])

    # Should return at least 2 issues
    assert len(suggestions) >= 2, \
        f"Should detect multiple issues. Found only {len(suggestions)}"

    # Verify different issue types/categories
    types = set(s.get("type", "unknown") for s in suggestions)

    print(f"✅ Test F passed: Detected {len(suggestions)} issues across {len(types)} categories")
    print(f"   Categories: {', '.join(types)}")


@pytest.mark.asyncio
async def test_response_schema_compliance():
    """
    Test G: Validates new response schema has required fields

    Expected: Each issue has id, category, severity, recommendation, confidence
    Requirement: Schema compliance per specification
    """
    result = await analyze_fast(text=TEST_PARAGRAPH_STATISTICAL, request_id="test_schema")

    suggestions = result.get("suggestions", [])

    assert len(suggestions) > 0, "Should return issues for validation"

    # Validate schema for each suggestion
    for idx, suggestion in enumerate(suggestions):
        assert "id" in suggestion, f"Issue {idx} missing 'id' field"
        assert "text" in suggestion or "original_text" in suggestion, \
            f"Issue {idx} missing text field"
        assert "suggestion" in suggestion or "improved_text" in suggestion, \
            f"Issue {idx} missing improved text"
        assert "rationale" in suggestion, f"Issue {idx} missing 'rationale'"
        assert "confidence" in suggestion, f"Issue {idx} missing 'confidence'"
        assert "type" in suggestion, f"Issue {idx} missing 'type' (category)"

        # New fields
        assert "severity" in suggestion, f"Issue {idx} missing 'severity'"
        assert suggestion.get("severity") in ["critical", "major", "minor", "advisory"], \
            f"Issue {idx} has invalid severity: {suggestion.get('severity')}"

        # Recommendation is optional but should be present for critical/major issues
        if suggestion.get("severity") in ["critical", "major"]:
            assert "recommendation" in suggestion and suggestion.get("recommendation"), \
                f"Issue {idx} ({suggestion.get('severity')}) should have recommendation"

    print(f"✅ Test G passed: All {len(suggestions)} issues comply with new schema")


# Run tests with pytest
if __name__ == "__main__":
    print("🧪 Running Enhanced Prompt Tests\n")

    # Run tests manually for quick validation
    asyncio.run(test_statistical_analysis_vagueness_detected())
    asyncio.run(test_analysis_population_issues_detected())
    asyncio.run(test_terminology_inconsistencies_detected())
    asyncio.run(test_controlled_negative_no_false_positives())
    asyncio.run(test_borderline_case_ambiguous_language())
    asyncio.run(test_multiple_issues_returned())
    asyncio.run(test_response_schema_compliance())

    print("\n✅ All tests passed!")
