# SCRI Calibration Session: Preparation Guide

**Status**: Ready for scheduling
**Purpose**: Validate that architecture supports real-world calibration workflow
**Duration**: 2-3 hours recommended

---

## Session Objectives

### What This Session IS

**A live parameter manipulation exercise** testing:
1. ✅ Can SCRI express their reality using the parameter interface?
2. ✅ Do simulation outputs move in ways they recognize?
3. ✅ Do they trust the directionality of change?
4. ✅ Can they iterate (guess → run → calibrate → run)?

**Format**:
- Interactive, hands-on
- SCRI drives parameter choices
- We observe, take notes, ask questions
- Learning session, not presentation

---

### What This Session IS NOT

❌ A demo of features
❌ A requirements-gathering meeting
❌ A UI critique session
❌ A sales pitch
❌ A commitment to build specific features next

**If SCRI says**: "We'd need [feature X] to really use this"

**Your response**:
> "Totally fair—that's why I didn't build them yet. I want to learn how you think about them before encoding anything."

**Why this works**:
- Signals maturity (not over-building)
- Invites collaboration (their expertise)
- Prevents premature assumptions (learn first, then build)

---

## Pre-Session Setup

### 1. Environment Preparation

**Install and verify**:
```bash
cd /Users/donmerriman/SeleenSIM
source venv/bin/activate
python -m pytest tests/ -v  # Should see: 216 passed
```

**Prepare example scripts**:
- `examples/constraint_integration.py` - Shows all constraint types
- Simple custom script for live manipulation

---

### 2. Example Trial Configuration

**Prepare baseline trial** (conservative estimates):
```python
from seleensim.entities import Site, Trial, PatientFlow
from seleensim.distributions import Triangular, Gamma, Bernoulli
from seleensim.simulation import SimulationEngine
from seleensim.constraints import (
    BudgetThrottlingConstraint,
    ResourceCapacityConstraint,
    LinearResponseCurve,
    LinearCapacityDegradation
)

# Baseline site
site = Site(
    site_id="SITE_001",
    activation_time=Triangular(low=30, mode=45, high=90),
    enrollment_rate=Gamma(shape=2, scale=1.5),
    dropout_rate=Bernoulli(p=0.15)
)

# Patient flow
flow = PatientFlow(
    flow_id="STANDARD_FLOW",
    states={"enrolled", "completed"},
    initial_state="enrolled",
    terminal_states={"completed"},
    transition_times={
        ("enrolled", "completed"): Triangular(low=90, mode=180, high=365)
    }
)

# Trial
trial = Trial(
    trial_id="BASELINE_TRIAL",
    target_enrollment=200,
    sites=[site],
    patient_flow=flow
)

# Conservative constraints (Week 1 guesses)
constraints = [
    BudgetThrottlingConstraint(
        budget_per_day=50000,
        response_curve=LinearResponseCurve(min_speed_ratio=0.5)  # 2x max slowdown
    ),
    ResourceCapacityConstraint(
        resource_id="MONITOR",
        # Defaults to NoCapacityDegradation (queueing only)
    )
]

# Run baseline
engine = SimulationEngine(master_seed=42, constraints=constraints)
results = engine.run(trial, num_runs=100)

print(f"P50 completion time: {results.completion_time_p50:.1f} days")
print(f"P90 completion time: {results.completion_time_p90:.1f} days")
```

---

### 3. Parameter Exploration Script

**Prepare for live manipulation**:
```python
def run_scenario(
    budget_per_day=50000,
    min_speed_ratio=0.5,
    capacity_threshold=0.8,
    capacity_max_multiplier=2.0,
    num_runs=100
):
    """
    Quick scenario runner for live exploration.

    SCRI can change any parameter and immediately see impact.
    """
    # Build constraints with parameters
    constraints = [
        BudgetThrottlingConstraint(
            budget_per_day=budget_per_day,
            response_curve=LinearResponseCurve(min_speed_ratio=min_speed_ratio)
        ),
        ResourceCapacityConstraint(
            resource_id="MONITOR",
            capacity_response=LinearCapacityDegradation(
                threshold=capacity_threshold,
                max_multiplier=capacity_max_multiplier
            )
        )
    ]

    # Run simulation
    engine = SimulationEngine(master_seed=42, constraints=constraints)
    results = engine.run(trial, num_runs=num_runs)

    return {
        "p10": results.completion_time_p10,
        "p50": results.completion_time_p50,
        "p90": results.completion_time_p90,
        "events_rescheduled": results.mean_events_rescheduled
    }

# Example usage during session:
print("Baseline (conservative):")
print(run_scenario())

print("\nMore aggressive budget pressure:")
print(run_scenario(min_speed_ratio=0.2))  # 5x max slowdown

print("\nHigher capacity degradation:")
print(run_scenario(capacity_max_multiplier=3.0))  # 3x slower when overloaded
```

