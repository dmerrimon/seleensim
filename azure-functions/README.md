# Ilana Azure Functions Deployment

This directory contains the Azure Functions version of the Ilana Protocol Intelligence API, converted from FastAPI for better performance and scalability.

## Setup

1. Install Azure Functions Core Tools:
```bash
npm install -g azure-functions-core-tools@4 --unsafe-perm true
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables in `local.settings.json`:
```json
{
  "Values": {
    "AZURE_OPENAI_ENDPOINT": "your_endpoint_here",
    "AZURE_OPENAI_KEY": "your_key_here",
    "PINECONE_API_KEY": "your_pinecone_key_here",
    "PINECONE_ENVIRONMENT": "your_pinecone_env_here"
  }
}
```

## Local Development

Start the Azure Functions runtime locally:
```bash
func start
```

The API will be available at `http://localhost:7071`

## Endpoints

- `GET /api/health` - Health check
- `POST /api/analyze-comprehensive` - Comprehensive protocol analysis
- `POST /api/analyze-protocol` - Multi-modal protocol analysis
- `POST /api/user-feedback` - Submit user feedback

## Deployment

1. Create Azure Function App:
```bash
az functionapp create --resource-group myResourceGroup --consumption-plan-location westus --runtime python --runtime-version 3.9 --functions-version 4 --name myFunctionApp --storage-account mystorageaccount
```

2. Deploy:
```bash
func azure functionapp publish myFunctionApp
```

3. Configure environment variables in Azure portal or using Azure CLI:
```bash
az functionapp config appsettings set --name myFunctionApp --resource-group myResourceGroup --settings AZURE_OPENAI_ENDPOINT=your_endpoint
```

## Performance Benefits

- **Cold start optimization**: ~2-3x faster than Render
- **Auto-scaling**: Handles traffic spikes automatically  
- **Global distribution**: Deploy to multiple regions
- **Built-in monitoring**: Application Insights integration
- **Cost-effective**: Pay only for execution time

## Frontend Integration

Update your frontend to use the Azure Functions endpoint:
```javascript
const AZURE_API_BASE = 'https://your-function-app.azurewebsites.net/api';
```