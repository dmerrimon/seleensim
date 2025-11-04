#!/usr/bin/env python3
"""
Optimization Rule Engine for Protocol Procedure Consolidation and Visit Schedule Optimization
Non-destructive, auditable, TA-aware suggestions for protocol improvement
"""

import os
import re
import json
import logging
import hashlib
import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass, asdict
from collections import defaultdict
from itertools import combinations
import difflib

try:
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.feature_extraction.text import TfidfVectorizer
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("⚠️ scikit-learn not available, using fallback similarity")

from therapeutic_area_classifier import TherapeuticAreaClassifier, TADetectionResult
from ta_aware_retrieval import TAwareRetrievalSystem

logger = logging.getLogger(__name__)

@dataclass
class OptimizationSuggestion:
    """Optimization suggestion schema"""
    suggestion_id: str
    type: str  # procedure_consolidation, visit_simplification, endpoint_alignment, frequency_rationalization, sample_consolidation
    section_id: str
    location: Dict[str, Any]  # visit_ids, char_offsets, etc.
    suggested_text: str
    rationale: str
    sources: List[Dict[str, str]]  # exemplar citations
    confidence: float
    impact_estimate: Dict[str, Any]
    original_procedures: List[str] = None
    severity: str = "minor"  # critical, major, minor

@dataclass
class ProcedureInstance:
    """Individual procedure instance"""
    text: str
    normalized_text: str
    visit_id: str
    visit_name: str
    section: str
    char_offset: int = 0

@dataclass
class VisitSchedule:
    """Visit schedule representation"""
    visit_id: str
    visit_name: str
    timepoint: str
    procedures: List[ProcedureInstance]
    window: str = ""

@dataclass
class ParsedDocument:
    """Parsed protocol document structure"""
    doc_id: str
    visit_schedule: List[VisitSchedule]
    endpoints: List[Dict[str, str]]
    sections: Dict[str, str]
    ta_detection: TADetectionResult = None

