# Smoke Tests - Check Status Button Flow

Comprehensive smoke tests for verifying the "Check Status" button flow works correctly with no 404 errors and graceful handling of missing jobs.

## Prerequisites

1. Backend server running (port 8000)
2. Frontend accessible (via Office Add-in or local development)
3. `shadow/jobs/` directory exists

## Backend Smoke Tests

### Test 1: Create Job via API

```bash
# Start backend
cd /Users/donmerriman/Ilana/ilana-backend
python main.py

# In another terminal, create a test job
curl -X POST http://127.0.0.1:8000/api/queue-job \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Patients will receive chemotherapy treatment daily.",
    "ta": "oncology",
    "mode": "document_truncated"
  }'
```

**Expected Output:**
```json
{
  "job_id": "abc12345-6789-...",
  "status": "queued",
  "created_at": "2024-11-12T..."
}
```

**Verification:**
- ✅ Returns HTTP 200
- ✅ Response contains `job_id` (valid UUID)
- ✅ Response contains `status: "queued"`
- ✅ Response contains `created_at` timestamp

---

### Test 2: Check Status - Existing Job (200 OK)

```bash
# Use job_id from Test 1
export JOB_ID="abc12345-6789-..."

curl -X GET "http://127.0.0.1:8000/api/job-status/$JOB_ID"
```

**Expected Output:**
```json
{
  "job_id": "abc12345-6789-...",
  "status": "queued",
  "created_at": "2024-11-12T...",
  "updated_at": "2024-11-12T...",
  "payload": {
    "text": "Patients will receive...",
    "ta": "oncology",
    "mode": "document_truncated"
  }
}
```

**Verification:**
- ✅ Returns HTTP 200
- ✅ Response contains all job fields
- ✅ `status` is "queued"
- ✅ No errors in console

---

### Test 3: Check Status - Missing Job (404)

```bash
# Use a non-existent job ID
export MISSING_ID="00000000-0000-0000-0000-000000000000"

curl -X GET "http://127.0.0.1:8000/api/job-status/$MISSING_ID"
```

**Expected Output:**
```json
{
  "detail": "Job not found"
}
```

**Verification:**
- ✅ Returns HTTP 404
- ✅ Response contains `detail: "Job not found"`
- ✅ No server errors or stack traces
- ✅ Logs show INFO level message (not ERROR)

---

### Test 4: Check Status - Invalid Job ID (400)

```bash
curl -X GET "http://127.0.0.1:8000/api/job-status/not-a-valid-uuid"
```

**Expected Output:**
```json
{
  "detail": "Invalid job_id format (must be UUID)"
}
```

**Verification:**
- ✅ Returns HTTP 400
- ✅ Response contains validation error message
- ✅ No server crashes

---

### Test 5: Verify Job File Created

```bash
# Check shadow/jobs/ directory
ls -la shadow/jobs/

# View specific job file
export JOB_ID="abc12345-6789-..."
cat "shadow/jobs/$JOB_ID.json"
```

**Expected:**
- ✅ File `shadow/jobs/{job_id}.json` exists
- ✅ File contains valid JSON
- ✅ JSON matches job structure

---

## Frontend Smoke Tests

### Test 6: Click Check Status Button (Existing Job)

**Steps:**
1. Open Word Add-in
2. Trigger a document analysis that creates a queued job
3. UI should show "Analysis Queued" card with job ID
4. Click "Check Status" button

**Expected Behavior:**
- ✅ Button changes to "Checking..." and becomes disabled
- ✅ No errors in browser console
- ✅ After ~1-2 seconds, button re-enables
- ✅ Status message updates (e.g., "Job is queued (0%)")
- ✅ Toast notification appears

**Verification in DevTools:**
```javascript
// Check API call
// Network tab should show:
// GET /api/job-status/{job_id} → 200 OK

// Check button state
const btn = document.querySelector('.check-status-btn');
console.log('Button disabled:', btn.disabled); // Should be false after check
console.log('Button text:', btn.textContent);  // Should be "Check Status"
```

