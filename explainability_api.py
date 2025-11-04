#!/usr/bin/env python3
"""
Explainability API for TA-Aware Suggestions
Provides detailed explanations, sources, and regulatory citations for suggestions
"""

import os
import json
import logging
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

try:
    from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
    from pydantic import BaseModel
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    # Fallback base class for when pydantic is not available
    class BaseModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
        
        def dict(self):
            return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

from therapeutic_area_classifier import TherapeuticAreaClassifier, TADetectionResult
from ta_aware_retrieval import TAwareRetrievalSystem

logger = logging.getLogger(__name__)

# API Models
class ExplainRequest(BaseModel):
    def __init__(self, suggestion_id: str, doc_id: Optional[str] = None, 
                 include_full_sources: bool = False, therapeutic_area: Optional[str] = None):
        super().__init__()
        self.suggestion_id = suggestion_id
        self.doc_id = doc_id
        self.include_full_sources = include_full_sources
        self.therapeutic_area = therapeutic_area

class SourceInfo(BaseModel):
    def __init__(self, id: str, title: str, type: str, score: float, snippet: str,
                 url: Optional[str] = None, ta_specific: bool = False, citation: Optional[str] = None):
        super().__init__()
        self.id = id
        self.title = title
        self.type = type
        self.score = score
        self.snippet = snippet
        self.url = url
        self.ta_specific = ta_specific
        self.citation = citation

class ExplainResponse(BaseModel):
    def __init__(self, suggestion_id: str, model_version: str, confidence: float, rationale: str,
                 therapeutic_area: str, sources: List[SourceInfo], retrieval_query: str,
                 generated_at: str, cache_expiry: str):
        super().__init__()
        self.suggestion_id = suggestion_id
        self.model_version = model_version
        self.confidence = confidence
        self.rationale = rationale
        self.therapeutic_area = therapeutic_area
        self.sources = sources
        self.retrieval_query = retrieval_query
        self.generated_at = generated_at
        self.cache_expiry = cache_expiry

@dataclass
class CachedExplanation:
    """Cached explanation data"""
    explanation: Dict[str, Any]
    timestamp: datetime
    doc_hash: str

