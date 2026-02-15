# Enrollment Ramp Curve Audit

## Status: NOT YET IMPLEMENTED ✓

**Good news**: Enrollment logic is not yet implemented (see `simulation.py:533`).

**This is the RIGHT time to define correct patterns** - before violations can occur.

---

## Current State

### What's Defined (CORRECT)

```python
# entities.py
@dataclass(frozen=True)
class Site:
    enrollment_rate: Distribution  # ✅ Distribution, not hardcoded value
```

**Why this is correct**:
- Enrollment rate is a **distribution** (explicit uncertainty)
- Not a magic number
- Calibratable - update distribution parameters, not code

### What's NOT Implemented

```python
# simulation.py:530-534
if event.event_type == "site_activation":
    # Site activated → can now enroll patients
    # For MVP: No downstream events yet (enrollment not implemented)
    pass
```

**Status**: Enrollment event generation is a stub.

---

## Risks When Implementing Enrollment

### The Ilana Law Applied

When implementing enrollment, ask for EVERY numeric literal:

> **"Could this number be different for a different organization?"**

### Risk 1: Hidden Ramp Curves

❌ **VIOLATION** (Do NOT do this):
```python
def generate_enrollment_events(site, current_time):
    # WRONG: Linear ramp assumption hardcoded
    ramp_duration = 30  # Why 30 days?
    ramp_factor = min(1.0, (current_time - site_activation_time) / ramp_duration)

    # WRONG: Enrollment rate scales linearly during ramp
    effective_rate = site.enrollment_rate.sample(seed) * ramp_factor
```

**Problems**:
- **30 days**: Why? Could be different for different organizations
- **Linear ramp**: Why linear? Could be exponential, S-curve, threshold-based
- **min(1.0, ...)**: Why cap at 1.0? Some sites might ramp to 150% over time

✅ **CORRECT** (Explicit ramp behavior):
```python
class EnrollmentRampCurve(ABC):
    """
    Defines how enrollment rate evolves after site activation.

    This is an ASSUMPTION about ramp-up dynamics.
    Different organizations have different ramp patterns:
    - Some ramp linearly (gradual acceleration)
    - Some have threshold effects (sudden activation)
    - Some have S-curves (slow start, rapid middle, plateau)
    """

    @abstractmethod
    def get_ramp_factor(self, days_since_activation: float, seed: int) -> float:
        """
        Get enrollment rate multiplier based on days since activation.

        Args:
            days_since_activation: Time since site became active
            seed: For stochastic ramps

        Returns:
            ramp_factor: Multiplier for base enrollment_rate (0.0 to 1.0+)
        """
        pass

class LinearRampCurve(EnrollmentRampCurve):
    """Linear ramp: rate = base * min(1.0, days / ramp_duration)"""

    def __init__(self, ramp_duration: float, max_factor: float = 1.0):
        self.ramp_duration = ramp_duration
        self.max_factor = max_factor

    def get_ramp_factor(self, days_since_activation: float, seed: int) -> float:
        return min(self.max_factor, days_since_activation / self.ramp_duration)

class ThresholdRampCurve(EnrollmentRampCurve):
    """Threshold ramp: 0% until activation_lag, then instant ramp to full"""

    def __init__(self, activation_lag: float):
        self.activation_lag = activation_lag

    def get_ramp_factor(self, days_since_activation: float, seed: int) -> float:
        return 1.0 if days_since_activation >= self.activation_lag else 0.0

class SCurveRampCurve(EnrollmentRampCurve):
    """S-curve ramp: Slow start, rapid middle, plateau"""

    def __init__(self, midpoint: float, steepness: float):
        self.midpoint = midpoint
        self.steepness = steepness

    def get_ramp_factor(self, days_since_activation: float, seed: int) -> float:
        import math
        # Logistic function: f(x) = 1 / (1 + e^(-steepness * (x - midpoint)))
        return 1.0 / (1.0 + math.exp(-self.steepness * (days_since_activation - self.midpoint)))

# Usage:
def generate_enrollment_events(site, current_time, ramp_curve: EnrollmentRampCurve, seed):
    days_since_activation = current_time - site_activation_time
    ramp_factor = ramp_curve.get_ramp_factor(days_since_activation, seed)

    base_rate = site.enrollment_rate.sample(seed)
    effective_rate = base_rate * ramp_factor
```

**Why this is correct**:
- Ramp behavior is **explicit** (user chooses LinearRamp, ThresholdRamp, SCurve)
- Parameters are **calibratable** (ramp_duration, activation_lag, etc.)
- Different orgs can have different ramp patterns without code changes

