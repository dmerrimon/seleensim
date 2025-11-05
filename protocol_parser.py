#!/usr/bin/env python3
"""
Protocol Document Parser for Optimization Rule Engine
Extracts visit schedules, procedures, and endpoints from protocol text
"""

import os
import re
import json
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import pandas as pd

from optimization_rule_engine import ProcedureInstance, VisitSchedule, ParsedDocument
from therapeutic_area_classifier import create_ta_classifier

logger = logging.getLogger(__name__)

class ProtocolParser:
    """
    Parser for extracting structured data from protocol documents
    
    Extracts:
    - Visit schedule and procedures
    - Primary and secondary endpoints
    - Study sections
    """
    
    def __init__(self):
        self.ta_classifier = create_ta_classifier()
        
        # Common section patterns
        self.section_patterns = {
            'objectives': [
                r'(?i)(primary\s+objective|study\s+objective|objective)',
                r'(?i)(secondary\s+objective)'
            ],
            'endpoints': [
                r'(?i)(primary\s+endpoint|primary\s+outcome)',
                r'(?i)(secondary\s+endpoint|secondary\s+outcome)',
                r'(?i)(exploratory\s+endpoint)'
            ],
            'visit_schedule': [
                r'(?i)(schedule\s+of\s+event|schedule\s+of\s+assessment|visit\s+schedule)',
                r'(?i)(study\s+procedures|protocol\s+procedures)'
            ],
            'inclusion_criteria': [
                r'(?i)(inclusion\s+criteria|eligibility\s+criteria)'
            ],
            'exclusion_criteria': [
                r'(?i)(exclusion\s+criteria)'
            ]
        }
        
        # Visit name patterns
        self.visit_patterns = [
            r'(?i)visit\s+(\d+[a-z]?)',
            r'(?i)(screening|baseline|day\s+\d+|week\s+\d+|month\s+\d+)',
            r'(?i)(end\s+of\s+study|eos|follow[- ]?up)',
            r'(?i)cycle\s+(\d+)',
            r'(?i)v(\d+)',
        ]
        
        # Procedure patterns
        self.procedure_patterns = {
            'vitals': [
                r'(?i)(vital\s+sign|vitals|blood\s+pressure|heart\s+rate|temperature|weight|height)',
                r'(?i)(bp|hr|temp|bmi)'
            ],
            'labs': [
                r'(?i)(laborator|lab|blood\s+test|chemistry|hematology|cbc|cmp)',
                r'(?i)(complete\s+blood\s+count|comprehensive\s+metabolic|liver\s+function)',
                r'(?i)(lipid|glucose|hba1c|biomarker)'
            ],
            'ecg': [
                r'(?i)(ecg|ekg|electrocardiogram|cardiac\s+monitor)'
            ],
            'imaging': [
                r'(?i)(imaging|ct\s+scan|mri|x[- ]?ray|ultrasound|radiograph)',
                r'(?i)(computed\s+tomography|magnetic\s+resonance)'
            ],
            'echo': [
                r'(?i)(echo|echocardiogram|cardiac\s+ultrasound)'
            ],
            'physical_exam': [
                r'(?i)(physical\s+exam|pe|examination|clinical\s+assessment)'
            ],
            'concomitant_meds': [
                r'(?i)(concomitant\s+medication|concurrent\s+medication|con\s+med)'
            ],
            'adverse_events': [
                r'(?i)(adverse\s+event|ae|safety\s+assessment|tolerability)'
            ]
        }
        
        logger.info("📋 Protocol Parser initialized")
    
    def parse_protocol(self, protocol_text: str, doc_id: str = None) -> ParsedDocument:
        """
        Parse protocol text into structured format
        
        Args:
            protocol_text: Full protocol text
            doc_id: Optional document identifier
            
        Returns:
            ParsedDocument with extracted structure
        """
        
        logger.info(f"🔍 Parsing protocol document ({len(protocol_text)} characters)")
        
        # Detect therapeutic area
        ta_detection = self.ta_classifier.detect_therapeutic_area(protocol_text)
        logger.info(f"📊 Detected TA: {ta_detection.therapeutic_area} ({ta_detection.confidence:.0%})")
        
        # Extract sections
        sections = self._extract_sections(protocol_text)
        
        # Extract endpoints
        endpoints = self._extract_endpoints(protocol_text, sections)
        
        # Extract visit schedule
        visit_schedule = self._extract_visit_schedule(protocol_text, sections)
        
        parsed_doc = ParsedDocument(
            doc_id=doc_id or "parsed_protocol",
            visit_schedule=visit_schedule,
            endpoints=endpoints,
            sections=sections,
            ta_detection=ta_detection
        )
        
        logger.info(f"✅ Parsed: {len(visit_schedule)} visits, {len(endpoints)} endpoints")
        return parsed_doc
    
    def _extract_sections(self, text: str) -> Dict[str, str]:
        """Extract major protocol sections"""
        
        sections = {}
        
        for section_name, patterns in self.section_patterns.items():
            for pattern in patterns:
                matches = list(re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE))
                
                if matches:
                    # Find section content
                    start_pos = matches[0].start()
                    
                    # Find end of section (next major heading or end of text)
                    next_section_pattern = r'(?i)^\s*\d+\.?\s*(primary|secondary|objective|endpoint|criteria|schedule|procedure|method|statistical|reference)'
                    next_match = re.search(next_section_pattern, text[start_pos + 100:], re.MULTILINE)
                    
                    if next_match:
                        end_pos = start_pos + 100 + next_match.start()
                    else:
                        end_pos = min(start_pos + 2000, len(text))  # Limit section size
                    
                    section_text = text[start_pos:end_pos].strip()
                    sections[section_name] = section_text
                    break  # Use first match
        
        return sections
    
    def _extract_endpoints(self, text: str, sections: Dict[str, str]) -> List[Dict[str, str]]:
        """Extract primary and secondary endpoints"""
        
        endpoints = []
        
        # Check endpoints section first
        endpoint_text = sections.get('endpoints', '')
        if not endpoint_text:
            # Look for endpoints in full text
            endpoint_patterns = [
                r'(?i)primary\s+endpoint[:\s]*([^\.]+\.)',
                r'(?i)primary\s+outcome[:\s]*([^\.]+\.)',
                r'(?i)secondary\s+endpoint[:\s]*([^\.]+\.)',
                r'(?i)secondary\s+outcome[:\s]*([^\.]+\.)'
            ]
            
            endpoint_text = text
        
        # Extract primary endpoints
        primary_patterns = [
            r'(?i)primary\s+endpoint[:\s]*([^\.]+\.)',
            r'(?i)primary\s+outcome[:\s]*([^\.]+\.)',
            r'(?i)the\s+primary\s+endpoint\s+is[:\s]*([^\.]+\.)'
        ]
        
        for pattern in primary_patterns:
            matches = re.findall(pattern, endpoint_text)
            for match in matches:
                endpoints.append({
                    'text': match.strip(),
                    'type': 'primary'
                })
        
        # Extract secondary endpoints
        secondary_patterns = [
            r'(?i)secondary\s+endpoint[:\s]*([^\.]+\.)',
            r'(?i)secondary\s+outcome[:\s]*([^\.]+\.)',
            r'(?i)secondary\s+endpoints?\s+include[:\s]*([^\.]+\.)'
        ]
        
        for pattern in secondary_patterns:
            matches = re.findall(pattern, endpoint_text)
            for match in matches:
                endpoints.append({
                    'text': match.strip(),
                    'type': 'secondary'
                })
        
        # If no endpoints found, try alternative extraction
        if not endpoints:
            endpoints = self._extract_endpoints_alternative(text)
        
        return endpoints
    
    def _extract_endpoints_alternative(self, text: str) -> List[Dict[str, str]]:
        """Alternative endpoint extraction method"""
        
        endpoints = []
        
        # Look for common endpoint patterns
        endpoint_indicators = [
            (r'(?i)(progression[- ]free\s+survival|pfs)', 'primary'),
            (r'(?i)(overall\s+survival|os)', 'primary'),
            (r'(?i)(objective\s+response\s+rate|orr)', 'primary'),
            (r'(?i)(change\s+in\s+hba1c)', 'primary'),
            (r'(?i)(change\s+in\s+blood\s+pressure)', 'primary'),
            (r'(?i)(safety\s+and\s+tolerability)', 'secondary'),
            (r'(?i)(adverse\s+events)', 'secondary'),
            (r'(?i)(quality\s+of\s+life)', 'secondary')
        ]
        
        for pattern, endpoint_type in endpoint_indicators:
            matches = re.findall(pattern, text)
            for match in matches:
                endpoints.append({
                    'text': match,
                    'type': endpoint_type
                })
        
        return endpoints
    
    def _extract_visit_schedule(self, text: str, sections: Dict[str, str]) -> List[VisitSchedule]:
        """Extract visit schedule and procedures"""
        
        visit_schedule = []
        
        # Look for schedule of events table
        schedule_text = sections.get('visit_schedule', '')
        if not schedule_text:
            # Search for table patterns in full text
            table_patterns = [
                r'(?i)(schedule\s+of\s+event|schedule\s+of\s+assessment).*?(?=\n\s*\n|\n\s*[A-Z]|\Z)',
                r'(?i)(visit\s+schedule).*?(?=\n\s*\n|\n\s*[A-Z]|\Z)'
            ]
            
            for pattern in table_patterns:
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    schedule_text = match.group(0)
                    break
        
        if schedule_text:
            # Try to parse structured schedule
            visit_schedule = self._parse_schedule_table(schedule_text)
        
        # If no structured schedule found, extract from text patterns
        if not visit_schedule:
            visit_schedule = self._extract_visits_from_text(text)
        
        return visit_schedule
    
    def _parse_schedule_table(self, schedule_text: str) -> List[VisitSchedule]:
        """Parse structured schedule of events table"""
        
        visits = []
        
        # Split into lines and look for visit headers
        lines = schedule_text.split('\n')
        current_visit = None
        procedures = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if line contains visit information
            visit_match = self._extract_visit_from_line(line)
            if visit_match:
                # Save previous visit if exists
                if current_visit:
                    visits.append(VisitSchedule(
                        visit_id=current_visit['id'],
                        visit_name=current_visit['name'],
                        timepoint=current_visit['timepoint'],
                        procedures=procedures
                    ))
                
                current_visit = visit_match
                procedures = []
            
            # Check if line contains procedure information
            procedure_match = self._extract_procedure_from_line(line)
            if procedure_match and current_visit:
                procedures.append(ProcedureInstance(
                    text=procedure_match['text'],
                    normalized_text=self._normalize_text(procedure_match['text']),
                    visit_id=current_visit['id'],
                    visit_name=current_visit['name'],
                    section='schedule'
                ))
        
        # Add final visit
        if current_visit:
            visits.append(VisitSchedule(
                visit_id=current_visit['id'],
                visit_name=current_visit['name'],
                timepoint=current_visit['timepoint'],
                procedures=procedures
            ))
        
        return visits
    
    def _extract_visits_from_text(self, text: str) -> List[VisitSchedule]:
        """Extract visits from unstructured text"""
        
        visits = []
        
        # Look for visit mentions in text
        for i, pattern in enumerate(self.visit_patterns):
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                visit_text = match.group(0)
                visit_id = f"V{len(visits) + 1}"
                
                # Extract procedures around this visit mention
                start_pos = max(0, match.start() - 200)
                end_pos = min(len(text), match.end() + 200)
                context = text[start_pos:end_pos]
                
                procedures = self._extract_procedures_from_context(context, visit_id, visit_text)
                
                if procedures:  # Only add visit if procedures found
                    visits.append(VisitSchedule(
                        visit_id=visit_id,
                        visit_name=visit_text,
                        timepoint=visit_text,
                        procedures=procedures
                    ))
        
        # If no visits found, create generic visit structure
        if not visits:
            visits = self._create_generic_visit_structure(text)
        
        return visits
    
    def _extract_visit_from_line(self, line: str) -> Optional[Dict[str, str]]:
        """Extract visit information from a line"""
        
        for pattern in self.visit_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                visit_text = match.group(0).strip()
                visit_id = f"V{hash(visit_text) % 1000}"  # Simple ID generation
                
                return {
                    'id': visit_id,
                    'name': visit_text,
                    'timepoint': visit_text
                }
        
        return None
    
    def _extract_procedure_from_line(self, line: str) -> Optional[Dict[str, str]]:
        """Extract procedure information from a line"""
        
        for proc_type, patterns in self.procedure_patterns.items():
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    return {
                        'text': line.strip(),
                        'type': proc_type
                    }
        
        # Generic procedure detection
        if any(word in line.lower() for word in ['assessment', 'evaluation', 'measurement', 'collection', 'review']):
            return {
                'text': line.strip(),
                'type': 'other'
            }
        
        return None
    
    def _extract_procedures_from_context(self, context: str, visit_id: str, visit_name: str) -> List[ProcedureInstance]:
        """Extract procedures from text context around a visit"""
        
        procedures = []
        
        # Split context into sentences/phrases
        sentences = re.split(r'[.;,\n]', context)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:  # Skip very short fragments
                continue
            
            # Check if sentence contains procedure indicators
            for proc_type, patterns in self.procedure_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, sentence, re.IGNORECASE):
                        procedures.append(ProcedureInstance(
                            text=sentence,
                            normalized_text=self._normalize_text(sentence),
                            visit_id=visit_id,
                            visit_name=visit_name,
                            section='extracted'
                        ))
                        break
        
        return procedures
    
    def _create_generic_visit_structure(self, text: str) -> List[VisitSchedule]:
        """Create generic visit structure when no visits are detected"""
        
        # Look for any procedure mentions and group them
        all_procedures = []
        
        sentences = re.split(r'[.\n]', text)
        for sentence in sentences[:50]:  # Limit search to avoid too many procedures
            sentence = sentence.strip()
            if len(sentence) < 15:
                continue
            
            for proc_type, patterns in self.procedure_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, sentence, re.IGNORECASE):
                        all_procedures.append(ProcedureInstance(
                            text=sentence,
                            normalized_text=self._normalize_text(sentence),
                            visit_id="V1",
                            visit_name="Study Visits",
                            section='extracted'
                        ))
                        break
        
        if all_procedures:
            return [VisitSchedule(
                visit_id="V1",
                visit_name="Study Visits",
                timepoint="Various timepoints",
                procedures=all_procedures[:10]  # Limit to 10 procedures
            )]
        
        return []
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        # Remove extra whitespace, convert to lowercase
        normalized = re.sub(r'\s+', ' ', text.lower().strip())
        # Remove punctuation except essential ones
        normalized = re.sub(r'[^\w\s\-/]', '', normalized)
        return normalized

