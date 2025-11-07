#!/usr/bin/env python3
"""
Guaranteed suggestions for specific drug monitoring requirements
Provides deterministic medical recommendations for high-risk therapies
"""

import re
from typing import List, Dict, Any


def guaranteed_suggestions(text: str) -> List[Dict[str, str]]:
    """
    Generate guaranteed medical monitoring suggestions for specific therapies
    
    Args:
        text: Protocol text to analyze
        
    Returns:
        List of suggestion dictionaries with original, improved, reason keys
    """
    if not text:
        return []
    
    text_lower = text.lower()
    suggestions = []
    
    # HER2-targeted therapy monitoring
    her2_keywords = ["trastuzumab", "herceptin", "her2"]
    if any(keyword in text_lower for keyword in her2_keywords):
        suggestions.append({
            "original": text,
            "improved": f"{text} with baseline ECHO/MUGA and cardiac monitoring per ACC guidance",
            "reason": "HER2-targeted therapy requires cardiotoxicity monitoring"
        })
    
    # Immunotherapy/checkpoint inhibitor monitoring
    immunotherapy_keywords = [
        "pembrolizumab", "keytruda",
        "nivolumab", "opdivo", 
        "ipilimumab", "yervoy",
        "atezolizumab", "tecentriq",
        "durvalumab", "imfinzi",
        "avelumab", "bavencio",
        "cemiplimab", "libtayo",
        "dostarlimab", "jemperli",
        "checkpoint inhibitor",
        "anti-pd-1", "anti-pd1", "anti pd-1", "anti pd1",
        "anti-pdl1", "anti-pd-l1", "anti pdl1", "anti pd-l1",
        "anti-ctla-4", "anti-ctla4", "anti ctla-4", "anti ctla4",
        "immunotherapy"
    ]
    
    if any(keyword in text_lower for keyword in immunotherapy_keywords):
        suggestions.append({
            "original": text,
            "improved": f"{text} with immune-related adverse event monitoring including thyroid function, liver enzymes, and corticosteroid management protocol",
            "reason": "Checkpoint inhibitor therapy requires systematic immune-related adverse event monitoring"
        })
    
    # CDK4/6 inhibitor monitoring
    cdk46_keywords = [
        "palbociclib", "ibrance",
        "ribociclib", "kisqali", 
        "abemaciclib", "verzenio",
        "cdk4/6", "cdk 4/6", "cdk4-6", "cdk 4-6"
    ]
    
    if any(keyword in text_lower for keyword in cdk46_keywords):
        suggestions.append({
            "original": text,
            "improved": f"{text} with complete blood count monitoring every 2 weeks for first 2 cycles, then monthly for neutropenia assessment",
            "reason": "CDK4/6 inhibitors require systematic hematologic monitoring for neutropenia"
        })
    
    # EGFR TKI monitoring  
    egfr_keywords = [
        "erlotinib", "tarceva",
        "gefitinib", "iressa",
        "afatinib", "gilotrif",
        "osimertinib", "tagrisso",
        "dacomitinib", "vizimpro",
        "egfr inhibitor", "egfr-tki", "egfr tki"
    ]
    
    if any(keyword in text_lower for keyword in egfr_keywords):
        suggestions.append({
            "original": text,
            "improved": f"{text} with dermatologic toxicity monitoring and interstitial lung disease surveillance per prescribing information",
            "reason": "EGFR inhibitors require monitoring for characteristic dermatologic and pulmonary toxicities"
        })
    
    # Anthracycline monitoring
    anthracycline_keywords = [
        "doxorubicin", "adriamycin",
        "daunorubicin", "cerubidine", 
        "epirubicin", "ellence",
        "idarubicin", "idamycin",
        "anthracycline"
    ]
    
    if any(keyword in text_lower for keyword in anthracycline_keywords):
        suggestions.append({
            "original": text,
            "improved": f"{text} with baseline and periodic ECHO/MUGA assessment for cumulative dose-dependent cardiotoxicity monitoring",
            "reason": "Anthracyclines require systematic cardiac monitoring for dose-dependent cardiomyopathy"
        })
    
    return suggestions