---

### Risk 2: Implicit Enrollment Caps

❌ **VIOLATION** (Do NOT do this):
```python
def enroll_patient(site, current_time):
    # WRONG: Magic cap on enrollment
    if site.current_enrolled >= site.max_capacity * 0.8:  # Why 0.8?
        enrollment_rate *= 0.5  # Why 0.5? Why this formula?
```

**Problems**:
- **0.8**: Hardcoded threshold (assumption)
- **0.5**: Hardcoded slowdown factor (assumption)
- **Linear formula**: Why multiply by 0.5, not use sigmoid or step function?

✅ **CORRECT** (Explicit capacity response):
```python
class CapacityResponseCurve(ABC):
    """Defines how enrollment rate responds to capacity pressure."""

    @abstractmethod
    def get_rate_multiplier(self, utilization_ratio: float, seed: int) -> float:
        """
        Args:
            utilization_ratio: current_enrolled / max_capacity (0.0 to 1.0)
        Returns:
            rate_multiplier: Adjustment to enrollment rate
        """
        pass

class LinearCapacityResponse(CapacityResponseCurve):
    """Rate decreases linearly as capacity fills."""

    def __init__(self, threshold: float = 0.8, min_rate_factor: float = 0.5):
        self.threshold = threshold
        self.min_rate_factor = min_rate_factor

    def get_rate_multiplier(self, utilization_ratio: float, seed: int) -> float:
        if utilization_ratio < self.threshold:
            return 1.0  # Full rate
        else:
            # Linear decrease from 1.0 at threshold to min_rate_factor at 1.0
            slope = (self.min_rate_factor - 1.0) / (1.0 - self.threshold)
            return 1.0 + slope * (utilization_ratio - self.threshold)

class NoCapacityResponse(CapacityResponseCurve):
    """Enrollment rate unaffected by capacity (hard cutoff at max_capacity)."""

    def get_rate_multiplier(self, utilization_ratio: float, seed: int) -> float:
        return 1.0 if utilization_ratio < 1.0 else 0.0
```

---

### Risk 3: Fixed Inter-Enrollment Times

❌ **VIOLATION** (Do NOT do this):
```python
def schedule_next_enrollment(site, current_time):
    # WRONG: Fixed inter-enrollment time formula
    mean_days_per_patient = 1.0 / site.enrollment_rate.sample(seed)
    next_enrollment_time = current_time + mean_days_per_patient  # Deterministic!
```

**Problems**:
- **Deterministic timing**: Real enrollment has variability
- **Simple inversion**: Assumes exponential inter-arrival times (hidden assumption)

✅ **CORRECT** (Explicit inter-enrollment distribution):
```python
from seleensim.distributions import Distribution

class InterEnrollmentTimeModel(ABC):
    """Defines distribution of time between enrollments."""

    @abstractmethod
    def sample_next_enrollment_time(
        self,
        base_rate: float,
        days_since_activation: float,
        seed: int
    ) -> float:
        """
        Sample time until next enrollment.

        Args:
            base_rate: From site.enrollment_rate
            days_since_activation: For ramp curves
            seed: For determinism

        Returns:
            days_until_next_enrollment
        """
        pass

class ExponentialInterEnrollmentModel(InterEnrollmentTimeModel):
    """Poisson process: exponential inter-arrival times."""

    def sample_next_enrollment_time(self, base_rate, days_since_activation, seed):
        import numpy as np
        rng = np.random.default_rng(seed)
        # Exponential distribution with rate parameter
        return rng.exponential(scale=1.0 / base_rate)

class GammaInterEnrollmentModel(InterEnrollmentTimeModel):
    """Gamma-distributed inter-arrival times (more flexible)."""

    def __init__(self, shape: float = 2.0):
        self.shape = shape

    def sample_next_enrollment_time(self, base_rate, days_since_activation, seed):
        import numpy as np
        rng = np.random.default_rng(seed)
        scale = 1.0 / (base_rate * self.shape)
        return rng.gamma(shape=self.shape, scale=scale)
```

**Why this matters**:
- Exponential assumes memoryless process (Poisson)
- Gamma allows "bursty" enrollment (k arrivals in clusters)
- Different orgs have different inter-enrollment patterns

---

### Risk 4: Season/Day-of-Week Effects