---

## Session Agenda (2-3 hours)

### Part 1: Context Setting (15 min)

**Explain what we built**:
- "We built calibration interfaces, not a trial management system"
- "We want to learn if you can express YOUR reality using OUR parameters"
- "This is about testing the architecture, not showing off features"

**Show the constraint**:
```python
# The question we're answering:
BudgetThrottlingConstraint(
    budget_per_day=?,
    response_curve=?
)
# Can SCRI fill in the ?'s with their reality?
```

---

### Part 2: Baseline Calibration (30 min)

**Goal**: Establish rough parameter ranges

**Exercise 1: Budget Pressure**

Ask SCRI:
1. "In your experience, when budget is tight, how much does work slow down?"
   - 1.5x slower?
   - 2x slower?
   - 5x slower?

2. "Is it linear? Or is there a threshold where it suddenly gets bad?"

3. "How would you describe the shape?"

**Live manipulation**:
```python
# Start conservative
run_scenario(min_speed_ratio=0.5)  # 2x max

# Try their suggestion
run_scenario(min_speed_ratio=0.3)  # ~3x max

# Compare results
# Ask: "Does this direction make sense?"
```

---

**Exercise 2: Resource Pressure**

Ask SCRI:
1. "When you have 1 monitor for 10 sites vs 1 for 5 sites, what happens?"

2. "Does work quality degrade? Or just queue up?"

3. "At what utilization level do you see slowdowns?"

**Live manipulation**:
```python
# No degradation (queueing only)
run_scenario(capacity_max_multiplier=1.0)

# Linear degradation
run_scenario(capacity_threshold=0.8, capacity_max_multiplier=2.0)

# Ask: "Which feels more realistic?"
```

---

### Part 3: Sensitivity Analysis (45 min)

**Goal**: Test if changes move outputs recognizably

**Test directionality**:

| Parameter | Change | Expected Impact |
|-----------|--------|----------------|
| `min_speed_ratio` | 0.5 → 0.2 | P90 should increase (more slowdown) |
| `budget_per_day` | 50k → 100k | P90 should decrease (less pressure) |
| `capacity_threshold` | 0.8 → 0.6 | P90 should increase (earlier degradation) |
| `capacity_max_multiplier` | 2.0 → 3.0 | P90 should increase (worse degradation) |

**For each change**:
1. Run baseline
2. Change ONE parameter
3. Run again
4. Ask: "Does this make sense? Too much? Too little?"

---

### Part 4: Realism Check (30 min)

**Goal**: Identify gaps in current model

**Questions to ask**:

**About distributions**:
1. "Does Triangular(30, 45, 90) feel right for site activation?"
2. "Is the shape right? Too symmetric? Too wide?"
3. "Would you describe it differently?"

**About response curves**:
1. "Is linear the right shape? Or more like a threshold?"
2. "Do you see gradual degradation or sudden drops?"
3. "Are there other factors we're missing?"

**About missing features**:
1. "What would make this feel more realistic?"
2. "What's the biggest gap between this and reality?"

**Critical**: Take notes, DON'T commit to building anything yet

---

### Part 5: Iteration Test (30 min)

**Goal**: Test the calibration loop

**Workflow**:
1. SCRI picks initial parameters (guesses)
2. Run simulation
3. SCRI reviews outputs: "Too high? Too low?"
4. SCRI adjusts parameters
5. Run again
6. Repeat until SCRI says "That feels about right"

**Success criteria**:
- ✅ SCRI can iterate without developer help
- ✅ Each iteration moves outputs in expected direction
- ✅ SCRI gains confidence in the model
- ✅ Parameters converge to reasonable values

