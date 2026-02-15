# Architectural Guardrails

**Purpose**: Prevent architectural regressions that break calibration readiness.

**Enforcement**: CI blocks PRs if guardrail tests fail.

---

## What Are Guardrails?

Guardrails are **automated architectural tests** that enforce [The Ilana Law](ARCHITECTURAL_PRINCIPLES.md):

> **"Could this number be different for a different organization?"**
>
> **YES** → It's an **assumption** → Must be **parameterized**
> **NO** → It's **structural** → OK to **hardcode**

Guardrails detect when:
- Magic numbers appear in constraint logic
- Hardcoded formulas replace injectable behaviors
- Assumptions leak into core engine code
- Entities gain business logic or sampling

---

## Why Guardrails Matter

### Without Guardrails
```python
# Looks innocent, but breaks calibration readiness
class BudgetThrottlingConstraint:
    def evaluate(self, state, event):
        # VIOLATION: 0.5 is assumption (could be 0.2 or 0.8 for other orgs)
        duration_multiplier = 1.0 / max(0.5, budget_ratio)
```

**Problem**: SCRI can't calibrate without editing Python code.

### With Guardrails
```python
# Guardrail test detects magic number
def test_budget_constraint_has_no_hardcoded_response_logic():
    source = inspect.getsource(BudgetThrottlingConstraint.evaluate)
    assert 'max(0.5' not in source  # ❌ FAIL - magic number detected
```

**Result**: PR blocked → Developer extracts assumption → Calibration preserved.

---

## Guardrail Test Suites

### 1. Calibration Readiness Tests
**File**: `tests/test_calibration_readiness.py`

**What they check**:
- ✅ No hardcoded response formulas in constraints
- ✅ Constraints accept behavior objects (not magic numbers)
- ✅ Structural constraints remain assumption-free
- ✅ Users can change assumptions via parameters

**Example violations caught**:
```python
# ❌ VIOLATION: Hardcoded linear response
duration_multiplier = 1.0 / budget_ratio

# ❌ VIOLATION: Hardcoded minimum
speed = max(0.5, budget_ratio)

# ❌ VIOLATION: Hardcoded 2x cap
multiplier = min(2.0, 1.0 / ratio)
```

**Correct pattern**:
```python
# ✅ CORRECT: Injectable response curve
duration_multiplier = self.response_curve.sample_multiplier(budget_ratio, seed)
```

### 2. Anti-Behavior Tests
**File**: `tests/test_anti_behavior.py`

**What they check**:
- ✅ Entities don't sample distributions
- ✅ Entities are immutable after construction
- ✅ Entities have no computed properties
- ✅ Entities have no execution methods
- ✅ Entities have no runtime state

**Example violations caught**:
```python
# ❌ VIOLATION: Entity sampling
class Site:
    def get_activation_time(self, seed):
        return self.activation_time.sample(seed)  # NO!

# ❌ VIOLATION: Computed property
class Trial:
    @property
    def total_cost(self):
        return sum(site.cost for site in self.sites)  # NO!
```

**Correct pattern**:
```python
# ✅ CORRECT: Engine samples, not entity
activation_time = site.activation_time.sample(seed)

# ✅ CORRECT: Engine computes, not entity
total_cost = sum(site.cost for site in trial.sites)
```

---

## CI Enforcement

### GitHub Actions Workflow

**File**: `.github/workflows/ci.yml`

**Jobs**:
1. **Test Suite** - Runs all 210 tests across Python 3.9-3.13
2. **Guardrails** - Runs calibration readiness + anti-behavior tests
3. **All Checks** - Requires BOTH jobs to pass

### Failure Scenarios

#### Scenario 1: Guardrail Test Fails
```
❌ Guardrail tests failed - ARCHITECTURE REGRESSION DETECTED

Guardrail failures indicate:
  - Hidden assumptions introduced in constraint logic
  - Magic numbers hardcoded where parameters required
  - Violation of The Ilana Law

This blocks calibration readiness. Review architectural principles.
```

