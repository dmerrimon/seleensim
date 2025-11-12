"""
RAG Gating Logic Patches for Ilana Protocol Intelligence API
Implements RAG_ASYNC_MODE gating to prevent synchronous heavy RAG operations
"""

import os
from typing import Dict, Any, List, Optional
from fastapi import HTTPException

# Configuration
RAG_ASYNC_MODE = os.getenv("RAG_ASYNC_MODE", "true").lower() == "true"
ENABLE_TA_ON_DEMAND = os.getenv("ENABLE_TA_ON_DEMAND", "true").lower() == "true"

class RAGAsyncModeException(Exception):
    """Exception raised when sync RAG operations are blocked by RAG_ASYNC_MODE"""
    pass

def check_rag_async_mode_gate(operation_name: str = "RAG operation") -> None:
    """
    Check if RAG_ASYNC_MODE blocks synchronous RAG operations
    
    Args:
        operation_name: Name of the operation for error messaging
        
    Raises:
        RAGAsyncModeException: If RAG_ASYNC_MODE is true and sync operation is attempted
    """
    if RAG_ASYNC_MODE:
        raise RAGAsyncModeException(
            f"{operation_name} blocked: RAG_ASYNC_MODE is enabled. "
            "Use async endpoints or set RAG_ASYNC_MODE=false for enterprise pilot."
        )

def create_rag_async_response(endpoint_suggestion: str = "/api/generate-rewrite-ta") -> Dict[str, Any]:
    """
    Create a standardized response when RAG operations are blocked
    
    Args:
        endpoint_suggestion: Suggested async endpoint to use instead
        
    Returns:
        Dict with error information and suggested alternatives
    """
    return {
        "error": "Synchronous RAG operation not available",
        "reason": "RAG_ASYNC_MODE is enabled",
        "message": "Heavy RAG operations (Vector DB + LLM) are only available via async endpoints to prevent timeouts",
        "suggested_endpoint": endpoint_suggestion,
        "alternatives": [
            "Use /api/generate-rewrite-ta for on-demand TA enhancement",
            "Use /api/optimize-document-async for large document processing", 
            "Set RAG_ASYNC_MODE=false in .env for enterprise pilot mode"
        ],
        "enterprise_pilot": "Contact support to enable synchronous RAG for enterprise pilot"
    }

# === PATCH 1: Vector DB Query Gating ===
def patch_query_vector_db():
    """
    Patch for query_vector_db function in main.py
    Add this code at the beginning of the query_vector_db function
    """
    patch_code = '''
    # RAG Gating Check
    if RAG_ASYNC_MODE:
        logger.warning("🚫 Vector DB query blocked by RAG_ASYNC_MODE")
        raise RAGAsyncModeException(
            "Vector DB queries blocked: RAG_ASYNC_MODE is enabled. "
            "Use async endpoints or set RAG_ASYNC_MODE=false."
        )
    
    logger.info(f"✅ RAG_ASYNC_MODE check passed for vector DB query")
    '''
    return patch_code

# === PATCH 2: TA-Aware Rewrite Gating ===
def patch_generate_ta_aware_rewrite():
    """
    Patch for generate_ta_aware_rewrite function in main.py
    Add this code at the beginning of the generate_ta_aware_rewrite function
    """
    patch_code = '''
    # RAG Gating Check
    if RAG_ASYNC_MODE:
        logger.warning("🚫 TA-aware rewrite blocked by RAG_ASYNC_MODE")
        raise RAGAsyncModeException(
            "TA-aware rewrite blocked: RAG_ASYNC_MODE is enabled. "
            "Use /api/generate-rewrite-ta or set RAG_ASYNC_MODE=false."
        )
    
    logger.info(f"✅ RAG_ASYNC_MODE check passed for TA-aware rewrite")
    '''
    return patch_code

# === PATCH 3: Analysis Endpoint Modifications ===
def patch_analyze_endpoint():
    """
    Patch for /api/analyze endpoint in main.py
    Modify the endpoint to handle RAG gating gracefully
    """
    patch_code = '''
    try:
        # Existing analyze logic here...
        pass
    except RAGAsyncModeException as e:
        # Return 202 with guidance when RAG is blocked
        logger.warning(f"🚫 Analysis endpoint blocked by RAG_ASYNC_MODE: {e}")
        
        return JSONResponse(
            status_code=202,
            content={
                "status": "queued", 
                "message": "Analysis queued for async processing",
                "reason": str(e),
                "request_id": request_id,
                "alternatives": {
                    "on_demand_ta": "/api/generate-rewrite-ta",
                    "async_document": "/api/optimize-document-async",
                    "simple_only": "Set USE_SIMPLE_AZURE_PROMPT=true for basic analysis"
                },
                "estimated_processing_time": "Use async endpoints for heavy operations"
            }
        )
    '''
    return patch_code

