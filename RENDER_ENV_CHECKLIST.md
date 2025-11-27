# Render Environment Variables Checklist

This document lists ALL environment variables that must be manually configured in the Render dashboard when creating a new service.

**IMPORTANT:** Environment variables in `render.yaml` are NOT automatically applied when creating a new service. You must manually configure them in the Render dashboard.

## How to Configure

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Select your service (e.g., `ilana-backend-v2`)
3. Navigate to **Environment** tab
4. Click **Add Environment Variable** for each variable below
5. Click **Save Changes**
6. Render will automatically redeploy with the new settings

---

## Critical Routing Variables

These control which pipeline is used:

- [ ] **USE_SIMPLE_AZURE_PROMPT** = `false`
  - **CRITICAL:** Must be `false` to enable legacy mode (PubMedBERT + Pinecone + Azure)
  - If `true` or missing, system uses simple Azure-only mode and ignores all enterprise features

---

## Feature Flags

Control which components are enabled in legacy mode:

- [ ] **ENABLE_AZURE_OPENAI** = `true`
  - Enables Azure OpenAI GPT-4 integration

- [ ] **ENABLE_PINECONE_INTEGRATION** = `true`
  - Enables Pinecone vector database for RAG retrieval
  - Set to `false` to disable Pinecone (Option 1 stabilization)

- [ ] **ENABLE_PUBMEDBERT** = `true`
  - Enables PubMedBERT medical domain inference
  - Set to `false` to disable PubMedBERT (Option 1 stabilization)

---

## Azure OpenAI Credentials

**Required when ENABLE_AZURE_OPENAI=true**

- [ ] **AZURE_OPENAI_API_KEY** = `<your_azure_openai_api_key>`
  - Secret: Mark as secret in Render
  - Do NOT commit to Git

- [ ] **AZURE_OPENAI_ENDPOINT** = `https://<your-resource>.openai.azure.com/`
  - Secret: Mark as secret in Render
  - Example: `https://ilana-openai.openai.azure.com/`

- [ ] **AZURE_OPENAI_DEPLOYMENT** = `<your_deployment_name>`
  - Secret: Mark as secret in Render
  - Example: `gpt-4o-deployment`, `gpt-4-32k`, etc.

---

## PubMedBERT / HuggingFace Credentials

**Required when ENABLE_PUBMEDBERT=true**

- [ ] **PUBMEDBERT_ENDPOINT_URL** = `https://api-inference.huggingface.co/models/<your-endpoint>`
  - Secret: Mark as secret in Render
  - Example: `https://abc123xyz.us-east-1.aws.endpoints.huggingface.cloud`
  - Must be a valid HuggingFace Inference Endpoint URL

- [ ] **HUGGINGFACE_API_KEY** = `hf_<your_api_key>`
  - Secret: Mark as secret in Render
  - Do NOT commit to Git
  - Format: `hf_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`

---

## Pinecone Vector Database Credentials

**Required when ENABLE_PINECONE_INTEGRATION=true**

- [ ] **PINECONE_API_KEY** = `<your_pinecone_api_key>`
  - Secret: Mark as secret in Render
  - Do NOT commit to Git

- [ ] **PINECONE_ENVIRONMENT** = `<your_pinecone_environment>`
  - Secret: Mark as secret in Render
  - Example: `us-east-1-aws`, `gcp-starter`, etc.

- [ ] **PINECONE_INDEX_NAME** = `protocol-intelligence-768`
  - Secret: Mark as secret in Render
  - Must match your existing Pinecone index name
  - Default: `protocol-intelligence-768`

---

## System Configuration

- [ ] **ENVIRONMENT** = `production`
  - Options: `development`, `production`, `testing`

- [ ] **CACHE_BUST_VERSION** = `NOV15_2024_OPTION2_HUGGINGFACE_FIX`
  - Used to force cache invalidation during deployment
  - Update this when you need to force a fresh build

- [ ] **PYTHON_VERSION** = `3.11`
  - Python runtime version

- [ ] **PYTHONDONTWRITEBYTECODE** = `1`
  - Prevents Python from writing .pyc files

- [ ] **PYTHONUNBUFFERED** = `1`
  - Forces Python output to be unbuffered (better for logs)

---

## Verification

After configuring all environment variables and deploying, verify the configuration by checking the logs for these markers:

### Expected Startup Logs

```
🚨🚨🚨 [MAIN_PY_DEPLOYMENT_MARKER_NOV15_2024] Application starting 🚨🚨🚨
🔧 RAG Configuration:
   RAG_ASYNC_MODE: True
   RAG_ASYNC_ALLOW_SYNC: False
   USE_SIMPLE_AZURE_PROMPT: False  ← MUST be False for legacy mode
   ENABLE_TA_ON_DEMAND: True
```

If using legacy mode, you should also see:

```
🔄 ADAPTER: Routing to legacy enterprise pipeline
✅ ADAPTER: Legacy pipeline imported successfully
🚨🚨🚨 [DEPLOYMENT_MARKER_V2_NOV14_23:00] Enterprise stack initialization starting 🚨🚨🚨
🔧 Enterprise feature flags: Pinecone=True, PubMedBERT=True
```

### If ENABLE_PUBMEDBERT=true:

```
✅ PubMedBERT inference endpoint configured: https://xxx.endpoints.huggingface.cloud
```

### If ENABLE_PINECONE_INTEGRATION=true:

```
✅ Pinecone vector DB initialized: protocol-intelligence-768
```

### Test the Health Endpoint

```bash
curl https://your-service.onrender.com/health/services
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
      "enabled": "true"
    },
    "pubmedbert": {
      "status": "configured",
      "enabled": "true"
    }
  }
}
```

---

## Common Issues

### Issue: Logs show "Simple mode active, legacy pipeline bypassed"

**Cause:** `USE_SIMPLE_AZURE_PROMPT` is `true` or not set

**Fix:** Set `USE_SIMPLE_AZURE_PROMPT=false` in Render dashboard and redeploy

### Issue: Missing "Enterprise feature flags" log

**Cause:** Legacy pipeline not being used (see issue above)

**Fix:** Ensure `USE_SIMPLE_AZURE_PROMPT=false`

### Issue: PubMedBERT 404 errors

**Cause:** Using old `/analyze` endpoint path

**Fix:** Ensure you're using commit `317ae611` or later which uses HuggingFace root endpoint

### Issue: Pinecone import errors

**Cause:** Missing `huggingface_hub` dependency or using deprecated import

**Fix:** Ensure `requirements.txt` has correct dependencies and `ENABLE_PINECONE_INTEGRATION` is properly set

---

## Quick Reference - Your Actual Values

**For ilanalabs-add-in service** (copy these exact values):

### Azure OpenAI
```
AZURE_OPENAI_API_KEY=77E50MKmkSJRfCB7ivtrQbDvU9Wn8wOuFMPuzsrxy5xWR9ROINv1JQQJ99BKACYeBjFXJ3w3AAABACOGDKMT
AZURE_OPENAI_ENDPOINT=https://protocol-talk.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o-deployment
ENABLE_AZURE_OPENAI=true
```

### Pinecone
```
PINECONE_API_KEY=pcsk_4Vp5Xw_6ucBVe9wAfcf1qBewRAxs9gzCNJrq3ZvDpQCZo5hG2zNsXum12LvsMJA2wBxQTn
PINECONE_ENVIRONMENT=gcp-starter
PINECONE_HOST=https://clinical-protocols-gdwejfu.svc.eastus2-5e25.prod-azure.pinecone.io
PINECONE_INDEX_NAME=protocol-intelligence-768
ENABLE_PINECONE_INTEGRATION=true
```

### HuggingFace/PubMedBERT
```
PUBMEDBERT_ENDPOINT_URL=https://dk8e3vdcuov185qm.us-east-1.aws.endpoints.huggingface.cloud
HUGGINGFACE_API_KEY=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
ENABLE_PUBMEDBERT=true
```

### Model Configuration
```
ANALYSIS_FAST_MODEL=gpt-4o-deployment
FAST_TOKEN_BUDGET=2000
FAST_MAX_TOKENS=1500
DEEP_TOKEN_BUDGET=3500
```

### Confidence & Performance
```
MIN_CONFIDENCE_ACCEPT=0.3
MIN_CONFIDENCE_AUTO_APPLY=0.85
SIMPLE_PROMPT_TIMEOUT_MS=20000
CHUNK_MAX_CHARS=3500
SELECTION_CHUNK_THRESHOLD=10000
```

### Feature Flags
```
USE_SIMPLE_AZURE_PROMPT=false
ENABLE_CONTINUOUS_LEARNING=true
ENABLE_ADVANCED_ANALYTICS=true
ENABLE_TA_ON_DEMAND=true
ENABLE_TA_SHADOW=false
ENABLE_LEGACY_PIPELINE=true
FALLBACK_TO_SIMPLE_ON_ERROR=true
RAG_ASYNC_MODE=true
TELEMETRY_ENABLED=true
```

### Python Environment
```
PYTHON_VERSION=3.11
PYTHONDONTWRITEBYTECODE=1
PYTHONUNBUFFERED=1
ENVIRONMENT=production
```

### ChromaDB
```
ANONYMIZED_TELEMETRY=False
CHROMA_TELEMETRY_DISABLED=True
```

---

## Quick Copy-Paste for Render Dashboard

**Manual Steps:**
1. Go to Render Dashboard → `ilanalabs-add-in` → Environment tab
2. For each variable above, click "Add Environment Variable"
3. Copy variable name and value exactly as shown
4. Mark API keys as "Secret" (checkbox in Render UI)
5. Click "Save Changes" (Render will auto-deploy)
