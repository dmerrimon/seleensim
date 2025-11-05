#!/usr/bin/env python3
"""
Optimization API Endpoint for Protocol Rule Engine
Provides REST API for optimization suggestions
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

from optimization_rule_engine import create_optimization_engine, OptimizationSuggestion
from protocol_parser import create_protocol_parser
from therapeutic_area_classifier import TADetectionResult

logger = logging.getLogger(__name__)

# API Models
class OptimizationRequest(BaseModel):
    doc_id: str
    protocol_text: str
    ta: Optional[str] = None
    phase: Optional[str] = None
    mode: str = "quick"  # quick, full, dry-run

class OptimizationResponse(BaseModel):
    suggestions: List[Dict[str, Any]]
    summary: Dict[str, Any]
    processing_time: float
    doc_id: str

class OptimizationAPI:
    """
    API service for protocol optimization
    """
    
    def __init__(self):
        self.parser = create_protocol_parser()
        self.engine = create_optimization_engine()
        self.app = FastAPI(title="Ilana Optimization API", version="1.0.0")
        
        # Setup routes
        self._setup_routes()
        
        logger.info("🚀 Optimization API initialized")
    
    def _setup_routes(self):
        """Setup FastAPI routes"""
        
        @self.app.post("/api/optimize-procedures", response_model=OptimizationResponse)
        async def optimize_procedures(request: OptimizationRequest, background_tasks: BackgroundTasks):
            """
            Main optimization endpoint
            
            Analyzes protocol text and returns optimization suggestions
            """
            
            start_time = datetime.utcnow()
            
            try:
                logger.info(f"🔧 Starting optimization for doc_id: {request.doc_id}")
                
                # Parse protocol
                parsed_doc = self.parser.parse_protocol(request.protocol_text, request.doc_id)
                
                # Override TA detection if provided
                if request.ta:
                    parsed_doc.ta_detection.therapeutic_area = request.ta
                if request.phase:
                    parsed_doc.ta_detection.phase = request.phase
                
                # Run optimization
                suggestions = self.engine.optimize_document(parsed_doc, mode=request.mode)
                
                # Calculate processing time
                processing_time = (datetime.utcnow() - start_time).total_seconds()
                
                # Convert suggestions to dict format
                suggestion_dicts = [self._suggestion_to_dict(s) for s in suggestions]
                
                # Create summary
                summary = self._create_summary(suggestions, parsed_doc)
                
                # Log telemetry in background
                background_tasks.add_task(
                    self._log_optimization_telemetry,
                    request.doc_id,
                    len(suggestions),
                    processing_time,
                    request.mode
                )
                
                return OptimizationResponse(
                    suggestions=suggestion_dicts,
                    summary=summary,
                    processing_time=processing_time,
                    doc_id=request.doc_id
                )
                
            except Exception as e:
                logger.error(f"❌ Optimization failed for {request.doc_id}: {e}")
                raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")
        
        @self.app.get("/api/optimize/health")
        async def health_check():
            """Health check endpoint"""
            return {"status": "healthy", "service": "optimization-api", "version": "1.0.0"}
        
        @self.app.get("/api/optimize/metrics")
        async def get_metrics():
            """Get optimization metrics and statistics"""
            # This would connect to your metrics store
            return {
                "total_optimizations": 0,
                "avg_suggestions_per_doc": 0,
                "avg_processing_time": 0,
                "top_suggestion_types": []
            }
    
    def _suggestion_to_dict(self, suggestion: OptimizationSuggestion) -> Dict[str, Any]:
        """Convert OptimizationSuggestion to dictionary"""
        
        return {
            "suggestion_id": suggestion.suggestion_id,
            "type": suggestion.type,
            "section_id": suggestion.section_id,
            "location": suggestion.location,
            "suggested_text": suggestion.suggested_text,
            "rationale": suggestion.rationale,
            "sources": suggestion.sources,
            "confidence": suggestion.confidence,
            "impact_estimate": suggestion.impact_estimate,
            "severity": suggestion.severity,
            "original_procedures": suggestion.original_procedures or []
        }
    
    def _create_summary(self, suggestions: List[OptimizationSuggestion], parsed_doc) -> Dict[str, Any]:
        """Create optimization summary"""
        
        if not suggestions:
            return {
                "n_suggestions": 0,
                "top_impact": "No optimization opportunities identified",
                "categories": {},
                "ta_detection": {
                    "therapeutic_area": parsed_doc.ta_detection.therapeutic_area if parsed_doc.ta_detection else "unknown",
                    "confidence": parsed_doc.ta_detection.confidence if parsed_doc.ta_detection else 0
                }
            }
        
        # Group by category
        categories = {}
        for suggestion in suggestions:
            category = suggestion.type
            if category not in categories:
                categories[category] = 0
            categories[category] += 1
        
        # Get top impact suggestion
        top_suggestion = max(suggestions, key=lambda x: x.impact_estimate.get('total_score', 0))
        
        return {
            "n_suggestions": len(suggestions),
            "top_impact": f"{top_suggestion.type.replace('_', ' ').title()}: {top_suggestion.suggested_text[:100]}...",
            "categories": categories,
            "total_impact_score": sum(s.impact_estimate.get('total_score', 0) for s in suggestions),
            "high_confidence_suggestions": len([s for s in suggestions if s.confidence > 0.8]),
            "ta_detection": {
                "therapeutic_area": parsed_doc.ta_detection.therapeutic_area if parsed_doc.ta_detection else "unknown",
                "confidence": parsed_doc.ta_detection.confidence if parsed_doc.ta_detection else 0
            }
        }
    
    async def _log_optimization_telemetry(self, doc_id: str, n_suggestions: int, processing_time: float, mode: str):
        """Log optimization telemetry for monitoring"""
        
        telemetry = {
            "timestamp": datetime.utcnow().isoformat(),
            "doc_id": doc_id,
            "n_suggestions": n_suggestions,
            "processing_time": processing_time,
            "mode": mode,
            "service": "optimization-api"
        }
        
        # In production, this would send to your telemetry system
        logger.info(f"📊 Optimization telemetry: {json.dumps(telemetry)}")

def create_optimization_api() -> OptimizationAPI:
    """Factory function for optimization API"""
    return OptimizationAPI()

# Example standalone server
if __name__ == "__main__":
    import uvicorn
    
    api = create_optimization_api()
    
    print("🚀 Starting Optimization API server...")
    print("📋 Available endpoints:")
    print("   POST /api/optimize-procedures - Main optimization endpoint")
    print("   GET  /api/optimize/health     - Health check")
    print("   GET  /api/optimize/metrics    - Optimization metrics")
    
    uvicorn.run(
        api.app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )