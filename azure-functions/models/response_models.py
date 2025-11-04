"""
Response models for Azure Functions
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class InlineSuggestion(BaseModel):
    """Individual inline suggestion"""
    type: str
    subtype: Optional[str] = None
    originalText: str
    suggestedText: str
    rationale: str
    complianceRationale: str
    fdaReference: Optional[str] = None
    emaReference: Optional[str] = None
    guidanceSource: Optional[str] = None
    readabilityScore: Optional[float] = None
    operationalImpact: Optional[str] = None
    retentionRisk: Optional[str] = None
    enrollmentImpact: Optional[str] = None
    backendConfidence: Optional[str] = None
    range: Dict[str, int] = Field(default_factory=lambda: {"start": 0, "end": 0})

class ComprehensiveAnalysisResponse(BaseModel):
    """Response model for comprehensive analysis"""
    suggestions: List[InlineSuggestion]
    metadata: Dict[str, Any]

class AnalysisScores(BaseModel):
    """Analysis scores model"""
    compliance: float = Field(..., ge=0, le=100)
    clarity: float = Field(..., ge=0, le=100) 
    engagement: float = Field(..., ge=0, le=100)
    delivery: float = Field(..., ge=0, le=100)
    overall_quality: float = Field(..., ge=0, le=100)

class IssueItem(BaseModel):
    """Individual issue item"""
    type: str
    message: str
    suggestion: Optional[str] = None
    severity: Optional[str] = "medium"

class RecommendationItem(BaseModel):
    """Individual recommendation item"""
    action: str
    category: str
    impact_area: str
    expected_improvement: float
    confidence: float
    evidence_strength: str

class ProtocolAnalysisResponse(BaseModel):
    """Response model for protocol analysis"""
    protocol_id: str
    analysis_timestamp: str
    scores: AnalysisScores
    issues: List[IssueItem]
    recommendations: List[RecommendationItem]
    therapeutic_area: str
    confidence_intervals: Dict[str, List[float]]
    processing_time: float
    metadata: Dict[str, Any]

class FeedbackResponse(BaseModel):
    """Response model for feedback processing"""
    status: str
    message: str
    learning_updates: Optional[Dict[str, Any]] = None

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    version: str
    components: Dict[str, str]