❌ **VIOLATION** (Do NOT do this):
```python
def adjust_for_season(current_time, base_rate):
    # WRONG: Hardcoded seasonal pattern
    day_of_year = current_time % 365
    if 335 <= day_of_year or day_of_year <= 15:  # Holiday season
        return base_rate * 0.5  # Why 0.5?
    return base_rate
```

**Problems**:
- **Holiday dates**: Vary by organization/country
- **0.5 factor**: Hardcoded slowdown
- **Step function**: Real seasonality is gradual

✅ **CORRECT** (Explicit seasonality model):
```python
class SeasonalityModel(ABC):
    """Models time-of-year effects on enrollment."""

    @abstractmethod
    def get_seasonal_multiplier(self, day_of_year: int, seed: int) -> float:
        pass

class NoSeasonality(SeasonalityModel):
    """No seasonal effects."""
    def get_seasonal_multiplier(self, day_of_year, seed):
        return 1.0

class HolidaySlowdown(SeasonalityModel):
    """Specific date ranges with reduced enrollment."""

    def __init__(self, slow_periods: List[Tuple[int, int, float]]):
        """
        Args:
            slow_periods: List of (start_day, end_day, multiplier)
                Example: [(335, 15, 0.5)] = Dec 1 - Jan 15, 50% rate
        """
        self.slow_periods = slow_periods

    def get_seasonal_multiplier(self, day_of_year, seed):
        for start, end, multiplier in self.slow_periods:
            # Handle wrap-around (Dec-Jan)
            if start > end:
                if day_of_year >= start or day_of_year <= end:
                    return multiplier
            else:
                if start <= day_of_year <= end:
                    return multiplier
        return 1.0

class SinusoidalSeasonality(SeasonalityModel):
    """Smooth sinusoidal variation."""

    def __init__(self, amplitude: float = 0.2, peak_day: int = 180):
        self.amplitude = amplitude
        self.peak_day = peak_day

    def get_seasonal_multiplier(self, day_of_year, seed):
        import math
        phase = 2 * math.pi * (day_of_year - self.peak_day) / 365
        return 1.0 + self.amplitude * math.cos(phase)
```

---

## Correct Implementation Pattern

When implementing enrollment, follow this structure:

```python
class EnrollmentConfiguration:
    """
    Container for all enrollment behavior assumptions.

    This makes ALL enrollment assumptions explicit and calibratable.
    """

    def __init__(
        self,
        ramp_curve: EnrollmentRampCurve,
        capacity_response: CapacityResponseCurve,
        inter_enrollment_model: InterEnrollmentTimeModel,
        seasonality: SeasonalityModel = NoSeasonality()
    ):
        self.ramp_curve = ramp_curve
        self.capacity_response = capacity_response
        self.inter_enrollment_model = inter_enrollment_model
        self.seasonality = seasonality

def generate_enrollment_events(
    site: Site,
    site_activation_time: float,
    current_time: float,
    current_enrolled: int,
    config: EnrollmentConfiguration,
    seed: int
) -> List[Event]:
    """
    Generate enrollment events for site.

    ALL behavior controlled by config, NO hardcoded assumptions.
    """
    events = []

    # Apply ramp curve
    days_since_activation = current_time - site_activation_time
    ramp_factor = config.ramp_curve.get_ramp_factor(days_since_activation, seed)

    # Apply capacity pressure
    if site.max_capacity:
        utilization = current_enrolled / site.max_capacity
        capacity_factor = config.capacity_response.get_rate_multiplier(utilization, seed)
    else:
        capacity_factor = 1.0

    # Apply seasonality
    day_of_year = int(current_time % 365)
    seasonal_factor = config.seasonality.get_seasonal_multiplier(day_of_year, seed)

    # Compute effective rate
    base_rate = site.enrollment_rate.sample(seed)
    effective_rate = base_rate * ramp_factor * capacity_factor * seasonal_factor

    # Sample inter-enrollment time
    time_to_next = config.inter_enrollment_model.sample_next_enrollment_time(
        effective_rate, days_since_activation, seed
    )

    # Create enrollment event
    enrollment_event = Event(
        event_id=f"enrollment_{site.site_id}_{current_enrolled + 1}",
        event_type="patient_enrollment",
        entity_id=site.site_id,
        time=current_time + time_to_next,
        metadata={"patient_number": current_enrolled + 1}
    )
    events.append(enrollment_event)

    return events
```

**Why this is correct**:
- ALL assumptions in `EnrollmentConfiguration`
- NO magic numbers in logic
- User controls ramp, capacity response, timing, seasonality
- Calibratable without code changes

---

## Usage Example