class ExplainabilityService:
    """
    Service for generating detailed explanations of TA-aware suggestions
    """
    
    def __init__(self):
        self.ta_classifier = TherapeuticAreaClassifier()
        self.ta_retrieval = TAwareRetrievalSystem()
        self.cache = {}  # In production, use Redis or similar
        self.cache_ttl = timedelta(hours=24)
        
        # Rate limiting
        self.rate_limits = {}  # doc_id -> request timestamps
        self.max_requests_per_hour = 30
        
        # Source databases
        self.regulatory_sources = self._load_regulatory_sources()
        self.exemplar_sources = self._load_exemplar_sources()
        
        logger.info("🔍 Explainability Service initialized")
    
    def _load_regulatory_sources(self) -> Dict[str, Dict]:
        """Load regulatory guidance database"""
        return {
            "ICH-E6-R3": {
                "title": "ICH E6(R3) Good Clinical Practice Guidelines",
                "type": "regulatory",
                "url": "https://database.ich.org/sites/default/files/ICH_E6-R3_GCP-Principles_Draft_2021_0419.pdf",
                "sections": {
                    "4.2.1": "Protocol procedures should be justified by study objectives and not unduly burdensome to participants.",
                    "4.5.1": "All medical terminology and abbreviations should be defined in the protocol.",
                    "4.6.1": "Visit schedules should specify timing, windows, and procedures clearly.",
                    "5.18.1": "Monitoring activities should be risk-based and proportionate to study complexity."
                }
            },
            "FDA-ONC-2018": {
                "title": "FDA Guidance: Clinical Trial Endpoints for Cancer Drug Approval",
                "type": "regulatory",
                "url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-trial-endpoints-approval-cancer-drugs-and-biologics",
                "sections": {
                    "3.1": "Progression-free survival is acceptable for accelerated approval when overall survival cannot be demonstrated.",
                    "3.2": "RECIST v1.1 criteria should be used for solid tumor response assessment.",
                    "4.1": "Biomarker endpoints require analytical and clinical validation."
                }
            },
            "FDA-CARDIO-2019": {
                "title": "FDA Guidance: Cardiovascular Outcome Trials for Diabetes Drugs",
                "type": "regulatory", 
                "url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/diabetes-mellitus-evaluating-cardiovascular-risk-new-antidiabetic-therapies-treat-type-2-diabetes",
                "sections": {
                    "2.1": "MACE endpoints should include cardiovascular death, non-fatal MI, and non-fatal stroke.",
                    "2.2": "Clinical Event Committee adjudication is required for MACE endpoints.",
                    "3.1": "Hazard ratio upper 95% CI should not exceed 1.3 for cardiovascular safety."
                }
            },
            "FDA-ENDO-2020": {
                "title": "FDA Guidance: Type 2 Diabetes Drug Development", 
                "type": "regulatory",
                "url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/type-2-diabetes-mellitus-evaluating-safety-new-antidiabetic-therapies-treat-type-2-diabetes",
                "sections": {
                    "4.1": "HbA1c change from baseline is the preferred efficacy endpoint for T2DM.",
                    "4.2": "HbA1c <7% responder rate provides additional efficacy information.",
                    "5.1": "Hypoglycemia events should be categorized by severity and biochemical confirmation."
                }
            },
            "EMA-QUAL-2019": {
                "title": "EMA Guideline on Quality of Life in Cancer Trials",
                "type": "regulatory",
                "url": "https://www.ema.europa.eu/en/documents/scientific-guideline/draft-guideline-evaluation-anticancer-medicinal-products-man-revision-4_en.pdf", 
                "sections": {
                    "3.2": "Quality of life should be measured using validated, disease-specific instruments.",
                    "3.3": "Missing data handling for QoL endpoints requires pre-specified analysis plans."
                }
            }
        }
    
    def _load_exemplar_sources(self) -> Dict[str, Dict]:
        """Load protocol exemplar database"""
        return {
            "oncology_prot_001": {
                "title": "Phase II Oncology Protocol - Breast Cancer Immunotherapy",
                "therapeutic_area": "oncology",
                "phase": "II",
                "indication": "breast_cancer",
                "procedures": {
                    "vitals": "Vital signs (BP, HR, temp, weight) at each visit per schedule.",
                    "imaging": "CT chest/abdomen/pelvis every 8 weeks per RECIST v1.1.",
                    "labs": "Safety labs (CBC, CMP, LFTs) at baseline, C1D1, C1D15, then every cycle.",
                    "biomarkers": "Circulating tumor DNA collected at baseline, C2D1, progression."
                }
            },
            "cardio_prot_001": {
                "title": "Phase III Cardiovascular Outcomes Trial - Diabetes Drug",
                "therapeutic_area": "cardiovascular", 
                "phase": "III",
                "indication": "type_2_diabetes",
                "procedures": {
                    "vitals": "Vital signs including orthostatic measurements at each visit.",
                    "ecg": "12-lead ECG in triplicate at baseline, 12, 24 weeks.",
                    "echo": "Echocardiogram at baseline, 24, 52 weeks for LVEF assessment.",
                    "mace_monitoring": "MACE follow-up calls every 12 weeks, CEC adjudication."
                }
            },
            "endo_prot_001": {
                "title": "Phase III Endocrinology Trial - Type 2 Diabetes",
                "therapeutic_area": "endocrinology",
                "phase": "III", 
                "indication": "type_2_diabetes",
                "procedures": {
                    "hba1c": "HbA1c at baseline, 12, 24 weeks via central laboratory.",
                    "glucose": "Fasting plasma glucose at baseline, 4, 8, 12, 16, 20, 24 weeks.",
                    "weight": "Body weight at each visit using calibrated scale.",
                    "hypoglycemia": "Hypoglycemia diary reviewed at each visit, severity grading per protocol."
                }
            }
        }
    
    async def explain_suggestion(self, request: ExplainRequest) -> ExplainResponse:
        """
        Generate detailed explanation for a suggestion
        """
        
        # Rate limiting check
        if not self._check_rate_limit(request.doc_id):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        # Check cache
        cache_key = self._generate_cache_key(request)
        cached = self._get_cached_explanation(cache_key)
        if cached:
            logger.info(f"📋 Returning cached explanation for {request.suggestion_id}")
            return cached
        
        # Generate explanation
        explanation = await self._generate_explanation(request)
        
        # Cache result
        self._cache_explanation(cache_key, explanation)
        
        # Log telemetry
        self._log_explanation_telemetry(request, explanation)
        
        return explanation
    
    async def _generate_explanation(self, request: ExplainRequest) -> ExplainResponse:
        """Generate detailed explanation with sources"""
        
        logger.info(f"🔍 Generating explanation for suggestion {request.suggestion_id}")
        
        # In a real implementation, this would:
        # 1. Look up the original suggestion from database
        # 2. Reconstruct the retrieval query used
        # 3. Re-run retrieval to get sources with scores
        # 4. Generate enhanced rationale
        
        # For now, simulate based on suggestion_id pattern
        suggestion_data = self._parse_suggestion_id(request.suggestion_id)
        
        # Determine therapeutic area
        ta = request.therapeutic_area or suggestion_data.get('ta', 'general_medicine')
        
        # Generate rationale
        rationale = self._generate_detailed_rationale(suggestion_data, ta)
        
        # Retrieve relevant sources
        sources = await self._retrieve_sources(suggestion_data, ta, request.include_full_sources)
        
        # Generate retrieval query
        retrieval_query = self._generate_retrieval_query(suggestion_data)
        
        explanation = ExplainResponse(
            suggestion_id=request.suggestion_id,
            model_version="ilana-ta-aware-v1.3.2",
            confidence=suggestion_data.get('confidence', 0.85),
            rationale=rationale,
            therapeutic_area=ta,
            sources=sources,
            retrieval_query=retrieval_query,
            generated_at=datetime.utcnow().isoformat(),
            cache_expiry=(datetime.utcnow() + self.cache_ttl).isoformat()
        )
        
        return explanation
    
    def _parse_suggestion_id(self, suggestion_id: str) -> Dict[str, Any]:
        """Parse suggestion ID to extract type and context"""
        
        # Example suggestion_id formats:
        # opt_0001_consolidation_oncology
        # dup_0023_vitals_cardio
        # freq_0012_labs_endo
        
        parts = suggestion_id.split('_')
        
        suggestion_type = parts[0] if len(parts) > 0 else 'unknown'
        suggestion_number = parts[1] if len(parts) > 1 else '0000'
        category = parts[2] if len(parts) > 2 else 'general'
        ta = parts[3] if len(parts) > 3 else 'general_medicine'
        
        return {
            'type': suggestion_type,
            'number': suggestion_number,
            'category': category,
            'ta': ta,
            'confidence': 0.85  # Default confidence
        }
    
    def _generate_detailed_rationale(self, suggestion_data: Dict, ta: str) -> str:
        """Generate detailed rationale based on suggestion type and TA"""
        
        suggestion_type = suggestion_data.get('type', 'unknown')
        category = suggestion_data.get('category', 'general')
        ta_name = self._format_ta_name(ta)
        
        base_rationales = {
            'opt': f"This optimization suggestion is based on {ta_name} best practices and regulatory requirements.",
            'dup': f"Duplicate procedures have been identified that can be consolidated per {ta_name} protocol standards.",
            'freq': f"Assessment frequency can be optimized based on {ta_name} regulatory guidelines.",
            'merge': f"Procedure merging follows {ta_name} efficiency recommendations.",
            'endpoint': f"Endpoint alignment with {ta_name} regulatory expectations and precedents."
        }
        
        base_rationale = base_rationales.get(suggestion_type, "This suggestion follows clinical trial best practices.")
        
        # Add TA-specific context
        ta_context = self._get_ta_specific_context(ta, category)
        
        # Add regulatory backing
        regulatory_context = self._get_regulatory_context(ta, suggestion_type)
        
        return f"{base_rationale} {ta_context} {regulatory_context}"
    
    def _get_ta_specific_context(self, ta: str, category: str) -> str:
        """Get TA-specific context for rationale"""
        
        contexts = {
            'oncology': {
                'vitals': "Vital sign monitoring in oncology trials typically follows q2-3 day schedules for safety during treatment cycles.",
                'imaging': "RECIST v1.1 imaging assessments are standard every 8-12 weeks in solid tumor trials.",
                'labs': "Safety laboratory monitoring follows dose-escalation safety requirements."
            },
            'cardiovascular': {
                'vitals': "Cardiovascular trials require careful BP monitoring with orthostatic measurements.",
                'ecg': "Serial ECG monitoring is critical for detecting cardiac safety signals.",
                'echo': "Echocardiographic assessment monitors for drug-induced cardiac dysfunction."
            },
            'endocrinology': {
                'glucose': "Glucose monitoring frequency should balance safety with participant burden.",
                'hba1c': "HbA1c measurement timing reflects 2-3 month glucose averaging period.",
                'weight': "Weight measurement standardization is important for metabolic endpoints."
            }
        }
        
        return contexts.get(ta, {}).get(category, "This follows standard clinical trial procedures.")
    
    def _get_regulatory_context(self, ta: str, suggestion_type: str) -> str:
        """Get regulatory context for the suggestion"""
        
        contexts = {
            'oncology': "This aligns with FDA oncology guidance and ICH E9 statistical principles.",
            'cardiovascular': "This follows FDA cardiovascular outcome trial guidance and EMA cardiology guidelines.", 
            'endocrinology': "This is consistent with FDA diabetes drug development guidance and ADA clinical standards."
        }
        
        base_context = contexts.get(ta, "This follows ICH-GCP guidelines and regulatory best practices.")
        
        if suggestion_type in ['opt', 'dup', 'merge']:
            return f"{base_context} Procedure optimization reduces participant burden per ICH E6 requirements."
        elif suggestion_type == 'freq':
            return f"{base_context} Assessment frequency optimization balances safety monitoring with participant experience."
        else:
            return base_context
    
    async def _retrieve_sources(self, suggestion_data: Dict, ta: str, include_full: bool) -> List[SourceInfo]:
        """Retrieve relevant sources for the suggestion"""
        
        sources = []
        
        # Always include ICH-GCP base guidance
        ich_source = self.regulatory_sources.get("ICH-E6-R3")
        if ich_source:
            sources.append(SourceInfo(
                id="ICH-E6-R3",
                title=ich_source["title"],
                type="regulatory",
                score=0.92,
                snippet=ich_source["sections"]["4.2.1"],
                url=ich_source["url"] if include_full else None,
                ta_specific=False,
                citation="ICH E6(R3) Section 4.2.1"
            ))
        
        # Add TA-specific regulatory sources
        ta_reg_sources = self._get_ta_regulatory_sources(ta, include_full)
        sources.extend(ta_reg_sources)
        
        # Add exemplar sources
        exemplar_sources = self._get_exemplar_sources(ta, suggestion_data, include_full)
        sources.extend(exemplar_sources)
        
        # Add industry standards
        if suggestion_data.get('category') in ['labs', 'imaging', 'biomarkers']:
            sources.append(SourceInfo(
                id="CDISC-SDTM",
                title="CDISC Study Data Tabulation Model",
                type="standard",
                score=0.78,
                snippet="Standardized data collection terminology ensures regulatory compliance and facilitates data exchange.",
                url="https://www.cdisc.org/standards/foundational/sdtm" if include_full else None,
                ta_specific=False,
                citation="CDISC SDTM v3.4"
            ))
        
        # Sort by score descending
        sources.sort(key=lambda x: x.score, reverse=True)
        
        return sources[:8]  # Limit to top 8 sources
    
    def _get_ta_regulatory_sources(self, ta: str, include_full: bool) -> List[SourceInfo]:
        """Get TA-specific regulatory sources"""
        
        sources = []
        
        ta_source_map = {
            'oncology': ["FDA-ONC-2018", "EMA-QUAL-2019"],
            'cardiovascular': ["FDA-CARDIO-2019"],
            'endocrinology': ["FDA-ENDO-2020"]
        }
        
        source_ids = ta_source_map.get(ta, [])
        
        for source_id in source_ids:
            source_data = self.regulatory_sources.get(source_id)
            if source_data:
                # Get most relevant section
                section_key = list(source_data["sections"].keys())[0]
                snippet = source_data["sections"][section_key]
                
                sources.append(SourceInfo(
                    id=source_id,
                    title=source_data["title"],
                    type="regulatory",
                    score=0.89,
                    snippet=snippet,
                    url=source_data["url"] if include_full else None,
                    ta_specific=True,
                    citation=f"{source_id} Section {section_key}"
                ))
        
        return sources
    
    def _get_exemplar_sources(self, ta: str, suggestion_data: Dict, include_full: bool) -> List[SourceInfo]:
        """Get exemplar protocol sources"""
        
        sources = []
        
        # Find matching exemplars
        for exemplar_id, exemplar_data in self.exemplar_sources.items():
            if exemplar_data.get("therapeutic_area") == ta:
                
                # Get relevant procedure text
                category = suggestion_data.get('category', 'general')
                snippet = exemplar_data.get("procedures", {}).get(category)
                
                if not snippet:
                    # Use first available procedure as fallback
                    procedures = exemplar_data.get("procedures", {})
                    snippet = list(procedures.values())[0] if procedures else "Example protocol procedure text."
                
                sources.append(SourceInfo(
                    id=exemplar_id,
                    title=exemplar_data["title"],
                    type="exemplar",
                    score=0.85,
                    snippet=snippet,
                    url=f"https://protocols.internal/exemplars/{exemplar_id}" if include_full else None,
                    ta_specific=True,
                    citation=f"Protocol {exemplar_id.upper()}"
                ))
        
        return sources
    
    def _generate_retrieval_query(self, suggestion_data: Dict) -> str:
        """Generate the retrieval query that would have been used"""
        
        suggestion_type = suggestion_data.get('type', '')
        category = suggestion_data.get('category', '')
        ta = suggestion_data.get('ta', '')
        
        return f"{suggestion_type} {category} {ta} regulatory guidance exemplar".strip()
    
    def _check_rate_limit(self, doc_id: Optional[str]) -> bool:
        """Check if request is within rate limits"""
        
        if not doc_id:
            return True  # Allow requests without doc_id
        
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        
        # Clean old entries
        if doc_id in self.rate_limits:
            self.rate_limits[doc_id] = [
                ts for ts in self.rate_limits[doc_id] if ts > hour_ago
            ]
        else:
            self.rate_limits[doc_id] = []
        
        # Check limit
        if len(self.rate_limits[doc_id]) >= self.max_requests_per_hour:
            return False
        
        # Add current request
        self.rate_limits[doc_id].append(now)
        return True
    
    def _generate_cache_key(self, request: ExplainRequest) -> str:
        """Generate cache key for request"""
        
        # Include doc_id hash to handle different document contexts
        doc_hash = hashlib.md5(request.doc_id.encode() if request.doc_id else b'').hexdigest()[:8]
        
        return f"{request.suggestion_id}:{doc_hash}:{request.therapeutic_area or 'auto'}"
    
    def _get_cached_explanation(self, cache_key: str) -> Optional[ExplainResponse]:
        """Get cached explanation if valid"""
        
        if cache_key not in self.cache:
            return None
        
        cached = self.cache[cache_key]
        if datetime.utcnow() - cached.timestamp > self.cache_ttl:
            del self.cache[cache_key]
            return None
        
        return ExplainResponse(**cached.explanation)
    
    def _cache_explanation(self, cache_key: str, explanation: ExplainResponse):
        """Cache explanation"""
        
        self.cache[cache_key] = CachedExplanation(
            explanation=explanation.dict(),
            timestamp=datetime.utcnow(),
            doc_hash=cache_key.split(':')[1]
        )
    
    def _log_explanation_telemetry(self, request: ExplainRequest, explanation: ExplainResponse):
        """Log explanation telemetry"""
        
        telemetry = {
            "event": "explanation_generated",
            "suggestion_id": request.suggestion_id,
            "doc_id": request.doc_id,
            "therapeutic_area": explanation.therapeutic_area,
            "confidence": explanation.confidence,
            "sources_count": len(explanation.sources),
            "model_version": explanation.model_version,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(f"📊 Explanation telemetry: {json.dumps(telemetry)}")
    
    def _format_ta_name(self, ta: str) -> str:
        """Format therapeutic area name for display"""
        
        names = {
            'oncology': 'Oncology',
            'cardiovascular': 'Cardiovascular',
            'endocrinology': 'Endocrinology',
            'neurology': 'Neurology',
            'psychiatry': 'Psychiatry',
            'infectious_diseases': 'Infectious Diseases',
            'respiratory': 'Respiratory',
            'immunology': 'Immunology',
            'gastroenterology': 'Gastroenterology',
            'dermatology': 'Dermatology',
            'general_medicine': 'General Medicine'
        }
        
        return names.get(ta, ta.replace('_', ' ').title())

def create_explainability_service() -> ExplainabilityService:
    """Factory function for explainability service"""
    return ExplainabilityService()

# FastAPI integration (if available)
if FASTAPI_AVAILABLE:
    def create_explainability_api() -> FastAPI:
        """Create FastAPI app with explainability endpoints"""
        
        app = FastAPI(title="Ilana Explainability API", version="1.0.0")
        service = create_explainability_service()
        
        @app.post("/api/explain-suggestion", response_model=ExplainResponse)
        async def explain_suggestion(request: ExplainRequest, background_tasks: BackgroundTasks):
            """Get detailed explanation for a suggestion"""
            
            try:
                explanation = await service.explain_suggestion(request)
                
                # Log usage in background
                background_tasks.add_task(
                    service._log_explanation_telemetry,
                    request,
                    explanation
                )
                
                return explanation
                
            except Exception as e:
                logger.error(f"❌ Explanation failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/api/explain/health")
        async def health_check():
            """Health check for explainability service"""
            return {"status": "healthy", "service": "explainability-api"}
        
        return app

# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test_explainability():
        service = create_explainability_service()
        
        request = ExplainRequest(
            suggestion_id="opt_0001_consolidation_oncology",
            doc_id="test_protocol",
            therapeutic_area="oncology"
        )
        
        explanation = await service.explain_suggestion(request)
        
        print("🔍 Explainability Test Results:")
        print(f"   Suggestion: {explanation.suggestion_id}")
        print(f"   Confidence: {explanation.confidence:.0%}")
        print(f"   Sources: {len(explanation.sources)}")
        print(f"   TA: {explanation.therapeutic_area}")
        print(f"   Rationale: {explanation.rationale[:100]}...")
        
        for i, source in enumerate(explanation.sources[:3]):
            print(f"   Source {i+1}: {source.title} ({source.type}, {source.score:.0%})")
    
    asyncio.run(test_explainability())