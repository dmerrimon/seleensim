# hybrid_controller.py
"""
Robust async-first hybrid controller for Ilana Protocol Intelligence.

Exposures:
- /api/recommend-language: Selection-first text analysis
- /api/analyze: Unified analysis entry point
- /api/generate-rewrite-ta: TA enhancement with shadow worker

Features:
- Selection-first text analysis with fast path
- Async document chunking for large inputs
- TA enhancement via /api/generate-rewrite-ta
- Shadow worker mode trigger for A/B comparison
- Graceful fallback if TA or shadow services fail
- Defensive type logging and awaitable-safe responses
"""

import os
import uuid
import json
import time
import logging
import asyncio
import inspect
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from pathlib import Path

logger = logging.getLogger("ilana.hybrid")
logger.setLevel(logging.INFO)

# Configuration
CHUNK_MAX_CHARS = int(os.getenv("CHUNK_MAX_CHARS", "3500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
ENABLE_TA_ON_DEMAND = os.getenv("ENABLE_TA_ON_DEMAND", "true").lower() == "true"
ENABLE_TA_SHADOW = os.getenv("ENABLE_TA_SHADOW", "false").lower() == "true"
SHADOW_TRIGGER_THRESHOLD = float(os.getenv("SHADOW_TRIGGER_THRESHOLD", "0.3"))

# ===== DEFENSIVE TYPE LOGGING =====
def log_hybrid_controller_info() -> Dict[str, Any]:
    """Log defensive type information about hybrid controller."""
    info = {
        "has_hybrid_controller": True,
        "handler_name": "handle_hybrid_request",
        "iscoroutinefunction": inspect.iscoroutinefunction(handle_hybrid_request),
        "is_awaitable_return": True  # Our implementation always returns awaitable-safe responses
    }
    logger.info(f"Hybrid controller type info: {json.dumps(info)}")
    return info

# ===== SERVICE IMPORTS =====
def _import_simple_handler() -> Optional[Any]:
    """Import simple recommendation handler if available."""
    try:
        from recommend_simple import recommend_language_simple
        return recommend_language_simple
    except Exception as e:
        logger.debug(f"Simple handler import failed: {e}")
        return None

def _import_ta_handler() -> Optional[Any]:
    """Import TA enhancement handler if available."""
    try:
        # This would be your TA enhancement service
        # For now, we'll simulate with placeholder
        return None
    except Exception as e:
        logger.debug(f"TA handler import failed: {e}")
        return None

# ===== HTTP SERVICE CALLS =====
async def _call_simple_http(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback: call the simple endpoint over HTTP."""
    try:
        import httpx
        url = "http://127.0.0.1:8000/api/recommend-language-simple"
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.exception(f"Simple HTTP call failed: {e}")
        raise

async def _call_ta_enhancement_http(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Call TA enhancement service over HTTP with graceful fallback."""
    try:
        import httpx
        url = "http://127.0.0.1:8000/api/generate-rewrite-ta"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 202:  # Queued due to RAG_ASYNC_MODE
                logger.info("TA enhancement queued for async processing")
                return resp.json()
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning(f"TA enhancement failed, using graceful fallback: {e}")
        # Graceful fallback - return basic analysis
        return {
            "status": "fallback",
            "message": "TA enhancement unavailable, using basic analysis",
            "error": str(e)
        }

# ===== JOB QUEUE & CHUNKING =====
async def _chunk_large_document(text: str, max_chars: int = None) -> List[Dict[str, Any]]:
    """Chunk large documents for async processing."""
    max_chars = max_chars or CHUNK_MAX_CHARS
    overlap = CHUNK_OVERLAP
    
    if len(text) <= max_chars:
        return [{"chunk_id": 0, "text": text, "start": 0, "end": len(text)}]
    
    chunks = []
    start = 0
    chunk_id = 0
    
    while start < len(text):
        end = min(start + max_chars, len(text))
        
        # Try to break at word boundary
        if end < len(text):
            last_space = text.rfind(' ', start, end)
            if last_space > start:
                end = last_space
        
        chunk_text = text[start:end]
        chunks.append({
            "chunk_id": chunk_id,
            "text": chunk_text,
            "start": start,
            "end": end,
            "length": len(chunk_text)
        })
        
        start = max(end - overlap, start + 1)  # Prevent infinite loops
        chunk_id += 1
    
    logger.info(f"Document chunked into {len(chunks)} pieces (max_chars={max_chars})")
    return chunks

async def _enqueue_document_job(payload: Dict[str, Any]) -> str:
    """Enqueue document job with chunking support."""
    job_id = str(uuid.uuid4())
    
    # Chunk document if needed
    text = payload.get("text", "")
    if len(text) > CHUNK_MAX_CHARS:
        chunks = await _chunk_large_document(text)
        payload["chunks"] = chunks
        payload["chunked"] = True
        logger.info(f"Job {job_id}: Document chunked into {len(chunks)} pieces")
    else:
        payload["chunked"] = False
    
    # Store job metadata
    try:
        jobs_dir = Path("jobs")
        jobs_dir.mkdir(exist_ok=True)
        
        job_data = {
            "job_id": job_id,
            "payload": payload,
            "status": "queued",
            "created_at": datetime.utcnow().isoformat(),
            "chunked": payload.get("chunked", False),
            "chunk_count": len(payload.get("chunks", []))
        }
        
        (jobs_dir / f"{job_id}.json").write_text(json.dumps(job_data, indent=2))
        logger.info(f"Job {job_id} queued successfully")
        
    except Exception as e:
        logger.error(f"Failed to store job {job_id}: {e}")
        # Non-fatal, job can still be processed
    
    return job_id

# ===== UTILITY FUNCTIONS =====
async def _maybe_await(value: Any) -> Any:
    """Safely await value if it's awaitable, otherwise return as-is."""
    if inspect.isawaitable(value):
        logger.debug(f"Value is awaitable, awaiting now. type={type(value)}")
        try:
            return await value
        except Exception as e:
            logger.exception(f"Awaiting value raised exception: {e}")
            raise
    return value

def _should_trigger_shadow_worker(text: str, ta: Optional[str]) -> bool:
    """Determine if shadow worker should be triggered for A/B comparison."""
    if not ENABLE_TA_SHADOW:
        return False
    
    # Simple hash-based deterministic trigger
    text_hash = hashlib.md5(text.encode()).hexdigest()
    hash_value = int(text_hash[:8], 16) / 0xFFFFFFFF
    
    should_trigger = hash_value < SHADOW_TRIGGER_THRESHOLD
    logger.debug(f"Shadow worker trigger check: {should_trigger} (threshold={SHADOW_TRIGGER_THRESHOLD})")
    return should_trigger

def _create_request_metadata(payload: Dict[str, Any], mode: str) -> Dict[str, Any]:
    """Create standardized request metadata."""
    text = payload.get("text", "")
    return {
        "request_id": payload.get("request_id", str(uuid.uuid4())),
        "mode": mode,
        "text_length": len(text),
        "ta": payload.get("ta"),
        "phase": payload.get("phase"),
        "shadow_triggered": _should_trigger_shadow_worker(text, payload.get("ta")),
        "timestamp": datetime.utcnow().isoformat()
    }

# ===== MAIN HYBRID CONTROLLER =====
async def handle_hybrid_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main hybrid controller entrypoint (async-first, awaitable-safe).
    
    Exposures:
    - /api/recommend-language: Selection-first text analysis
    - /api/analyze: Unified analysis entry point  
    - /api/generate-rewrite-ta: TA enhancement with shadow worker
    
    Returns:
      - selection quick-pass: {"request_id":..., "status":"ok", "suggestions": [...]}
      - document enqueue: {"request_id":..., "status":"queued", "job_id": "...", "chunks": [...]}  
      - ta enhancement: {"request_id":..., "status":"enhanced", "suggestions": [...], "ta_metadata": {...}}
      - error: {"request_id":..., "status":"error", "error":"...", "fallback": {...}}
    """
    start_time = time.time()
    mode = payload.get("mode", "selection")
    metadata = _create_request_metadata(payload, mode)
    request_id = metadata["request_id"]
    
    logger.info(f"🚀 Hybrid request start: {request_id} mode={mode} text_len={metadata['text_length']}")
    
    try:
        # ===== SELECTION-FIRST ANALYSIS =====
        if mode in ("selection", "selection_only"):
            return await _handle_selection_mode(payload, metadata)
        
        # ===== TA ENHANCEMENT MODE =====
        elif mode in ("ta_enhanced", "ta_on_demand"):
            return await _handle_ta_enhancement_mode(payload, metadata)
        
        # ===== DOCUMENT CHUNKING MODE =====
        elif mode in ("document", "document_truncated", "document_chunked"):
            return await _handle_document_mode(payload, metadata)
        
        # ===== OPTIMIZE SELECTION MODE =====
        elif mode in ("optimize_selection",):
            return await _handle_optimize_selection_mode(payload, metadata)
        
        # ===== UNKNOWN MODE =====
        else:
            logger.warning(f"❌ Unknown hybrid mode: {mode}")
            return {
                "request_id": request_id,
                "status": "error",
                "error": f"unknown-mode:{mode}",
                "supported_modes": ["selection", "ta_enhanced", "document_chunked", "optimize_selection"],
                "latency_ms": int((time.time() - start_time) * 1000)
            }
    
    except Exception as e:
        logger.exception(f"💥 Hybrid request failed: {request_id}")
        return {
            "request_id": request_id,
            "status": "error",
            "error": str(e),
            "mode": mode,
            "latency_ms": int((time.time() - start_time) * 1000)
        }

# ===== MODE HANDLERS =====
async def _handle_selection_mode(payload: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle selection-first text analysis with fast path."""
    request_id = metadata["request_id"]
    
    # Try in-process simple handler first
    simple_handler = _import_simple_handler()
    if simple_handler:
        try:
            logger.debug(f"📍 Using in-process simple handler: {getattr(simple_handler, '__name__', str(simple_handler))}")
            
            # Create proper SimpleRecommendRequest object
            from recommend_simple import SimpleRecommendRequest
            simple_request = SimpleRecommendRequest(
                text=payload.get("text", ""),
                ta=payload.get("ta"),
                phase=payload.get("phase")
            )
            
            result = await _maybe_await(simple_handler(simple_request))
            
            # Trigger shadow worker if enabled
            shadow_result = None
            if metadata["shadow_triggered"]:
                shadow_result = await _trigger_shadow_worker(payload, "selection")
            
            return {
                "request_id": request_id,
                "status": "ok",
                "suggestions": result,
                "metadata": metadata,
                "shadow_worker": shadow_result
            }
            
        except Exception as e:
            logger.exception(f"⚠️ In-process simple handler failed: {e}")
            # Continue to HTTP fallback
    
    # Fallback to HTTP simple endpoint
    try:
        result = await _call_simple_http(payload)
        
        shadow_result = None
        if metadata["shadow_triggered"]:
            shadow_result = await _trigger_shadow_worker(payload, "selection")
        
        return {
            "request_id": request_id,
            "status": "ok",
            "suggestions": result,
            "metadata": metadata,
            "shadow_worker": shadow_result,
            "fallback": "http"
        }
        
    except Exception as e:
        logger.exception(f"💥 Simple HTTP fallback failed: {e}")
        return {
            "request_id": request_id,
            "status": "error",
            "error": "selection-unavailable",
            "details": str(e),
            "metadata": metadata
        }

async def _handle_ta_enhancement_mode(payload: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle TA enhancement with graceful fallback."""
    request_id = metadata["request_id"]
    
    if not ENABLE_TA_ON_DEMAND:
        logger.warning("⚠️ TA on-demand is disabled")
        return {
            "request_id": request_id,
            "status": "disabled",
            "message": "TA enhancement is disabled. Set ENABLE_TA_ON_DEMAND=true to enable.",
            "metadata": metadata
        }
    
    try:
        # Call TA enhancement service
        ta_payload = {
            "text": payload.get("text", ""),
            "ta": payload.get("ta"),
            "phase": payload.get("phase"),
            "suggestion_id": payload.get("suggestion_id", str(uuid.uuid4()))
        }
        
        ta_result = await _call_ta_enhancement_http(ta_payload)
        
        # Trigger shadow worker if enabled
        shadow_result = None
        if metadata["shadow_triggered"]:
            shadow_result = await _trigger_shadow_worker(payload, "ta_enhanced")
        
        return {
            "request_id": request_id,
            "status": "enhanced" if ta_result.get("status") != "fallback" else "fallback",
            "suggestions": ta_result,
            "metadata": metadata,
            "shadow_worker": shadow_result,
            "ta_enhancement": True
        }
        
    except Exception as e:
        logger.exception(f"💥 TA enhancement failed: {e}")
        
        # Graceful fallback to basic selection
        try:
            fallback_result = await _handle_selection_mode(payload, metadata)
            fallback_result["status"] = "fallback"
            fallback_result["ta_enhancement_error"] = str(e)
            return fallback_result
        except Exception as fallback_error:
            logger.exception(f"💥 TA enhancement fallback failed: {fallback_error}")
            return {
                "request_id": request_id,
                "status": "error",
                "error": "ta-enhancement-failed",
                "details": str(e),
                "fallback_error": str(fallback_error),
                "metadata": metadata
            }

async def _handle_document_mode(payload: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle async document chunking for large inputs."""
    request_id = metadata["request_id"]
    
    try:
        job_id = await _enqueue_document_job(payload)
        
        # Add chunking metadata
        text = payload.get("text", "")
        chunked = len(text) > CHUNK_MAX_CHARS
        
        result = {
            "request_id": request_id,
            "status": "queued",
            "job_id": job_id,
            "chunked": chunked,
            "metadata": metadata
        }
        
        if chunked:
            chunks = await _chunk_large_document(text)
            result["chunk_count"] = len(chunks)
            result["estimated_processing_time"] = f"{len(chunks) * 30}s"
        
        return result
        
    except Exception as e:
        logger.exception(f"💥 Document job enqueueing failed: {e}")
        return {
            "request_id": request_id,
            "status": "error",
            "error": "enqueue-failed",
            "details": str(e),
            "metadata": metadata
        }

async def _handle_optimize_selection_mode(payload: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Handle optimize selection mode with enhanced processing."""
    request_id = metadata["request_id"]
    
    try:
        # First run basic selection
        selection_result = await _handle_selection_mode(payload, metadata)
        
        # Then enhance with TA if available and requested
        if payload.get("ta") and ENABLE_TA_ON_DEMAND:
            ta_result = await _handle_ta_enhancement_mode(payload, metadata)
            
            return {
                "request_id": request_id,
                "status": "optimized",
                "basic_suggestions": selection_result.get("suggestions"),
                "enhanced_suggestions": ta_result.get("suggestions"),
                "optimization_applied": True,
                "metadata": metadata
            }
        else:
            selection_result["status"] = "optimized"
            selection_result["optimization_applied"] = False
            return selection_result
            
    except Exception as e:
        logger.exception(f"💥 Optimize selection failed: {e}")
        return {
            "request_id": request_id,
            "status": "error",
            "error": "optimization-failed",
            "details": str(e),
            "metadata": metadata
        }

# ===== SHADOW WORKER =====
async def _trigger_shadow_worker(payload: Dict[str, Any], mode: str) -> Optional[Dict[str, Any]]:
    """Trigger shadow worker for A/B comparison studies."""
    try:
        shadow_id = str(uuid.uuid4())
        logger.info(f"🔬 Shadow worker triggered: {shadow_id} mode={mode}")
        
        # In a real implementation, this would queue a background comparison job
        # For now, return metadata about the shadow execution
        return {
            "shadow_id": shadow_id,
            "triggered": True,
            "mode": mode,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "queued"
        }
        
    except Exception as e:
        logger.warning(f"⚠️ Shadow worker trigger failed: {e}")
        return {
            "triggered": False,
            "error": str(e)
        }

# ===== INITIALIZATION =====
# Log controller information on import
try:
    # We need to define the function before we can check it
    log_hybrid_controller_info()
except NameError:
    # Function not yet defined, will be called after module load
    pass