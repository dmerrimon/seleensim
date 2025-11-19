#!/usr/bin/env python3
"""
Ilana Protocol Intelligence API Service - Enterprise Production Version
Full enterprise AI stack with Azure OpenAI + Pinecone + PubMedBERT
"""

import os
import sys
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
# Note: In managed deployments (Render, Heroku, AWS, etc.), environment variables
# should be set via the platform dashboard, not via .env files. This loader attempts
# to read from file but falls back gracefully to system environment variables.
env_path = os.getenv(
    "PRODUCTION_ENV_PATH",
    str(Path(__file__).parent / "config" / "environments" / "production.env")
)
env_path = Path(env_path)

if env_path.exists():
    load_dotenv(env_path)
    logging.info(f"✅ Loaded environment from {env_path}")
else:
    logging.info(f"Production env file not found at {env_path}; falling back to environment variables.")

# RAG Gating Configuration
RAG_ASYNC_MODE = os.getenv("RAG_ASYNC_MODE", "true").lower() == "true"
RAG_ASYNC_ALLOW_SYNC = os.getenv("RAG_ASYNC_ALLOW_SYNC", "false").lower() == "true"
USE_SIMPLE_AZURE_PROMPT = os.getenv("USE_SIMPLE_AZURE_PROMPT", "true").lower() == "true"
ENABLE_TA_ON_DEMAND = os.getenv("ENABLE_TA_ON_DEMAND", "true").lower() == "true"
ENABLE_TA_SHADOW = os.getenv("ENABLE_TA_SHADOW", "false").lower() == "true"
ENABLE_DOCUMENT_ANALYSIS = os.getenv("ENABLE_DOCUMENT_ANALYSIS", "false").lower() == "true"
CHUNK_MAX_CHARS = int(os.getenv("CHUNK_MAX_CHARS", "3500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uuid
import inspect
import json
import asyncio
import time

# Add parent directory to path for enterprise components
parent_path = Path(__file__).parent.parent
sys.path.insert(0, str(parent_path))
sys.path.insert(0, str(parent_path / "config"))

# Import enterprise AI components
try:
    from config_loader import get_config, IlanaConfig
    from optimized_real_ai_service import create_optimized_real_ai_service, OptimizedRealAIService, InlineSuggestion
    ENTERPRISE_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("✅ Enterprise AI components loaded successfully")
except ImportError as e:
    ENTERPRISE_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(f"⚠️ Enterprise AI components not available: {e}")

# Import RL feedback module
from rl_feedback import (
    RLFeedbackEvent,
    ReinforcementEvent,
    validate_phi_redacted,
    store_feedback_event,
    store_reinforcement_event
)

# Fallback InlineSuggestion
from dataclasses import dataclass
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# RAG Gating Exception
class RAGAsyncModeException(Exception):
    """Exception raised when sync RAG operations are blocked by RAG_ASYNC_MODE"""
    pass

def check_rag_async_mode_gate(operation_name: str = "RAG operation") -> None:
    """Check if RAG_ASYNC_MODE blocks synchronous RAG operations"""
    if RAG_ASYNC_MODE and not RAG_ASYNC_ALLOW_SYNC:
        raise RAGAsyncModeException(
            f"{operation_name} blocked: RAG_ASYNC_MODE is enabled. "
            "Use async endpoints or set RAG_ASYNC_ALLOW_SYNC=true in config."
        )
    elif RAG_ASYNC_MODE and RAG_ASYNC_ALLOW_SYNC:
        logger.warning(
            f"⚠️ {operation_name} executing synchronously with RAG_ASYNC_ALLOW_SYNC=true. "
            "This may cause timeouts. Not recommended in production."
        )

# Log RAG configuration
logger.warning("🚨🚨🚨 [MAIN_PY_DEPLOYMENT_MARKER_NOV15_2024] Application starting 🚨🚨🚨")
logger.info(f"🔧 RAG Configuration:")
logger.info(f"   RAG_ASYNC_MODE: {RAG_ASYNC_MODE}")
logger.info(f"   RAG_ASYNC_ALLOW_SYNC: {RAG_ASYNC_ALLOW_SYNC}")
logger.info(f"   USE_SIMPLE_AZURE_PROMPT: {USE_SIMPLE_AZURE_PROMPT}")
logger.info(f"   ENABLE_TA_ON_DEMAND: {ENABLE_TA_ON_DEMAND}")
logger.info(f"   ENABLE_TA_SHADOW: {ENABLE_TA_SHADOW}")
logger.info(f"   ENABLE_DOCUMENT_ANALYSIS: {ENABLE_DOCUMENT_ANALYSIS}")
logger.info(f"   CHUNK_MAX_CHARS: {CHUNK_MAX_CHARS}")
logger.info(f"   CHUNK_OVERLAP: {CHUNK_OVERLAP}")

# Explain RAG_ASYNC_MODE behavior
if RAG_ASYNC_MODE and not RAG_ASYNC_ALLOW_SYNC:
    logger.info(
        "ℹ️  RAG_ASYNC_MODE=true — Synchronous TA-heavy operations (vector DB queries, "
        "TA-aware rewrites) will be queued and return HTTP 202. This prevents timeouts "
        "in production. To allow synchronous operations for testing, set "
        "RAG_ASYNC_ALLOW_SYNC=true (not recommended in production)."
    )
elif RAG_ASYNC_MODE and RAG_ASYNC_ALLOW_SYNC:
    logger.warning(
        "⚠️ RAG_ASYNC_ALLOW_SYNC=true — Synchronous RAG operations are permitted despite "
        "RAG_ASYNC_MODE=true. This may cause request timeouts. Only use for testing or "
        "debugging. Not recommended in production environments."
    )
else:
    logger.info(
        "ℹ️  RAG_ASYNC_MODE=false — All operations including TA-heavy vector DB queries "
        "will execute synchronously. Suitable for development/testing with small datasets."
    )

# Global enterprise AI service
enterprise_ai_service: Optional[OptimizedRealAIService] = None

# Request/Response Models  
class ComprehensiveAnalysisRequest(BaseModel):
    """Request model for comprehensive analysis"""
    text: str = Field(..., min_length=10, description="Text to analyze")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Analysis options")
    chunk_index: Optional[int] = Field(0, description="Chunk index for processing")
    total_chunks: Optional[int] = Field(1, description="Total number of chunks")

class TADetectRequest(BaseModel):
    """Request model for TA detection"""
    content: str

class TextEnhanceRequest(BaseModel):
    """Request model for text enhancement"""
    original_text: str
    therapeutic_area: Optional[str] = "general_medicine"
    enhancement_type: Optional[str] = "clarity_and_compliance"

class TARecommendationsRequest(BaseModel):
    """Request model for TA recommendations"""
    therapeutic_area: str
    protocol_type: Optional[str] = "clinical_trial"

class ExplainSuggestionRequest(BaseModel):
    """Request model for suggestion explanation expansion"""
    suggestion_id: str = Field(..., description="ID of the suggestion to explain")
    ta: Optional[str] = Field(None, description="Therapeutic area")
    analysis_mode: Optional[str] = Field("legacy", description="Analysis mode used")

# FastAPI app
app = FastAPI(
    title="Ilana Protocol Intelligence API",
    description="AI-powered clinical protocol analysis and optimization with real medical intelligence",
    version="1.3.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS for development and Office Add-ins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",  # Allow all origins for dev
        "https://*.office.com",
        "https://*.microsoft.com", 
        "https://*.sharepoint.com",
        "https://localhost:*",
        "http://localhost:*"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Global error handlers for structured error responses
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with structured error response"""
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    
    error_response = {
        "error_code": f"HTTP_{exc.status_code}",
        "message": exc.detail,
        "request_id": request_id,
        "timestamp": datetime.utcnow().isoformat(),
        "path": str(request.url.path)
    }
    
    logger.error(f"HTTP Exception {exc.status_code}: {exc.detail} - Request: {request_id}")
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions with structured error response"""
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    
    error_response = {
        "error_code": "INTERNAL_ERROR",
        "message": "An internal server error occurred. Please try again later.",
        "request_id": request_id,
        "timestamp": datetime.utcnow().isoformat(),
        "path": str(request.url.path)
    }
    
    logger.error(f"Unhandled exception: {str(exc)} - Request: {request_id}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=error_response
    )

@app.middleware("http")
async def add_request_id_middleware(request: Request, call_next):
    """Add request ID to all requests for tracking"""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Add to response headers
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

@app.on_event("startup")
async def startup_event():
    """Initialize enterprise AI service on startup"""
    global enterprise_ai_service
    
    logger.info("🚀 Starting Enterprise Ilana AI Service")
    
    if ENTERPRISE_AVAILABLE:
        try:
            # Debug environment variables
            logger.info(f"🔍 Environment check - AZURE_OPENAI_ENDPOINT: {os.getenv('AZURE_OPENAI_ENDPOINT', 'NOT SET')[:50]}...")
            logger.info(f"🔍 Environment check - AZURE_OPENAI_API_KEY: {'SET' if os.getenv('AZURE_OPENAI_API_KEY') else 'NOT SET'}")
            logger.info(f"🔍 Environment check - AZURE_OPENAI_DEPLOYMENT: {os.getenv('AZURE_OPENAI_DEPLOYMENT', 'NOT SET')}")
            logger.info(f"🔍 Environment check - ENABLE_AZURE_OPENAI: {os.getenv('ENABLE_AZURE_OPENAI', 'NOT SET')}")
            
            # Load enterprise configuration
            config = get_config("production")
            enterprise_ai_service = create_optimized_real_ai_service(config)
            logger.info("✅ Enterprise AI service initialized with full stack (Azure OpenAI + Pinecone + PubMedBERT)")
        except Exception as e:
            logger.warning(f"⚠️ Enterprise AI service initialization failed: {e}")
            logger.warning(f"⚠️ Full error details: {str(e)}")
            enterprise_ai_service = None
    else:
        logger.warning("⚠️ Enterprise AI components not available, using fallback analysis")
        enterprise_ai_service = None
    
    logger.info("✅ Enterprise AI production deployment ready with full stack")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Ilana Protocol Intelligence API",
        "version": "1.2.0",
        "status": "running",
        "deployment": "production",
        "features": [
            "Protocol Issue Detection",
            "Therapeutic Area Classification",
            "Text Enhancement",
            "Compliance Analysis",
            "Feasibility Assessment"
        ]
    }

@app.get("/taskpane.html")
async def serve_taskpane():
    """Serve the Office add-in taskpane HTML"""
    return FileResponse("taskpane.html", media_type="text/html")

@app.get("/ilana-comprehensive.js")
async def serve_js():
    """Serve the taskpane JavaScript"""
    return FileResponse("ilana-comprehensive.js", media_type="application/javascript")

@app.get("/ilana-telemetry.js")
async def serve_telemetry_js():
    """Serve the telemetry JavaScript module"""
    return FileResponse("ilana-telemetry.js", media_type="application/javascript")

@app.get("/style-comprehensive.css")
async def serve_css():
    """Serve the taskpane CSS"""
    return FileResponse("style-comprehensive.css", media_type="text/css")

@app.get("/health")
async def health_check():
    """Basic health check endpoint - lightweight for load balancers"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.2.0",
        "deployment": "production",
        "services": {
            "api": "active",
            "cors": "enabled",
            "analysis": "active"
        }
    }


@app.get("/health/services")
async def health_check_services():
    """Detailed health check for Pinecone, PubMedBERT, and Azure OpenAI"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }

    # Check Azure OpenAI
    try:
        from openai import AzureOpenAI
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        azure_key = os.getenv("AZURE_OPENAI_API_KEY")

        if azure_endpoint and azure_key:
            health_status["services"]["azure_openai"] = {
                "status": "configured",
                "endpoint": azure_endpoint[:30] + "...",
                "deployment": os.getenv("AZURE_OPENAI_DEPLOYMENT", "unknown"),
                "enabled": os.getenv("ENABLE_AZURE_OPENAI", "false")
            }
        else:
            health_status["services"]["azure_openai"] = {
                "status": "not_configured",
                "error": "Missing AZURE_OPENAI_ENDPOINT or API key"
            }
    except Exception as e:
        health_status["services"]["azure_openai"] = {
            "status": "error",
            "error": str(e)
        }

    # Check Pinecone
    try:
        pinecone_key = os.getenv("PINECONE_API_KEY")
        pinecone_index = os.getenv("PINECONE_INDEX_NAME")

        if pinecone_key and pinecone_index:
            health_status["services"]["pinecone"] = {
                "status": "configured",
                "index_name": pinecone_index,
                "enabled": os.getenv("ENABLE_PINECONE_INTEGRATION", "false")
            }
        else:
            health_status["services"]["pinecone"] = {
                "status": "not_configured",
                "error": "Missing PINECONE_API_KEY or INDEX_NAME"
            }
    except Exception as e:
        health_status["services"]["pinecone"] = {
            "status": "error",
            "error": str(e)
        }

    # Check PubMedBERT
    try:
        pubmedbert_endpoint = os.getenv("PUBMEDBERT_ENDPOINT_URL")
        huggingface_key = os.getenv("HUGGINGFACE_API_KEY")

        if pubmedbert_endpoint and huggingface_key:
            health_status["services"]["pubmedbert"] = {
                "status": "configured",
                "endpoint": pubmedbert_endpoint[:40] + "...",
                "enabled": os.getenv("ENABLE_PUBMEDBERT", "true")
            }
        else:
            health_status["services"]["pubmedbert"] = {
                "status": "not_configured",
                "error": "Missing PUBMEDBERT_ENDPOINT_URL or HUGGINGFACE_API_KEY"
            }
    except Exception as e:
        health_status["services"]["pubmedbert"] = {
            "status": "error",
            "error": str(e)
        }

    # Check legacy pipeline
    health_status["services"]["legacy_pipeline"] = {
        "status": "enabled" if not USE_SIMPLE_AZURE_PROMPT else "disabled",
        "flag": f"USE_SIMPLE_AZURE_PROMPT={USE_SIMPLE_AZURE_PROMPT}",
        "components": {
            "azure_openai": health_status["services"]["azure_openai"]["status"],
            "pinecone": health_status["services"]["pinecone"]["status"],
            "pubmedbert": health_status["services"]["pubmedbert"]["status"]
        }
    }

    # Overall status
    all_healthy = all(
        svc.get("status") in ["configured", "enabled"]
        for svc in health_status["services"].values()
        if isinstance(svc, dict) and svc.get("status") != "disabled"
    )

    health_status["status"] = "healthy" if all_healthy else "degraded"

    return health_status

@app.get("/health/optimizations")
async def get_optimization_config():
    """
    Get current optimization settings (Step 3)

    Returns configuration for:
    - Pinecone vector DB query limits
    - PubMedBERT conditional usage
    - Smart skipping thresholds
    """
    from optimization_config import get_optimization_summary

    try:
        summary = get_optimization_summary()
        return {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "optimizations": summary,
            "step": "Step 3: Trim Vector DB & PubMedBERT Usage"
        }
    except Exception as e:
        logger.error(f"❌ Failed to get optimization config: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

@app.get("/health/prompts")
async def get_prompt_stats():
    """
    Get prompt optimization statistics and token usage (Step 4)

    Returns:
    - Token budgets for fast and deep paths
    - Cumulative token usage statistics
    - Cost estimates
    - Optimization impact metrics
    """
    from prompt_optimizer import get_token_stats, FAST_TOKEN_BUDGET, DEEP_TOKEN_BUDGET

    try:
        stats = get_token_stats()
        return {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "token_budgets": {
                "fast_path": FAST_TOKEN_BUDGET,
                "deep_path": DEEP_TOKEN_BUDGET
            },
            "usage": stats,
            "step": "Step 4: Prompt + Model Tuning"
        }
    except Exception as e:
        logger.error(f"❌ Failed to get prompt stats: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

@app.get("/health/resilience")
async def get_resilience_status():
    """
    Get resilience status (Step 5)

    Returns:
    - Circuit breaker states for all services
    - Retry statistics
    - Fallback usage metrics
    """
    from resilience import get_all_circuit_breaker_states

    try:
        circuit_breakers = get_all_circuit_breaker_states()

        # Calculate health score
        total_breakers = len(circuit_breakers)
        closed_breakers = sum(1 for cb in circuit_breakers.values() if cb["state"] == "closed")
        health_score = (closed_breakers / total_breakers * 100) if total_breakers > 0 else 100

        overall_status = "healthy" if health_score == 100 else "degraded" if health_score >= 50 else "critical"

        return {
            "status": overall_status,
            "health_score": health_score,
            "timestamp": datetime.utcnow().isoformat(),
            "circuit_breakers": circuit_breakers,
            "configuration": {
                "circuit_breaker_threshold": os.getenv("CIRCUIT_BREAKER_THRESHOLD", "5"),
                "circuit_breaker_timeout": os.getenv("CIRCUIT_BREAKER_TIMEOUT", "60"),
                "max_retries": os.getenv("MAX_RETRIES", "3"),
                "retry_backoff_base": os.getenv("RETRY_BACKOFF_BASE", "1.0")
            },
            "step": "Step 5: Timeouts & Fallbacks"
        }
    except Exception as e:
        logger.error(f"❌ Failed to get resilience status: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

@app.get("/debug/azure-openai")
async def debug_azure_openai():
    """Debug Azure OpenAI connection"""
    debug_info = {
        "environment_check": {},
        "connection_test": {},
        "configuration": {}
    }
    
    # Check environment variables
    debug_info["environment_check"] = {
        "AZURE_OPENAI_ENDPOINT": os.getenv('AZURE_OPENAI_ENDPOINT', 'NOT SET')[:50] + '...' if os.getenv('AZURE_OPENAI_ENDPOINT') else 'NOT SET',
        "AZURE_OPENAI_API_KEY": 'SET' if os.getenv('AZURE_OPENAI_API_KEY') else 'NOT SET',
        "AZURE_OPENAI_API_KEY_LENGTH": len(os.getenv('AZURE_OPENAI_API_KEY', '')),
        "AZURE_OPENAI_DEPLOYMENT": os.getenv('AZURE_OPENAI_DEPLOYMENT', 'NOT SET'),
        "ENABLE_AZURE_OPENAI": os.getenv('ENABLE_AZURE_OPENAI', 'NOT SET')
    }
    
    # Test configuration loading
    if ENTERPRISE_AVAILABLE:
        try:
            from config_loader import get_config
            config = get_config("production")
            debug_info["configuration"] = {
                "config_loaded": True,
                "enable_azure_openai": getattr(config, 'enable_azure_openai', 'NOT SET'),
                "azure_openai_endpoint": getattr(config, 'azure_openai_endpoint', 'NOT SET')[:50] + '...' if hasattr(config, 'azure_openai_endpoint') else 'NOT SET',
                "azure_openai_deployment": getattr(config, 'azure_openai_deployment', 'NOT SET'),
                "api_key_available": bool(getattr(config, 'azure_openai_api_key', None))
            }
            
            # Test Azure OpenAI connection
            try:
                from openai import AzureOpenAI
                client = AzureOpenAI(
                    api_key=config.azure_openai_api_key,
                    api_version="2024-02-01",
                    azure_endpoint=config.azure_openai_endpoint
                )
                
                # Test models list
                models = client.models.list()
                model_count = len(list(models))
                
                debug_info["connection_test"] = {
                    "client_created": True,
                    "models_accessible": True,
                    "model_count": model_count,
                    "test_status": "SUCCESS"
                }
                
            except Exception as conn_error:
                debug_info["connection_test"] = {
                    "client_created": False,
                    "error_type": type(conn_error).__name__,
                    "error_message": str(conn_error),
                    "test_status": "FAILED"
                }
                
        except Exception as config_error:
            debug_info["configuration"] = {
                "config_loaded": False,
                "error": str(config_error)
            }
    else:
        debug_info["configuration"] = {
            "enterprise_available": False,
            "message": "Enterprise components not available"
        }
    
    return debug_info

@app.get("/debug/test-azure-ai")
async def test_azure_ai_direct():
    """Direct test of Azure OpenAI to see what it returns"""
    if not enterprise_ai_service:
        return {"error": "Enterprise AI service not available"}
    
    try:
        # Test with simple medical text
        test_text = "HER2-positive breast cancer patients will receive trastuzumab. Monitor for cardiotoxicity."
        
        from optimized_real_ai_service import TADetectionResult
        # Create mock TA detection
        ta_detection = TADetectionResult(
            therapeutic_area="oncology",
            subindication="breast_cancer", 
            phase="III",
            confidence=1.0,
            confidence_scores={"oncology": 1.0},
            detected_keywords=["her2", "breast cancer", "trastuzumab"],
            reasoning="Test data"
        )
        
        # Call the chunk analysis directly
        suggestions = await enterprise_ai_service._analyze_chunk_enterprise(
            test_text, 0, ta_detection, 
            "Test vector context from Pinecone",
            "Test PubMedBERT insights"
        )
        
        return {
            "test_text": test_text,
            "suggestions_count": len(suggestions),
            "suggestions": [
                {
                    "type": s.type,
                    "subtype": s.subtype,
                    "original": s.originalText[:100],
                    "suggested": s.suggestedText[:100],
                    "backend": s.backendConfidence
                } for s in suggestions[:3]
            ]
        }
        
    except Exception as e:
        return {"error": f"Direct Azure AI test failed: {str(e)}"}

async def simple_recommend_language(content: str, chunk_index: int = 0, total_chunks: int = 1) -> Dict[str, Any]:
    """Simple Azure OpenAI recommendation function - direct calls without complex pipeline"""
    logger.info(f"🚀 SIMPLE AI: Direct Azure OpenAI analysis for chunk {chunk_index + 1}/{total_chunks}")
    
    try:
        from openai import AzureOpenAI
        from config_loader import get_config
        
        config = get_config("production")
        client = AzureOpenAI(
            api_key=config.azure_openai_api_key,
            api_version="2024-02-01",
            azure_endpoint=config.azure_openai_endpoint
        )
        
        # Direct medical prompt - no complex abstraction layers
        prompt = f"""You are a pharmaceutical protocol optimization AI. Analyze this text and provide specific medical recommendations.

Text to analyze:
{content}

Provide exactly 3-5 specific medical recommendations in this format:
1. Original: "patient" → Suggested: "participant" (Reason: ICH-GCP compliance for clinical research)
2. Original: "HER2+ breast cancer" → Suggested: "HER2+ breast cancer with trastuzumab-related cardiotoxicity monitoring per ACC/AHA guidelines" (Reason: Drug-specific safety monitoring)

Focus on:
- Medical terminology corrections (patient → participant)
- Drug-specific monitoring requirements (trastuzumab cardiotoxicity, CDK4/6 neutropenia)
- ICH-GCP compliance improvements
- Regulatory guidance enhancements

Format each recommendation as: Original: "text" → Suggested: "text" (Reason: explanation)"""

        response = client.chat.completions.create(
            model=config.azure_openai_deployment,
            messages=[
                {"role": "system", "content": "You are a pharmaceutical protocol AI providing specific medical recommendations."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.3
        )
        
        ai_response = response.choices[0].message.content
        logger.info(f"✅ SIMPLE AI: Got Azure OpenAI response ({len(ai_response)} chars)")
        
        # Parse simple text response into suggestions
        suggestions = []
        lines = ai_response.strip().split('\n')
        
        for i, line in enumerate(lines):
            if '→' in line and 'Original:' in line and 'Suggested:' in line:
                try:
                    # Extract original and suggested text
                    parts = line.split('→')
                    original_part = parts[0].strip()
                    suggested_part = parts[1].strip()
                    
                    original_text = original_part.split('Original:')[1].strip().strip('"').strip("'")
                    suggested_full = suggested_part.split('(Reason:')[0].strip()
                    suggested_text = suggested_full.split('Suggested:')[1].strip().strip('"').strip("'")
                    
                    reason = ""
                    if '(Reason:' in suggested_part:
                        reason = suggested_part.split('(Reason:')[1].strip().rstrip(')')
                    
                    suggestions.append({
                        "id": f"simple_ai_chunk_{chunk_index}_issue_{i}",
                        "type": "medical_terminology",
                        "severity": "medium",
                        "text": original_text,
                        "suggestion": suggested_text,
                        "rationale": reason,
                        "regulatory_source": "Azure OpenAI Medical Analysis",
                        "position": {"start": i * 20, "end": i * 20 + len(original_text)},
                        "category": "medical_enhancement",
                        "confidence": 0.9,
                        "ai_enhanced": True,
                        "simple_ai_analysis": True,
                        "backend_confidence": "azure_openai_direct"
                    })
                except Exception as parse_error:
                    logger.warning(f"Failed to parse AI response line: {line} - {parse_error}")
                    continue
        
        logger.info(f"✅ SIMPLE AI: Parsed {len(suggestions)} medical recommendations")
        
        return {
            "suggestions": suggestions,
            "metadata": {
                "chunk_index": chunk_index,
                "total_chunks": total_chunks,
                "content_length": len(content),
                "suggestions_generated": len(suggestions),
                "simple_ai_enabled": True,
                "processing_time": 0.8,
                "model_version": "2.0.0-simple-azure-direct",
                "ai_stack": "Azure OpenAI Direct",
                "ai_response_length": len(ai_response)
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Simple AI analysis failed: {e}")
        # Return basic fallback
        return {
            "suggestions": [{
                "id": f"fallback_chunk_{chunk_index}_issue_0",
                "type": "terminology",
                "severity": "medium", 
                "text": "patient",
                "suggestion": "participant",
                "rationale": "Use 'participant' instead of 'patient' per ICH-GCP guidelines",
                "regulatory_source": "ICH-GCP Guidelines",
                "position": {"start": 0, "end": 7},
                "category": "compliance",
                "confidence": 0.8,
                "ai_enhanced": False,
                "simple_ai_analysis": False
            }],
            "metadata": {
                "chunk_index": chunk_index,
                "total_chunks": total_chunks,
                "content_length": len(content),
                "suggestions_generated": 1,
                "simple_ai_enabled": False,
                "processing_time": 0.1,
                "model_version": "1.0.0-fallback",
                "ai_stack": "Fallback Pattern",
                "error": str(e)
            }
        }

@app.post("/api/telemetry")
async def log_telemetry(request: Request, telemetry_data: dict):
    """Log frontend telemetry events for monitoring and analytics"""
    try:
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        
        # Add server-side metadata
        enriched_telemetry = {
            **telemetry_data,
            "server_request_id": request_id,
            "server_timestamp": datetime.utcnow().isoformat(),
            "user_agent": request.headers.get("user-agent"),
            "origin": request.headers.get("origin"),
            "referer": request.headers.get("referer")
        }
        
        # Log to console and telemetry system
        logger.info(f"📊 Frontend Telemetry: {json.dumps(enriched_telemetry)}")
        
        # Send to telemetry service if available
        if hasattr(globals(), 'telemetry_service') and telemetry_service:
            try:
                telemetry_service.log_event(enriched_telemetry)
            except Exception as e:
                logger.warning(f"Telemetry service error: {e}")
        
        return {
            "status": "logged",
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Telemetry logging failed: {e}")
        return {
            "status": "error",
            "message": "Failed to log telemetry",
            "request_id": getattr(request.state, 'request_id', 'unknown')
        }

@app.post("/api/rl/feedback")
async def rl_feedback(request: Request, feedback_data: dict):
    """
    Accept RL feedback events (e.g., undo signals) with strict PHI protection.

    This endpoint enforces:
    - redactPHI flag must be true
    - No raw text fields allowed (use hashes)
    - Stores events to shadow/feedback/ for replay
    """
    try:
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))

        # Validate PHI redaction
        is_valid, error_msg = validate_phi_redacted(feedback_data)
        if not is_valid:
            logger.warning(f"❌ RL feedback rejected: {error_msg}")
            raise HTTPException(
                status_code=400,
                detail=f"PHI validation failed: {error_msg}"
            )

        # Validate and parse event using Pydantic
        try:
            event = RLFeedbackEvent(**feedback_data)
        except Exception as e:
            logger.warning(f"❌ RL feedback validation failed: {e}")
            raise HTTPException(
                status_code=422,
                detail=f"Validation error: {str(e)}"
            )

        # Store event to shadow/feedback/
        result = store_feedback_event(event, event_type="rl_feedback")

        if result["success"]:
            logger.info(f"✅ RL feedback stored: {event.suggestion_id} (event: {event.event})")
            return {"ok": True}
        else:
            logger.error(f"❌ Failed to store RL feedback: {result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail="Failed to store RL feedback"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ RL feedback endpoint error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@app.get("/api/sources/{suggestion_id}")
async def get_suggestion_sources(suggestion_id: str):
    """
    Get explainability sources for a specific suggestion.

    Returns regulatory citations, Pinecone exemplars, and reasoning breakdown
    for transparency and auditability.

    Args:
        suggestion_id: Unique suggestion identifier

    Returns:
        JSON object with sources array containing regulatory citations
    """
    try:
        logger.info(f"📚 Fetching sources for suggestion: {suggestion_id}")

        # TODO: In production, retrieve actual sources from:
        # 1. Pinecone metadata (exemplar snippets used for RAG)
        # 2. Regulatory database (ICH-GCP, FDA, EMA citations)
        # 3. Model reasoning logs

        # For now, return mock sources structure that matches expected format
        sources = [
            {
                "title": "ICH-GCP E6(R2) - Good Clinical Practice",
                "url": "https://database.ich.org/sites/default/files/E6_R2_Addendum.pdf",
                "citation": "Section 5.18.3 - Protocol amendments require documentation of rationale and regulatory approval timelines",
                "type": "regulatory",
                "relevance_score": 0.92
            },
            {
                "title": "FDA Guidance - Clinical Trial Conduct",
                "url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents",
                "citation": "21 CFR 312.120 - Protocol amendments must clearly describe changes and provide scientific justification",
                "type": "regulatory",
                "relevance_score": 0.88
            },
            {
                "title": "Protocol Exemplar from Vector DB",
                "url": None,
                "citation": "Similar high-quality protocol used clear, unambiguous language for this objective",
                "type": "exemplar",
                "relevance_score": 0.85,
                "metadata": {
                    "therapeutic_area": "oncology",
                    "phase": "Phase III",
                    "vector_distance": 0.15
                }
            }
        ]

        return {
            "suggestion_id": suggestion_id,
            "sources": sources,
            "generated_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Failed to fetch sources for {suggestion_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve sources: {str(e)}"
        )

@app.post("/api/reinforce")
async def reinforce(request: Request, feedback_data: dict):
    """
    Legacy reinforcement endpoint for backward compatibility.

    Accepts reinforcement signals (accept/undo) with optional PHI protection.
    Stores events to shadow/feedback/ for replay.
    """
    try:
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))

        # Validate and parse event using Pydantic
        try:
            event = ReinforcementEvent(**feedback_data)
        except Exception as e:
            logger.warning(f"❌ Reinforcement validation failed: {e}")
            raise HTTPException(
                status_code=422,
                detail=f"Validation error: {str(e)}"
            )

        # Log warning if PHI protection is not enabled
        if not event.redactPHI:
            logger.warning(f"⚠️ Reinforcement signal without PHI protection: {event.suggestion_id}")

        # Store event to shadow/feedback/
        result = store_reinforcement_event(event)

        if result["success"]:
            logger.info(f"✅ Reinforcement signal stored: {event.suggestion_id} (action: {event.action})")
            return {
                "status": "success",
                "message": "Reinforcement signal received",
                "suggestion_id": event.suggestion_id,
                "action": event.action,
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            logger.error(f"❌ Failed to store reinforcement signal: {result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail="Failed to store reinforcement signal"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Reinforcement endpoint error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@app.get("/api/audit/events")
async def get_audit_events(
    tenant_id: str = None,
    user_id_hash: str = None,
    action: str = None,
    start_date: str = None,
    end_date: str = None,
    limit: int = 100
):
    """
    B2B Audit Log Dashboard - Query RL feedback events with tenant filtering

    Query parameters:
    - tenant_id: Filter by tenant (required for multi-tenant deployments)
    - user_id_hash: Filter by hashed user ID
    - action: Filter by action type (accept, undo, reject)
    - start_date: ISO 8601 start date filter
    - end_date: ISO 8601 end date filter
    - limit: Max number of events to return (default: 100, max: 1000)
    """
    try:
        import json
        from pathlib import Path

        # Limit max results
        limit = min(limit, 1000)

        # Read all feedback events from shadow/feedback/
        feedback_dir = Path(__file__).parent / "shadow" / "feedback"
        if not feedback_dir.exists():
            return {
                "events": [],
                "count": 0,
                "filtered_count": 0,
                "message": "No feedback events found"
            }

        # Load all feedback JSON files
        events = []
        for feedback_file in feedback_dir.glob("*.json"):
            try:
                with open(feedback_file, 'r') as f:
                    event = json.load(f)

                    # Apply filters
                    if tenant_id and event.get('tenant_id') != tenant_id:
                        continue
                    if user_id_hash and event.get('user_id_hash') != user_id_hash:
                        continue
                    if action and event.get('action') != action:
                        continue

                    # Date filtering
                    if start_date or end_date:
                        event_time = event.get('timestamp', '')
                        if start_date and event_time < start_date:
                            continue
                        if end_date and event_time > end_date:
                            continue

                    events.append(event)
            except Exception as e:
                logger.warning(f"Failed to load feedback file {feedback_file}: {e}")
                continue

        # Sort by timestamp descending (newest first)
        events.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        # Apply limit
        total_count = len(events)
        events = events[:limit]

        return {
            "events": events,
            "count": len(events),
            "total_count": total_count,
            "filters": {
                "tenant_id": tenant_id,
                "user_id_hash": user_id_hash,
                "action": action,
                "start_date": start_date,
                "end_date": end_date
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Audit events endpoint error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query audit events: {str(e)}"
        )

@app.post("/api/diagnose-highlight")
async def diagnose_highlight(request: Request, highlight_data: dict):
    """Simulate highlight functionality for QA testing"""
    try:
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        search_text = highlight_data.get('search_text', '')
        
        # Simulate finding text ranges (mock Office.js behavior)
        if not search_text:
            raise HTTPException(status_code=400, detail="search_text is required")
        
        # Mock range calculation based on text length
        text_length = len(search_text)
        mock_range = {
            "start": 0,
            "end": min(text_length, 50),
            "found": True,
            "highlight_color": "#FFA500" if "adverse" in search_text.lower() else "#ea1537"
        }
        
        # Simulate processing delay
        import time
        time.sleep(0.1)  # 100ms simulation
        
        return {
            "status": "success",
            "request_id": request_id,
            "search_text": search_text,
            "range": mock_range,
            "simulation": True,
            "message": f"Mock highlight applied to '{search_text[:30]}...' at range {mock_range['start']}-{mock_range['end']}",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Diagnose highlight failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Highlight diagnosis failed: {str(e)}"
        )

@app.post("/api/recommend-language")
async def recommend_language_route(request: ComprehensiveAnalysisRequest):
    """Language recommendation endpoint with simple/legacy pipeline routing"""
    try:
        content = request.text
        chunk_index = getattr(request, 'chunk_index', 0) 
        total_chunks = getattr(request, 'total_chunks', 1)
        
        # Check environment flag for simple vs legacy pipeline
        use_simple_azure = os.getenv("USE_SIMPLE_AZURE_PROMPT", "true").lower() == "true"
        logger.info(f"🔀 ROUTING: USE_SIMPLE_AZURE_PROMPT={use_simple_azure}")
        
        if use_simple_azure:
            # Route to simple Azure OpenAI function
            result = await simple_recommend_language(content, chunk_index, total_chunks)
            result["metadata"]["pipeline_used"] = "simple_azure_direct"
            return result
        else:
            # Route to legacy enterprise pipeline
            logger.info(f"🤖 LEGACY PIPELINE: Analyzing chunk {chunk_index + 1}/{total_chunks} ({len(content)} chars)")
            
            if enterprise_ai_service:
                try:
                    # Call legacy enterprise AI stack (Azure OpenAI + Pinecone + PubMedBERT)
                    suggestions, metadata = await enterprise_ai_service.analyze_comprehensive(
                        content,
                        {"chunk_index": chunk_index, "total_chunks": total_chunks}
                    )
                    
                    # Convert to API response format
                    issues = []
                    for suggestion in suggestions:
                        issues.append({
                            "id": f"legacy_chunk_{chunk_index}_issue_{len(issues)}",
                            "type": suggestion.type,
                            "severity": suggestion.subtype.replace("enterprise_", "") if suggestion.subtype else "medium",
                            "text": suggestion.originalText,
                            "suggestion": suggestion.suggestedText,
                            "rationale": suggestion.rationale,
                            "regulatory_source": suggestion.guidanceSource or "Legacy Enterprise AI Analysis",
                            "position": suggestion.range if suggestion.range else {"start": 0, "end": len(suggestion.originalText)},
                            "category": suggestion.type,
                            "confidence": 0.95,  # Enterprise AI confidence
                            "ai_enhanced": True,
                            "legacy_enterprise_analysis": True,
                            "backend_confidence": suggestion.backendConfidence,
                            "compliance_rationale": suggestion.complianceRationale,
                            "fda_reference": suggestion.fdaReference,
                            "ema_reference": suggestion.emaReference,
                            "operational_impact": suggestion.operationalImpact,
                            "retention_risk": suggestion.retentionRisk
                        })
                    
                    logger.info(f"✅ LEGACY PIPELINE: Generated {len(issues)} pharma-grade suggestions using full AI stack")
                    
                    # Return legacy enterprise AI response
                    return {
                        "suggestions": issues,
                        "metadata": {
                            "chunk_index": chunk_index,
                            "total_chunks": total_chunks,
                            "content_length": len(content),
                            "suggestions_generated": len(issues),
                            "enterprise_ai_enabled": True,
                            "processing_time": metadata.get("processing_time", 0),
                            "model_version": metadata.get("model_version", "5.0.0-full-enterprise-stack"),
                            "ai_stack": "Legacy Azure OpenAI + Pinecone + PubMedBERT",
                            "pipeline_used": "legacy_enterprise",
                            "therapeutic_area_detection": metadata.get("therapeutic_area_detection", {}),
                            "enterprise_features": metadata.get("enterprise_features", {})
                        }
                    }
                    
                except Exception as ai_error:
                    logger.error(f"❌ Legacy Enterprise AI analysis failed: {ai_error}")
                    # Fall through to pattern-based analysis
            
            # Legacy fallback pattern-based analysis
            logger.warning("⚠️ Using legacy fallback pattern analysis")
            issues = []
            sentences = content.split('.')
            
            # Enhanced fallback patterns with specific replacements
            fallback_patterns = [
                ("patient", "participant", "compliance", "Use 'participant' instead of 'patient' per ICH-GCP guidelines for clinical research"),
                ("patients", "participants", "compliance", "Use 'participants' instead of 'patients' per ICH-GCP guidelines for clinical research"),
                ("will be", "shall be", "compliance", "Use 'shall be' instead of 'will be' for protocol requirements per regulatory standards"),
                ("daily", "once daily", "feasibility", "Consider specifying 'once daily' for clarity and reducing participant burden"),
                ("every day", "once daily", "clarity", "Use standardized terminology 'once daily' instead of 'every day'"),
                ("twice a day", "twice daily", "clarity", "Use standardized terminology 'twice daily' instead of 'twice a day'"),
                ("morning", "in the morning", "clarity", "Specify 'in the morning' for clearer dosing instructions"),
                ("evening", "in the evening", "clarity", "Specify 'in the evening' for clearer dosing instructions"),
                ("doctor", "investigator", "compliance", "Use 'investigator' instead of 'doctor' per clinical research standards"),
                ("study drug", "investigational product", "compliance", "Use 'investigational product' instead of 'study drug' per ICH-GCP terminology"),
                ("side effect", "adverse event", "compliance", "Use 'adverse event' instead of 'side effect' per ICH-GCP guidelines"),
                ("side effects", "adverse events", "compliance", "Use 'adverse events' instead of 'side effects' per ICH-GCP guidelines")
            ]
            
            for i, sentence in enumerate(sentences[:10]):
                sentence = sentence.strip()
                if len(sentence) < 10:
                    continue
                
                for pattern, replacement, issue_type, rationale in fallback_patterns:
                    if pattern in sentence.lower():
                        # Find the exact text and create replacement
                        original_text = sentence
                        suggested_text = sentence.replace(pattern, replacement)
                        
                        # If the replacement is the same as original, skip
                        if original_text == suggested_text:
                            continue
                        
                        issues.append({
                            "id": f"legacy_fallback_chunk_{chunk_index}_issue_{len(issues)}",
                            "type": issue_type,
                            "severity": "medium",
                            "text": original_text[:150] + "..." if len(original_text) > 150 else original_text,
                            "suggestion": suggested_text[:200] + "..." if len(suggested_text) > 200 else suggested_text,
                            "rationale": rationale,
                            "regulatory_source": "ICH-GCP Guidelines",
                            "position": {"start": i * 50, "end": i * 50 + len(sentence)},
                            "category": issue_type,
                            "confidence": 0.8,
                            "ai_enhanced": False,
                            "legacy_enterprise_analysis": False,
                            "original_term": pattern,
                            "suggested_term": replacement
                        })
                        break
            
            return {
                "suggestions": issues,
                "metadata": {
                    "chunk_index": chunk_index,
                    "total_chunks": total_chunks,
                    "content_length": len(content),
                    "suggestions_generated": len(issues),
                    "enterprise_ai_enabled": False,
                    "processing_time": 0.1,
                    "model_version": "1.0.0-legacy-pattern-fallback",
                    "ai_stack": "Legacy Pattern matching fallback",
                    "pipeline_used": "legacy_fallback"
                }
            }
        
    except Exception as e:
        logger.error(f"❌ Language recommendation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Language recommendation failed: {str(e)}")

@app.post("/analyze-comprehensive")
async def analyze_comprehensive(request: ComprehensiveAnalysisRequest):
    """Legacy comprehensive analysis endpoint - preserved for backward compatibility"""
    return await recommend_language_route(request)

# ---- START PATCH: Analysis Mode Routing ----
import json
from typing import Optional
import httpx
import traceback

# Analysis service base URL for fallback requests
ANALYSIS_SERVICE_BASE = os.getenv("ANALYSIS_SERVICE_BASE", "http://127.0.0.1:8000")  # local fallback

analysis_mode_logger = logging.getLogger("ilana.analysis_mode")
analysis_mode_logger.setLevel(logging.INFO)

# Try to import existing simple endpoint handler; if not available, we'll call HTTP fallback
def _call_simple_inprocess(payload: dict):
    """
    Attempt to call an in-process simple handler if available.
    Expected signature in existing code (optional):
      def recommend_language_simple(payload: dict) -> dict
    """
    try:
        # adjust import path if your module name differs
        from recommend_simple import recommend_language_simple
        return recommend_language_simple(payload)
    except Exception:
        return None

def _call_legacy_inprocess(payload: dict):
    try:
        from legacy_pipeline import run_legacy_pipeline  # if exists
        return run_legacy_pipeline(payload)
    except Exception:
        return None

async def _http_post(path: str, payload: dict, timeout: int = 25):
    url = f"{ANALYSIS_SERVICE_BASE.rstrip('/')}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        # Return JSON if possible, else text
        try:
            return resp.json()
        except Exception:
            return {"raw": resp.text}

def _generate_request_id():
    return str(uuid.uuid4())

@app.get("/debug/handler-types")
async def debug_handler_types():
    info = {}
    try:
        import hybrid_controller as hc
        info["has_hybrid_controller"] = True
        info["handler_name"] = getattr(hc, "handle_hybrid_request", None).__name__ if getattr(hc, "handle_hybrid_request", None) else None
        info["iscoroutinefunction"] = inspect.iscoroutinefunction(hc.handle_hybrid_request) if getattr(hc, "handle_hybrid_request", None) else False
        # Try calling with a safe dummy payload but do not await if it's a coroutine function:
        try:
            res = hc.handle_hybrid_request({"mode":"selection","text":"debug","request_id":"debug"})
            info["returned_type"] = str(type(res))
            info["is_awaitable_return"] = inspect.isawaitable(res)
        except Exception as e:
            info["call_exception"] = str(e)
    except Exception as ex:
        info["has_hybrid_controller"] = False
        info["error"] = str(ex)
    return info

@app.post("/api/analyze")
async def analyze_entry(request: Request, background_tasks: BackgroundTasks):
    """
    Protocol analysis with automatic fast/deep path selection

    Fast path (< 10s): Selections up to 2000 chars using gpt-4o-mini
    Deep path (background): Large selections with full RAG stack

    Payload: {"text": str, "mode": "selection", "request_id": str}
    Returns: {"status": "fast"|"queued", "request_id": str, "suggestions": [...]}
    """
    import time
    import hashlib
    start_time = time.time()

    payload = await request.json()
    req_id = payload.get("request_id") or _generate_request_id()
    text = payload.get("text", "")
    text_len = len(text)

    # Enforce selection mode only
    mode = payload.get("mode", "selection")
    if mode != "selection":
        logger.warning(f"⚠️ Rejecting non-selection mode: {mode}")
        raise HTTPException(
            status_code=400,
            detail=f"Only 'selection' mode is supported. Received mode: {mode}"
        )

    payload.setdefault("request_id", req_id)

    # Start telemetry trace
    headers_dict = dict(request.headers.items()) if request.headers else {}
    request_id = start_trace(
        analyze_mode="smart_routing",
        model_path="auto",
        request_data=payload,
        headers=headers_dict
    )

    logger.info(f"🚀 Analysis request: {req_id} text_len={text_len}")

    try:
        # Import fast analysis module
        from fast_analysis import analyze_fast, SELECTION_CHUNK_THRESHOLD

        # Decision: Fast path vs deep path
        use_fast_path = text_len <= SELECTION_CHUNK_THRESHOLD

        if use_fast_path:
            # === FAST PATH: Synchronous, < 4s ===
            logger.info(f"⚡ Using FAST path: {req_id} ({text_len} <= {SELECTION_CHUNK_THRESHOLD} chars)")

            result = await analyze_fast(
                text=text,
                ta=payload.get("ta"),
                phase=payload.get("phase"),
                request_id=req_id
            )

            # End telemetry trace
            end_trace(request_id, result, None, {"model_path": "fast", "timings": result.get("metadata", {})})

            # Transform to API format
            suggestions = result.get("suggestions", [])
            metadata = result.get("metadata", {})

            def hash_content(text: str) -> str:
                """SHA-256 hash for proprietary content protection"""
                if not text:
                    return "empty"
                return hashlib.sha256(text.encode('utf-8')).hexdigest()

            transformed_suggestions = []
            for suggestion in suggestions:
                original_text = suggestion.get("text", "")

                transformed_suggestions.append({
                    "id": suggestion.get("id", f"suggestion_{req_id}"),
                    "original_text": original_text,  # Frontend expects "original_text"
                    "improved_text": suggestion.get("suggestion", ""),  # Frontend expects "improved_text"
                    "rationale": suggestion.get("rationale", ""),
                    "confidence": suggestion.get("confidence", 0.9),
                    "type": suggestion.get("type", "clarity"),
                    "ta": payload.get("ta"),
                    "phase": payload.get("phase"),
                    "model_path": "fast"
                })

            response = {
                "status": "fast",
                "request_id": req_id,
                "suggestions": transformed_suggestions,
                "latency_ms": metadata.get("total_ms", 0),
                "metadata": {
                    "model": metadata.get("model", "gpt-4o-mini"),
                    "cache_hit": metadata.get("cache_hit", False),
                    "timings": {
                        "preprocess_ms": metadata.get("preprocess_ms", 0),
                        "azure_ms": metadata.get("azure_ms", 0),
                        "postprocess_ms": metadata.get("postprocess_ms", 0),
                        "total_ms": metadata.get("total_ms", 0)
                    }
                }
            }

            logger.info(f"✅ FAST path complete: {req_id} ({metadata.get('total_ms', 0)}ms, {len(transformed_suggestions)} suggestions)")
            return response

        else:
            # === DEEP PATH: Background job queue ===
            logger.info(f"📋 Using DEEP path (background job): {req_id} ({text_len} > {SELECTION_CHUNK_THRESHOLD} chars)")

            # Import job queue
            from job_queue import create_job, process_job_async
            from server.jobs import get_job_store
            import uuid

            # Create job in job queue
            job_id = create_job(
                text=text,
                ta=payload.get("ta"),
                phase=payload.get("phase")
            )

            # Also create job in JobStore for status persistence
            job_store = get_job_store()
            job_uuid = str(uuid.uuid4())
            job_store.create_job(
                job_id=job_uuid,
                payload={
                    "text": text,
                    "ta": payload.get("ta"),
                    "phase": payload.get("phase"),
                    "mode": "selection",
                    "request_id": req_id
                }
            )

            # Queue background task to process the job (uses injected background_tasks)
            background_tasks.add_task(process_job_async, job_id)

            # End telemetry trace
            end_trace(request_id, {"status": "queued", "job_id": job_id}, None, {"model_path": "deep_queued"})

            logger.info(f"✅ Job queued: {job_id} ({job_uuid})")

            # Return queued response
            return {
                "status": "queued",
                "request_id": req_id,
                "job_id": job_uuid,  # Use JobStore UUID for status polling
                "message": "Analysis queued for background processing",
                "poll_url": f"/api/job-status/{job_uuid}",
                "estimated_time_s": 30
            }

    except Exception as e:
        logger.error(f"❌ Analysis failed: {req_id} - {type(e).__name__}: {e}")
        end_trace(request_id, None, f"Analysis failed: {str(e)}", {"model_path": "error"})
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )

# Legacy mode routing functions removed - now using direct legacy_pipeline.py calls

@app.post("/api/ta-detect")
async def detect_therapeutic_area_simple(request: TADetectRequest):
    """Simplified therapeutic area detection endpoint"""
    try:
        logger.info(f"🎯 TA detection for {len(request.content)} characters")
        
        content_lower = request.content.lower()
        
        ta_keywords = {
            "cardiovascular": ["heart", "cardiac", "cardiovascular", "blood pressure", "hypertension"],
            "oncology": ["cancer", "tumor", "oncology", "chemotherapy", "radiation"],
            "endocrinology": ["diabetes", "insulin", "glucose", "thyroid", "hormone"],
            "neurology": ["brain", "neurological", "seizure", "stroke", "dementia"]
        }
        
        detected_ta = "general_medicine"
        confidence = 0.5
        keywords_found = []
        
        for ta, keywords in ta_keywords.items():
            matches = [kw for kw in keywords if kw in content_lower]
            if matches:
                detected_ta = ta
                confidence = min(1.0, 0.8 + len(matches) * 0.1)
                keywords_found = [f"{kw} (1x)" for kw in matches[:5]]
                break
        
        return {
            "therapeutic_area": detected_ta,
            "confidence": confidence,
            "keywords_found": keywords_found,
            "alternative_areas": [
                {"area": "general_medicine", "confidence": 0.3} if detected_ta != "general_medicine" else {"area": "oncology", "confidence": 0.2}
            ]
        }
        
    except Exception as e:
        logger.error(f"❌ TA detection failed: {e}")
        raise HTTPException(status_code=500, detail=f"TA detection failed: {str(e)}")

@app.post("/api/enhance-text")
async def enhance_text_simple(request: TextEnhanceRequest):
    """Simplified text enhancement endpoint"""
    try:
        logger.info(f"🤖 Text enhancement for {len(request.original_text)} chars")
        
        enhanced_text = request.original_text
        explanation = f"Enhanced for {request.therapeutic_area} protocol compliance"
        
        if "patient" in request.original_text.lower():
            enhanced_text = enhanced_text.replace("patient", "subject").replace("Patient", "Subject")
            explanation += ". Changed 'patient' to 'subject' per ICH-GCP guidelines."
        
        return {
            "enhanced_text": enhanced_text,
            "explanation": explanation,
            "confidence": 0.85,
            "regulatory_basis": [
                {
                    "source": "ICH E6(R2) GCP Guidance",
                    "relevance": 0.85,
                    "citation": "Good Clinical Practice guidelines"
                }
            ],
            "therapeutic_area": request.therapeutic_area,
            "enhancement_type": request.enhancement_type,
            "improvements": ["Terminology standardization"]
        }
        
    except Exception as e:
        logger.error(f"❌ Text enhancement failed: {e}")
        raise HTTPException(status_code=500, detail=f"Text enhancement failed: {str(e)}")

@app.post("/api/ta-recommendations")
async def get_ta_recommendations_simple(request: TARecommendationsRequest):
    """Simplified TA recommendations endpoint"""
    try:
        logger.info(f"🏥 TA recommendations for {request.therapeutic_area}")
        
        recommendations = [
            {
                "title": "ICH-GCP Compliance",
                "content": "Ensure all trial procedures follow ICH Good Clinical Practice guidelines",
                "priority": "high",
                "regulatory_source": "ICH E6(R2) GCP Guidance"
            },
            {
                "title": "Statistical Analysis Plan", 
                "content": "Develop comprehensive SAP addressing endpoints and multiplicity",
                "priority": "high",
                "regulatory_source": "ICH E9 Statistical Principles"
            }
        ]
        
        return {
            "therapeutic_area": request.therapeutic_area,
            "protocol_type": request.protocol_type,
            "recommendations": recommendations,
            "total_recommendations": len(recommendations),
            "last_updated": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ TA recommendations failed: {e}")
        raise HTTPException(status_code=500, detail=f"TA recommendations failed: {str(e)}")

# ---- SSE Job Streaming Endpoints ----

# In-memory job event storage (replace with Redis/database in production)
job_events = {}
job_subscribers = {}

def emit_job_event(job_id: str, event_data: dict):
    """Emit an event for a specific job"""
    if job_id not in job_events:
        job_events[job_id] = []
    
    # Add timestamp to event
    event_data['timestamp'] = datetime.utcnow().isoformat()
    job_events[job_id].append(event_data)
    
    # Write to log file for persistence
    job_dir = Path("jobs") / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    with open(job_dir / "events.log", "a") as f:
        f.write(json.dumps(event_data) + "\n")
    
    logger.info(f"📡 Emitted event for job {job_id}: {event_data['type']}")

def load_job_events(job_id: str) -> List[dict]:
    """Load existing events for a job from file"""
    events = []
    job_dir = Path("jobs") / job_id
    events_file = job_dir / "events.log"
    
    if events_file.exists():
        try:
            with open(events_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
        except Exception as e:
            logger.warning(f"Failed to load events for job {job_id}: {e}")
    
    return events

async def generate_job_events(job_id: str):
    """Generator for SSE events for a specific job"""
    logger.info(f"🔴 Starting SSE stream for job {job_id}")
    
    # Send existing events first
    existing_events = load_job_events(job_id)
    for event in existing_events:
        yield f"data: {json.dumps(event)}\n\n"
    
    # Track last event index to avoid duplicates
    last_event_idx = len(existing_events)
    
    # Stream new events
    max_duration = 300  # 5 minutes max
    start_time = time.time()
    
    while time.time() - start_time < max_duration:
        # Check for new events
        current_events = job_events.get(job_id, [])
        
        if len(current_events) > last_event_idx:
            # Send new events
            for event in current_events[last_event_idx:]:
                yield f"data: {json.dumps(event)}\n\n"
            last_event_idx = len(current_events)
            
            # Check if job is complete
            if current_events and current_events[-1].get('type') == 'complete':
                logger.info(f"✅ Job {job_id} completed, ending SSE stream")
                break
        
        # Wait before checking again
        await asyncio.sleep(1)
    
    # Send final heartbeat
    yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': datetime.utcnow().isoformat()})}\n\n"
    logger.info(f"🔴 Ended SSE stream for job {job_id}")

@app.get("/api/stream-job/{job_id}/events")
async def stream_job_events(job_id: str, request: Request):
    """SSE endpoint for streaming job progress events"""
    logger.info(f"📡 SSE connection requested for job {job_id}")
    
    # Validate job exists
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        logger.warning(f"❌ Job {job_id} not found")
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    async def event_stream():
        try:
            async for event in generate_job_events(job_id):
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"🔌 Client disconnected from job {job_id} stream")
                    break
                yield event
        except Exception as e:
            logger.error(f"❌ SSE stream error for job {job_id}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

@app.get("/api/job-status/{job_id}")
async def get_job_status(job_id: str):
    """
    Get current job status and latest events.

    Returns 200 with job data if found, 404 if not found.
    Validates job_id is UUID format.
    """
    # Import JobStore
    from server.jobs import get_job_store

    # Validate UUID format (400 Bad Request if invalid)
    try:
        uuid.UUID(job_id)
    except (ValueError, AttributeError):
        logger.warning(f"⚠️ Invalid job_id format (not UUID): {job_id}")
        raise HTTPException(status_code=400, detail="Invalid job_id format (must be UUID)")

    # Log request
    logger.info(f"📊 Job status request for job_id: {job_id}")

    # Get job from store
    job_store = get_job_store()
    job_data = job_store.get_job(job_id)

    if not job_data:
        # Log at INFO level (not ERROR) - 404 is normal for expired/non-existent jobs
        logger.info(f"ℹ️ Job {job_id} not found (404)")
        raise HTTPException(status_code=404, detail="Job not found")

    # Return job data
    logger.info(f"✅ Returning job {job_id} status: {job_data.get('status')}")
    return job_data

@app.post("/api/queue-job")
async def queue_job(request: Request):
    """
    Create a new job with queued status.

    Accepts minimal payload and returns job_id.

    Request body:
        {
            "text": str (optional),
            "ta": str (optional),
            "mode": str (optional),
            "user_id_hash": str (optional)
        }

    Returns:
        {
            "job_id": str (UUID),
            "status": "queued",
            "created_at": str (ISO timestamp)
        }
    """
    from server.jobs import create_job

    try:
        payload = await request.json()
        logger.info(f"📥 Queue job request: {len(payload.get('text', ''))} chars")

        # Create job
        job_id = create_job(payload)

        # Get job data to return
        from server.jobs import get_job_store
        job_store = get_job_store()
        job_data = job_store.get_job(job_id)

        logger.info(f"✅ Job {job_id} queued successfully")
        return {
            "job_id": job_id,
            "status": job_data.get("status", "queued"),
            "created_at": job_data.get("created_at")
        }
    except Exception as e:
        logger.error(f"❌ Error queueing job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to queue job: {str(e)}")

@app.post("/api/job/{job_id}/emit-event")
async def emit_event_to_job(job_id: str, event_data: dict):
    """Emit an event to a job stream (for worker processes)"""
    emit_job_event(job_id, event_data)
    return {"status": "emitted", "job_id": job_id, "event_type": event_data.get('type')}

# ---- TA-Enhanced Rewrite Endpoint ----

class GenerateRewriteTARequest(BaseModel):
    """Request model for TA-enhanced rewrite generation"""
    suggestion_id: str = Field(..., description="ID of the suggestion to enhance")
    text: str = Field(..., min_length=1, max_length=5000, description="Text to rewrite")
    ta: Optional[str] = Field(None, description="Therapeutic area (auto-detected if not provided)")
    phase: Optional[str] = Field(None, description="Clinical trial phase")
    doc_id: Optional[str] = Field(None, description="Document ID for context")

# Rate limiting storage (replace with Redis in production)
rate_limit_storage = {}
MAX_REQUESTS_PER_MINUTE = int(os.getenv("TA_REWRITE_RATE_LIMIT", "10"))

def check_rate_limit(user_id: str = "default") -> bool:
    """Simple rate limiting check"""
    now = time.time()
    window_start = now - 60  # 1 minute window
    
    if user_id not in rate_limit_storage:
        rate_limit_storage[user_id] = []
    
    # Clean old requests
    rate_limit_storage[user_id] = [req_time for req_time in rate_limit_storage[user_id] if req_time > window_start]
    
    # Check limit
    if len(rate_limit_storage[user_id]) >= MAX_REQUESTS_PER_MINUTE:
        return False
    
    # Add current request
    rate_limit_storage[user_id].append(now)
    return True

async def fast_ta_classifier(text: str) -> Dict[str, Any]:
    """Fast TA classification using simple keyword matching"""
    text_lower = text.lower()
    
    # Enhanced TA keywords with confidence scoring
    ta_patterns = {
        "oncology": {
            "keywords": ["cancer", "tumor", "oncology", "chemotherapy", "radiation", "metastasis", "carcinoma", "lymphoma", "leukemia", "melanoma", "her2", "egfr", "kras", "pd-l1", "immunotherapy"],
            "weight": [3, 3, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1]
        },
        "cardiovascular": {
            "keywords": ["heart", "cardiac", "cardiovascular", "blood pressure", "hypertension", "arrhythmia", "coronary", "myocardial", "atherosclerosis", "stroke", "ace inhibitor", "beta blocker"],
            "weight": [3, 3, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1]
        },
        "endocrinology": {
            "keywords": ["diabetes", "insulin", "glucose", "thyroid", "hormone", "endocrine", "metabolic", "adrenal", "pituitary", "pancreatic", "hba1c", "metformin"],
            "weight": [3, 3, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1]
        },
        "neurology": {
            "keywords": ["brain", "neurological", "seizure", "stroke", "dementia", "alzheimer", "parkinson", "epilepsy", "multiple sclerosis", "cognitive", "neurodegeneration"],
            "weight": [3, 3, 2, 2, 2, 2, 2, 2, 2, 2, 1]
        },
        "infectious_disease": {
            "keywords": ["infection", "bacterial", "viral", "antibiotic", "antiviral", "pathogen", "microbe", "sepsis", "pneumonia", "hepatitis", "hiv", "covid"],
            "weight": [3, 3, 3, 2, 2, 2, 2, 2, 2, 2, 1, 1]
        },
        "respiratory": {
            "keywords": ["lung", "respiratory", "asthma", "copd", "pneumonia", "bronchial", "pulmonary", "ventilation", "oxygen", "breathing"],
            "weight": [3, 3, 2, 2, 2, 2, 2, 2, 1, 1]
        }
    }
    
    ta_scores = {}
    detected_keywords = {}
    
    for ta, patterns in ta_patterns.items():
        score = 0
        found_keywords = []
        
        for keyword, weight in zip(patterns["keywords"], patterns["weight"]):
            if keyword in text_lower:
                score += weight
                found_keywords.append(keyword)
        
        if score > 0:
            ta_scores[ta] = score
            detected_keywords[ta] = found_keywords
    
    if not ta_scores:
        return {
            "therapeutic_area": "general_medicine",
            "confidence": 0.5,
            "confidence_scores": {"general_medicine": 0.5},
            "detected_keywords": [],
            "reasoning": "No specific TA keywords detected"
        }
    
    # Get top TA
    top_ta = max(ta_scores.keys(), key=lambda k: ta_scores[k])
    max_score = ta_scores[top_ta]
    confidence = min(0.95, 0.6 + (max_score / 10))  # Score-based confidence
    
    return {
        "therapeutic_area": top_ta,
        "confidence": confidence,
        "confidence_scores": ta_scores,
        "detected_keywords": detected_keywords.get(top_ta, []),
        "reasoning": f"Detected {len(detected_keywords.get(top_ta, []))} {top_ta} keywords with score {max_score}"
    }

async def query_vector_db(text: str, ta: str, phase: Optional[str] = None) -> List[Dict[str, Any]]:
    """Query vector database for exemplars (stubbed implementation)"""

    # RAG Gating Check - centralized gate function
    check_rag_async_mode_gate("Vector DB query")

    logger.info(f"✅ RAG_ASYNC_MODE check passed for vector DB query")
    
    # In production, this would query Pinecone/ChromaDB/etc.
    # For now, return mock exemplars based on TA
    
    exemplar_templates = {
        "oncology": [
            {
                "text": "Participants with HER2-positive breast cancer will receive trastuzumab therapy with mandatory cardiac monitoring per ACC/AHA guidelines.",
                "improved": "Study participants diagnosed with HER2-positive breast adenocarcinoma will receive trastuzumab-based therapy according to protocol, with baseline and periodic echocardiographic assessment of left ventricular ejection fraction (LVEF) as per American College of Cardiology/American Heart Association guidelines for cardiotoxicity monitoring.",
                "rationale": "Enhanced medical terminology with specific cardiac safety monitoring requirements",
                "sources": ["ACC/AHA Cardio-Oncology Guidelines", "FDA Trastuzumab Label"],
                "similarity": 0.89
            },
            {
                "text": "Patients will receive chemotherapy treatment daily.",
                "improved": "Study participants will receive protocol-specified chemotherapy regimen administered once daily (QD) per institutional standards.",
                "rationale": "Standardized dosing terminology and participant language per ICH-GCP",
                "sources": ["ICH-GCP E6(R2)", "NCCN Guidelines"],
                "similarity": 0.76
            }
        ],
        "cardiovascular": [
            {
                "text": "Heart failure patients will take medications twice daily.",
                "improved": "Participants with heart failure with reduced ejection fraction (HFrEF) will receive study medication twice daily (BID) with dose titration based on clinical response and tolerability.",
                "rationale": "Specific HF subtype classification and standardized dosing terminology",
                "sources": ["AHA/ACC Heart Failure Guidelines", "ESC Heart Failure Guidelines"],
                "similarity": 0.85
            },
            {
                "text": "Blood pressure will be monitored regularly.",
                "improved": "Systolic and diastolic blood pressure will be measured at baseline and every 2 weeks (±3 days) using standardized sphygmomanometry per protocol-specified procedures.",
                "rationale": "Specific measurement methodology and timing windows",
                "sources": ["AHA/ACC Hypertension Guidelines"],
                "similarity": 0.72
            }
        ],
        "endocrinology": [
            {
                "text": "Diabetic patients will check glucose levels daily.",
                "improved": "Participants with Type 2 diabetes mellitus will perform self-monitoring of blood glucose (SMBG) once daily in the fasting state using protocol-provided glucometers.",
                "rationale": "Specific diabetes subtype and standardized glucose monitoring terminology",
                "sources": ["ADA Standards of Care", "FDA Guidance on Diabetes"],
                "similarity": 0.83
            },
            {
                "text": "Insulin doses will be adjusted as needed.",
                "improved": "Insulin dosing will be titrated according to protocol-specified algorithms based on fasting plasma glucose targets (80-130 mg/dL) and postprandial glucose levels (<180 mg/dL).",
                "rationale": "Specific glycemic targets per clinical guidelines",
                "sources": ["ADA/EASD Consensus Statement"],
                "similarity": 0.78
            }
        ],
        "general_medicine": [
            {
                "text": "Patients will be monitored for side effects.",
                "improved": "Study participants will be assessed for adverse events (AEs) according to Common Terminology Criteria for Adverse Events (CTCAE) v5.0 at each protocol-specified visit.",
                "rationale": "Standardized AE terminology and assessment criteria",
                "sources": ["ICH-GCP E6(R2)", "CTCAE v5.0"],
                "similarity": 0.70
            },
            {
                "text": "Participants will visit the clinic monthly.",
                "improved": "Study participants will attend protocol-specified clinic visits monthly (every 28 ± 7 days) for safety and efficacy assessments.",
                "rationale": "Standardized visit windows and assessment purposes",
                "sources": ["ICH-GCP E6(R2)"],
                "similarity": 0.68
            }
        ]
    }
    
    # Get exemplars for the TA, fallback to general_medicine
    exemplars = exemplar_templates.get(ta, exemplar_templates["general_medicine"])
    
    # Filter by phase if provided (mock filtering)
    if phase and phase.lower() in ["i", "ii", "iii"]:
        # In production, this would filter by actual phase data
        # For now, just add phase context to reasoning
        for exemplar in exemplars:
            exemplar["phase_context"] = f"Phase {phase.upper()} considerations applied"
    
    # Return top 2 exemplars
    return exemplars[:2]

def get_regulatory_guidelines(ta: str) -> List[str]:
    """Get relevant regulatory guidelines for TA"""
    guidelines = {
        "oncology": [
            "FDA Guidance: Clinical Trial Endpoints for Cancer Drug Approval",
            "ICH E6(R2): Good Clinical Practice - ensure participant vs patient terminology"
        ],
        "cardiovascular": [
            "FDA Guidance: Cardiovascular Safety Studies for Diabetes Medications",
            "EMA Guidance: Clinical Investigation of Human Medicines for Cardiovascular Disease"
        ],
        "endocrinology": [
            "FDA Guidance: Diabetes Mellitus - Evaluating Cardiovascular Risk",
            "EMA Guidance: Clinical Investigation of Medicines for Diabetes Treatment"
        ],
        "neurology": [
            "FDA Guidance: Alzheimer's Disease - Developing Drugs for Treatment",
            "EMA Guidance: Clinical Investigation of Medicines for Neurological Disorders"
        ],
        "infectious_disease": [
            "FDA Guidance: Antibacterial Therapies for Serious Bacterial Diseases",
            "EMA Guidance: Development of Antimicrobial Medicinal Products"
        ],
        "respiratory": [
            "FDA Guidance: Chronic Obstructive Pulmonary Disease - Developing Drugs",
            "EMA Guidance: Clinical Investigation of Medicines for Respiratory Diseases"
        ],
        "general_medicine": [
            "ICH E6(R2): Good Clinical Practice Guidelines",
            "FDA Guidance: General Clinical Pharmacology Considerations"
        ]
    }
    
    return guidelines.get(ta, guidelines["general_medicine"])[:2]

async def generate_ta_aware_rewrite(text: str, ta: str, phase: Optional[str], exemplars: List[Dict], guidelines: List[str]) -> Dict[str, Any]:
    """Generate TA-aware rewrite using Azure OpenAI or mock"""

    # RAG Gating Check - centralized gate function
    check_rag_async_mode_gate("TA-aware rewrite generation")

    logger.info(f"✅ RAG_ASYNC_MODE check passed for TA-aware rewrite")
    
    start_time = time.time()
    
    try:
        # Try to use Azure OpenAI if available
        if ENTERPRISE_AVAILABLE:
            from config_loader import get_config
            from openai import AzureOpenAI
            
            config = get_config("production")
            client = AzureOpenAI(
                api_key=config.azure_openai_api_key,
                api_version="2024-02-01",
                azure_endpoint=config.azure_openai_endpoint
            )
            
            # Construct TA-aware prompt
            exemplar_context = ""
            if exemplars:
                exemplar_context = "\n\nEXEMPLARS from similar protocols:\n"
                for i, ex in enumerate(exemplars, 1):
                    exemplar_context += f"{i}. Original: \"{ex['text']}\"\n"
                    exemplar_context += f"   Improved: \"{ex['improved']}\"\n"
                    exemplar_context += f"   Rationale: {ex['rationale']}\n\n"
            
            regulatory_context = ""
            if guidelines:
                regulatory_context = f"\n\nREGULATORY GUIDELINES for {ta.upper()}:\n"
                for guideline in guidelines:
                    regulatory_context += f"- {guideline}\n"
            
            phase_context = f"\nClinical Phase: {phase.upper()}" if phase else ""
            
            prompt = f"""You are a clinical protocol optimization AI specializing in {ta.replace('_', ' ').upper()}. 

TASK: Rewrite this protocol text to be more precise, compliant, and therapeutic area-appropriate.

ORIGINAL TEXT: "{text}"

THERAPEUTIC AREA: {ta.replace('_', ' ').title()}{phase_context}{exemplar_context}{regulatory_context}

REQUIREMENTS:
1. Use "participants" instead of "patients" per ICH-GCP
2. Include specific {ta.replace('_', ' ')} medical terminology and monitoring requirements
3. Add relevant safety monitoring based on TA-specific risks
4. Ensure regulatory compliance for {ta.replace('_', ' ')} studies
5. Follow exemplar patterns for improvement style

RESPONSE FORMAT:
Provide exactly one improved version with rationale, following this structure:
IMPROVED: [Your rewritten text here]
RATIONALE: [Brief explanation of changes made]
SOURCES: [Relevant guidelines or standards referenced]"""

            response = client.chat.completions.create(
                model=config.azure_openai_deployment,
                messages=[
                    {"role": "system", "content": f"You are a {ta.replace('_', ' ')} clinical protocol optimization specialist."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.3
            )
            
            ai_response = response.choices[0].message.content
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Parse the structured response
            improved_text = ""
            rationale = ""
            sources = []
            
            lines = ai_response.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if line.startswith('IMPROVED:'):
                    current_section = 'improved'
                    improved_text = line.replace('IMPROVED:', '').strip()
                elif line.startswith('RATIONALE:'):
                    current_section = 'rationale'
                    rationale = line.replace('RATIONALE:', '').strip()
                elif line.startswith('SOURCES:'):
                    current_section = 'sources'
                    sources_text = line.replace('SOURCES:', '').strip()
                    if sources_text:
                        sources = [s.strip() for s in sources_text.split(',')]
                elif current_section == 'improved' and line:
                    improved_text += " " + line
                elif current_section == 'rationale' and line:
                    rationale += " " + line
                elif current_section == 'sources' and line:
                    sources.extend([s.strip() for s in line.split(',')])
            
            # Clean up and validate
            if not improved_text:
                improved_text = ai_response[:200] + "..." if len(ai_response) > 200 else ai_response
            if not rationale:
                rationale = f"AI-enhanced rewrite optimized for {ta.replace('_', ' ')} protocols"
            if not sources:
                sources = guidelines[:2] if guidelines else ["ICH-GCP E6(R2)"]
            
            return {
                "improved": improved_text.strip(),
                "rationale": rationale.strip(),
                "sources": sources[:3],  # Limit to 3 sources
                "model_version": f"azure-openai-{ta}-aware",
                "latency_ms": latency_ms,
                "ta_context": ta,
                "phase_context": phase
            }
            
    except Exception as e:
        logger.warning(f"Azure OpenAI failed for TA rewrite: {e}, falling back to mock")
    
    # Mock fallback generator
    latency_ms = int((time.time() - start_time) * 1000)
    
    # Generate mock improvement based on TA patterns
    ta_specific_improvements = {
        "oncology": {
            "replacements": [
                ("patients", "study participants with confirmed malignancy"),
                ("treatment", "protocol-specified anticancer therapy"),
                ("side effects", "treatment-emergent adverse events per CTCAE v5.0"),
                ("response", "objective response per RECIST v1.1 criteria")
            ],
            "additions": [
                "with baseline and periodic tumor assessments",
                "including mandatory safety laboratory monitoring",
                "per institutional oncology protocols"
            ]
        },
        "cardiovascular": {
            "replacements": [
                ("patients", "participants with cardiovascular disease"),
                ("blood pressure", "systolic and diastolic blood pressure"),
                ("heart", "cardiac function and hemodynamics"),
                ("monitoring", "cardiovascular safety monitoring per ACC/AHA guidelines")
            ],
            "additions": [
                "with baseline ECG and echocardiogram",
                "including cardiac biomarker assessment",
                "per cardiovascular safety protocols"
            ]
        }
    }
    
    improved_text = text
    ta_patterns = ta_specific_improvements.get(ta, ta_specific_improvements.get("oncology"))
    
    # Apply TA-specific replacements
    for original, replacement in ta_patterns["replacements"]:
        if original in improved_text.lower():
            improved_text = improved_text.replace(original, replacement)
    
    # Add TA-specific context
    if ta_patterns["additions"]:
        improved_text += f" {ta_patterns['additions'][0]}"
    
    # Ensure participant terminology
    improved_text = improved_text.replace("patients", "participants").replace("patient", "participant")
    
    return {
        "improved": improved_text,
        "rationale": f"TA-aware enhancement for {ta.replace('_', ' ')} with mock AI generator",
        "sources": guidelines[:2] if guidelines else ["ICH-GCP E6(R2)", f"{ta.title()} Protocol Guidelines"],
        "model_version": f"mock-generator-{ta}-aware",
        "latency_ms": latency_ms,
        "ta_context": ta,
        "phase_context": phase,
        "mock_fallback": True
    }

@app.post("/api/generate-rewrite-ta")
async def generate_rewrite_ta(request: GenerateRewriteTARequest, req: Request):
    """Generate TA-enhanced rewrite with vector DB exemplars and regulatory context"""
    
    # Rate limiting check
    client_ip = req.client.host if req.client else "unknown"
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429, 
            detail=f"Rate limit exceeded. Maximum {MAX_REQUESTS_PER_MINUTE} requests per minute."
        )
    
    start_time = time.time()
    logger.info(f"🎯 TA-Enhanced rewrite request: {request.suggestion_id} for TA: {request.ta}")
    
    # Start telemetry trace
    headers_dict = dict(req.headers.items()) if req.headers else {}
    request_data = {
        "text": request.text,
        "ta": request.ta,
        "phase": request.phase,
        "doc_id": request.doc_id,
        "suggestion_id": request.suggestion_id
    }
    telemetry_request_id = start_trace(
        analyze_mode="ta_enhanced",
        model_path="ta_on_demand",
        request_data=request_data,
        headers=headers_dict
    )
    
    try:
        # Step 1: TA classification if not provided
        ta = request.ta
        ta_classification = None
        
        if not ta:
            logger.info("🔍 Running fast TA classification")
            ta_classification = await fast_ta_classifier(request.text)
            ta = ta_classification["therapeutic_area"]
            logger.info(f"✅ TA classified as: {ta} (confidence: {ta_classification['confidence']:.2f})")
        
        # Step 2: Query vector database for exemplars
        logger.info(f"📚 Querying vector DB for {ta} exemplars")
        exemplars = await query_vector_db(request.text, ta, request.phase)
        logger.info(f"✅ Found {len(exemplars)} exemplars")
        
        # Step 3: Get regulatory guidelines
        guidelines = get_regulatory_guidelines(ta)
        logger.info(f"📋 Retrieved {len(guidelines)} regulatory guidelines")
        
        # Step 4: Generate TA-aware rewrite
        logger.info("🤖 Generating TA-aware rewrite")
        rewrite_result = await generate_ta_aware_rewrite(
            request.text, ta, request.phase, exemplars, guidelines
        )
        
        total_latency = int((time.time() - start_time) * 1000)
        
        # Step 5: Construct response
        response = {
            "suggestion_id": request.suggestion_id,
            "original_text": request.text,
            "improved": rewrite_result["improved"],
            "rationale": rewrite_result["rationale"],
            "sources": rewrite_result["sources"],
            "model_version": rewrite_result["model_version"],
            "latency_ms": total_latency,
            "ta_info": {
                "therapeutic_area": ta,
                "phase": request.phase,
                "confidence": ta_classification["confidence"] if ta_classification else 1.0,
                "detected_keywords": ta_classification["detected_keywords"] if ta_classification else [],
                "exemplars_used": len(exemplars),
                "guidelines_applied": len(guidelines)
            },
            "metadata": {
                "doc_id": request.doc_id,
                "timestamp": datetime.utcnow().isoformat(),
                "model_path": "ta_on_demand",
                "rate_limit_remaining": MAX_REQUESTS_PER_MINUTE - len(rate_limit_storage.get(client_ip, [])),
                "processing_steps": ["ta_classification", "vector_db_query", "regulatory_lookup", "ai_generation"]
            }
        }
        
        logger.info(f"✅ TA-Enhanced rewrite completed in {total_latency}ms")
        
        # End telemetry trace
        end_trace(telemetry_request_id, response, None, {
            "ta_detected": ta,
            "exemplars_used": len(exemplars),
            "guidelines_applied": len(guidelines)
        })
        
        return response
        
    except RAGAsyncModeException as e:
        # Handle RAG gating gracefully
        logger.info(f"ℹ️  TA-Enhanced rewrite blocked by RAG_ASYNC_MODE (expected behavior)")

        # Return standardized 202 response
        return JSONResponse(
            status_code=202,
            content={
                "request_id": request.suggestion_id,
                "result": {"status": "queued"},
                "message": (
                    "RAG is in async mode — TA-enhanced operations are queued to prevent timeouts. "
                    "Use /api/analyze with USE_SIMPLE_AZURE_PROMPT=true for immediate suggestions, "
                    "or set RAG_ASYNC_ALLOW_SYNC=true for testing (not recommended in production)."
                )
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        error_latency = int((time.time() - start_time) * 1000)
        logger.error(f"❌ TA-Enhanced rewrite failed: {e}")
        
        # End telemetry trace with error
        end_trace(telemetry_request_id, None, f"TA-enhanced rewrite failed: {str(e)}", {
            "error_type": type(e).__name__,
            "latency_ms": error_latency
        })
        
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "TA-enhanced rewrite generation failed",
                "message": str(e),
                "latency_ms": error_latency,
                "suggestion_id": request.suggestion_id
            }
        )

@app.post("/api/explain-suggestion")
async def explain_suggestion(request: ExplainSuggestionRequest):
    """
    Expand on a suggestion's rationale with detailed clinical impact explanation.

    This endpoint provides a more detailed explanation of why a suggestion was made,
    including regulatory context, clinical significance, and potential risks.
    """
    start_time = time.time()
    logger.info(f"📖 Explain suggestion request: {request.suggestion_id} (TA: {request.ta})")

    try:
        # Use Azure OpenAI to generate expanded explanation
        from openai import AzureOpenAI
        from config_loader import get_config

        config = get_config("production")
        client = AzureOpenAI(
            api_key=config.azure_openai_api_key,
            api_version="2024-02-01",
            azure_endpoint=config.azure_openai_endpoint
        )

        # Create a prompt to expand on clinical impact
        ta_context = request.ta or "general clinical protocols"
        prompt = f"""You are an expert clinical protocol reviewer with deep knowledge of ICH-GCP guidelines and regulatory requirements.

Provide a detailed explanation of the clinical and regulatory significance of implementing a protocol improvement for {ta_context}.

Your explanation should cover:
1. **Regulatory Context**: Why this change aligns with ICH-GCP, FDA, or EMA guidelines
2. **Clinical Significance**: How this improves participant safety, data quality, or operational efficiency
3. **Risk Mitigation**: What specific risks or compliance issues this addresses
4. **Best Practices**: Industry standards that support this recommendation

Keep the explanation:
- Clinically accurate and evidence-based
- Specific to regulatory requirements
- 3-5 paragraphs in length
- Professional and authoritative in tone

Focus on the "why" behind protocol improvements, not just the "what"."""

        # Call Azure OpenAI
        response = client.chat.completions.create(
            model=config.azure_openai_deployment,
            messages=[
                {"role": "system", "content": "You are an expert clinical protocol reviewer specializing in regulatory compliance and participant safety."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )

        rationale_full = response.choices[0].message.content.strip()
        latency_ms = int((time.time() - start_time) * 1000)

        logger.info(f"✅ Explanation generated in {latency_ms}ms ({len(rationale_full)} chars)")

        return {
            "suggestion_id": request.suggestion_id,
            "rationale_full": rationale_full,
            "rationale": rationale_full,  # Alias for backward compatibility
            "explanation": rationale_full,  # Alias for backward compatibility
            "latency_ms": latency_ms,
            "ta": request.ta,
            "model": config.azure_openai_deployment,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        error_latency = int((time.time() - start_time) * 1000)
        logger.error(f"❌ Explain suggestion failed: {e}")

        # Return a fallback generic explanation
        fallback_text = """This protocol improvement aligns with ICH-GCP E6(R2) guidelines for clinical trial quality and participant safety.

The recommended change enhances regulatory compliance by ensuring clear documentation, standardized terminology, and explicit safety monitoring procedures. These improvements support data integrity, reduce operational ambiguity, and align with FDA 21 CFR Part 312 requirements for investigational new drug applications.

Implementing this change mitigates potential protocol deviations, improves site compliance, and strengthens the overall quality management system for the clinical trial."""

        return {
            "suggestion_id": request.suggestion_id,
            "rationale_full": fallback_text,
            "rationale": fallback_text,
            "explanation": fallback_text,
            "latency_ms": error_latency,
            "ta": request.ta,
            "model": "fallback",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url)
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url)
        }
    )

# ===============================
# TELEMETRY SYSTEM
# ===============================

from telemetry import log_model_call, start_trace, end_trace, count_suggestions, extract_user_id_from_request

# ===============================
# SHADOW WORKER ADMIN API
# ===============================

from ta_shadow_worker import get_shadow_samples, get_shadow_stats, submit_shadow_request

def check_admin_auth(authorization: str = Header(None)) -> bool:
    """Stub admin authentication - replace with real auth in production"""
    # In production, validate JWT token or API key
    # For now, just check for any authorization header
    if not authorization:
        raise HTTPException(
            status_code=401, 
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Stub validation - accept any non-empty token with minimum length
    if authorization.startswith("Bearer ") and len(authorization) > 20:
        return True
    
    raise HTTPException(
        status_code=401,
        detail="Invalid authorization token",
        headers={"WWW-Authenticate": "Bearer"}
    )

@app.get("/api/shadow-samples")
async def get_shadow_samples_endpoint(
    limit: int = Query(50, ge=1, le=200),
    authorization: str = Header(None)
):
    """
    Admin endpoint to fetch shadow processing samples
    Requires authorization header (stubbed authentication)
    """
    # Check admin authentication
    check_admin_auth(authorization)
    
    try:
        samples = get_shadow_samples(limit)
        
        return {
            "samples": samples,
            "count": len(samples),
            "limit": limit,
            "timestamp": datetime.utcnow().isoformat(),
            "admin_endpoint": True
        }
        
    except Exception as e:
        logger.error(f"🔮 Admin API error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch shadow samples: {str(e)}")

@app.get("/api/shadow-stats")
async def get_shadow_stats_endpoint(authorization: str = Header(None)):
    """
    Admin endpoint to fetch shadow processing statistics
    Requires authorization header (stubbed authentication)
    """
    # Check admin authentication
    check_admin_auth(authorization)
    
    try:
        stats = get_shadow_stats()
        
        return {
            "stats": stats,
            "timestamp": datetime.utcnow().isoformat(),
            "admin_endpoint": True
        }
        
    except Exception as e:
        logger.error(f"🔮 Admin stats API error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch shadow stats: {str(e)}")

@app.post("/api/optimize-document-async")
async def optimize_document_async(request: Request):
    """
    Back-compat endpoint expected by frontend.
    Accepts JSON: { text, ta?, user_id_hash? }
    Tries to enqueue a background job in-process; if not available, POSTs to /api/analyze with mode=document_truncated.
    Returns: {"request_id": "...", "result": {"status":"queued", "job_id":"..."}}
    """
    # Gate document analysis when feature flag is disabled
    if not ENABLE_DOCUMENT_ANALYSIS:
        logger.warning("🚫 Document analysis disabled - rejecting /api/optimize-document-async request")
        raise HTTPException(
            status_code=410,
            detail="Document analysis disabled. Use selection-based analysis."
        )

    try:
        payload = await request.json()
        text = payload.get("text", "")
        ta = payload.get("ta")
        user_id_hash = payload.get("user_id_hash")

        logger.info(f"📄 Async document optimization requested - length: {len(text)}, ta: {ta}")
        
        # 1) Try to call an in-process enqueue if available
        try:
            # attempt import - adjust path/name if your enqueue lives elsewhere
            from hybrid_controller import _enqueue_document_job  # type: ignore
            job_id = await _enqueue_document_job({"text": text, "ta": ta, "user_id_hash": user_id_hash})
            logger.info(f"📋 Document job enqueued via in-process: {job_id}")
            return {"request_id": job_id, "result": {"status": "queued", "job_id": job_id}}
        except Exception as e:
            logger.debug("In-process enqueue not available or failed: %s", e)

        # 2) Fallback: call /api/analyze (local HTTP POST) with mode=document_truncated
        try:
            # Construct local base - respect environment if available
            local_base = f"http://127.0.0.1:{int(os.getenv('PORT', 8000))}"
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{local_base}/api/analyze",
                    json={"text": text, "mode": "document_truncated", "ta": ta}
                )
                resp.raise_for_status()
                # Expect the analyze route to return wrapper {request_id, model_path, result}
                result = resp.json()
                logger.info(f"📋 Document job enqueued via HTTP fallback: {result.get('request_id')}")
                return result
        except Exception as e:
            logger.exception("Fallback HTTP enqueue failed: %s", e)
            raise HTTPException(status_code=502, detail="Could not enqueue document analysis")
    except Exception as e:
        logger.error(f"Optimize document async error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process async document request: {str(e)}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )