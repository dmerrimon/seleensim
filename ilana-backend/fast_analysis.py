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
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

# Step 4: Import prompt optimization utilities
from prompt_optimizer import build_fast_prompt, track_token_usage

# Step 6: Import enhanced cache manager
from cache_manager import get_cached, set_cached

# Step 7: Import metrics collector
from metrics_collector import record_request

logger = logging.getLogger(__name__)

# Configuration
FAST_MODEL = os.getenv("ANALYSIS_FAST_MODEL", "gpt-4o-mini")
FAST_TIMEOUT_MS = int(os.getenv("SIMPLE_PROMPT_TIMEOUT_MS", "10000"))  # 10 second timeout
FAST_MAX_TOKENS = 300
FAST_TEMPERATURE = 0.2
SELECTION_CHUNK_THRESHOLD = int(os.getenv("SELECTION_CHUNK_THRESHOLD", "2000"))  # 2000 chars = ~3-5 protocol sentences


# Old cache functions removed in Step 6 - now using cache_manager


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

        # Check cache (Step 6: Enhanced cache manager)
        cached_result = get_cached(
            text=trimmed_text,
            model=FAST_MODEL,
            ta=ta,
            phase=phase,
            analysis_type="fast"
        )

        if cached_result:
            total_ms = int((time.time() - start_time) * 1000)
            cached_result["metadata"]["cache_hit"] = True
            cached_result["metadata"]["total_ms"] = total_ms
            logger.info(f"✅ Returning cached result: {req_id}")

            # Step 7: Record cache hit metrics
            record_request(
                request_id=req_id,
                endpoint="/api/analyze",
                duration_ms=total_ms,
                status_code=200,
                path_type="fast",
                cache_hit=True,
                suggestions_count=len(cached_result.get("suggestions", [])),
                tokens_used=0,  # No tokens used for cache hits
                error=None,
                text_length=len(text),
                model=FAST_MODEL
            )

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

        # 3. Call Azure OpenAI with circuit breaker + retry + timeout
        azure_start = time.time()

        from resilience import get_circuit_breaker, retry_with_backoff, with_timeout

        circuit_breaker = get_circuit_breaker("azure_openai")

        try:
            # Wrap in circuit breaker → retry → timeout (Step 5)
            # Use optimized prompts from prompt_data (Step 4)
            suggestion_data, actual_tokens = await circuit_breaker.call_async(
                retry_with_backoff,
                with_timeout,
                _call_azure_fast,
                FAST_TIMEOUT_MS / 1000.0,
                prompt_data["system"],
                prompt_data["user"],
                req_id,
                max_retries=2  # Fast path: only 2 retries (not 3)
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

        # 4. Postprocess: Format response (handles new issues array format)
        postprocess_start = time.time()

        suggestions = []

        # New format: {"issues": [...]}
        if suggestion_data and "issues" in suggestion_data:
            issues = suggestion_data.get("issues", [])
            for idx, issue in enumerate(issues[:10]):  # Limit to 10 issues max
                # Map new schema to frontend format
                suggestions.append({
                    "id": issue.get("id", f"{req_id}_fast_{idx+1}"),
                    "text": issue.get("original_text", ""),
                    "suggestion": issue.get("improved_text", ""),
                    "rationale": issue.get("rationale", ""),
                    "confidence": issue.get("confidence", 0.8),
                    "type": issue.get("category", "clarity"),  # category -> type mapping
                    "severity": issue.get("severity", "minor"),
                    "recommendation": issue.get("recommendation", "")
                })
        # Legacy format fallback: single issue object
        elif suggestion_data and suggestion_data.get("original_text"):
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

        # Cache successful result (Step 6: Enhanced cache manager)
        set_cached(
            text=trimmed_text,
            model=FAST_MODEL,
            result=result,
            ta=ta,
            phase=phase,
            analysis_type="fast"
        )

        # Emit performance warning if slow
        if timings["total_ms"] > 8000:
            logger.warning(f"⚠️ Slow fast analysis: {timings['total_ms']}ms (target: <10000ms)")

        logger.info(f"✅ Fast analysis complete: {req_id} ({timings['total_ms']}ms, {len(suggestions)} suggestions)")

        # Step 7: Record metrics
        record_request(
            request_id=req_id,
            endpoint="/api/analyze",
            duration_ms=timings["total_ms"],
            status_code=200,
            path_type="fast",
            cache_hit=False,
            suggestions_count=len(suggestions),
            tokens_used=actual_tokens.get("total_tokens", 0),
            error=None,
            text_length=len(text),
            model=FAST_MODEL
        )

        return result

    except Exception as e:
        total_ms = int((time.time() - start_time) * 1000)
        logger.error(f"❌ Fast analysis failed: {req_id} ({total_ms}ms) - {type(e).__name__}: {e}")

        # Step 7: Record error metrics
        record_request(
            request_id=req_id,
            endpoint="/api/analyze",
            duration_ms=total_ms,
            status_code=500,
            path_type="fast",
            cache_hit=False,
            suggestions_count=0,
            tokens_used=0,
            error=f"{type(e).__name__}: {str(e)}",
            text_length=len(text),
            model=FAST_MODEL
        )

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
