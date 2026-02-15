"""
Unit tests for distribution framework.

Focus areas:
1. Determinism: Same seed produces same sample
2. Bounds validation: Samples respect bounds, invalid bounds rejected
3. Parameter validation: Invalid parameters fail at construction
4. Serialization: Round-trip to_dict/from_dict preserves behavior
5. Statistical properties: Mean and percentiles are reasonable
"""

import pytest
import json
from seleensim.distributions import (
    Distribution, Triangular, LogNormal, Gamma, Bernoulli, from_dict
)


class TestDeterminism:
    """Test that sampling is deterministic given a seed."""

    def test_triangular_deterministic(self):
        dist = Triangular(low=10, mode=30, high=60)
        sample1 = dist.sample(seed=42)
        sample2 = dist.sample(seed=42)
        assert sample1 == sample2, "Same seed must produce same sample"

    def test_lognormal_deterministic(self):
        dist = LogNormal(mean=50, cv=0.3)
        sample1 = dist.sample(seed=123)
        sample2 = dist.sample(seed=123)
        assert sample1 == sample2

    def test_gamma_deterministic(self):
        dist = Gamma(shape=2, scale=5)
        sample1 = dist.sample(seed=999)
        sample2 = dist.sample(seed=999)
        assert sample1 == sample2

    def test_bernoulli_deterministic(self):
        dist = Bernoulli(p=0.7)
        sample1 = dist.sample(seed=1)
        sample2 = dist.sample(seed=1)
        assert sample1 == sample2

    def test_different_seeds_produce_different_samples(self):
        """Different seeds should generally produce different samples."""
        dist = Triangular(low=10, mode=30, high=60)
        samples = [dist.sample(seed=i) for i in range(10)]
        # At least some should be different
        assert len(set(samples)) > 1, "Different seeds should produce varied samples"


class TestBoundsValidation:
    """Test bounds enforcement and validation."""

    def test_triangular_respects_bounds(self):
        dist = Triangular(low=10, mode=30, high=60, bounds=(20, 50))
        samples = [dist.sample(seed=i) for i in range(100)]
        assert all(20 <= s <= 50 for s in samples), "All samples must respect bounds"

    def test_lognormal_respects_bounds(self):
        dist = LogNormal(mean=50, cv=0.3, bounds=(30, 70))
        samples = [dist.sample(seed=i) for i in range(100)]
        assert all(30 <= s <= 70 for s in samples)

    def test_gamma_respects_bounds(self):
        dist = Gamma(shape=2, scale=5, bounds=(5, 15))
        samples = [dist.sample(seed=i) for i in range(100)]
        assert all(5 <= s <= 15 for s in samples)

    def test_invalid_bounds_rejected(self):
        with pytest.raises(ValueError, match="min must be < max"):
            Triangular(low=10, mode=30, high=60, bounds=(50, 20))

    def test_bounds_accept_list_or_tuple(self):
        """Bounds can be provided as list or tuple."""
        dist1 = Triangular(low=10, mode=30, high=60, bounds=(20, 50))
        dist2 = Triangular(low=10, mode=30, high=60, bounds=[20, 50])
        # Both should work and produce valid samples
        assert 20 <= dist1.sample(seed=42) <= 50
        assert 20 <= dist2.sample(seed=42) <= 50

    def test_tight_bounds_raise_error(self):
        """Bounds that are impossible to satisfy should raise RuntimeError."""
        # Triangular(10, 30, 60) with bounds (0, 5) - impossible
        dist = Triangular(low=10, mode=30, high=60, bounds=(0, 5))
        with pytest.raises(RuntimeError, match="Could not generate sample within bounds"):
            dist.sample(seed=42)

    def test_bernoulli_ignores_bounds(self):
        """Bernoulli should not support bounds (always 0 or 1)."""
        dist = Bernoulli(p=0.5)
        assert dist.bounds is None


