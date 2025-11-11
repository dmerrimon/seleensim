# Canary Rollout QA Checklist
## acceptSuggestionHandler Phased Deployment

**Version:** 1.0
**Last Updated:** 2025-11-10
**Owner:** Engineering Team

---

## 📋 Overview

This checklist guides the safe rollout of the new `acceptSuggestionHandler` with comprehensive telemetry and RL feedback. The rollout follows a phased approach with hash-based canary routing.

### Rollout Phases
- **Phase 1:** Internal Canary (0-5%) - Week 1
- **Phase 2:** Expand Canary (5-25%) - Week 2
- **Phase 3:** Majority Rollout (25-75%) - Week 3
- **Phase 4:** Full Migration (100%) - Week 4
- **Phase 5:** Cleanup - Week 5

---

## 🔍 Pre-Deployment Checks

### Code Review
- [ ] Review acceptSuggestionHandler implementation (lines ~3045-3190 in taskpane.html)
- [ ] Review doUndoFixed implementation (lines ~3204-3284)
- [ ] Review acceptChangeRouter (lines ~3303-3333)
- [ ] Verify wireAcceptButtons uses router (line ~2576)
- [ ] Verify canaryRolloutPercent initialized to 10 (line ~1117)

### Telemetry Validation
- [ ] Verify all required fields in suggestion_accepted event:
  - suggestion_id, request_id, user_id_hash
  - ta, phase, model_path, analysis_mode
  - latency_ms, accepted_at
  - original_text_hash, improved_text_hash
  - confidence, severity, suggestion_type
  - handler_version, canary flag

- [ ] Verify all required fields in suggestion_undone event:
  - suggestion_id, request_id, user_id_hash
  - ta, phase, undone_at, time_to_undo_ms
  - original_text_hash, improved_text_hash
  - suggestion_type, severity
  - handler_version, canary flag

### PHI Protection
- [ ] Confirm NO raw text in telemetry (only hashes)
- [ ] Confirm redactPHI: true in all RL feedback calls
- [ ] Verify SHA-256 hashing for all text fields
- [ ] Verify context_snippet limited to 200 chars

### Endpoint Usage
- [ ] Accept calls /api/reinforce (positive signal)
- [ ] Undo calls /api/rl/feedback (negative signal)
- [ ] Both endpoints exist and respond correctly

### Test Coverage
- [ ] Run test_telemetry_rl.js (all tests pass)
- [ ] 8 canary routing tests pass
- [ ] SHA-256 hashing tests pass
- [ ] PHI protection tests pass
- [ ] Integration tests pass

---

## 🚀 Phase 1: Internal Canary (0-5%)

### Configuration
```javascript
window.IlanaState.canaryRolloutPercent = 5;  // 5% of users
```

### Pre-Launch Checklist
- [ ] Deploy to staging environment
- [ ] Test with internal user accounts
- [ ] Verify canary routing telemetry appears
- [ ] Check shadow/feedback/ directory for RL event files

### Functionality Tests

#### Accept Change (Word Desktop)
- [ ] Click Accept Change button
- [ ] Text is replaced correctly in document
- [ ] Card shows "Accepted ✓" badge
- [ ] Undo toast appears for 10 seconds
- [ ] Console shows [CANARY] prefix in logs

#### Accept Change (Word Online)
- [ ] Click Accept Change button
- [ ] Text is replaced correctly in document
- [ ] Card shows "Accepted ✓" badge
- [ ] Undo toast appears for 10 seconds

#### Undo Functionality
- [ ] Click Undo within 10 seconds
- [ ] Text reverts to original
- [ ] Card badge removed
- [ ] Accept button re-enabled

### Telemetry Verification
- [ ] Check backend logs for suggestion_accepted events
- [ ] Check backend logs for canary_routing events
- [ ] Verify percentile distribution (expect ~5% canary)
- [ ] Check shadow/feedback/ for reinforcement_*.json files

### RL Feedback Storage
- [ ] Files created in shadow/feedback/
- [ ] Filename format: reinforcement_TIMESTAMP_SUGGESTIONID.json
- [ ] JSON contains all required fields
- [ ] redactPHI: true in all files
- [ ] NO raw text in files (only hashes)

