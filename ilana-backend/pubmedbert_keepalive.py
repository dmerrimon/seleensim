#!/usr/bin/env python3
"""
PubMedBERT Keep-Alive Service

Pings the PubMedBERT HuggingFace endpoint every 5 minutes to prevent cold starts.
Prevents 503 errors and ensures RAG pipeline always has real embeddings.

Run this as a background process or use a cron job:
- Direct: python pubmedbert_keepalive.py &
- Systemd: Create a service unit
- Cron: */5 * * * * python /path/to/pubmedbert_keepalive.py --once
"""

import os
import time
import requests
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
PUBMEDBERT_ENDPOINT = os.getenv(
    "PUBMEDBERT_ENDPOINT_URL",
    "https://n0m9u56pgan8l9dr.us-east-1.aws.endpoints.huggingface.cloud"
)
HUGGINGFACE_API_KEY = os.getenv(
    "HUGGINGFACE_API_KEY",
    "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"
)
PING_INTERVAL_SECONDS = int(os.getenv("PUBMEDBERT_PING_INTERVAL", "300"))  # 5 minutes
TIMEOUT_SECONDS = 30


def ping_pubmedbert() -> bool:
    """
    Send a lightweight ping to PubMedBERT to keep it warm.

    Returns:
        True if successful, False otherwise
    """
    try:
        headers = {
            "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
            "Content-Type": "application/json"
        }

        # Use short text for minimal processing
        payload = {
            "inputs": "keep warm",
            "parameters": {"return_tensors": True}
        }

        logger.info(f"🏓 Pinging PubMedBERT endpoint...")
        start_time = time.time()

        response = requests.post(
            PUBMEDBERT_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=TIMEOUT_SECONDS
        )

        elapsed_ms = (time.time() - start_time) * 1000

        if response.status_code == 200:
            logger.info(f"✅ PubMedBERT responding ({elapsed_ms:.0f}ms) - endpoint is warm")
            return True
        elif response.status_code == 503:
            logger.warning(f"⚠️ PubMedBERT cold start (503) after {elapsed_ms:.0f}ms - will retry")
            return False
        else:
            logger.error(f"❌ PubMedBERT error: HTTP {response.status_code}")
            return False

    except requests.exceptions.Timeout:
        logger.error(f"❌ PubMedBERT timeout after {TIMEOUT_SECONDS}s")
        return False
    except Exception as e:
        logger.error(f"❌ PubMedBERT ping failed: {type(e).__name__}: {e}")
        return False


def run_keepalive_loop():
    """
    Run continuous keep-alive loop.

    Pings PubMedBERT every PING_INTERVAL_SECONDS to prevent cold starts.
    """
    logger.info(f"🚀 PubMedBERT Keep-Alive Service started")
    logger.info(f"   - Endpoint: {PUBMEDBERT_ENDPOINT}")
    logger.info(f"   - Ping interval: {PING_INTERVAL_SECONDS}s ({PING_INTERVAL_SECONDS / 60:.1f} minutes)")

    consecutive_failures = 0
    max_consecutive_failures = 5

    while True:
        try:
            success = ping_pubmedbert()

            if success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                logger.warning(f"⚠️ Consecutive failures: {consecutive_failures}/{max_consecutive_failures}")

                if consecutive_failures >= max_consecutive_failures:
                    logger.error(f"❌ PubMedBERT unreachable after {max_consecutive_failures} attempts")
                    logger.error("   Consider checking HuggingFace endpoint status or restarting service")
                    # Reset counter but continue trying
                    consecutive_failures = 0

            # Wait before next ping
            logger.info(f"💤 Sleeping for {PING_INTERVAL_SECONDS}s until next ping...")
            time.sleep(PING_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            logger.info("🛑 Keep-alive service stopped by user")
            break
        except Exception as e:
            logger.error(f"❌ Unexpected error in keep-alive loop: {e}")
            time.sleep(60)  # Wait 1 minute before retrying after unexpected error


def run_once():
    """
    Ping PubMedBERT once and exit.

    Useful for cron jobs: */5 * * * * python pubmedbert_keepalive.py --once
    """
    logger.info("🏓 Running single PubMedBERT ping...")
    success = ping_pubmedbert()

    if success:
        logger.info("✅ Ping successful")
        exit(0)
    else:
        logger.error("❌ Ping failed")
        exit(1)


if __name__ == "__main__":
    import sys

    if "--once" in sys.argv:
        run_once()
    else:
        run_keepalive_loop()
