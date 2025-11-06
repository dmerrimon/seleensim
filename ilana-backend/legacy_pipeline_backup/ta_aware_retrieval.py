#!/usr/bin/env python3
"""
Therapeutic Area Aware Retrieval System
Provides TA-filtered exemplar retrieval and endpoint suggestions
"""

import os
import json
import logging
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
import hashlib

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    print("⚠️ ChromaDB not available, using fallback retrieval")

from therapeutic_area_classifier import TherapeuticAreaClassifier, TADetectionResult

logger = logging.getLogger(__name__)

@dataclass
class ProtocolExemplar:
    """Protocol exemplar for retrieval"""
    id: str
    text: str
    therapeutic_area: str
    subindication: str
    phase: str
    section_type: str  # objectives, endpoints, procedures, etc.
    source: str
    metadata: Dict[str, Any]

@dataclass
class RetrievalResult:
    """Result from exemplar retrieval"""
    exemplar: ProtocolExemplar
    relevance_score: float
    ta_match_score: float
    section_match_score: float

@dataclass
class EndpointSuggestion:
    """Endpoint suggestion with rationale"""
    endpoint_text: str
    endpoint_type: str  # primary, secondary, exploratory
    measurement_method: str
    frequency: str
    rationale: str
    regulatory_precedent: str
    source_exemplars: List[str]
    confidence: float