class TestParameterValidation:
    """Test that invalid parameters are rejected at construction."""

    def test_triangular_requires_low_lt_mode_lt_high(self):
        with pytest.raises(ValueError, match="low < mode < high"):
            Triangular(low=30, mode=30, high=60)

        with pytest.raises(ValueError, match="low < mode < high"):
            Triangular(low=10, mode=70, high=60)

    def test_lognormal_requires_positive_mean(self):
        with pytest.raises(ValueError, match="mean must be > 0"):
            LogNormal(mean=-10, cv=0.3)

        with pytest.raises(ValueError, match="mean must be > 0"):
            LogNormal(mean=0, cv=0.3)

    def test_lognormal_requires_positive_cv(self):
        with pytest.raises(ValueError, match="cv must be > 0"):
            LogNormal(mean=50, cv=-0.1)

        with pytest.raises(ValueError, match="cv must be > 0"):
            LogNormal(mean=50, cv=0)

    def test_gamma_requires_positive_shape(self):
        with pytest.raises(ValueError, match="shape must be > 0"):
            Gamma(shape=-2, scale=5)

    def test_gamma_requires_positive_scale(self):
        with pytest.raises(ValueError, match="scale must be > 0"):
            Gamma(shape=2, scale=0)

    def test_bernoulli_requires_p_in_0_1(self):
        with pytest.raises(ValueError, match="p must be in"):
            Bernoulli(p=-0.1)

        with pytest.raises(ValueError, match="p must be in"):
            Bernoulli(p=1.5)

    def test_percentile_validates_range(self):
        dist = Triangular(low=10, mode=30, high=60)
        with pytest.raises(ValueError, match="percentile must be in"):
            dist.percentile(-10)

        with pytest.raises(ValueError, match="percentile must be in"):
            dist.percentile(150)


class TestSerialization:
    """Test JSON serialization round-trip."""

    def test_triangular_serialization(self):
        dist = Triangular(low=10, mode=30, high=60, bounds=(15, 55))
        data = dist.to_dict()

        assert data["type"] == "Triangular"
        assert data["params"]["low"] == 10
        assert data["params"]["mode"] == 30
        assert data["params"]["high"] == 60
        assert data["bounds"] == (15, 55)

        # Round-trip
        reconstructed = from_dict(data)
        assert isinstance(reconstructed, Triangular)
        assert reconstructed.sample(seed=42) == dist.sample(seed=42)

    def test_lognormal_serialization(self):
        dist = LogNormal(mean=50, cv=0.3, bounds=(20, 100))
        data = dist.to_dict()

        assert data["type"] == "LogNormal"
        assert data["params"]["mean"] == 50
        assert data["params"]["cv"] == 0.3
        assert data["bounds"] == (20, 100)

        reconstructed = from_dict(data)
        assert isinstance(reconstructed, LogNormal)
        assert reconstructed.sample(seed=99) == dist.sample(seed=99)

    def test_gamma_serialization(self):
        dist = Gamma(shape=2, scale=5)
        data = dist.to_dict()

        assert data["type"] == "Gamma"
        assert data["params"]["shape"] == 2
        assert data["params"]["scale"] == 5
        assert data["bounds"] is None

        reconstructed = from_dict(data)
        assert isinstance(reconstructed, Gamma)
        assert reconstructed.sample(seed=777) == dist.sample(seed=777)

    def test_bernoulli_serialization(self):
        dist = Bernoulli(p=0.7)
        data = dist.to_dict()

        assert data["type"] == "Bernoulli"
        assert data["params"]["p"] == 0.7
        assert data["bounds"] is None

        reconstructed = from_dict(data)
        assert isinstance(reconstructed, Bernoulli)
        assert reconstructed.sample(seed=1) == dist.sample(seed=1)

    def test_serialization_is_json_compatible(self):
        """Ensure to_dict output can be JSON serialized."""
        dist = Triangular(low=10, mode=30, high=60)
        data = dist.to_dict()
        json_str = json.dumps(data)
        loaded = json.loads(json_str)
        reconstructed = from_dict(loaded)
        assert reconstructed.sample(seed=42) == dist.sample(seed=42)

    def test_from_dict_unknown_type(self):
        with pytest.raises(ValueError, match="Unknown distribution type"):
            from_dict({"type": "Weibull", "params": {}, "bounds": None})


