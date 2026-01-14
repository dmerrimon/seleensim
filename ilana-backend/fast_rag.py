#!/usr/bin/env python3
"""
Fast RAG Module - Lightweight Retrieval-Augmented Generation for Fast Path

Provides quick Pinecone + PubMedBERT integration for fast analysis:
- PubMedBERT embeddings with exponential backoff retry (3 attempts)
- Pinecone query for top 3 exemplars (2s timeout)
- Fallback to enhanced clinical embeddings if PubMedBERT unavailable
- Graceful degradation if Pinecone fails
"""

import os
import asyncio
import aiohttp
import logging
import time
from typing import List, Dict, Any, Optional
import hashlib
import math

logger = logging.getLogger(__name__)

# Configuration
PUBMEDBERT_ENDPOINT = os.getenv("PUBMEDBERT_ENDPOINT_URL", "")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "protocol-intelligence-768")

# Fast path RAG limits
FAST_RAG_TOP_K = 3  # Only top 3 exemplars for speed
FAST_RAG_REGULATORY_TOP_K = 2  # Top 2 regulatory citations
FAST_RAG_TIMEOUT_MS = 2000  # 2s timeout for RAG query
PUBMEDBERT_RETRY_ATTEMPTS = 3  # Max 3 retry attempts
PUBMEDBERT_INITIAL_DELAY_MS = 500  # Initial retry delay

# Pinecone namespaces
PROTOCOL_NAMESPACE = ""  # Default namespace for protocol exemplars
REGULATORY_NAMESPACE = "regulatory-guidance"  # Regulatory docs namespace

# Singleton Pinecone client
_pinecone_client = None
_pinecone_index = None
_init_attempted = False


def _init_pinecone():
    """Initialize Pinecone client (singleton pattern)"""
    global _pinecone_client, _pinecone_index, _init_attempted

    if _init_attempted:
        return _pinecone_index is not None

    _init_attempted = True

    if not PINECONE_API_KEY:
        logger.warning("⚠️ PINECONE_API_KEY not set, RAG disabled")
        return False

    try:
        from pinecone import Pinecone
        _pinecone_client = Pinecone(api_key=PINECONE_API_KEY)
        _pinecone_index = _pinecone_client.Index(PINECONE_INDEX_NAME)
        logger.info("✅ Pinecone initialized for fast RAG")
        return True
    except Exception as e:
        logger.error(f"❌ Pinecone initialization failed: {e}")
        return False


def get_pinecone_index():
    """
    Get current Pinecone index (initializes if needed)

    Returns:
        Pinecone index object, or None if unavailable
    """
    if not _init_pinecone():
        return None
    return _pinecone_index


async def get_pubmedbert_embedding(text: str, request_id: str = "unknown") -> Optional[List[float]]:
    """
    Get PubMedBERT embedding with exponential backoff retry

    Args:
        text: Protocol text to embed (will be truncated to 8000 chars)
        request_id: Request tracking ID

    Returns:
        768-dimensional embedding vector, or None if all retries failed
    """
    if not PUBMEDBERT_ENDPOINT or not HUGGINGFACE_API_KEY:
        logger.warning(f"⚠️ [{request_id}] PubMedBERT not configured")
        return None

    text = text[:8000]  # Truncate to ~2000 tokens

    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {"inputs": text}

    for attempt in range(1, PUBMEDBERT_RETRY_ATTEMPTS + 1):
        try:
            timeout = aiohttp.ClientTimeout(total=5)  # 5s per attempt

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    PUBMEDBERT_ENDPOINT,
                    headers=headers,
                    json=payload,
                    timeout=timeout
                ) as response:
                    if response.status == 200:
                        result = await response.json()

                        # Handle different PubMedBERT response formats
                        if isinstance(result, list) and len(result) > 0:
                            embedding = result[0] if isinstance(result[0], list) else result
                            logger.info(f"✅ [{request_id}] PubMedBERT embedding successful (attempt {attempt})")
                            return embedding
                        elif isinstance(result, dict) and 'embeddings' in result:
                            logger.info(f"✅ [{request_id}] PubMedBERT embedding successful (attempt {attempt})")
                            return result['embeddings']
                        else:
                            logger.warning(f"⚠️ [{request_id}] Unexpected PubMedBERT format: {type(result)}")
                            return None

                    elif response.status == 503:
                        # Service unavailable - likely cold start
                        delay_ms = PUBMEDBERT_INITIAL_DELAY_MS * (2 ** (attempt - 1))  # Exponential backoff
                        logger.warning(
                            f"⚠️ [{request_id}] PubMedBERT 503 (cold start), "
                            f"retry {attempt}/{PUBMEDBERT_RETRY_ATTEMPTS} in {delay_ms}ms"
                        )

                        if attempt < PUBMEDBERT_RETRY_ATTEMPTS:
                            await asyncio.sleep(delay_ms / 1000.0)
                            continue
                        else:
                            logger.error(f"❌ [{request_id}] PubMedBERT failed after {PUBMEDBERT_RETRY_ATTEMPTS} retries")
                            return None

                    else:
                        logger.error(f"❌ [{request_id}] PubMedBERT API error: {response.status}")
                        return None

        except asyncio.TimeoutError:
            logger.warning(f"⚠️ [{request_id}] PubMedBERT timeout (attempt {attempt}/{PUBMEDBERT_RETRY_ATTEMPTS})")

            if attempt < PUBMEDBERT_RETRY_ATTEMPTS:
                delay_ms = PUBMEDBERT_INITIAL_DELAY_MS * (2 ** (attempt - 1))
                await asyncio.sleep(delay_ms / 1000.0)
                continue
            else:
                return None

        except Exception as e:
            logger.error(f"❌ [{request_id}] PubMedBERT error (attempt {attempt}): {type(e).__name__}: {e}")
            return None

    return None


