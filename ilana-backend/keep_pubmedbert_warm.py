#!/usr/bin/env python3
"""
PubMedBERT Keep-Alive Script
Prevents HuggingFace serverless endpoint from going to sleep

Run this as a background job or cron task to keep endpoint warm
"""

import os
import time
import requests
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
PUBMEDBERT_ENDPOINT = os.getenv("PUBMEDBERT_ENDPOINT_URL", "https://dk8e3vdcuov185qm.us-east-1.aws.endpoints.huggingface.cloud")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")
PING_INTERVAL_SECONDS = 600  # 10 minutes
WARMUP_TEXT = "clinical trial protocol"

def ping_endpoint():
    """Send a lightweight request to keep endpoint warm"""
    try:
        headers = {
            "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {"inputs": WARMUP_TEXT}

        response = requests.post(
            PUBMEDBERT_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            logger.info(f"✅ [{datetime.now().strftime('%H:%M:%S')}] PubMedBERT endpoint warm")
            return True
        elif response.status_code == 503:
            logger.warning(f"⚠️ [{datetime.now().strftime('%H:%M:%S')}] PubMedBERT cold start detected, warming up...")
            # Wait for it to warm up
            time.sleep(30)
            # Try again
            response2 = requests.post(PUBMEDBERT_ENDPOINT, headers=headers, json=payload, timeout=30)
            if response2.status_code == 200:
                logger.info(f"✅ [{datetime.now().strftime('%H:%M:%S')}] PubMedBERT endpoint warmed successfully")
                return True
            else:
                logger.error(f"❌ [{datetime.now().strftime('%H:%M:%S')}] PubMedBERT failed to warm: {response2.status_code}")
                return False
        else:
            logger.error(f"❌ [{datetime.now().strftime('%H:%M:%S')}] PubMedBERT error: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"❌ [{datetime.now().strftime('%H:%M:%S')}] PubMedBERT ping failed: {e}")
        return False

def run_keep_alive():
    """Main keep-alive loop"""
    logger.info("🔥 PubMedBERT Keep-Alive started")
    logger.info(f"   Endpoint: {PUBMEDBERT_ENDPOINT}")
    logger.info(f"   Ping interval: {PING_INTERVAL_SECONDS}s ({PING_INTERVAL_SECONDS // 60} minutes)")

    # Initial warmup
    logger.info("🔄 Initial warmup...")
    ping_endpoint()

    # Keep-alive loop
    while True:
        time.sleep(PING_INTERVAL_SECONDS)
        ping_endpoint()

if __name__ == "__main__":
    if not HUGGINGFACE_API_KEY:
        logger.error("❌ HUGGINGFACE_API_KEY not set")
        exit(1)

    run_keep_alive()
