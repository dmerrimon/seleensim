"""
Tests for /api/job-status endpoint and JobStore functionality.

Run with: pytest tests/test_job_status.py -v
"""

import json
import pytest
import tempfile
import shutil
from pathlib import Path
from fastapi.testclient import TestClient
import uuid
from datetime import datetime


# Test JobStore class
class TestJobStore:
    """Test suite for JobStore class"""

    @pytest.fixture
    def temp_job_store(self):
        """Create a temporary JobStore for testing"""
        from server.jobs import JobStore

        temp_dir = tempfile.mkdtemp()
        store = JobStore(base_dir=temp_dir)
        yield store
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_jobstore_initialization(self, temp_job_store):
        """Test JobStore initializes correctly"""
        assert temp_job_store.base_dir.exists()
        assert temp_job_store.base_dir.is_dir()

    def test_validate_job_id_valid_uuid(self, temp_job_store):
        """Test UUID validation accepts valid UUIDs"""
        valid_uuid = str(uuid.uuid4())
        assert temp_job_store._validate_job_id(valid_uuid) is True

    def test_validate_job_id_invalid_uuid(self, temp_job_store):
        """Test UUID validation rejects invalid UUIDs"""
        assert temp_job_store._validate_job_id("not-a-uuid") is False
        assert temp_job_store._validate_job_id("12345") is False
        assert temp_job_store._validate_job_id("") is False
        assert temp_job_store._validate_job_id(None) is False

    def test_store_job_success(self, temp_job_store):
        """Test storing a job successfully"""
        job_id = str(uuid.uuid4())
        job = {
            "job_id": job_id,
            "status": "queued",
            "payload": {"text": "test document"}
        }

        result = temp_job_store.store_job(job)

        assert result is True

        # Verify file exists
        json_file = temp_job_store.base_dir / f"{job_id}.json"
        assert json_file.exists()

    def test_store_job_auto_timestamps(self, temp_job_store):
        """Test that store_job adds timestamps automatically"""
        job_id = str(uuid.uuid4())
        job = {
            "job_id": job_id,
            "status": "queued"
        }

        temp_job_store.store_job(job)

        # Retrieve and check timestamps
        stored_job = temp_job_store.get_job(job_id)
        assert "created_at" in stored_job
        assert "updated_at" in stored_job

    def test_store_job_without_job_id_fails(self, temp_job_store):
        """Test storing a job without job_id fails"""
        job = {"status": "queued"}
        result = temp_job_store.store_job(job)
        assert result is False

    def test_store_job_invalid_job_id_fails(self, temp_job_store):
        """Test storing a job with invalid job_id fails"""
        job = {
            "job_id": "not-a-uuid",
            "status": "queued"
        }
        result = temp_job_store.store_job(job)
        assert result is False

    def test_get_job_success(self, temp_job_store):
        """Test retrieving an existing job"""
        job_id = str(uuid.uuid4())
        job = {
            "job_id": job_id,
            "status": "completed",
            "result": {"suggestions": []}
        }

        temp_job_store.store_job(job)
        retrieved_job = temp_job_store.get_job(job_id)

        assert retrieved_job is not None
        assert retrieved_job["job_id"] == job_id
        assert retrieved_job["status"] == "completed"

    def test_get_job_not_found(self, temp_job_store):
        """Test retrieving non-existent job returns None"""
        non_existent_id = str(uuid.uuid4())
        result = temp_job_store.get_job(non_existent_id)
        assert result is None

    def test_get_job_invalid_uuid(self, temp_job_store):
        """Test retrieving job with invalid UUID returns None"""
        result = temp_job_store.get_job("not-a-uuid")
        assert result is None

    def test_update_job_success(self, temp_job_store):
        """Test updating an existing job"""
        job_id = str(uuid.uuid4())
        job = {
            "job_id": job_id,
            "status": "running",
            "progress": 0
        }

        temp_job_store.store_job(job)

        # Update job
        updates = {"status": "completed", "progress": 100}
        result = temp_job_store.update_job(job_id, updates)

        assert result is True

        # Verify updates
        updated_job = temp_job_store.get_job(job_id)
        assert updated_job["status"] == "completed"
        assert updated_job["progress"] == 100

    def test_update_job_non_existent_fails(self, temp_job_store):
        """Test updating non-existent job fails"""
        non_existent_id = str(uuid.uuid4())
        result = temp_job_store.update_job(non_existent_id, {"status": "completed"})
        assert result is False

    def test_list_jobs(self, temp_job_store):
        """Test listing jobs"""
        # Create multiple jobs
        job_ids = [str(uuid.uuid4()) for _ in range(3)]
        for i, job_id in enumerate(job_ids):
            job = {
                "job_id": job_id,
                "status": "queued" if i < 2 else "completed"
            }
            temp_job_store.store_job(job)

        # List all jobs
        all_jobs = temp_job_store.list_jobs()
        assert len(all_jobs) == 3

        # List by status
        queued_jobs = temp_job_store.list_jobs(status="queued")
        assert len(queued_jobs) == 2

    def test_delete_job_success(self, temp_job_store):
        """Test deleting a job"""
        job_id = str(uuid.uuid4())
        job = {"job_id": job_id, "status": "queued"}

        temp_job_store.store_job(job)
        assert temp_job_store.get_job(job_id) is not None

        # Delete job
        result = temp_job_store.delete_job(job_id)
        assert result is True

        # Verify deleted
        assert temp_job_store.get_job(job_id) is None

    def test_get_job_from_events_format(self, temp_job_store):
        """Test loading job from event-based directory format"""
        job_id = str(uuid.uuid4())

        # Create event-based directory structure
        job_dir = temp_job_store.base_dir / job_id
        job_dir.mkdir()

        # Create events.log
        events_file = job_dir / "events.log"
        events = [
            {"type": "start", "timestamp": datetime.utcnow().isoformat()},
            {"type": "progress", "processed": 50, "total": 100, "timestamp": datetime.utcnow().isoformat()},
            {"type": "complete", "result": {"suggestions": []}, "timestamp": datetime.utcnow().isoformat()}
        ]

        with open(events_file, 'w') as f:
            for event in events:
                f.write(json.dumps(event) + '\n')

        # Get job (should load from events)
        job_data = temp_job_store.get_job(job_id)

        assert job_data is not None
        assert job_data["job_id"] == job_id
        assert job_data["status"] == "completed"
        assert job_data["progress"] == 100
        assert job_data["events_count"] == 3


