# Ilana Simple Azure Prompt - Canary Rollout Plan

## Overview
This document outlines the 10-step canary rollout plan for deploying the `USE_SIMPLE_AZURE_PROMPT` feature to production. The rollout will gradually increase traffic exposure while monitoring key metrics to ensure system stability and performance.

## Success Criteria
- **Parse Success Rate**: >= 98%
- **Median Latency**: < 2000ms
- **Error Rate**: < 2%
- **User Acceptance Rate**: >= 85% (suggestions accepted vs ignored)

## Rollback Criteria
- Parse success rate drops below 95%
- Median latency exceeds 3000ms
- Error rate exceeds 5%
- More than 3 critical user reports in 24 hours

---

## Step 1: Pre-Deployment Validation (Day 0)
**Duration**: 2 hours  
**Traffic**: 0%

### Actions:
1. Deploy `recommend_simple.py` to staging environment
2. Verify `/api/recommend-language-simple` endpoint responds correctly
3. Run integration tests with `golden_model_outputs.txt`
4. Validate telemetry logging is working correctly
5. Confirm rollback procedures are ready

### Validation:
```bash
# Test simple endpoint
curl -X POST http://staging.ilana.com/api/recommend-language-simple \
  -H "Content-Type: application/json" \
  -d '{"text":"Patient receives trastuzumab therapy","ta":"oncology"}'

# Verify telemetry
tail -f ./logs/ilana_telemetry.log | grep "MODEL_CALL_SUCCESS"
```

### Success Criteria:
- All staging tests pass
- Telemetry logs are generating correctly
- Response time < 1500ms in staging

---

## Step 2: Deploy to Production (Disabled)
**Duration**: 1 hour  
**Traffic**: 0%

### Actions:
1. Deploy `recommend_simple.py` to production
2. Deploy `guaranteed_suggestions.py` to production
3. Deploy updated adapters (`optimized_real_ai_service.py`, etc.)
4. Set `USE_SIMPLE_AZURE_PROMPT=false` globally
5. Verify all legacy endpoints still function normally

### Validation:
- Legacy `/analyze-comprehensive` endpoint works unchanged
- No increase in error rates
- Telemetry confirms `model_path=legacy` for all requests

### Success Criteria:
- Zero impact on existing functionality
- All health checks pass
- Legacy pipeline performance unchanged

---

## Step 3: Enable for Internal Users (1% Traffic)
**Duration**: 4 hours  
**Traffic**: 1% (internal users only)

### Actions:
1. Create internal user allowlist in configuration
2. Set `USE_SIMPLE_AZURE_PROMPT=true` for allowlisted users
3. Monitor internal user sessions closely
4. Collect feedback from internal teams

### Monitoring:
```sql
-- Monitor parse success rate
SELECT 
  model_path,
  AVG(CASE WHEN parse_success THEN 1.0 ELSE 0.0 END) as parse_success_rate,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY latency_ms) as median_latency_ms,
  COUNT(*) as request_count
FROM telemetry_logs 
WHERE timestamp >= NOW() - INTERVAL '1 hour'
GROUP BY model_path;
```

### Success Criteria:
- Parse success rate >= 98%
- Median latency < 2000ms
- No critical errors reported
- Internal user feedback positive

---

## Step 4: Canary Rollout - 5% Traffic
**Duration**: 24 hours  
**Traffic**: 5%

### Actions:
1. Enable simple prompt for 5% of production traffic using feature flag
2. Implement A/B testing logic in frontend (`isSimpleAzurePromptEnabled()`)
3. Monitor telemetry dashboard continuously
4. Set up automated alerting for metric thresholds

### Monitoring Dashboard:
- **Parse Success Rate**: Real-time graph (simple vs legacy)
- **Latency Distribution**: P50, P95, P99 metrics
- **Error Rate**: 5-minute rolling average
- **Suggestion Count**: Average suggestions per request
- **User Acceptance Rate**: Accept vs ignore actions

### Alert Thresholds:
- Parse success < 96% for 5 minutes → Page on-call
- Median latency > 2500ms for 10 minutes → Alert team
- Error rate > 3% for 5 minutes → Page on-call

### Success Criteria:
- All success criteria met for 24 hours
- No increase in user complaints
- Telemetry shows stable performance

---

## Step 5: Increase to 15% Traffic
**Duration**: 48 hours  
**Traffic**: 15%

### Actions:
1. Increase feature flag percentage to 15%
2. Continue monitoring all metrics
3. Begin collecting user feedback surveys
4. Monitor backend resource utilization