class TestStatisticalProperties:
    """Test that mean and percentiles are reasonable."""

    def test_triangular_mean(self):
        dist = Triangular(low=10, mode=30, high=60)
        expected_mean = (10 + 30 + 60) / 3
        assert abs(dist.mean() - expected_mean) < 1e-6

    def test_triangular_percentiles(self):
        dist = Triangular(low=10, mode=30, high=60)
        p0 = dist.percentile(0)
        p50 = dist.percentile(50)
        p100 = dist.percentile(100)

        assert 10 <= p0 <= 11, "0th percentile should be near low"
        assert 20 <= p50 <= 40, "50th percentile should be central"
        assert 59 <= p100 <= 60, "100th percentile should be near high"

    def test_lognormal_mean(self):
        dist = LogNormal(mean=50, cv=0.3)
        assert abs(dist.mean() - 50) < 1e-6

    def test_lognormal_percentiles_ordered(self):
        dist = LogNormal(mean=50, cv=0.3)
        p25 = dist.percentile(25)
        p50 = dist.percentile(50)
        p75 = dist.percentile(75)

        assert p25 < p50 < p75, "Percentiles should be monotonically increasing"
        assert p25 > 0, "LogNormal is positive"

    def test_gamma_mean(self):
        dist = Gamma(shape=2, scale=5)
        expected_mean = 2 * 5
        assert abs(dist.mean() - expected_mean) < 1e-6

    def test_gamma_percentiles_ordered(self):
        dist = Gamma(shape=2, scale=5)
        p10 = dist.percentile(10)
        p50 = dist.percentile(50)
        p90 = dist.percentile(90)

        assert p10 < p50 < p90
        assert p10 > 0, "Gamma is positive"

    def test_bernoulli_mean(self):
        dist = Bernoulli(p=0.7)
        assert abs(dist.mean() - 0.7) < 1e-6

    def test_bernoulli_percentiles(self):
        dist = Bernoulli(p=0.7)
        # p=0.7 means 70% chance of 1, 30% chance of 0
        # Percentile should return 0 for p <= 30, and 1 for p > 30
        assert dist.percentile(0) == 0
        assert dist.percentile(29) == 0
        assert dist.percentile(30) == 0
        assert dist.percentile(31) == 1
        assert dist.percentile(50) == 1
        assert dist.percentile(100) == 1

    def test_samples_approximate_mean(self):
        """For large samples, empirical mean should approximate theoretical mean."""
        dist = Triangular(low=10, mode=30, high=60)
        samples = [dist.sample(seed=i) for i in range(1000)]
        empirical_mean = sum(samples) / len(samples)
        theoretical_mean = dist.mean()

        # Allow 10% tolerance given finite samples
        assert abs(empirical_mean - theoretical_mean) / theoretical_mean < 0.1


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_bernoulli_deterministic_p_equals_0(self):
        dist = Bernoulli(p=0.0)
        samples = [dist.sample(seed=i) for i in range(10)]
        assert all(s == 0 for s in samples), "p=0 should always return 0"

    def test_bernoulli_deterministic_p_equals_1(self):
        dist = Bernoulli(p=1.0)
        samples = [dist.sample(seed=i) for i in range(10)]
        assert all(s == 1 for s in samples), "p=1 should always return 1"

    def test_very_tight_triangular(self):
        """Triangular with mode very close to boundaries."""
        dist = Triangular(low=10, mode=10.1, high=10.2)
        samples = [dist.sample(seed=i) for i in range(50)]
        assert all(10 <= s <= 10.2 for s in samples)

    def test_lognormal_low_cv(self):
        """LogNormal with very low CV (nearly deterministic)."""
        dist = LogNormal(mean=100, cv=0.01)
        samples = [dist.sample(seed=i) for i in range(50)]
        empirical_mean = sum(samples) / len(samples)
        assert abs(empirical_mean - 100) / 100 < 0.1, "Low CV should have tight distribution"

    def test_gamma_shape_1_is_exponential(self):
        """Gamma with shape=1 is equivalent to exponential distribution."""
        dist = Gamma(shape=1, scale=5)
        # Mean of exponential is scale
        assert abs(dist.mean() - 5) < 1e-6