# Test API endpoint
class TestJobStatusEndpoint:
    """Test suite for /api/job-status/{job_id} endpoint"""

    @pytest.fixture
    def client(self):
        """Create FastAPI test client"""
        from main import app
        return TestClient(app)

    @pytest.fixture
    def create_test_job(self):
        """Helper to create a test job"""
        from server.jobs import get_job_store

        def _create_job(status="completed", result=None):
            job_id = str(uuid.uuid4())
            job_store = get_job_store()
            job = {
                "job_id": job_id,
                "status": status,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            if result:
                job["result"] = result

            job_store.store_job(job)
            return job_id

        return _create_job

    def test_job_status_returns_200_for_existing_job(self, client, create_test_job):
        """Test that job-status returns 200 for existing job"""
        job_id = create_test_job(status="completed", result={"suggestions": []})

        response = client.get(f"/api/job-status/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "completed"
        assert "result" in data

    def test_job_status_returns_404_for_missing_job(self, client):
        """Test that job-status returns 404 for non-existent job"""
        non_existent_id = str(uuid.uuid4())

        response = client.get(f"/api/job-status/{non_existent_id}")

        assert response.status_code == 404
        data = response.json()
        # Handle both 'detail' and 'error' keys (depending on error handler)
        error_msg = data.get("detail") or data.get("error")
        assert error_msg is not None
        assert "not found" in error_msg.lower()

    def test_job_status_returns_400_for_invalid_uuid(self, client):
        """Test that job-status returns 400 for invalid UUID"""
        invalid_id = "not-a-uuid"

        response = client.get(f"/api/job-status/{invalid_id}")

        assert response.status_code == 400
        data = response.json()
        # Handle both 'detail' and 'error' keys (depending on error handler)
        error_msg = data.get("detail") or data.get("error")
        assert error_msg is not None
        assert "invalid" in error_msg.lower()

    def test_job_status_includes_all_required_fields(self, client, create_test_job):
        """Test that job-status response includes all required fields"""
        job_id = create_test_job(status="running")

        response = client.get(f"/api/job-status/{job_id}")

        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "job_id" in data
        assert "status" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_job_status_handles_running_job(self, client, create_test_job):
        """Test job-status for running job"""
        job_id = create_test_job(status="running")

        response = client.get(f"/api/job-status/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"

    def test_job_status_handles_failed_job(self, client):
        """Test job-status for failed job"""
        from server.jobs import get_job_store

        job_id = str(uuid.uuid4())
        job_store = get_job_store()
        job = {
            "job_id": job_id,
            "status": "failed",
            "error_message": "Test error"
        }
        job_store.store_job(job)

        response = client.get(f"/api/job-status/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert "error_message" in data
        assert data["error_message"] == "Test error"

    def test_job_status_handles_completed_job_with_result(self, client, create_test_job):
        """Test job-status for completed job with results"""
        result_data = {
            "suggestions": [
                {"id": "1", "text": "Test suggestion"}
            ]
        }
        job_id = create_test_job(status="completed", result=result_data)

        response = client.get(f"/api/job-status/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert "result" in data
        assert len(data["result"]["suggestions"]) == 1


# Smoke test instructions
"""
SMOKE TEST INSTRUCTIONS:

1. Start backend:
   cd /Users/donmerriman/Ilana/ilana-backend
   python main.py

2. Create a test job file:
   echo '{
     "job_id": "12345678-1234-1234-1234-123456789abc",
     "status": "completed",
     "created_at": "2025-01-01T00:00:00",
     "updated_at": "2025-01-01T00:01:00",
     "result": {"suggestions": [{"id": "1", "text": "Test"}]}
   }' > jobs/12345678-1234-1234-1234-123456789abc.json

3. Test existing job (should return 200):
   curl http://127.0.0.1:8000/api/job-status/12345678-1234-1234-1234-123456789abc

   Expected response:
   {
     "job_id": "12345678-1234-1234-1234-123456789abc",
     "status": "completed",
     ...
   }

4. Test non-existent job (should return 404):
   curl http://127.0.0.1:8000/api/job-status/00000000-0000-0000-0000-000000000000

   Expected response:
   {
     "detail": "Job not found"
   }

5. Test invalid UUID (should return 400):
   curl http://127.0.0.1:8000/api/job-status/not-a-uuid

   Expected response:
   {
     "detail": "Invalid job_id format (must be UUID)"
   }

6. Check backend logs:
   - Should see INFO logs for each request
   - 404s should be logged at INFO level (not ERROR)
"""
