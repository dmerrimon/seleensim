#!/usr/bin/env python3
"""
Fast Analysis Module - Optimized for Sub-4s Response Times

Provides lightweight protocol analysis for interactive selections using:
- Minimal context (selected text + ±1 sentence, max 500 chars)
- Fast Azure model (gpt-4o-mini by default)
- Aggressive timeouts and caching
- No heavy RAG/PubMedBERT/Pinecone operations

For deep analysis with full RAG stack, use background job queue.
"""

import os
import time
import logging
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)

# Configuration
FAST_MODEL = os.getenv("ANALYSIS_FAST_MODEL", "gpt-4o-mini")
FAST_TIMEOUT_MS = int(os.getenv("SIMPLE_PROMPT_TIMEOUT_MS", "10000"))  # 10 second timeout
FAST_MAX_TOKENS = 300
FAST_TEMPERATURE = 0.2
SELECTION_CHUNK_THRESHOLD = int(os.getenv("SELECTION_CHUNK_THRESHOLD", "2000"))  # 2000 chars = ~3-5 protocol sentences

# Simple in-memory cache (24h TTL)
_cache = {}
_cache_ttl = {}


def _cache_key(text: str, ta: Optional[str], model: str) -> str:
    """Generate cache key from inputs"""
    content = f"{text}|{ta or 'general'}|{model}"
    return hashlib.sha256(content.encode()).hexdigest()


def _get_cached(key: str) -> Optional[Dict[str, Any]]:
    """Get cached result if still valid"""
    if key in _cache:
        if datetime.now() < _cache_ttl.get(key, datetime.min):
            logger.info(f"✅ Cache hit: {key[:12]}...")
            return _cache[key]
        else:
            # Expired
            del _cache[key]
            del _cache_ttl[key]
    return None


def _set_cache(key: str, value: Dict[str, Any], ttl_hours: int = 24):
    """Cache result with TTL"""
    _cache[key] = value
    _cache_ttl[key] = datetime.now() + timedelta(hours=ttl_hours)


def _build_fast_prompt(text: str, ta: Optional[str] = None) -> str:
    """
    Build minimal prompt for fast analysis

    Args:
        text: Selected protocol text (up to 2000 chars, ~3-5 sentences)
        ta: Optional therapeutic area hint

    Returns:
        Concise prompt optimized for gpt-4o-mini
    """
    ta_context = f" in the {ta.replace('_', ' ')} domain" if ta else ""

    return f"""You are a clinical protocol editor. Analyze this protocol text{ta_context} and suggest ONE improvement focused on clarity, precision, or regulatory compliance.

PROTOCOL TEXT:
{text}

RESPOND IN JSON:
{{
  "original_text": "exact quote needing improvement",
  "improved_text": "your rewrite",
  "rationale": "brief explanation (1 sentence)",
  "type": "clarity|compliance|terminology",
  "confidence": 0.0-1.0
}}

If no issues found, return {{"original_text": "", "improved_text": "", "rationale": "No changes needed", "type": "none", "confidence": 1.0}}"""


