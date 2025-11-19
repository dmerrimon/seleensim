#!/usr/bin/env python3
"""
Resilience Utilities for Step 5: Timeouts & Fallbacks

Provides circuit breakers, retry logic, and fallback chains to ensure
the system remains resilient to external service failures.

Features:
- Circuit breaker pattern (prevents cascading failures)
- Exponential backoff retry
- Timeout guards for async operations
- Fallback chains for graceful degradation
"""

import os
import time
import asyncio
import logging
import random
from typing import Callable, Any, Optional, List, TypeVar
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar('T')

# Configuration
CIRCUIT_BREAKER_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "5"))
CIRCUIT_BREAKER_TIMEOUT = int(os.getenv("CIRCUIT_BREAKER_TIMEOUT", "60"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BACKOFF_BASE = float(os.getenv("RETRY_BACKOFF_BASE", "1.0"))


class CircuitState(str, Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Blocking requests (too many failures)
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker pattern implementation

    Prevents cascading failures by "opening" the circuit after N failures,
    blocking requests for a timeout period, then allowing test requests.
    """

    def __init__(self, name: str, threshold: int = CIRCUIT_BREAKER_THRESHOLD, timeout: int = CIRCUIT_BREAKER_TIMEOUT):
        self.name = name
        self.threshold = threshold
        self.timeout = timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.opened_at: Optional[datetime] = None

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""

        # Check if circuit should transition to HALF_OPEN
        if self.state == CircuitState.OPEN:
            if self.opened_at and (datetime.utcnow() - self.opened_at).total_seconds() > self.timeout:
                logger.info(f"🔄 Circuit breaker {self.name}: OPEN → HALF_OPEN (testing recovery)")
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is OPEN")

        # Attempt the call
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure()
            raise

    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with circuit breaker protection"""

        # Check if circuit should transition to HALF_OPEN
        if self.state == CircuitState.OPEN:
            if self.opened_at and (datetime.utcnow() - self.opened_at).total_seconds() > self.timeout:
                logger.info(f"🔄 Circuit breaker {self.name}: OPEN → HALF_OPEN (testing recovery)")
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is OPEN")

        # Attempt the call
        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure()
            raise

    def _record_success(self):
        """Record successful call"""
        self.success_count += 1

        if self.state == CircuitState.HALF_OPEN:
            # Recovered! Close the circuit
            logger.info(f"✅ Circuit breaker {self.name}: HALF_OPEN → CLOSED (recovered)")
            self.state = CircuitState.CLOSED
            self.failure_count = 0

    def _record_failure(self):
        """Record failed call"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.state == CircuitState.HALF_OPEN:
            # Still failing, reopen circuit
            logger.warning(f"⚠️ Circuit breaker {self.name}: HALF_OPEN → OPEN (still failing)")
            self.state = CircuitState.OPEN
            self.opened_at = datetime.utcnow()

        elif self.failure_count >= self.threshold:
            # Too many failures, open circuit
            logger.error(f"🔴 Circuit breaker {self.name}: CLOSED → OPEN ({self.failure_count} failures)")
            self.state = CircuitState.OPEN
            self.opened_at = datetime.utcnow()

    def reset(self):
        """Manually reset circuit breaker"""
        logger.info(f"🔄 Circuit breaker {self.name}: Manual reset")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.opened_at = None

    def get_state(self) -> dict:
        """Get current circuit breaker state"""
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "threshold": self.threshold,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


# Global circuit breakers for external services
_circuit_breakers = {
    "azure_openai": CircuitBreaker("azure_openai", threshold=5, timeout=60),
    "pinecone": CircuitBreaker("pinecone", threshold=3, timeout=30),
    "pubmedbert": CircuitBreaker("pubmedbert", threshold=3, timeout=30)
}


def get_circuit_breaker(service: str) -> CircuitBreaker:
    """Get circuit breaker for service"""
    return _circuit_breakers.get(service, CircuitBreaker(service))


async def retry_with_backoff(
    func: Callable,
    *args,
    max_retries: int = MAX_RETRIES,
    backoff_base: float = RETRY_BACKOFF_BASE,
    retryable_exceptions: tuple = (Exception,),
    **kwargs
) -> Any:
    """
    Retry async function with exponential backoff

    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        backoff_base: Base delay in seconds (doubles each retry)
        retryable_exceptions: Tuple of exceptions that should trigger retry

    Returns:
        Result of function call

    Raises:
        Last exception if all retries exhausted
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except retryable_exceptions as e:
            last_exception = e

            if attempt < max_retries:
                # Calculate backoff with jitter
                delay = (backoff_base * (2 ** attempt)) + random.uniform(0, 1)
                logger.warning(f"⏱️ Retry {attempt + 1}/{max_retries} after {delay:.2f}s: {type(e).__name__}: {e}")
                await asyncio.sleep(delay)
            else:
                logger.error(f"❌ All {max_retries} retries exhausted: {type(e).__name__}: {e}")

    raise last_exception


async def with_timeout(
    func: Callable,
    timeout_seconds: float,
    *args,
    **kwargs
) -> Any:
    """
    Execute async function with timeout

    Args:
        func: Async function to execute
        timeout_seconds: Timeout in seconds

    Returns:
        Result of function call

    Raises:
        asyncio.TimeoutError if timeout exceeded
    """
    try:
        return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.error(f"⏱️ Timeout after {timeout_seconds}s: {func.__name__}")
        raise


class FallbackChain:
    """
    Execute functions in fallback chain until one succeeds

    Example:
        chain = FallbackChain()
        chain.add(call_gpt4, "primary")
        chain.add(call_gpt4_mini, "fallback")
        chain.add(get_cached_response, "emergency")
        result = await chain.execute()
    """

    def __init__(self, name: str = "unnamed"):
        self.name = name
        self.steps: List[tuple] = []  # [(func, label, args, kwargs)]

    def add(self, func: Callable, label: str, *args, **kwargs):
        """Add function to fallback chain"""
        self.steps.append((func, label, args, kwargs))
        return self

    async def execute(self) -> Any:
        """Execute fallback chain"""
        last_exception = None

        for i, (func, label, args, kwargs) in enumerate(self.steps):
            try:
                logger.info(f"🔄 FallbackChain[{self.name}]: Trying {label} ({i+1}/{len(self.steps)})")
                result = await func(*args, **kwargs)
                logger.info(f"✅ FallbackChain[{self.name}]: Success with {label}")
                return result
            except Exception as e:
                last_exception = e
                logger.warning(f"⚠️ FallbackChain[{self.name}]: {label} failed: {type(e).__name__}: {e}")
                # Continue to next fallback

        # All fallbacks failed
        logger.error(f"❌ FallbackChain[{self.name}]: All {len(self.steps)} steps failed")
        raise FallbackChainExhaustedError(f"All fallbacks exhausted for {self.name}") from last_exception


class FallbackChainExhaustedError(Exception):
    """Raised when all fallbacks in chain fail"""
    pass


def get_all_circuit_breaker_states() -> dict:
    """Get state of all circuit breakers"""
    return {
        name: breaker.get_state()
        for name, breaker in _circuit_breakers.items()
    }


def reset_all_circuit_breakers():
    """Reset all circuit breakers (for testing/recovery)"""
    for breaker in _circuit_breakers.values():
        breaker.reset()


# Log configuration on import
logger.info("🛡️ Resilience module loaded (Step 5):")
logger.info(f"   - Circuit breaker threshold: {CIRCUIT_BREAKER_THRESHOLD} failures")
logger.info(f"   - Circuit breaker timeout: {CIRCUIT_BREAKER_TIMEOUT}s")
logger.info(f"   - Max retries: {MAX_RETRIES}")
logger.info(f"   - Retry backoff base: {RETRY_BACKOFF_BASE}s")


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "get_circuit_breaker",
    "retry_with_backoff",
    "with_timeout",
    "FallbackChain",
    "FallbackChainExhaustedError",
    "get_all_circuit_breaker_states",
    "reset_all_circuit_breakers"
]