```python
# Conservative organization (slow, predictable ramp)
conservative_config = EnrollmentConfiguration(
    ramp_curve=LinearRampCurve(ramp_duration=60, max_factor=1.0),
    capacity_response=LinearCapacityResponse(threshold=0.7, min_rate_factor=0.3),
    inter_enrollment_model=ExponentialInterEnrollmentModel(),
    seasonality=NoSeasonality()
)

# Aggressive organization (fast ramp, holiday impacts)
aggressive_config = EnrollmentConfiguration(
    ramp_curve=ThresholdRampCurve(activation_lag=14),  # Instant ramp after 2 weeks
    capacity_response=NoCapacityResponse(),  # No slowdown until hard cap
    inter_enrollment_model=GammaInterEnrollmentModel(shape=1.5),  # Bursty
    seasonality=HolidaySlowdown([(335, 15, 0.4)])  # Dec-Jan 40% rate
)

# After calibration with SCRI data
scri_config = EnrollmentConfiguration(
    ramp_curve=SCurveRampCurve(midpoint=45, steepness=0.1),  # Data-fitted S-curve
    capacity_response=LinearCapacityResponse(threshold=0.85, min_rate_factor=0.6),
    inter_enrollment_model=ExponentialInterEnrollmentModel(),  # Poisson validated
    seasonality=SinusoidalSeasonality(amplitude=0.15, peak_day=120)  # May peak
)

# Run simulations
results_conservative = engine.run(trial, enrollment_config=conservative_config)
results_aggressive = engine.run(trial, enrollment_config=aggressive_config)
results_scri = engine.run(trial, enrollment_config=scri_config)
```

---

## Checklist for Implementation

Before implementing enrollment logic, ensure:

### Architecture
- [ ] **No magic numbers** in enrollment logic
- [ ] **Ramp behavior** is `EnrollmentRampCurve` object, not hardcoded
- [ ] **Capacity response** is `CapacityResponseCurve` object, not formula
- [ ] **Inter-enrollment timing** is distribution-based, not deterministic
- [ ] **Seasonality** is `SeasonalityModel` object, not conditional

### The Ilana Law
- [ ] Apply to every numeric literal: "Could this be different for another org?"
- [ ] If YES: Extract to parameter/curve/distribution
- [ ] If NO: Document why it's structural

### Testing
- [ ] Add tests to `test_calibration_readiness.py` for enrollment
- [ ] Test: No hardcoded ramp durations
- [ ] Test: No hardcoded capacity thresholds
- [ ] Test: No hardcoded seasonal adjustments
- [ ] Test: Enrollment config accepts behavior objects, not literals

### Documentation
- [ ] Document all `EnrollmentConfiguration` parameters
- [ ] Explain what each curve/model controls
- [ ] Provide calibration guidance
- [ ] Show examples of different organizational patterns

---

## Summary

### Current Status
✅ **SAFE** - Enrollment not yet implemented, no violations present

### When Implementing
⚠️ **HIGH RISK** - Enrollment has many hidden assumption opportunities:
1. Ramp curves (linear vs threshold vs S-curve)
2. Capacity pressure (how enrollment slows near capacity)
3. Inter-enrollment timing (exponential vs gamma vs other)
4. Seasonality (holiday effects, day-of-week)

### The Pattern
**Before**: Hidden assumptions → Hard to calibrate
```python
ramp_factor = min(1.0, days / 30)  # Hidden: 30 days, linear, cap at 1.0
```

**After**: Explicit assumptions → Easy to calibrate
```python
ramp_factor = ramp_curve.get_ramp_factor(days, seed)  # Explicit behavior object
```

### The Rule
> **"Could this number be different for a different organization?"**
>
> **YES** → Parameter/curve/distribution
> **NO** → Hardcode (but document why it's structural)

---

## Next Audit Targets

After enrollment is implemented correctly, audit:
1. **Dropout logic** - When/how do patients drop out?
2. **Site closeout** - How do sites wind down enrollment?
3. **Protocol amendments** - How do mid-trial changes affect behavior?
4. **Data monitoring** - How do interim analyses affect trial continuation?

Each of these has hidden assumption risks. Apply The Ilana Law to each.

---

## References

- `docs/ARCHITECTURAL_PRINCIPLES.md` - The Ilana Law and core principles
- `docs/ARCHITECTURAL_REVIEW_FINDINGS.md` - Budget constraint violation analysis
- `constraint_fix_v2_stochastic.py` - Example of correct curve abstraction
- `tests/test_calibration_readiness.py` - Automated architectural tests
