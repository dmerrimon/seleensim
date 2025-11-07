#!/usr/bin/env python3
"""
Simple recommendation service for Ilana Protocol Intelligence
Direct Azure OpenAI calls with simple parsing - no complex pipelines
"""

import os
import re
import json
import time
import hashlib
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Load environment variables
env_path = Path(__file__).parent / "config" / "environments" / "production.env"
if env_path.exists():
    load_dotenv(env_path)

logger = logging.getLogger(__name__)

# Request model
class SimpleRecommendRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="Protocol text to analyze")
    ta: Optional[str] = Field(None, description="Therapeutic area (optional)")
    phase: Optional[str] = Field(None, description="Study phase (optional)")

# Response models
class SimpleSuggestion(BaseModel):
    original: str
    improved: str
    reason: str

class SimpleRecommendResponse(BaseModel):
    suggestions: List[SimpleSuggestion]
    metadata: Dict[str, Any]

# FastAPI app
app = FastAPI(
    title="Ilana Simple Recommendations API",
    description="Simple Azure OpenAI protocol recommendations",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

def redact_phi(text: str) -> str:
    """Redact potential PHI from log text"""
    # Redact patterns that look like MRNs (6-10 digits) or SSNs (9 digits with optional dashes)
    text = re.sub(r'\b\d{6,10}\b', '[REDACTED_MRN]', text)
    text = re.sub(r'\b\d{3}-?\d{2}-?\d{4}\b', '[REDACTED_SSN]', text)
    text = re.sub(r'\b\d{9}\b', '[REDACTED_ID]', text)
    return text

def get_prompt_hash(text: str) -> str:
    """Generate hash of prompt for logging"""
    return hashlib.md5(text.encode()).hexdigest()[:8]

def parse_simple_response(raw_text: str) -> List[Dict[str, str]]:
    """
    Parse Azure OpenAI response into structured suggestions
    
    Expected format:
    ORIGINAL: "<text>"
    IMPROVED: "<text>"
    REASON: "<text>"
    ---
    ORIGINAL: "<text>"
    IMPROVED: "<text>"
    REASON: "<text>"
    """
    suggestions = []
    
    # Split by --- to handle multiple blocks
    blocks = raw_text.split('---')
    
    for block in blocks:
        block = block.strip()
        if not block:
            continue
            
        # Extract ORIGINAL, IMPROVED, REASON using regex
        original_match = re.search(r'ORIGINAL:\s*["\']?([^"\'\n]+)["\']?', block, re.IGNORECASE)
        improved_match = re.search(r'IMPROVED:\s*["\']?([^"\'\n]+)["\']?', block, re.IGNORECASE)
        reason_match = re.search(r'REASON:\s*["\']?([^"\'\n]+)["\']?', block, re.IGNORECASE)
        
        if original_match and improved_match and reason_match:
            suggestions.append({
                "original": original_match.group(1).strip(),
                "improved": improved_match.group(1).strip(),
                "reason": reason_match.group(1).strip()
            })
        else:
            # Fallback: try multiline extraction
            lines = block.split('\n')
            current_suggestion = {}
            
            for line in lines:
                line = line.strip()
                if line.startswith('ORIGINAL:'):
                    current_suggestion['original'] = line.replace('ORIGINAL:', '').strip().strip('"\'')
                elif line.startswith('IMPROVED:'):
                    current_suggestion['improved'] = line.replace('IMPROVED:', '').strip().strip('"\'')
                elif line.startswith('REASON:'):
                    current_suggestion['reason'] = line.replace('REASON:', '').strip().strip('"\'')
            
            if len(current_suggestion) == 3:
                suggestions.append(current_suggestion)
    
    return suggestions

async def call_azure_openai(prompt: str) -> str:
    """Call Azure OpenAI with the given prompt"""
    try:
        from openai import AzureOpenAI
        from config_loader import get_config
        
        config = get_config("production")
        client = AzureOpenAI(
            api_key=config.azure_openai_api_key,
            api_version="2024-02-01",
            azure_endpoint=config.azure_openai_endpoint
        )
        
        response = client.chat.completions.create(
            model=config.azure_openai_deployment,
            messages=[
                {"role": "system", "content": "You are an expert clinical protocol editor."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=512
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"Azure OpenAI call failed: {e}")
        raise

@app.post("/api/recommend-language-simple", response_model=SimpleRecommendResponse)
async def recommend_language_simple(request: SimpleRecommendRequest):
    """Simple language recommendation endpoint"""
    start_time = time.time()
    request_id = hashlib.md5(f"{time.time()}{request.text}".encode()).hexdigest()[:8]
    
    try:
        # Construct the SIMPLE REWRITE prompt
        prompt = f"""You are an expert clinical protocol editor. Improve this short protocol sentence to be precise, auditable, and regulatory-minded. Replace "patient" with "participant" and keep clinical meaning identical.

Text:
"{request.text}"

Rules:
- Do NOT change dose amounts or schedules (if present).
- Use neutral, auditable phrasing.
- If trastuzumab or HER2 therapy is present, add a short cardiotoxicity monitoring clause.

Output format (plain text exactly like this):
ORIGINAL: "<original>"
IMPROVED: "<improved>"
REASON: "<one-sentence rationale referencing guideline if applicable>"

Now improve."""
        
        prompt_hash = get_prompt_hash(prompt)
        
        # Log request (with PHI redaction)
        logger.info(f"Request {request_id}: prompt_hash={prompt_hash}, text_length={len(request.text)}, ta={request.ta}, phase={request.phase}")
        logger.debug(f"Request {request_id}: redacted_text={redact_phi(request.text[:100])}")
        
        # Call Azure OpenAI
        try:
            raw_response = await call_azure_openai(prompt)
            model_call_success = True
        except Exception as e:
            logger.error(f"Request {request_id}: Azure OpenAI call failed: {e}")
            raise HTTPException(status_code=502, detail=f"Model call failed: {str(e)}")
        
        # Parse response
        try:
            suggestions = parse_simple_response(raw_response)
            parse_success = True
        except Exception as e:
            logger.error(f"Request {request_id}: Response parsing failed: {e}")
            suggestions = []
            parse_success = False
        
        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Log results
        logger.info(f"Request {request_id}: "
                   f"latency_ms={latency_ms}, "
                   f"parse_success={parse_success}, "
                   f"suggestion_count={len(suggestions)}, "
                   f"model_version=gpt-4o")
        
        # Prepare response
        response_suggestions = [
            SimpleSuggestion(
                original=s["original"],
                improved=s["improved"],
                reason=s["reason"]
            ) for s in suggestions
        ]
        
        metadata = {
            "request_id": request_id,
            "prompt_hash": prompt_hash,
            "model_version": "gpt-4o",
            "latency_ms": latency_ms,
            "parse_success": parse_success,
            "suggestion_count": len(suggestions),
            "timestamp": datetime.utcnow().isoformat(),
            "ta": request.ta,
            "phase": request.phase
        }
        
        return SimpleRecommendResponse(
            suggestions=response_suggestions,
            metadata=metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Request {request_id}: Unexpected error after {latency_ms}ms: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "simple-recommendations",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(
        "recommend_simple:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )