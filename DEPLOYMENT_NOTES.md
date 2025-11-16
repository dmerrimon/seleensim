# Deployment Notes

## Option 1: Disable PubMedBERT and Pinecone (Short-term Stabilization)

The code has been updated to support environment-based control of PubMedBERT and Pinecone services.

### Required Render Environment Variable Updates

To disable PubMedBERT and Pinecone and eliminate 404 errors:

1. Go to Render Dashboard: https://dashboard.render.com
2. Select your service: `ilana-backend`
3. Navigate to **Environment** tab
4. Add or update these environment variables:

```
ENABLE_PUBMEDBERT=false
ENABLE_PINECONE_INTEGRATION=false
```

5. Click **Save Changes**
6. Render will automatically redeploy with the new settings

### What This Does

When these environment variables are set to `false`:

- ✅ No HTTP calls to HuggingFace PubMedBERT endpoint (eliminates 404 errors)
- ✅ No Pinecone import/initialization attempts (eliminates import errors)
- ✅ System falls back to Azure GPT-4 + local medical intelligence patterns
- ✅ Production logs remain clean without service errors
- ✅ /health/services endpoint reflects disabled services accurately

### Expected Log Output After Update

After deploying with disabled services, you should see:

```
🔧 Enterprise feature flags: Pinecone=False, PubMedBERT=False
ℹ️ Pinecone disabled via ENABLE_PINECONE_INTEGRATION=false; skipping vector DB initialization
ℹ️ PubMedBERT disabled via ENABLE_PUBMEDBERT=false; skipping inference endpoint initialization
```

### Verification

After deployment, test the health endpoint:

```bash
curl https://ilanalabs-add-in.onrender.com/health/services
```

Expected response:
```json
{
  "status": "healthy",
  "services": {
    "azure_openai": {
      "status": "configured",
      "enabled": "true"
    },
    "pinecone": {
      "status": "configured",
      "enabled": "false"
    },
    "pubmedbert": {
      "status": "configured",
      "enabled": "false"
    }
  }
}
```

### System Still Works

Even with PubMedBERT and Pinecone disabled, the system continues to:

- ✅ Analyze clinical protocols using Azure GPT-4
- ✅ Provide regulatory suggestions (ICH-GCP, FDA, EMA)
- ✅ Detect therapeutic areas
- ✅ Generate improvement suggestions
- ✅ Return 200 OK responses

The only difference is the system uses Azure GPT-4 + local medical patterns instead of the full RAG stack.

---

## Option 2: Fix HuggingFace and Pinecone Integration

**Status:** CODE COMPLETE (Commit 317ae611) - Configuration Required

### Implementation Summary

The HuggingFace PubMedBERT fix has been implemented and deployed to commit `317ae611`.

**Changes Made:**

1. **HuggingFace API Fix** (`legacy_pipeline_backup/optimized_real_ai_service.py` lines 933-986):
   - Changed endpoint from `POST {endpoint}/analyze` to `POST {endpoint}` (root)
   - Simplified payload to HuggingFace format: `{"inputs": "text"}`
   - Updated response parser to handle classification, NER, and embeddings formats
   - Added proper error handling and timeout configuration

2. **Environment-Based Routing** (already implemented in previous commits):
   - `USE_SIMPLE_AZURE_PROMPT=false` enables legacy mode
   - `ENABLE_PUBMEDBERT=true/false` controls PubMedBERT feature
   - `ENABLE_PINECONE_INTEGRATION=true/false` controls Pinecone feature

### CRITICAL: Render Dashboard Configuration Required

**The code is deployed, but environment variables MUST be manually configured in Render dashboard.**

Environment variables in `render.yaml` are NOT automatically applied when creating new services.

#### Step-by-Step Instructions

1. **Go to Render Dashboard**
   - URL: https://dashboard.render.com
   - Select your service: `ilana-backend-v2`

2. **Navigate to Environment Tab**
   - Click on "Environment" in the left sidebar