**Action required**:
1. Review the failing test
2. Identify the magic number or hardcoded assumption
3. Extract assumption into parameter or response curve
4. Update constraint to accept injectable behavior
5. Update tests with new API

#### Scenario 2: Test Suite Fails but Guardrails Pass
```
❌ Test suite failed
✅ Guardrails: success
```

**Interpretation**: Bug or regression, but architecture remains sound.

#### Scenario 3: Both Fail
```
❌ Test suite failed
❌ Guardrail tests failed
```

**Interpretation**: Architectural violation + functionality broken. Fix architecture first.

---

## When Guardrails Trigger

### ✅ Guardrails SHOULD Trigger (Good Catches)

**Example 1**: Magic number in constraint
```python
# PR introduces:
delay = event.duration * 1.5  # ❌ Why 1.5?

# Guardrail catches:
test_no_numeric_literals_in_constraint_logic → FAIL
```

**Example 2**: Hardcoded response curve
```python
# PR introduces:
if budget_ratio < 0.3:  # ❌ Why 0.3?
    multiplier = 5.0

# Guardrail catches:
test_budget_constraint_has_no_hardcoded_response_logic → FAIL
```

**Example 3**: Entity sampling
```python
# PR introduces:
class Site:
    def get_next_enrollment_time(self):
        return self.enrollment_rate.sample(random.randint(0, 1000))  # ❌

# Guardrail catches:
test_site_does_not_sample_distributions → FAIL
```

### ❌ Guardrails Should NOT Trigger (False Positives)

If guardrails fail incorrectly, update the test, not the constraint logic.

**Example**: Structural constant flagged incorrectly
```python
# This is OK (structural):
num_percentiles = 3  # P10, P50, P90 - fixed by simulation theory

# If guardrail incorrectly flags it, update guardrail to ignore this pattern
```

---

## Guardrail Philosophy

### Core Principles

1. **Treat failures as architecture regressions**, not test failures
2. **Block PRs until fixed** - no exceptions
3. **Educate on The Ilana Law** - failure messages explain why
4. **Evolve tests as needed** - add new checks for new constraint types

### What Guardrails Protect

| Protected Property | Without Guardrails | With Guardrails |
|-------------------|-------------------|----------------|
| Calibration readiness | Assumptions hardcoded → SCRI can't update | Parameters exposed → SCRI updates easily |
| Entity purity | Entities sample/compute → non-deterministic | Entities inert → engine controls sampling |
| Assumption visibility | Hidden in code → undiscoverable | Explicit in parameters → documented |
| Code evolution | Magic numbers accumulate → technical debt | Violations caught early → stays clean |

### Maintenance Burden

**Low**:
- Guardrails are passive (run automatically in CI)
- Failures are rare (only when assumptions introduced)
- Fix guidance is clear (extract to parameter)
- Tests evolve slowly (only when adding new constraint types)

**High value**:
- Prevents architectural decay
- Enforces calibration readiness
- Documents assumptions via parameters
- Reduces long-term technical debt

---

## Adding New Guardrails

When implementing new constraint types (STEP 3+), add corresponding guardrails:

### Template: New Constraint Guardrail

```python
# In tests/test_calibration_readiness.py

def test_new_constraint_has_no_hardcoded_assumptions():
    """
    NewConstraint should accept behavior objects, not magic numbers.

    Example violation:
        capacity_multiplier = 1.2  # ❌ Why 1.2?

    Correct pattern:
        capacity_multiplier = self.response_curve.sample(...)  # ✅
    """
    # Check __init__ signature
    sig = inspect.signature(NewConstraint.__init__)
    params = sig.parameters

    assert 'behavior_object' in params, \
        "NewConstraint must accept behavior object parameter"

    # Check evaluate() method
    source = inspect.getsource(NewConstraint.evaluate)

    # Forbidden patterns
    forbidden = [
        (r'\b1\.\d+\b', 'hardcoded multiplier'),
        (r'max\(\s*0\.\d+', 'hardcoded minimum'),
        (r'if\s+\w+\s*[<>]=?\s*0\.\d+', 'hardcoded threshold')
    ]

    for pattern, explanation in forbidden:
        assert not re.search(pattern, source), \
            f"Found {explanation}: {pattern}"
```

