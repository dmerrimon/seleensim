# SeleenSIM Calibration UI

**⚠️ THROWAWAY CODE - For SCRI calibration session only**

**Purpose**: Interactive parameter manipulation for validation checkpoint

**Lifespan**: Single session, then disposable

**Status**: Ready for SCRI session

---

## Directory Structure

```
calibration_ui/
├── README.md              # This file
├── requirements.txt       # Dependencies
├── notebook/              # Jupyter notebooks (live manipulation)
│   ├── 01_baseline_calibration.ipynb    # Baseline + exercises
│   ├── 02_sensitivity_analysis.ipynb    # Parameter sweeps
│   └── 03_live_calibration_session.ipynb # Fast iteration (recommended)
└── control_panel/         # (Future: Streamlit/Gradio if needed)
```

---

## Design Principles

**This is NOT a product** - It's a validation tool.

### ✅ What This IS
- **Throwaway interface** for one-time SCRI session
- **Parameter manipulation tool** (sliders, inputs, re-run)
- **Directionality tester** (does changing X affect Y as expected?)
- **Learning environment** (SCRI explores parameter space)
- **Validation checkpoint** (does architecture support calibration?)

### ❌ What This IS NOT
- ❌ Production UI (this code gets deleted after session)
- ❌ Feature showcase (this is for learning, not selling)
- ❌ Requirements tool (no persistence, no workflows)
- ❌ Dashboard (no monitoring, no auth, no integrations)
- ❌ Engine modification (imports only, never modifies)

---

## Rules for This Code

Per user directive:

