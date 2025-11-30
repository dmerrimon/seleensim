#!/usr/bin/env python3
"""
Enhanced Cache Manager for Step 6: Caching

Provides intelligent caching with:
- Redis backend with in-memory fallback
- Smart cache keys (content hash + model + TA + phase)
- TTL optimization based on content type
- Cache statistics and monitoring
- LRU eviction for in-memory cache
- Cache warming strategies

Target: 50-70% cache hit rate for repeated protocol sections
"""

import os
import time
import hashlib
import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import OrderedDict

logger = logging.getLogger(__name__)

# Configuration
ENABLE_REDIS = os.getenv("ENABLE_REDIS", "false").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
DEFAULT_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "24"))
FAST_CACHE_TTL_HOURS = int(os.getenv("FAST_CACHE_TTL_HOURS", "6"))  # Shorter TTL for fast path
DEEP_CACHE_TTL_HOURS = int(os.getenv("DEEP_CACHE_TTL_HOURS", "48"))  # Longer TTL for deep path
MAX_MEMORY_CACHE_SIZE = int(os.getenv("MAX_MEMORY_CACHE_SIZE", "1000"))  # LRU eviction

# Code version for cache invalidation
# Increment this whenever deploying bug fixes to invalidate stale cache
CODE_VERSION = os.getenv("CODE_VERSION", "v1.4.1")  # Bumped from v1.4.0 to invalidate cache after NameError fix

# Cache statistics
_stats = {
    "hits": 0,
    "misses": 0,
    "sets": 0,
    "evictions": 0,
    "errors": 0,
    "redis_available": False
}


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Dict[str, Any]
    created_at: datetime
    expires_at: datetime
    access_count: int
    last_accessed: datetime
    size_bytes: int


