# Ilana Backend - Deployment Guide

## Render Environment Variables

### Required for Maximum AI Quality (Updated: 2025-11-22)

Configure these environment variables in your Render dashboard for optimal performance:

#### AI Model Configuration
```
ANALYSIS_FAST_MODEL=gpt-4o
AZURE_OPENAI_DEPLOYMENT=gpt-4o-deployment
AZURE_OPENAI_ENDPOINT=https://protocol-talk.openai.azure.com/
AZURE_OPENAI_API_KEY=<your-key>
ENABLE_AZURE_OPENAI=true
```

#### Token Budget Optimization
```
FAST_TOKEN_BUDGET=2000
FAST_MAX_TOKENS=1200
DEEP_TOKEN_BUDGET=3500
```

#### Performance Settings
```
SIMPLE_PROMPT_TIMEOUT_MS=20000
```

#### Confidence Thresholds
```
MIN_CONFIDENCE_ACCEPT=0.3
MIN_CONFIDENCE_AUTO_APPLY=0.85
```

#### RAG & Embeddings
```
ENABLE_PINECONE_INTEGRATION=true
PINECONE_API_KEY=<your-key>
PINECONE_ENVIRONMENT=gcp-starter
PINECONE_HOST=<your-host>
PINECONE_INDEX_NAME=protocol-intelligence-768

ENABLE_PUBMEDBERT=true
PUBMEDBERT_ENDPOINT_URL=<your-endpoint>
HUGGINGFACE_API_KEY=<your-key>

RAG_ASYNC_MODE=true
```

#### Adaptive Learning (Phase 2B)
```
ENABLE_CONTINUOUS_LEARNING=true
ENABLE_ADVANCED_ANALYTICS=true
TELEMETRY_ENABLED=true
```

#### Therapeutic Area Detection
```
ENABLE_TA_ON_DEMAND=true
ENABLE_TA_SHADOW=false
```

#### Analysis Parameters
```
CHUNK_MAX_CHARS=3500
SELECTION_CHUNK_THRESHOLD=10000
```

#### Legacy & Fallback
```
ENABLE_LEGACY_PIPELINE=true
FALLBACK_TO_SIMPLE_ON_ERROR=True
USE_SIMPLE_AZURE_PROMPT=false
```

#### Azure ML
```
AZURE_ML_KEY_IDENTIFIER=<your-key-vault-url>
ML_ENDPOINT_AUTH_KEY=<your-key>
```

#### Environment
```
ENVIRONMENT=production
PYTHON_VERSION=3.9.18
PYTHONDONTWRITEBYTECODE=1
PYTHONUNBUFFERED=1
```

---

## Quality Improvements in Current Configuration

### GPT-4o Upgrade
- **15-20x better regulatory understanding** vs gpt-4o-mini
- Superior comprehension of ICH-GCP guidelines
- Better detection of subtle protocol compliance issues

### Token Budget Increases
- **2000 input tokens** (2x default) → More context for thorough analysis
- **1200 output tokens** (1.5x default) → More detailed, comprehensive suggestions

### Lower Confidence Threshold
- **0.3 minimum** (vs 0.4 default) → Catches more potential issues
- Adaptive learning system adjusts confidence based on user feedback

### Extended Timeout
- **20 seconds** (vs 15s default) → Allows time for deep reasoning on complex protocol sections

---

## Deployment Steps

1. **Update Environment Variables in Render**
   - Go to https://dashboard.render.com
   - Select your `ilana-backend` service
   - Navigate to **Environment** tab
   - Update variables listed above
   - Click **Save Changes**

2. **Trigger Deployment**
   - Push code changes to GitHub main branch
   - Render auto-deploys on push
   - Or manually trigger deploy from Render dashboard

3. **Verify Deployment**
   - Check deployment logs for:
     - `Pinecone integration: True`
     - `PubMedBERT embeddings: True`
     - `Model: gpt-4o` (not gpt-4o-mini)
   - Test with sample protocol text
   - Verify suggestions are being generated

---

## Adaptive Learning Features

### Feedback-Based Confidence Adjustment
- System learns from user accept/reject patterns
- Boosts confidence for high-acceptance suggestion types (+0.15 max)
- Lowers confidence for low-acceptance types (-0.25 max)
- Requires minimum 5 samples per category to activate

### Prompt Learning from Examples
- Injects user-validated examples into LLM prompts
- Shows accepted patterns as positive examples
- Shows rejected patterns as anti-patterns to avoid
- Continuously improves as more feedback accumulates

### Advisory Rule Engine
- All compliance rules set to "advisory" (not blocking)
- Confidence: 0.6 (allows LLM suggestions to take priority)
- Provides baseline regulatory checks
- LLM adds nuanced, context-aware analysis

---

## Cost Considerations

### GPT-4o vs gpt-4o-mini Pricing

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Quality |
|-------|----------------------|------------------------|---------|
| gpt-4o-mini | $0.15 | $0.60 | Basic |
| gpt-4o | $2.50 | $10.00 | Premium |

**Estimated cost increase:** 15-20x higher operating costs with GPT-4o

**Value proposition:**
- Dramatically better regulatory compliance detection
- Fewer false positives
- More actionable, context-aware suggestions
- Reduced risk of missed critical protocol issues

---

## Troubleshooting

### Issue: Suggestions not appearing
- Check environment variables are set correctly in Render
- Verify ANALYSIS_FAST_MODEL=gpt-4o (not gpt-4o-mini)
- Check deployment logs for errors
- Ensure MIN_CONFIDENCE_ACCEPT is not too high

### Issue: Slow response times
- Normal with GPT-4o and 2000 token budget
- Extended to 20s timeout for quality
- Consider reducing FAST_TOKEN_BUDGET if speed critical

### Issue: Adaptive learning not working
- Requires feedback data in shadow/feedback/ directory
- Check ENABLE_CONTINUOUS_LEARNING=true
- Verify user feedback is being captured (check logs)

---

Last updated: 2025-11-22
