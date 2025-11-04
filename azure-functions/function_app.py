"""
Azure Functions App for Ilana Protocol Intelligence
Simplified version to fix timeout issues
"""

import azure.functions as func
import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

# Configure Azure Functions logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the function app
app = func.FunctionApp()

@app.function_name("health")
@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint"""
    
    try:
        logger.info("Health check requested")
        
        # Check if environment variables are set
        has_openai = bool(os.getenv('AZURE_OPENAI_ENDPOINT'))
        has_pinecone = bool(os.getenv('PINECONE_API_KEY'))
        
        components_status = {
            "azure_functions": "✅ Active",
            "azure_openai": "✅ Configured" if has_openai else "❌ Not Configured",
            "pinecone": "✅ Configured" if has_pinecone else "❌ Not Configured"
        }
        
        response_data = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "components": components_status
        }
        
        logger.info(f"Health check successful: {response_data}")
        
        return func.HttpResponse(
            json.dumps(response_data),
            status_code=200,
            headers={"Content-Type": "application/json"}
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return func.HttpResponse(
            json.dumps({"status": "unhealthy", "error": str(e)}),
            status_code=500,
            headers={"Content-Type": "application/json"}
        )

@app.function_name("analyze_comprehensive")
@app.route(route="analyze-comprehensive", methods=["POST"])
def analyze_comprehensive(req: func.HttpRequest) -> func.HttpResponse:
    """Simplified analyze comprehensive endpoint"""
    
    try:
        logger.info("Comprehensive analysis requested")
        
        # Parse request
        try:
            req_data = req.get_json()
            if not req_data:
                raise ValueError("No JSON data provided")
            
            text = req_data.get('text', '')
            options = req_data.get('options', {})
            
            if not text or len(text) < 10:
                raise ValueError("Text must be at least 10 characters")
                
        except Exception as e:
            logger.error(f"Request parsing failed: {str(e)}")
            return func.HttpResponse(
                json.dumps({"error": f"Invalid request data: {str(e)}"}),
                status_code=400,
                headers={"Content-Type": "application/json"}
            )
        
        logger.info(f"Processing {len(text)} characters")
        
        # For now, return mock suggestions to test the connection
        mock_suggestions = [
            {
                "type": "clarity",
                "subtype": "general",
                "originalText": text[:50] + "..." if len(text) > 50 else text,
                "suggestedText": "Improved version of the text",
                "rationale": "This text can be made clearer and more concise",
                "complianceRationale": "Improved clarity enhances regulatory compliance",
                "fdaReference": None,
                "emaReference": None,
                "guidanceSource": "General writing best practices",
                "readabilityScore": 85.0,
                "operationalImpact": "Low",
                "retentionRisk": "Low",
                "enrollmentImpact": "Minimal",
                "backendConfidence": "high",
                "range": {"start": 0, "end": min(50, len(text))}
            }
        ]
        
        metadata = {
            "processing_time": 0.5,
            "chunks_processed": 1,
            "total_suggestions": len(mock_suggestions),
            "text_length": len(text),
            "timestamp": datetime.utcnow().isoformat(),
            "mode": "mock"
        }
        
        response_data = {
            "suggestions": mock_suggestions,
            "metadata": metadata
        }
        
        logger.info(f"Analysis completed: {len(mock_suggestions)} suggestions")
        
        return func.HttpResponse(
            json.dumps(response_data),
            status_code=200,
            headers={"Content-Type": "application/json"}
        )
        
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": f"Analysis failed: {str(e)}"}),
            status_code=500,
            headers={"Content-Type": "application/json"}
        )

@app.function_name("analyze_protocol")
@app.route(route="analyze-protocol", methods=["POST"])
def analyze_protocol(req: func.HttpRequest) -> func.HttpResponse:
    """Simplified protocol analysis endpoint"""
    
    try:
        logger.info("Protocol analysis requested")
        
        # Parse request
        try:
            req_data = req.get_json()
            if not req_data:
                raise ValueError("No JSON data provided")
            
            text = req_data.get('text', '')
            protocol_id = req_data.get('protocol_id', f"protocol_{int(datetime.utcnow().timestamp())}")
            
        except Exception as e:
            return func.HttpResponse(
                json.dumps({"error": f"Invalid request data: {str(e)}"}),
                status_code=400,
                headers={"Content-Type": "application/json"}
            )
        
        # Mock response for testing
        response_data = {
            "protocol_id": protocol_id,
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "scores": {
                "compliance": 80.0,
                "clarity": 85.0,
                "engagement": 78.0,
                "delivery": 82.0,
                "overall_quality": 81.25
            },
            "issues": [
                {
                    "type": "clarity",
                    "message": "Some sections could be clearer",
                    "suggestion": "Consider simplifying technical language",
                    "severity": "medium"
                }
            ],
            "recommendations": [
                {
                    "action": "Improve clarity",
                    "category": "clarity",
                    "impact_area": "communication",
                    "expected_improvement": 10.0,
                    "confidence": 85.0,
                    "evidence_strength": "moderate"
                }
            ],
            "therapeutic_area": "General Medicine",
            "confidence_intervals": {"overall": [75.0, 87.0]},
            "processing_time": 0.5,
            "metadata": {
                "text_length": len(text),
                "api_version": "1.0.0",
                "mode": "mock"
            }
        }
        
        logger.info(f"Protocol analysis completed for {protocol_id}")
        
        return func.HttpResponse(
            json.dumps(response_data),
            status_code=200,
            headers={"Content-Type": "application/json"}
        )
        
    except Exception as e:
        logger.error(f"Protocol analysis failed: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": f"Protocol analysis failed: {str(e)}"}),
            status_code=500,
            headers={"Content-Type": "application/json"}
        )

@app.function_name("user_feedback")
@app.route(route="user-feedback", methods=["POST"])
def submit_user_feedback(req: func.HttpRequest) -> func.HttpResponse:
    """Submit user feedback endpoint"""
    
    try:
        logger.info("User feedback submitted")
        
        # Parse request
        req_data = req.get_json()
        session_id = req_data.get('sessionId', 'unknown') if req_data else 'unknown'
        
        response_data = {
            "status": "success",
            "message": "Thank you for your feedback! It helps improve Ilana for everyone.",
            "sessionId": session_id
        }
        
        return func.HttpResponse(
            json.dumps(response_data),
            status_code=200,
            headers={"Content-Type": "application/json"}
        )
        
    except Exception as e:
        logger.error(f"Feedback processing failed: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": f"Feedback processing failed: {str(e)}"}),
            status_code=500,
            headers={"Content-Type": "application/json"}
        )