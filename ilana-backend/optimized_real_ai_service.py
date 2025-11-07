#!/usr/bin/env python3
"""
Adapter for optimized_real_ai_service.py
Routes to legacy pipeline only when USE_SIMPLE_AZURE_PROMPT=false
"""

import os
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# TODO: legacy pipeline — safe mode; remove after validation
# This adapter routes to the complex legacy pipeline when USE_SIMPLE_AZURE_PROMPT=false
# The legacy pipeline is preserved in legacy_pipeline_backup/ for safety

def should_use_legacy_pipeline() -> bool:
    """Check if we should use legacy pipeline based on environment flag"""
    return os.getenv("USE_SIMPLE_AZURE_PROMPT", "true").lower() != "true"

if should_use_legacy_pipeline():
    logger.info("🔄 ADAPTER: Routing to legacy enterprise pipeline")
    try:
        # Import from legacy backup location
        from legacy_pipeline_backup.optimized_real_ai_service import (
            OptimizedRealAIService,
            InlineSuggestion, 
            TADetectionResult,
            create_optimized_real_ai_service
        )
        logger.info("✅ ADAPTER: Legacy pipeline imported successfully")
    except ImportError as e:
        logger.error(f"❌ ADAPTER: Failed to import legacy pipeline: {e}")
        raise ImportError(f"Legacy pipeline not available: {e}")
else:
    logger.info("🚀 ADAPTER: Simple mode active, legacy pipeline bypassed")
    # Provide minimal stubs for when legacy is not used
    from dataclasses import dataclass
    from typing import Optional
    
    @dataclass 
    class InlineSuggestion:
        type: str
        subtype: Optional[str] = None
        originalText: str = ""
        suggestedText: str = ""
        rationale: str = ""
        complianceRationale: str = ""
        fdaReference: Optional[str] = None
        emaReference: Optional[str] = None
        guidanceSource: Optional[str] = None
        readabilityScore: Optional[float] = None
        operationalImpact: Optional[str] = None
        retentionRisk: Optional[str] = None
        enrollmentImpact: Optional[str] = None
        backendConfidence: Optional[str] = None
        range: Dict[str, int] = None

    @dataclass
    class TADetectionResult:
        therapeutic_area: str
        subindication: str
        phase: str
        confidence: float
        confidence_scores: Dict[str, float]
        detected_keywords: List[str]
        reasoning: str

    class OptimizedRealAIService:
        """Stub class when legacy pipeline is not used"""
        def __init__(self, config):
            logger.warning("⚠️ ADAPTER: OptimizedRealAIService stub - legacy pipeline disabled")
            
        async def analyze_comprehensive(self, content: str, options: Dict[str, Any]) -> Tuple[List[InlineSuggestion], Dict[str, Any]]:
            logger.warning("⚠️ ADAPTER: Legacy analysis called but disabled - returning empty results")
            return [], {"adapter_mode": "simple", "legacy_disabled": True}

    def create_optimized_real_ai_service(config):
        """Factory function stub when legacy pipeline is not used"""
        logger.warning("⚠️ ADAPTER: Creating stub service - legacy pipeline disabled")
        return OptimizedRealAIService(config)