class LRUCache:
    """
    LRU (Least Recently Used) cache with size limit

    When cache is full, evicts least recently accessed items
    """

    def __init__(self, max_size: int = MAX_MEMORY_CACHE_SIZE):
        self.max_size = max_size
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = None  # For thread safety if needed

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get item from cache, moving it to end (most recent)"""
        if key not in self.cache:
            return None

        entry = self.cache.pop(key)

        # Check if expired
        if datetime.now() > entry.expires_at:
            logger.debug(f"Cache entry expired: {key[:12]}...")
            return None

        # Update access metadata
        entry.access_count += 1
        entry.last_accessed = datetime.now()

        # Move to end (most recent)
        self.cache[key] = entry

        return entry.value

    def set(self, key: str, value: Dict[str, Any], ttl_hours: int = DEFAULT_TTL_HOURS):
        """Set item in cache, evicting LRU if needed"""
        # Remove if already exists (to update)
        if key in self.cache:
            del self.cache[key]

        # Evict LRU if at capacity
        if len(self.cache) >= self.max_size:
            evicted_key, evicted_entry = self.cache.popitem(last=False)
            _stats["evictions"] += 1
            logger.debug(f"Evicted LRU entry: {evicted_key[:12]}... (accessed {evicted_entry.access_count} times)")

        # Create entry
        now = datetime.now()
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=now,
            expires_at=now + timedelta(hours=ttl_hours),
            access_count=0,
            last_accessed=now,
            size_bytes=len(json.dumps(value))
        )

        # Add to end (most recent)
        self.cache[key] = entry

    def clear(self):
        """Clear all cached items"""
        self.cache.clear()

    def size(self) -> int:
        """Get current cache size"""
        return len(self.cache)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_size = sum(entry.size_bytes for entry in self.cache.values())

        if self.cache:
            avg_access = sum(entry.access_count for entry in self.cache.values()) / len(self.cache)
            oldest_entry = min(self.cache.values(), key=lambda e: e.created_at)
            newest_entry = max(self.cache.values(), key=lambda e: e.created_at)
        else:
            avg_access = 0
            oldest_entry = None
            newest_entry = None

        return {
            "entries": len(self.cache),
            "max_size": self.max_size,
            "total_size_bytes": total_size,
            "avg_access_count": round(avg_access, 2),
            "oldest_entry_age_hours": (
                (datetime.now() - oldest_entry.created_at).total_seconds() / 3600
                if oldest_entry else 0
            ),
            "newest_entry_age_hours": (
                (datetime.now() - newest_entry.created_at).total_seconds() / 3600
                if newest_entry else 0
            )
        }


# Global in-memory LRU cache
_memory_cache = LRUCache(MAX_MEMORY_CACHE_SIZE)

# Redis client (lazy initialization)
_redis_client = None


def _get_redis_client():
    """Get or create Redis client"""
    global _redis_client, _stats

    if not ENABLE_REDIS:
        return None

    if _redis_client is not None:
        return _redis_client

    try:
        import redis
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        _redis_client.ping()
        _stats["redis_available"] = True
        logger.info(f"✅ Redis connected: {REDIS_URL}")
        return _redis_client
    except ImportError:
        logger.warning("⚠️ redis-py not installed, using in-memory cache only")
        _stats["redis_available"] = False
        return None
    except Exception as e:
        logger.warning(f"⚠️ Redis connection failed: {e}, using in-memory cache only")
        _stats["redis_available"] = False
        return None


def generate_cache_key(
    text: str,
    model: str,
    ta: Optional[str] = None,
    phase: Optional[str] = None,
    analysis_type: str = "fast"
) -> str:
    """
    Generate deterministic cache key

    Args:
        text: Protocol text to analyze
        model: Model name (e.g., gpt-4o-mini)
        ta: Optional therapeutic area
        phase: Optional study phase
        analysis_type: "fast" or "deep"

    Returns:
        Cache key (SHA256 hash)
    """
    # Normalize text (trim, lowercase, remove extra whitespace)
    normalized_text = " ".join(text.lower().strip().split())

    # Build key components (including CODE_VERSION for cache invalidation)
    components = [
        normalized_text,
        model,
        ta or "none",
        phase or "none",
        analysis_type,
        CODE_VERSION  # Invalidates cache when code changes
    ]

    # Hash to fixed-length key
    key_string = "|".join(components)
    cache_key = hashlib.sha256(key_string.encode()).hexdigest()

    return cache_key


def get_ttl_for_type(analysis_type: str, content_length: int) -> int:
    """
    Get optimal TTL based on analysis type and content

    Args:
        analysis_type: "fast" or "deep"
        content_length: Length of protocol text

    Returns:
        TTL in hours
    """
    # Deep analysis results are more expensive, cache longer
    if analysis_type == "deep":
        return DEEP_CACHE_TTL_HOURS

    # Fast analysis for short texts changes less, can cache longer
    if analysis_type == "fast" and content_length < 500:
        return FAST_CACHE_TTL_HOURS * 2  # 12 hours for very short texts

    return FAST_CACHE_TTL_HOURS


def get_cached(
    text: str,
    model: str,
    ta: Optional[str] = None,
    phase: Optional[str] = None,
    analysis_type: str = "fast"
) -> Optional[Dict[str, Any]]:
    """
    Get cached analysis result

    Args:
        text: Protocol text
        model: Model name
        ta: Optional therapeutic area
        phase: Optional study phase
        analysis_type: "fast" or "deep"

    Returns:
        Cached result or None
    """
    cache_key = generate_cache_key(text, model, ta, phase, analysis_type)

    # Try Redis first (if enabled)
    redis_client = _get_redis_client()
    if redis_client:
        try:
            cached_json = redis_client.get(f"ilana:cache:{cache_key}")
            if cached_json:
                _stats["hits"] += 1
                result = json.loads(cached_json)
                logger.info(f"✅ Redis cache hit: {cache_key[:12]}...")
                return result
        except Exception as e:
            logger.error(f"❌ Redis get error: {e}")
            _stats["errors"] += 1

    # Fallback to in-memory cache
    result = _memory_cache.get(cache_key)
    if result:
        _stats["hits"] += 1
        logger.info(f"✅ Memory cache hit: {cache_key[:12]}...")
        return result

    # Cache miss
    _stats["misses"] += 1
    logger.debug(f"❌ Cache miss: {cache_key[:12]}...")
    return None


def set_cached(
    text: str,
    model: str,
    result: Dict[str, Any],
    ta: Optional[str] = None,
    phase: Optional[str] = None,
    analysis_type: str = "fast"
):
    """
    Cache analysis result

    Args:
        text: Protocol text
        model: Model name
        result: Analysis result to cache
        ta: Optional therapeutic area
        phase: Optional study phase
        analysis_type: "fast" or "deep"
    """
    cache_key = generate_cache_key(text, model, ta, phase, analysis_type)
    ttl_hours = get_ttl_for_type(analysis_type, len(text))

    # Try Redis first (if enabled)
    redis_client = _get_redis_client()
    if redis_client:
        try:
            ttl_seconds = ttl_hours * 3600
            redis_client.setex(
                f"ilana:cache:{cache_key}",
                ttl_seconds,
                json.dumps(result)
            )
            logger.debug(f"✅ Redis cache set: {cache_key[:12]}... (TTL: {ttl_hours}h)")
        except Exception as e:
            logger.error(f"❌ Redis set error: {e}")
            _stats["errors"] += 1

    # Always cache in memory as fallback
    _memory_cache.set(cache_key, result, ttl_hours)
    _stats["sets"] += 1
    logger.debug(f"✅ Memory cache set: {cache_key[:12]}... (TTL: {ttl_hours}h)")


def clear_cache():
    """Clear all cached results"""
    global _memory_cache

    # Clear Redis
    redis_client = _get_redis_client()
    if redis_client:
        try:
            # Delete all keys matching pattern
            keys = redis_client.keys("ilana:cache:*")
            if keys:
                redis_client.delete(*keys)
                logger.info(f"🗑️ Cleared {len(keys)} Redis cache entries")
        except Exception as e:
            logger.error(f"❌ Redis clear error: {e}")

    # Clear in-memory
    _memory_cache.clear()
    logger.info("🗑️ Cleared in-memory cache")


def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics

    Returns:
        Dict with cache stats and metrics
    """
    total_requests = _stats["hits"] + _stats["misses"]
    hit_rate = (_stats["hits"] / total_requests * 100) if total_requests > 0 else 0

    # Get memory cache stats
    memory_stats = _memory_cache.get_stats()

    # Try to get Redis stats
    redis_stats = {}
    redis_client = _get_redis_client()
    if redis_client and _stats["redis_available"]:
        try:
            info = redis_client.info("stats")
            redis_stats = {
                "connected": True,
                "total_keys": redis_client.dbsize(),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "used_memory": info.get("used_memory_human", "N/A")
            }
        except Exception as e:
            logger.error(f"❌ Redis stats error: {e}")
            redis_stats = {"connected": False, "error": str(e)}
    else:
        redis_stats = {"connected": False, "enabled": ENABLE_REDIS}

    return {
        "global": {
            "total_requests": total_requests,
            "hits": _stats["hits"],
            "misses": _stats["misses"],
            "hit_rate_pct": round(hit_rate, 2),
            "sets": _stats["sets"],
            "evictions": _stats["evictions"],
            "errors": _stats["errors"]
        },
        "memory_cache": memory_stats,
        "redis": redis_stats,
        "configuration": {
            "redis_enabled": ENABLE_REDIS,
            "redis_url": REDIS_URL if ENABLE_REDIS else None,
            "default_ttl_hours": DEFAULT_TTL_HOURS,
            "fast_ttl_hours": FAST_CACHE_TTL_HOURS,
            "deep_ttl_hours": DEEP_CACHE_TTL_HOURS,
            "max_memory_size": MAX_MEMORY_CACHE_SIZE
        },
        "target_metrics": {
            "target_hit_rate": "50-70%",
            "current_vs_target": (
                "GOOD" if hit_rate >= 50 else
                "OK" if hit_rate >= 30 else
                "LOW"
            )
        }
    }


def reset_cache_stats():
    """Reset cache statistics (for testing)"""
    global _stats
    _stats = {
        "hits": 0,
        "misses": 0,
        "sets": 0,
        "evictions": 0,
        "errors": 0,
        "redis_available": _stats["redis_available"]
    }


# Log configuration on import
logger.info("💾 Cache manager loaded (Step 6):")
logger.info(f"   - Code version: {CODE_VERSION} (for cache invalidation)")
logger.info(f"   - Redis enabled: {ENABLE_REDIS}")
logger.info(f"   - Fast TTL: {FAST_CACHE_TTL_HOURS}h, Deep TTL: {DEEP_CACHE_TTL_HOURS}h")
logger.info(f"   - Max memory cache size: {MAX_MEMORY_CACHE_SIZE} entries")
logger.info(f"   - Target hit rate: 50-70%")


__all__ = [
    "get_cached",
    "set_cached",
    "clear_cache",
    "get_cache_stats",
    "reset_cache_stats",
    "generate_cache_key",
    "get_ttl_for_type"
]
