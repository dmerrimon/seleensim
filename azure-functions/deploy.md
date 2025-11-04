# Azure Functions Deployment Guide

## Quick Deployment Commands

1. **Login to Azure:**
```bash
az login
```

2. **Create Resource Group:**
```bash
az group create --name ilana-rg --location westus2
```

3. **Create Storage Account:**
```bash
az storage account create --name ilanastorage$(date +%s) --location westus2 --resource-group ilana-rg --sku Standard_LRS
```

4. **Create Function App:**
```bash
az functionapp create --resource-group ilana-rg --consumption-plan-location westus2 --runtime python --runtime-version 3.9 --functions-version 4 --name ilana-functions-$(date +%s) --storage-account ilanastorage$(date +%s)
```

5. **Deploy Functions:**
```bash
func azure functionapp publish ilana-functions-YOUR_SUFFIX
```

6. **Set Environment Variables:**
```bash
az functionapp config appsettings set --name ilana-functions-YOUR_SUFFIX --resource-group ilana-rg --settings \
    AZURE_OPENAI_ENDPOINT="your_endpoint_here" \
    AZURE_OPENAI_KEY="your_key_here" \
    PINECONE_API_KEY="your_pinecone_key_here" \
    PINECONE_ENVIRONMENT="your_pinecone_env_here"
```

## Alternative: Use Azure Portal

1. Go to [Azure Portal](https://portal.azure.com)
2. Create new Function App
3. Choose Python 3.9 runtime
4. Use Consumption plan for cost efficiency
5. Deploy using VS Code Azure Functions extension

## Performance Benefits vs Render

- **Cold Start**: ~2-3x faster than Render
- **Scaling**: Automatic scaling to handle traffic spikes
- **Global**: Deploy to multiple regions
- **Cost**: Pay only for execution time
- **Monitoring**: Built-in Application Insights

## Expected Performance Improvements

- **Render**: 30-60 second timeouts, slow cold starts
- **Azure Functions**: 5-15 second responses, faster cold starts
- **Chunked Analysis**: 3 chunks max vs 6 chunks = 50% faster
- **Auto-scaling**: No more server overload issues

## Frontend Integration

After deployment, update your frontend endpoint:

```javascript
// In ilana-comprehensive.js
const API_BASE_URL = 'https://ilana-functions-YOUR_SUFFIX.azurewebsites.net/api';
```

## Testing the Deployment

1. **Health Check:**
```bash
curl https://ilana-functions-YOUR_SUFFIX.azurewebsites.net/api/health
```

2. **Analyze Test:**
```bash
curl -X POST "https://ilana-functions-YOUR_SUFFIX.azurewebsites.net/api/analyze-comprehensive" \
  -H "Content-Type: application/json" \
  -d '{"text": "This is a test protocol for clinical trial analysis."}'
```

## Monitoring

- View logs in Azure Portal > Function App > Functions > Monitor
- Application Insights provides detailed performance metrics
- Set up alerts for errors or performance issues