# ARCHITECTURE LOCK

**Status**: 🔒 LOCKED (2026-02-14)
**Authority**: Foundational document - changes require explicit architectural review

---

## Purpose

This document defines **what this system is and is not**. It protects the architecture from well-intentioned erosion under pressure.

When someone says "just add X", this document is your answer.

---

## The Core Distinction: Assumption vs Interface

### ❌ NOT: "The System Knows How Trials Work"

**Wrong approach**:
```python
def budget_throttle(budget_ratio):
    if budget_ratio < 0.5:
        return 2.0  # System assumes 50% budget = 2x slower
```

**Why it fails**: Bakes assumptions into code → SCRI can't calibrate without developer

### ✅ YES: "The System Provides Tools to Express Reality"

**Correct approach**:
```python
def budget_throttle(budget_ratio, response_curve):
    return response_curve.sample_multiplier(budget_ratio)
    # System asks: "How does YOUR budget affect YOUR work?"
```

**Why it works**: Separates structure from behavior → SCRI calibrates via parameters

---

## The Rule

> **"Calibration changes parameters, never structure."**

### What This Means

**Structure** (hardcoded, never changes):
- Constraint exists ✓
- Engine evaluates constraints ✓
- Events can be delayed ✓
- Time flows forward ✓
- Seeds produce determinism ✓

**Behavior** (parameterized, SCRI calibrates):
- How much budget slows work ✓
- How resource pressure affects efficiency ✓
- Site activation time distributions ✓
- Enrollment rates ✓
- Dropout probabilities ✓

### Examples

| SCRI Says | System Response | Requires |
|-----------|----------------|----------|
| "Budget pressure causes 5x slowdown, not 2x" | ✅ Change `min_speed_ratio` parameter | Config change |
| "We need enrollment to ramp over 60 days" | ✅ Add `EnrollmentRampCurve` parameter | Parameter |
| "Constraints should compose differently" | ❌ NO - This is structure | Code change |
| "Sites should track their own budget" | ❌ NO - This is structure | Code change |

**If SCRI's need requires changing structure → it's a feature request, not calibration.**

---

## MVP Boundary (What's In)

### Core Primitives (Implemented ✓)

1. **Probability Distributions**
   - Triangular, LogNormal, Gamma, Bernoulli
   - Stateless, deterministic sampling
   - JSON serializable

2. **Entity Models**
   - Site, Activity, Resource, PatientFlow, Trial
   - Frozen dataclasses (immutable)
   - No business logic, no sampling

3. **Constraint System**
   - Validity: TemporalPrecedence, Predecessor
   - Feasibility: BudgetThrottling, ResourceCapacity
   - Response curves: Injectable behavior objects

4. **Simulation Engine**
   - Monte Carlo with explicit seeds
   - Event-driven discrete time
   - Deterministic, reproducible

5. **Calibration Infrastructure**
   - Response curve abstractions
   - Parameter interfaces
   - CI guardrails (28 tests)

### What's Calibratable (Parameters ✓)

- Distribution parameters (mean, CV, low/mode/high)
- Response curve shapes (linear, threshold, etc.)
- Response curve parameters (thresholds, max penalties)
- Resource capacities
- Budget rates

### What's NOT Calibratable (Structure 🔒)

- How constraints compose (AND/MAX/MERGE rules)
- Event scheduling algorithm
- Determinism mechanism (seeding)
- Entity immutability
- Constraint evaluation order

---

## MVP Boundary (What's Out)

### Explicitly Deferred (High Risk)

**1. Enrollment Logic**
- **Why deferred**: Highest assumption density
- **Risk areas**: Ramp curves, capacity pressure, inter-arrival times, seasonality
- **Before implementing**: SCRI must validate pattern with Budget + Capacity constraints
- **Documentation**: See `docs/ENROLLMENT_RAMP_AUDIT.md`

**2. Portfolio / Multi-Trial Logic**
- **Why deferred**: Strategic layer, not simulation primitive
- **Risk**: Resource allocation across trials = organizational assumptions
- **When**: After single-trial calibration proven

**3. Optimization Algorithms**
- **Why deferred**: Premature - need cost functions from SCRI
- **Risk**: Objective function = hidden strategic assumptions
- **When**: After SCRI defines success metrics empirically

### Out of Scope (Execution Layer)

**4. UI / Dashboard**
- Not a primitive, execution tracking
- Risk: Feature creep, not architecture

