#!/bin/bash

# QA Test Harness for Ilana API Analysis
# This script tests /api/analyze endpoints and highlight functionality

set -e  # Exit on any error

# Configuration
# Set ILANA_API_BASE environment variable to test against production
# Default: http://127.0.0.1:8000
API_BASE_URL="${ILANA_API_BASE:-http://127.0.0.1:8000}"
QA_DIR="$(dirname "$0")"
SAMPLE_PROTOCOLS_FILE="$QA_DIR/sample_protocols.json"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Ilana QA Test Harness${NC}"
echo "========================================"
echo "API Base URL: $API_BASE_URL"
echo "Sample Data: $SAMPLE_PROTOCOLS_FILE"
echo ""

# Check if sample protocols file exists
if [ ! -f "$SAMPLE_PROTOCOLS_FILE" ]; then
    echo -e "${RED}❌ Sample protocols file not found: $SAMPLE_PROTOCOLS_FILE${NC}"
    exit 1
fi

# Check if backend is running
echo -e "${YELLOW}🔍 Checking backend health...${NC}"
if ! curl -s -f "$API_BASE_URL/health" > /dev/null; then
    echo -e "${RED}❌ Backend not responding at $API_BASE_URL${NC}"
    echo "Please start the backend with: cd ilana-backend && uvicorn main:app --reload --port 8000"
    exit 1
fi
echo -e "${GREEN}✅ Backend is running${NC}"

# Create results directory
mkdir -p "$QA_DIR/results"

# Function to extract text from sample protocols
extract_sample_text() {
    local key="$1"
    python3 -c "
import json
import sys
with open('$SAMPLE_PROTOCOLS_FILE', 'r') as f:
    data = json.load(f)
    if '$key' in data['sample_texts']:
        print(data['sample_texts']['$key']['text'])
    else:
        sys.exit(1)
"
}

# Function to make API call and save response
test_api_call() {
    local endpoint="$1"
    local payload="$2"
    local output_file="$3"
    local description="$4"
    
    echo -e "${YELLOW}📡 Testing $description${NC}"
    echo "Endpoint: $endpoint"
    echo "Output: $output_file"
    
    local start_time=$(date +%s%3N)
    
    # Make API call
    local response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -H "Accept: application/json" \
        -d "$payload" \
        "$API_BASE_URL$endpoint" \
        -w "\n%{http_code}\n%{time_total}")
    
    local end_time=$(date +%s%3N)
    local duration=$((end_time - start_time))
    
    # Parse response
    local body=$(echo "$response" | head -n -2)
    local http_code=$(echo "$response" | tail -n 2 | head -n 1)
    local time_total=$(echo "$response" | tail -n 1)
    
    # Save response to file
    echo "$body" | jq '.' > "$output_file" 2>/dev/null || echo "$body" > "$output_file"
    
    if [ "$http_code" = "200" ] || [ "$http_code" = "202" ]; then
        echo -e "${GREEN}✅ Success (${http_code}) - ${duration}ms${NC}"
        
        # Try to extract suggestions count
        local suggestions_count=$(echo "$body" | jq -r '.result.suggestions | length' 2>/dev/null || echo "unknown")
        if [ "$suggestions_count" != "null" ] && [ "$suggestions_count" != "unknown" ]; then
            echo -e "   📋 Suggestions found: $suggestions_count"
        fi
    else
        echo -e "${RED}❌ Failed ($http_code)${NC}"
        echo "Response: $body"
    fi
    echo ""
}

# Test 1: Selection Mode Analysis
echo -e "${BLUE}🎯 Test 1: Selection Mode Analysis${NC}"
echo "----------------------------------------"

# Extract adverse event monitoring text
SELECTION_TEXT=$(extract_sample_text "adverse_event_monitoring")
if [ -z "$SELECTION_TEXT" ]; then
    echo -e "${RED}❌ Failed to extract adverse_event_monitoring text${NC}"
    exit 1
fi

SELECTION_PAYLOAD=$(cat <<EOF
{
    "text": "$SELECTION_TEXT",
    "mode": "selection",
    "ta": "general_medicine",
    "request_id": "qa_selection_$(date +%s)"
}
EOF
)

test_api_call "/api/analyze" "$SELECTION_PAYLOAD" "$QA_DIR/results/last_response.json" "Selection Mode Analysis"

