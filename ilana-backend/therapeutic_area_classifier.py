#!/usr/bin/env python3
"""
Therapeutic Area (TA) Classifier for Protocol Intelligence
Detects therapeutic area, disease indication, and study phase from protocol text
"""

import os
import re
import json
import logging
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
import pickle

try:
    from transformers import AutoTokenizer, AutoModel
    import torch
    from sklearn.linear_model import LogisticRegression
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics import classification_report
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("⚠️ Transformers not available, using fallback classification")

logger = logging.getLogger(__name__)

@dataclass
class TADetectionResult:
    """Result of therapeutic area detection"""
    therapeutic_area: str
    subindication: str
    phase: str
    confidence: float
    confidence_scores: Dict[str, float]
    detected_keywords: List[str]
    reasoning: str

class TherapeuticAreaClassifier:
    """
    Therapeutic Area Classifier for Protocol Intelligence
    
    Detects:
    - Primary therapeutic area (oncology, cardiology, etc.)
    - Disease subindication (e.g., "Type 2 Diabetes")
    - Study phase (I, II, III, IV)
    """
    
    # THERAPEUTIC AREA DEFINITIONS (Big Pharma Standard)
    THERAPEUTIC_AREAS = {
        'oncology': {
            'keywords': [
                'cancer', 'tumor', 'tumour', 'carcinoma', 'sarcoma', 'lymphoma', 'leukemia', 'leukaemia',
                'melanoma', 'neoplasm', 'malignancy', 'metastatic', 'chemotherapy', 'radiation therapy',
                'immunotherapy', 'targeted therapy', 'RECIST', 'progression-free survival', 'overall survival',
                'complete response', 'partial response', 'stable disease', 'progressive disease',
                'biomarker', 'companion diagnostic', 'PD-L1', 'HER2', 'EGFR', 'KRAS', 'BRAF'
            ],
            'exclusions': ['oncology nurse', 'radiation protection'],
            'weight': 1.0
        },
        'cardiovascular': {
            'keywords': [
                'cardiovascular', 'cardiac', 'heart', 'coronary', 'myocardial', 'hypertension', 'hyperlipidemia',
                'atherosclerosis', 'heart failure', 'arrhythmia', 'atrial fibrillation', 'stroke', 'MACE',
                'major adverse cardiovascular events', 'ejection fraction', 'blood pressure', 'lipid',
                'cholesterol', 'LDL', 'HDL', 'triglycerides', 'statin', 'ACE inhibitor', 'beta blocker',
                'ECG', 'echocardiogram', 'angiography', 'NYHA class'
            ],
            'exclusions': [],
            'weight': 1.0
        },
        'endocrinology': {
            'keywords': [
                'diabetes', 'diabetic', 'insulin', 'glucose', 'glycemic', 'HbA1c', 'hemoglobin A1c',
                'metformin', 'GLP-1', 'SGLT2', 'thyroid', 'hyperthyroidism', 'hypothyroidism',
                'adrenal', 'cortisol', 'hormone', 'endocrine', 'metabolism', 'obesity',
                'BMI', 'weight loss', 'bariatric', 'lipid metabolism'
            ],
            'exclusions': [],
            'weight': 1.0
        },
        'neurology': {
            'keywords': [
                'neurological', 'neurologic', 'brain', 'CNS', 'central nervous system', 'spinal',
                'Alzheimer', 'dementia', 'Parkinson', 'epilepsy', 'seizure', 'multiple sclerosis',
                'stroke', 'migraine', 'neuropathy', 'ALS', 'amyotrophic lateral sclerosis',
                'cognitive', 'MMSE', 'MoCA', 'neuropsychological', 'EEG', 'MRI brain',
                'cerebrospinal fluid', 'CSF', 'blood-brain barrier'
            ],
            'exclusions': [],
            'weight': 1.0
        },
        'psychiatry': {
            'keywords': [
                'psychiatric', 'depression', 'anxiety', 'schizophrenia', 'bipolar', 'ADHD',
                'attention deficit', 'autism', 'PTSD', 'post-traumatic stress', 'OCD',
                'obsessive compulsive', 'panic disorder', 'social anxiety', 'GAD',
                'generalized anxiety disorder', 'antidepressant', 'antipsychotic', 'mood stabilizer',
                'HAMD', 'Hamilton Depression', 'MADRS', 'GAF', 'PANSS', 'CGI'
            ],
            'exclusions': [],
            'weight': 1.0
        },
        'infectious_diseases': {
            'keywords': [
                'infectious', 'infection', 'antimicrobial', 'antibiotic', 'antiviral', 'antifungal',
                'bacterial', 'viral', 'fungal', 'parasitic', 'HIV', 'hepatitis', 'tuberculosis',
                'pneumonia', 'sepsis', 'urinary tract infection', 'UTI', 'skin infection',
                'respiratory infection', 'bloodstream infection', 'catheter infection',
                'surgical site infection', 'culture', 'sensitivity', 'resistance'
            ],
            'exclusions': [],
            'weight': 1.0
        },
        'respiratory': {
            'keywords': [
                'respiratory', 'pulmonary', 'lung', 'asthma', 'COPD', 'chronic obstructive pulmonary',
                'bronchitis', 'pneumonia', 'pulmonary fibrosis', 'sleep apnea', 'rhinitis',
                'sinusitis', 'cough', 'dyspnea', 'spirometry', 'FEV1', 'FVC', 'peak flow',
                'inhaler', 'bronchodilator', 'corticosteroid', 'oxygen saturation'
            ],
            'exclusions': [],
            'weight': 1.0
        },
        'immunology': {
            'keywords': [
                'immunology', 'immune', 'autoimmune', 'rheumatoid arthritis', 'lupus', 'SLE',
                'inflammatory bowel disease', 'IBD', 'Crohn', 'ulcerative colitis', 'psoriasis',
                'multiple sclerosis', 'immunosuppressive', 'immunomodulator', 'biologics',
                'monoclonal antibody', 'TNF', 'interleukin', 'interferon', 'cytokine'
            ],
            'exclusions': [],
            'weight': 1.0
        },
        'gastroenterology': {
            'keywords': [
                'gastroenterology', 'gastrointestinal', 'GI', 'liver', 'hepatic', 'digestive',
                'stomach', 'intestinal', 'colon', 'rectal', 'pancreatic', 'biliary',
                'inflammatory bowel disease', 'IBD', 'GERD', 'gastroesophageal reflux',
                'peptic ulcer', 'gallbladder', 'cirrhosis', 'hepatitis', 'colonoscopy', 'endoscopy'
            ],
            'exclusions': [],
            'weight': 1.0
        },
        'dermatology': {
            'keywords': [
                'dermatology', 'dermatologic', 'skin', 'cutaneous', 'dermal', 'epidermal',
                'psoriasis', 'eczema', 'atopic dermatitis', 'acne', 'rosacea', 'melanoma',
                'basal cell carcinoma', 'squamous cell carcinoma', 'wound healing',
                'topical', 'dermatological', 'PASI', 'DLQI'
            ],
            'exclusions': [],
            'weight': 1.0
        }
    }
    
    # STUDY PHASE PATTERNS
    PHASE_PATTERNS = {
        'I': [r'phase\s+I\b', r'phase\s+1\b', r'first-in-human', r'dose escalation', r'safety run-in'],
        'II': [r'phase\s+II\b', r'phase\s+2\b', r'proof of concept', r'dose finding'],
        'III': [r'phase\s+III\b', r'phase\s+3\b', r'pivotal', r'confirmatory', r'registration'],
        'IV': [r'phase\s+IV\b', r'phase\s+4\b', r'post-marketing', r'real world evidence', r'observational']
    }
    
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.tfidf_vectorizer = None
        self.classifiers = {}
        self.is_trained = False
        
        # Initialize lightweight model
        self._initialize_fallback_classifier()
        
        logger.info("🎯 Therapeutic Area Classifier initialized")
    
    def _initialize_fallback_classifier(self):
        """Initialize rule-based fallback classifier"""
        
        # Create TF-IDF vectorizer for keyword matching
        all_keywords = []
        for ta_info in self.THERAPEUTIC_AREAS.values():
            all_keywords.extend(ta_info['keywords'])
        
        self.keyword_vocab = set(all_keywords)
        logger.info(f"✅ Fallback classifier ready with {len(self.keyword_vocab)} keywords")
    
    def detect_therapeutic_area(self, protocol_text: str) -> TADetectionResult:
        """
        Detect therapeutic area from protocol text
        
        Args:
            protocol_text: Full protocol text or relevant sections
            
        Returns:
            TADetectionResult with TA, confidence, and reasoning
        """
        
        # Preprocess text
        text_lower = protocol_text.lower()
        
        # Score each therapeutic area
        ta_scores = {}
        detected_keywords = defaultdict(list)
        
        for ta_name, ta_info in self.THERAPEUTIC_AREAS.items():
            score = 0
            
            # Keyword matching with context awareness
            for keyword in ta_info['keywords']:
                # Count occurrences with context weighting
                pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
                matches = len(re.findall(pattern, text_lower))
                
                if matches > 0:
                    detected_keywords[ta_name].append(f"{keyword} ({matches}x)")
                    
                    # Weight by importance and frequency
                    if len(keyword.split()) > 1:  # Multi-word terms are more specific
                        score += matches * 2.0
                    else:
                        score += matches * 1.0
                    
                    # Boost for title/objective mentions
                    if keyword in text_lower[:500]:  # First 500 chars (title/abstract)
                        score += matches * 1.5
            
            # Apply exclusions
            for exclusion in ta_info.get('exclusions', []):
                if exclusion.lower() in text_lower:
                    score *= 0.5  # Penalize but don't eliminate
            
            ta_scores[ta_name] = score * ta_info['weight']
        
        # Determine best match
        if not ta_scores or max(ta_scores.values()) == 0:
            return TADetectionResult(
                therapeutic_area="general_medicine",
                subindication="unspecified",
                phase=self._detect_phase(protocol_text),
                confidence=0.3,
                confidence_scores=ta_scores,
                detected_keywords=[],
                reasoning="No specific therapeutic area keywords detected"
            )
        
        # Get top TA
        top_ta = max(ta_scores.items(), key=lambda x: x[1])
        ta_name, ta_score = top_ta
        
        # Calculate confidence (normalized)
        total_score = sum(ta_scores.values())
        confidence = min(ta_score / max(total_score, 1.0), 1.0)
        
        # Adjust confidence based on keyword diversity
        keyword_diversity = len(detected_keywords[ta_name])
        if keyword_diversity >= 3:
            confidence = min(confidence * 1.2, 1.0)
        elif keyword_diversity == 1:
            confidence *= 0.8
        
        # Detect subindication and phase
        subindication = self._detect_subindication(protocol_text, ta_name)
        phase = self._detect_phase(protocol_text)
        
        # Generate reasoning
        reasoning = f"Detected {keyword_diversity} {ta_name} keywords: {', '.join(detected_keywords[ta_name][:3])}"
        if keyword_diversity > 3:
            reasoning += f" (and {keyword_diversity - 3} more)"
        
        return TADetectionResult(
            therapeutic_area=ta_name,
            subindication=subindication,
            phase=phase,
            confidence=confidence,
            confidence_scores=ta_scores,
            detected_keywords=detected_keywords[ta_name],
            reasoning=reasoning
        )
    
    def _detect_phase(self, text: str) -> str:
        """Detect study phase from protocol text"""
        
        text_lower = text.lower()
        phase_scores = defaultdict(int)
        
        for phase, patterns in self.PHASE_PATTERNS.items():
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower))
                phase_scores[phase] += matches
        
        if not phase_scores:
            return "unspecified"
        
        return max(phase_scores.items(), key=lambda x: x[1])[0]
    
    def _detect_subindication(self, text: str, ta_name: str) -> str:
        """Detect specific disease indication within therapeutic area"""
        
        text_lower = text.lower()
        
        # TA-specific subindication patterns
        subindication_patterns = {
            'oncology': {
                'breast_cancer': ['breast cancer', 'breast carcinoma', 'ductal carcinoma', 'lobular carcinoma'],
                'lung_cancer': ['lung cancer', 'lung carcinoma', 'NSCLC', 'non-small cell lung', 'SCLC', 'small cell lung'],
                'colorectal_cancer': ['colorectal cancer', 'colon cancer', 'rectal cancer', 'CRC'],
                'prostate_cancer': ['prostate cancer', 'prostate carcinoma', 'castration resistant'],
                'melanoma': ['melanoma', 'metastatic melanoma'],
                'lymphoma': ['lymphoma', 'hodgkin', 'non-hodgkin', 'NHL', 'DLBCL'],
                'leukemia': ['leukemia', 'leukaemia', 'AML', 'CML', 'ALL', 'CLL']
            },
            'cardiovascular': {
                'hypertension': ['hypertension', 'high blood pressure', 'elevated blood pressure'],
                'heart_failure': ['heart failure', 'HF', 'congestive heart failure', 'CHF'],
                'coronary_artery_disease': ['coronary artery disease', 'CAD', 'coronary heart disease'],
                'atrial_fibrillation': ['atrial fibrillation', 'AF', 'AFib'],
                'hyperlipidemia': ['hyperlipidemia', 'hypercholesterolemia', 'dyslipidemia']
            },
            'endocrinology': {
                'type_2_diabetes': ['type 2 diabetes', 't2dm', 'diabetes mellitus type 2'],
                'type_1_diabetes': ['type 1 diabetes', 't1dm', 'diabetes mellitus type 1'],
                'obesity': ['obesity', 'overweight', 'weight management'],
                'hypothyroidism': ['hypothyroidism', 'underactive thyroid'],
                'hyperthyroidism': ['hyperthyroidism', 'overactive thyroid']
            },
            'neurology': {
                'alzheimer_disease': ['alzheimer', 'alzheimer disease', 'alzheimer\'s disease', 'AD'],
                'parkinson_disease': ['parkinson', 'parkinson disease', 'parkinson\'s disease', 'PD'],
                'multiple_sclerosis': ['multiple sclerosis', 'MS', 'relapsing remitting'],
                'epilepsy': ['epilepsy', 'seizure disorder', 'epileptic seizures'],
                'migraine': ['migraine', 'chronic migraine', 'episodic migraine']
            },
            'psychiatry': {
                'major_depression': ['major depression', 'major depressive disorder', 'MDD'],
                'generalized_anxiety': ['generalized anxiety disorder', 'GAD'],
                'schizophrenia': ['schizophrenia', 'schizoaffective'],
                'bipolar_disorder': ['bipolar disorder', 'bipolar I', 'bipolar II'],
                'ADHD': ['ADHD', 'attention deficit hyperactivity disorder']
            }
        }
        
        if ta_name not in subindication_patterns:
            return "unspecified"
        
        # Score subindications
        subind_scores = {}
        for subind, patterns in subindication_patterns[ta_name].items():
            score = 0
            for pattern in patterns:
                score += len(re.findall(r'\b' + re.escape(pattern) + r'\b', text_lower))
            subind_scores[subind] = score
        
        if not subind_scores or max(subind_scores.values()) == 0:
            return "unspecified"
        
        return max(subind_scores.items(), key=lambda x: x[1])[0]
    
    def get_ta_summary(self) -> Dict[str, int]:
        """Get summary of available therapeutic areas"""
        return {ta: len(info['keywords']) for ta, info in self.THERAPEUTIC_AREAS.items()}

