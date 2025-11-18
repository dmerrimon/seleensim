#!/usr/bin/env python3
"""
Legacy Pipeline Wrapper - Production RAG with Pinecone + PubMedBERT
Provides unified entry point for the enterprise AI pipeline
"""

import os
import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Global service instance (initialized on first use)
_legacy_service = None
_service_lock = asyncio.Lock()

# Feature flag for emergency rollback
ENABLE_LEGACY_PIPELINE = os.getenv("ENABLE_LEGACY_PIPELINE", "true").lower() == "true"

# Circuit breaker settings
MAX_TIMEOUT_SECONDS = 10
FALLBACK_TO_SIMPLE_ON_ERROR = True


async def _get_or_create_legacy_service():
    """Get or create the legacy AI service (singleton pattern)"""
    global _legacy_service

    async with _service_lock:
        if _legacy_service is None:
            try:
                logger.info("🔄 Initializing legacy pipeline service...")

                # Import legacy components
                from legacy_pipeline_backup.config_loader import get_config
                from legacy_pipeline_backup.optimized_real_ai_service import OptimizedRealAIService

                # Load configuration
                config = get_config("production")

                # Create service instance
                _legacy_service = OptimizedRealAIService(config)

                logger.info("✅ Legacy pipeline initialized successfully")
                logger.info(f"   - Pinecone: {_legacy_service.enable_pinecone}")
                logger.info(f"   - PubMedBERT: {_legacy_service.enable_pubmedbert}")
                logger.info(f"   - TA Detection: {_legacy_service.enable_ta_detection}")

            except Exception as e:
                logger.error(f"❌ Legacy pipeline initialization failed: {e}")
                raise

        return _legacy_service


async def run_legacy_pipeline(
    text: str,
    ta: Optional[str] = None,
    phase: Optional[str] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run the complete legacy pipeline: TA detection → Pinecone → PubMedBERT → Azure OpenAI

    Args:
        text: Protocol text to analyze
        ta: Optional therapeutic area hint (if known)
        phase: Optional study phase (Phase I, II, III, IV)
        request_id: Request tracking ID

    Returns:
        Dict with format:
        {
            "request_id": str,
            "model_path": "legacy_pipeline",
            "result": {
                "suggestions": List[Dict],
                "metadata": Dict
            }
        }
    """
    start_time = time.time()
    request_id = request_id or f"legacy_{int(time.time() * 1000)}"

    try:
        # Check feature flag
        if not ENABLE_LEGACY_PIPELINE:
            logger.warning(f"⚠️ Legacy pipeline disabled by feature flag (request: {request_id})")
            raise ValueError("Legacy pipeline disabled. Set ENABLE_LEGACY_PIPELINE=true to enable.")

        logger.info(f"🚀 Legacy pipeline start: {request_id} (text_len={len(text)})")

        # Get service instance
        service = await _get_or_create_legacy_service()

        # Prepare options
        options = {
            "therapeutic_area": ta,
            "study_phase": phase,
            "request_id": request_id
        }

        # Call legacy analysis with timeout
        try:
            suggestions, metadata = await asyncio.wait_for(
                service.analyze_comprehensive(text, options),
                timeout=MAX_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            logger.error(f"⏱️ Legacy pipeline timeout after {MAX_TIMEOUT_SECONDS}s (request: {request_id})")
            raise

        # Convert suggestions to dict format
        suggestions_list = []
        for suggestion in suggestions:
            suggestions_list.append({
                "id": f"legacy_{len(suggestions_list) + 1}",
                "type": suggestion.type,
                "subtype": suggestion.subtype,
                "text": suggestion.originalText,
                "suggestion": suggestion.suggestedText,
                "rationale": suggestion.rationale,
                "confidence": 0.9 if suggestion.backendConfidence == "high" else 0.7,
                "sources": [
                    src for src in [
                        suggestion.fdaReference,
                        suggestion.emaReference,
                        suggestion.guidanceSource
                    ] if src
                ],
                "metadata": {
                    "readability_score": suggestion.readabilityScore,
                    "operational_impact": suggestion.operationalImpact,
                    "retention_risk": suggestion.retentionRisk
                }
            })

        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)

        # Add pipeline metadata
        metadata["pipeline_used"] = "legacy_pipeline"
        metadata["pinecone_enabled"] = service.enable_pinecone
        metadata["pubmedbert_enabled"] = service.enable_pubmedbert
        metadata["ta_detection_enabled"] = service.enable_ta_detection
        metadata["latency_ms"] = latency_ms
        metadata["request_id"] = request_id
        metadata["timestamp"] = datetime.utcnow().isoformat()

        logger.info(f"✅ Legacy pipeline complete: {request_id} ({latency_ms}ms, {len(suggestions_list)} suggestions)")

        return {
            "request_id": request_id,
            "model_path": "legacy_pipeline",
            "result": {
                "suggestions": suggestions_list,
                "metadata": metadata
            }
        }

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)

        logger.error(f"💥 Legacy pipeline failed: {request_id} ({latency_ms}ms) - {type(e).__name__}: {e}")

        # Emit telemetry for fallback
        logger.warning(f"🔄 Fallback triggered for request: {request_id}")

        # Re-raise for handling by caller
        raise


async def run_legacy_pipeline_with_fallback(
    text: str,
    ta: Optional[str] = None,
    phase: Optional[str] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run legacy pipeline with automatic fallback to simple mode on failure

    This provides a safer entry point that won't fail the entire request
    if legacy pipeline has issues.
    """
    try:
        return await run_legacy_pipeline(text, ta, phase, request_id)

    except Exception as e:
        logger.error(f"❌ Legacy pipeline failed, attempting fallback: {e}")

        if not FALLBACK_TO_SIMPLE_ON_ERROR:
            raise

        # Try to fallback to simple handler
        try:
            from recommend_simple import recommend_language_simple, SimpleRecommendRequest

            logger.info("🔄 Falling back to simple pipeline...")

            simple_request = SimpleRecommendRequest(
                text=text,
                ta=ta,
                phase=phase
            )

            result = await recommend_language_simple(simple_request)

            # Convert Pydantic model to dict
            result_dict = result.model_dump() if hasattr(result, 'model_dump') else result.dict()

            # Add fallback metadata
            result_dict["metadata"]["pipeline_used"] = "simple_pipeline_fallback"
            result_dict["metadata"]["fallback_reason"] = str(e)
            result_dict["metadata"]["legacy_pipeline_failed"] = True

            return {
                "request_id": request_id or f"fallback_{int(time.time() * 1000)}",
                "model_path": "simple_fallback",
                "result": result_dict
            }

        except Exception as fallback_error:
            logger.error(f"💥 Fallback also failed: {fallback_error}")
            raise


# Export main function
__all__ = ["run_legacy_pipeline", "run_legacy_pipeline_with_fallback"]
