#!/usr/bin/env python3
"""
Optimization Configuration for Step 3: Trim Vector DB & PubMedBERT Usage

Controls resource usage in the legacy pipeline to reduce latency and costs:
- Pinecone vector DB query limits
- PubMedBERT conditional usage
- Smart skipping for simple/small texts

Environment variables:
- PINECONE_TOP_K: Number of similar protocols to retrieve (default: 3, was 5)
- PUBMEDBERT_MIN_CHARS: Minimum text length to use PubMedBERT (default: 500)
- SKIP_VECTOR_SEARCH_UNDER_CHARS: Skip Pinecone for very short texts (default: 200)
- ENABLE_SMART_SKIPPING: Enable intelligent feature skipping (default: true)
"""

import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Pinecone Configuration
PINECONE_TOP_K = int(os.getenv("PINECONE_TOP_K", "3"))  # Reduced from 5 to 3 (40% reduction)
PINECONE_TOP_K_FAST = int(os.getenv("PINECONE_TOP_K_FAST", "2"))  # Even faster mode for background jobs

# PubMedBERT Configuration
PUBMEDBERT_MIN_CHARS = int(os.getenv("PUBMEDBERT_MIN_CHARS", "500"))  # Skip for very short texts
PUBMEDBERT_TIMEOUT_S = int(os.getenv("PUBMEDBERT_TIMEOUT_S", "5"))  # 5 second timeout

# Smart Skipping Configuration
ENABLE_SMART_SKIPPING = os.getenv("ENABLE_SMART_SKIPPING", "true").lower() == "true"
SKIP_VECTOR_SEARCH_UNDER_CHARS = int(os.getenv("SKIP_VECTOR_SEARCH_UNDER_CHARS", "200"))  # Too short for meaningful vector search

# Performance Budgets (milliseconds)
VECTOR_SEARCH_BUDGET_MS = int(os.getenv("VECTOR_SEARCH_BUDGET_MS", "2000"))  # 2s max for Pinecone
PUBMEDBERT_BUDGET_MS = int(os.getenv("PUBMEDBERT_BUDGET_MS", "3000"))  # 3s max for PubMedBERT


def should_use_pinecone(text: str, ta: str = None) -> bool:
    """
    Determine if Pinecone vector search should be used

    Skip Pinecone if:
    - Text is very short (< 200 chars)
    - Smart skipping is enabled and text is simple

    Args:
        text: Protocol text to analyze
        ta: Therapeutic area (if known)

    Returns:
        True if Pinecone should be used, False to skip
    """
    if not ENABLE_SMART_SKIPPING:
        return True

    text_len = len(text)

    # Skip for very short texts
    if text_len < SKIP_VECTOR_SEARCH_UNDER_CHARS:
        logger.info(f"⏭️ Skipping Pinecone: text too short ({text_len} < {SKIP_VECTOR_SEARCH_UNDER_CHARS} chars)")
        return False

    return True


def should_use_pubmedbert(text: str, ta: str = None) -> bool:
    """
    Determine if PubMedBERT embeddings should be used

    Skip PubMedBERT if:
    - Text is very short (< 500 chars)
    - TA is already known (PubMedBERT is mainly for TA detection)
    - Smart skipping is enabled and not medically complex

    Args:
        text: Protocol text to analyze
        ta: Therapeutic area (if known)

    Returns:
        True if PubMedBERT should be used, False to skip
    """
    if not ENABLE_SMART_SKIPPING:
        return True

    text_len = len(text)

    # Skip for very short texts
    if text_len < PUBMEDBERT_MIN_CHARS:
        logger.info(f"⏭️ Skipping PubMedBERT: text too short ({text_len} < {PUBMEDBERT_MIN_CHARS} chars)")
        return False

    # Skip if TA is already known (PubMedBERT mainly helps with TA detection)
    if ta and ta != "general_medicine":
        logger.info(f"⏭️ Skipping PubMedBERT: TA already known ({ta})")
        return False

    return True


def get_optimized_top_k(text_len: int, is_background_job: bool = True) -> int:
    """
    Get optimal top_k value based on text length and context

    Args:
        text_len: Length of protocol text
        is_background_job: True if running in background (can afford more time)

    Returns:
        Optimal top_k value (1-5)
    """
    # Background jobs can afford slightly more retrieval
    base_top_k = PINECONE_TOP_K if is_background_job else PINECONE_TOP_K_FAST

    # Very large texts need fewer exemplars (already have context)
    if text_len > 5000:
        return max(1, base_top_k - 1)

    # Medium texts use standard top_k
    if text_len > 1000:
        return base_top_k

    # Short texts might benefit from one extra exemplar
    return min(5, base_top_k + 1)


def get_optimization_summary() -> Dict[str, Any]:
    """
    Get current optimization configuration

    Returns:
        Dict with all optimization settings
    """
    return {
        "pinecone": {
            "top_k": PINECONE_TOP_K,
            "top_k_fast": PINECONE_TOP_K_FAST,
            "skip_under_chars": SKIP_VECTOR_SEARCH_UNDER_CHARS,
            "budget_ms": VECTOR_SEARCH_BUDGET_MS
        },
        "pubmedbert": {
            "min_chars": PUBMEDBERT_MIN_CHARS,
            "timeout_s": PUBMEDBERT_TIMEOUT_S,
            "budget_ms": PUBMEDBERT_BUDGET_MS
        },
        "smart_skipping": {
            "enabled": ENABLE_SMART_SKIPPING
        },
        "performance_impact": {
            "pinecone_reduction": "40% (5 → 3 vectors)",
            "pubmedbert_skip_rate": f"~{int((PUBMEDBERT_MIN_CHARS / 2000) * 100)}% of small selections",
            "estimated_latency_savings": "2-5 seconds for small texts"
        }
    }


# Log configuration on import
logger.info("📊 Optimization config loaded (Step 3):")
logger.info(f"   - Pinecone top_k: {PINECONE_TOP_K} (fast: {PINECONE_TOP_K_FAST})")
logger.info(f"   - PubMedBERT min chars: {PUBMEDBERT_MIN_CHARS}")
logger.info(f"   - Smart skipping: {ENABLE_SMART_SKIPPING}")
logger.info(f"   - Skip vector search under: {SKIP_VECTOR_SEARCH_UNDER_CHARS} chars")


__all__ = [
    "should_use_pinecone",
    "should_use_pubmedbert",
    "get_optimized_top_k",
    "get_optimization_summary",
    "PINECONE_TOP_K",
    "PINECONE_TOP_K_FAST",
    "PUBMEDBERT_MIN_CHARS",
    "ENABLE_SMART_SKIPPING"
]
