#!/usr/bin/env python3
"""
Configuration Management for Optimization Stack (Step 9)

Centralizes all environment variables and configuration for Steps 3-7:
- Step 3: Optimization config (Pinecone/PubMedBERT)
- Step 4: Prompt optimizer (token budgets)
- Step 5: Resilience (circuit breakers, retries)
- Step 6: Cache manager (Redis, TTL)
- Step 7: Metrics collector (telemetry)

Provides validation, defaults, and runtime configuration management.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)


@dataclass
class OptimizationConfig:
    """Complete configuration for optimization stack"""

    # ============================================================================
    # STEP 3: Optimization Config (Pinecone/PubMedBERT)
    # ============================================================================

    # Pinecone vector DB settings
    pinecone_top_k: int = 3
    pinecone_min_text_length: int = 200

    # PubMedBERT settings
    pubmedbert_min_chars: int = 500

    # ============================================================================
    # STEP 4: Prompt Optimizer (Token Budgets)
    # ============================================================================

    # Token budgets for prompt optimization
    fast_token_budget: int = 500
    deep_token_budget: int = 2000

    # Model selection
    analysis_fast_model: str = "gpt-4o-mini"
    analysis_deep_model: str = "gpt-4o"

    # Timeout settings
    simple_prompt_timeout_ms: int = 10000  # 10 seconds

    # ============================================================================
    # STEP 5: Resilience (Circuit Breakers, Retries, Timeouts)
    # ============================================================================

    # Circuit breaker settings
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60  # seconds

    # Retry settings
    max_retries: int = 3
    retry_backoff_base: float = 1.0  # seconds

    # ============================================================================
    # STEP 6: Cache Manager (Redis, LRU, TTL)
    # ============================================================================

    # Redis settings
    enable_redis: bool = False
    redis_url: str = "redis://localhost:6379"

    # TTL settings (hours)
    cache_ttl_hours: int = 24
    fast_cache_ttl_hours: int = 6
    deep_cache_ttl_hours: int = 48

    # Memory cache settings
    max_memory_cache_size: int = 1000

    # ============================================================================
    # STEP 7: Metrics Collector (Telemetry & Profiling)
    # ============================================================================

    # Metrics settings
    enable_metrics: bool = True
    max_traces: int = 1000

    # ============================================================================
    # Performance Targets
    # ============================================================================

    # Target metrics for monitoring
    fast_path_target_p95_ms: int = 10000  # 10 seconds
    cache_hit_rate_target_min: float = 50.0  # 50%
    cache_hit_rate_target_max: float = 70.0  # 70%

    # Validation flags
    _validated: bool = field(default=False, repr=False)
    _validation_errors: List[str] = field(default_factory=list, repr=False)


def load_config_from_env() -> OptimizationConfig:
    """
    Load configuration from environment variables

    Returns:
        OptimizationConfig with values from environment (or defaults)
    """
    config = OptimizationConfig(
        # Step 3: Optimization Config
        pinecone_top_k=int(os.getenv("PINECONE_TOP_K", "3")),
        pinecone_min_text_length=int(os.getenv("PINECONE_MIN_TEXT_LENGTH", "200")),
        pubmedbert_min_chars=int(os.getenv("PUBMEDBERT_MIN_CHARS", "500")),

        # Step 4: Prompt Optimizer
        fast_token_budget=int(os.getenv("FAST_TOKEN_BUDGET", "500")),
        deep_token_budget=int(os.getenv("DEEP_TOKEN_BUDGET", "2000")),
        analysis_fast_model=os.getenv("ANALYSIS_FAST_MODEL", "gpt-4o-mini"),
        analysis_deep_model=os.getenv("ANALYSIS_DEEP_MODEL", "gpt-4o"),
        simple_prompt_timeout_ms=int(os.getenv("SIMPLE_PROMPT_TIMEOUT_MS", "10000")),

        # Step 5: Resilience
        circuit_breaker_threshold=int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "5")),
        circuit_breaker_timeout=int(os.getenv("CIRCUIT_BREAKER_TIMEOUT", "60")),
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
        retry_backoff_base=float(os.getenv("RETRY_BACKOFF_BASE", "1.0")),

        # Step 6: Cache Manager
        enable_redis=os.getenv("ENABLE_REDIS", "false").lower() == "true",
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
        cache_ttl_hours=int(os.getenv("CACHE_TTL_HOURS", "24")),
        fast_cache_ttl_hours=int(os.getenv("FAST_CACHE_TTL_HOURS", "6")),
        deep_cache_ttl_hours=int(os.getenv("DEEP_CACHE_TTL_HOURS", "48")),
        max_memory_cache_size=int(os.getenv("MAX_MEMORY_CACHE_SIZE", "1000")),

        # Step 7: Metrics Collector
        enable_metrics=os.getenv("ENABLE_METRICS", "true").lower() == "true",
        max_traces=int(os.getenv("MAX_TRACES", "1000")),

        # Performance Targets
        fast_path_target_p95_ms=int(os.getenv("FAST_PATH_TARGET_P95_MS", "10000")),
        cache_hit_rate_target_min=float(os.getenv("CACHE_HIT_RATE_TARGET_MIN", "50.0")),
        cache_hit_rate_target_max=float(os.getenv("CACHE_HIT_RATE_TARGET_MAX", "70.0")),
    )

    return config


def validate_config(config: OptimizationConfig) -> bool:
    """
    Validate configuration values

    Args:
        config: Configuration to validate

    Returns:
        True if valid, False otherwise (check config._validation_errors)
    """
    errors = []

    # Step 3 validation
    if config.pinecone_top_k < 1 or config.pinecone_top_k > 10:
        errors.append(f"PINECONE_TOP_K must be between 1 and 10 (got {config.pinecone_top_k})")

    if config.pubmedbert_min_chars < 0:
        errors.append(f"PUBMEDBERT_MIN_CHARS must be >= 0 (got {config.pubmedbert_min_chars})")

    # Step 4 validation
    if config.fast_token_budget < 100 or config.fast_token_budget > 2000:
        errors.append(f"FAST_TOKEN_BUDGET must be between 100 and 2000 (got {config.fast_token_budget})")

    if config.deep_token_budget < 500 or config.deep_token_budget > 8000:
        errors.append(f"DEEP_TOKEN_BUDGET must be between 500 and 8000 (got {config.deep_token_budget})")

    if config.simple_prompt_timeout_ms < 1000:
        errors.append(f"SIMPLE_PROMPT_TIMEOUT_MS must be >= 1000ms (got {config.simple_prompt_timeout_ms})")

    # Step 5 validation
    if config.circuit_breaker_threshold < 1:
        errors.append(f"CIRCUIT_BREAKER_THRESHOLD must be >= 1 (got {config.circuit_breaker_threshold})")

    if config.circuit_breaker_timeout < 10:
        errors.append(f"CIRCUIT_BREAKER_TIMEOUT must be >= 10s (got {config.circuit_breaker_timeout})")

    if config.max_retries < 0 or config.max_retries > 10:
        errors.append(f"MAX_RETRIES must be between 0 and 10 (got {config.max_retries})")

    if config.retry_backoff_base < 0.1:
        errors.append(f"RETRY_BACKOFF_BASE must be >= 0.1s (got {config.retry_backoff_base})")

    # Step 6 validation
    if config.cache_ttl_hours < 1:
        errors.append(f"CACHE_TTL_HOURS must be >= 1 (got {config.cache_ttl_hours})")

    if config.max_memory_cache_size < 10:
        errors.append(f"MAX_MEMORY_CACHE_SIZE must be >= 10 (got {config.max_memory_cache_size})")

    # Step 7 validation
    if config.max_traces < 10:
        errors.append(f"MAX_TRACES must be >= 10 (got {config.max_traces})")

    # Performance targets validation
    if config.cache_hit_rate_target_min < 0 or config.cache_hit_rate_target_min > 100:
        errors.append(f"CACHE_HIT_RATE_TARGET_MIN must be 0-100 (got {config.cache_hit_rate_target_min})")

    if config.cache_hit_rate_target_max < config.cache_hit_rate_target_min:
        errors.append(f"CACHE_HIT_RATE_TARGET_MAX must be >= TARGET_MIN")

    # Update config
    config._validation_errors = errors
    config._validated = len(errors) == 0

    if not config._validated:
        for error in errors:
            logger.error(f"Configuration validation error: {error}")

    return config._validated


def get_config_summary(config: OptimizationConfig) -> Dict[str, Any]:
    """
    Get human-readable configuration summary

    Args:
        config: Configuration to summarize

    Returns:
        Dict with organized configuration sections
    """
    return {
        "step_3_optimization": {
            "pinecone_top_k": config.pinecone_top_k,
            "pinecone_min_text_length": config.pinecone_min_text_length,
            "pubmedbert_min_chars": config.pubmedbert_min_chars,
            "description": "Smart skipping for Pinecone and PubMedBERT"
        },
        "step_4_prompts": {
            "fast_token_budget": config.fast_token_budget,
            "deep_token_budget": config.deep_token_budget,
            "fast_model": config.analysis_fast_model,
            "deep_model": config.analysis_deep_model,
            "timeout_ms": config.simple_prompt_timeout_ms,
            "description": "Token optimization and model selection"
        },
        "step_5_resilience": {
            "circuit_breaker_threshold": config.circuit_breaker_threshold,
            "circuit_breaker_timeout": config.circuit_breaker_timeout,
            "max_retries": config.max_retries,
            "retry_backoff_base": config.retry_backoff_base,
            "description": "Circuit breakers, retry logic, timeouts"
        },
        "step_6_caching": {
            "enable_redis": config.enable_redis,
            "redis_url": config.redis_url if config.enable_redis else None,
            "fast_cache_ttl_hours": config.fast_cache_ttl_hours,
            "deep_cache_ttl_hours": config.deep_cache_ttl_hours,
            "max_memory_cache_size": config.max_memory_cache_size,
            "description": "LRU cache with Redis fallback"
        },
        "step_7_metrics": {
            "enable_metrics": config.enable_metrics,
            "max_traces": config.max_traces,
            "description": "Telemetry and performance profiling"
        },
        "performance_targets": {
            "fast_path_p95_ms": config.fast_path_target_p95_ms,
            "cache_hit_rate_target": f"{config.cache_hit_rate_target_min}-{config.cache_hit_rate_target_max}%",
            "description": "Target metrics for monitoring"
        },
        "validation": {
            "is_valid": config._validated,
            "errors": config._validation_errors if not config._validated else []
        }
    }


def get_environment_variables_docs() -> Dict[str, Dict[str, str]]:
    """
    Get documentation for all environment variables

    Returns:
        Dict mapping variable name to {description, default, type}
    """
    return {
        # Step 3: Optimization Config
        "PINECONE_TOP_K": {
            "description": "Number of similar documents to retrieve from Pinecone (reduced for performance)",
            "default": "3",
            "type": "int",
            "step": "3"
        },
        "PINECONE_MIN_TEXT_LENGTH": {
            "description": "Minimum text length to use Pinecone (skip for short texts)",
            "default": "200",
            "type": "int",
            "step": "3"
        },
        "PUBMEDBERT_MIN_CHARS": {
            "description": "Minimum chars to use PubMedBERT for TA detection",
            "default": "500",
            "type": "int",
            "step": "3"
        },

        # Step 4: Prompt Optimizer
        "FAST_TOKEN_BUDGET": {
            "description": "Token budget for fast analysis path",
            "default": "500",
            "type": "int",
            "step": "4"
        },
        "DEEP_TOKEN_BUDGET": {
            "description": "Token budget for deep analysis path",
            "default": "2000",
            "type": "int",
            "step": "4"
        },
        "ANALYSIS_FAST_MODEL": {
            "description": "Azure OpenAI model for fast analysis",
            "default": "gpt-4o-mini",
            "type": "str",
            "step": "4"
        },
        "ANALYSIS_DEEP_MODEL": {
            "description": "Azure OpenAI model for deep analysis",
            "default": "gpt-4o",
            "type": "str",
            "step": "4"
        },
        "SIMPLE_PROMPT_TIMEOUT_MS": {
            "description": "Timeout for fast analysis in milliseconds",
            "default": "10000",
            "type": "int",
            "step": "4"
        },

        # Step 5: Resilience
        "CIRCUIT_BREAKER_THRESHOLD": {
            "description": "Failures before circuit breaker opens",
            "default": "5",
            "type": "int",
            "step": "5"
        },
        "CIRCUIT_BREAKER_TIMEOUT": {
            "description": "Seconds before circuit breaker retries (OPEN → HALF_OPEN)",
            "default": "60",
            "type": "int",
            "step": "5"
        },
        "MAX_RETRIES": {
            "description": "Maximum retry attempts for failed operations",
            "default": "3",
            "type": "int",
            "step": "5"
        },
        "RETRY_BACKOFF_BASE": {
            "description": "Base delay in seconds for exponential backoff",
            "default": "1.0",
            "type": "float",
            "step": "5"
        },

        # Step 6: Cache Manager
        "ENABLE_REDIS": {
            "description": "Enable Redis for distributed caching",
            "default": "false",
            "type": "bool",
            "step": "6"
        },
        "REDIS_URL": {
            "description": "Redis connection URL",
            "default": "redis://localhost:6379",
            "type": "str",
            "step": "6"
        },
        "CACHE_TTL_HOURS": {
            "description": "Default cache TTL in hours",
            "default": "24",
            "type": "int",
            "step": "6"
        },
        "FAST_CACHE_TTL_HOURS": {
            "description": "Cache TTL for fast analysis results",
            "default": "6",
            "type": "int",
            "step": "6"
        },
        "DEEP_CACHE_TTL_HOURS": {
            "description": "Cache TTL for deep analysis results (longer, more expensive)",
            "default": "48",
            "type": "int",
            "step": "6"
        },
        "MAX_MEMORY_CACHE_SIZE": {
            "description": "Maximum entries in in-memory LRU cache",
            "default": "1000",
            "type": "int",
            "step": "6"
        },

        # Step 7: Metrics Collector
        "ENABLE_METRICS": {
            "description": "Enable telemetry and metrics collection",
            "default": "true",
            "type": "bool",
            "step": "7"
        },
        "MAX_TRACES": {
            "description": "Maximum request traces to keep in memory",
            "default": "1000",
            "type": "int",
            "step": "7"
        },

        # Performance Targets
        "FAST_PATH_TARGET_P95_MS": {
            "description": "Target p95 latency for fast path in milliseconds",
            "default": "10000",
            "type": "int",
            "step": "targets"
        },
        "CACHE_HIT_RATE_TARGET_MIN": {
            "description": "Minimum target cache hit rate percentage",
            "default": "50.0",
            "type": "float",
            "step": "targets"
        },
        "CACHE_HIT_RATE_TARGET_MAX": {
            "description": "Maximum target cache hit rate percentage",
            "default": "70.0",
            "type": "float",
            "step": "targets"
        }
    }


# Global configuration instance
_config: Optional[OptimizationConfig] = None


def get_config() -> OptimizationConfig:
    """
    Get global configuration instance (singleton pattern)

    Returns:
        Loaded and validated configuration
    """
    global _config

    if _config is None:
        _config = load_config_from_env()
        if not validate_config(_config):
            logger.warning("⚠️ Configuration has validation errors!")

    return _config


def reload_config() -> OptimizationConfig:
    """
    Reload configuration from environment (for testing/hot-reload)

    Returns:
        Newly loaded configuration
    """
    global _config
    _config = None
    return get_config()


# Initialize configuration on module import
logger.info("⚙️ Loading optimization configuration (Step 9)...")
_config = get_config()

if _config._validated:
    logger.info("✅ Configuration loaded and validated successfully")
else:
    logger.error(f"❌ Configuration validation failed with {len(_config._validation_errors)} errors")


__all__ = [
    "OptimizationConfig",
    "load_config_from_env",
    "validate_config",
    "get_config_summary",
    "get_environment_variables_docs",
    "get_config",
    "reload_config"
]
