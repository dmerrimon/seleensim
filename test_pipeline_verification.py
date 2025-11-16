#!/usr/bin/env python3
"""Verify which pipeline is actually being used"""
import requests
import json

url = "https://ilanalabs-add-in.onrender.com/api/analyze"

test_payload = {
    "text": "Patient will receive chemotherapy infusion over 30 minutes",
    "mode": "selection",
    "request_id": "pipeline_verification_test_20251115",
    "ta": "oncology",
    "phase": "phase_iii"
}

print("Sending test request...")
print(f"Request ID: {test_payload['request_id']}")
print(f"Text: {test_payload['text']}")
print()

response = requests.post(url, json=test_payload, timeout=30)

print(f"Status Code: {response.status_code}")
print()
print("Response:")
print(json.dumps(response.json(), indent=2))
print()
print("=" * 80)
print("ANALYSIS:")
print("=" * 80)

if response.status_code == 200:
    data = response.json()
    suggestions = data.get("suggestions", [])

    print(f"Number of suggestions: {len(suggestions)}")
    print()

    for i, suggestion in enumerate(suggestions, 1):
        print(f"Suggestion {i}:")
        print(f"  model_path: {suggestion.get('model_path')}")
        print(f"  latency_ms: {suggestion.get('latency_ms')}")
        print(f"  type: {suggestion.get('type')}")
        print(f"  confidence: {suggestion.get('confidence')}")
        print(f"  improved_text: {suggestion.get('improved_text')[:100]}...")
        print(f"  rationale: {suggestion.get('rationale')[:150]}...")
        print()

    print("=" * 80)
    print("VERDICT:")
    print("=" * 80)

    # Check for indicators
    model_path = suggestions[0].get('model_path') if suggestions else None
    rationale = suggestions[0].get('rationale', '') if suggestions else ''

    if 'simple_fallback' in str(model_path):
        print("❌ Using SIMPLE FALLBACK (not full enterprise stack)")
    elif 'legacy' in str(model_path):
        print("✅ Using LEGACY pipeline")

        # Check for sophisticated RAG indicators
        rag_indicators = [
            'ICH' in rationale,
            'GCP' in rationale,
            'E6' in rationale,
            'regulatory' in rationale.lower(),
            'guideline' in rationale.lower()
        ]

        if any(rag_indicators):
            print("✅ Response shows RAG characteristics (regulatory references)")
        else:
            print("⚠️  Response lacks RAG indicators - might be using simple fallback")

    print()
    print(f"Check Render logs for request_id: {test_payload['request_id']}")
    print("Look for these log lines:")
    print("  - '🚀 Legacy pipeline start' = using real pipeline")
    print("  - '🔄 Falling back to simple pipeline' = using fallback")
    print("  - '✅ Legacy pipeline complete' = real pipeline succeeded")
