# Regulatory Knowledge Base Deployment Guide

## Overview
This guide walks through deploying the Ilana backend with the regulatory knowledge base (FDA guidance + ICH guidelines) to Render.

## Prerequisites
- Render account with existing `ilana-backend` service
- Environment variables configured in Render dashboard:
  - `PINECONE_API_KEY`
  - `PINECONE_INDEX_NAME` (should be: `protocol-intelligence-768`)
  - `AZURE_OPENAI_API_KEY`
  - `AZURE_OPENAI_ENDPOINT`
  - `HUGGINGFACE_API_KEY`
  - `PUBMEDBERT_ENDPOINT_URL`

## Step 1: Deploy Code Changes

### 1.1 Push Latest Code
```bash
git push origin main
```

This deploys:
- GPT-4o model upgrade
- Enhanced system prompts with citation requirements
- Dual-namespace RAG (protocol + regulatory)
- Regulatory indexer script
- 6 enhanced few-shot examples

### 1.2 Verify Deployment
Wait for Render to complete the deployment (check Render Dashboard > Logs).

## Step 2: Upload Regulatory Data Files

The regulatory indexer needs access to:
- `data/data/fda_guidance_chunks/` (830 files)
- `data/data/ich_e6_requirements.json`
- `data/data/ICH/` (11 PDF files)

**Option A: Include in Git Repository** (Recommended for initial setup)
```bash
# From ilana-backend directory
git add ../data/data/fda_guidance_chunks/
git add ../data/data/ich_e6_requirements.json
git add ../data/data/ICH/
git commit -m "Add regulatory data files for indexing"
git push
```

**Option B: Upload via Render Shell** (If files too large for git)
Use Render's shell feature to upload files directly to the server.

## Step 3: Run Regulatory Indexer (One-Time Operation)

### 3.1 Access Render Shell
1. Go to Render Dashboard
2. Select `ilana-backend` service
3. Click "Shell" tab at top
4. Wait for shell to connect

### 3.2 Run the Indexer
```bash
# Set environment variables (if not already set)
export PINECONE_API_KEY="<your-pinecone-api-key>"

# Run the indexer (this will take 15-20 minutes)
python regulatory_indexer.py --index-all
```

This will:
1. Load PubMedBERT model (~500 MB, first time only)
2. Process 830 FDA guidance chunks → Pinecone
3. Process ICH E6 JSON requirements → Pinecone
4. Extract text from 11 ICH guideline PDFs → ~1000-1500 chunks → Pinecone
5. Verify indexing with test queries

### 3.3 Expected Output
```
🔧 Initializing Pinecone connection...
🧠 Loading PubMedBERT embedding model...
✅ Initialization complete

📚 Indexing FDA Guidance Documents...
   Found 830 FDA guidance chunks
   ✅ Indexed 50/830 chunks...
   ✅ Indexed 100/830 chunks...
   ...
   ✅ Successfully indexed 830 FDA guidance chunks

📚 Indexing ICH E6 Requirements...
   ✅ Successfully indexed 156 ICH requirements

📚 Indexing ICH Guideline PDFs...
   Found 11 ICH guideline PDFs

   📖 Processing ich-e-1-population-exposure... (1/11)
   📄 Created 45 chunks
   ✅ Completed: 45 chunks

   📖 Processing ich-e9-r1-addendum... (8/11)
   📄 Created 128 chunks
   ✅ Completed: 128 chunks
   ...

   ✅ Successfully indexed 1247 chunks from 11 ICH guideline PDFs

🔍 Verifying regulatory indexing...
   ✅ Found 2233 vectors in regulatory-guidance namespace

   🧪 Testing regulatory query...
   Found 3 relevant regulatory documents:

   1. ICH E9
      Section: 5.7
      Score: 0.892
      Preview: Pre-specification of the analysis...

✅ Verification complete
```

### 3.4 Troubleshooting

**Error: ModuleNotFoundError**
```bash
pip install -r requirements.txt
```

**Error: Data directory not found**
Verify the data files were uploaded correctly:
```bash
ls -la ../data/data/fda_guidance_chunks/ | head
ls -la ../data/data/ICH/
```

**Error: Pinecone connection failed**
Check environment variables:
```bash
echo $PINECONE_API_KEY
python -c "import os; from pinecone import Pinecone; pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY')); print('✅ Connected')"
```

## Step 4: Verify RAG is Working