async def analyze_fast(
    text: str,
    ta: Optional[str] = None,
    phase: Optional[str] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fast synchronous analysis for small selections

    Target: < 10 seconds total (typically 3-6s for uncached)

    Args:
        text: Selected protocol text (up to 2000 chars)
        ta: Optional therapeutic area
        phase: Optional study phase (currently unused in fast path)
        request_id: Request tracking ID

    Returns:
        {
            "status": "fast",
            "request_id": str,
            "suggestions": [{"id", "text", "suggestion", "rationale", "confidence", "type"}],
            "metadata": {"latency_ms", "model", "cache_hit", ...}
        }
    """
    start_time = time.time()
    req_id = request_id or f"fast_{int(time.time() * 1000)}"

    logger.info(f"⚡ Fast analysis start: {req_id} (text_len={len(text)})")

    # Timing breakdown
    timings = {
        "preprocess_ms": 0,
        "azure_ms": 0,
        "postprocess_ms": 0,
        "total_ms": 0
    }

    try:
        # 1. Preprocess: Trim text if needed
        preprocess_start = time.time()

        if len(text) > SELECTION_CHUNK_THRESHOLD:
            logger.warning(f"⚠️ Text exceeds fast threshold ({len(text)} > {SELECTION_CHUNK_THRESHOLD})")
            # Take first SELECTION_CHUNK_THRESHOLD chars
            trimmed_text = text[:SELECTION_CHUNK_THRESHOLD]
        else:
            trimmed_text = text

        # Check cache
        cache_key = _cache_key(trimmed_text, ta, FAST_MODEL)
        cached_result = _get_cached(cache_key)

        if cached_result:
            cached_result["metadata"]["cache_hit"] = True
            cached_result["metadata"]["total_ms"] = int((time.time() - start_time) * 1000)
            return cached_result

        timings["preprocess_ms"] = int((time.time() - preprocess_start) * 1000)

        # 2. Build prompt
        prompt = _build_fast_prompt(trimmed_text, ta)

        # 3. Call Azure OpenAI with timeout
        azure_start = time.time()

        try:
            suggestion_data = await asyncio.wait_for(
                _call_azure_fast(prompt, req_id),
                timeout=FAST_TIMEOUT_MS / 1000.0
            )
        except asyncio.TimeoutError:
            logger.error(f"⏱️ Azure timeout after {FAST_TIMEOUT_MS}ms: {req_id}")
            raise Exception(f"Analysis timeout after {FAST_TIMEOUT_MS}ms")

        timings["azure_ms"] = int((time.time() - azure_start) * 1000)

        # 4. Postprocess: Format response
        postprocess_start = time.time()

        suggestions = []
        if suggestion_data and suggestion_data.get("original_text"):
            suggestions.append({
                "id": f"{req_id}_fast_1",
                "text": suggestion_data.get("original_text", ""),
                "suggestion": suggestion_data.get("improved_text", ""),
                "rationale": suggestion_data.get("rationale", ""),
                "confidence": suggestion_data.get("confidence", 0.8),
                "type": suggestion_data.get("type", "clarity")
            })

        timings["postprocess_ms"] = int((time.time() - postprocess_start) * 1000)
        timings["total_ms"] = int((time.time() - start_time) * 1000)

        # Build result
        result = {
            "status": "fast",
            "request_id": req_id,
            "suggestions": suggestions,
            "metadata": {
                **timings,
                "model": FAST_MODEL,
                "cache_hit": False,
                "text_length": len(text),
                "trimmed": len(text) > SELECTION_CHUNK_THRESHOLD,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        # Cache successful result
        _set_cache(cache_key, result)

        # Emit performance warning if slow
        if timings["total_ms"] > 8000:
            logger.warning(f"⚠️ Slow fast analysis: {timings['total_ms']}ms (target: <10000ms)")

        logger.info(f"✅ Fast analysis complete: {req_id} ({timings['total_ms']}ms, {len(suggestions)} suggestions)")

        return result

    except Exception as e:
        total_ms = int((time.time() - start_time) * 1000)
        logger.error(f"❌ Fast analysis failed: {req_id} ({total_ms}ms) - {type(e).__name__}: {e}")

        # Return error response
        return {
            "status": "error",
            "request_id": req_id,
            "suggestions": [],
            "metadata": {
                **timings,
                "total_ms": total_ms,
                "error": str(e),
                "model": FAST_MODEL
            }
        }


async def _call_azure_fast(prompt: str, request_id: str) -> Dict[str, Any]:
    """
    Call Azure OpenAI with fast model and aggressive settings

    Args:
        prompt: JSON-formatted prompt
        request_id: Request tracking ID

    Returns:
        Parsed JSON response from model
    """
    import json
    from openai import AsyncAzureOpenAI

    # Get Azure credentials (support both naming conventions)
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_KEY")

    if not azure_endpoint or not azure_key:
        raise ValueError("Azure OpenAI credentials not configured")

    client = AsyncAzureOpenAI(
        api_key=azure_key,
        api_version="2024-02-15-preview",
        azure_endpoint=azure_endpoint
    )

    try:
        response = await client.chat.completions.create(
            model=FAST_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a clinical protocol editor. Always respond with valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=FAST_MAX_TOKENS,
            temperature=FAST_TEMPERATURE,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content

        # Parse JSON response
        try:
            result = json.loads(content)
            return result
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parse error: {e}\nContent: {content}")
            return {}

    except Exception as e:
        logger.error(f"❌ Azure call failed: {request_id} - {type(e).__name__}: {e}")
        raise


# Export main function
__all__ = ["analyze_fast", "SELECTION_CHUNK_THRESHOLD"]