---

## Exemptions

### When Hardcoding Is Allowed

**Structural constants** (defined by simulation theory, not organization):
```python
# ✅ OK: Mathematical constants
SECONDS_PER_DAY = 86400
DAYS_PER_YEAR = 365.25

# ✅ OK: Percentiles (P10/P50/P90 standard in planning)
percentiles = [10, 50, 90]

# ✅ OK: Priority queue ordering
def __lt__(self, other):
    return self.time < other.time

# ✅ OK: Epsilon for float comparison
if abs(a - b) < 1e-9:
```

**Test-specific values**:
```python
# ✅ OK: Test setup
site = Site(capacity=100)  # Arbitrary test value
```

### When to Add Exemptions

If a guardrail incorrectly flags structural code:
1. Confirm it's truly structural (not organization-specific)
2. Document why in code comment
3. Update guardrail test to ignore that pattern

```python
# Guardrail update example
if re.search(r'\b86400\b', source):
    # Exemption: SECONDS_PER_DAY is structural constant
    pass
```

---

## Comparison: With vs Without Guardrails

### Scenario: Adding New Budget Constraint

#### Without Guardrails (Risky)

```python
# Developer implements:
class BudgetThrottlingConstraint:
    def evaluate(self, state, event):
        # Seems reasonable...
        duration_multiplier = 1.0 / max(0.5, budget_ratio)

# PR review:
# ✅ Tests pass
# ✅ Code review: "Looks good"
# ✅ PR merged

# Week 10: SCRI calibration
# ❌ "How do I change the 2x max slowdown to 5x?"
# ❌ "Why is 0.5 hardcoded? That's not what we observed."
# ❌ Architectural fix required, downstream changes
```

#### With Guardrails (Safe)

```python
# Developer implements:
class BudgetThrottlingConstraint:
    def evaluate(self, state, event):
        duration_multiplier = 1.0 / max(0.5, budget_ratio)

# CI runs:
# ❌ test_budget_constraint_has_no_hardcoded_response_logic → FAIL
#    Found 'max(0.5': hardcoded minimum

# PR blocked with guidance:
# "Extract assumption into response_curve parameter"

# Developer fixes:
class BudgetThrottlingConstraint:
    def __init__(self, budget_per_day, response_curve):
        self.response_curve = response_curve

    def evaluate(self, state, event):
        duration_multiplier = self.response_curve.sample_multiplier(...)

# CI runs:
# ✅ Guardrails pass
# ✅ Tests pass
# ✅ PR merged

# Week 10: SCRI calibration
# ✅ "Change min_speed_ratio from 0.5 → 0.2 in config"
# ✅ No code changes required
# ✅ Calibration succeeds
```

---

## Summary

| Property | Value |
|----------|-------|
| **Purpose** | Enforce The Ilana Law via automated tests |
| **Scope** | Calibration readiness + entity purity |
| **Enforcement** | CI blocks PRs if guardrails fail |
| **Failure interpretation** | Architecture regression, not test failure |
| **Maintenance** | Low (passive, rare failures, clear fixes) |
| **Value** | High (prevents decay, enforces calibration readiness) |

**Key Insight**: Guardrails are not just tests. They are **constitutional rules** that protect the architecture from erosion over time.

Without guardrails, good architecture decays through small violations.
With guardrails, The Ilana Law remains enforceable indefinitely.

---

**See also**:
- [Architectural Principles](ARCHITECTURAL_PRINCIPLES.md) - The Ilana Law definition
- [Architectural Review Findings](ARCHITECTURAL_REVIEW_FINDINGS.md) - Why guardrails were added
- [STEP 1 Completion](STEP1_COMPLETION.md) - First constraint fixed with guardrails