**5. Real-time Integrations**
- Not simulation, data engineering
- Risk: Complexity explosion

**6. User Management / Auth**
- Not simulation, application layer
- Risk: Distraction from core value

---

## The Ilana Law (Constitutional)

> **"Could this number be different for a different organization?"**
>
> **YES** → It's an **assumption** → Must be **parameterized**
> **NO** → It's **structural** → OK to **hardcode**

### Enforcement Mechanism

**CI Guardrails** (28 tests):
- Detect hardcoded assumptions in constraint logic
- Require behavior objects, not magic numbers
- Block PRs with violations
- Run on every commit

**Test file**: `tests/test_calibration_readiness.py`

### Examples

| Question | Answer | Action |
|----------|--------|--------|
| Could max budget slowdown be different? | YES | → Parameter: `min_speed_ratio` |
| Could capacity threshold be different? | YES | → Parameter: `threshold` |
| Could constraint composition be different? | NO | → Hardcode: `compose_via_and()` |
| Could time flow backward? | NO | → Hardcode: `time += delta` |

---

## Prohibited Patterns

### ❌ Pattern 1: Hardcoded Response Curves

**Violation**:
```python
if budget_ratio < 0.5:
    slowdown = 2.0  # Why 0.5? Why 2.0?
```

**Correct**:
```python
slowdown = response_curve.sample_multiplier(budget_ratio, seed)
```

**Caught by**: `test_budget_constraint_has_no_hardcoded_response_logic()`

---

### ❌ Pattern 2: Entity Sampling

**Violation**:
```python
class Site:
    def get_activation_time(self, seed):
        return self.activation_time.sample(seed)  # NO!
```

**Correct**:
```python
# Engine samples, not entity
activation_time = site.activation_time.sample(seed)
```

**Caught by**: `test_site_does_not_sample_distributions()`

---

### ❌ Pattern 3: Hidden Defaults

**Violation**:
```python
class BadConstraint:
    def __init__(self, budget: float, max_slowdown: float = 2.0):
        # ^^^^^^^^^ Hidden assumption!
```

**Correct**:
```python
class GoodConstraint:
    def __init__(self, budget: float, response_curve: ResponseCurve):
        # ^^^^^^^^^^^^^ Explicit behavior object
```

**Caught by**: `test_constraints_accept_behavior_objects_not_magic_numbers()`

---

### ❌ Pattern 4: Org-Specific Logic

**Violation**:
```python
if org_type == "pharma":
    buffer = 30  # Pharma needs 30-day buffer
elif org_type == "biotech":
    buffer = 14  # Biotech moves faster
```

**Correct**:
```python
# User provides buffer as parameter
buffer = config.regulatory_buffer_days
```

**Caught by**: Code review + architectural review

---

## Calibration Contract

### What SCRI Can Change (Parameters)

✅ Distribution parameters:
```python
# Week 1: Expert guess
activation_time = Triangular(low=30, mode=45, high=90)

# Week 6: Calibrated
activation_time = Triangular(low=25, mode=38, high=75)
```

✅ Response curve parameters:
```python
# Week 1: Conservative estimate
response_curve = LinearResponseCurve(min_speed_ratio=0.5)

# Week 6: Data-driven
response_curve = LinearResponseCurve(min_speed_ratio=0.2)
```

✅ Response curve models:
```python
# Week 1: Linear assumption
response_curve = LinearResponseCurve(...)

# Week 6: Threshold discovered
response_curve = ThresholdResponseCurve(...)
```

### What SCRI Cannot Change (Structure)

❌ Constraint composition logic
❌ Event scheduling algorithm
❌ Determinism mechanism
❌ Entity definitions
❌ Constraint evaluation order

**If SCRI needs these → Feature request, not calibration**

---

## Red Lines (Non-Negotiable)

### 1. Entities Remain Pure Data

**No methods beyond `to_dict()`**
- No `calculate_X()`
- No `sample_Y()`
- No `compute_Z()`

**Why**: Entities are specifications, not executors

---

### 2. Constraints Remain Structureless

**No hardcoded domain logic**
- No `if org_type == "pharma"`
- No magic thresholds
- No hardcoded formulas

**Why**: Constraints define gates, not organizational rules

---

### 3. Engine Remains Domain-Agnostic

