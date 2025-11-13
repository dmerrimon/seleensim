# PubMedBERT Endpoint Update

## Change Summary

**Date:** 2024-11-12
**Type:** Configuration Update
**Impact:** Production and Development environments

---

## Updated Endpoint URL

**Old Endpoint (Azure):**
```
https://usz78oxlybv4xfh2.eastus.azure.endpoints.huggingface.cloud
```

**New Endpoint (AWS US-East-1):**
```
https://dk8e3vdcuov185qm.us-east-1.aws.endpoints.huggingface.cloud
```

**Endpoint Management:**
https://endpoints.huggingface.co/dmerriman/endpoints/ilana-pubmedbert-handler-fsm

---

## Files Updated

### 1. Development Environment
**File:** `config/environments/development.env`
```bash
# PubmedBERT Configuration
PUBMEDBERT_ENDPOINT_URL=https://dk8e3vdcuov185qm.us-east-1.aws.endpoints.huggingface.cloud
HUGGINGFACE_API_KEY=<your_huggingface_api_key>
```

### 2. Production Environment
**File:** `config/environments/production.env`
```bash
# PubmedBERT Configuration
PUBMEDBERT_ENDPOINT_URL=https://dk8e3vdcuov185qm.us-east-1.aws.endpoints.huggingface.cloud
HUGGINGFACE_API_KEY=<your_huggingface_api_key>
```

### 3. Sample Configuration
**File:** `.env.sample`
```bash
# === Integration Configuration ===
# PubMed BERT (for medical NER and embeddings)
PUBMEDBERT_ENDPOINT_URL=https://dk8e3vdcuov185qm.us-east-1.aws.endpoints.huggingface.cloud
HUGGINGFACE_API_KEY=your_huggingface_api_key_here
```

---

## What Changed

- **Region:** Azure East US → AWS US-East-1
- **Endpoint ID:** `usz78oxlybv4xfh2` → `dk8e3vdcuov185qm`
- **Provider:** Azure Hugging Face Endpoints → AWS Hugging Face Endpoints

---

## Impact

### Affected Components
- ✅ PubMedBERT embeddings generation
- ✅ Medical NER (Named Entity Recognition)
- ✅ Semantic search with Pinecone
- ✅ RAG (Retrieval-Augmented Generation) pipeline

### Expected Improvements
- 🚀 **Latency:** Potentially lower latency from AWS US-East-1
- 💪 **Reliability:** AWS infrastructure benefits
- 💰 **Cost:** May vary based on AWS vs Azure pricing

---

## Deployment Steps

### Local Development

1. **Pull latest changes:**
```bash
git pull origin main
```

2. **Verify environment variables:**
```bash
cd ilana-backend
grep PUBMEDBERT config/environments/development.env
```

Expected output:
```
PUBMEDBERT_ENDPOINT_URL=https://dk8e3vdcuov185qm.us-east-1.aws.endpoints.huggingface.cloud
```

3. **Restart backend server:**
```bash
python3 main.py
```

4. **Test endpoint:**
```bash
# The server should log successful connection to new endpoint
tail -f logs/ilana.log | grep -i pubmedbert
```

---

### Production Deployment (Render)

1. **Update environment variable on Render:**
   - Go to Render Dashboard
   - Navigate to `ilana-backend` service
   - Update environment variable:
     - Key: `PUBMEDBERT_ENDPOINT_URL`
     - Value: `https://dk8e3vdcuov185qm.us-east-1.aws.endpoints.huggingface.cloud`

2. **Trigger redeployment:**
   - Render will automatically redeploy when environment changes
   - Or manually trigger: Deploy → Deploy Latest Commit

3. **Verify deployment:**
```bash
curl https://your-backend.onrender.com/health
```

---

## Testing

### 1. Health Check
```bash
curl http://127.0.0.1:8000/health
```

Expected: Server responds with `200 OK`

### 2. Embeddings Test
```bash
curl -X POST http://127.0.0.1:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Patients will receive chemotherapy treatment.",
    "mode": "selection"
  }'
```

Expected: Analysis completes without errors

### 3. Check Logs
```bash
tail -f logs/ilana.log | grep -i "pubmedbert\|embedding"
```

Expected logs:
- No connection errors
- Successful embedding generation
- Response times within normal range

---

## Rollback Plan

If issues occur, revert to old Azure endpoint:

```bash
# In config/environments/development.env and production.env
PUBMEDBERT_ENDPOINT_URL=https://usz78oxlybv4xfh2.eastus.azure.endpoints.huggingface.cloud
```

Then restart the service.

---

## Monitoring

### Metrics to Watch

1. **Endpoint Health:**
   - Monitor Hugging Face endpoint dashboard
   - Check for 5xx errors or timeouts

2. **Response Times:**
   - Embeddings generation latency
   - Overall analysis pipeline speed

3. **Error Rates:**
   - Check for increased 500/502/503 errors
   - Monitor failed embedding requests

### Hugging Face Endpoint Dashboard
https://endpoints.huggingface.co/dmerriman/endpoints/ilana-pubmedbert-handler-fsm

**Monitor:**
- Request count
- Latency (p50, p95, p99)
- Error rate
- Throughput

---

## FAQ

### Q: Why migrate from Azure to AWS?
A: Potential benefits in latency, cost, and reliability. AWS US-East-1 may provide better performance for our use case.

### Q: Will this break existing functionality?
A: No. The endpoint interface remains the same; only the URL changes.

### Q: What if the new endpoint fails?
A: Follow the rollback plan to revert to the Azure endpoint immediately.

### Q: Do users need to update anything?
A: No. This is a backend configuration change invisible to frontend users.

### Q: How long is the migration?
A: Zero downtime. Services update configuration and restart automatically.

---

## Verification Checklist

After deployment, verify:

- [ ] Backend service starts without errors
- [ ] Health check endpoint responds 200 OK
- [ ] Test analysis request completes successfully
- [ ] No PubMedBERT connection errors in logs
- [ ] Embedding generation works correctly
- [ ] Response times are within acceptable range
- [ ] No increase in error rates
- [ ] Hugging Face dashboard shows healthy metrics

---

## Support

**Endpoint Issues:**
- Hugging Face Support: https://huggingface.co/support
- Endpoint Dashboard: https://endpoints.huggingface.co/dmerriman/endpoints/ilana-pubmedbert-handler-fsm

**Backend Issues:**
- Check logs: `logs/ilana.log`
- GitHub Issues: https://github.com/dmerrimon/ilanalabs-add-in/issues

---

**Status:** ✅ Updated
**Applied:** Development ✅ | Production ✅ | Sample Config ✅
**Tested:** Pending production deployment

**Updated by:** Claude Code
**Date:** 2024-11-12