class OptimizationRuleEngine:
    """
    Optimization Rule Engine for Protocol Enhancement
    
    Provides:
    - Procedure consolidation (exact and semantic duplicates)
    - Visit schedule simplification
    - Endpoint-to-assessment alignment
    - Assessment frequency rationalization
    - Sample collection optimization
    """
    
    def __init__(self):
        self.ta_classifier = TherapeuticAreaClassifier()
        self.ta_retrieval = TAwareRetrievalSystem()
        self.vectorizer = None
        self.suggestion_counter = 0
        
        # Initialize text processing
        if SKLEARN_AVAILABLE:
            self.vectorizer = TfidfVectorizer(
                stop_words='english',
                ngram_range=(1, 3),
                max_features=1000
            )
        
        # TA-specific frequency thresholds (procedures per timeframe)
        self.frequency_thresholds = {
            'oncology': {
                'vitals': {'max_per_week': 2, 'rationale': 'Oncology vitals typically q2-3 days for safety monitoring'},
                'labs_safety': {'max_per_week': 3, 'rationale': 'Safety labs q2-3 days in Phase I, weekly in Phase II'},
                'labs_efficacy': {'max_per_week': 1, 'rationale': 'Efficacy biomarkers weekly or biweekly'},
                'imaging': {'max_per_month': 1, 'rationale': 'RECIST imaging q8-12 weeks standard'},
                'ecg': {'max_per_week': 1, 'rationale': 'ECG weekly adequate unless cardiotoxicity concern'}
            },
            'cardiovascular': {
                'vitals': {'max_per_week': 3, 'rationale': 'CV trials require frequent BP monitoring'},
                'ecg': {'max_per_week': 2, 'rationale': 'ECG monitoring critical for CV safety'},
                'labs': {'max_per_week': 1, 'rationale': 'Lipid panels and biomarkers weekly sufficient'},
                'echo': {'max_per_month': 1, 'rationale': 'Echocardiograms monthly for EF monitoring'}
            },
            'endocrinology': {
                'glucose': {'max_per_week': 3, 'rationale': 'Glucose monitoring 2-3x weekly in diabetes trials'},
                'hba1c': {'max_per_month': 1, 'rationale': 'HbA1c reflects 2-3 month average, monthly adequate'},
                'vitals': {'max_per_week': 1, 'rationale': 'Weight/vitals weekly for weight management studies'}
            }
        }
        
        logger.info("🔧 Optimization Rule Engine initialized")
    
    def optimize_document(self, parsed_doc: ParsedDocument, mode: str = "full") -> List[OptimizationSuggestion]:
        """
        Main optimization entry point
        
        Args:
            parsed_doc: Parsed protocol document
            mode: "quick" (deterministic only), "full" (with semantic analysis)
            
        Returns:
            List of optimization suggestions ranked by impact
        """
        
        logger.info(f"🚀 Starting optimization analysis in {mode} mode")
        suggestions = []
        
        # 1. EXACT DUPLICATE PROCEDURES
        suggestions.extend(self._detect_exact_duplicates(parsed_doc))
        
        # 2. WITHIN-VISIT PROCEDURE MERGING
        suggestions.extend(self._detect_within_visit_redundancy(parsed_doc))
        
        # 3. VISIT WINDOW SIMPLIFICATION
        suggestions.extend(self._suggest_visit_simplification(parsed_doc))
        
        # 4. ENDPOINT-TO-ASSESSMENT ALIGNMENT
        suggestions.extend(self._check_endpoint_assessment_alignment(parsed_doc))
        
        # 5. ASSESSMENT FREQUENCY RATIONALIZATION
        suggestions.extend(self._rationalize_assessment_frequency(parsed_doc))
        
        if mode == "full":
            # 6. SEMANTIC DUPLICATE DETECTION (slower)
            suggestions.extend(self._detect_semantic_duplicates(parsed_doc))
            
            # 7. SAMPLE COLLECTION OPTIMIZATION
            suggestions.extend(self._optimize_sample_collection(parsed_doc))
        
        # Rank by impact and return
        ranked_suggestions = self._rank_suggestions(suggestions, parsed_doc)
        
        logger.info(f"⚡ Generated {len(ranked_suggestions)} optimization suggestions")
        return ranked_suggestions
    
    def _detect_exact_duplicates(self, parsed_doc: ParsedDocument) -> List[OptimizationSuggestion]:
        """Detect exact procedure duplicates across visits"""
        
        suggestions = []
        procedure_map = defaultdict(list)
        
        # Build procedure inventory
        for visit in parsed_doc.visit_schedule:
            for proc in visit.procedures:
                normalized = self._normalize_procedure_text(proc.text)
                procedure_map[normalized].append((visit, proc))
        
        # Find duplicates
        for normalized_text, occurrences in procedure_map.items():
            if len(occurrences) >= 2:
                # Group by visits
                visits = [occ[0] for occ in occurrences]
                procedures = [occ[1] for occ in occurrences]
                
                # Get TA-specific exemplar for consolidation
                exemplar = self._get_consolidation_exemplar(normalized_text, parsed_doc.ta_detection)
                
                suggestion = OptimizationSuggestion(
                    suggestion_id=self._generate_id("dup"),
                    type="procedure_consolidation",
                    section_id="visit_schedule",
                    location={
                        "visit_ids": [v.visit_id for v in visits],
                        "visit_names": [v.visit_name for v in visits]
                    },
                    suggested_text=f"Consolidate '{procedures[0].text}' across {len(visits)} visits into standardized language: '{exemplar}'",
                    rationale=f"Identical procedure repeated across visits {[v.visit_name for v in visits]}. Consolidation reduces redundancy while maintaining clarity. Common practice in {parsed_doc.ta_detection.therapeutic_area if parsed_doc.ta_detection else 'clinical'} protocols.",
                    sources=self._get_consolidation_sources(normalized_text, parsed_doc.ta_detection),
                    confidence=0.95,  # High confidence for exact duplicates
                    impact_estimate={
                        "issues_reduced": len(visits) - 1,
                        "amendment_risk_reduction": 0.1 * len(visits),
                        "clarity_improvement": "high"
                    },
                    original_procedures=[proc.text for proc in procedures],
                    severity="minor"
                )
                
                suggestions.append(suggestion)
        
        return suggestions
    
    def _detect_within_visit_redundancy(self, parsed_doc: ParsedDocument) -> List[OptimizationSuggestion]:
        """Detect redundant procedures within the same visit"""
        
        suggestions = []
        
        for visit in parsed_doc.visit_schedule:
            if len(visit.procedures) < 2:
                continue
                
            # Check for token overlap between procedures in same visit
            for i, proc1 in enumerate(visit.procedures):
                for j, proc2 in enumerate(visit.procedures[i+1:], i+1):
                    overlap = self._calculate_token_overlap(proc1.text, proc2.text)
                    
                    if overlap > 0.7:  # 70% token overlap threshold
                        merged_text = self._suggest_procedure_merge(proc1.text, proc2.text)
                        
                        suggestion = OptimizationSuggestion(
                            suggestion_id=self._generate_id("merge"),
                            type="procedure_consolidation",
                            section_id="visit_schedule",
                            location={
                                "visit_id": visit.visit_id,
                                "visit_name": visit.visit_name,
                                "procedure_indices": [i, j]
                            },
                            suggested_text=f"Merge overlapping procedures in {visit.visit_name}: '{merged_text}'",
                            rationale=f"Procedures '{proc1.text}' and '{proc2.text}' have {overlap:.0%} overlap. Merging reduces redundancy and improves readability.",
                            sources=[{"type": "algorithmic", "method": "token_overlap_analysis"}],
                            confidence=0.85,
                            impact_estimate={
                                "issues_reduced": 1,
                                "clarity_improvement": "medium"
                            },
                            original_procedures=[proc1.text, proc2.text],
                            severity="minor"
                        )
                        
                        suggestions.append(suggestion)
        
        return suggestions
    
    def _suggest_visit_simplification(self, parsed_doc: ParsedDocument) -> List[OptimizationSuggestion]:
        """Suggest visit window and frequency simplifications"""
        
        suggestions = []
        
        # Check for adjacent visits with minimal differences
        for i, visit in enumerate(parsed_doc.visit_schedule[:-1]):
            next_visit = parsed_doc.visit_schedule[i + 1]
            
            # Check if visits are very close in time with similar procedures
            if self._are_visits_mergeable(visit, next_visit):
                suggestion = OptimizationSuggestion(
                    suggestion_id=self._generate_id("visit"),
                    type="visit_simplification",
                    section_id="visit_schedule",
                    location={
                        "visit_ids": [visit.visit_id, next_visit.visit_id],
                        "visit_names": [visit.visit_name, next_visit.visit_name]
                    },
                    suggested_text=f"Consider merging {visit.visit_name} and {next_visit.visit_name} into single visit with combined procedures",
                    rationale=f"Visits are temporally close with similar procedures. Merging reduces participant burden while maintaining data quality.",
                    sources=self._get_visit_merge_sources(parsed_doc.ta_detection),
                    confidence=0.75,
                    impact_estimate={
                        "visit_reduction": 1,
                        "participant_burden_reduction": "medium",
                        "cost_reduction": "low"
                    },
                    severity="minor"
                )
                
                suggestions.append(suggestion)
        
        return suggestions
    
    def _check_endpoint_assessment_alignment(self, parsed_doc: ParsedDocument) -> List[OptimizationSuggestion]:
        """Check if endpoints have corresponding assessments in visit schedule"""
        
        suggestions = []
        
        for endpoint in parsed_doc.endpoints:
            endpoint_text = endpoint.get('text', '')
            endpoint_type = endpoint.get('type', 'unknown')
            
            # Check if endpoint has matching assessment in visit schedule
            has_matching_assessment = self._has_matching_assessment(endpoint_text, parsed_doc.visit_schedule)
            
            if not has_matching_assessment:
                # Suggest assessment schedule based on TA and endpoint type
                suggested_schedule = self._suggest_assessment_schedule(
                    endpoint_text, 
                    endpoint_type,
                    parsed_doc.ta_detection
                )
                
                suggestion = OptimizationSuggestion(
                    suggestion_id=self._generate_id("endpoint"),
                    type="endpoint_alignment",
                    section_id="endpoints",
                    location={
                        "endpoint_text": endpoint_text,
                        "endpoint_type": endpoint_type
                    },
                    suggested_text=f"Add assessment schedule for '{endpoint_text}': {suggested_schedule}",
                    rationale=f"Primary endpoint requires explicit measurement schedule for regulatory compliance and data integrity.",
                    sources=self._get_endpoint_sources(endpoint_text, parsed_doc.ta_detection),
                    confidence=0.90,
                    impact_estimate={
                        "compliance_improvement": "high",
                        "audit_risk_reduction": 0.3
                    },
                    severity="major"
                )
                
                suggestions.append(suggestion)
        
        return suggestions
    
    def _rationalize_assessment_frequency(self, parsed_doc: ParsedDocument) -> List[OptimizationSuggestion]:
        """Check for overly frequent assessments and suggest optimization"""
        
        suggestions = []
        
        if not parsed_doc.ta_detection:
            return suggestions
        
        ta = parsed_doc.ta_detection.therapeutic_area
        thresholds = self.frequency_thresholds.get(ta, {})
        
        # Analyze frequency of each procedure type
        procedure_frequencies = self._analyze_procedure_frequencies(parsed_doc.visit_schedule)
        
        for proc_type, frequency_data in procedure_frequencies.items():
            if proc_type in thresholds:
                threshold = thresholds[proc_type]
                
                if frequency_data['per_week'] > threshold.get('max_per_week', 10):
                    suggestion = OptimizationSuggestion(
                        suggestion_id=self._generate_id("freq"),
                        type="frequency_rationalization",
                        section_id="visit_schedule",
                        location={
                            "procedure_type": proc_type,
                            "visits": frequency_data['visits']
                        },
                        suggested_text=f"Reduce {proc_type} frequency from {frequency_data['per_week']:.1f}/week to {threshold['max_per_week']}/week",
                        rationale=f"{threshold['rationale']}. Current frequency ({frequency_data['per_week']:.1f}/week) exceeds {ta} standard ({threshold['max_per_week']}/week).",
                        sources=[{
                            "type": "ta_standard",
                            "therapeutic_area": ta,
                            "citation": f"{ta.title()} frequency guidelines"
                        }],
                        confidence=0.80,
                        impact_estimate={
                            "participant_burden_reduction": "medium",
                            "cost_reduction": "medium",
                            "frequency_optimization": frequency_data['per_week'] - threshold['max_per_week']
                        },
                        severity="minor"
                    )
                    
                    suggestions.append(suggestion)
        
        return suggestions
    
    def _detect_semantic_duplicates(self, parsed_doc: ParsedDocument) -> List[OptimizationSuggestion]:
        """Detect semantically similar procedures using embeddings/similarity"""
        
        suggestions = []
        
        if not SKLEARN_AVAILABLE:
            logger.warning("Semantic duplicate detection requires scikit-learn")
            return suggestions
        
        # Collect all unique procedures
        all_procedures = []
        for visit in parsed_doc.visit_schedule:
            all_procedures.extend(visit.procedures)
        
        if len(all_procedures) < 2:
            return suggestions
        
        # Vectorize procedure texts
        try:
            texts = [proc.text for proc in all_procedures]
            vectors = self.vectorizer.fit_transform(texts)
            similarity_matrix = cosine_similarity(vectors)
            
            # Find high-similarity pairs
            for i in range(len(all_procedures)):
                for j in range(i + 1, len(all_procedures)):
                    similarity = similarity_matrix[i][j]
                    
                    if similarity > 0.88:  # High semantic similarity threshold
                        proc1, proc2 = all_procedures[i], all_procedures[j]
                        
                        # Don't suggest if already exact duplicates
                        if proc1.normalized_text == proc2.normalized_text:
                            continue
                        
                        merged_text = self._suggest_semantic_merge(proc1.text, proc2.text)
                        
                        suggestion = OptimizationSuggestion(
                            suggestion_id=self._generate_id("semantic"),
                            type="procedure_consolidation",
                            section_id="visit_schedule",
                            location={
                                "procedure_texts": [proc1.text, proc2.text],
                                "visits": [proc1.visit_id, proc2.visit_id]
                            },
                            suggested_text=f"Consider consolidating semantically similar procedures: '{merged_text}'",
                            rationale=f"Procedures are {similarity:.0%} semantically similar. Consolidation may reduce confusion and improve protocol clarity.",
                            sources=[{
                                "type": "semantic_analysis",
                                "method": "cosine_similarity",
                                "similarity_score": similarity
                            }],
                            confidence=0.70,  # Lower confidence for semantic matches
                            impact_estimate={
                                "clarity_improvement": "medium",
                                "issues_reduced": 1
                            },
                            original_procedures=[proc1.text, proc2.text],
                            severity="minor"
                        )
                        
                        suggestions.append(suggestion)
        
        except Exception as e:
            logger.warning(f"Semantic analysis failed: {e}")
        
        return suggestions
    
    def _optimize_sample_collection(self, parsed_doc: ParsedDocument) -> List[OptimizationSuggestion]:
        """Optimize blood draws and sample collection procedures"""
        
        suggestions = []
        
        for visit in parsed_doc.visit_schedule:
            blood_draws = [proc for proc in visit.procedures if self._is_blood_draw(proc.text)]
            
            if len(blood_draws) > 1:
                # Suggest consolidating multiple blood draws
                total_volume = self._estimate_blood_volume(blood_draws)
                
                suggestion = OptimizationSuggestion(
                    suggestion_id=self._generate_id("sample"),
                    type="sample_consolidation",
                    section_id="visit_schedule",
                    location={
                        "visit_id": visit.visit_id,
                        "visit_name": visit.visit_name,
                        "blood_draws": len(blood_draws)
                    },
                    suggested_text=f"Consolidate {len(blood_draws)} blood draws in {visit.visit_name} into single draw with aliquot splitting",
                    rationale=f"Multiple blood draws can be consolidated to reduce participant burden. Estimated total volume: {total_volume}mL.",
                    sources=[{
                        "type": "best_practice",
                        "citation": "ICH E6 participant burden minimization"
                    }],
                    confidence=0.85,
                    impact_estimate={
                        "participant_burden_reduction": "high",
                        "needle_sticks_reduced": len(blood_draws) - 1
                    },
                    severity="minor"
                )
                
                suggestions.append(suggestion)
        
        return suggestions
    
    # HELPER METHODS
    
    def _normalize_procedure_text(self, text: str) -> str:
        """Normalize procedure text for comparison"""
        # Convert to lowercase, remove extra spaces, basic stemming
        normalized = re.sub(r'\s+', ' ', text.lower().strip())
        normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove punctuation
        return normalized
    
    def _calculate_token_overlap(self, text1: str, text2: str) -> float:
        """Calculate token overlap between two texts"""
        tokens1 = set(text1.lower().split())
        tokens2 = set(text2.lower().split())
        
        if not tokens1 or not tokens2:
            return 0.0
        
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        
        return len(intersection) / len(union)
    
    def _suggest_procedure_merge(self, text1: str, text2: str) -> str:
        """Suggest merged text for overlapping procedures"""
        # Simple merge strategy - take unique tokens
        tokens1 = text1.split()
        tokens2 = text2.split()
        
        # Use the longer text as base and add unique tokens from shorter
        if len(tokens1) >= len(tokens2):
            base, additional = tokens1, tokens2
        else:
            base, additional = tokens2, tokens1
        
        unique_tokens = []
        for token in additional:
            if token.lower() not in [t.lower() for t in base]:
                unique_tokens.append(token)
        
        if unique_tokens:
            return ' '.join(base + ['&'] + unique_tokens)
        else:
            return ' '.join(base)
    
    def _are_visits_mergeable(self, visit1: VisitSchedule, visit2: VisitSchedule) -> bool:
        """Check if two visits could be merged"""
        # Simple heuristic: similar procedure counts and types
        if abs(len(visit1.procedures) - len(visit2.procedures)) > 2:
            return False
        
        # Check for similar procedure types
        types1 = set([self._get_procedure_type(p.text) for p in visit1.procedures])
        types2 = set([self._get_procedure_type(p.text) for p in visit2.procedures])
        
        overlap = len(types1.intersection(types2)) / max(len(types1.union(types2)), 1)
        return overlap > 0.6
    
    def _get_procedure_type(self, text: str) -> str:
        """Classify procedure into type"""
        text_lower = text.lower()
        
        if any(term in text_lower for term in ['vital', 'bp', 'blood pressure', 'heart rate', 'temperature']):
            return 'vitals'
        elif any(term in text_lower for term in ['lab', 'blood', 'chemistry', 'hematology', 'cbc']):
            return 'labs'
        elif any(term in text_lower for term in ['ecg', 'ekg', 'electrocardiogram']):
            return 'ecg'
        elif any(term in text_lower for term in ['imaging', 'ct', 'mri', 'x-ray', 'scan']):
            return 'imaging'
        elif any(term in text_lower for term in ['echo', 'echocardiogram', 'ultrasound']):
            return 'echo'
        else:
            return 'other'
    
    def _has_matching_assessment(self, endpoint_text: str, visit_schedule: List[VisitSchedule]) -> bool:
        """Check if endpoint has matching assessment in visit schedule"""
        endpoint_lower = endpoint_text.lower()
        
        # Extract key terms from endpoint
        key_terms = self._extract_endpoint_terms(endpoint_lower)
        
        # Check if any procedure matches these terms
        for visit in visit_schedule:
            for proc in visit.procedures:
                if any(term in proc.text.lower() for term in key_terms):
                    return True
        
        return False
    
    def _extract_endpoint_terms(self, endpoint_text: str) -> List[str]:
        """Extract key measurement terms from endpoint text"""
        terms = []
        
        # Common endpoint measurement terms
        measurement_patterns = {
            'hba1c': ['hba1c', 'hemoglobin a1c', 'glycated hemoglobin'],
            'blood_pressure': ['blood pressure', 'bp', 'systolic', 'diastolic'],
            'survival': ['survival', 'death', 'mortality'],
            'response': ['response', 'recist', 'tumor', 'lesion'],
            'function': ['function', 'ejection fraction', 'lvef'],
            'lab': ['lab', 'laboratory', 'biomarker']
        }
        
        for category, patterns in measurement_patterns.items():
            if any(pattern in endpoint_text for pattern in patterns):
                terms.extend(patterns)
        
        return terms
    
    def _suggest_assessment_schedule(self, endpoint_text: str, endpoint_type: str, ta_detection: TADetectionResult) -> str:
        """Suggest appropriate assessment schedule for endpoint"""
        
        # TA-specific scheduling recommendations
        if ta_detection:
            ta = ta_detection.therapeutic_area
            
            if ta == 'oncology':
                if 'survival' in endpoint_text.lower():
                    return "Survival status every 12 weeks until death or study closure"
                elif 'response' in endpoint_text.lower() or 'recist' in endpoint_text.lower():
                    return "Imaging assessments every 8 weeks per RECIST v1.1"
                elif 'biomarker' in endpoint_text.lower():
                    return "Laboratory assessments at baseline, cycle 1 day 15, then every 2 cycles"
            
            elif ta == 'cardiovascular':
                if 'mace' in endpoint_text.lower():
                    return "Clinical assessments monthly with event adjudication"
                elif 'blood pressure' in endpoint_text.lower():
                    return "BP measurements at baseline, weeks 2, 4, 8, 12"
                elif 'ejection fraction' in endpoint_text.lower():
                    return "Echocardiogram at baseline, 6 weeks, 12 weeks"
            
            elif ta == 'endocrinology':
                if 'hba1c' in endpoint_text.lower():
                    return "HbA1c at baseline, week 12, week 24"
                elif 'weight' in endpoint_text.lower():
                    return "Weight measurement weekly for first 12 weeks, then monthly"
        
        # Default schedule
        return "Baseline and week 12 assessments (adjust based on endpoint sensitivity)"
    
    def _analyze_procedure_frequencies(self, visit_schedule: List[VisitSchedule]) -> Dict[str, Dict]:
        """Analyze frequency of each procedure type across visits"""
        
        procedure_counts = defaultdict(list)
        
        for visit in visit_schedule:
            for proc in visit.procedures:
                proc_type = self._get_procedure_type(proc.text)
                procedure_counts[proc_type].append(visit.visit_name)
        
        # Calculate per-week frequencies (assuming study duration)
        frequencies = {}
        for proc_type, visits in procedure_counts.items():
            # Simple heuristic: assume 24-week study for frequency calculation
            study_weeks = 24
            frequencies[proc_type] = {
                'total_count': len(visits),
                'per_week': len(visits) / study_weeks,
                'visits': visits
            }
        
        return frequencies
    
    def _is_blood_draw(self, text: str) -> bool:
        """Check if procedure is a blood draw"""
        blood_terms = ['blood', 'plasma', 'serum', 'laboratory', 'lab draw', 'venipuncture']
        return any(term in text.lower() for term in blood_terms)
    
    def _estimate_blood_volume(self, blood_draws: List[ProcedureInstance]) -> float:
        """Estimate total blood volume for multiple draws"""
        # Simple heuristic: 5-10mL per draw
        return len(blood_draws) * 7.5
    
    def _get_consolidation_exemplar(self, procedure_text: str, ta_detection: TADetectionResult) -> str:
        """Get TA-specific exemplar for procedure consolidation"""
        
        if ta_detection:
            # TA-specific exemplar language
            if ta_detection.therapeutic_area == 'oncology':
                if 'vital' in procedure_text:
                    return "Vital signs (BP, HR, temp, weight) at each visit"
                elif 'lab' in procedure_text:
                    return "Safety laboratories (CBC, CMP, LFTs) per schedule"
            
            elif ta_detection.therapeutic_area == 'cardiovascular':
                if 'vital' in procedure_text:
                    return "Vital signs including orthostatic measurements"
                elif 'ecg' in procedure_text:
                    return "12-lead ECG in triplicate"
        
        # Generic exemplar
        return f"Standardized {procedure_text} per protocol schedule"
    
    def _get_consolidation_sources(self, procedure_text: str, ta_detection: TADetectionResult) -> List[Dict[str, str]]:
        """Get source citations for consolidation suggestions"""
        
        sources = [{
            "type": "best_practice",
            "citation": "ICH E6 GCP Guidelines - Protocol clarity and standardization"
        }]
        
        if ta_detection:
            sources.append({
                "type": "ta_standard",
                "therapeutic_area": ta_detection.therapeutic_area,
                "citation": f"{ta_detection.therapeutic_area.title()} clinical trial standards"
            })
        
        return sources
    
    def _get_visit_merge_sources(self, ta_detection: TADetectionResult) -> List[Dict[str, str]]:
        """Get sources for visit merging suggestions"""
        return [{
            "type": "efficiency",
            "citation": "FDA Guidance on Reducing Participant Burden in Clinical Trials"
        }]
    
    def _get_endpoint_sources(self, endpoint_text: str, ta_detection: TADetectionResult) -> List[Dict[str, str]]:
        """Get regulatory sources for endpoint recommendations"""
        
        sources = [{
            "type": "regulatory",
            "citation": "ICH E9 Statistical Principles - Endpoint specification"
        }]
        
        if ta_detection:
            if ta_detection.therapeutic_area == 'oncology':
                sources.append({
                    "type": "guidance",
                    "citation": "FDA Guidance on Clinical Trial Endpoints for Cancer Drug Approval"
                })
            elif ta_detection.therapeutic_area == 'cardiovascular':
                sources.append({
                    "type": "guidance", 
                    "citation": "FDA Guidance on Cardiovascular Outcome Trials"
                })
        
        return sources
    
    def _suggest_semantic_merge(self, text1: str, text2: str) -> str:
        """Suggest merged text for semantically similar procedures"""
        # Use difflib to find common subsequences
        common = difflib.SequenceMatcher(None, text1.split(), text2.split()).get_longest_common_subsequence()
        
        if common:
            return ' '.join(common) + " (combined assessment)"
        else:
            return f"{text1} / {text2} (combined)"
    
    def _rank_suggestions(self, suggestions: List[OptimizationSuggestion], parsed_doc: ParsedDocument) -> List[OptimizationSuggestion]:
        """Rank suggestions by impact score"""
        
        for suggestion in suggestions:
            # Calculate impact score
            impact_score = self._calculate_impact_score(suggestion, parsed_doc)
            suggestion.impact_estimate['total_score'] = impact_score
        
        # Sort by impact score descending
        return sorted(suggestions, key=lambda x: x.impact_estimate.get('total_score', 0), reverse=True)
    
    def _calculate_impact_score(self, suggestion: OptimizationSuggestion, parsed_doc: ParsedDocument) -> float:
        """Calculate overall impact score for suggestion"""
        
        score = 0.0
        
        # Base score by type
        type_weights = {
            'endpoint_alignment': 1.0,  # Highest priority
            'procedure_consolidation': 0.8,
            'frequency_rationalization': 0.7,
            'visit_simplification': 0.6,
            'sample_consolidation': 0.5
        }
        
        score += type_weights.get(suggestion.type, 0.3)
        
        # Confidence weight
        score *= suggestion.confidence
        
        # Severity weight
        severity_weights = {'critical': 1.5, 'major': 1.2, 'minor': 1.0}
        score *= severity_weights.get(suggestion.severity, 1.0)
        
        # TA relevance boost
        if parsed_doc.ta_detection and suggestion.confidence > 0.8:
            score *= 1.1
        
        return score
    
    def _generate_id(self, prefix: str) -> str:
        """Generate unique suggestion ID"""
        self.suggestion_counter += 1
        return f"{prefix}_{self.suggestion_counter:04d}"