**No trial-specific logic**
- No "enrollment" special cases
- No "IRB approval" hardcoded
- No therapeutic area assumptions

**Why**: Engine is Monte Carlo simulator, not trial manager

---

### 4. Determinism Remains Absolute

**No randomness without seeds**
- No `random.random()`
- No `time.time()` in logic
- No external state dependencies

**Why**: Reproducibility is non-negotiable for validation

---

## Boundaries of Responsibility

### This System IS:
- ✅ Monte Carlo simulation engine for discrete events
- ✅ Constraint evaluation framework
- ✅ Probability distribution library
- ✅ Deterministic sampler with explicit seeds
- ✅ Parameter interface for calibration

### This System IS NOT:
- ❌ Trial management software
- ❌ Project scheduling tool
- ❌ Resource allocation optimizer
- ❌ Reporting/analytics platform
- ❌ Integration middleware
- ❌ Database or storage layer

**Corollary**: If it's not simulation primitive, it doesn't belong in the engine.

---

## Decision Framework: Should We Add Feature X?

### Step 1: Classify

Is X:
- A) New entity type (e.g., "Patient", "Investigator")
- B) New constraint type (e.g., "RegulatoryApprovalConstraint")
- C) New response curve (e.g., "SigmoidResponseCurve")
- D) New engine behavior (e.g., "parallel event processing")
- E) Application feature (e.g., "export to Excel")

### Step 2: Apply Tests

| Question | If NO → Reject |
|----------|---------------|
| Is it a simulation primitive? | E fails (application layer) |
| Can it be parameterized? | Watch for hardcoded assumptions |
| Does it respect The Ilana Law? | Must not bake in org-specific logic |
| Does it require SCRI calibration first? | B might (need pattern validation) |
| Could it be a parameter, not code? | C might (could be config) |

### Step 3: Check Precedent

**Has this pattern been validated?**
- Response curves: YES (Budget + Capacity proven)
- Enrollment ramps: NO (need SCRI calibration first)
- Stochastic curves: NO (need mean vs variance evidence)

**Rule**: Don't add second instance of pattern until first instance calibrated

---

## Escape Hatches (When to Break the Lock)

### Valid Reasons to Change Structure

1. **Fundamental correctness issue**
   - Example: "Composition rule is mathematically wrong"
   - Threshold: Peer-reviewed proof required

2. **Determinism violation**
   - Example: "Seeds don't actually guarantee reproducibility"
   - Threshold: Reproducible counter-example required

3. **Performance cliff**
   - Example: "Simulation takes 10+ minutes for 100 runs"
   - Threshold: Profiling data + alternative approach required

### Invalid Reasons (Pressure, Not Principle)

❌ "Client needs it by next week"
❌ "Everyone else does it this way"
❌ "It would only take a few hours"
❌ "We could just add one flag"
❌ "It's a small change"

**Response to pressure**: "That sounds like a valuable feature. Let me show you how to express it with parameters first. If parameters can't handle it, we'll revisit structure."

---

## Maintenance Rules

### Adding New Response Curves

**Allowed without lock change**:
- New implementations of `BudgetResponseCurve`
- New implementations of `CapacityResponseCurve`

**Requirements**:
1. Must implement abstract interface
2. Must be parameterized (no hardcoded assumptions)
3. Must pass guardrail tests
4. Must have calibration example in tests

**Watch for**: Proliferation (if > 5 implementations, consider consolidation)

---

### Adding New Constraint Types

**Requires architectural review**:
- New constraint must fit validity/feasibility taxonomy
- Must identify: What response behavior does it need?
- Must follow pattern: Structure in constraint, behavior in curve

**Before implementing**:
1. Document in proposal (like `constraint_fix_proposal.py`)
2. Identify all assumptions
3. Design response curve interface
4. Show calibration workflow
5. Get approval

---

### Adding New Entity Types

**Rarely needed** (current 5 entities cover most cases):
- Site, Activity, Resource, PatientFlow, Trial

**If needed**:
1. Must be frozen dataclass
2. Must have no methods beyond `to_dict()`
3. Must validate at construction
4. Must have no default values that imply assumptions

---

## Version Control

### This Lock Covers

**MVP Version**: 1.0 (current)
- 4 constraint types
- 2 response curve abstractions
- 4 response curve implementations
- 216 tests passing
- 28 guardrail tests

### Future Versions