def get_drug_specific_monitoring(drug_class: str) -> Dict[str, str]:
    """
    Get specific monitoring requirements for drug classes
    
    Args:
        drug_class: Drug class identifier
        
    Returns:
        Dictionary with monitoring details
    """
    monitoring_protocols = {
        "her2_targeted": {
            "baseline": "ECHO or MUGA scan",
            "frequency": "Every 3 months during treatment",
            "parameters": "LVEF assessment, clinical heart failure symptoms",
            "guidance": "ACC/AHA Heart Failure Guidelines"
        },
        "checkpoint_inhibitor": {
            "baseline": "Thyroid function, liver enzymes, CBC",
            "frequency": "Monthly for first 3 months, then per clinical judgment", 
            "parameters": "TSH, T4, ALT, AST, bilirubin, CBC with differential",
            "guidance": "ASCO Clinical Practice Guideline on immune-related AEs"
        },
        "cdk46_inhibitor": {
            "baseline": "Complete blood count with differential",
            "frequency": "Every 2 weeks x 2 cycles, then monthly",
            "parameters": "Absolute neutrophil count, platelet count",
            "guidance": "Prescribing information dose modification guidelines"
        },
        "egfr_inhibitor": {
            "baseline": "Skin examination, pulmonary function if indicated",
            "frequency": "Weekly x 4, then monthly",
            "parameters": "Dermatologic toxicity grading, dyspnea assessment",
            "guidance": "CTCAE v5.0 grading criteria"
        },
        "anthracycline": {
            "baseline": "ECHO or MUGA scan",
            "frequency": "Every 3-4 cycles or cumulative dose thresholds",
            "parameters": "LVEF, cumulative dose tracking",
            "guidance": "Cardio-oncology consensus recommendations"
        }
    }
    
    return monitoring_protocols.get(drug_class, {})


def detect_high_risk_therapy(text: str) -> List[str]:
    """
    Detect high-risk therapies requiring enhanced monitoring
    
    Args:
        text: Protocol text to analyze
        
    Returns:
        List of detected therapy types
    """
    detected_therapies = []
    text_lower = text.lower()
    
    # Define therapy detection patterns
    therapy_patterns = {
        "her2_targeted": ["trastuzumab", "herceptin", "her2"],
        "checkpoint_inhibitor": ["pembrolizumab", "nivolumab", "ipilimumab", "checkpoint inhibitor", "immunotherapy"],
        "cdk46_inhibitor": ["palbociclib", "ribociclib", "abemaciclib", "cdk4/6"],
        "egfr_inhibitor": ["erlotinib", "gefitinib", "osimertinib", "egfr"],
        "anthracycline": ["doxorubicin", "daunorubicin", "epirubicin", "anthracycline"]
    }
    
    for therapy_type, keywords in therapy_patterns.items():
        if any(keyword in text_lower for keyword in keywords):
            detected_therapies.append(therapy_type)
    
    return detected_therapies


def format_monitoring_recommendation(therapy_type: str, original_text: str) -> Dict[str, str]:
    """
    Format a comprehensive monitoring recommendation
    
    Args:
        therapy_type: Type of therapy detected
        original_text: Original protocol text
        
    Returns:
        Formatted suggestion dictionary
    """
    monitoring = get_drug_specific_monitoring(therapy_type)
    
    if not monitoring:
        return {}
    
    improved_text = f"{original_text} with {monitoring.get('baseline', 'appropriate baseline')} and {monitoring.get('frequency', 'periodic')} monitoring per {monitoring.get('guidance', 'clinical guidelines')}"
    
    reason_map = {
        "her2_targeted": "HER2-targeted therapy requires systematic cardiotoxicity monitoring",
        "checkpoint_inhibitor": "Checkpoint inhibitor therapy requires immune-related adverse event monitoring",
        "cdk46_inhibitor": "CDK4/6 inhibitors require systematic hematologic monitoring",
        "egfr_inhibitor": "EGFR inhibitors require dermatologic and pulmonary toxicity monitoring",
        "anthracycline": "Anthracyclines require systematic cardiac monitoring for dose-dependent toxicity"
    }
    
    return {
        "original": original_text,
        "improved": improved_text,
        "reason": reason_map.get(therapy_type, f"{therapy_type} requires enhanced safety monitoring")
    }