# Scenario Metadata (Future Enhancement)

## Purpose

Add interpretability and governance metadata to scenarios **without** affecting computation.

**Critical Rule**: Metadata is write-only for documentation, read-only for reporting. Never used for execution logic.

## Proposed Design

```python
@dataclass(frozen=True)
class ScenarioProfile:
    scenario_id: str
    description: str
    version: str

    # Existing fields...
    site_overrides: Dict[str, Dict[str, Any]]
    activity_overrides: Dict[str, Dict[str, Any]]
    # ...

    # NEW: Interpretability metadata
    metadata: Dict[str, str] = field(default_factory=dict)
    # Example:
    # {
    #     "confidence": "low | medium | high",
    #     "source": "expert | historical | sponsor_claim | regulatory",
    #     "validated_by": "clinical_ops_team",
    #     "date_reviewed": "2026-02-15",
    #     "assumption_basis": "Similar trials in EU showed 20-30% delays"
    # }
```

## Use Cases

### 1. Confidence Tracking

```python
scenario_low_confidence = ScenarioProfile(
    scenario_id="PESSIMISTIC_ENROLLMENT",
    description="30% lower enrollment if competitor trial launches",
    version="1.0.0",
    site_overrides={...},
    metadata={
        "confidence": "low",
        "source": "expert",
        "assumption_basis": "Speculative - no historical data for this indication"
    }
)

scenario_high_confidence = ScenarioProfile(
    scenario_id="REGULATORY_DELAY",
    description="EU approval adds 8 weeks",
    version="1.0.0",
    site_overrides={...},
    metadata={
        "confidence": "high",
        "source": "historical",
        "assumption_basis": "Last 5 EU trials averaged 8.2 week delay"
    }
)

# When reporting:
# "Scenario PESSIMISTIC_ENROLLMENT has low confidence (expert opinion only)"
# "Scenario REGULATORY_DELAY has high confidence (historical average)"
```

### 2. Source Attribution

```python
scenario = ScenarioProfile(
    scenario_id="SPONSOR_OPTIMISTIC",
    description="Sponsor expects faster enrollment",
    version="1.0.0",
    site_overrides={...},
    metadata={
        "source": "sponsor_claim",
        "provided_by": "sponsor_clinical_team",
        "date_provided": "2026-01-15",
        "validation_status": "pending_review"
    }
)

# Governance: "This scenario reflects sponsor assumptions, not validated by historical data"
```

### 3. Review Tracking

```python
scenario = ScenarioProfile(
    scenario_id="BUDGET_CONSTRAINED",
    description="Reduced monitor capacity",
    version="2.0.0",
    site_overrides={...},
    metadata={
        "confidence": "medium",
        "source": "historical",
        "reviewed_by": "clinical_ops_team, finance_team",
        "review_date": "2026-02-14",
        "approval_status": "approved",
        "last_updated_reason": "Increased from 20% to 30% reduction based on Q1 actuals"
    }
)

# Audit trail: Who reviewed? When? What changed?
```

## The Invariant

**Metadata may observe assumptions, never influence simulation.**

### ✅ Allowed Uses

```python
# After simulation: reporting and governance
results = engine.run(apply_scenario(base, scenario), num_runs=100)

# Report with metadata context
print(f"Scenario: {scenario.scenario_id}")
print(f"  P50: {results.completion_time_p50:.1f} days")
print(f"  Confidence: {scenario.metadata.get('confidence', 'unknown')}")
print(f"  Source: {scenario.metadata.get('source', 'unknown')}")

# Governance check
low_confidence_scenarios = [
    s for s in scenarios
    if s.metadata.get('confidence') == 'low'
]
print(f"Warning: {len(low_confidence_scenarios)} scenarios have low confidence")

# Audit trail
for scenario in scenarios:
    print(f"{scenario.scenario_id}: reviewed by {scenario.metadata.get('reviewed_by', 'none')}")
```

### ❌ Forbidden Uses

```python
# VIOLATION: Using metadata to make execution decisions

def apply_scenario(base: Trial, scenario: ScenarioProfile) -> Trial:
    # ❌ WRONG: Adjusting computation based on metadata
    if scenario.metadata.get('confidence') == 'low':
        # Reduce override magnitude because low confidence
        scale_factor *= 0.8  # NO!

    # ❌ WRONG: Skipping overrides based on source
    if scenario.metadata.get('source') == 'sponsor_claim':
        # Ignore sponsor scenarios
        return base  # NO!

    # ✅ CORRECT: Metadata never read during execution
    # Just apply overrides as specified
    return _apply_overrides(base, scenario)
```

```python
# VIOLATION: Engine reading metadata

class BadEngine:
    def run(self, trial, num_runs=100):
        # ❌ WRONG: Adjusting simulation based on scenario metadata
        if hasattr(trial, 'scenario_metadata'):
            if trial.scenario_metadata.get('confidence') == 'low':
                # Run fewer iterations for low confidence
                num_runs = 50  # NO!
```

## Why This Matters

### Good: Documentation and Governance

