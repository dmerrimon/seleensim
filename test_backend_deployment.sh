#!/bin/bash
# Test ilanalabs-add-in backend deployment

BACKEND_URL="https://ilanalabs-add-in.onrender.com"

echo "================================================"
echo "Testing ilanalabs-add-in Backend Deployment"
echo "================================================"
echo ""

# Test 1: Health endpoint
echo "1. Testing /health endpoint..."
curl -s -X GET "${BACKEND_URL}/health" | python3 -m json.tool
echo ""

# Test 2: Service health (shows which services are configured)
echo "2. Testing /health/services endpoint..."
curl -s -X GET "${BACKEND_URL}/health/services" | python3 -m json.tool
echo ""

# Test 3: Quick analysis test
echo "3. Testing /api/analyze endpoint with sample text..."
curl -s -X POST "${BACKEND_URL}/api/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Subjects will be initially enrolled into the appropriate Group 1 subgroup based on their disease symptoms/status at enrollment.",
    "user_id": "test_user",
    "request_id": "test_request"
  }' | python3 -m json.tool
echo ""

echo "================================================"
echo "Test Complete"
echo "================================================"