### Error Monitoring
- [ ] Check error logs for Office.js errors
- [ ] Check error logs for suggestion_accept_error events
- [ ] Check error logs for suggestion_undo_error events
- [ ] Error rate < 1%

### Success Criteria
- ✅ No critical errors
- ✅ Accept/Undo works in both Desktop and Online
- ✅ Telemetry shape correct (all fields present)
- ✅ RL events stored in shadow/feedback/
- ✅ NO PHI in any telemetry or RL events
- ✅ Routing percentile matches expected 5%

**Decision:** [ ] PROCEED to Phase 2 | [ ] ROLLBACK (set canary to 0)

---

## 📈 Phase 2: Expand Canary (5-25%)

### Configuration
```javascript
window.IlanaState.canaryRolloutPercent = 25;  // 25% of users
```

### Monitoring (1 week)
- [ ] Daily error rate check (should be < 1%)
- [ ] Daily telemetry completeness check
- [ ] Daily RL event count check
- [ ] Compare suggestion_accepted rates: old vs new handler
- [ ] Compare undo rates: old vs new handler

### Metrics to Track

| Metric | Old Handler | New Handler | Expected |
|--------|-------------|-------------|----------|
| Error Rate | _____% | _____% | < 1% |
| Accept Success Rate | _____% | _____% | > 95% |
| Undo Rate | _____% | _____% | 5-10% |
| Avg Latency (ms) | _____ | _____ | < 500ms |
| Telemetry Complete | _____% | _____% | 100% |
| RL Events Stored | _____ | _____ | 100% |

### User Feedback
- [ ] Check support tickets for accept/undo issues
- [ ] Check user reports of incorrect replacements
- [ ] Check user reports of undo failures

### Success Criteria
- ✅ Error rate stable (< 1%)
- ✅ No increase in support tickets
- ✅ Telemetry metrics comparable to old handler
- ✅ RL events storing correctly
- ✅ Deterministic routing (same users always same handler)

**Decision:** [ ] PROCEED to Phase 3 | [ ] STAY at 25% | [ ] ROLLBACK

---

## 🌐 Phase 3: Majority Rollout (25-75%)

### Configuration
```javascript
window.IlanaState.canaryRolloutPercent = 75;  // 75% of users
```

### Monitoring (1 week)
- [ ] Daily error rate check
- [ ] Daily comparison: old vs new handler metrics
- [ ] Check for any edge cases in logs
- [ ] Verify RL feedback pipeline not overwhelmed

### Scale Testing
- [ ] Check backend load (API requests per minute)
- [ ] Check shadow/feedback/ storage capacity
- [ ] Verify /api/reinforce response times
- [ ] Verify /api/rl/feedback response times

### Success Criteria
- ✅ Error rate remains < 1%
- ✅ No performance degradation
- ✅ Backend handles increased RL event volume
- ✅ User experience consistent with old handler

**Decision:** [ ] PROCEED to Phase 4 | [ ] STAY at 75% | [ ] ROLLBACK

---

## 🎯 Phase 4: Full Migration (100%)

### Configuration
```javascript
window.IlanaState.canaryRolloutPercent = 100;  // All users
```

### Final Validation (1 week)
- [ ] All users on new handler
- [ ] No increase in error rate
- [ ] Telemetry complete for 100% of events
- [ ] RL feedback pipeline stable
- [ ] No user complaints

### Success Criteria
- ✅ Error rate < 1%
- ✅ All telemetry events have correct schema
- ✅ RL events storing successfully
- ✅ No degradation in user experience

**Decision:** [ ] PROCEED to Cleanup | [ ] ROLLBACK

---

## 🧹 Phase 5: Cleanup

### Code Cleanup Tasks
- [ ] Remove old `handleAcceptChange()` function
- [ ] Remove old `handleUndo()` function
- [ ] Remove `acceptChangeRouter()` wrapper
- [ ] Rename `acceptSuggestionHandler` → `handleAcceptChange`
- [ ] Rename `doUndoFixed` → `handleUndo`
- [ ] Update `wireAcceptButtons()` to call handler directly
- [ ] Remove canaryRolloutPercent from window.IlanaState
- [ ] Remove canary: true flags from telemetry
- [ ] Remove handler_version fields from telemetry
- [ ] Remove [CANARY] console.log prefixes

