"""
Integration test for async document optimization flow
Tests /api/optimize-document-async, job polling, and SSE streaming
"""

import pytest
import requests
import time
import subprocess
import os
import json
import sseclient
from typing import Dict, Any, Generator
import threading
from pathlib import Path

class TestOptimizeDocumentAsyncFlow:
    """Integration tests for async document optimization workflow"""
    
    @classmethod
    def setup_class(cls):
        """Start test server before running tests"""
        cls.server_process = subprocess.Popen(
            ["python3", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8002"],
            env={**os.environ, "ANALYSIS_MODE": "hybrid"},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for server to start
        cls._wait_for_server("http://127.0.0.1:8002/health", timeout=15)
        
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
    
    def _poll_job_status(self, job_id: str, timeout: int = 30) -> Dict[str, Any]:
        """Poll job status until completion or timeout"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            response = requests.get(f"http://127.0.0.1:8002/api/job-status/{job_id}")
            assert response.status_code == 200
            
            status_data = response.json()
            job_status = status_data.get("status")
            
            if job_status in ["completed", "failed", "error"]:
                return status_data
            
            time.sleep(1)
        
        raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds")
    
    def _read_job_events_log(self, job_id: str) -> Generator[Dict[str, Any], None, None]:
        """Read events from job log file"""
        log_path = Path(f"jobs/{job_id}/events.log")
        
        if not log_path.exists():
            return
        
        with open(log_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
    
    def _stream_job_events_sse(self, job_id: str, timeout: int = 30) -> Generator[Dict[str, Any], None, None]:
        """Stream events via SSE endpoint"""
        try:
            response = requests.get(
                f"http://127.0.0.1:8002/api/stream-job/{job_id}/events",
                stream=True,
                timeout=timeout,
                headers={'Accept': 'text/event-stream'}
            )
            
            if response.status_code != 200:
                return
            
            client = sseclient.SSEClient(response)
            
            for event in client.events():
                if event.data:
                    try:
                        yield json.loads(event.data)
                    except json.JSONDecodeError:
                        continue
                        
        except requests.exceptions.RequestException:
            # Fallback to log file reading if SSE fails
            yield from self._read_job_events_log(job_id)
    
    def test_async_document_optimization_complete_flow(self):
        """Test complete async document optimization workflow"""
        # Step 1: Start async document optimization
        document_text = """
        Patients enrolled in the clinical study showed positive response to treatment.
        Adverse events were monitored throughout the trial period.
        The study protocol followed ICH guidelines for good clinical practice.
        Data was collected and analyzed according to regulatory requirements.
        """
        
        payload = {
            "text": document_text.strip(),
            "mode": "document_chunked",
            "therapeutic_area": "oncology",
            "async_processing": True
        }
        
        response = requests.post(
            "http://127.0.0.1:8002/api/optimize-document-async",
            json=payload,
            timeout=10
        )
        
        assert response.status_code == 202  # Accepted for async processing
        data = response.json()
        
        # Assert initial response structure
        assert "job_id" in data
        assert "status" in data
        assert data["status"] == "queued"
        assert "estimated_completion" in data
        
        job_id = data["job_id"]
        
        # Step 2: Poll job status until completion
        final_status = self._poll_job_status(job_id, timeout=60)
        
        assert final_status["status"] == "completed"
        assert "result" in final_status
        assert "progress" in final_status
        assert final_status["progress"] == 100
        
        # Step 3: Verify job result contains suggestions
        result = final_status["result"]
        assert "suggestions" in result
        assert "metadata" in result
        
        suggestions = result["suggestions"]
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0
        
        # Verify suggestion structure
        for suggestion in suggestions:
            assert "id" in suggestion
            assert "type" in suggestion
            assert "text" in suggestion
            assert "suggestion" in suggestion
            assert "rationale" in suggestion
    
    def test_async_document_sse_event_streaming(self):
        """Test SSE event streaming during async processing"""
        payload = {
            "text": "Patient data analysis for regulatory submission requirements.",
            "mode": "document_chunked",
            "async_processing": True
        }
        
        # Start async job
        response = requests.post(
            "http://127.0.0.1:8002/api/optimize-document-async",
            json=payload,
            timeout=10
        )
        
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        
        # Stream events via SSE
        events_received = []
        
        def collect_events():
            for event in self._stream_job_events_sse(job_id, timeout=30):
                events_received.append(event)
                if event.get("type") == "completed":
                    break
        
        # Start event collection in background thread
        event_thread = threading.Thread(target=collect_events)
        event_thread.start()
        
        # Wait for completion
        event_thread.join(timeout=35)
        
        # Verify events were received
        assert len(events_received) > 0
        
        # Check for expected event types
        event_types = [event.get("type") for event in events_received]
        assert "started" in event_types
        assert "progress" in event_types or "chunk_processed" in event_types
        assert "completed" in event_types or "finished" in event_types
        
        # Verify progress events
        progress_events = [e for e in events_received if e.get("type") == "progress"]
        if progress_events:
            for event in progress_events:
                assert "progress" in event
                assert 0 <= event["progress"] <= 100
    
    def test_async_document_job_events_log_file(self):
        """Test job events are written to log file"""
        payload = {
            "text": "Clinical trial participants showed improvement in primary endpoints.",
            "mode": "document_chunked",
            "async_processing": True
        }
        
        # Start async job
        response = requests.post(
            "http://127.0.0.1:8002/api/optimize-document-async",
            json=payload,
            timeout=10
        )
        
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        
        # Wait for job completion
        final_status = self._poll_job_status(job_id, timeout=30)
        assert final_status["status"] == "completed"
        
        # Read events from log file
        events_from_log = list(self._read_job_events_log(job_id))
        
        assert len(events_from_log) > 0
        
        # Verify log structure
        for event in events_from_log:
            assert "timestamp" in event
            assert "type" in event
            assert "job_id" in event
            assert event["job_id"] == job_id
    
    def test_async_document_large_text_chunking(self):
        """Test async processing with large text requiring chunking"""
        # Create large document text
        large_text = """
        Clinical study protocol for oncology research participants.
        Participants enrolled in the multi-center trial showed significant improvement.
        Adverse events were carefully monitored and reported according to regulatory guidelines.
        The primary endpoint was progression-free survival as measured by RECIST criteria.
        Secondary endpoints included overall response rate and quality of life assessments.
        Safety data was collected throughout the treatment period.
        Statistical analysis was performed using appropriate methodologies.
        Results demonstrated efficacy and acceptable safety profile.
        Regulatory submissions will include comprehensive data packages.
        """ * 20  # Make it large enough to require chunking
        
        payload = {
            "text": large_text.strip(),
            "mode": "document_chunked",
            "async_processing": True,
            "chunk_size": 500  # Force smaller chunks
        }
        
        response = requests.post(
            "http://127.0.0.1:8002/api/optimize-document-async",
            json=payload,
            timeout=10
        )
        
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        
        # Poll with longer timeout for large document
        final_status = self._poll_job_status(job_id, timeout=90)
        
        assert final_status["status"] == "completed"
        result = final_status["result"]
        
        # Should have processed multiple chunks
        metadata = result.get("metadata", {})
        if "chunks_processed" in metadata:
            assert metadata["chunks_processed"] > 1
        
        # Should have suggestions from multiple chunks
        suggestions = result["suggestions"]
        assert len(suggestions) > 0
    
    def test_async_document_job_cancellation(self):
        """Test job cancellation functionality"""
        payload = {
            "text": "Long running document analysis task for testing cancellation.",
            "mode": "document_chunked",
            "async_processing": True
        }
        
        # Start async job
        response = requests.post(
            "http://127.0.0.1:8002/api/optimize-document-async",
            json=payload,
            timeout=10
        )
        
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        
        # Wait a moment for job to start
        time.sleep(2)
        
        # Cancel the job
        cancel_response = requests.post(f"http://127.0.0.1:8002/api/job/{job_id}/cancel")
        
        if cancel_response.status_code == 200:
            # Wait for cancellation to take effect
            time.sleep(2)
            
            # Check final status
            status_response = requests.get(f"http://127.0.0.1:8002/api/job-status/{job_id}")
            assert status_response.status_code == 200
            
            status_data = status_response.json()
            assert status_data["status"] in ["cancelled", "failed", "completed"]
    
    def test_async_document_invalid_job_id(self):
        """Test job status polling with invalid job ID"""
        invalid_job_id = "invalid-job-id-12345"
        
        response = requests.get(f"http://127.0.0.1:8002/api/job-status/{invalid_job_id}")
        assert response.status_code == 404
        
        data = response.json()
        assert "error" in data or "detail" in data
    
    def test_async_document_sse_invalid_job_id(self):
        """Test SSE streaming with invalid job ID"""
        invalid_job_id = "invalid-job-id-12345"
        
        response = requests.get(
            f"http://127.0.0.1:8002/api/stream-job/{invalid_job_id}/events",
            timeout=5
        )
        
        assert response.status_code == 404
    
    def test_async_document_progress_tracking(self):
        """Test detailed progress tracking during async processing"""
        payload = {
            "text": "Comprehensive clinical trial analysis with multiple endpoints and safety assessments.",
            "mode": "document_chunked",
            "async_processing": True
        }
        
        response = requests.post(
            "http://127.0.0.1:8002/api/optimize-document-async",
            json=payload,
            timeout=10
        )
        
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        
        # Monitor progress during execution
        progress_values = []
        start_time = time.time()
        
        while time.time() - start_time < 30:
            status_response = requests.get(f"http://127.0.0.1:8002/api/job-status/{job_id}")
            assert status_response.status_code == 200
            
            status_data = status_response.json()
            progress = status_data.get("progress", 0)
            progress_values.append(progress)
            
            if status_data["status"] in ["completed", "failed"]:
                break
                
            time.sleep(1)
        
        # Progress should increase over time
        assert len(progress_values) > 0
        assert max(progress_values) > 0
        assert progress_values[-1] in [100, progress_values[-2]]  # Should reach 100 or stay stable


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])