def _get_enhanced_clinical_embedding(text: str) -> List[float]:
    """
    Generate enhanced clinical embedding using proven patterns (fallback)

    Based on ai_service.py clinical keyword weighting
    """
    clinical_keywords = {
        # High-value clinical terms
        'primary endpoint': 1.0, 'secondary endpoint': 0.95, 'efficacy': 0.9,
        'safety': 0.95, 'adverse events': 0.9, 'participants': 0.85,
        'randomized': 0.9, 'double-blind': 0.85, 'placebo': 0.8,
        'protocol': 0.9, 'inclusion criteria': 0.85, 'exclusion criteria': 0.85,

        # Statistical analysis terms
        'statistical analysis': 0.9, 'intention-to-treat': 0.95, 'itt': 0.95,
        'per-protocol': 0.85, 'as-treated': 0.85, 'subgroup analysis': 0.8,

        # Regulatory terms
        'ich e6': 0.9, 'gcp': 0.85, 'fda': 0.8, 'ich-gcp': 0.9,
        'regulatory': 0.75, 'ethics': 0.7, 'irb': 0.75
    }

    text_lower = text.lower()

    # Calculate semantic weights
    semantic_score = 0
    word_count = 0

    for word in text_lower.split()[:150]:
        word_count += 1
        for term, weight in clinical_keywords.items():
            if term in text_lower:
                semantic_score += weight
                break
        else:
            # Medical/scientific suffixes
            if len(word) > 6 and any(suffix in word for suffix in ['tion', 'ment', 'ance', 'ence']):
                semantic_score += 0.3
            elif word in ['patient', 'study', 'trial', 'clinical', 'medical']:
                semantic_score += 0.5

    semantic_component = min(semantic_score / max(word_count, 1), 1.0)

    # Generate 768-dimensional embedding
    embedding = []
    text_hash = hashlib.sha256(text.encode()).digest()

    for i in range(768):
        hash_component = (text_hash[i % len(text_hash)] / 255.0 - 0.5) * 2
        semantic_weight = semantic_component * math.sin(i / 768 * 2 * math.pi)
        position_component = math.cos(i / 768 * 4 * math.pi) * 0.1
        length_component = min(len(text) / 1000, 1.0) * math.sin(i / 768 * math.pi) * 0.1

        final_value = (
            hash_component * 0.4 +
            semantic_weight * 0.4 +
            position_component * 0.1 +
            length_component * 0.1
        )
        embedding.append(final_value)

    logger.info("🔧 Generated enhanced clinical embedding (fallback)")
    return embedding


async def get_regulatory_citations(text: str, embedding: List[float], request_id: str = "unknown") -> List[Dict[str, Any]]:
    """
    Get relevant regulatory citations from FDA/ICH guidance documents

    Args:
        text: Protocol text being analyzed
        embedding: Pre-computed embedding vector
        request_id: Request tracking ID

    Returns:
        List of regulatory citations (max 2)
    """
    try:
        results = _pinecone_index.query(
            vector=embedding,
            top_k=FAST_RAG_REGULATORY_TOP_K,
            namespace=REGULATORY_NAMESPACE,
            include_metadata=True
        )

        citations = []
        for match in results.matches:
            metadata = match.metadata
            citations.append({
                'id': match.id,
                'score': float(match.score),
                'text': metadata.get('full_text', metadata.get('text', ''))[:600],
                'source': metadata.get('source', 'FDA/ICH Guidance'),
                'section': metadata.get('section', ''),
                'title': metadata.get('title', ''),
                'regulatory_weight': metadata.get('regulatory_weight', 'mandatory'),
                'type': 'regulatory'
            })

        logger.info(f"📜 [{request_id}] Retrieved {len(citations)} regulatory citations")
        return citations

    except Exception as e:
        logger.warning(f"⚠️ [{request_id}] Regulatory citation retrieval failed: {e}")
        return []


