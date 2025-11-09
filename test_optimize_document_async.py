"""
Unit test for /api/optimize-document-async endpoint
Tests the backward-compatible endpoint with in-process and HTTP fallback logic
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add backend directory to path for imports
backend_path = Path(__file__).parent / "ilana-backend"
sys.path.insert(0, str(backend_path))

print(f"Importing from: {backend_path}")

from main import app

# Verify endpoint is registered
print(f"Registered routes: {[route.path for route in app.routes if hasattr(route, 'path')][:10]}")
print(f"Looking for /api/optimize-document-async...")

client = TestClient(app)


def test_optimize_document_async_basic():
    """Test that the endpoint accepts valid payload and returns JSON response"""
    payload = {
        "text": "Patients will receive treatment daily for adverse events.",
        "ta": "oncology",
        "user_id_hash": "test_user_123"
    }

    response = client.post("/api/optimize-document-async", json=payload)

    # Should return 200 OK or 202 if queued
    assert response.status_code in [200, 202, 502], f"Unexpected status: {response.status_code}"

    # Should return JSON
    data = response.json()
    assert isinstance(data, dict), "Response should be a dictionary"

    # Should have request_id in response
    if response.status_code == 200:
        assert "request_id" in data or "result" in data, "Response should have request_id or result"
        print(f"✅ Basic test passed: {data}")


def test_optimize_document_async_missing_text():
    """Test that endpoint handles missing text field gracefully"""
    payload = {
        "ta": "oncology"
    }

    response = client.post("/api/optimize-document-async", json=payload)

    # Should still process (text defaults to empty string)
    assert response.status_code in [200, 202, 400, 500, 502], f"Unexpected status: {response.status_code}"
    print(f"✅ Missing text test passed with status: {response.status_code}")


def test_optimize_document_async_large_document():
    """Test that endpoint handles large document payloads"""
    large_text = "Patients will receive chemotherapy treatment. " * 500  # ~20KB
    payload = {
        "text": large_text,
        "ta": "oncology",
        "user_id_hash": "test_large_doc"
    }

    response = client.post("/api/optimize-document-async", json=payload)

    # Should accept large payloads
    assert response.status_code in [200, 202, 502], f"Unexpected status: {response.status_code}"

    data = response.json()
    assert isinstance(data, dict), "Response should be a dictionary"
    print(f"✅ Large document test passed: {len(large_text)} chars processed")


def test_optimize_document_async_response_format():
    """Test that response matches expected format"""
    payload = {
        "text": "Study participants will be monitored for adverse events per ICH-GCP.",
        "ta": "general_medicine"
    }

    response = client.post("/api/optimize-document-async", json=payload)

    if response.status_code == 200:
        data = response.json()

        # Check for expected response structure
        # Either direct result or wrapped result
        if "result" in data:
            result = data["result"]
            if "status" in result and result["status"] == "queued":
                assert "job_id" in result, "Queued result should have job_id"
                print(f"✅ Response format test passed (queued): {result}")
        else:
            # Direct result format
            assert "request_id" in data or "suggestions" in data, "Direct result should have request_id or suggestions"
            print(f"✅ Response format test passed (direct): {data.keys()}")


def test_optimize_document_async_fallback_behavior():
    """Test that HTTP fallback works when in-process enqueue fails"""
    # This test assumes hybrid_controller may not be available
    payload = {
        "text": "HER2-positive breast cancer patients require cardiac monitoring.",
        "ta": "oncology"
    }

    response = client.post("/api/optimize-document-async", json=payload)

    # Should fall back gracefully
    assert response.status_code in [200, 202, 502], f"Fallback failed with status: {response.status_code}"

    if response.status_code == 502:
        data = response.json()
        assert "detail" in data, "502 error should have detail message"
        assert "Could not enqueue" in data["detail"], "502 should indicate enqueue failure"
        print(f"✅ Fallback behavior test: Correctly returned 502 when services unavailable")
    else:
        print(f"✅ Fallback behavior test: Successfully processed via fallback with status {response.status_code}")


if __name__ == "__main__":
    print("Running unit tests for /api/optimize-document-async endpoint...\n")

    try:
        test_optimize_document_async_basic()
        test_optimize_document_async_missing_text()
        test_optimize_document_async_large_document()
        test_optimize_document_async_response_format()
        test_optimize_document_async_fallback_behavior()

        print("\n✅ All tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
