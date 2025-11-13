"""
Unit tests for job status and queue endpoints.

Tests:
- GET /api/job-status/{job_id} returns 200 for existing job
- GET /api/job-status/{job_id} returns 404 for missing job
- GET /api/job-status/{job_id} returns 400 for invalid job_id format
- POST /api/queue-job creates new job and returns job_id
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path
import json
import uuid

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
from server.jobs import get_job_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_job_store():
    """Clean up job store before each test"""
    job_store = get_job_store()
    # Note: In a real test environment, you'd use a test-specific directory
    yield
    # Cleanup after test if needed


def test_job_status_200_for_existing():
    """Test that /api/job-status returns 200 for an existing job"""
    # Create a test job
    job_store = get_job_store()
    job_id = str(uuid.uuid4())

    test_job = {
        "job_id": job_id,
        "status": "queued",
        "payload": {"text": "Test protocol text"},
        "created_at": "2024-11-12T10:00:00",
        "updated_at": "2024-11-12T10:00:00"
    }

    success = job_store.store_job(test_job)
    assert success, "Failed to create test job"

    # Test the endpoint
    response = client.get(f"/api/job-status/{job_id}")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data["job_id"] == job_id
    assert data["status"] == "queued"
    assert "created_at" in data
    assert "updated_at" in data

    # Cleanup
    job_store.delete_job(job_id)
    print(f"✅ test_job_status_200_for_existing passed")


def test_job_status_404_for_missing():
    """Test that /api/job-status returns 404 for a non-existent job"""
    # Use a valid UUID that doesn't exist
    job_id = str(uuid.uuid4())

    response = client.get(f"/api/job-status/{job_id}")

    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
    data = response.json()

    # Handle both FastAPI standard format and custom error handler format
    error_msg = data.get("detail") or data.get("error")
    assert error_msg is not None, f"Expected error message in response, got: {data}"
    assert "not found" in error_msg.lower(), f"Expected 'not found' message, got: {error_msg}"

    print(f"✅ test_job_status_404_for_missing passed")


def test_job_status_400_for_invalid_id():
    """Test that /api/job-status returns 400 for invalid job_id format"""
    invalid_ids = [
        "not-a-uuid",
        "12345",
        "invalid-job-id"
    ]

    for invalid_id in invalid_ids:
        response = client.get(f"/api/job-status/{invalid_id}")
        assert response.status_code == 400, f"Expected 400 for '{invalid_id}', got {response.status_code}"
        data = response.json()

        # Handle both FastAPI standard format and custom error handler format
        error_msg = data.get("detail") or data.get("error")
        assert error_msg is not None, f"Expected error message for '{invalid_id}', got: {data}"
        assert "invalid" in error_msg.lower() or "format" in error_msg.lower(), \
            f"Expected validation error for '{invalid_id}', got: {error_msg}"

    print(f"✅ test_job_status_400_for_invalid_id passed")


def test_queue_job_creates_job():
    """Test that POST /api/queue-job creates a new job and returns job_id"""
    payload = {
        "text": "Patients will receive chemotherapy treatment daily.",
        "ta": "oncology",
        "mode": "document_truncated"
    }

    response = client.post("/api/queue-job", json=payload)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()

    assert "job_id" in data
    assert "status" in data
    assert "created_at" in data
    assert data["status"] == "queued"

    # Validate job_id is a valid UUID
    try:
        uuid.UUID(data["job_id"])
        print(f"✅ Valid UUID: {data['job_id']}")
    except ValueError:
        pytest.fail(f"Invalid UUID format: {data['job_id']}")

    # Verify the job was actually created
    job_store = get_job_store()
    job = job_store.get_job(data["job_id"])
    assert job is not None, "Job should exist in store"
    assert job["status"] == "queued"
    assert job["payload"]["text"] == payload["text"]

    # Cleanup
    job_store.delete_job(data["job_id"])
    print(f"✅ test_queue_job_creates_job passed")


def test_queue_job_minimal_payload():
    """Test that POST /api/queue-job works with minimal payload"""
    payload = {"text": "Test"}

    response = client.post("/api/queue-job", json=payload)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()

    assert "job_id" in data
    assert "status" in data

    # Cleanup
    job_store = get_job_store()
    job_store.delete_job(data["job_id"])
    print(f"✅ test_queue_job_minimal_payload passed")


def test_job_lifecycle():
    """Test complete job lifecycle: create -> query -> update -> query"""
    # 1. Create job
    payload = {"text": "Test protocol", "ta": "general_medicine"}
    response = client.post("/api/queue-job", json=payload)
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    # 2. Query initial status
    response = client.get(f"/api/job-status/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"

    # 3. Update job status
    job_store = get_job_store()
    job_store.update_job(job_id, {"status": "running", "progress": 50})

    # 4. Query updated status
    response = client.get(f"/api/job-status/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data.get("progress") == 50

    # 5. Complete job
    job_store.update_job(job_id, {
        "status": "completed",
        "progress": 100,
        "result": {"suggestions": []}
    })

    # 6. Query completed status
    response = client.get(f"/api/job-status/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data.get("progress") == 100
    assert "result" in data

    # Cleanup
    job_store.delete_job(job_id)
    print(f"✅ test_job_lifecycle passed")


if __name__ == "__main__":
    print("Running unit tests for job endpoints...\n")

    try:
        test_job_status_200_for_existing()
        test_job_status_404_for_missing()
        test_job_status_400_for_invalid_id()
        test_queue_job_creates_job()
        test_queue_job_minimal_payload()
        test_job_lifecycle()

        print("\n✅ All tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
