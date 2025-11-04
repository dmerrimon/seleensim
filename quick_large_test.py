#!/usr/bin/env python3
import requests
import time

# Create a large protocol (50,000 characters)
large_protocol = """
PROTOCOL TITLE: Phase III Randomized Study of Pembrolizumab in Advanced Breast Cancer

BACKGROUND: Breast cancer remains a leading cause of cancer death worldwide. Despite advances in treatment, patients with metastatic disease have limited therapeutic options after progression on standard therapies. Pembrolizumab has shown promising activity in early phase studies.

OBJECTIVES: 
Primary: Evaluate progression-free survival per RECIST v1.1
Secondary: Overall survival, objective response rate, safety profile

DESIGN: Multicenter, randomized, double-blind, placebo-controlled Phase III study. Approximately 600 patients randomized 2:1.

POPULATION:
Inclusion: Adults ≥18 years with metastatic breast cancer, measurable disease per RECIST v1.1, ECOG 0-1, adequate organ function
Exclusion: Prior immunotherapy, active autoimmune disease, brain metastases

TREATMENT: Pembrolizumab 200mg IV Q3W vs placebo until progression or toxicity

PROCEDURES:
Visit 1 (Screening): Informed consent, medical history, physical exam, vital signs, laboratory tests (CBC, CMP, LFTs, TSH, urinalysis), ECG, echo, CT/MRI imaging
Visit 2 (C1D1): Vitals, labs (CBC, CMP, LFTs, TSH), physical exam, AE assessment, drug administration  
Visit 3 (C1D15): Vitals, labs (CBC, CMP, LFTs), AE assessment
Visit 4 (C2D1): Vitals, labs, physical exam, AE assessment, drug administration
Visit 5 (C3D1): Vitals, labs, physical exam, AE assessment, drug administration, imaging
""" * 200  # Repeat to make it ~50k characters

print(f"Testing with {len(large_protocol):,} character protocol...")
start_time = time.time()

try:
    response = requests.post(
        "http://localhost:8000/api/analyze",
        json={"content": large_protocol, "analysis_type": "large_test"},
        timeout=60  # 60 second timeout
    )
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ SUCCESS - {len(large_protocol):,} chars in {processing_time:.3f}s")
        print(f"   TA: {data['therapeutic_area']}")
        print(f"   Suggestions: {len(data['suggestions'])}")
        print(f"   Score: {data['overall_score']}")
        print(f"   Rate: {len(large_protocol)/processing_time:,.0f} chars/sec")
    else:
        print(f"❌ FAILED - Status: {response.status_code}")
        
except requests.exceptions.Timeout:
    print("❌ TIMEOUT after 60 seconds")
except Exception as e:
    print(f"❌ ERROR: {e}")