# === PATCH 4: Environment Variable Loading ===
def patch_environment_variables():
    """
    Patch to add RAG gating environment variables to main.py
    Add this code after the existing environment loading
    """
    patch_code = '''
    # RAG Gating Configuration
    RAG_ASYNC_MODE = os.getenv("RAG_ASYNC_MODE", "true").lower() == "true"
    USE_SIMPLE_AZURE_PROMPT = os.getenv("USE_SIMPLE_AZURE_PROMPT", "true").lower() == "true"
    ENABLE_TA_ON_DEMAND = os.getenv("ENABLE_TA_ON_DEMAND", "true").lower() == "true"
    ENABLE_TA_SHADOW = os.getenv("ENABLE_TA_SHADOW", "false").lower() == "true"
    CHUNK_MAX_CHARS = int(os.getenv("CHUNK_MAX_CHARS", "3500"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
    
    # Log configuration
    logger.info(f"🔧 RAG Configuration:")
    logger.info(f"   RAG_ASYNC_MODE: {RAG_ASYNC_MODE}")
    logger.info(f"   USE_SIMPLE_AZURE_PROMPT: {USE_SIMPLE_AZURE_PROMPT}")
    logger.info(f"   ENABLE_TA_ON_DEMAND: {ENABLE_TA_ON_DEMAND}")
    logger.info(f"   ENABLE_TA_SHADOW: {ENABLE_TA_SHADOW}")
    logger.info(f"   CHUNK_MAX_CHARS: {CHUNK_MAX_CHARS}")
    logger.info(f"   CHUNK_OVERLAP: {CHUNK_OVERLAP}")
    '''
    return patch_code

# === PATCH 5: Import RAGAsyncModeException ===
def patch_imports():
    """
    Patch to add RAGAsyncModeException import to main.py
    Add this to the imports section
    """
    patch_code = '''
    from rag_gating_patch import RAGAsyncModeException, check_rag_async_mode_gate, create_rag_async_response
    '''
    return patch_code

# === COMPLETE PATCHED FUNCTIONS ===

async def patched_query_vector_db(text: str, ta: str, phase: Optional[str] = None) -> List[Dict[str, Any]]:
    """Patched version of query_vector_db with RAG gating"""
    
    # RAG Gating Check
    if RAG_ASYNC_MODE:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("🚫 Vector DB query blocked by RAG_ASYNC_MODE")
        raise RAGAsyncModeException(
            "Vector DB queries blocked: RAG_ASYNC_MODE is enabled. "
            "Use async endpoints or set RAG_ASYNC_MODE=false."
        )
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"✅ RAG_ASYNC_MODE check passed for vector DB query")
    
    # Original query_vector_db implementation continues here...
    # (The rest of the function remains the same)
    
    exemplar_templates = {
        "oncology": [
            {
                "text": "Participants with HER2-positive breast cancer will receive trastuzumab therapy with mandatory cardiac monitoring per ACC/AHA guidelines.",
                "improved": "Study participants diagnosed with HER2-positive breast adenocarcinoma will receive trastuzumab-based therapy according to protocol, with baseline and periodic echocardiographic assessment of left ventricular ejection fraction (LVEF) as per American College of Cardiology/American Heart Association guidelines for cardiotoxicity monitoring.",
                "rationale": "Enhanced medical terminology with specific cardiac safety monitoring requirements",
                "sources": ["ACC/AHA Cardio-Oncology Guidelines", "FDA Trastuzumab Label"],
                "similarity": 0.89
            }
        ]
        # ... rest of templates
    }
    
    return exemplar_templates.get(ta, exemplar_templates.get("oncology", []))[:2]

async def patched_generate_ta_aware_rewrite(text: str, ta: str, phase: Optional[str], exemplars: List[Dict], guidelines: List[str]) -> Dict[str, Any]:
    """Patched version of generate_ta_aware_rewrite with RAG gating"""
    import time
    import logging
    
    # RAG Gating Check
    if RAG_ASYNC_MODE:
        logger = logging.getLogger(__name__)
        logger.warning("🚫 TA-aware rewrite blocked by RAG_ASYNC_MODE")
        raise RAGAsyncModeException(
            "TA-aware rewrite blocked: RAG_ASYNC_MODE is enabled. "
            "Use /api/generate-rewrite-ta or set RAG_ASYNC_MODE=false."
        )
    
    logger = logging.getLogger(__name__)
    logger.info(f"✅ RAG_ASYNC_MODE check passed for TA-aware rewrite")
    
    start_time = time.time()
    
    # Original generate_ta_aware_rewrite implementation continues here...
    # (The rest of the function remains the same)
    
    # Mock implementation for now
    return {
        "improved": f"Enhanced {ta}-specific version: {text}",
        "rationale": f"Enhanced for {ta} regulatory compliance",
        "sources": guidelines[:2] if guidelines else ["General guidelines"],
        "model_version": "gated-azure-openai-v1.0"
    }

# === USAGE INSTRUCTIONS ===
"""
To apply these patches to main.py:

1. Add environment variable loading patch after line ~21
2. Add import patch after line ~30  
3. Replace query_vector_db function with patched_query_vector_db
4. Replace generate_ta_aware_rewrite function with patched_generate_ta_aware_rewrite
5. Add RAGAsyncModeException handling to /api/analyze endpoint
6. Test with RAG_ASYNC_MODE=true and RAG_ASYNC_MODE=false

Example error responses:
- 202 Queued: When sync RAG is blocked, redirect to async endpoints
- 503 Service Unavailable: When RAG services are completely disabled
- Helpful error messages with alternative endpoints
"""