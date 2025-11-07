#!/usr/bin/env python3
"""
Adapter for therapeutic_area_classifier.py
Routes to legacy pipeline only when USE_SIMPLE_AZURE_PROMPT=false
"""

import os
import logging

logger = logging.getLogger(__name__)

# TODO: legacy pipeline — safe mode; remove after validation
# This adapter routes to the complex TA classification when USE_SIMPLE_AZURE_PROMPT=false

def should_use_legacy_pipeline() -> bool:
    """Check if we should use legacy pipeline based on environment flag"""
    return os.getenv("USE_SIMPLE_AZURE_PROMPT", "true").lower() != "true"

if should_use_legacy_pipeline():
    logger.info("🔄 TA ADAPTER: Using legacy therapeutic area classification")
    try:
        from legacy_pipeline_backup.therapeutic_area_classifier import (
            TherapeuticAreaClassifier,
            TADetectionResult,
            create_ta_classifier
        )
        logger.info("✅ TA ADAPTER: Legacy TA classifier imported successfully")
    except ImportError as e:
        logger.error(f"❌ TA ADAPTER: Failed to import legacy TA classifier: {e}")
        raise ImportError(f"Legacy TA classifier not available: {e}")
else:
    logger.info("🚀 TA ADAPTER: Using simple TA classification mode")
    # Simple TA classification stubs
    from dataclasses import dataclass
    from typing import Dict, List
    
    @dataclass
    class TADetectionResult:
        """Simplified TA detection result"""
        therapeutic_area: str
        subindication: str
        phase: str
        confidence: float
        confidence_scores: Dict[str, float]
        detected_keywords: List[str]
        reasoning: str
    
    class TherapeuticAreaClassifier:
        """Simplified TA classifier"""
        def __init__(self):
            logger.info("🚀 TA ADAPTER: Simple TA classifier initialized")
        
        def detect_therapeutic_area(self, text: str) -> TADetectionResult:
            """Simple keyword-based TA detection"""
            text_lower = text.lower()
            
            # Simple keyword mapping
            if any(word in text_lower for word in ["cancer", "tumor", "oncology"]):
                ta = "oncology"
            elif any(word in text_lower for word in ["heart", "cardiac", "cardiovascular"]):
                ta = "cardiovascular" 
            elif any(word in text_lower for word in ["diabetes", "insulin", "glucose"]):
                ta = "endocrinology"
            elif any(word in text_lower for word in ["brain", "neurological", "seizure"]):
                ta = "neurology"
            else:
                ta = "general_medicine"
            
            return TADetectionResult(
                therapeutic_area=ta,
                subindication="unknown",
                phase="III",
                confidence=0.8,
                confidence_scores={ta: 0.8},
                detected_keywords=[],
                reasoning="Simple keyword-based detection"
            )
    
    def create_ta_classifier() -> TherapeuticAreaClassifier:
        """Factory function for simple TA classifier"""
        return TherapeuticAreaClassifier()