def create_ta_classifier() -> TherapeuticAreaClassifier:
    """Factory function for TA classifier"""
    return TherapeuticAreaClassifier()

# Example usage and testing
if __name__ == "__main__":
    # Test the classifier
    classifier = create_ta_classifier()
    
    # Test protocols
    test_protocols = [
        {
            "text": "Phase II study of pembrolizumab in patients with metastatic breast cancer. Primary endpoint is progression-free survival measured by RECIST v1.1.",
            "expected_ta": "oncology"
        },
        {
            "text": "Phase III randomized trial of ACE inhibitor therapy in patients with heart failure and reduced ejection fraction. Primary endpoint is cardiovascular death.",
            "expected_ta": "cardiovascular"
        },
        {
            "text": "Phase II study of metformin in patients with type 2 diabetes mellitus. Primary endpoint is change in HbA1c from baseline.",
            "expected_ta": "endocrinology"
        }
    ]
    
    print("🧪 Testing TA Classifier:")
    for i, test in enumerate(test_protocols):
        result = classifier.detect_therapeutic_area(test["text"])
        print(f"\nTest {i+1}:")
        print(f"Expected: {test['expected_ta']}")
        print(f"Detected: {result.therapeutic_area} (confidence: {result.confidence:.2f})")
        print(f"Phase: {result.phase}")
        print(f"Subindication: {result.subindication}")
        print(f"Reasoning: {result.reasoning}")
        
    print(f"\n📊 TA Summary: {classifier.get_ta_summary()}")