```python
# Generate governance report
def generate_scenario_audit_report(scenarios: List[ScenarioProfile]) -> str:
    report = "Scenario Audit Report\n"
    report += "=" * 80 + "\n\n"

    for scenario in scenarios:
        report += f"Scenario: {scenario.scenario_id}\n"
        report += f"  Description: {scenario.description}\n"
        report += f"  Confidence: {scenario.metadata.get('confidence', 'not specified')}\n"
        report += f"  Source: {scenario.metadata.get('source', 'not specified')}\n"
        report += f"  Reviewed: {scenario.metadata.get('reviewed_by', 'pending review')}\n"
        report += f"  Version: {scenario.version}\n\n"

    # Flag issues
    unreviewed = [s for s in scenarios if 'reviewed_by' not in s.metadata]
    if unreviewed:
        report += f"WARNING: {len(unreviewed)} scenarios pending review\n"

    return report

# This is good - documentation and oversight
```

### Bad: Execution Logic

```python
# ❌ WRONG: Weighting scenarios by confidence
def weighted_scenario_analysis(base: Trial, scenarios: List[ScenarioProfile]):
    results = {}

    for scenario in scenarios:
        modified = apply_scenario(base, scenario)
        result = engine.run(modified, num_runs=100)

        # ❌ VIOLATION: Using metadata for computation
        confidence = scenario.metadata.get('confidence')
        weight = {'low': 0.5, 'medium': 1.0, 'high': 1.5}.get(confidence, 1.0)

        # Weight results by confidence
        results[scenario.scenario_id] = result.completion_time_p50 * weight

    # This is WRONG - metadata influencing analysis
    # If you want weighted analysis, make it explicit in the scenario definition
    # Or do it in post-processing with explicit user-provided weights
```

## Implementation Notes

### Phase 1: Add Field (Non-Breaking)

```python
# Add metadata field with default empty dict
@dataclass(frozen=True)
class ScenarioProfile:
    # ... existing fields ...
    metadata: Dict[str, str] = field(default_factory=dict)

    # Existing code continues to work (default={})
```

### Phase 2: Conventions (Not Enforcement)

```python
# Define standard keys (conventions, not enforced)
METADATA_KEYS = {
    "confidence": ["low", "medium", "high"],
    "source": ["expert", "historical", "sponsor_claim", "regulatory"],
    "reviewed_by": "string",
    "review_date": "ISO 8601 date",
    "assumption_basis": "string"
}

# But don't validate - let users add whatever they want
# Metadata is free-form documentation
```

### Phase 3: Reporting Utilities

```python
def summarize_scenario_metadata(scenarios: List[ScenarioProfile]) -> pd.DataFrame:
    """Extract metadata for analysis (after execution, for reporting)."""
    data = []
    for scenario in scenarios:
        data.append({
            "scenario_id": scenario.scenario_id,
            "version": scenario.version,
            "confidence": scenario.metadata.get("confidence", "not specified"),
            "source": scenario.metadata.get("source", "not specified"),
            "reviewed": "yes" if "reviewed_by" in scenario.metadata else "no"
        })

    return pd.DataFrame(data)

# Use this AFTER simulation for governance reporting
```

### Phase 4: Documentation

- Add example scenarios with metadata to examples/
- Document metadata conventions (not requirements)
- Add governance workflow examples
- Emphasize: "Metadata observes, never influences"

## Test Strategy

### Structural Tests (Like Metrics Invariant)

```python
def test_metadata_never_read_during_apply_scenario():
    """Verify apply_scenario() doesn't read metadata."""
    import inspect
    from seleensim.scenarios import apply_scenario

    source = inspect.getsource(apply_scenario)

    # Should NOT contain metadata reads
    forbidden_patterns = [
        "scenario.metadata",
        "scenario.metadata.get"
    ]

    for pattern in forbidden_patterns:
        assert pattern not in source, \
            f"VIOLATION: apply_scenario() reads metadata ({pattern})"
```

```python
def test_metadata_is_documentation_only():
    """Verify metadata doesn't affect scenario application."""
    base = Trial(...)

    scenario_no_metadata = ScenarioProfile(
        scenario_id="TEST",
        site_overrides={...}
    )

    scenario_with_metadata = ScenarioProfile(
        scenario_id="TEST",
        site_overrides={...},
        metadata={"confidence": "low", "source": "expert"}
    )

    result1 = apply_scenario(base, scenario_no_metadata)
    result2 = apply_scenario(base, scenario_with_metadata)

    # Results should be identical (metadata not used)
    assert result1.sites[0].activation_time.mode == result2.sites[0].activation_time.mode
```

## Summary

**What Metadata Is**:
- Documentation of scenario assumptions
- Confidence and source attribution
- Audit trail for governance
- Context for reporting

**What Metadata Is NOT**:
- Input to simulation logic
- Weight or filter for analysis
- Execution parameter
- Control flow variable

**The Rule**:
```python
# ✅ Read metadata AFTER simulation for reporting
print(f"Confidence: {scenario.metadata.get('confidence')}")

# ❌ Read metadata DURING simulation for decisions
if scenario.metadata.get('confidence') == 'low':
    adjust_behavior()  # VIOLATION
```

**When To Implement**:
- Not urgent (marked as future enhancement)
- After core scenario system proven stable
- When governance workflows become priority
- When users need audit trails

**Key Guarantee**:
Metadata follows same invariant as metrics - **observe, never influence**.
