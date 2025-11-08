"""
Integration test for /api/generate-rewrite-ta endpoint
Tests TA-aware rewriting with mocked vector DB and Azure AI
"""

import pytest
import requests
import subprocess
import os
import time
from unittest.mock import patch, MagicMock, AsyncMock
import json
from typing import Dict, Any, List

class TestGenerateRewriteTAIntegration:
    """Integration tests for TA-aware rewrite generation"""
    
    @classmethod
    def setup_class(cls):
        """Start test server with mocked dependencies"""
        cls.server_process = subprocess.Popen(
            ["python3", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
            env={**os.environ, "ANALYSIS_MODE": "hybrid", "RAG_ASYNC_MODE": "false"},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for server to start
        cls._wait_for_server("http://127.0.0.1:8000/health", timeout=15)
        
    @classmethod
    def teardown_class(cls):
        """Stop test server after tests complete"""
        if hasattr(cls, 'server_process'):
            cls.server_process.terminate()
            try:
                cls.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.server_process.kill()
                cls.server_process.wait()
    
    @staticmethod
    def _wait_for_server(url: str, timeout: int = 30):
        """Wait for server to become available"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    return
            except requests.exceptions.RequestException:
                pass
            time.sleep(0.5)
        raise RuntimeError(f"Server did not start within {timeout} seconds")
    
    @staticmethod
    def _create_mock_vector_db_response() -> List[Dict[str, Any]]:
        """Create deterministic vector DB response"""
        return [
            {
                "id": "exemplar_001",
                "text": "Patients enrolled in clinical trial",
                "improved": "Study participants enrolled in clinical research trial",
                "rationale": "Use 'participants' per ICH-GCP guidelines",
                "therapeutic_area": "oncology",
                "confidence": 0.95,
                "regulatory_source": "ICH-GCP E6(R2)",
                "metadata": {
                    "vector_score": 0.87,
                    "exemplar_type": "terminology_replacement"
                }
            },
            {
                "id": "exemplar_002", 
                "text": "adverse events monitoring",
                "improved": "adverse events monitoring per CTCAE v5.0 criteria",
                "rationale": "Include standardized grading system reference",
                "therapeutic_area": "oncology",
                "confidence": 0.92,
                "regulatory_source": "FDA Guidance",
                "metadata": {
                    "vector_score": 0.83,
                    "exemplar_type": "regulatory_enhancement"
                }
            }
        ]
    
    @staticmethod
    def _create_mock_azure_response() -> Dict[str, Any]:
        """Create deterministic Azure AI response"""
        return {
            "improved": "Study participants demonstrated favorable clinical response to the investigational oncology treatment, with comprehensive adverse event monitoring conducted per CTCAE v5.0 criteria and ICH-GCP guidelines.",
            "rationale": "Enhanced for regulatory compliance by replacing 'patients' with 'participants' per ICH-GCP requirements, adding specific reference to CTCAE v5.0 for adverse event classification, and incorporating comprehensive monitoring language required for oncology trials.",
            "sources": [
                "ICH-GCP E6(R2): Good Clinical Practice Guidelines",
                "FDA Guidance: Clinical Trial Endpoints for Cancer Drugs",
                "CTCAE v5.0: Common Terminology Criteria for Adverse Events"
            ],
            "model_version": "azure-openai-gpt4-oncology-aware-v2.1",
            "confidence": 0.94,
            "processing_metadata": {
                "prompt_tokens": 245,
                "completion_tokens": 178,
                "total_tokens": 423,
                "model_temperature": 0.3,
                "therapeutic_context": "oncology_clinical_trials"
            }
        }
    
    @staticmethod
    def _create_mock_regulatory_guidelines() -> List[str]:
        """Create mock regulatory guidelines"""
        return [
            "ICH-GCP E6(R2): Use 'participant' instead of 'patient' in clinical research",
            "FDA Guidance: Include specific safety monitoring protocols for oncology trials",
            "CTCAE v5.0: Reference standardized adverse event grading system",
            "EMA Guidelines: Ensure comprehensive safety data collection and reporting"
        ]
    
    @staticmethod
    def _handle_ta_response(response, expected_suggestion_id: str = None):
        """Handle TA response that may be 200 (processed) or 202 (queued)"""
        assert response.status_code in [200, 202], f"Unexpected status code: {response.status_code}"
        data = response.json()
        
        if response.status_code == 202:
            # Verify queued response structure
            assert "status" in data
            assert data["status"] == "queued"
            if expected_suggestion_id:
                assert "suggestion_id" in data
                assert data["suggestion_id"] == expected_suggestion_id
            assert "message" in data
            return data, True  # True = is_queued
        
        return data, False  # False = not_queued
    
    def test_generate_rewrite_ta_oncology_deterministic(self):
        """Test TA rewrite with mocked dependencies for deterministic output"""
        
        # Mock the external dependencies
        with patch('main.query_vector_db') as mock_vector_db, \
             patch('main.generate_ta_aware_rewrite') as mock_azure, \
             patch('main.get_regulatory_guidelines') as mock_guidelines:
            
            # Configure mocks with deterministic responses
            mock_vector_db.return_value = self._create_mock_vector_db_response()
            mock_azure.return_value = self._create_mock_azure_response()
            mock_guidelines.return_value = self._create_mock_regulatory_guidelines()
            
            # Test payload
            payload = {
                "text": "Patients showed good response to treatment with adverse events monitoring",
                "ta": "oncology",
                "context": "clinical_trial",
                "suggestion_id": "test_deterministic_001"
            }
            
            response = requests.post(
                "http://127.0.0.1:8000/api/generate-rewrite-ta",
                json=payload,
                timeout=15
            )
            
            data, is_queued = self._handle_ta_response(response, "test_deterministic_001")
            
            if is_queued:
                # Test passes with queued response
                return
            
            # If status is 200, verify full response structure
            assert "suggestion_id" in data
            assert data["suggestion_id"] == "test_deterministic_001"
            assert "original_text" in data
            assert "improved" in data
            assert "rationale" in data
            assert "sources" in data
            assert "model_version" in data
            
            # Verify deterministic improved text
            expected_improved = "Study participants demonstrated favorable clinical response to the investigational oncology treatment, with comprehensive adverse event monitoring conducted per CTCAE v5.0 criteria and ICH-GCP guidelines."
            assert data["improved"] == expected_improved
            
            # Verify sources are included
            sources = data["sources"]
            assert isinstance(sources, list)
            assert len(sources) >= 2
            assert any("ICH-GCP" in source for source in sources)
            assert any("CTCAE" in source for source in sources)
            
            # Verify rationale mentions regulatory compliance
            rationale = data["rationale"]
            assert "ICH-GCP" in rationale
            assert "participants" in rationale
            assert "CTCAE" in rationale
            
            # Verify mock functions were called correctly
            mock_vector_db.assert_called_once()
            mock_azure.assert_called_once()
            mock_guidelines.assert_called_once_with("oncology")
    
    def test_generate_rewrite_ta_cardiology_context(self):
        """Test TA rewrite with cardiology therapeutic area"""
        
        cardiology_exemplars = [
            {
                "id": "cardio_001",
                "text": "heart failure patients",
                "improved": "patients with heart failure",
                "rationale": "Person-first language per AHA guidelines",
                "therapeutic_area": "cardiology",
                "confidence": 0.89
            }
        ]
        
        cardiology_azure_response = {
            "improved": "Participants with heart failure demonstrated significant improvement in ejection fraction measurements, with cardiac safety monitoring conducted per AHA/ACC guidelines throughout the treatment period.",
            "rationale": "Enhanced for cardiology regulatory compliance by using person-first language and including specific cardiac safety monitoring requirements.",
            "sources": [
                "AHA/ACC Heart Failure Guidelines",
                "FDA Guidance: Cardiovascular Safety Studies"
            ],
            "model_version": "azure-openai-gpt4-cardiology-aware-v1.8"
        }
        
        with patch('main.query_vector_db') as mock_vector_db, \
             patch('main.generate_ta_aware_rewrite') as mock_azure, \
             patch('main.get_regulatory_guidelines') as mock_guidelines:
            
            mock_vector_db.return_value = cardiology_exemplars
            mock_azure.return_value = cardiology_azure_response
            mock_guidelines.return_value = ["AHA/ACC Guidelines: Use person-first language"]
            
            payload = {
                "text": "Heart failure patients showed improvement in cardiac function",
                "ta": "cardiology", 
                "context": "clinical_study",
                "suggestion_id": "cardio_test_001"
            }
            
            response = requests.post(
                "http://127.0.0.1:8000/api/generate-rewrite-ta",
                json=payload,
                timeout=15
            )
            
            data, is_queued = self._handle_ta_response(response, "cardio_test_001")
            
            if is_queued:
                # Test passes with queued response
                return
            
            # Verify cardiology-specific improvements
            improved_text = data["improved"]
            assert "participants with heart failure" in improved_text
            assert "AHA/ACC" in improved_text
            
            # Verify cardiology sources
            sources = data["sources"]
            assert any("AHA/ACC" in source for source in sources)
    
    def test_generate_rewrite_ta_error_handling(self):
        """Test error handling when external services fail"""
        
        with patch('main.query_vector_db') as mock_vector_db, \
             patch('main.generate_ta_aware_rewrite') as mock_azure:
            
            # Simulate vector DB failure
            mock_vector_db.side_effect = Exception("Vector DB connection failed")
            
            payload = {
                "text": "Test text for error handling",
                "ta": "oncology",
                "context": "clinical_trial",
                "suggestion_id": "error_test_001"
            }
            
            response = requests.post(
                "http://127.0.0.1:8000/api/generate-rewrite-ta",
                json=payload,
                timeout=10
            )
            
            # Should still return a response, possibly with fallback behavior
            assert response.status_code in [200, 202, 500, 502]
            
            if response.status_code == 202:
                data = response.json()
                assert "status" in data
                assert data["status"] == "queued"
                return
                
            if response.status_code == 200:
                data = response.json()
                # Should have basic response structure even on error
                assert "suggestion_id" in data
                assert "improved" in data or "error" in data
    
    def test_generate_rewrite_ta_empty_exemplars(self):
        """Test behavior when vector DB returns no exemplars"""
        
        with patch('main.query_vector_db') as mock_vector_db, \
             patch('main.generate_ta_aware_rewrite') as mock_azure, \
             patch('main.get_regulatory_guidelines') as mock_guidelines:
            
            # Return empty exemplars
            mock_vector_db.return_value = []
            
            # Azure should still generate improvement
            mock_azure.return_value = {
                "improved": "Enhanced text with regulatory improvements",
                "rationale": "General regulatory enhancement without specific exemplars",
                "sources": ["General regulatory guidelines"],
                "model_version": "azure-openai-fallback-v1.0"
            }
            
            mock_guidelines.return_value = ["General regulatory guideline"]
            
            payload = {
                "text": "Sample text without matching exemplars",
                "ta": "rare_disease",
                "context": "clinical_trial", 
                "suggestion_id": "no_exemplars_001"
            }
            
            response = requests.post(
                "http://127.0.0.1:8000/api/generate-rewrite-ta",
                json=payload,
                timeout=10
            )
            
            data, is_queued = self._handle_ta_response(response, "no_exemplars_001")
            
            if is_queued:
                # Test passes with queued response
                return
            
            assert "improved" in data
            assert data["improved"] == "Enhanced text with regulatory improvements"
    
    def test_generate_rewrite_ta_metadata_tracking(self):
        """Test that metadata is properly tracked and returned"""
        
        with patch('main.query_vector_db') as mock_vector_db, \
             patch('main.generate_ta_aware_rewrite') as mock_azure, \
             patch('main.get_regulatory_guidelines') as mock_guidelines:
            
            mock_vector_db.return_value = self._create_mock_vector_db_response()
            
            azure_response = self._create_mock_azure_response()
            mock_azure.return_value = azure_response
            
            mock_guidelines.return_value = self._create_mock_regulatory_guidelines()
            
            payload = {
                "text": "Detailed text for metadata tracking testing",
                "ta": "oncology",
                "context": "phase_3_trial",
                "suggestion_id": "metadata_test_001"
            }
            
            response = requests.post(
                "http://127.0.0.1:8000/api/generate-rewrite-ta",
                json=payload,
                timeout=15
            )
            
            data, is_queued = self._handle_ta_response(response, "metadata_test_001")
            
            if is_queued:
                # Test passes with queued response
                return
            
            # Verify metadata fields
            assert "latency_ms" in data
            assert isinstance(data["latency_ms"], (int, float))
            assert data["latency_ms"] > 0
            
            assert "ta_info" in data
            ta_info = data["ta_info"]
            assert ta_info["therapeutic_area"] == "oncology"
            assert "exemplars_used" in ta_info
            assert "guidelines_applied" in ta_info
            
            # Verify processing metadata
            assert "metadata" in data
            metadata = data["metadata"]
            assert "model_path" in metadata
            assert metadata["model_path"] == "ta_on_demand"
    
    def test_generate_rewrite_ta_invalid_payload(self):
        """Test validation of invalid request payloads"""
        
        # Missing required fields
        invalid_payloads = [
            {"text": ""},  # Empty text
            {"ta": "oncology"},  # Missing text
            {"text": "sample", "ta": ""},  # Empty TA
            {"text": "sample", "ta": "oncology"},  # Missing suggestion_id
        ]
        
        for payload in invalid_payloads:
            response = requests.post(
                "http://127.0.0.1:8000/api/generate-rewrite-ta",
                json=payload,
                timeout=5
            )
            
            assert response.status_code in [400, 422]  # Bad request or validation error
    
    def test_generate_rewrite_ta_long_text_handling(self):
        """Test handling of very long input text"""
        
        with patch('main.query_vector_db') as mock_vector_db, \
             patch('main.generate_ta_aware_rewrite') as mock_azure, \
             patch('main.get_regulatory_guidelines') as mock_guidelines:
            
            mock_vector_db.return_value = self._create_mock_vector_db_response()
            
            # Mock response for long text
            mock_azure.return_value = {
                "improved": "Comprehensive regulatory-compliant rewrite of the extended clinical protocol text...",
                "rationale": "Extensive improvements made to ensure regulatory compliance across all sections",
                "sources": ["Multiple regulatory sources"],
                "model_version": "azure-openai-extended-context-v1.0"
            }
            
            mock_guidelines.return_value = self._create_mock_regulatory_guidelines()
            
            # Create very long text
            long_text = "Clinical trial protocol section. " * 200
            
            payload = {
                "text": long_text,
                "ta": "oncology",
                "context": "protocol_document",
                "suggestion_id": "long_text_001"
            }
            
            response = requests.post(
                "http://127.0.0.1:8000/api/generate-rewrite-ta",
                json=payload,
                timeout=30  # Longer timeout for long text
            )
            
            # May get 422 for very long text or 202 for queued
            assert response.status_code in [200, 202, 422]
            
            if response.status_code == 422:
                # Text may be too long, this is acceptable
                return
                
            data, is_queued = self._handle_ta_response(response, "long_text_001")
            
            if is_queued:
                # Test passes with queued response
                return
            
            assert "improved" in data
            assert len(data["improved"]) > 0
            
            # Should handle long text gracefully
            assert "latency_ms" in data
            # May take longer but should complete
            assert data["latency_ms"] < 30000  # Less than 30 seconds


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])