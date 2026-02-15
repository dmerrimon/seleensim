"""
Probability distribution framework for simulation engine.

Design principles:
- Stateless sampling with explicit seeds for reproducibility
- Intuitive, domain-agnostic parameterizations
- Serializable to JSON for calibration workflows
- No fitted state or hidden assumptions
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import numpy as np
from scipy import stats


class Distribution(ABC):
    """
    Base interface for probability distributions.

    All distributions must support:
    - Reproducible sampling via explicit seed
    - Summary statistics (mean, percentiles)
    - JSON serialization
    - Optional bounds validation
    """

    def __init__(self, bounds: Optional[tuple[float, float]] = None):
        """
        Initialize distribution with optional bounds.

        Args:
            bounds: Optional (min, max) tuple to constrain samples.
                   Enforced via rejection sampling.

        Raises:
            ValueError: If bounds are invalid (min >= max).
        """
        if bounds is not None:
            if len(bounds) != 2:
                raise ValueError(f"bounds must be (min, max), got {bounds}")
            if bounds[0] >= bounds[1]:
                raise ValueError(f"bounds min must be < max, got {bounds}")
        self.bounds = bounds

    @abstractmethod
    def sample(self, seed: int) -> float:
        """
        Generate a single sample.

        Args:
            seed: Random seed for reproducibility.

        Returns:
            A single sampled value, respecting bounds if set.
        """
        pass

    @abstractmethod
    def mean(self) -> float:
        """Return the expected value of the distribution."""
        pass

    @abstractmethod
    def percentile(self, p: float) -> float:
        """
        Return the p-th percentile.

        Args:
            p: Percentile in [0, 100].

        Returns:
            Value at the p-th percentile.

        Raises:
            ValueError: If p not in [0, 100].
        """
        if not 0 <= p <= 100:
            raise ValueError(f"percentile must be in [0, 100], got {p}")

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize distribution to dict for JSON export.

        Returns:
            Dict with 'type', 'params', and 'bounds' keys.
        """
        pass

    def _apply_bounds(self, rng: np.random.Generator, sample_fn, max_attempts: int = 1000) -> float:
        """
        Apply bounds via rejection sampling.

        Args:
            rng: NumPy random generator.
            sample_fn: Callable that returns a sample using rng.
            max_attempts: Maximum rejection sampling attempts.

        Returns:
            Sample within bounds.

        Raises:
            RuntimeError: If bounds cannot be satisfied after max_attempts.
        """
        if self.bounds is None:
            return sample_fn()

        min_val, max_val = self.bounds
        for _ in range(max_attempts):
            value = sample_fn()
            if min_val <= value <= max_val:
                return value

        raise RuntimeError(
            f"Could not generate sample within bounds {self.bounds} "
            f"after {max_attempts} attempts. Bounds may be too tight."
        )


class Triangular(Distribution):
    """
    Triangular distribution for expert elicitation.

    Parameterized by (low, mode, high) representing:
    - low: Pessimistic scenario
    - mode: Most likely value
    - high: Optimistic scenario

    Common use: When experts provide three-point estimates.
    """

    def __init__(self, low: float, mode: float, high: float,
                 bounds: Optional[tuple[float, float]] = None):
        """
        Initialize triangular distribution.

        Args:
            low: Minimum value (pessimistic).
            mode: Most likely value (peak).
            high: Maximum value (optimistic).
            bounds: Optional additional bounds enforcement.

        Raises:
            ValueError: If low >= mode >= high or parameters invalid.
        """
        super().__init__(bounds)

        if not (low < mode < high):
            raise ValueError(f"Require low < mode < high, got low={low}, mode={mode}, high={high}")

        self.low = low
        self.mode = mode
        self.high = high
        self._dist = stats.triang(
            c=(mode - low) / (high - low),
            loc=low,
            scale=high - low
        )

    def sample(self, seed: int) -> float:
        rng = np.random.default_rng(seed)
        return self._apply_bounds(rng, lambda: self._dist.rvs(random_state=rng))

    def mean(self) -> float:
        return (self.low + self.mode + self.high) / 3

    def percentile(self, p: float) -> float:
        super().percentile(p)  # Validate p
        return self._dist.ppf(p / 100)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "Triangular",
            "params": {
                "low": self.low,
                "mode": self.mode,
                "high": self.high
            },
            "bounds": self.bounds
        }