class TAwareRetrievalSystem:
    """
    Therapeutic Area Aware Retrieval System
    
    Provides:
    - TA-filtered exemplar retrieval 
    - Disease-specific endpoint suggestions
    - Protocol section templates
    """
    
    # ENDPOINT LIBRARY BY THERAPEUTIC AREA
    ENDPOINT_LIBRARY = {
        'oncology': {
            'primary_endpoints': [
                {
                    'text': 'Progression-free survival (PFS) as assessed by investigator according to RECIST v1.1',
                    'type': 'survival',
                    'measurement': 'RECIST v1.1 imaging assessments',
                    'frequency': 'Every 8 weeks for first 2 years, then every 12 weeks',
                    'rationale': 'Primary efficacy endpoint for solid tumor trials, regulatory accepted',
                    'precedent': 'FDA Guidance on Clinical Trial Endpoints for Cancer Drug Approval'
                },
                {
                    'text': 'Overall survival (OS) defined as time from randomization to death from any cause',
                    'type': 'survival', 
                    'measurement': 'Survival status collection',
                    'frequency': 'Every 12 weeks until death or study closure',
                    'rationale': 'Gold standard endpoint for cancer trials, ultimate clinical benefit',
                    'precedent': 'ICH E9 Statistical Principles for Clinical Trials'
                },
                {
                    'text': 'Objective response rate (ORR) per RECIST v1.1 by investigator assessment',
                    'type': 'response',
                    'measurement': 'RECIST v1.1 imaging assessments',
                    'frequency': 'Every 8 weeks until progression',
                    'rationale': 'Surrogate endpoint for accelerated approval in oncology',
                    'precedent': '21 CFR 314.510 Accelerated Approval'
                },
                {
                    'text': 'Pathological complete response (pCR) rate in neoadjuvant setting',
                    'type': 'pathological',
                    'measurement': 'Surgical pathology assessment',
                    'frequency': 'At time of surgery',
                    'rationale': 'Surrogate endpoint for neoadjuvant breast cancer trials',
                    'precedent': 'FDA Guidance on Pathological Complete Response'
                }
            ],
            'secondary_endpoints': [
                {
                    'text': 'Duration of response (DoR) in patients with confirmed response',
                    'type': 'survival',
                    'measurement': 'RECIST v1.1 imaging assessments',
                    'frequency': 'Every 8 weeks until progression',
                    'rationale': 'Assesses durability of treatment benefit',
                    'precedent': 'FDA Guidance on Clinical Trial Endpoints'
                },
                {
                    'text': 'Safety and tolerability assessed by CTCAE v5.0',
                    'type': 'safety',
                    'measurement': 'CTCAE grading of adverse events',
                    'frequency': 'Continuously throughout study',
                    'rationale': 'Required safety assessment for all cancer trials',
                    'precedent': 'ICH E6 Good Clinical Practice'
                }
            ]
        },
        'cardiovascular': {
            'primary_endpoints': [
                {
                    'text': 'Major Adverse Cardiovascular Events (MACE) composite of cardiovascular death, non-fatal myocardial infarction, and non-fatal stroke',
                    'type': 'composite',
                    'measurement': 'Clinical Event Committee adjudication',
                    'frequency': 'Event-driven, minimum 6-month follow-up',
                    'rationale': 'Standard composite endpoint for cardiovascular outcomes trials',
                    'precedent': 'FDA Guidance on Cardiovascular Outcome Trials'
                },
                {
                    'text': 'Change in left ventricular ejection fraction (LVEF) from baseline to 12 weeks',
                    'type': 'functional',
                    'measurement': 'Echocardiography (ECHO) or MUGA scan',
                    'frequency': 'Baseline, 6 weeks, 12 weeks',
                    'rationale': 'Surrogate endpoint for heart failure drug development',
                    'precedent': 'FDA Draft Guidance on Heart Failure'
                },
                {
                    'text': 'Change in systolic blood pressure from baseline to 8 weeks',
                    'type': 'biomarker',
                    'measurement': 'Standardized office blood pressure measurement',
                    'frequency': 'Baseline, 2, 4, 6, 8 weeks',
                    'rationale': 'Validated surrogate endpoint for hypertension trials',
                    'precedent': 'FDA Guidance on Hypertension Drug Development'
                }
            ],
            'secondary_endpoints': [
                {
                    'text': 'Change in 6-minute walk distance from baseline',
                    'type': 'functional',
                    'measurement': '6-minute walk test per ATS guidelines',
                    'frequency': 'Baseline, 6, 12, 24 weeks',
                    'rationale': 'Functional assessment of exercise capacity',
                    'precedent': 'ATS Guidelines for 6-Minute Walk Test'
                }
            ]
        },
        'endocrinology': {
            'primary_endpoints': [
                {
                    'text': 'Change in HbA1c from baseline to 24 weeks',
                    'type': 'biomarker',
                    'measurement': 'Central laboratory HbA1c measurement',
                    'frequency': 'Baseline, 12, 24 weeks',
                    'rationale': 'Gold standard endpoint for diabetes drug development',
                    'precedent': 'FDA Guidance on Type 2 Diabetes Drug Development'
                },
                {
                    'text': 'Percentage of patients achieving HbA1c <7% at 24 weeks',
                    'type': 'responder',
                    'measurement': 'Central laboratory HbA1c measurement',
                    'frequency': 'Week 24',
                    'rationale': 'Clinical target achievement endpoint for diabetes',
                    'precedent': 'ADA Clinical Practice Recommendations'
                },
                {
                    'text': 'Change in body weight from baseline to 24 weeks',
                    'type': 'anthropometric',
                    'measurement': 'Standardized weight measurement',
                    'frequency': 'Baseline, 4, 8, 12, 16, 20, 24 weeks',
                    'rationale': 'Important endpoint for obesity and diabetes drug development',
                    'precedent': 'FDA Guidance on Weight Management Drug Development'
                }
            ]
        },
        'neurology': {
            'primary_endpoints': [
                {
                    'text': 'Change in Alzheimer Disease Assessment Scale-Cognitive Subscale (ADAS-Cog) from baseline',
                    'type': 'cognitive',
                    'measurement': 'ADAS-Cog assessment by trained rater',
                    'frequency': 'Baseline, 12, 24, 52 weeks',
                    'rationale': 'FDA-qualified endpoint for Alzheimer disease trials',
                    'precedent': 'FDA Guidance on Alzheimer Disease Drug Development'
                },
                {
                    'text': 'Change in Unified Parkinson Disease Rating Scale (UPDRS) Part III from baseline',
                    'type': 'functional',
                    'measurement': 'UPDRS Part III assessment by qualified rater',
                    'frequency': 'Baseline, 4, 8, 12, 24 weeks',
                    'rationale': 'Standard motor assessment for Parkinson disease trials',
                    'precedent': 'FDA Guidance on Parkinson Disease Drug Development'
                },
                {
                    'text': 'Seizure frequency reduction from baseline seizure frequency',
                    'type': 'clinical',
                    'measurement': 'Patient diary and caregiver reports',
                    'frequency': 'Daily diary throughout study',
                    'rationale': 'Primary endpoint for antiepileptic drug development',
                    'precedent': 'FDA Guidance on Epilepsy Drug Development'
                }
            ]
        }
    }
    
    def __init__(self):
        self.ta_classifier = TherapeuticAreaClassifier()
        self.vector_db = None
        self.exemplar_store = {}
        
        # Initialize vector database if available
        if CHROMA_AVAILABLE:
            self._initialize_chroma_db()
        
        logger.info("🔍 TA-Aware Retrieval System initialized")
    
    def _initialize_chroma_db(self):
        """Initialize ChromaDB for vector storage"""
        try:
            self.vector_db = chromadb.Client(Settings(
                persist_directory="./data/ta_vectors",
                anonymized_telemetry=False
            ))
            
            # Create or get collection
            try:
                self.collection = self.vector_db.get_collection("ta_protocols")
                logger.info("✅ Connected to existing TA vector collection")
            except:
                self.collection = self.vector_db.create_collection(
                    name="ta_protocols",
                    metadata={"description": "TA-aware protocol exemplars"}
                )
                logger.info("✅ Created new TA vector collection")
                
        except Exception as e:
            logger.warning(f"⚠️ ChromaDB initialization failed: {e}")
            self.vector_db = None
    
    def add_protocol_exemplar(self, exemplar: ProtocolExemplar):
        """Add protocol exemplar to the retrieval system"""
        
        # Store exemplar
        self.exemplar_store[exemplar.id] = exemplar
        
        # Add to vector database if available
        if self.vector_db and self.collection:
            try:
                # Create metadata for filtering
                metadata = {
                    "therapeutic_area": exemplar.therapeutic_area,
                    "subindication": exemplar.subindication,
                    "phase": exemplar.phase,
                    "section_type": exemplar.section_type,
                    "source": exemplar.source
                }
                metadata.update(exemplar.metadata)
                
                # Add to collection
                self.collection.add(
                    documents=[exemplar.text],
                    metadatas=[metadata],
                    ids=[exemplar.id]
                )
                
                logger.debug(f"Added exemplar {exemplar.id} to vector DB")
                
            except Exception as e:
                logger.warning(f"Failed to add exemplar to vector DB: {e}")
    
    def retrieve_exemplars(
        self, 
        query_text: str, 
        therapeutic_area: str = None,
        phase: str = None,
        section_type: str = None,
        top_k: int = 5
    ) -> List[RetrievalResult]:
        """
        Retrieve relevant protocol exemplars
        
        Args:
            query_text: Text to search for
            therapeutic_area: Filter by TA
            phase: Filter by study phase
            section_type: Filter by section type
            top_k: Number of results to return
            
        Returns:
            List of RetrievalResult objects
        """
        
        # Auto-detect TA if not provided
        if not therapeutic_area:
            ta_result = self.ta_classifier.detect_therapeutic_area(query_text)
            therapeutic_area = ta_result.therapeutic_area
            logger.info(f"Auto-detected TA: {therapeutic_area}")
        
        results = []
        
        # Vector search if available
        if self.vector_db and self.collection:
            try:
                # Build where clause for filtering
                where_clause = {}
                if therapeutic_area and therapeutic_area != "general_medicine":
                    where_clause["therapeutic_area"] = therapeutic_area
                if phase:
                    where_clause["phase"] = phase
                if section_type:
                    where_clause["section_type"] = section_type
                
                # Query vector database
                query_results = self.collection.query(
                    query_texts=[query_text],
                    n_results=top_k * 2,  # Get more to allow for filtering
                    where=where_clause if where_clause else None
                )
                
                # Process results
                for i, doc_id in enumerate(query_results['ids'][0]):
                    if doc_id in self.exemplar_store:
                        exemplar = self.exemplar_store[doc_id]
                        distance = query_results['distances'][0][i]
                        relevance_score = max(0, 1 - distance)  # Convert distance to similarity
                        
                        # Calculate TA match score
                        ta_match_score = 1.0 if exemplar.therapeutic_area == therapeutic_area else 0.3
                        
                        # Calculate section match score
                        section_match_score = 1.0 if exemplar.section_type == section_type else 0.7
                        
                        results.append(RetrievalResult(
                            exemplar=exemplar,
                            relevance_score=relevance_score,
                            ta_match_score=ta_match_score,
                            section_match_score=section_match_score
                        ))
                
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")
        
        # Fallback to keyword search
        if not results:
            results = self._fallback_keyword_search(
                query_text, therapeutic_area, phase, section_type, top_k
            )
        
        # Sort by combined score and return top_k
        for result in results:
            result.combined_score = (
                result.relevance_score * 0.5 +
                result.ta_match_score * 0.3 +
                result.section_match_score * 0.2
            )
        
        results.sort(key=lambda x: x.combined_score, reverse=True)
        return results[:top_k]
    
    def _fallback_keyword_search(
        self, 
        query_text: str,
        therapeutic_area: str,
        phase: str,
        section_type: str,
        top_k: int
    ) -> List[RetrievalResult]:
        """Fallback keyword-based search"""
        
        query_words = set(query_text.lower().split())
        results = []
        
        for exemplar in self.exemplar_store.values():
            # Filter by criteria
            if therapeutic_area and exemplar.therapeutic_area != therapeutic_area:
                continue
            if phase and exemplar.phase != phase:
                continue
            if section_type and exemplar.section_type != section_type:
                continue
            
            # Calculate keyword overlap
            exemplar_words = set(exemplar.text.lower().split())
            overlap = len(query_words.intersection(exemplar_words))
            relevance_score = overlap / max(len(query_words), 1)
            
            if relevance_score > 0:
                results.append(RetrievalResult(
                    exemplar=exemplar,
                    relevance_score=relevance_score,
                    ta_match_score=1.0,
                    section_match_score=1.0
                ))
        
        return results
    
    def suggest_endpoints(
        self, 
        objective_text: str,
        therapeutic_area: str = None,
        phase: str = None,
        endpoint_type: str = "primary"
    ) -> List[EndpointSuggestion]:
        """
        Suggest appropriate endpoints based on study objectives
        
        Args:
            objective_text: Study objectives text
            therapeutic_area: TA (auto-detected if None)
            phase: Study phase
            endpoint_type: primary, secondary, or exploratory
            
        Returns:
            List of EndpointSuggestion objects
        """
        
        # Auto-detect TA if not provided
        if not therapeutic_area:
            ta_result = self.ta_classifier.detect_therapeutic_area(objective_text)
            therapeutic_area = ta_result.therapeutic_area
            logger.info(f"Auto-detected TA for endpoints: {therapeutic_area}")
        
        suggestions = []
        
        # Get endpoints from library
        if therapeutic_area in self.ENDPOINT_LIBRARY:
            ta_endpoints = self.ENDPOINT_LIBRARY[therapeutic_area]
            endpoint_category = f"{endpoint_type}_endpoints"
            
            if endpoint_category in ta_endpoints:
                for endpoint_data in ta_endpoints[endpoint_category]:
                    # Calculate relevance based on objective text
                    relevance = self._calculate_endpoint_relevance(
                        objective_text, endpoint_data
                    )
                    
                    if relevance > 0.1:  # Lowered threshold for broader suggestions
                        suggestion = EndpointSuggestion(
                            endpoint_text=endpoint_data['text'],
                            endpoint_type=endpoint_type,
                            measurement_method=endpoint_data['measurement'],
                            frequency=endpoint_data['frequency'],
                            rationale=endpoint_data['rationale'],
                            regulatory_precedent=endpoint_data['precedent'],
                            source_exemplars=[f"{therapeutic_area}_library"],
                            confidence=relevance
                        )
                        suggestions.append(suggestion)
        
        # Sort by confidence
        suggestions.sort(key=lambda x: x.confidence, reverse=True)
        
        return suggestions[:3]  # Return top 3 suggestions
    
    def _calculate_endpoint_relevance(self, objective_text: str, endpoint_data: Dict) -> float:
        """Calculate relevance score between objectives and endpoint"""
        
        objective_lower = objective_text.lower()
        endpoint_lower = endpoint_data['text'].lower()
        
        # Keyword matching
        score = 0.0
        
        # Look for endpoint type keywords in objectives
        endpoint_keywords = {
            'survival': ['survival', 'death', 'mortality', 'overall survival', 'progression-free'],
            'response': ['response', 'remission', 'tumor', 'lesion', 'RECIST'],
            'biomarker': ['biomarker', 'blood', 'serum', 'plasma', 'level', 'concentration'],
            'functional': ['function', 'capacity', 'performance', 'ability', 'assessment'],
            'safety': ['safety', 'tolerability', 'adverse', 'toxicity', 'side effect']
        }
        
        endpoint_type = endpoint_data.get('type', '')
        if endpoint_type in endpoint_keywords:
            for keyword in endpoint_keywords[endpoint_type]:
                if keyword in objective_lower:
                    score += 0.2
        
        # Direct keyword overlap
        objective_words = set(objective_lower.split())
        endpoint_words = set(endpoint_lower.split())
        overlap = len(objective_words.intersection(endpoint_words))
        score += overlap * 0.1
        
        # Base relevance for being in the correct therapeutic area
        if score == 0:  # No keyword matches
            score = 0.2  # Give base relevance for TA match
        
        return min(score, 1.0)
    
    def get_ta_blueprint(self, therapeutic_area: str, phase: str) -> Dict[str, str]:
        """Get protocol blueprint/template for specific TA and phase"""
        
        blueprints = {
            'oncology': {
                'I': {
                    'title': 'Phase I, Open-Label, Dose-Escalation Study of [DRUG] in Patients with Advanced Solid Tumors',
                    'primary_objective': 'To determine the maximum tolerated dose (MTD) and/or recommended Phase II dose (RP2D) of [DRUG] in patients with advanced solid tumors',
                    'primary_endpoint': 'Incidence of dose-limiting toxicities (DLTs) during the first cycle of treatment',
                    'key_inclusion': 'Patients ≥18 years with histologically confirmed advanced solid tumors, ECOG PS ≤1, adequate organ function',
                    'key_procedures': 'Safety run-in with 3+3 dose escalation design, DLT assessment period of 28 days, tumor assessments every 8 weeks per RECIST v1.1'
                },
                'II': {
                    'title': 'Phase II, Randomized, Double-Blind, Placebo-Controlled Study of [DRUG] in Patients with [INDICATION]',
                    'primary_objective': 'To evaluate the efficacy of [DRUG] compared to placebo in patients with [INDICATION]',
                    'primary_endpoint': 'Progression-free survival (PFS) as assessed by investigator according to RECIST v1.1',
                    'key_inclusion': 'Patients ≥18 years with histologically confirmed [INDICATION], measurable disease per RECIST v1.1, ECOG PS ≤1',
                    'key_procedures': 'Randomization 2:1 to [DRUG] vs placebo, tumor assessments every 8 weeks, safety assessments per CTCAE v5.0'
                }
            },
            'cardiovascular': {
                'III': {
                    'title': 'Phase III, Randomized, Double-Blind, Placebo-Controlled Cardiovascular Outcomes Trial of [DRUG] in Patients with [INDICATION]',
                    'primary_objective': 'To evaluate the cardiovascular safety and efficacy of [DRUG] compared to placebo in patients with [INDICATION]',
                    'primary_endpoint': 'Time to first occurrence of Major Adverse Cardiovascular Events (MACE): cardiovascular death, non-fatal myocardial infarction, or non-fatal stroke',
                    'key_inclusion': 'Patients ≥18 years with [INDICATION] and high cardiovascular risk, on stable background therapy',
                    'key_procedures': 'Event-driven trial design, Clinical Event Committee adjudication, minimum 2-year follow-up'
                }
            },
            'endocrinology': {
                'III': {
                    'title': 'Phase III, Randomized, Double-Blind, Active-Controlled Study of [DRUG] in Patients with Type 2 Diabetes Mellitus',
                    'primary_objective': 'To evaluate the efficacy and safety of [DRUG] compared to [ACTIVE CONTROL] in patients with type 2 diabetes mellitus',
                    'primary_endpoint': 'Change in HbA1c from baseline to 24 weeks',
                    'key_inclusion': 'Adults ≥18 years with T2DM, HbA1c 7.0-10.5%, on stable metformin therapy',
                    'key_procedures': '1:1 randomization, HbA1c assessments at weeks 12 and 24, continuous glucose monitoring substudy'
                }
            }
        }
        
        return blueprints.get(therapeutic_area, {}).get(phase, {})

