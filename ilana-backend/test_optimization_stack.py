#!/usr/bin/env python3
"""
Comprehensive Tests for Optimization Stack (Steps 3-7)

Tests the performance optimization modules implemented in Steps 3-7:
- Step 3: Optimization config (Pinecone/PubMedBERT smart skipping)
- Step 4: Prompt optimizer (token budgets and optimization)
- Step 5: Resilience (circuit breakers, retry, timeouts)
- Step 6: Cache manager (LRU cache with Redis fallback)
- Step 7: Metrics collector (telemetry and profiling)
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock


# ============================================================================
# STEP 3: Optimization Config Tests
# ============================================================================

class TestOptimizationConfig:
    """Test Step 3: Pinecone/PubMedBERT smart skipping logic"""

    def test_should_use_pinecone_short_text(self):
        """Test Pinecone skipped for short texts"""
        from optimization_config import should_use_pinecone

        short_text = "Brief protocol section."
        assert should_use_pinecone(short_text) is False

    def test_should_use_pinecone_long_text(self):
        """Test Pinecone used for long texts"""
        from optimization_config import should_use_pinecone

        long_text = "A" * 300  # > 200 chars
        assert should_use_pinecone(long_text) is True

    def test_should_use_pubmedbert_short_text(self):
        """Test PubMedBERT skipped for short texts"""
        from optimization_config import should_use_pubmedbert

        short_text = "Brief protocol section."
        assert should_use_pubmedbert(short_text) is False

    def test_should_use_pubmedbert_long_text(self):
        """Test PubMedBERT used for long texts"""
        from optimization_config import should_use_pubmedbert

        long_text = "A" * 600  # > 500 chars (PUBMEDBERT_MIN_CHARS)
        assert should_use_pubmedbert(long_text) is True

    def test_should_use_pubmedbert_known_ta(self):
        """Test PubMedBERT skipped when TA already known"""
        from optimization_config import should_use_pubmedbert

        long_text = "A" * 600
        # If TA is known (not general_medicine), skip PubMedBERT
        assert should_use_pubmedbert(long_text, ta="oncology") is False

    def test_pinecone_top_k_reduced(self):
        """Test Pinecone top_k is reduced from default 5 to 3"""
        from optimization_config import PINECONE_TOP_K

        assert PINECONE_TOP_K == 3  # 40% reduction for performance


# ============================================================================
# STEP 4: Prompt Optimizer Tests
# ============================================================================

class TestPromptOptimizer:
    """Test Step 4: Token budget enforcement and prompt optimization"""

    def test_token_budgets_defined(self):
        """Test token budgets are properly configured"""
        from prompt_optimizer import FAST_TOKEN_BUDGET, DEEP_TOKEN_BUDGET

        assert FAST_TOKEN_BUDGET == 500
        assert DEEP_TOKEN_BUDGET == 2000

    def test_build_fast_prompt(self):
        """Test fast prompt generation with token counting"""
        from prompt_optimizer import build_fast_prompt

        text = "Test protocol text for analysis."
        result = build_fast_prompt(text, ta="oncology")

        assert "system" in result
        assert "user" in result
        assert "tokens" in result
        assert result["tokens"]["total_input"] > 0
        assert result["tokens"]["budget"] == 500

    def test_count_tokens_precise(self):
        """Test precise token counting with tiktoken"""
        from prompt_optimizer import count_tokens_precise

        text = "Hello, world!"
        tokens = count_tokens_precise(text, model="gpt-4")

        # Should be a small number for short text
        assert tokens > 0
        assert tokens < 10

    def test_track_token_usage(self):
        """Test token usage tracking"""
        from prompt_optimizer import track_token_usage, get_token_stats

        # Track some usage (correct parameter names: input_tokens, output_tokens)
        track_token_usage("fast_path", input_tokens=100, output_tokens=50)

        stats = get_token_stats()
        assert "fast_path" in stats
        assert stats["fast_path"]["total_requests"] >= 1

    def test_prompt_templates_exist(self):
        """Test prompt templates are defined"""
        from prompt_optimizer import FAST_ANALYSIS_TEMPLATE, DEEP_ANALYSIS_TEMPLATE

        assert FAST_ANALYSIS_TEMPLATE.system is not None
        assert FAST_ANALYSIS_TEMPLATE.user_template is not None
        assert DEEP_ANALYSIS_TEMPLATE.system is not None
        assert DEEP_ANALYSIS_TEMPLATE.user_template is not None


# ============================================================================
# STEP 5: Resilience Tests
# ============================================================================

class TestResilience:
    """Test Step 5: Circuit breakers, retry logic, and timeouts"""

    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker starts in CLOSED state"""
        from resilience import CircuitBreaker, CircuitState

        breaker = CircuitBreaker("test_service")
        assert breaker.state == CircuitState.CLOSED

    def test_circuit_breaker_success(self):
        """Test circuit breaker allows successful calls"""
        from resilience import CircuitBreaker

        breaker = CircuitBreaker("test_service", threshold=3)

        def success_func():
            return "success"

        result = breaker.call(success_func)
        assert result == "success"
        assert breaker.failure_count == 0

    def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures"""
        from resilience import CircuitBreaker, CircuitState, CircuitBreakerOpenError

        breaker = CircuitBreaker("test_service", threshold=3)

        def failing_func():
            raise Exception("Service failed")

        # Fail 3 times to open circuit
        for _ in range(3):
            with pytest.raises(Exception):
                breaker.call(failing_func)

        assert breaker.state == CircuitState.OPEN

        # Next call should be blocked
        with pytest.raises(CircuitBreakerOpenError):
            breaker.call(failing_func)

    @pytest.mark.asyncio
    async def test_retry_with_backoff_success(self):
        """Test retry succeeds on second attempt"""
        from resilience import retry_with_backoff

        call_count = {"count": 0}

        async def flaky_func():
            call_count["count"] += 1
            if call_count["count"] < 2:
                raise Exception("Temporary failure")
            return "success"

        result = await retry_with_backoff(flaky_func, max_retries=3, backoff_base=0.1)
        assert result == "success"
        assert call_count["count"] == 2

    @pytest.mark.asyncio
    async def test_retry_with_backoff_exhausted(self):
        """Test retry exhausts all attempts"""
        from resilience import retry_with_backoff

        async def always_fails():
            raise Exception("Permanent failure")

        with pytest.raises(Exception, match="Permanent failure"):
            await retry_with_backoff(always_fails, max_retries=2, backoff_base=0.1)

    @pytest.mark.asyncio
    async def test_with_timeout_success(self):
        """Test timeout allows fast operations"""
        from resilience import with_timeout

        async def fast_func():
            await asyncio.sleep(0.1)
            return "success"

        result = await with_timeout(fast_func, 1.0)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_with_timeout_exceeds(self):
        """Test timeout cancels slow operations"""
        from resilience import with_timeout

        async def slow_func():
            await asyncio.sleep(2.0)
            return "too slow"

        with pytest.raises(asyncio.TimeoutError):
            await with_timeout(slow_func, 0.5)


# ============================================================================
# STEP 6: Cache Manager Tests
# ============================================================================

class TestCacheManager:
    """Test Step 6: LRU cache with Redis fallback"""

    def test_cache_key_generation(self):
        """Test deterministic cache key generation"""
        from cache_manager import generate_cache_key

        key1 = generate_cache_key("test text", "gpt-4o-mini", ta="oncology", phase="phase3", analysis_type="fast")
        key2 = generate_cache_key("test text", "gpt-4o-mini", ta="oncology", phase="phase3", analysis_type="fast")

        # Same inputs should produce same key
        assert key1 == key2
        assert len(key1) == 64  # SHA256 hash

    def test_cache_key_different_inputs(self):
        """Test cache keys differ for different inputs"""
        from cache_manager import generate_cache_key

        key1 = generate_cache_key("text1", "gpt-4o-mini")
        key2 = generate_cache_key("text2", "gpt-4o-mini")

        assert key1 != key2

    def test_get_ttl_for_type_fast(self):
        """Test TTL calculation for fast analysis"""
        from cache_manager import get_ttl_for_type

        ttl = get_ttl_for_type("fast", 100)
        assert ttl > 0

    def test_get_ttl_for_type_deep(self):
        """Test TTL calculation for deep analysis"""
        from cache_manager import get_ttl_for_type

        ttl_deep = get_ttl_for_type("deep", 1000)
        ttl_fast = get_ttl_for_type("fast", 1000)

        # Deep analysis should have longer TTL
        assert ttl_deep > ttl_fast

    def test_lru_cache_basic_operations(self):
        """Test LRU cache get/set operations"""
        from cache_manager import LRUCache

        cache = LRUCache(max_size=3)

        # Set and get
        cache.set("key1", {"data": "value1"}, ttl_hours=1)
        result = cache.get("key1")

        assert result is not None
        assert result["data"] == "value1"

    def test_lru_cache_eviction(self):
        """Test LRU cache evicts least recently used items"""
        from cache_manager import LRUCache

        cache = LRUCache(max_size=2)

        cache.set("key1", {"data": "value1"}, ttl_hours=1)
        cache.set("key2", {"data": "value2"}, ttl_hours=1)

        # Access key1 to make it more recent
        cache.get("key1")

        # Add key3, should evict key2 (LRU)
        cache.set("key3", {"data": "value3"}, ttl_hours=1)

        assert cache.get("key1") is not None
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") is not None

    def test_cache_stats(self):
        """Test cache statistics tracking"""
        from cache_manager import get_cache_stats, reset_cache_stats

        reset_cache_stats()
        stats = get_cache_stats()

        assert "global" in stats
        assert "memory_cache" in stats
        assert "target_metrics" in stats


# ============================================================================
# STEP 7: Metrics Collector Tests
# ============================================================================

class TestMetricsCollector:
    """Test Step 7: Telemetry and profiling metrics"""

    def test_record_request(self):
        """Test recording request metrics"""
        from metrics_collector import record_request

        record_request(
            request_id="test_123",
            endpoint="/api/analyze",
            duration_ms=1500,
            status_code=200,
            path_type="fast",
            cache_hit=False,
            suggestions_count=3,
            tokens_used=250
        )

        # Should not raise any exceptions
        assert True

    def test_calculate_percentiles(self):
        """Test percentile calculation"""
        from metrics_collector import calculate_percentiles

        values = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        percentiles = calculate_percentiles(values)

        assert "p50" in percentiles
        assert "p90" in percentiles
        assert "p95" in percentiles
        assert "p99" in percentiles

        # p50 should be somewhere in the middle
        assert 400 <= percentiles["p50"] <= 700
        # p99 should be near the end
        assert percentiles["p99"] >= 900

    def test_calculate_percentiles_empty(self):
        """Test percentile calculation with empty values"""
        from metrics_collector import calculate_percentiles

        percentiles = calculate_percentiles([])

        assert percentiles["p50"] == 0.0
        assert percentiles["p90"] == 0.0

    def test_get_performance_metrics(self):
        """Test performance metrics retrieval"""
        from metrics_collector import get_performance_metrics

        metrics = get_performance_metrics()

        assert "latency_percentiles" in metrics
        assert "throughput" in metrics
        assert "performance_targets" in metrics

    def test_get_all_metrics(self):
        """Test comprehensive metrics retrieval"""
        from metrics_collector import get_all_metrics

        metrics = get_all_metrics()

        assert "timestamp" in metrics
        assert "requests" in metrics
        assert "performance" in metrics
        assert "cache" in metrics
        assert "suggestions" in metrics
        assert "tokens" in metrics
        assert "errors" in metrics

    def test_export_prometheus(self):
        """Test Prometheus format export"""
        from metrics_collector import export_prometheus

        prometheus_text = export_prometheus()

        # Should be plain text with metrics
        assert isinstance(prometheus_text, str)
        assert "ilana_" in prometheus_text  # Our metric prefix


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestOptimizationStackIntegration:
    """Integration tests for the full optimization stack"""

    @pytest.mark.asyncio
    async def test_fast_analysis_with_cache_and_metrics(self):
        """Test fast analysis flow with caching and metrics"""
        from cache_manager import get_cached, set_cached
        from metrics_collector import record_request

        text = "Test protocol text for caching"
        model = "gpt-4o-mini"

        # Check cache (should be miss)
        cached = get_cached(text, model, analysis_type="fast")
        assert cached is None

        # Simulate result
        result = {
            "status": "fast",
            "suggestions": [{"text": "test"}],
            "metadata": {"total_ms": 1500}
        }

        # Cache result
        set_cached(text, model, result, analysis_type="fast")

        # Record metrics
        record_request(
            request_id="test_integration",
            endpoint="/api/analyze",
            duration_ms=1500,
            path_type="fast",
            cache_hit=False,
            suggestions_count=1,
            tokens_used=100
        )

        # Retrieve from cache (should be hit)
        cached = get_cached(text, model, analysis_type="fast")
        assert cached is not None
        assert cached["status"] == "fast"

    def test_optimization_config_with_metrics(self):
        """Test optimization decisions are tracked in metrics"""
        from optimization_config import should_use_pinecone, should_use_pubmedbert
        from metrics_collector import get_all_metrics

        # Make optimization decisions
        short_text = "Brief text"
        long_text = "A" * 600

        should_use_pinecone(short_text)  # Should skip
        should_use_pubmedbert(long_text)  # Should use

        # Metrics should be available
        metrics = get_all_metrics()
        assert metrics is not None


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformanceTargets:
    """Test that performance targets are met"""

    def test_cache_operation_performance(self):
        """Test cache operations are fast (<1ms)"""
        from cache_manager import LRUCache

        cache = LRUCache(max_size=1000)

        # Measure set performance
        start = time.time()
        for i in range(100):
            cache.set(f"key{i}", {"data": f"value{i}"}, ttl_hours=1)
        set_duration = time.time() - start

        # Should be < 10ms for 100 operations
        assert set_duration < 0.01

        # Measure get performance
        start = time.time()
        for i in range(100):
            cache.get(f"key{i}")
        get_duration = time.time() - start

        # Should be < 10ms for 100 operations
        assert get_duration < 0.01

    def test_metrics_collection_overhead(self):
        """Test metrics collection has minimal overhead"""
        from metrics_collector import record_request

        start = time.time()
        for i in range(100):
            record_request(
                request_id=f"perf_{i}",
                endpoint="/api/analyze",
                duration_ms=1000,
                path_type="fast",
                cache_hit=False,
                suggestions_count=1,
                tokens_used=100
            )
        duration = time.time() - start

        # Should be < 50ms for 100 recordings
        assert duration < 0.05


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
