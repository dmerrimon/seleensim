#!/usr/bin/env python3
"""
Test script for large pharmaceutical protocol analysis
Tests Ilana's ability to handle 200K+ character protocols
"""

import requests
import time
import json

def generate_large_protocol(size_target=200000):
    """Generate a realistic large pharmaceutical protocol"""
    
    protocol_base = """
PROTOCOL TITLE: A Randomized, Double-Blind, Placebo-Controlled, Phase III Study of Investigational Drug XYZ versus Standard of Care in Patients with Advanced Oncological Conditions

1. BACKGROUND AND RATIONALE
The field of oncology has undergone significant transformation with the advent of precision medicine and targeted therapies. Current standard of care treatments have shown efficacy, however there remains substantial unmet medical need for patients who experience disease progression or intolerance to existing therapeutic options.

2. STUDY OBJECTIVES
Primary Objective: To evaluate progression-free survival (PFS) according to RECIST v1.1 criteria
Secondary Objectives: Overall survival, objective response rate, duration of response, safety profile

3. STUDY DESIGN AND METHODOLOGY
This multicenter, randomized, double-blind, placebo-controlled Phase III study will enroll approximately 600 patients across multiple international sites. Patients will be stratified by key baseline characteristics and randomized in a 2:1 ratio.

4. PATIENT POPULATION AND ELIGIBILITY
Inclusion Criteria: Adults ≥18 years with histologically confirmed advanced disease, measurable lesions per RECIST v1.1, ECOG performance status 0-1, adequate organ function
Exclusion Criteria: Prior exposure to study drug class, active brain metastases, significant comorbidities

5. TREATMENT ADMINISTRATION
Study drug will be administered orally at 400mg daily in 28-day cycles. Dose modifications are permitted based on toxicity. Treatment continues until progression, unacceptable toxicity, or withdrawal.

6. STUDY PROCEDURES AND ASSESSMENTS
Comprehensive visit schedule including screening, treatment, and follow-up phases with detailed procedures, laboratory assessments, imaging studies, and safety monitoring.

7. EFFICACY ENDPOINTS AND ASSESSMENTS
Primary endpoint assessment via imaging every 8 weeks for first year, then every 12 weeks. Independent central review of all scans. Time-to-event analyses for survival endpoints.

8. SAFETY MONITORING AND REPORTING
Continuous safety monitoring with detailed adverse event collection, grading per CTCAE v5.0, and expedited reporting procedures for serious adverse events.

9. STATISTICAL ANALYSIS PLAN
Sample size calculation provides 90% power to detect clinically meaningful difference. Intent-to-treat and per-protocol analyses planned with appropriate interim analyses.

10. DATA MANAGEMENT AND QUALITY ASSURANCE
Electronic data capture system with comprehensive data management procedures, monitoring plans, and quality control measures.

11. REGULATORY AND ETHICAL CONSIDERATIONS
Study conducted per ICH-GCP, local regulations, and institutional requirements with appropriate oversight and compliance monitoring.
"""

    # Expand each section with detailed pharmaceutical content
    detailed_protocol = ""
    
    for section_num in range(1, 12):
        section_content = protocol_base
        
        # Add detailed subsections
        for subsection in range(1, 26):  # 25 subsections per section
            detailed_protocol += f"""
{section_num}.{subsection} DETAILED PROCEDURES AND REQUIREMENTS

This subsection provides comprehensive guidance for clinical site personnel regarding the conduct of this pharmaceutical clinical trial. All procedures must be performed in accordance with Good Clinical Practice guidelines, sponsor standard operating procedures, and applicable regulatory requirements.

{section_num}.{subsection}.1 Procedural Guidelines
Site staff must ensure proper execution of all study-related activities including participant screening, enrollment, treatment administration, safety monitoring, efficacy assessments, and data collection. Each procedure requires appropriate documentation in source documents and case report forms.

{section_num}.{subsection}.2 Timing and Visit Windows
All study visits must be conducted within specified time windows as outlined in the study calendar. Deviations from the protocol-specified timing require documentation and may impact the evaluability of study endpoints.

{section_num}.{subsection}.3 Documentation Requirements
Complete and accurate documentation is essential for regulatory compliance and data integrity. All study-related activities must be recorded contemporaneously in source documents with appropriate signatures and dates.

{section_num}.{subsection}.4 Training and Qualification
Site personnel must complete protocol-specific training and maintain current Good Clinical Practice certification. Regular refresher training may be required throughout the study conduct.

{section_num}.{subsection}.5 Quality Assurance Measures
Regular monitoring visits will verify compliance with the protocol, GCP guidelines, and regulatory requirements. Sites must maintain study documents according to sponsor and regulatory standards.

{section_num}.{subsection}.6 Safety Considerations
Patient safety is the primary concern throughout the study. Any safety signals or concerns must be reported immediately according to established procedures and timelines.

{section_num}.{subsection}.7 Data Collection Standards
All data must be collected according to the case report form completion guidelines with attention to accuracy, completeness, and consistency across all study sites.

{section_num}.{subsection}.8 Compliance Monitoring
Regular assessment of protocol compliance includes review of enrollment rates, inclusion/exclusion criteria adherence, visit scheduling, and procedure completion.

{section_num}.{subsection}.9 Communication Procedures
Clear communication channels must be maintained between sites, sponsor, and regulatory authorities. Regular updates and notifications ensure effective study management.

{section_num}.{subsection}.10 Emergency Procedures
Sites must have appropriate emergency procedures in place for handling serious adverse events, medical emergencies, and other urgent situations that may arise during study conduct.

"""
    
    # Add comprehensive appendices
    appendices = [
        "APPENDIX A: Study Calendar and Visit Schedule",
        "APPENDIX B: Laboratory Manual and Procedures", 
        "APPENDIX C: Imaging Guidelines and Requirements",
        "APPENDIX D: Pharmacokinetic Sampling Procedures",
        "APPENDIX E: Adverse Event Reporting Guidelines",
        "APPENDIX F: Concomitant Medication Restrictions",
        "APPENDIX G: Emergency Contact Information",
        "APPENDIX H: Case Report Form Completion Guidelines",
        "APPENDIX I: Source Document Requirements",
        "APPENDIX J: Protocol Amendment History"
    ]
    
    for appendix in appendices:
        detailed_protocol += f"\n\n{appendix}\n" + "=" * len(appendix) + "\n"
        # Add detailed content for each appendix
        for item in range(1, 51):  # 50 detailed items per appendix
            detailed_protocol += f"""
{appendix.split(':')[0]}.{item} Detailed information and procedures for {appendix.lower()} including comprehensive instructions, requirements, contact information, forms, templates, guidelines, and reference materials that are essential for proper study conduct and regulatory compliance. This section provides specific step-by-step instructions and comprehensive reference materials for clinical site personnel to ensure consistent and compliant study execution across all participating sites and investigators.

"""
    
    # Ensure we reach the target size
    current_size = len(detailed_protocol)
    if current_size < size_target:
        padding_needed = size_target - current_size
        padding_text = "Additional detailed protocol content including standard operating procedures, case report form guidelines, regulatory compliance requirements, quality assurance measures, and comprehensive reference materials for clinical trial conduct. " * (padding_needed // 200 + 1)
        detailed_protocol += padding_text[:padding_needed]
    
    return detailed_protocol

def test_large_protocol_analysis():
    """Test API with realistic large protocol"""
    
    print("🧪 Testing Ilana API with Enterprise-Scale Pharmaceutical Protocol")
    print("=" * 70)
    
    # Generate realistic large protocol
    print("📄 Generating realistic pharmaceutical protocol...")
    large_protocol = generate_large_protocol(220000)  # Target 220K chars
    
    protocol_size = len(large_protocol)
    print(f"✅ Generated protocol: {protocol_size:,} characters")
    print(f"📊 Size comparison: Real pharma protocols often 200K-500K+ characters")
    
    # Test API performance
    print("\n🚀 Testing Ilana API performance...")
    
    api_url = "http://localhost:8000/api/analyze"
    payload = {
        "content": large_protocol,
        "analysis_type": "enterprise_large_protocol"
    }
    
    try:
        start_time = time.time()
        response = requests.post(api_url, json=payload, timeout=300)  # 5 minute timeout
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        if response.status_code == 200:
            analysis_data = response.json()
            
            print(f"✅ SUCCESS: Enterprise protocol analysis completed")
            print(f"   📄 Protocol size: {protocol_size:,} characters")
            print(f"   ⏱️  Processing time: {processing_time:.2f} seconds")
            print(f"   🎯 TA detected: {analysis_data.get('therapeutic_area', 'N/A')}")
            print(f"   💡 Suggestions: {len(analysis_data.get('suggestions', []))}")
            print(f"   📊 Overall score: {analysis_data.get('overall_score', 'N/A')}")
            print(f"   🚀 Performance: {int(protocol_size/processing_time):,} chars/second")
            
            # Performance benchmarks for enterprise protocols
            if processing_time < 30:
                print("🟢 EXCELLENT: <30 seconds for 200K+ character protocol")
            elif processing_time < 60:
                print("🟡 GOOD: 30-60 seconds for large enterprise protocol")  
            elif processing_time < 120:
                print("🟠 ACCEPTABLE: 1-2 minutes for enterprise protocol")
            else:
                print("🔴 NEEDS OPTIMIZATION: >2 minutes for enterprise protocol")
                
            # Analyze suggestions for large protocol
            suggestions = analysis_data.get('suggestions', [])
            if len(suggestions) > 15:
                print(f"✅ Good analysis depth: {len(suggestions)} optimization opportunities")
            elif len(suggestions) > 5:
                print(f"⚠️  Moderate coverage: {len(suggestions)} suggestions for large protocol")
            else:
                print(f"❌ May need tuning: Only {len(suggestions)} suggestions for 200K+ protocol")
                
        else:
            print(f"❌ FAILED: API returned status {response.status_code}")
            if response.status_code == 413:
                print("   💡 Request too large - implement document chunking")
            elif response.status_code == 504:
                print("   💡 Gateway timeout - optimize processing or add async handling")
            elif response.status_code == 500:
                print("   💡 Server error - check memory usage and processing optimization")
            
    except requests.exceptions.Timeout:
        print("❌ TIMEOUT: Request exceeded 5 minute timeout")
        print("   💡 For enterprise deployment, implement:")
        print("      • Background processing with progress tracking")
        print("      • Document chunking for very large protocols")
        print("      • WebSocket status updates for long-running analysis")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ REQUEST ERROR: {e}")
        print("   💡 Network issue - may need retry logic for large documents")
        
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
    
    # Recommendations for enterprise deployment
    print("\n🏢 ENTERPRISE DEPLOYMENT RECOMMENDATIONS:")
    print("   • Implement progressive document chunking (10-20KB chunks)")
    print("   • Add real-time progress indicators for analysis >30 seconds")
    print("   • Use background processing with status updates via WebSocket")
    print("   • Implement intelligent caching for repeated large document analysis")
    print("   • Add memory optimization for concurrent large document processing")
    print("   • Consider server-side preprocessing for 500K+ character protocols")
    print("   • Implement document size warnings and user guidance")
    print("   • Add retry logic with exponential backoff for network issues")

if __name__ == "__main__":
    test_large_protocol_analysis()