# Test 2: Document Mode Analysis  
echo -e "${BLUE}📄 Test 2: Document Mode Analysis${NC}"
echo "----------------------------------------"

# Extract full protocol text
DOCUMENT_TEXT=$(extract_sample_text "full_protocol_excerpt")
if [ -z "$DOCUMENT_TEXT" ]; then
    echo -e "${RED}❌ Failed to extract full_protocol_excerpt text${NC}"
    exit 1
fi

DOCUMENT_PAYLOAD=$(cat <<EOF
{
    "text": "$DOCUMENT_TEXT",
    "mode": "document_truncated", 
    "ta": "oncology",
    "request_id": "qa_document_$(date +%s)"
}
EOF
)

test_api_call "/api/analyze" "$DOCUMENT_PAYLOAD" "$QA_DIR/results/last_response_full.json" "Document Mode Analysis"

# Test 3: Highlight Diagnosis
echo -e "${BLUE}🎨 Test 3: Highlight Diagnosis${NC}"
echo "----------------------------------------"

HIGHLIGHT_PAYLOAD1=$(cat <<EOF
{
    "search_text": "Side effects will be monitored",
    "test_type": "adverse_event_terminology"
}
EOF
)

test_api_call "/api/diagnose-highlight" "$HIGHLIGHT_PAYLOAD1" "$QA_DIR/results/highlight_diagnosis_1.json" "Highlight Adverse Event Text"

HIGHLIGHT_PAYLOAD2=$(cat <<EOF
{
    "search_text": "patients with advanced solid tumors",
    "test_type": "patient_terminology"
}
EOF
)

test_api_call "/api/diagnose-highlight" "$HIGHLIGHT_PAYLOAD2" "$QA_DIR/results/highlight_diagnosis_2.json" "Highlight Patient Terminology"

# Test 4: Oncology-Specific Analysis
echo -e "${BLUE}🩺 Test 4: Oncology-Specific Analysis${NC}"
echo "----------------------------------------"

ONCOLOGY_TEXT=$(extract_sample_text "dosing_regimen_oncology")
if [ -z "$ONCOLOGY_TEXT" ]; then
    echo -e "${RED}❌ Failed to extract dosing_regimen_oncology text${NC}"
    exit 1
fi

ONCOLOGY_PAYLOAD=$(cat <<EOF
{
    "text": "$ONCOLOGY_TEXT",
    "mode": "selection",
    "ta": "oncology", 
    "request_id": "qa_oncology_$(date +%s)"
}
EOF
)

test_api_call "/api/analyze" "$ONCOLOGY_PAYLOAD" "$QA_DIR/results/oncology_analysis.json" "Oncology-Specific Analysis"

# Test 5: Error Handling
echo -e "${BLUE}⚠️  Test 5: Error Handling${NC}"
echo "----------------------------------------"

ERROR_PAYLOAD=$(cat <<EOF
{
    "text": "",
    "mode": "invalid_mode"
}
EOF
)

echo -e "${YELLOW}📡 Testing Error Handling (Empty Text)${NC}"
curl -s -X POST \
    -H "Content-Type: application/json" \
    -d "$ERROR_PAYLOAD" \
    "$API_BASE_URL/api/analyze" \
    -w "\nHTTP Code: %{http_code}\n" \
    -o "$QA_DIR/results/error_response.json"

echo ""

# Summary Report
echo -e "${BLUE}📊 Test Results Summary${NC}"
echo "========================================"
echo "Results saved in: $QA_DIR/results/"
echo ""
echo "Files created:"
ls -la "$QA_DIR/results/"
echo ""

# Validate JSON responses
echo -e "${YELLOW}🔍 Validating JSON responses...${NC}"
for json_file in "$QA_DIR/results"/*.json; do
    if jq empty "$json_file" 2>/dev/null; then
        echo -e "${GREEN}✅ Valid JSON: $(basename "$json_file")${NC}"
    else
        echo -e "${RED}❌ Invalid JSON: $(basename "$json_file")${NC}"
    fi
done

echo ""
echo -e "${GREEN}🎉 QA Test Harness completed!${NC}"
echo ""
echo "Next steps:"
echo "1. Review response files in $QA_DIR/results/"
echo "2. Run Playwright UI tests: npm test"
echo "3. Check telemetry logs in backend console"