1. **This is throwaway** - Delete after SCRI session
2. **Lives under /calibration_ui/** - Isolated from engine
3. **Imports engine, never modifies it** - Read-only access
4. **No assumptions** - Just parameter manipulation
5. **No persistence** - No databases, no saved state
6. **No workflows** - No auth, no user management
7. **Clarity over aesthetics** - Quick and functional

**If anything pressures engine architecture, STOP.**

---

## Use Cases

### 1. SCRI Session: Live Parameter Manipulation
**Goal**: Can SCRI express their reality using our parameters?

**Workflow**:
```python
# SCRI says: "I think budget pressure causes 2x slowdown"
min_speed_ratio = 0.5  # 👈 CHANGE THIS VALUE

# Run simulation
constraint = BudgetThrottlingConstraint(
    budget_per_day=50000,
    response_curve=LinearResponseCurve(min_speed_ratio=min_speed_ratio)
)
results = engine.run(trial, constraints=[constraint], num_runs=100)

# Show results
print(f"P50 completion: {results.completion_time_p50:.1f} days")

# SCRI: "Too fast, more like 5x slowdown"
min_speed_ratio = 0.2  # 👈 CHANGE AGAIN

# Re-run, iterate until SCRI says "That feels right"
```

### 2. Sensitivity Analysis
**Goal**: Does changing X affect Y in expected ways?

**Test**:
- Sweep `min_speed_ratio` from 0.2 → 1.0
- Plot P50 completion time
- Ask SCRI: "Does this direction make sense?"

### 3. Convergence Test
**Goal**: Can SCRI iterate without developer help?

**Success**: SCRI adjusts parameters independently until convergence

---

## What's Included

### Notebook 1: Baseline Calibration (`01_baseline_calibration.ipynb`)
**Purpose**: Interactive parameter manipulation

**Content**:
- Define baseline trial (site, flow, constraints)
- Exercise 1: Budget constraint (change `min_speed_ratio`, re-run)
- Exercise 2: Capacity constraint (change `threshold`, `max_multiplier`, re-run)
- Exercise 3: Combined constraints
- Comparison: Unconstrained vs constrained
- Save calibrated parameters to JSON

**Usage**: Open in Jupyter, execute cells, change parameter values inline, re-run

### Notebook 2: Sensitivity Analysis (`02_sensitivity_analysis.ipynb`)
**Purpose**: Test directionality

**Content**:
- Sweep `min_speed_ratio` from 0.2 → 1.0, plot results
- Sweep `budget_per_day` from 25k → 150k, plot results
- Sweep capacity `threshold` from 0.5 → 1.0, plot results
- Sweep capacity `max_multiplier` from 1.0 → 5.0, plot results
- Summary table of all sensitivity tests

**Usage**: Run all cells, review plots with SCRI, validate directionality

### Notebook 3: Live Calibration Session (`03_live_calibration_session.ipynb`)
**Purpose**: Fast iteration during live SCRI session

**Structure** (per requirements):
- Cell 1: Load assumption parameters (JSON/dict)
- Cell 2: Modify 4 key parameters (change → re-run)
- Cell 3: Run simulation (5-10 seconds)
- Cell 4: Visualize outputs (histogram + box plot)
- Save: Export calibrated parameters to JSON

**Workflow**: Load → Modify → Run → Visualize → Repeat

**Usage**: Start here for live SCRI session, iterate until convergence

---

## Quick Start

```bash
# Install dependencies
cd calibration_ui
pip install -r requirements.txt

# Launch Jupyter
jupyter notebook

# For live SCRI session (recommended):
# → Open: notebook/03_live_calibration_session.ipynb
# → Fast iteration: Load → Modify → Run → Visualize → Repeat

# For exploration:
# → 01_baseline_calibration.ipynb (exercises)
# → 02_sensitivity_analysis.ipynb (parameter sweeps)
```

---

## Integration with Engine

**Imports only, never modifies:**

```python
# Read-only access to engine
from seleensim.entities import Site, Trial, PatientFlow
from seleensim.distributions import Triangular, Gamma, Bernoulli
from seleensim.simulation import SimulationEngine
from seleensim.constraints import (
    BudgetThrottlingConstraint,
    LinearResponseCurve,
    # ... etc
)

# Use engine as-is
engine = SimulationEngine(master_seed=42, constraints=[...])
results = engine.run(trial, num_runs=100)
```

**No modifications to engine code. Ever.**

---

## SCRI Session Checklist

**Before session:**
- [ ] `jupyter notebook` launches successfully
- [ ] Both notebooks run without errors
- [ ] Baseline trial is reasonable (not dummy data)
- [ ] Visualizations render correctly
- [ ] Parameter ranges make sense

**During session:**
- [ ] SCRI drives parameter choices (not you)
- [ ] Ask "why?" for their estimates
- [ ] Test directionality together
- [ ] Document gaps in comments
- [ ] Save final parameters to JSON

**After session:**
- [ ] Export calibrated parameters
- [ ] Document findings in session notes (within notebook)
- [ ] Assess: Did architecture hold up?
- [ ] Decide: Keep? Modify? Rebuild?
- [ ] **Delete this directory if no longer needed**

---

## Constraints (from ARCHITECTURE_LOCK.md)

### ✅ Allowed
- Import engine modules (read-only)
- Manipulate parameters
- Visualize results
- Export calibrated parameters to JSON

### ❌ Prohibited
- Modify engine code
- Add new assumptions to engine
- Create persistence layer
- Build workflows or auth
- Integrate with external systems

**If you need any of the prohibited items, you're building the wrong thing.**

---

## Success Criteria

After SCRI session, you should be able to say:

1. ✅ **SCRI understood parameters** - They knew what each parameter meant
2. ✅ **SCRI provided estimates** - They gave values from experience
3. ✅ **SCRI trusted directionality** - More X → More Y made sense
4. ✅ **SCRI iterated independently** - They changed parameters without help
5. ✅ **Results were interpretable** - Outputs matched their intuition
6. ✅ **Calibrated parameters saved** - Final values exported to JSON

**If all YES**: Architecture validated, delete this directory, proceed

**If any NO**: Document gaps, assess if fixable with parameters or requires engine changes

---

## After SCRI Session

### Scenario A: Architecture Validated ✅
- Save calibrated parameters to repo
- Document findings
- Delete this directory (it's throwaway)
- Proceed to next phase

### Scenario B: Minor Gaps ⚠️
- Document what's missing (new response curves? new distributions?)
- Assess if fixable with parameters
- Design solution
- Test again

### Scenario C: Major Rework 🚩
- Document root cause
- Architectural review required
- Update ARCHITECTURE_LOCK.md
- Redesign approach

---

## Response Patterns (from SCRI_CALIBRATION_PREP.md)

**When SCRI says**: "We need enrollment ramps to really use this"

**You say**: "Totally fair—that's why I didn't build them yet. I want to learn how you think about them before encoding anything."

**When SCRI says**: "Can this integrate with our EDC?"

**You say**: "That's execution tracking, not simulation. Let's first validate the simulation works, then we can discuss integration."

**When SCRI says**: "This doesn't capture [X]"

**You say**: "Exactly what I needed to hear. Tell me more about X. How would you describe it?"

---

## References

- `../ARCHITECTURE_LOCK.md` - Architectural boundaries
- `../docs/SCRI_CALIBRATION_PREP.md` - Complete session guide (600+ lines)
- `../docs/GUARDRAILS.md` - What's enforced automatically
- `../examples/constraint_integration.py` - Constraint usage patterns

---

**Remember**: This code is disposable. Its purpose is to validate the engine architecture, not to become a product.

If SCRI can calibrate using our parameters → Architecture validated → Delete this directory

If SCRI can't → Document gaps → Assess what needs to change → Iterate

Either outcome is valuable. The goal is learning.