---

## Questions to Ask SCRI

### About Current Model

**Budget constraint**:
- [ ] Does budget pressure actually slow work, or is it more binary (proceed/stop)?
- [ ] What's the typical range of budget_per_day for your trials?
- [ ] Is 2x max slowdown realistic? Or more like 5x? 10x?
- [ ] Is the relationship linear? Or more like a threshold?

**Resource constraint**:
- [ ] Do you see efficiency degradation, or just queueing?
- [ ] At what utilization % do things start slowing down?
- [ ] Is it gradual or sudden?
- [ ] What resources matter most? (monitors, coordinators, PIs?)

**Distributions**:
- [ ] Are triangular distributions intuitive? Or would you prefer different shapes?
- [ ] Can you estimate low/mode/high from experience?
- [ ] Would normal or lognormal feel more natural?

---

### About Deferred Features

**Enrollment** (DO NOT BUILD YET - LEARN FIRST):
- [ ] How do enrollment rates ramp at your sites?
- [ ] Linear? Threshold? S-curve?
- [ ] How long is the ramp period typically?
- [ ] What factors affect the ramp? (seasonality, site experience, etc.)

**Variance modeling**:
- [ ] Is it just about mean outcomes? Or does variability matter?
- [ ] Do you care about "worst case" vs "typical case"?
- [ ] Would "same mean, different variance" matter for planning?

**Multi-site interactions**:
- [ ] Do sites compete for shared resources?
- [ ] Do you see learning effects (later sites activate faster)?
- [ ] Are there portfolio-level constraints?

---

## What to Observe

### Good Signs ✅

- SCRI immediately says "That number is way off"
  - *Shows they have intuition about parameters*

- SCRI asks "Can I try X instead?"
  - *Shows they understand parameter interface*

- SCRI says "That moved the right direction"
  - *Shows they trust the model*

- SCRI debates among themselves about right value
  - *Shows parameters map to their mental models*

### Warning Signs ⚠️

- SCRI says "I have no idea what this should be"
  - *Parameter might be too abstract or poorly named*

- SCRI says "This doesn't capture [important thing]"
  - *Might be missing a key assumption*

- SCRI says "The outputs don't make sense"
  - *Could be bug, or could be model gap*

### Red Flags 🚩

- SCRI says "We need [big feature] before this is useful"
  - *If true, we mis-scoped MVP*
  - *If false, we need to show value of current state*

- SCRI says "This is too complicated"
  - *Interface might not be intuitive*
  - *Need to simplify or add docs*

- SCRI loses interest after 30 minutes
  - *Not engaging with the problem space*
  - *Might need different approach*

---

## Post-Session Actions

### Immediate (Within 24 Hours)

1. **Document findings**:
   - What parameters did SCRI settle on?
   - What felt right vs wrong?
   - What gaps did they identify?

2. **Assess architecture**:
   - Did current parameters suffice?
   - Were there assumption types we missed?
   - Do response curves need new shapes?

3. **Prioritize next steps**:
   - What should be built next?
   - What should be deferred longer?
   - What should be changed?

---

### Medium Term (Within 1 Week)

1. **If architecture held up** ✅:
   - Document calibrated parameters
   - Run validation simulations
   - Plan enrollment logic design (if needed)

2. **If gaps discovered** ⚠️:
   - Document gaps explicitly
   - Design solutions (parameters first, structure last)
   - Propose architectural changes if needed

3. **If major rework needed** 🚩:
   - Conduct architectural review
   - Identify what broke
   - Design corrected approach
   - Update ARCHITECTURE_LOCK.md

---

## Session Facilitation Tips

### Do's ✅

- **Let SCRI drive**: "What do you think this should be?"
- **Ask why**: "What makes you say 2x vs 5x?"
- **Test understanding**: "If I increase X, what happens to Y?"
- **Embrace uncertainty**: "We don't know either - that's why we're here"
- **Take notes**: Document everything, commit to nothing

### Don'ts ❌

- **Don't present**: This isn't a demo
- **Don't defend**: If they say it's wrong, believe them
- **Don't commit**: "We can build that" → "Let's see if parameters work first"
- **Don't rush**: Let them think, debate, iterate
- **Don't oversell**: Acknowledge gaps honestly

