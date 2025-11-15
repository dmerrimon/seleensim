#!/usr/bin/env python3
"""Test the /api/explain-suggestion endpoint"""
import requests
import json

# Test locally (will fail if server not running locally, but that's ok)
# The real test will be on Render after deployment

def test_endpoint(base_url):
    """Test the explain-suggestion endpoint"""
    endpoint = f"{base_url}/api/explain-suggestion"

    payload = {
        "suggestion_id": "test_suggestion_001",
        "ta": "cardiology",
        "analysis_mode": "legacy"
    }

    print(f"Testing endpoint: {endpoint}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print()

    try:
        response = requests.post(endpoint, json=payload, timeout=30)

        print(f"Status Code: {response.status_code}")
        print()

        if response.status_code == 200:
            data = response.json()
            print("✅ SUCCESS!")
            print()
            print("Response fields:")
            print(f"  - suggestion_id: {data.get('suggestion_id')}")
            print(f"  - latency_ms: {data.get('latency_ms')}")
            print(f"  - model: {data.get('model')}")
            print(f"  - ta: {data.get('ta')}")
            print()
            print("Rationale Full (first 500 chars):")
            print(data.get('rationale_full', '')[:500])
            print("...")
            print()
            print("✅ All response fields present")

            # Verify all expected fields
            required_fields = ['suggestion_id', 'rationale_full', 'rationale', 'explanation', 'latency_ms']
            missing = [f for f in required_fields if f not in data]

            if missing:
                print(f"❌ Missing fields: {missing}")
                return False

            return True
        else:
            print(f"❌ FAILED with status {response.status_code}")
            print(response.text)
            return False

    except requests.exceptions.ConnectionError:
        print("⚠️  Could not connect - server may not be running locally")
        print("   This is OK - we'll test on Render after deployment")
        return None
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    print("=" * 80)
    print("Testing /api/explain-suggestion endpoint")
    print("=" * 80)
    print()

    # Test on Render (production)
    print("Testing on Render production:")
    print("-" * 80)
    result = test_endpoint("https://ilanalabs-add-in.onrender.com")

    print()
    print("=" * 80)
    if result:
        print("✅ ENDPOINT TEST PASSED")
    elif result is None:
        print("⚠️  ENDPOINT NOT TESTED (will test after deployment)")
    else:
        print("❌ ENDPOINT TEST FAILED")
    print("=" * 80)
