# Smoke Tests: Selection-Only Mode

Quick validation tests to ensure the selection-only mode works correctly after deployment.

## Prerequisites
- Backend running on `http://localhost:8000` (or your deployment URL)
- Frontend deployed to Word Online or Office Desktop
- `ENABLE_DOCUMENT_ANALYSIS=false` set in backend environment

## Test Suite

### Test 1: Selection Analysis Works ✅
**Objective:** Verify that selection-based analysis still functions correctly

**Steps:**
1. Open Word document in Word Online/Desktop
2. Open Ilana add-in taskpane
3. Select 1-2 paragraphs of text (20-200 words)
4. Click **Analyze** button
5. Wait 3-10 seconds

**Expected Result:**
- ✅ Suggestions appear in sidebar
- ✅ No errors displayed
- ✅ Response time < 15 seconds

**Actual Result:** _____________________

---

### Test 2: No Selection Shows Guidance Modal ✅
**Objective:** Verify modal appears when no text is selected

**Steps:**
1. Open Word document
2. Ensure NO text is selected (click in empty space)
3. Click **Analyze** button

**Expected Result:**
- ✅ Modal appears with title "Select Text to Analyze"
- ✅ Modal description says "To use Ilana's analysis features, please select specific text..."
- ✅ Only ONE button visible: "Select Text First"
- ✅ NO "Analyze Document (Truncated)" button
- ✅ NO "Queue Deep Analysis" button

**Actual Result:** _____________________

---

### Test 3: Document Analysis Options Hidden 🚫
**Objective:** Verify document analysis UI is completely hidden

**Steps:**
1. Open Ilana add-in
2. Click **Analyze** without selection to open modal
3. Inspect modal contents

**Expected Result:**
- ✅ "Analyze Document (Truncated)" button NOT visible
- ✅ "Queue Deep Analysis" button NOT visible
- ✅ Only "Select Text First" button visible

**Actual Result:** _____________________

---

### Test 4: Backend Rejects Document Modes (410) 🚫
**Objective:** Verify backend returns 410 for document analysis requests

**Test 4a: Test /api/analyze with document_truncated mode**
```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "Test document text", "mode": "document_truncated"}' \
  -v
```

**Expected Result:**
```
< HTTP/1.1 410 Gone
{
  "detail": "Document analysis disabled. Use selection-based analysis."
}
```

**Actual Result:** _____________________

**Test 4b: Test /api/analyze with document mode**
```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "Test document text", "mode": "document"}' \
  -v
```

**Expected Result:**
```
< HTTP/1.1 410 Gone
{
  "detail": "Document analysis disabled. Use selection-based analysis."
}
```

**Actual Result:** _____________________

**Test 4c: Test /api/optimize-document-async**
```bash
curl -X POST http://localhost:8000/api/optimize-document-async \
  -H "Content-Type: application/json" \
  -d '{"text": "Test document text"}' \
  -v
```

**Expected Result:**
```
< HTTP/1.1 410 Gone
{
  "detail": "Document analysis disabled. Use selection-based analysis."
}
```

**Actual Result:** _____________________

---

### Test 5: Selection Mode Still Allowed ✅
**Objective:** Verify selection mode is NOT blocked

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "Patients will receive treatment daily for adverse events.", "mode": "selection", "ta": "oncology"}' \
  -v
