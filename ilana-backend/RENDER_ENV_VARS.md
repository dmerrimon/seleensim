# Required Render Environment Variables

## For Legacy Pipeline to work, set ALL of these in your Render dashboard:

### Azure OpenAI (REQUIRED - already working)
```
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-4o-deployment
```

### Pinecone (REQUIRED for RAG)
```
PINECONE_API_KEY=your-pinecone-key
PINECONE_ENVIRONMENT=gcp-starter
PINECONE_INDEX_NAME=protocol-intelligence-768
```

### PubMedBERT (REQUIRED for medical embeddings)
```
HUGGINGFACE_API_KEY=your-huggingface-key
PUBMEDBERT_ENDPOINT_URL=https://api-inference.huggingface.co/models/microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext
```

### Legacy Pipeline Control
```
ENABLE_LEGACY_PIPELINE=true
```

## How to Check

1. Go to Render dashboard → Your service → Environment
2. Verify ALL variables above are set with actual values (not empty)
3. After adding/changing variables, Render auto-redeploys
4. Check deployment logs for errors

## Debugging

If pinecone_enabled is still false after setting these:

1. Check Render logs for:
   - `ValueError: Required environment variable missing: PINECONE_API_KEY`
   - `⚠️ Pinecone initialization failed:`

2. Test the variables are accessible:
   ```python
   import os
   print(os.getenv("PINECONE_API_KEY"))  # Should NOT be None or ""
   ```
