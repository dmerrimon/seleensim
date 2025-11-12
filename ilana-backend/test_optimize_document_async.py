#!/usr/bin/env python3
"""
Unit test for /api/optimize-document-async endpoint
"""

import pytest
import httpx
import asyncio
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_optimize_document_async_endpoint():
    """Test that /api/optimize-document-async returns proper JSON response"""
    payload = {
        "text": "PROTOCOL TITLE: A Phase 2 Study to Evaluate Safety and Efficacy in Patients with Cancer",
        "ta": "oncology",
        "user_id_hash": "test_user_123"
    }
    
    response = client.post("/api/optimize-document-async", json=payload)
    
    # Should return 200 OK
    assert response.status_code == 200
    
    # Should return JSON
    json_data = response.json()
    assert isinstance(json_data, dict)
    
    # Should have required fields
    assert "request_id" in json_data
    assert "result" in json_data
    assert isinstance(json_data["result"], dict)
    assert "status" in json_data["result"]
    assert json_data["result"]["status"] == "queued"
    assert "job_id" in json_data["result"]
    
    # Fields should be non-empty strings
    assert isinstance(json_data["request_id"], str)
    assert len(json_data["request_id"]) > 0
    assert isinstance(json_data["result"]["job_id"], str)
    assert len(json_data["result"]["job_id"]) > 0
    
    print(f"✅ Test passed! Response: {json_data}")

def test_optimize_document_async_minimal_payload():
    """Test endpoint with minimal payload"""
    payload = {"text": "Test document"}
    
    response = client.post("/api/optimize-document-async", json=payload)
    
    assert response.status_code == 200
    json_data = response.json()
    assert "request_id" in json_data
    assert "result" in json_data
    assert json_data["result"]["status"] == "queued"
    
    print(f"✅ Minimal test passed! Response: {json_data}")

def test_optimize_document_async_empty_text():
    """Test endpoint handles empty text gracefully"""
    payload = {"text": ""}
    
    response = client.post("/api/optimize-document-async", json=payload)
    
    # Should still return 200 (backend handles empty text gracefully)
    assert response.status_code == 200
    json_data = response.json()
    assert "request_id" in json_data
    
    print(f"✅ Empty text test passed! Response: {json_data}")

if __name__ == "__main__":
    print("🧪 Running /api/optimize-document-async tests...")
    test_optimize_document_async_endpoint()
    test_optimize_document_async_minimal_payload() 
    test_optimize_document_async_empty_text()
    print("🎉 All tests passed!")