```

**Expected Result:**
```
< HTTP/1.1 200 OK
{
  "request_id": "...",
  "model_path": "...",
  "result": {
    "suggestions": [ ... ]
  }
}
```

**Actual Result:** _____________________

---

### Test 6: Telemetry Event Logged 📊
**Objective:** Verify `document_analysis_disabled` telemetry fires

**Steps:**
1. Open browser DevTools (F12) → Console tab
2. Click **Analyze** button without text selection
3. Look for telemetry log in console

**Expected Result:**
Console shows:
```javascript
📊 Telemetry: {
  event: 'document_analysis_disabled',
  attempted_mode: 'no_selection',
  selection_length: 0,
  user_id_hash: '...',
  timestamp: '2025-11-12T...'
}
```

**Actual Result:** _____________________

---

### Test 7: Modal Close and Retry Flow ✅
**Objective:** Verify users can recover from no-selection state

**Steps:**
1. Click **Analyze** without selection → modal appears
2. Click **X** or close button to dismiss modal
3. Select text in document
4. Click **Analyze** again

**Expected Result:**
- ✅ Modal closes properly
- ✅ Selection analysis runs successfully after selecting text
- ✅ Suggestions appear

**Actual Result:** _____________________

---

### Test 8: Feature Flag Toggle 🔧
**Objective:** Verify flag can re-enable document analysis (for admins)

**Steps:**
1. Stop backend server
2. Set `ENABLE_DOCUMENT_ANALYSIS=true` in `.env`
3. Restart backend server
4. Run Test 4a again (should now return 200, not 410)

**Expected Result:**
```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "Test", "mode": "document_truncated"}'
```

Returns: **200 OK** (not 410) with analysis result

**Actual Result:** _____________________

**Cleanup:** Set `ENABLE_DOCUMENT_ANALYSIS=false` and restart server

---

## Environment Validation

### Backend Environment Check
```bash
# SSH into backend server or check logs
grep "ENABLE_DOCUMENT_ANALYSIS" logs/startup.log
```

**Expected Output:**
```
🔧 RAG Configuration:
   ...
   ENABLE_DOCUMENT_ANALYSIS: False
```

**Actual Result:** _____________________

---

## Pass/Fail Criteria

### ✅ All Tests Must Pass
- [ ] Test 1: Selection analysis works
- [ ] Test 2: Modal shows guidance (no document options)
- [ ] Test 3: Document buttons hidden
- [ ] Test 4: Backend returns 410 for document modes
- [ ] Test 5: Selection mode still allowed (200 OK)
- [ ] Test 6: Telemetry logged
- [ ] Test 7: Modal close and retry works
- [ ] Test 8: Feature flag toggle works

### 🚨 Failure Response
If any test fails:
1. **Do NOT deploy to production**
2. Check backend logs for errors
3. Verify `ENABLE_DOCUMENT_ANALYSIS=false` is set
4. Verify frontend code deployed correctly
5. Re-run failed test
6. Escalate to development team if still failing

---

## Production Deployment Checklist

Before deploying to production:
- [ ] All smoke tests pass in staging
- [ ] Backend environment has `ENABLE_DOCUMENT_ANALYSIS=false`
- [ ] Frontend bundle deployed
- [ ] Telemetry dashboard configured to monitor `document_analysis_disabled` events
- [ ] User documentation updated
- [ ] Support team briefed on change
- [ ] Rollback plan reviewed and tested

---

## Monitoring Post-Deployment

### First 24 Hours
Monitor these metrics:
- `document_analysis_disabled` event frequency
- API error rates (should not increase)
- Average response time for `/api/analyze?mode=selection` (should decrease)
- User support tickets mentioning "can't analyze document"

### Expected Trends
- 📉 API response times: 30% faster
- 📉 Backend resource usage: 40-50% reduction
- 📈 `document_analysis_disabled` events: Expected for 7-10 days as users adapt
- 📊 User satisfaction: Monitor feedback

### Alert Thresholds
- ⚠️ `document_analysis_disabled` > 100 events/hour → Review user guidance
- 🚨 `/api/analyze` error rate > 5% → Investigate backend issues
- 🚨 Average response time > 15 seconds → Check infrastructure

---

## Contact for Issues

- **Test Failures:** Slack #ilana-engineering
- **Deployment Issues:** DevOps on-call
- **User Reports:** Support team lead

**Smoke Test Version:** 1.0.0
**Last Updated:** 2025-11-12