**1.1**: Stochastic response curves (after SCRI validation)
**1.2**: State enhancement for degradation (after SCRI validation)
**2.0**: Enrollment logic (after pattern proven with SCRI)

**Each version requires**:
- Architectural review document
- Updated ARCHITECTURE_LOCK.md
- Guardrail tests for new patterns

---

## Calibration Session Protocol

### What SCRI Session IS

**Purpose**: Test if architecture supports calibration workflow

**Success criteria**:
1. ✅ SCRI can express their reality using parameters
2. ✅ Changing parameters changes outcomes recognizably
3. ✅ SCRI trusts directionality (more X → more Y makes sense)
4. ✅ SCRI can iterate (guess → run → calibrate → run)

**Format**:
- Live parameter manipulation
- "What if" exploration
- Sensitivity analysis
- Learning session, not demo

---

### What SCRI Session IS NOT

❌ Demo of features
❌ Requirements gathering meeting
❌ UI critique session
❌ Commitment to build X next

**If SCRI says**: "We'd need enrollment ramps to really use this"

**Response**: "Totally fair—that's why I didn't build them yet. I want to learn how you think about them before encoding anything."

**Why this works**: Signals maturity, invites collaboration, prevents premature assumptions

---

### Questions to Ask SCRI

**About current constraints**:
1. "Does 2x max budget slowdown feel right? Or too aggressive/conservative?"
2. "How does resource pressure actually affect your work?"
3. "What's the shape? Linear? Threshold? Something else?"

**About deferred features**:
1. "How do enrollment rates ramp at your sites?"
2. "Is it linear? Threshold? S-curve? Something else?"
3. "What factors affect the ramp shape?"

**About variance**:
1. "Is it just about mean slowdown? Or does variability matter?"
2. "Do you see predictable slowdowns or erratic ones?"
3. "Would 'same mean, different variance' matter for your planning?"

---

## Authority and Governance

### Who Can Change This Lock?

**ARCHITECTURE_LOCK.md changes require**:
1. Written proposal with rationale
2. Impact analysis (breaking changes?)
3. Alternative considered and rejected
4. Approval from: [Project lead / Architecture committee]

### Who Can Add Parameters?

**New parameters can be added by**:
- Any developer
- Must follow existing patterns
- Must add guardrail tests
- Must document in response curve docstring

**No approval needed for**:
- New response curve implementations (if follow interface)
- New distribution implementations (if follow interface)
- Test additions

---

## Historical Context

**Why This Lock Exists**

On 2026-02-14, after STEPS 1-3 completion:
- Fixed BudgetThrottlingConstraint (hardcoded 2x → parameterized)
- Locked guardrails in CI
- Applied same pattern to ResourceCapacityConstraint

**Lesson learned**: "Without explicit boundary, well-intentioned features erode architecture."

**This lock**: Prevents backsliding under pressure from clients, deadlines, or "just one more thing"

---

## Enforcement

### Automated (CI)

- 28 guardrail tests run on every PR
- PR blocked if violations detected
- No exceptions

### Manual (Code Review)

Before merging:
- [ ] Does this add hardcoded assumptions?
- [ ] Could this be a parameter instead?
- [ ] Does this violate The Ilana Law?
- [ ] Does this change structure vs behavior?
- [ ] Is this primitive or feature?

### Quarterly (Architectural Review)

Every quarter:
- Review response curve count (if > 5, consolidate?)
- Review constraint types (any coupling?)
- Review this lock (still relevant?)
- Document lessons learned

---

## Summary: The Core Protection

**This lock protects**:
1. ✅ Separation of structure (engine) from behavior (parameters)
2. ✅ Calibration-readiness (SCRI can tune without developer)
3. ✅ Entity purity (data, not executors)
4. ✅ Constraint purity (gates, not domain logic)
5. ✅ Determinism (reproducible always)
6. ✅ Long-term maintainability (no technical debt)

**This lock prevents**:
1. ❌ Hardcoded assumptions accumulating
2. ❌ Org-specific logic in engine
3. ❌ Feature creep disguised as "small changes"
4. ❌ Calibration requiring developer intervention
5. ❌ Technical debt from "just this once" exceptions

---

**When someone says "just add X"**, show them this document.

**When pressure mounts**, this lock is your authority.

**When in doubt**, ask: "Is this structure or behavior? Could it be a parameter?"

🔒 **LOCKED - Changes require architectural review**
