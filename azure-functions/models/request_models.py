"""
Request models for Azure Functions
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class ProtocolAnalysisRequest(BaseModel):
    """Request model for protocol analysis"""
    text: str = Field(..., min_length=50, max_length=100000, description="Protocol text to analyze")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Analysis options")
    protocol_id: Optional[str] = Field(None, description="Optional protocol identifier")

class ComprehensiveAnalysisRequest(BaseModel):
    """Request model for comprehensive sentence-level analysis"""
    text: str = Field(..., min_length=10, max_length=150000, description="Text to analyze")
    mode: Optional[str] = Field("sentence_level", description="Analysis mode")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Analysis options")

class UserFeedbackRequest(BaseModel):
    """Request model for user feedback and ratings"""
    sessionId: str
    overallRating: Optional[str] = None
    comments: Optional[str] = None
    timestamp: str

class FeedbackRequest(BaseModel):
    """Request model for user feedback"""
    protocol_id: str
    feedback: Dict[str, Any]
    user_id: Optional[str] = None