---

## Success Criteria

### Minimum Success ✅

After session, you can say:
1. ✅ "SCRI can express their intuition using our parameters"
2. ✅ "Changing parameters changes outputs in expected ways"
3. ✅ "SCRI trusts the directionality (more X → more Y)"
4. ✅ "We identified specific gaps, not vague concerns"

### Ideal Success 🎯

After session, SCRI says:
- "I could run this myself with different parameters"
- "The outputs feel realistic given the inputs"
- "I see how this could help us plan better"
- "Here's what we'd need next to really use it"

### Failure Indicators 🚨

After session, SCRI says:
- "This doesn't capture how trials actually work"
- "I can't tell what changing parameters would do"
- "We'd need to rebuild this to make it useful"
- "This is more work than our current spreadsheets"

**If failure**: Don't panic. Document what broke. This is discovery, not deployment.

---

## Follow-Up Plan

### Scenario A: Architecture Validated ✅

**Next steps**:
1. Document calibrated parameters in repo
2. Run extended validation (more runs, more scenarios)
3. Design enrollment logic (if SCRI needs it)
4. Plan stochastic curves (if variance matters)
5. Move toward production readiness

**Timeline**: 2-4 weeks to next milestone

---

### Scenario B: Minor Gaps Found ⚠️

**Examples**:
- "Need threshold response curves, not just linear"
- "Need gamma distribution option, not just triangular"
- "Need batch processing for parameter sweeps"

**Next steps**:
1. Assess if gaps can be filled with parameters
2. Design new response curve types if needed
3. Add new distributions if needed
4. Test with SCRI again

**Timeline**: 1-2 weeks to address, then re-test

---

### Scenario C: Major Rework Needed 🚩

**Examples**:
- "Budget constraint isn't the right model"
- "Need completely different constraint types"
- "Entity model doesn't match our process"

**Next steps**:
1. Conduct deep architectural review
2. Identify root cause of mismatch
3. Propose corrected approach
4. Get buy-in before implementing
5. Update ARCHITECTURE_LOCK.md

**Timeline**: 4-6 weeks to redesign and validate

---

## Appendix: Common Questions

**Q: "Can we integrate this with our EDC system?"**
**A**: "That's out of scope for simulation engine, but we can design outputs that integrate. What format do you need?"

**Q: "Can this optimize site selection?"**
**A**: "Not yet - that's a strategic layer on top of simulation. We can discuss after calibration proves the simulation works."

**Q: "Can we see this in a dashboard?"**
**A**: "Not today - we focused on the simulation engine first. Once we validate the model, we can layer on visualization."

**Q: "How accurate is this?"**
**A**: "As accurate as your parameters. That's what we're here to test - can you parameterize your reality?"

**Q: "What if we don't know these parameters?"**
**A**: "That's valuable data! If you can't estimate it, maybe it doesn't matter. Or maybe we need different parameters."

**Q: "Can we run this on historical data?"**
**A**: "Yes, eventually. First we need to validate the forward simulation works. Then we can build calibration from historical data."

---

## Final Checklist

Before session:
- [ ] Environment tested (216/216 tests pass)
- [ ] Example scripts prepared
- [ ] Baseline trial configuration ready
- [ ] Questions list printed
- [ ] Note-taking setup (doc + recording if approved)
- [ ] ARCHITECTURE_LOCK.md reviewed
- [ ] No feature commitments in talking points

During session:
- [ ] Let SCRI drive parameter choices
- [ ] Document their intuitions and ranges
- [ ] Test directionality (more X → more Y)
- [ ] Ask about missing features (but don't commit)
- [ ] Observe engagement level
- [ ] Note confusion or excitement points

After session:
- [ ] Summarize findings within 24 hours
- [ ] Assess architecture held up or needs changes
- [ ] Document calibrated parameters
- [ ] Plan next steps based on scenario (A/B/C)
- [ ] Update project plan

---

**This session is the MOMENT.**

It validates whether months of architectural work was worth it.

Approach it as **discovery**, not demo.

Your job: **Learn how SCRI thinks about reality.**

Their job: **Test if your interfaces can express it.**

Success: **"Yes, I can calibrate this myself."**
