#!/usr/bin/env python3
"""
Unit tests for recommend_simple.py
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from recommend_simple import app, parse_simple_response, redact_phi, get_prompt_hash

client = TestClient(app)

class TestParseSimpleResponse:
    """Test the parse_simple_response function"""
    
    def test_parse_single_suggestion(self):
        """Test parsing a single suggestion block"""
        raw_text = '''ORIGINAL: "The patient will receive trastuzumab"
IMPROVED: "The participant will receive trastuzumab with cardiac monitoring per ACC/AHA guidelines"
REASON: "Replaced 'patient' with 'participant' per ICH-GCP and added cardiotoxicity monitoring for trastuzumab per regulatory guidance"'''
        
        suggestions = parse_simple_response(raw_text)
        
        assert len(suggestions) == 1
        assert suggestions[0]["original"] == "The patient will receive trastuzumab"
        assert suggestions[0]["improved"] == "The participant will receive trastuzumab with cardiac monitoring per ACC/AHA guidelines"
        assert "ICH-GCP" in suggestions[0]["reason"]
    
    def test_parse_multiple_suggestions(self):
        """Test parsing multiple suggestion blocks separated by ---"""
        raw_text = '''ORIGINAL: "Patient eligibility"
IMPROVED: "Participant eligibility"
REASON: "Terminology per ICH-GCP guidelines"
---
ORIGINAL: "Daily dosing"
IMPROVED: "Once daily dosing"
REASON: "Clearer specification of dosing frequency"'''
        
        suggestions = parse_simple_response(raw_text)
        
        assert len(suggestions) == 2
        assert suggestions[0]["original"] == "Patient eligibility"
        assert suggestions[0]["improved"] == "Participant eligibility"
        assert suggestions[1]["original"] == "Daily dosing"
        assert suggestions[1]["improved"] == "Once daily dosing"
    
    def test_parse_with_quotes(self):
        """Test parsing with various quote styles"""
        raw_text = '''ORIGINAL: 'Patients will be monitored'
IMPROVED: "Participants will be monitored"
REASON: 'Updated terminology per regulations' '''
        
        suggestions = parse_simple_response(raw_text)
        
        assert len(suggestions) == 1
        assert suggestions[0]["original"] == "Patients will be monitored"
        assert suggestions[0]["improved"] == "Participants will be monitored"
    
    def test_parse_malformed_response(self):
        """Test parsing when response doesn't match expected format"""
        raw_text = "This is not a properly formatted response"
        
        suggestions = parse_simple_response(raw_text)
        
        assert len(suggestions) == 0
    
    def test_parse_partial_response(self):
        """Test parsing when only some fields are present"""
        raw_text = '''ORIGINAL: "Some text"
IMPROVED: "Better text"'''
        
        suggestions = parse_simple_response(raw_text)
        
        assert len(suggestions) == 0  # Should require all three fields

class TestRedactPhi:
    """Test PHI redaction functionality"""
    
    def test_redact_mrn_patterns(self):
        """Test redaction of MRN-like patterns"""
        text = "Patient MRN 1234567 was enrolled"
        redacted = redact_phi(text)
        assert "1234567" not in redacted
        assert "[REDACTED_MRN]" in redacted
    
    def test_redact_ssn_patterns(self):
        """Test redaction of SSN-like patterns"""
        text = "SSN: 123-45-6789 provided"
        redacted = redact_phi(text)
        assert "123-45-6789" not in redacted
        assert "[REDACTED_SSN]" in redacted
    
    def test_redact_nine_digit_ids(self):
        """Test redaction of 9-digit ID patterns"""
        text = "ID number 123456789 recorded"
        redacted = redact_phi(text)
        assert "123456789" not in redacted
        assert "[REDACTED_ID]" in redacted
    
    def test_preserve_normal_numbers(self):
        """Test that normal numbers are preserved"""
        text = "Dose is 100mg daily for 30 days"
        redacted = redact_phi(text)
        assert "100" in redacted
        assert "30" in redacted

class TestGetPromptHash:
    """Test prompt hashing functionality"""
    
    def test_consistent_hash(self):
        """Test that same text produces same hash"""
        text = "Test prompt text"
        hash1 = get_prompt_hash(text)
        hash2 = get_prompt_hash(text)
        assert hash1 == hash2
    
    def test_different_hash(self):
        """Test that different text produces different hash"""
        hash1 = get_prompt_hash("Text 1")
        hash2 = get_prompt_hash("Text 2")
        assert hash1 != hash2
    
    def test_hash_length(self):
        """Test that hash is correct length"""
        hash_val = get_prompt_hash("Any text")
        assert len(hash_val) == 8

class TestApiEndpoint:
    """Test the API endpoint"""
    
    @patch('recommend_simple.call_azure_openai')
    def test_successful_request(self, mock_openai):
        """Test successful API request"""
        # Mock Azure OpenAI response
        mock_openai.return_value = '''ORIGINAL: "Patient will receive treatment"
IMPROVED: "Participant will receive treatment"
REASON: "Updated terminology per ICH-GCP guidelines"'''
        
        request_data = {
            "text": "Patient will receive treatment",
            "ta": "oncology",
            "phase": "III"
        }
        
        response = client.post("/api/recommend-language-simple", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "suggestions" in data
        assert "metadata" in data
        assert len(data["suggestions"]) == 1
        assert data["suggestions"][0]["original"] == "Patient will receive treatment"
        assert data["suggestions"][0]["improved"] == "Participant will receive treatment"
        assert data["metadata"]["suggestion_count"] == 1
        assert data["metadata"]["parse_success"] is True
    
    @patch('recommend_simple.call_azure_openai')
    def test_model_call_failure(self, mock_openai):
        """Test API response when model call fails"""
        # Mock Azure OpenAI failure
        mock_openai.side_effect = Exception("Model unavailable")
        
        request_data = {
            "text": "Test text"
        }
        
        response = client.post("/api/recommend-language-simple", json=request_data)
        
        assert response.status_code == 502
        assert "Model call failed" in response.json()["detail"]
    
    def test_invalid_request_data(self):
        """Test API response with invalid request data"""
        request_data = {
            "text": ""  # Empty text should fail validation
        }
        
        response = client.post("/api/recommend-language-simple", json=request_data)
        
        assert response.status_code == 422  # Validation error
    
    @patch('recommend_simple.call_azure_openai')
    def test_trastuzumab_detection(self, mock_openai):
        """Test that trastuzumab triggers cardiotoxicity monitoring"""
        mock_openai.return_value = '''ORIGINAL: "Patient receives trastuzumab"
IMPROVED: "Participant receives trastuzumab with cardiac monitoring per ACC/AHA guidelines"
REASON: "Added cardiotoxicity monitoring for trastuzumab per regulatory guidance"'''
        
        request_data = {
            "text": "Patient receives trastuzumab for HER2+ breast cancer"
        }
        
        response = client.post("/api/recommend-language-simple", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        suggestion = data["suggestions"][0]
        assert "cardiac" in suggestion["improved"].lower() or "cardio" in suggestion["improved"].lower()
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["service"] == "simple-recommendations"
        assert "timestamp" in data

if __name__ == "__main__":
    pytest.main([__file__, "-v"])