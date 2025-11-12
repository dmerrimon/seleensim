"""
Comprehensive test suite for the /api/generate-rewrite-ta endpoint
Tests TA-Enhanced rewriting functionality with mocked dependencies
"""

import pytest
import json
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import HTTPException
import time

# Import the FastAPI app
from main import app

client = TestClient(app)

class TestGenerateRewriteTA:
    """Test suite for TA-Enhanced rewrite endpoint"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_azure_response = {
            "improved": "Study participants demonstrated improved clinical outcomes following the investigational treatment regimen.",
            "rationale": "Enhanced for ICH-GCP compliance with participant-focused terminology and clearer clinical outcome description.",
            "sources": [
                "ICH-GCP Guidelines Section 4.2.1",
                "FDA Clinical Trial Terminology Guidance"
            ],
            "model_version": "gpt-4",
            "latency_ms": 1250
        }
        
        self.mock_vector_exemplars = [
            {
                "text_snippet": "participants showed significant improvement",
                "ta": "oncology",
                "phase": "phase_3",
                "score": 0.92
            },
            {
                "text_snippet": "clinical outcomes were measured using validated instruments",
                "ta": "oncology", 
                "phase": "phase_3",
                "score": 0.88
            }
        ]
        
        self.mock_regulatory_guidelines = [
            "Use 'participants' instead of 'patients' per ICH-GCP requirements",
            "Ensure outcome measures are clearly defined and validated"
        ]
    
    def test_generate_rewrite_ta_success_with_ta_provided(self):
        """Test successful TA rewrite with TA classification provided"""
        payload = {
            "suggestion_id": "test_123",
            "text": "Patients showed good response to treatment.",
            "ta": "oncology",
            "phase": "phase_3",
            "doc_id": "doc_456"
        }
        
        with patch('main.query_vector_db') as mock_vector_db, \
             patch('main.get_regulatory_guidelines') as mock_regulatory, \
             patch('main.generate_ta_aware_rewrite') as mock_azure:
            
            # Configure mocks
            mock_vector_db.return_value = self.mock_vector_exemplars
            mock_regulatory.return_value = self.mock_regulatory_guidelines
            mock_azure.return_value = self.mock_azure_response
            
            response = client.post("/api/generate-rewrite-ta", json=payload)
            
            # Assertions
            assert response.status_code == 200
            data = response.json()
            
            # Check response structure
            assert "improved" in data
            assert "rationale" in data
            assert "sources" in data
            assert "model_version" in data
            assert "latency_ms" in data
            assert "ta_info" in data
            assert "metadata" in data
            
            # Check specific values
            assert data["improved"] == self.mock_azure_response["improved"]
            assert data["ta_info"]["therapeutic_area"] == "oncology"
            assert data["ta_info"]["exemplars_used"] == 2
            assert isinstance(data["latency_ms"], (int, float))
            
            # Verify mock calls
            mock_vector_db.assert_called_once_with(payload["text"], "oncology", "phase_3")
            mock_regulatory.assert_called_once_with("oncology")
            mock_azure.assert_called_once()

    def test_generate_rewrite_ta_success_without_ta_classification(self):
        """Test successful TA rewrite with automatic TA classification"""
        payload = {
            "suggestion_id": "test_456", 
            "text": "The medication showed efficacy in treating the condition.",
            "doc_id": "doc_789"
        }
        
        with patch('main.fast_ta_classifier') as mock_classify, \
             patch('main.query_vector_db') as mock_vector_db, \
             patch('main.get_regulatory_guidelines') as mock_regulatory, \
             patch('main.generate_ta_aware_rewrite') as mock_azure:
            
            # Configure mocks
            mock_classify.return_value = {"therapeutic_area": "cardiology", "confidence": 0.9, "detected_keywords": ["medication", "condition"]}
            mock_vector_db.return_value = self.mock_vector_exemplars
            mock_regulatory.return_value = self.mock_regulatory_guidelines
            mock_azure.return_value = self.mock_azure_response
            
            response = client.post("/api/generate-rewrite-ta", json=payload)
            
            # Assertions
            assert response.status_code == 200
            data = response.json()
            
            assert data["ta_info"]["therapeutic_area"] == "cardiology"
            
            # Verify TA classification was called
            mock_classify.assert_called_once_with(payload["text"])
            mock_vector_db.assert_called_once_with(payload["text"], "cardiology", None)

    def test_generate_rewrite_ta_vector_db_unavailable(self):
        """Test behavior when vector DB is unavailable (graceful degradation)"""
        payload = {
            "suggestion_id": "test_789",
            "text": "Treatment was effective for most patients.",
            "ta": "neurology"
        }
        
        with patch('main.query_vector_db') as mock_vector_db, \
             patch('main.get_regulatory_guidelines') as mock_regulatory, \
             patch('main.generate_ta_aware_rewrite') as mock_azure:
            
            # Simulate vector DB unavailable
            mock_vector_db.side_effect = Exception("Vector DB connection failed")
            mock_regulatory.return_value = self.mock_regulatory_guidelines
            mock_azure.return_value = self.mock_azure_response
            
            response = client.post("/api/generate-rewrite-ta", json=payload)
            
            # Should still succeed with empty exemplars
            assert response.status_code == 200
            data = response.json()
            assert data["ta_info"]["exemplars_used"] == 0
            
            # Azure should still be called
            mock_azure.assert_called_once()

    def test_generate_rewrite_ta_azure_openai_failure(self):
        """Test behavior when Azure OpenAI is unavailable"""
        payload = {
            "suggestion_id": "test_101112",
            "text": "The study results were positive.",
            "ta": "infectious_disease"
        }
        
        with patch('main.query_vector_db') as mock_vector_db, \
             patch('main.get_regulatory_guidelines') as mock_regulatory, \
             patch('main.generate_ta_aware_rewrite') as mock_azure:
            
            mock_vector_db.return_value = self.mock_vector_exemplars
            mock_regulatory.return_value = self.mock_regulatory_guidelines
            
            # Simulate Azure OpenAI failure
            mock_azure.side_effect = Exception("Azure OpenAI service unavailable")
            
            response = client.post("/api/generate-rewrite-ta", json=payload)
            
            # Should return 500 error
            assert response.status_code == 500
            data = response.json()
            assert "error" in data
            error_details = data["error"]
            assert "message" in error_details
            assert "Azure OpenAI service unavailable" in error_details["message"]

    def test_generate_rewrite_ta_rate_limiting(self):
        """Test rate limiting behavior"""
        payload = {
            "suggestion_id": "rate_test_123",
            "text": "Testing rate limits on this endpoint.",
            "ta": "general_medicine"
        }
        
        with patch('main.query_vector_db') as mock_vector_db, \
             patch('main.get_regulatory_guidelines') as mock_regulatory, \
             patch('main.generate_ta_aware_rewrite') as mock_azure:
            
            mock_vector_db.return_value = self.mock_vector_exemplars
            mock_regulatory.return_value = self.mock_regulatory_guidelines
            mock_azure.return_value = self.mock_azure_response
            
            # Make multiple rapid requests to trigger rate limiting
            responses = []
            for i in range(10):
                response = client.post("/api/generate-rewrite-ta", json={
                    **payload,
                    "suggestion_id": f"rate_test_{i}"
                })
                responses.append(response.status_code)
            
            # At least one request should succeed
            assert 200 in responses
            
            # Rate limiting may return 429 for some requests
            rate_limited = [status for status in responses if status == 429]
            print(f"Rate limited requests: {len(rate_limited)}/{len(responses)}")

    def test_generate_rewrite_ta_invalid_payload(self):
        """Test validation of request payload"""
        
        # Missing required fields
        response = client.post("/api/generate-rewrite-ta", json={})
        assert response.status_code == 422
        
        # Invalid suggestion_id type
        response = client.post("/api/generate-rewrite-ta", json={
            "suggestion_id": 123,  # Should be string
            "text": "Valid text"
        })
        assert response.status_code == 422
        
        # Empty text
        response = client.post("/api/generate-rewrite-ta", json={
            "suggestion_id": "test",
            "text": ""
        })
        assert response.status_code == 422

    def test_generate_rewrite_ta_long_text_handling(self):
        """Test handling of very long text input"""
        long_text = "This is a very long clinical trial description. " * 200  # ~9000 chars
        
        payload = {
            "suggestion_id": "long_text_test",
            "text": long_text,
            "ta": "oncology"
        }
        
        with patch('main.query_vector_db') as mock_vector_db, \
             patch('main.get_regulatory_guidelines') as mock_regulatory, \
             patch('main.generate_ta_aware_rewrite') as mock_azure:
            
            mock_vector_db.return_value = self.mock_vector_exemplars
            mock_regulatory.return_value = self.mock_regulatory_guidelines
            mock_azure.return_value = self.mock_azure_response
            
            response = client.post("/api/generate-rewrite-ta", json=payload)
            
            # Should handle long text gracefully
            assert response.status_code == 200
            data = response.json()
            assert "improved" in data

    def test_generate_rewrite_ta_special_characters(self):
        """Test handling of special characters and encoding"""
        payload = {
            "suggestion_id": "special_chars_test",
            "text": "Patients' müller-cells showed 95% efficacy (α=0.05).",
            "ta": "ophthalmology"
        }
        
        with patch('main.query_vector_db') as mock_vector_db, \
             patch('main.get_regulatory_guidelines') as mock_regulatory, \
             patch('main.generate_ta_aware_rewrite') as mock_azure:
            
            mock_vector_db.return_value = self.mock_vector_exemplars
            mock_regulatory.return_value = self.mock_regulatory_guidelines
            mock_azure.return_value = self.mock_azure_response
            
            response = client.post("/api/generate-rewrite-ta", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            assert "improved" in data

    def test_generate_rewrite_ta_concurrent_requests(self):
        """Test concurrent request handling"""
        import threading
        import queue
        
        results = queue.Queue()
        
        def make_request(thread_id):
            payload = {
                "suggestion_id": f"concurrent_test_{thread_id}",
                "text": f"Concurrent test request {thread_id}.",
                "ta": "general_medicine"
            }
            
            with patch('main.query_vector_db') as mock_vector_db, \
                 patch('main.get_regulatory_guidelines') as mock_regulatory, \
                 patch('main.generate_ta_aware_rewrite') as mock_azure:
                
                mock_vector_db.return_value = self.mock_vector_exemplars
                mock_regulatory.return_value = self.mock_regulatory_guidelines
                mock_azure.return_value = self.mock_azure_response
                
                response = client.post("/api/generate-rewrite-ta", json=payload)
                results.put((thread_id, response.status_code))
        
        # Create and start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_request, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        success_count = 0
        while not results.empty():
            thread_id, status_code = results.get()
            if status_code == 200:
                success_count += 1
        
        # Most requests should succeed
        assert success_count >= 3

    @pytest.mark.asyncio
    async def test_async_mock_functions(self):
        """Test the mock helper functions work correctly"""
        
        # Test TA classification mock
        with patch('main.fast_ta_classifier') as mock_classify:
            mock_classify.return_value = {"therapeutic_area": "cardiology", "confidence": 0.8, "detected_keywords": []}
            result = await mock_classify("heart medication study")
            assert result["therapeutic_area"] == "cardiology"
        
        # Test vector DB query mock
        with patch('main.query_vector_db') as mock_vector:
            mock_vector.return_value = self.mock_vector_exemplars
            result = await mock_vector("test text", "oncology", "phase_2")
            assert len(result) == 2
            assert result[0]["ta"] == "oncology"
        
        # Test regulatory guidelines mock
        with patch('main.get_regulatory_guidelines') as mock_regulatory:
            mock_regulatory.return_value = self.mock_regulatory_guidelines
            result = mock_regulatory("cardiology")
            assert len(result) == 2
            assert "ICH-GCP" in result[0]

    def test_generate_rewrite_ta_response_timing(self):
        """Test that response timing is properly recorded"""
        payload = {
            "suggestion_id": "timing_test",
            "text": "Testing response timing measurement.",
            "ta": "dermatology"
        }
        
        with patch('main.query_vector_db') as mock_vector_db, \
             patch('main.get_regulatory_guidelines') as mock_regulatory, \
             patch('main.generate_ta_aware_rewrite') as mock_azure:
            
            # Add artificial delay to Azure call
            def slow_azure_call(*args, **kwargs):
                time.sleep(0.1)  # 100ms delay
                return self.mock_azure_response
            
            mock_vector_db.return_value = self.mock_vector_exemplars
            mock_regulatory.return_value = self.mock_regulatory_guidelines
            mock_azure.side_effect = slow_azure_call
            
            start_time = time.time()
            response = client.post("/api/generate-rewrite-ta", json=payload)
            end_time = time.time()
            
            assert response.status_code == 200
            data = response.json()
            
            # Check latency is recorded
            assert "latency_ms" in data
            assert data["latency_ms"] >= 100  # Should include our artificial delay
            
            # Check total request time
            total_time_ms = (end_time - start_time) * 1000
            assert total_time_ms >= 100

    def test_generate_rewrite_ta_different_phases(self):
        """Test handling of different clinical trial phases"""
        phases = ["phase_1", "phase_2", "phase_3", "phase_4", "general"]
        
        for phase in phases:
            payload = {
                "suggestion_id": f"phase_test_{phase}",
                "text": f"Testing {phase} specific terminology.",
                "ta": "oncology",
                "phase": phase
            }
            
            with patch('main.query_vector_db') as mock_vector_db, \
                 patch('main.get_regulatory_guidelines') as mock_regulatory, \
                 patch('main.generate_ta_aware_rewrite') as mock_azure:
                
                mock_vector_db.return_value = self.mock_vector_exemplars
                mock_regulatory.return_value = self.mock_regulatory_guidelines
                mock_azure.return_value = self.mock_azure_response
                
                response = client.post("/api/generate-rewrite-ta", json=payload)
                
                assert response.status_code == 200, f"Failed for phase: {phase}"
                
                # Verify vector DB was called with correct phase
                mock_vector_db.assert_called_with(payload["text"], "oncology", phase)

    def test_generate_rewrite_ta_telemetry_logging(self):
        """Test that telemetry is properly logged"""
        payload = {
            "suggestion_id": "telemetry_test",
            "text": "Testing telemetry logging functionality.",
            "ta": "psychiatry"
        }
        
        with patch('main.query_vector_db') as mock_vector_db, \
             patch('main.get_regulatory_guidelines') as mock_regulatory, \
             patch('main.generate_ta_aware_rewrite') as mock_azure:
            
            mock_vector_db.return_value = self.mock_vector_exemplars
            mock_regulatory.return_value = self.mock_regulatory_guidelines
            mock_azure.return_value = self.mock_azure_response
            
            response = client.post("/api/generate-rewrite-ta", json=payload)
            
            assert response.status_code == 200
            
            # Verify response contains model_path in metadata
            data = response.json()
            assert "metadata" in data
            assert data["metadata"]["model_path"] == "ta_on_demand"

if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])