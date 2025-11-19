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

# Step 4: Import prompt optimization utilities
from prompt_optimizer import build_fast_prompt, track_token_usage

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


# _build_fast_prompt removed in Step 4 - now using prompt_optimizer.build_fast_prompt


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

        # 2. Build optimized prompt (Step 4)
        prompt_data = build_fast_prompt(trimmed_text, ta)

        # Log token budget info
        token_info = prompt_data["tokens"]
        logger.info(
            f"📊 [{req_id}] Prompt tokens: {token_info['total_input']} "
            f"(budget: {token_info['budget']}, system: {token_info['system']}, user: {token_info['user']})"
        )

        # 3. Call Azure OpenAI with timeout
        azure_start = time.time()

        try:
            suggestion_data, actual_tokens = await asyncio.wait_for(
                _call_azure_fast(prompt_data["system"], prompt_data["user"], req_id),
                timeout=FAST_TIMEOUT_MS / 1000.0
            )
        except asyncio.TimeoutError:
            logger.error(f"⏱️ Azure timeout after {FAST_TIMEOUT_MS}ms: {req_id}")
            raise Exception(f"Analysis timeout after {FAST_TIMEOUT_MS}ms")

        timings["azure_ms"] = int((time.time() - azure_start) * 1000)

        # Track token usage (Step 4)
        track_token_usage(
            "fast_path",
            actual_tokens.get("prompt_tokens", token_info["total_input"]),
            actual_tokens.get("completion_tokens", token_info["expected_output"])
        )

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
                "timestamp": datetime.utcnow().isoformat(),
                # Step 4: Token usage tracking
                "tokens": {
                    "prompt": actual_tokens.get("prompt_tokens", token_info["total_input"]),
                    "completion": actual_tokens.get("completion_tokens", token_info["expected_output"]),
                    "total": actual_tokens.get("total_tokens", 0),
                    "budget": token_info["budget"]
                }
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


async def _call_azure_fast(system_prompt: str, user_prompt: str, request_id: str) -> tuple[Dict[str, Any], Dict[str, int]]:
    """
    Call Azure OpenAI with fast model and optimized prompts (Step 4)

    Args:
        system_prompt: System message (optimized)
        user_prompt: User message (optimized)
        request_id: Request tracking ID

    Returns:
        Tuple of (parsed JSON response, token usage dict)
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
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            max_tokens=FAST_MAX_TOKENS,
            temperature=FAST_TEMPERATURE,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content

        # Extract token usage (Step 4)
        token_usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0
        }

        # Parse JSON response
        try:
            result = json.loads(content)
            return result, token_usage
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parse error: {e}\nContent: {content}")
            return {}, token_usage

    except Exception as e:
        logger.error(f"❌ Azure call failed: {request_id} - {type(e).__name__}: {e}")
        raise


# Export main function
__all__ = ["analyze_fast", "SELECTION_CHUNK_THRESHOLD"]