def create_optimization_engine() -> OptimizationRuleEngine:
    """Factory function for optimization rule engine"""
    return OptimizationRuleEngine()

# Example usage and testing
if __name__ == "__main__":
    # Test the optimization engine
    engine = create_optimization_engine()
    
    # Mock parsed document for testing
    test_procedures = [
        ProcedureInstance("Vital signs", "vital signs", "V1", "Visit 1", "schedule"),
        ProcedureInstance("Vitals", "vitals", "V2", "Visit 2", "schedule"),
        ProcedureInstance("Blood pressure and heart rate", "blood pressure and heart rate", "V3", "Visit 3", "schedule"),
        ProcedureInstance("Laboratory safety tests", "laboratory safety tests", "V1", "Visit 1", "schedule"),
        ProcedureInstance("Lab safety", "lab safety", "V2", "Visit 2", "schedule"),
    ]
    
    test_visits = [
        VisitSchedule("V1", "Visit 1", "Baseline", test_procedures[:2]),
        VisitSchedule("V2", "Visit 2", "Week 4", test_procedures[2:4]),
        VisitSchedule("V3", "Visit 3", "Week 8", test_procedures[4:])
    ]
    
    test_endpoints = [
        {"text": "Change in HbA1c from baseline", "type": "primary"},
        {"text": "Safety and tolerability", "type": "secondary"}
    ]
    
    test_doc = ParsedDocument(
        doc_id="test_001",
        visit_schedule=test_visits,
        endpoints=test_endpoints,
        sections={"objectives": "Test protocol"},
        ta_detection=None
    )
    
    print("🧪 Testing Optimization Rule Engine:")
    suggestions = engine.optimize_document(test_doc, mode="quick")
    
    print(f"✅ Generated {len(suggestions)} suggestions:")
    for i, suggestion in enumerate(suggestions[:3]):
        print(f"\n{i+1}. {suggestion.type.replace('_', ' ').title()}")
        print(f"   Suggestion: {suggestion.suggested_text}")
        print(f"   Rationale: {suggestion.rationale}")
        print(f"   Confidence: {suggestion.confidence:.0%}")
        print(f"   Impact Score: {suggestion.impact_estimate.get('total_score', 0):.2f}")