### Test Updates
- [ ] Update test_telemetry_rl.js for single handler
- [ ] Remove canary routing tests
- [ ] Update mock implementations
- [ ] Verify all tests pass

### Documentation Updates
- [ ] Update ACCEPT_CHANGE_IMPLEMENTATION.md
- [ ] Archive this QA checklist
- [ ] Document lessons learned

---

## 🔄 Rollback Procedure

If issues are detected at any phase:

### Immediate Rollback
```javascript
// Set canary percentage to 0 (instant rollback to old handler)
window.IlanaState.canaryRolloutPercent = 0;
```

### Rollback Steps
1. **Deploy config change** (set canaryRolloutPercent = 0)
2. **Verify routing** (check canary_routing telemetry shows 100% old handler)
3. **Monitor errors** (error rate should drop if issue was in new handler)
4. **Investigate logs** (find root cause)
5. **Fix in dev** (address issue locally)
6. **Test fix** (verify fix resolves issue)
7. **Re-deploy** (restart canary at 5%)

### Rollback Triggers
- **Critical:** Error rate > 5%
- **Critical:** Data loss (document corruption)
- **Critical:** PHI leak detected
- **High:** Error rate > 2%
- **High:** User complaints > 5 per day
- **Medium:** Telemetry incomplete > 10%
- **Low:** RL events not storing > 5%

---

## 📊 Monitoring Dashboard

### Telemetry Queries

**Canary Distribution:**
```sql
SELECT
  handler,
  COUNT(*) as count,
  COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () as percent
FROM telemetry
WHERE event = 'canary_routing'
  AND timestamp > NOW() - INTERVAL '1 day'
GROUP BY handler;
```

**Error Rate by Handler:**
```sql
SELECT
  CASE
    WHEN handler_version = 'acceptSuggestionHandler_v1' THEN 'NEW'
    ELSE 'OLD'
  END as handler,
  COUNT(CASE WHEN event LIKE '%_error' THEN 1 END) * 100.0 / COUNT(*) as error_rate
FROM telemetry
WHERE event IN ('suggestion_accepted', 'suggestion_accept_error')
  AND timestamp > NOW() - INTERVAL '1 day'
GROUP BY handler;
```

**Undo Rate by Handler:**
```sql
SELECT
  CASE
    WHEN handler_version LIKE '%_v1' THEN 'NEW'
    ELSE 'OLD'
  END as handler,
  COUNT(CASE WHEN event = 'suggestion_undone' THEN 1 END) * 100.0 /
    COUNT(CASE WHEN event = 'suggestion_accepted' THEN 1 END) as undo_rate
FROM telemetry
WHERE timestamp > NOW() - INTERVAL '1 day'
GROUP BY handler;
```

**RL Event Storage:**
```bash
# Check shadow/feedback/ directory
ls -lh /path/to/ilana-backend/shadow/feedback/
wc -l /path/to/ilana-backend/shadow/feedback/reinforcement_*.json
wc -l /path/to/ilana-backend/shadow/feedback/rl_feedback_*.json
```

---

## ✅ Sign-Off

### Phase 1 Approval
- [ ] QA Lead: _________________ Date: _______
- [ ] Engineering Lead: _________________ Date: _______

### Phase 2 Approval
- [ ] QA Lead: _________________ Date: _______
- [ ] Engineering Lead: _________________ Date: _______

### Phase 3 Approval
- [ ] QA Lead: _________________ Date: _______
- [ ] Engineering Lead: _________________ Date: _______
- [ ] Product Manager: _________________ Date: _______

### Phase 4 Approval
- [ ] QA Lead: _________________ Date: _______
- [ ] Engineering Lead: _________________ Date: _______
- [ ] Product Manager: _________________ Date: _______

### Phase 5 Completion
- [ ] Engineering Lead: _________________ Date: _______
- [ ] Cleanup verified by: _________________ Date: _______

---

## 📝 Notes & Lessons Learned

### Issues Encountered


### Resolutions


### Recommendations for Future Rollouts


---

**END OF CHECKLIST**
