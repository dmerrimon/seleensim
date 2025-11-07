#!/usr/bin/env python3
"""
Adapter for ta_aware_retrieval.py
Routes to legacy pipeline only when USE_SIMPLE_AZURE_PROMPT=false
"""

import os
import logging

logger = logging.getLogger(__name__)

# TODO: legacy pipeline — safe mode; remove after validation
# This adapter routes to the complex TA-aware retrieval when USE_SIMPLE_AZURE_PROMPT=false

def should_use_legacy_pipeline() -> bool:
    """Check if we should use legacy pipeline based on environment flag"""
    return os.getenv("USE_SIMPLE_AZURE_PROMPT", "true").lower() != "true"

if should_use_legacy_pipeline():
    logger.info("🔄 RETRIEVAL ADAPTER: Using legacy TA-aware retrieval system")
    try:
        from legacy_pipeline_backup.ta_aware_retrieval import (
            TAwareRetrievalSystem,
            ProtocolExemplar,
            RetrievalResult,
            EndpointSuggestion,
            create_ta_retrieval_system
        )
        logger.info("✅ RETRIEVAL ADAPTER: Legacy TA-aware retrieval imported successfully")
    except ImportError as e:
        logger.error(f"❌ RETRIEVAL ADAPTER: Failed to import legacy retrieval: {e}")
        raise ImportError(f"Legacy TA-aware retrieval not available: {e}")
else:
    logger.info("🚀 RETRIEVAL ADAPTER: TA-aware retrieval disabled in simple mode")
    # Simple stubs when not using legacy pipeline
    from dataclasses import dataclass
    from typing import Dict, List, Any
    
    @dataclass
    class ProtocolExemplar:
        """Stub for protocol exemplar"""
        id: str
        text: str
        therapeutic_area: str
        subindication: str
        phase: str
        section_type: str
        source: str
        metadata: Dict[str, Any]
    
    @dataclass
    class RetrievalResult:
        """Stub for retrieval result"""
        exemplar: ProtocolExemplar
        relevance_score: float
        ta_match_score: float
        section_match_score: float
    
    @dataclass
    class EndpointSuggestion:
        """Stub for endpoint suggestion"""
        endpoint_text: str
        endpoint_type: str
        measurement_method: str
        frequency: str
        rationale: str
        regulatory_precedent: str
        source_exemplars: List[str]
        confidence: float
    
    class TAwareRetrievalSystem:
        """Stub class when TA-aware retrieval is disabled"""
        def __init__(self):
            logger.info("🚀 RETRIEVAL ADAPTER: TA-aware retrieval stub initialized")
        
        def retrieve_exemplars(self, *args, **kwargs) -> List[RetrievalResult]:
            logger.warning("⚠️ RETRIEVAL ADAPTER: TA-aware retrieval disabled")
            return []
        
        def suggest_endpoints(self, *args, **kwargs) -> List[EndpointSuggestion]:
            logger.warning("⚠️ RETRIEVAL ADAPTER: Endpoint suggestions disabled")
            return []
    
    def create_ta_retrieval_system() -> TAwareRetrievalSystem:
        """Factory function for stub retrieval system"""
        return TAwareRetrievalSystem()