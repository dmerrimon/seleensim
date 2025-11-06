#!/usr/bin/env python3
"""
Test Azure OpenAI Connection
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / "config" / "environments" / "production.env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Loaded environment from {env_path}")
else:
    print(f"❌ Environment file not found at {env_path}")

# Test imports
try:
    from openai import AzureOpenAI
    print("✅ AzureOpenAI import successful")
except ImportError as e:
    print(f"❌ AzureOpenAI import failed: {e}")
    sys.exit(1)

# Get configuration
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
api_key = os.getenv("AZURE_OPENAI_API_KEY")
deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")

print(f"🔍 Endpoint: {endpoint}")
print(f"🔍 API Key: {'SET' if api_key else 'NOT SET'} (length: {len(api_key) if api_key else 0})")
print(f"🔍 Deployment: {deployment}")

if not all([endpoint, api_key, deployment]):
    print("❌ Missing required configuration")
    sys.exit(1)

# Test connection
try:
    print("🔄 Creating Azure OpenAI client...")
    client = AzureOpenAI(
        api_key=api_key,
        api_version="2024-02-01",
        azure_endpoint=endpoint
    )
    print("✅ Client created successfully")
    
    print("🔄 Testing connection with models.list()...")
    models = client.models.list()
    model_list = list(models)
    print(f"✅ Connection successful - {len(model_list)} models available")
    
    if model_list:
        print("Available models:")
        for model in model_list[:3]:  # Show first 3 models
            print(f"  - {model.id}")
    
    print("🔄 Testing chat completion...")
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'Azure OpenAI is working!'"}
        ],
        max_tokens=50
    )
    print(f"✅ Chat completion successful: {response.choices[0].message.content}")
    
except Exception as e:
    print(f"❌ Azure OpenAI test failed: {type(e).__name__}: {e}")
    print(f"❌ Full error: {str(e)}")