def create_protocol_parser() -> ProtocolParser:
    """Factory function for protocol parser"""
    return ProtocolParser()

# Example usage and testing
if __name__ == "__main__":
    # Test the protocol parser
    parser = create_protocol_parser()
    
    # Sample protocol text for testing
    test_protocol = """
    Primary Objective:
    To evaluate the efficacy and safety of Drug X in patients with metastatic breast cancer.
    
    Primary Endpoint:
    Progression-free survival (PFS) as assessed by investigator according to RECIST v1.1.
    
    Secondary Endpoints:
    - Overall survival (OS)
    - Objective response rate (ORR)
    - Safety and tolerability
    
    Schedule of Events:
    
    Visit 1 (Screening):
    - Medical history
    - Physical examination
    - Vital signs
    - Laboratory assessments (CBC, chemistry panel)
    - ECG
    - Imaging (CT chest/abdomen/pelvis)
    
    Visit 2 (Baseline/Day 1):
    - Physical examination
    - Vital signs
    - Laboratory safety tests
    - Drug administration
    
    Visit 3 (Week 4):
    - Physical exam
    - Vitals
    - Lab safety
    - Adverse event assessment
    
    Visit 4 (Week 8):
    - Physical examination
    - Vital signs
    - Laboratory assessments
    - Imaging assessment
    """
    
    print("🧪 Testing Protocol Parser:")
    parsed_doc = parser.parse_protocol(test_protocol, "test_protocol")
    
    print(f"\n📊 Therapeutic Area: {parsed_doc.ta_detection.therapeutic_area} ({parsed_doc.ta_detection.confidence:.0%})")
    print(f"📋 Sections extracted: {list(parsed_doc.sections.keys())}")
    print(f"🎯 Endpoints found: {len(parsed_doc.endpoints)}")
    for endpoint in parsed_doc.endpoints:
        print(f"   - {endpoint['type']}: {endpoint['text']}")
    
    print(f"📅 Visits found: {len(parsed_doc.visit_schedule)}")
    for visit in parsed_doc.visit_schedule:
        print(f"   - {visit.visit_name}: {len(visit.procedures)} procedures")
        for proc in visit.procedures[:3]:  # Show first 3 procedures
            print(f"     • {proc.text[:50]}...")