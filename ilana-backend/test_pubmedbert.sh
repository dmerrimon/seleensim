#!/bin/bash
# Quick test script for PubMedBERT endpoint

echo "========================================="
echo "PUBMEDBERT ENDPOINT TEST"
echo "========================================="
echo ""

# Check if HUGGINGFACE_API_KEY is set in .env
if [ -f .env ]; then
  source .env
fi

if [ -z "$HUGGINGFACE_API_KEY" ]; then
  echo "❌ HUGGINGFACE_API_KEY not set"
  echo "Please set it in your .env file or as environment variable"
  exit 1
fi

echo "Testing endpoint with API key..."
echo ""

# Test the endpoint with authentication
curl -X POST https://dk8e3vdcuov185qm.us-east-1.aws.endpoints.huggingface.cloud \
  -H "Authorization: Bearer $HUGGINGFACE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"inputs": "adverse events"}' \
  2>&1 | head -20

echo ""
echo "========================================="
echo "If you see JSON response above, endpoint is working!"
echo "If you see 401 error, your API key is invalid"
echo "If you see 503 error, endpoint is not running"
echo "========================================="