3. **Configure Critical Routing Variable**

   **MOST CRITICAL - Add this first:**
   ```
   Key:   USE_SIMPLE_AZURE_PROMPT
   Value: false
   ```

   This enables legacy mode (PubMedBERT + Pinecone + Azure). Without this, the system defaults to simple Azure-only mode.

4. **Configure Feature Flags**

   ```
   Key:   ENABLE_AZURE_OPENAI
   Value: true

   Key:   ENABLE_PUBMEDBERT
   Value: true

   Key:   ENABLE_PINECONE_INTEGRATION
   Value: true
   ```

5. **Configure Azure OpenAI Credentials**

   **Mark these as "Secret" in Render:**
   ```
   Key:   AZURE_OPENAI_API_KEY
   Value: <your_azure_openai_api_key>
   Secret: ✓

   Key:   AZURE_OPENAI_ENDPOINT
   Value: https://<your-resource>.openai.azure.com/
   Secret: ✓

   Key:   AZURE_OPENAI_DEPLOYMENT
   Value: <your_deployment_name>
   Secret: ✓
   ```

6. **Configure PubMedBERT/HuggingFace Credentials**

   **Mark these as "Secret" in Render:**
   ```
   Key:   PUBMEDBERT_ENDPOINT_URL
   Value: https://<your-endpoint>.endpoints.huggingface.cloud
   Secret: ✓

   Key:   HUGGINGFACE_API_KEY
   Value: hf_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
   Secret: ✓
   ```

7. **Configure Pinecone Credentials**

   **Mark these as "Secret" in Render:**
   ```
   Key:   PINECONE_API_KEY
   Value: <your_pinecone_api_key>
   Secret: ✓

   Key:   PINECONE_ENVIRONMENT
   Value: <your_pinecone_environment>
   Secret: ✓

   Key:   PINECONE_INDEX_NAME
   Value: protocol-intelligence-768
   Secret: ✓
   ```

8. **Configure System Variables**

   ```
   Key:   ENVIRONMENT
   Value: production

   Key:   CACHE_BUST_VERSION
   Value: NOV15_2024_OPTION2_HUGGINGFACE_FIX

   Key:   PYTHON_VERSION
   Value: 3.11

   Key:   PYTHONDONTWRITEBYTECODE
   Value: 1

   Key:   PYTHONUNBUFFERED
   Value: 1
   ```

9. **Save and Deploy**
   - Click "Save Changes"
   - Render will automatically redeploy with the new environment variables

### Verification After Deployment

#### Check Startup Logs

After deployment completes, verify you see these logs (in order):

```
🚨🚨🚨 [MAIN_PY_DEPLOYMENT_MARKER_NOV15_2024] Application starting 🚨🚨🚨
🔧 RAG Configuration:
   RAG_ASYNC_MODE: True
   RAG_ASYNC_ALLOW_SYNC: False
   USE_SIMPLE_AZURE_PROMPT: False  ← CRITICAL: Must be False
   ENABLE_TA_ON_DEMAND: True

🔄 ADAPTER: Routing to legacy enterprise pipeline  ← Confirms legacy mode active
✅ ADAPTER: Legacy pipeline imported successfully

🚨🚨🚨 [DEPLOYMENT_V3_NOV16_2024_CACHE_CLEAR] Enterprise initialization 🚨🚨🚨  ← NEW MARKER
🔧 Enterprise feature flags: Pinecone=True, PubMedBERT=True  ← Confirms features enabled
🔧 USE_SIMPLE_AZURE_PROMPT=false  ← Confirms routing variable is correct

✅ PubMedBERT inference endpoint configured: https://xxx.endpoints.huggingface.cloud
✅ Pinecone vector DB initialized: protocol-intelligence-768

INFO:     Application startup complete.
```

**If you see the OLD marker `[DEPLOYMENT_MARKER_V2_NOV14_23:00]` instead of `[DEPLOYMENT_V3_NOV16_2024_CACHE_CLEAR]`, that proves Render is using cached bytecode. Manual redeploy required.**