---

### Test 7: Click Check Status Button (Missing Job)

**Steps:**
1. Manually create a job card with fake job ID:
```javascript
showJobQueuedMessage('00000000-0000-0000-0000-000000000000', 'test');
```
2. Click "Check Status" button

**Expected Behavior:**
- ✅ Button changes to "Checking..." briefly
- ✅ Network call returns 404
- ✅ UI updates to show "⚠️ Job Not Found"
- ✅ Shows two buttons: "Create New Job" and "Analyze Again"
- ✅ Status message shows "Job not found - please retry analysis"
- ✅ No console errors (warnings OK)

**Verification:**
```javascript
// Check UI state
const card = document.querySelector('.job-queued-card');
console.log('Card HTML:', card.innerHTML);
// Should contain "Job Not Found"

// Check telemetry
// Console should show: job_status_notfound event sent
```

---

### Test 8: Retry Job Creation (404 → Create New Job)

**Steps:**
1. After seeing "Job Not Found" UI (Test 7)
2. Click "Create New Job" button

**Expected Behavior:**
- ✅ POST request to `/api/queue-job`
- ✅ New job created with new job_id
- ✅ UI updates to show new job card
- ✅ Toast shows "New job created successfully!"
- ✅ New job can be checked via "Check Status"

**Verification:**
```javascript
// Check network
// Should see POST /api/queue-job → 200 OK

// Check new job card
const card = document.querySelector('.job-queued-card');
const newJobId = card.dataset.jobId;
console.log('New job ID:', newJobId);
// Should be different from original fake ID
```

---

### Test 9: Network Timeout Handling

**Steps:**
1. Slow down network in DevTools (Slow 3G)
2. Click "Check Status" button
3. Wait for 10s timeout

**Expected Behavior:**
- ✅ After 10 seconds, timeout occurs
- ✅ Error message shown: "Request timed out"
- ✅ Exponential backoff retry logic kicks in
- ✅ Button re-enabled
- ✅ No infinite loading state

**Verification:**
```javascript
// Console should show:
// "Job status check timed out for {job_id}"
// "Retry attempt 1/5 for job {job_id} in 2000ms"
```

---

### Test 10: Server Error (500) Handling

**Steps:**
1. Simulate 500 error (temporarily break backend or use mock)
2. Click "Check Status" button

**Expected Behavior:**
- ✅ Status code 500 detected
- ✅ Exponential backoff retry logic activated
- ✅ Status message: "Retrying job status check (1/5)..."
- ✅ After 5 attempts, shows "Job Failed" UI
- ✅ Button re-enabled

**Verification:**
```javascript
// Console output:
// "Server error 500 for job {job_id}"
// "Retry attempt 1/5 for job {job_id} in 2000ms"
// ...
// "Max retry attempts (5) reached for job {job_id}"
```

---

## Integration Tests

### Test 11: Full Lifecycle Test

**Steps:**
1. Open Word add-in
2. Select text or trigger document analysis
3. Job is queued (UI shows "Analysis Queued")
4. Click "Check Status" multiple times
5. Backend processes job (manually update status in JSON file if needed)
6. Final check shows "completed" status
7. UI shows suggestions

**Expected Behavior:**
- ✅ Job created via backend
- ✅ Status checks return correct state progression
- ✅ UI updates correctly at each stage
- ✅ Completed job shows results
- ✅ No 404 errors at any point

---

### Test 12: Multiple Jobs Concurrently

**Steps:**
1. Create multiple jobs via POST /api/queue-job (3-5 jobs)
2. Check status of each job
3. Verify all return correct status

**Expected:**
- ✅ Each job has unique ID
- ✅ Each job can be queried independently
- ✅ No cross-contamination between jobs
- ✅ All jobs stored in shadow/jobs/

---

## Automated Test Execution