class LogNormal(Distribution):
    """
    LogNormal distribution for right-skewed positive quantities.

    Parameterized by (mean, cv) where:
    - mean: Expected value in original scale
    - cv: Coefficient of variation (std/mean)

    Common use: Durations, rates that cannot be negative and have long tails.
    """

    def __init__(self, mean: float, cv: float,
                 bounds: Optional[tuple[float, float]] = None):
        """
        Initialize log-normal distribution.

        Args:
            mean: Expected value (must be > 0).
            cv: Coefficient of variation (std/mean, must be > 0).
            bounds: Optional bounds enforcement.

        Raises:
            ValueError: If mean <= 0 or cv <= 0.
        """
        super().__init__(bounds)

        if mean <= 0:
            raise ValueError(f"mean must be > 0, got {mean}")
        if cv <= 0:
            raise ValueError(f"cv must be > 0, got {cv}")

        self.mean_val = mean
        self.cv = cv

        # Convert (mean, cv) to underlying (mu, sigma) parameters
        variance = (cv * mean) ** 2
        self.sigma = np.sqrt(np.log(1 + variance / mean**2))
        self.mu = np.log(mean) - 0.5 * self.sigma**2

        self._dist = stats.lognorm(s=self.sigma, scale=np.exp(self.mu))

    def sample(self, seed: int) -> float:
        rng = np.random.default_rng(seed)
        return self._apply_bounds(rng, lambda: self._dist.rvs(random_state=rng))

    def mean(self) -> float:
        return self.mean_val

    def percentile(self, p: float) -> float:
        super().percentile(p)  # Validate p
        return self._dist.ppf(p / 100)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "LogNormal",
            "params": {
                "mean": self.mean_val,
                "cv": self.cv
            },
            "bounds": self.bounds
        }


class Gamma(Distribution):
    """
    Gamma distribution for flexible positive quantities.

    Parameterized by (shape, scale):
    - shape (α): Controls skewness
    - scale (θ): Controls spread

    Mean = shape * scale
    Variance = shape * scale^2

    Common use: Rates, waiting times, counts.
    """

    def __init__(self, shape: float, scale: float,
                 bounds: Optional[tuple[float, float]] = None):
        """
        Initialize gamma distribution.

        Args:
            shape: Shape parameter (α, must be > 0).
            scale: Scale parameter (θ, must be > 0).
            bounds: Optional bounds enforcement.

        Raises:
            ValueError: If shape <= 0 or scale <= 0.
        """
        super().__init__(bounds)

        if shape <= 0:
            raise ValueError(f"shape must be > 0, got {shape}")
        if scale <= 0:
            raise ValueError(f"scale must be > 0, got {scale}")

        self.shape = shape
        self.scale = scale
        self._dist = stats.gamma(a=shape, scale=scale)

    def sample(self, seed: int) -> float:
        rng = np.random.default_rng(seed)
        return self._apply_bounds(rng, lambda: self._dist.rvs(random_state=rng))

    def mean(self) -> float:
        return self.shape * self.scale

    def percentile(self, p: float) -> float:
        super().percentile(p)  # Validate p
        return self._dist.ppf(p / 100)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "Gamma",
            "params": {
                "shape": self.shape,
                "scale": self.scale
            },
            "bounds": self.bounds
        }


class Bernoulli(Distribution):
    """
    Bernoulli distribution for binary events.

    Parameterized by (p):
    - p: Probability of success (returns 1)
    - 1-p: Probability of failure (returns 0)

    Common use: Yes/no outcomes, event occurrence.
    """

    def __init__(self, p: float):
        """
        Initialize Bernoulli distribution.

        Args:
            p: Probability of success in [0, 1].

        Raises:
            ValueError: If p not in [0, 1].

        Note:
            Bounds are not supported for Bernoulli (output is always 0 or 1).
        """
        super().__init__(bounds=None)

        if not 0 <= p <= 1:
            raise ValueError(f"p must be in [0, 1], got {p}")

        self.p = p
        self._dist = stats.bernoulli(p=p)

    def sample(self, seed: int) -> float:
        rng = np.random.default_rng(seed)
        return float(self._dist.rvs(random_state=rng))

    def mean(self) -> float:
        return self.p

    def percentile(self, p: float) -> float:
        super().percentile(p)  # Validate p
        # For Bernoulli: 0 if p <= (1-self.p)*100, else 1
        return 0.0 if p <= (1 - self.p) * 100 else 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "Bernoulli",
            "params": {
                "p": self.p
            },
            "bounds": None
        }


def from_dict(data: Dict[str, Any]) -> Distribution:
    """
    Deserialize distribution from dict.

    Args:
        data: Dict with 'type', 'params', and 'bounds' keys.

    Returns:
        Distribution instance.

    Raises:
        ValueError: If type is unknown or params are invalid.
    """
    dist_type = data.get("type")
    params = data.get("params", {})
    bounds = data.get("bounds")

    if dist_type == "Triangular":
        return Triangular(
            low=params["low"],
            mode=params["mode"],
            high=params["high"],
            bounds=bounds
        )
    elif dist_type == "LogNormal":
        return LogNormal(
            mean=params["mean"],
            cv=params["cv"],
            bounds=bounds
        )
    elif dist_type == "Gamma":
        return Gamma(
            shape=params["shape"],
            scale=params["scale"],
            bounds=bounds
        )
    elif dist_type == "Bernoulli":
        return Bernoulli(p=params["p"])
    else:
        raise ValueError(f"Unknown distribution type: {dist_type}")
