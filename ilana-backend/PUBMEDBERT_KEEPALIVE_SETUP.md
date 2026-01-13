# PubMedBERT Keep-Alive Setup

## Problem Summary

**Issue**: PubMedBERT HuggingFace endpoint goes into "cold start" (503 errors) when unused, causing RAG pipeline to fail and return 0 suggestions.

**Root Cause**: When PubMedBERT is unavailable, the system uses a "fallback" embedding that generates semantically meaningless vectors. These fake embeddings query Pinecone and return irrelevant protocol examples, causing GPT-4o to generate 0 suggestions.

**Solution**: Keep PubMedBERT warm by pinging it every 5 minutes.

---

## Deployment Options

### Option 1: Render Background Worker (Recommended for Production)

Add PubMedBERT keep-alive as a background worker in your Render service:

1. **Create/Update `Procfile`** in your repository root:
   ```
   web: gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120 --workers 2
   keepalive: python3 pubmedbert_keepalive.py
   ```

2. **In Render Dashboard:**
   - Go to your `ilana-backend` service
   - Click "Settings" → "Environment"
   - Add environment variable:
     - Key: `PUBMEDBERT_PING_INTERVAL`
     - Value: `300` (5 minutes)

3. **Enable the background worker:**
   - Render will automatically detect the `keepalive` process in Procfile
   - It will run continuously alongside your web server
   - Logs will appear in the main service logs with prefix `[keepalive]`

4. **Deploy:**
   - Commit and push changes
   - Render will auto-deploy with both processes running

**Cost**: No additional cost - background workers run on the same instance as your web service.

---

### Option 2: Separate Render Background Worker Service

Create a dedicated background worker service:

1. **In Render Dashboard:**
   - Click "New +" → "Background Worker"
   - Name: `ilana-pubmedbert-keepalive`
   - Environment: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python3 pubmedbert_keepalive.py`

2. **Set Environment Variables:**
   - Copy all env vars from your main service
   - Required:
     - `PUBMEDBERT_ENDPOINT_URL`
     - `HUGGINGFACE_API_KEY`
     - `PUBMEDBERT_PING_INTERVAL=300`

3. **Deploy:**
   - Render will start the background worker
   - Check logs to confirm pings are working

**Cost**: Additional $7/month for separate worker instance (if using paid plan).

---

### Option 3: Local Cron Job (Development Only)

For local development or testing:

1. **Test the script:**
   ```bash
   cd /Users/donmerriman/Ilana/ilana-backend
   python3 pubmedbert_keepalive.py --once
   ```

2. **Set up cron job:**
   ```bash
   # Edit crontab
   crontab -e

   # Add this line (pings every 5 minutes)
   */5 * * * * cd /Users/donmerriman/Ilana/ilana-backend && python3 pubmedbert_keepalive.py --once >> /tmp/pubmedbert_keepalive.log 2>&1
   ```

3. **Verify cron is running:**
   ```bash
   tail -f /tmp/pubmedbert_keepalive.log
   ```

**Note**: This only works when your local machine is running. Not suitable for production.

---

## Testing & Verification

### 1. Verify Keep-Alive is Running

**Render Logs:**
```bash
# Look for these log lines every 5 minutes:
🏓 Pinging PubMedBERT endpoint...
✅ PubMedBERT responding (220ms) - endpoint is warm
💤 Sleeping for 300s until next ping...
```

### 2. Verify RAG is Using Real Embeddings

**Test the Word Add-In:**
1. Select text containing "subjects" (should be "participants")
2. Click "Analyze Selection"
3. Check Render logs for:
   ```
   ⚡ Fast analysis start: fast_xxx (mode=LLM-only)
   🔍 Fetching RAG exemplars from Pinecone
   ✅ Retrieved 3 exemplars from Pinecone
   ```

4. **Key Check**: Look for this line - it should NOT appear:
   ```
   ⚠️ PubMedBERT unavailable, using enhanced fallback  ❌ BAD
   ```

5. **Instead, you should see:**
   ```
   ✅ PubMedBERT embedding successful  ✓ GOOD
   ```

### 3. Verify Suggestions are Generated

**Browser Console:**
```javascript
✅ Fast analysis selection result: Object
  - Suggestions array: Array(1)  // NOT Array(0)!
  - Suggestion: "Replace 'subjects' with 'participants' per ICH E6(R3)"
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PUBMEDBERT_ENDPOINT_URL` | (from .env) | HuggingFace endpoint URL |
| `HUGGINGFACE_API_KEY` | (from .env) | HuggingFace API key |
| `PUBMEDBERT_PING_INTERVAL` | `300` | Seconds between pings (5 min recommended) |

### Adjusting Ping Interval

**Too Frequent** (< 2 minutes):
- May hit HuggingFace rate limits
- Wastes resources

**Too Infrequent** (> 10 minutes):
- Endpoint may still go cold between pings
- HuggingFace pause threshold is ~5-15 minutes

**Recommended**: 300 seconds (5 minutes)

---

## Troubleshooting

### Issue: Keep-Alive Logs Show 503 Errors

**Symptoms:**
```
⚠️ PubMedBERT cold start (503) after 10000ms - will retry
⚠️ Consecutive failures: 3/5
```

**Possible Causes:**
1. HuggingFace endpoint is paused/stopped
2. Ping interval too long (endpoint still going cold)
3. HuggingFace billing issue

**Solutions:**
1. Check HuggingFace endpoint status in dashboard
2. Reduce `PUBMEDBERT_PING_INTERVAL` to 180 seconds (3 minutes)
3. Verify HuggingFace account is active

---

### Issue: Keep-Alive Stops Running

**Symptoms:**
- No keep-alive logs in Render
- Analysis starts showing "enhanced fallback" again

**Solutions:**

**Option 1 - Check Procfile:**
```bash
# Verify Procfile exists and has keepalive process
cat Procfile
```

**Option 2 - Check Render Dashboard:**
- Go to service → "Processes"
- Verify `keepalive` process is listed and "Running"

**Option 3 - Restart Service:**
- In Render dashboard, click "Manual Deploy" → "Clear build cache & deploy"

---

### Issue: Still Getting 0 Suggestions After Keep-Alive

**Debug Steps:**

1. **Check if PubMedBERT is being used:**
   ```
   # Should see in Render logs:
   ✅ PubMedBERT embedding successful  ← Good!

   # Should NOT see:
   ⚠️ PubMedBERT unavailable, using enhanced fallback  ← Bad!
   ```

2. **Check RAG retrieval results:**
   ```
   # Should see in logs:
   ✅ Retrieved 3 exemplars from Pinecone

   # Check if exemplars are relevant:
   - Exemplar 1: "Participants will be randomized..." ← Good!
   - Exemplar 1: "Lorem ipsum dolor sit amet..." ← Bad (irrelevant)
   ```

3. **Check GPT-4o response:**
   ```
   # Should see:
   📊 Generated 1-3 AI suggestions

   # Should NOT see:
   📊 Generated 0 AI suggestions  ← Issue is in LLM prompt, not RAG
   ```

---

## Alternative Solution: Increase PubMedBERT Retry Timeout

If keep-alive doesn't solve the problem, you can increase the timeout to allow cold starts to complete:

**Edit `fast_rag.py` line 90-93:**
```python
# Current:
PUBMEDBERT_RETRY_DELAYS = [500, 1000, 2000]  # ms

