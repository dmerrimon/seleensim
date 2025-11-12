"""
Comprehensive test suite for TA Shadow Worker
Tests shadow file creation, admin API endpoints, and integration
"""

import pytest
import json
import os
import time
import asyncio
from pathlib import Path
from unittest.mock import patch, Mock, AsyncMock
from fastapi.testclient import TestClient
import tempfile
import shutil

# Import the FastAPI app and shadow worker
from main import app
from ta_shadow_worker import TAShadowWorker, submit_shadow_request

client = TestClient(app)

class TestTAShadowWorker:
    """Test suite for TA Shadow Worker functionality"""
    
    def setup_method(self):
        """Set up test fixtures and temporary directory"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_shadow_dir = self.temp_dir / "shadow"
        self.test_shadow_dir.mkdir(exist_ok=True)
        
        # Create test shadow worker with custom directory
        self.shadow_worker = TAShadowWorker()
        self.shadow_worker.shadow_dir = self.test_shadow_dir
        
        # Mock payload and response
        self.mock_request_payload = {
            "text": "Patients showed good response to treatment.",
            "mode": "selection",
            "ta": "oncology"
        }
        
        self.mock_simple_output = {
            "suggestions": [
                {
                    "id": "simple_001",
                    "type": "medical_terminology",
                    "text": "patients",
                    "suggestion": "participants", 
                    "rationale": "Use participants per ICH-GCP",
                    "confidence": 0.9
                }
            ],
            "metadata": {
                "model_path": "simple",
                "latency_ms": 150
            }
        }
        
        self.mock_ta_output = {
            "ta_classification": {
                "therapeutic_area": "oncology",
                "confidence": 0.95,
                "detected_keywords": ["patients", "treatment"]
            },
            "exemplars_found": 2,
            "guidelines_applied": 3,
            "rewrite": {
                "improved": "Study participants demonstrated favorable response to investigational treatment.",
                "rationale": "Enhanced for regulatory compliance",
                "sources": ["ICH-GCP", "FDA Guidance"],
                "model_version": "azure-openai-oncology-aware"
            },
            "suggestions": [
                {
                    "id": "ta_enhanced_001",
                    "type": "ta_enhanced",
                    "original_text": "Patients showed good response to treatment.",
                    "improved_text": "Study participants demonstrated favorable response to investigational treatment.",
                    "confidence": 0.95,
                    "therapeutic_area": "oncology"
                }
            ]
        }
    
    def teardown_method(self):
        """Clean up test directory"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_shadow_worker_initialization(self):
        """Test shadow worker initializes correctly"""
        worker = TAShadowWorker()
        
        assert worker.shadow_dir.exists()
        assert worker.max_per_minute > 0
        assert hasattr(worker, 'executor')
        assert hasattr(worker, 'shadow_requests')
        assert hasattr(worker, 'shadow_lock')
    
    def test_shadow_rate_limiting(self):
        """Test shadow worker rate limiting"""
        # Set low rate limit for testing
        self.shadow_worker.max_per_minute = 2
        
        # First request should pass
        assert self.shadow_worker.check_shadow_rate_limit() == True
        
        # Second request should pass
        assert self.shadow_worker.check_shadow_rate_limit() == True
        
        # Third request should fail
        assert self.shadow_worker.check_shadow_rate_limit() == False
    
    @patch('ta_shadow_worker.fast_ta_classifier')
    @patch('ta_shadow_worker.query_vector_db')
    @patch('ta_shadow_worker.get_regulatory_guidelines')
    @patch('ta_shadow_worker.generate_ta_aware_rewrite')
    def test_shadow_processing_sync(self, mock_generate, mock_guidelines, mock_vector_db, mock_classifier):
        """Test synchronous shadow processing"""
        # Configure mocks
        mock_classifier.return_value = self.mock_ta_output["ta_classification"]
        mock_vector_db.return_value = [{"text": "example", "improved": "enhanced example"}] * 2
        mock_guidelines.return_value = ["Guideline 1", "Guideline 2", "Guideline 3"]
        mock_generate.return_value = self.mock_ta_output["rewrite"]
        
        # Run shadow processing
        request_id = "test_shadow_001"
        self.shadow_worker._process_shadow_sync(
            request_id, 
            self.mock_request_payload, 
            self.mock_simple_output
        )
        
        # Check shadow file was created
        shadow_file = self.test_shadow_dir / f"{request_id}.json"
        assert shadow_file.exists()
        
        # Read and validate shadow result
        with open(shadow_file, 'r') as f:
            shadow_result = json.load(f)
        
        assert shadow_result["request_id"] == request_id
        assert "simple_output" in shadow_result
        assert "ta_output" in shadow_result
        assert "similarity_score" in shadow_result
        assert "latency_ms" in shadow_result
        assert "timestamp" in shadow_result
        assert "request_metadata" in shadow_result
        
        # Validate structure
        assert isinstance(shadow_result["similarity_score"], float)
        assert isinstance(shadow_result["latency_ms"], int)
        assert shadow_result["latency_ms"] > 0
    
    def test_shadow_similarity_calculation(self):
        """Test similarity score calculation between simple and TA outputs"""
        similarity = self.shadow_worker._calculate_similarity(
            self.mock_simple_output,
            self.mock_ta_output
        )
        
        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0
    
    def test_shadow_similarity_empty_inputs(self):
        """Test similarity calculation with empty inputs"""
        empty_output = {"suggestions": []}
        
        similarity = self.shadow_worker._calculate_similarity(empty_output, empty_output)
        assert similarity == 0.0
    
    def test_shadow_file_saving(self):
        """Test shadow result file saving"""
        test_result = {
            "request_id": "test_save_001",
            "simple_output": self.mock_simple_output,
            "ta_output": self.mock_ta_output,
            "similarity_score": 0.75,
            "latency_ms": 1500,
            "timestamp": "2025-01-01T12:00:00Z"
        }
        
        self.shadow_worker._save_shadow_result("test_save_001", test_result)
        
        # Verify file exists and contains correct data
        shadow_file = self.test_shadow_dir / "test_save_001.json"
        assert shadow_file.exists()
        
        with open(shadow_file, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data == test_result
    
    def test_shadow_error_handling(self):
        """Test shadow processing error handling"""
        # Create request with empty text to trigger error
        bad_payload = {"text": "", "mode": "selection"}
        
        self.shadow_worker._process_shadow_sync(
            "test_error_001", 
            bad_payload, 
            self.mock_simple_output
        )
        
        # Should still create a file (but may be empty due to early return)
        # The main test is that it doesn't crash
    
    def test_get_shadow_samples_empty(self):
        """Test getting shadow samples from empty directory"""
        samples = self.shadow_worker.get_shadow_samples(10)
        assert isinstance(samples, list)
        assert len(samples) == 0
    
    def test_get_shadow_samples_with_data(self):
        """Test getting shadow samples with existing data"""
        # Create test shadow files
        for i in range(3):
            test_result = {
                "request_id": f"test_sample_{i:03d}",
                "simple_output": self.mock_simple_output,
                "ta_output": self.mock_ta_output,
                "similarity_score": 0.8 + (i * 0.05),
                "latency_ms": 1000 + (i * 100),
                "timestamp": f"2025-01-01T12:{i:02d}:00Z"
            }
            
            shadow_file = self.test_shadow_dir / f"test_sample_{i:03d}.json"
            with open(shadow_file, 'w') as f:
                json.dump(test_result, f, indent=2)
        
        # Get samples
        samples = self.shadow_worker.get_shadow_samples(2)
        
        assert len(samples) == 2
        assert all("request_id" in sample for sample in samples)
        assert all("file_size" in sample for sample in samples)
        assert all("file_modified" in sample for sample in samples)
    
    def test_get_shadow_stats_empty(self):
        """Test getting shadow stats from empty directory"""
        stats = self.shadow_worker.get_shadow_stats()
        
        assert stats["total_samples"] == 0
        assert stats["avg_similarity"] == 0.0
        assert stats["avg_latency_ms"] == 0
        assert stats["error_count"] == 0
        assert stats["success_rate"] == 0.0
    
    def test_get_shadow_stats_with_data(self):
        """Test getting shadow stats with existing data"""
        # Create test shadow files with different similarity scores
        test_similarities = [0.7, 0.8, 0.9]
        test_latencies = [1000, 1500, 2000]
        
        for i, (sim, lat) in enumerate(zip(test_similarities, test_latencies)):
            test_result = {
                "request_id": f"test_stats_{i:03d}",
                "similarity_score": sim,
                "latency_ms": lat,
                "timestamp": f"2025-01-01T12:{i:02d}:00Z",
                "error": False
            }
            
            shadow_file = self.test_shadow_dir / f"test_stats_{i:03d}.json"
            with open(shadow_file, 'w') as f:
                json.dump(test_result, f, indent=2)
        
        # Get stats
        stats = self.shadow_worker.get_shadow_stats()
        
        assert stats["total_samples"] == 3
        assert stats["avg_similarity"] == round(sum(test_similarities) / len(test_similarities), 3)
        assert stats["avg_latency_ms"] == int(sum(test_latencies) / len(test_latencies))
        assert stats["error_count"] == 0
        assert stats["success_rate"] == 100.0
    
    @pytest.mark.asyncio
    async def test_submit_shadow_request_function(self):
        """Test the async submit_shadow_request function"""
        with patch('ta_shadow_worker.shadow_worker') as mock_worker:
            mock_worker.process_shadow_request = AsyncMock()
            
            await submit_shadow_request(self.mock_request_payload, self.mock_simple_output)
            
            mock_worker.process_shadow_request.assert_called_once_with(
                self.mock_request_payload, 
                self.mock_simple_output
            )

class TestShadowAdminAPI:
    """Test suite for Shadow Worker Admin API endpoints"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.valid_auth_header = "Bearer admin_test_token_123456789"
        self.invalid_auth_header = "Bearer short"
        
    def test_shadow_samples_endpoint_no_auth(self):
        """Test shadow samples endpoint without authorization"""
        response = client.get("/api/shadow-samples")
        
        assert response.status_code == 401
        data = response.json()
        assert "Authorization header required" in data["error"]
    
    def test_shadow_samples_endpoint_invalid_auth(self):
        """Test shadow samples endpoint with invalid authorization"""
        response = client.get(
            "/api/shadow-samples",
            headers={"Authorization": self.invalid_auth_header}
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "Invalid authorization token" in data["error"]
    
    def test_shadow_samples_endpoint_valid_auth(self):
        """Test shadow samples endpoint with valid authorization"""
        with patch('main.get_shadow_samples') as mock_get_samples:
            mock_get_samples.return_value = [
                {
                    "request_id": "admin_test_001",
                    "similarity_score": 0.85,
                    "latency_ms": 1200,
                    "timestamp": "2025-01-01T12:00:00Z"
                }
            ]
            
            response = client.get(
                "/api/shadow-samples?limit=10",
                headers={"Authorization": self.valid_auth_header}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert "samples" in data
            assert "count" in data
            assert "limit" in data
            assert "timestamp" in data
            assert "admin_endpoint" in data
            
            assert data["admin_endpoint"] == True
            assert data["count"] == 1
            assert data["limit"] == 10
            assert len(data["samples"]) == 1
            
            mock_get_samples.assert_called_once_with(10)
    
    def test_shadow_samples_endpoint_custom_limit(self):
        """Test shadow samples endpoint with custom limit"""
        with patch('main.get_shadow_samples') as mock_get_samples:
            mock_get_samples.return_value = []
            
            response = client.get(
                "/api/shadow-samples?limit=25",
                headers={"Authorization": self.valid_auth_header}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["limit"] == 25
            
            mock_get_samples.assert_called_once_with(25)
    
    def test_shadow_samples_endpoint_invalid_limit(self):
        """Test shadow samples endpoint with invalid limit values"""
        # Test limit too low
        response = client.get(
            "/api/shadow-samples?limit=0",
            headers={"Authorization": self.valid_auth_header}
        )
        assert response.status_code == 422
        
        # Test limit too high
        response = client.get(
            "/api/shadow-samples?limit=500",
            headers={"Authorization": self.valid_auth_header}
        )
        assert response.status_code == 422
    
    def test_shadow_stats_endpoint_no_auth(self):
        """Test shadow stats endpoint without authorization"""
        response = client.get("/api/shadow-stats")
        
        assert response.status_code == 401
        data = response.json()
        assert "Authorization header required" in data["error"]
    
    def test_shadow_stats_endpoint_valid_auth(self):
        """Test shadow stats endpoint with valid authorization"""
        with patch('main.get_shadow_stats') as mock_get_stats:
            mock_get_stats.return_value = {
                "total_samples": 42,
                "avg_similarity": 0.825,
                "avg_latency_ms": 1350,
                "error_count": 2,
                "success_rate": 95.2,
                "rate_limit": "15/30/min"
            }
            
            response = client.get(
                "/api/shadow-stats",
                headers={"Authorization": self.valid_auth_header}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert "stats" in data
            assert "timestamp" in data
            assert "admin_endpoint" in data
            
            assert data["admin_endpoint"] == True
            stats = data["stats"]
            
            assert stats["total_samples"] == 42
            assert stats["avg_similarity"] == 0.825
            assert stats["avg_latency_ms"] == 1350
            assert stats["error_count"] == 2
            assert stats["success_rate"] == 95.2
            
            mock_get_stats.assert_called_once()
    
    def test_shadow_samples_endpoint_error_handling(self):
        """Test shadow samples endpoint error handling"""
        with patch('main.get_shadow_samples') as mock_get_samples:
            mock_get_samples.side_effect = Exception("Database connection failed")
            
            response = client.get(
                "/api/shadow-samples",
                headers={"Authorization": self.valid_auth_header}
            )
            
            assert response.status_code == 500
            data = response.json()
            assert "Failed to fetch shadow samples" in data["error"]
    
    def test_shadow_stats_endpoint_error_handling(self):
        """Test shadow stats endpoint error handling"""
        with patch('main.get_shadow_stats') as mock_get_stats:
            mock_get_stats.side_effect = Exception("File system error")
            
            response = client.get(
                "/api/shadow-stats",
                headers={"Authorization": self.valid_auth_header}
            )
            
            assert response.status_code == 500
            data = response.json()
            assert "Failed to fetch shadow stats" in data["error"]

class TestShadowIntegration:
    """Test suite for Shadow Worker integration with main analysis pipeline"""
    
    def test_shadow_directory_creation(self):
        """Test that shadow directory is created on import"""
        shadow_dir = Path("shadow")
        # The directory should be created when ta_shadow_worker is imported
        assert shadow_dir.exists()
    
    def test_environment_variable_configuration(self):
        """Test shadow worker respects environment variables"""
        # Test default value
        worker = TAShadowWorker()
        assert worker.max_per_minute > 0
        
        # Test custom environment value
        with patch.dict(os.environ, {"SHADOW_MAX_PER_MIN": "100"}):
            worker_custom = TAShadowWorker()
            assert worker_custom.max_per_minute == 100
    
    @pytest.mark.asyncio
    async def test_shadow_integration_does_not_affect_response(self):
        """Test that shadow worker doesn't affect main API responses"""
        # Mock the shadow worker to ensure it doesn't interfere
        with patch('main.submit_shadow_request') as mock_shadow:
            mock_shadow.return_value = asyncio.sleep(0)  # Quick async operation
            
            # Make a regular API call  
            response = client.post(
                "/api/analyze",
                json={
                    "text": "Testing shadow integration",
                    "mode": "selection"
                }
            )
            
            # Response should be successful regardless of shadow worker
            assert response.status_code in [200, 502]  # 502 if service unavailable
            
            # Shadow worker should have been called if response was successful
            if response.status_code == 200:
                mock_shadow.assert_called()

if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])