#### Test Health Endpoint

```bash
curl https://ilanalabs-add-in.onrender.com/health/services
```

Expected response with Option 2 enabled:

```json
{
  "status": "healthy",
  "services": {
    "azure_openai": {
      "status": "configured",
      "enabled": "true"
    },
    "pinecone": {
      "status": "configured",
      "enabled": "true"
    },
    "pubmedbert": {
      "status": "configured",
      "enabled": "true"
    }
  }
}
```

### Troubleshooting

#### Issue: Still seeing old deployment marker after Git push

**Symptom:** Logs show `[DEPLOYMENT_MARKER_V2_NOV14_23:00]` instead of `[DEPLOYMENT_V3_NOV16_2024_CACHE_CLEAR]`

**Cause:** Render is using cached Python bytecode (.pyc files) instead of recompiling from source

**Fix:**
1. Go to Render Dashboard → Your Service
2. Click **Manual Deploy** → **Clear build cache & deploy**
3. Wait for deployment to complete
4. Check logs for `[DEPLOYMENT_V3_NOV16_2024_CACHE_CLEAR]` marker
5. If STILL showing old marker after cache clear, contact Render support (rare but possible)

**Alternative Fix (if dashboard cache clear doesn't work):**
1. Go to Render Dashboard → Environment tab
2. Add a temporary variable: `FORCE_REBUILD=1`
3. Click Save Changes (triggers redeploy)
4. After successful deployment, remove `FORCE_REBUILD` variable

#### Issue: Logs show "Simple mode active, legacy pipeline bypassed"

**Symptom:** You see this log instead of "Routing to legacy enterprise pipeline"

**Cause:** `USE_SIMPLE_AZURE_PROMPT` is `true` or not set in Render environment

**Fix:**
1. Go to Render Dashboard → Environment tab
2. Verify `USE_SIMPLE_AZURE_PROMPT=false` is present
3. If missing, add it and redeploy
4. Check logs again for "Routing to legacy enterprise pipeline"

#### Issue: Missing "Enterprise feature flags" log

**Symptom:** No log showing `Pinecone=True, PubMedBERT=True`

**Cause:** Legacy pipeline not being used (see issue above)

**Fix:** Same as above - ensure `USE_SIMPLE_AZURE_PROMPT=false`

#### Issue: PubMedBERT still returning 404 errors

**Symptom:** Logs show 404 errors when calling PubMedBERT endpoint

**Possible Causes:**
1. Using old code (before commit 317ae611)
2. Wrong endpoint URL configured

**Fix:**
1. Verify Render is using commit 317ae611 or later
2. Verify `PUBMEDBERT_ENDPOINT_URL` does NOT have `/analyze` at the end
3. Test endpoint manually: `curl -X POST https://your-endpoint.endpoints.huggingface.cloud -H "Authorization: Bearer $HUGGINGFACE_API_KEY" -d '{"inputs": "medical text"}'`

#### Issue: Pinecone import errors

**Symptom:** `cannot import name 'cached_download' from 'huggingface_hub'`

**Cause:** Pinecone client library dependency issue

**Fix:**
1. Set `ENABLE_PINECONE_INTEGRATION=false` to disable temporarily
2. Or update Pinecone client library version in requirements.txt

### Complete Checklist Reference

See `RENDER_ENV_CHECKLIST.md` for a complete checklist of all environment variables with checkboxes.

### Pinecone Import Fix (Future Work)

**Current Issue:**
`cannot import name 'cached_download' from 'huggingface_hub'`

**Future Fix:**
Replace `cached_download` with `hf_hub_download` in Pinecone initialization code if this error occurs.

---

## Deployment Strategy

### Current Status (Nov 15, 2024)

**Option 2 Code: COMPLETE** (Commit 317ae611)
- HuggingFace PubMedBERT API fix implemented
- Response parser updated for HuggingFace formats
- Environment-based routing working correctly
- Code deployed to `ilana-backend-v2` service

**Configuration: IN PROGRESS**
- Environment variables need to be manually configured in Render dashboard
- See "Step-by-Step Instructions" above

### Deployment Options

**Option 1: Stable Azure-Only Mode (Quick Fix)**
- Set `USE_SIMPLE_AZURE_PROMPT=true` in Render (or leave unset)
- Set `ENABLE_PUBMEDBERT=false` and `ENABLE_PINECONE_INTEGRATION=false`
- System uses only Azure GPT-4
- No 404 or import errors
- Good for immediate stabilization

**Option 2: Full Enterprise RAG Stack (Recommended)**
- Set `USE_SIMPLE_AZURE_PROMPT=false` in Render ← **CRITICAL**
- Set `ENABLE_PUBMEDBERT=true` and `ENABLE_PINECONE_INTEGRATION=true`
- Configure all Azure, HuggingFace, and Pinecone credentials
- Full RAG stack with medical domain embeddings and vector search
- Follow "Step-by-Step Instructions" above

### Next Steps

1. **If choosing Option 1 (Azure-only):**
   - Go to Render dashboard
   - Set `USE_SIMPLE_AZURE_PROMPT=true` (or leave unset - defaults to true)
   - System is stable, no further action needed

2. **If choosing Option 2 (Full RAG):**
   - Follow "Step-by-Step Instructions" in Option 2 section above
   - Configure all environment variables in Render dashboard
   - Verify deployment using logs and health endpoint
   - Monitor for any errors in first 24 hours

---

## Commit Reference

### Option 1 Implementation (Environment Flags)

**Commit:** `5f2129f2`

Files modified:
- `ilana-backend/legacy_pipeline_backup/config_loader.py` - Added ENABLE_PUBMEDBERT config field
- `ilana-backend/legacy_pipeline_backup/optimized_real_ai_service.py` - Read flags from config, added guards
- `ilana-backend/main.py` - Updated health endpoint to reflect service status

### Option 2 Implementation (HuggingFace API Fix)

**Initial Implementation Commit:** `f59a2a5b`
- Fixed HuggingFace PubMedBERT endpoint from `/analyze` to root
- Simplified payload to `{"inputs": "text"}` format
- Updated response parser for HuggingFace formats
- Updated cache bust in render.yaml

**Service Rename Commit:** `ff40a2d2`
- Renamed service from `ilana-backend` to `ilana-backend-v2`
- Attempted to bypass Render caching issues

**Final Implementation Commit:** `317ae611`
- Added version comment to force Docker layer invalidation
- All Option 2 code changes verified working

**Bytecode Cache Fix Commit:** `147a64d9` ← **DEPLOY THIS**
- Changed feature flags log from INFO to WARNING level (ensures visibility in Render logs)
- Added explicit USE_SIMPLE_AZURE_PROMPT value logging
- Updated deployment marker to V3_NOV16_2024
- Added Python bytecode cache deletion: `/opt/render/.cache/Python*`
- Updated cache bust version to NOV16_2024_BYTECODE_CLEAR
- Added `RENDER_ENV_CHECKLIST.md` with complete environment variable checklist
- Updated `render.yaml` with clear documentation
- Updated `DEPLOYMENT_NOTES.md` with step-by-step Render dashboard instructions
- **This is the current production commit - deploy this to fix bytecode caching issue**

### Files Modified for Option 2

- `ilana-backend/legacy_pipeline_backup/optimized_real_ai_service.py` (lines 1-7, 933-986)
  - Version marker and HuggingFace API fix
- `render.yaml` (lines 1-30, 58-82)
  - Documentation and environment variable comments
- `DEPLOYMENT_NOTES.md` (Option 2 section)
  - Complete deployment and troubleshooting guide
- `RENDER_ENV_CHECKLIST.md` (NEW)
  - Environment variable configuration checklist