### 4.1 Test via API
```bash
curl -X POST https://your-app.onrender.com/analyze-selection \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Subjects will be enrolled based on inclusion criteria.",
    "request_id": "test_regulatory_rag"
  }'
```

### 4.2 Check Logs for Regulatory Citations
Look for log entries like:
```
✅ [test_regulatory_rag] Retrieved 3 exemplars + 2 regulatory citations
```

### 4.3 Verify Response Contains Specific Citations
The analysis response should now include specific regulatory references in rationales:
- "ICH E6(R3) Section 1.58 requires..."
- "ICH E9 Section 5.7 mandates pre-specification..."
- "FDA Statistical Guidance Section 3.4.2 requires..."

## Step 5: Production Rollout

Once verified in staging:

### 5.1 Update .env Configuration
Set the following in Render environment variables:
```
ANALYSIS_FAST_MODEL=gpt-4o
FAST_MAX_TOKENS=2000
FAST_TOKEN_BUDGET=1000
ENABLE_PINECONE_INTEGRATION=true
```

### 5.2 Monitor Performance
- Check latency impact (RAG adds ~500-800ms for dual queries)
- Verify cost increase (~$0.10 per analysis with GPT-4o vs ~$0.005 with mini)
- Monitor quality improvement in user feedback

### 5.3 Gradual Rollout (Optional)
Add feature flag for gradual rollout:
```
ENABLE_REGULATORY_RAG=true
REGULATORY_RAG_ROLLOUT_PERCENT=10  # Start with 10% of requests
```

## Maintenance

### Re-indexing
If you add new regulatory documents:
```bash
# Index only new FDA documents
python regulatory_indexer.py --index-fda

# Index only new ICH PDFs
python regulatory_indexer.py --index-ich-pdfs

# Verify
python regulatory_indexer.py --verify
```

### Monitoring Pinecone Usage
```python
from pinecone import Pinecone
pc = Pinecone(api_key="...")
index = pc.Index("protocol-intelligence-768")
stats = index.describe_index_stats()
print(stats["namespaces"]["regulatory-guidance"]["vector_count"])
```

Expected vector counts:
- FDA guidance: ~830 vectors
- ICH E6 JSON: ~150 vectors
- ICH PDFs: ~1200-1500 vectors
- **Total regulatory namespace: ~2200-2500 vectors**
- Protocol exemplars (default namespace): ~53,848 vectors

## Cost Estimates

### One-Time Indexing Cost
- Compute: ~15-20 minutes on Render = minimal
- Pinecone storage: 2500 vectors × 768 dims = negligible (included in free tier)
- PubMedBERT inference: Free (using HuggingFace Inference API)

### Ongoing Costs
- **Per analysis with regulatory RAG:**
  - GPT-4o: ~$0.10 per analysis (2000 tokens input, 600 tokens output)
  - Pinecone queries: 2 queries per analysis (included in free tier up to 100K requests/month)
  - PubMedBERT embedding: 1 embedding per analysis (free)

- **Cost increase from GPT-4o-mini:**
  - Previous: ~$0.005 per analysis
  - New: ~$0.10 per analysis
  - **20x increase, but enterprise-quality regulatory citations**

### Pricing Strategy
With improved quality and regulatory citations:
- Justify premium tier: $50-100/month (vs $10-20/month basic)
- Cost per analysis: $0.10
- Break-even: ~500-1000 analyses/month per user
- Target: Clinical research organizations, large pharma

## Success Metrics

Track improvement in:
- **Regulatory citation specificity**: % of suggestions with section numbers (target: >80%)
- **User acceptance rate**: % of suggestions accepted (target: +15-20% improvement)
- **Time saved**: Reduction in protocol review time
- **Compliance quality**: Fewer regulatory deficiencies in submissions

## Rollback Plan

If issues occur:
```bash
# 1. Revert to GPT-4o-mini
# In Render dashboard, set:
ANALYSIS_FAST_MODEL=gpt-4o-mini
FAST_MAX_TOKENS=1500

# 2. Disable regulatory RAG
ENABLE_PINECONE_INTEGRATION=false

# 3. Re-deploy previous commit
git revert HEAD~6..HEAD
git push
```

## Support

For issues:
- Check Render logs: Dashboard > Logs
- Verify Pinecone status: https://status.pinecone.io/
- Test locally: `python regulatory_indexer.py --verify`