# Change to (allow longer warm-up):
PUBMEDBERT_RETRY_DELAYS = [2000, 5000, 10000]  # 2s, 5s, 10s
```

**Trade-off**: First request after cold start will take 15-20 seconds, but will succeed instead of falling back to fake embeddings.

---

## Success Metrics

**Before Keep-Alive:**
- Response time: 30ms (cache hit) or 4000ms (cold start fail)
- PubMedBERT errors: Multiple 503s per hour
- Fallback embeddings used: 30-50% of requests
- Suggestions generated: 0-1 per request

**After Keep-Alive:**
- Response time: 2000-3000ms (full RAG + LLM)
- PubMedBERT errors: <1% (only during HuggingFace outages)
- Fallback embeddings used: <1%
- Suggestions generated: 1-3 per request (accurate)

---

## Deployment Checklist

- [ ] Create `pubmedbert_keepalive.py` in repository root
- [ ] Create or update `Procfile` with `keepalive` process
- [ ] Set `PUBMEDBERT_PING_INTERVAL=300` in Render environment
- [ ] Commit and push changes to GitHub
- [ ] Verify Render auto-deploys with keepalive process
- [ ] Check Render logs for keep-alive ping messages
- [ ] Test Word add-in selection analysis
- [ ] Verify 0 "enhanced fallback" warnings in logs
- [ ] Verify suggestions are being generated (Array(1+), not Array(0))

---

## Recommended: Option 1 (Procfile Background Worker)

**Next Steps:**
1. Create `Procfile` (if it doesn't exist) or update existing one
2. Add `keepalive: python3 pubmedbert_keepalive.py` line
3. Commit and push
4. Monitor Render logs for keep-alive pings

This ensures PubMedBERT stays warm 24/7 and your RAG pipeline always gets real, semantically meaningful embeddings for accurate protocol example retrieval.