def create_ta_retrieval_system() -> TAwareRetrievalSystem:
    """Factory function for TA-aware retrieval system"""
    return TAwareRetrievalSystem()

# Example usage
if __name__ == "__main__":
    # Test the retrieval system
    retrieval = create_ta_retrieval_system()
    
    # Test endpoint suggestions
    print("🎯 Testing Endpoint Suggestions:")
    
    test_objectives = [
        "To evaluate the efficacy of the study drug in patients with metastatic breast cancer",
        "To assess the cardiovascular safety of the drug in patients with diabetes",
        "To determine the effect on glucose control in type 2 diabetes patients"
    ]
    
    for obj in test_objectives:
        print(f"\nObjective: {obj}")
        suggestions = retrieval.suggest_endpoints(obj)
        for i, suggestion in enumerate(suggestions[:2]):
            print(f"  {i+1}. {suggestion.endpoint_text}")
            print(f"     Measurement: {suggestion.measurement_method}")
            print(f"     Confidence: {suggestion.confidence:.2f}")
    
    # Test blueprint generation
    print(f"\n📋 Testing Blueprint Generation:")
    blueprint = retrieval.get_ta_blueprint("oncology", "II")
    if blueprint:
        print(f"Title: {blueprint.get('title', 'N/A')}")
        print(f"Primary Endpoint: {blueprint.get('primary_endpoint', 'N/A')}")