### Additional Monitoring:
- Azure OpenAI API quotas and throttling
- Simple endpoint response time trends
- Database performance (if applicable)
- Memory and CPU utilization

### Success Criteria:
- All core metrics remain within thresholds
- User satisfaction surveys >= 4.2/5.0
- No resource constraints observed
- Backend costs within 5% of baseline

---

## Step 6: Increase to 35% Traffic
**Duration**: 72 hours  
**Traffic**: 35%

### Actions:
1. Increase feature flag to 35%
2. Perform load testing on simple endpoint
3. Optimize any performance bottlenecks found
4. Document any operational learnings

### Load Testing:
```bash
# Simulate peak traffic
ab -n 1000 -c 50 -H "Content-Type: application/json" \
   -p test_payload.json http://api.ilana.com/api/recommend-language-simple
```

### Success Criteria:
- System handles increased load without degradation
- Parse success rate maintains >= 98%
- Cost per request within acceptable range
- No customer escalations

---

## Step 7: Increase to 65% Traffic
**Duration**: 96 hours  
**Traffic**: 65%

### Actions:
1. Increase feature flag to 65%
2. Monitor for any edge cases or unusual patterns
3. Compare business metrics (user engagement, retention)
4. Prepare documentation for full rollout

### Business Metrics:
- Time spent per session
- Suggestions accepted per user
- Document analysis completion rate
- User retention metrics

### Success Criteria:
- Technical metrics stable
- Business metrics show neutral or positive impact
- Support ticket volume unchanged
- Team confidence high for full rollout

---

## Step 8: Full Rollout - 100% Traffic
**Duration**: 7 days  
**Traffic**: 100%

### Actions:
1. Set `USE_SIMPLE_AZURE_PROMPT=true` globally
2. Monitor closely for 48 hours
3. Begin planning legacy system deprecation
4. Document rollout success and learnings

### Extended Monitoring:
- Weekly performance reports
- User satisfaction tracking
- Cost analysis and optimization
- Planning for legacy code removal

### Success Criteria:
- All metrics stable at 100% traffic
- User experience equivalent or improved
- System performing within all thresholds
- Team ready to deprecate legacy pipeline

---

## Step 9: Legacy System Deprecation Planning
**Duration**: 14 days  
**Traffic**: 100% simple

### Actions:
1. Create deprecation timeline for legacy pipeline
2. Remove legacy code from adapters (keep TODO comments)
3. Update documentation and runbooks
4. Plan final cleanup activities

### Cleanup Tasks:
- Remove `legacy_pipeline_backup/` after 30 days
- Update monitoring dashboards
- Archive legacy telemetry data
- Update deployment procedures

---

## Step 10: Rollout Complete
**Duration**: Ongoing  
**Traffic**: 100% simple (legacy removed)

### Actions:
1. Remove feature flags and adapter code
2. Simplify codebase by removing legacy references
3. Conduct post-rollout review meeting
4. Document final performance metrics and improvements

### Final Success Validation:
- Parse success rate >= 98% sustained
- Median latency < 2000ms sustained
- User satisfaction maintained or improved
- Operational costs optimized
- Team velocity improved with simpler codebase

---

## Rollback Procedures

### Immediate Rollback (< 5 minutes)
```bash
# Emergency rollback - disable simple prompt globally
kubectl patch configmap ilana-config -p '{"data":{"USE_SIMPLE_AZURE_PROMPT":"false"}}'
kubectl rollout restart deployment/ilana-backend
```

### Partial Rollback (< 15 minutes)
```bash
# Reduce traffic percentage
curl -X POST https://api.flagsmith.com/api/v1/flags/simple-azure-prompt/ \
  -H "Authorization: Bearer $FLAGSMITH_TOKEN" \
  -d '{"percentage_allocation": 5}'
```

### Full Rollback (< 30 minutes)
1. Set feature flag to 0% traffic
2. Revert to previous deployment version
3. Verify legacy pipeline performance
4. Communicate rollback status to stakeholders

## Communication Plan

### Stakeholders:
- Engineering Team
- Product Management
- Customer Success
- Executive Leadership

### Updates:
- **Daily**: Engineering team standup updates
- **Step completion**: Slack notification to #ilana-rollout
- **Issues**: Immediate Slack alert + email to stakeholders
- **Completion**: Post-rollout summary report

## Emergency Contacts

- **On-call Engineer**: +1-xxx-xxx-xxxx
- **Tech Lead**: @tech-lead-slack
- **Product Manager**: @pm-slack
- **Escalation**: @engineering-manager