### Backend Unit Tests

```bash
cd /Users/donmerriman/Ilana/ilana-backend
python tests/test_job_endpoints.py
```

**Expected Output:**
```
Running unit tests for job endpoints...

✅ test_job_status_200_for_existing passed
✅ test_job_status_404_for_missing passed
✅ test_job_status_400_for_invalid_id passed
✅ test_queue_job_creates_job passed
✅ test_queue_job_minimal_payload passed
✅ test_job_lifecycle passed

✅ All tests passed!
```

---

### Frontend Unit Tests

Open browser console and run:

```javascript
// Load test scripts
// (Assuming test files are included in page)

// Run tests
await test_checkJobStatus_handles_200();
await test_checkJobStatus_handles_404();
```

**Expected Console Output:**
```
🧪 Running test_checkJobStatus_handles_200...
✅ Test case 1 passed: Completed job handled correctly
✅ Test case 2 passed: Running job handled correctly
✅ Test case 3 passed: Failed job handled correctly
✅ All test cases passed!

🧪 Running test_checkJobStatus_handles_404...
✅ test_checkJobStatus_handles_404 passed
```

---

## Checklist Summary

### Backend ✅
- [ ] POST /api/queue-job creates jobs
- [ ] GET /api/job-status/{id} returns 200 for existing
- [ ] GET /api/job-status/{id} returns 404 for missing
- [ ] GET /api/job-status/{id} returns 400 for invalid UUID
- [ ] Jobs stored in shadow/jobs/ directory
- [ ] All backend unit tests pass

### Frontend ✅
- [ ] Check Status button disables during check
- [ ] Check Status button re-enables after response
- [ ] 200 response displays job status correctly
- [ ] 404 response shows "Job Not Found" UI
- [ ] "Create New Job" button calls /api/queue-job
- [ ] Timeout (10s) handled gracefully
- [ ] Server errors (500) trigger exponential backoff
- [ ] Max 5 retry attempts enforced
- [ ] No console errors (warnings OK)
- [ ] Defensive DOM guards prevent null errors

### Integration ✅
- [ ] Full job lifecycle works end-to-end
- [ ] Multiple jobs can coexist
- [ ] Polling works correctly
- [ ] Telemetry events sent properly

---

## Troubleshooting

### Issue: 404 on job-status endpoint

**Check:**
```bash
# Verify server is running
curl http://127.0.0.1:8000/health || echo "Server not running"

# Check if job exists
ls shadow/jobs/*.json

# Verify job ID matches
cat shadow/jobs/{job_id}.json
```

**Fix:**
- Ensure backend is running
- Verify job was actually created
- Check job_id is valid UUID

---

### Issue: Button stays disabled

**Check:**
```javascript
// In browser console
const btn = document.querySelector('.check-status-btn');
console.log({
  disabled: btn.disabled,
  ariaBusy: btn.getAttribute('aria-busy'),
  text: btn.textContent
});
```

**Fix:**
- Check for JavaScript errors in console
- Verify checkJobStatus completes (not stuck in promise)
- Ensure error handler re-enables button

---

### Issue: Jobs not persisting

**Check:**
```bash
# Verify directory exists
ls -la shadow/jobs/

# Check permissions
ls -ld shadow/jobs/
```

**Fix:**
```bash
# Create directory if missing
mkdir -p shadow/jobs

# Fix permissions
chmod 755 shadow/jobs
```

---

## Success Criteria

All smoke tests pass when:
✅ Backend returns correct HTTP status codes (200, 404, 400)
✅ Frontend handles all responses gracefully
✅ No 404 errors for valid jobs
✅ Missing jobs show retry UI
✅ Button always re-enables after check
✅ Timeouts and errors handled with backoff
✅ Jobs persist to shadow/jobs/ directory
✅ All unit tests pass

---

**Test Status:** Ready for execution
**Last Updated:** 2024-11-12
**Version:** 1.0.0