async def get_fast_exemplars(text: str, request_id: str = "unknown") -> Dict[str, List[Dict[str, Any]]]:
    """
    Get protocol exemplars AND regulatory citations using dual-namespace queries

    Args:
        text: Protocol text to find similar examples for
        request_id: Request tracking ID

    Returns:
        Dict with 'exemplars' and 'regulatory' keys, each containing list of results
        Returns {'exemplars': [], 'regulatory': []} if RAG unavailable
    """
    start_time = time.time()

    # Initialize Pinecone if needed
    if not _init_pinecone():
        logger.warning(f"⚠️ [{request_id}] Pinecone not available, skipping RAG")
        return {'exemplars': [], 'regulatory': []}

    try:
        # 1. Get embedding with retry logic
        embedding = await get_pubmedbert_embedding(text, request_id)

        # Fallback to enhanced clinical embedding if PubMedBERT fails
        if embedding is None:
            logger.warning(f"⚠️ [{request_id}] PubMedBERT unavailable, using enhanced fallback")
            embedding = _get_enhanced_clinical_embedding(text)

        # 2. Query both namespaces in parallel
        query_start = time.time()

        # Protocol exemplars (default namespace)
        protocol_results = _pinecone_index.query(
            vector=embedding,
            top_k=FAST_RAG_TOP_K,
            namespace=PROTOCOL_NAMESPACE,
            include_metadata=True
        )

        # Regulatory citations
        regulatory_citations = await get_regulatory_citations(text, embedding, request_id)

        query_ms = int((time.time() - query_start) * 1000)

        # 3. Format protocol exemplars
        exemplars = []
        for match in protocol_results.matches:
            exemplars.append({
                'id': match.id,
                'score': float(match.score),
                'text': match.metadata.get('text', '')[:500],
                'protocol_id': match.metadata.get('protocol_id', 'unknown'),
                'section_type': match.metadata.get('type', 'unknown'),
                'type': 'protocol',
                'metadata': match.metadata
            })

        total_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"✅ [{request_id}] RAG retrieved {len(exemplars)} exemplars + "
            f"{len(regulatory_citations)} regulatory citations "
            f"(query: {query_ms}ms, total: {total_ms}ms)"
        )

        return {
            'exemplars': exemplars,
            'regulatory': regulatory_citations
        }

    except Exception as e:
        total_ms = int((time.time() - start_time) * 1000)
        logger.error(f"❌ [{request_id}] RAG failed ({total_ms}ms): {type(e).__name__}: {e}")
        return {'exemplars': [], 'regulatory': []}


def format_exemplars_for_prompt(rag_results: Dict[str, List[Dict[str, Any]]]) -> str:
    """
    Format protocol exemplars AND regulatory citations for prompt injection

    Args:
        rag_results: Dict with 'exemplars' and 'regulatory' lists from get_fast_exemplars()

    Returns:
        Formatted string for prompt injection with regulatory citations first
    """
    formatted = ""

    # Add regulatory citations first (most important for compliance)
    regulatory = rag_results.get('regulatory', [])
    if regulatory:
        formatted += "\n\nREGULATORY GUIDANCE (Must cite specific sections in your rationale):\n"
        for idx, reg in enumerate(regulatory, 1):
            source = reg.get('source', 'FDA/ICH')
            section = reg.get('section', '')
            title = reg.get('title', '')
            text = reg.get('text', '')[:400]

            formatted += f"\n{idx}. {source}"
            if section:
                formatted += f" - Section: {section}"
            if title:
                formatted += f"\n   Title: {title}"
            formatted += f"\n   Content: {text}...\n"

    # Add protocol exemplars (for writing quality)
    exemplars = rag_results.get('exemplars', [])
    if exemplars:
        formatted += "\n\nPROTOCOL WRITING EXAMPLES (Best practices):\n"
        for idx, ex in enumerate(exemplars, 1):
            formatted += f"\nExample {idx} (relevance: {ex.get('score', 0):.3f}):\n"
            formatted += f"{ex.get('text', '')[:300]}...\n"

    if formatted:
        formatted += "\nIMPORTANT: Cite specific regulatory sections (e.g., 'ICH E9 Section 5.7') in your rationale.\n"

    return formatted


# Export main functions
__all__ = [
    "get_pubmedbert_embedding",
    "get_fast_exemplars",
    "format_exemplars_for_prompt"
]
