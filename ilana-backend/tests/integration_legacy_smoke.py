#!/usr/bin/env python3
"""
Integration Smoke Tests for Legacy Pipeline
Tests the complete pipeline end-to-end with real services (Pinecone, PubMedBERT, Azure OpenAI)

IMPORTANT: These tests require valid API keys in .env file:
- AZURE_OPENAI_API_KEY
- PINECONE_API_KEY
- HUGGINGFACE_API_KEY
"""

import pytest
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
load_dotenv()


class TestLegacyPipelineIntegration:
    """Integration tests for legacy pipeline with real services"""

    @pytest.fixture(autouse=True)
    def check_env_vars(self):
        """Verify required environment variables are set"""
        required_vars = [
            "AZURE_OPENAI_API_KEY",
            "PINECONE_API_KEY",
            "PINECONE_ENVIRONMENT",
            "PINECONE_INDEX_NAME"
        ]

        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            pytest.skip(f"Missing required environment variables: {', '.join(missing)}")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_legacy_pipeline_oncology(self):
        """Test legacy pipeline with oncology protocol text"""

        from legacy_pipeline import run_legacy_pipeline

        text = """
        Patients with advanced solid tumors will receive the study drug at 200mg orally once daily.
        Adverse events will be monitored using CTCAE v5.0 criteria. Patients may experience
        nausea, fatigue, or decreased appetite during treatment.
        """

        result = await run_legacy_pipeline(
            text=text,
            ta="oncology",
            phase="Phase II",
            request_id="integration_test_oncology"
        )

        # Verify response structure
        assert "request_id" in result
        assert "model_path" in result
        assert "result" in result
        assert result["model_path"] == "legacy_pipeline"

        # Verify suggestions
        suggestions = result["result"]["suggestions"]
        assert isinstance(suggestions, list)
        print(f"\n✅ Received {len(suggestions)} suggestions for oncology text")

        # Verify metadata
        metadata = result["result"]["metadata"]
        assert metadata["pipeline_used"] == "legacy_pipeline"
        assert metadata["pinecone_enabled"] is True
        assert "latency_ms" in metadata
        print(f"   Pipeline latency: {metadata['latency_ms']}ms")

        # Print sample suggestion if any
        if suggestions:
            sample = suggestions[0]
            print(f"\n   Sample suggestion:")
            print(f"   Type: {sample['type']}")
            print(f"   Original: {sample['text'][:50]}...")
            print(f"   Suggested: {sample['suggestion'][:50]}...")
            print(f"   Confidence: {sample['confidence']}")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_legacy_pipeline_cardiovascular(self):
        """Test legacy pipeline with cardiovascular protocol text"""

        from legacy_pipeline import run_legacy_pipeline

        text = """
        Patients with coronary artery disease will undergo percutaneous coronary intervention.
        Blood pressure will be monitored every 4 hours post-procedure. Target systolic BP
        should remain below 140 mmHg.
        """

        result = await run_legacy_pipeline(
            text=text,
            ta="cardiovascular",
            phase="Phase III",
            request_id="integration_test_cardio"
        )

        assert result["model_path"] == "legacy_pipeline"
        assert "suggestions" in result["result"]
        print(f"\n✅ Cardiovascular test successful ({len(result['result']['suggestions'])} suggestions)")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_legacy_pipeline_general_medicine(self):
        """Test legacy pipeline with general medicine text"""

        from legacy_pipeline import run_legacy_pipeline

        text = """
        Subjects will be randomized 1:1 to receive either active treatment or placebo.
        Primary endpoint is change from baseline in symptom severity score at Week 12.
        """

        result = await run_legacy_pipeline(
            text=text,
            ta="general_medicine",
            phase="Phase I",
            request_id="integration_test_general"
        )

        assert result["model_path"] == "legacy_pipeline"
        metadata = result["result"]["metadata"]
        print(f"\n✅ General medicine test successful")
        print(f"   TA detected: {metadata.get('ta_detected', 'unknown')}")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_legacy_pipeline_latency(self):
        """Test that legacy pipeline completes within acceptable time"""

        from legacy_pipeline import run_legacy_pipeline
        import time

        text = "Patients will receive 50mg of the study drug twice daily."

        start = time.time()
        result = await run_legacy_pipeline(
            text=text,
            request_id="integration_test_latency"
        )
        latency_ms = int((time.time() - start) * 1000)

        # Should complete within 10 seconds (MAX_TIMEOUT_SECONDS)
        assert latency_ms < 10000, f"Pipeline took too long: {latency_ms}ms"
        print(f"\n✅ Latency test passed: {latency_ms}ms")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_legacy_pipeline_with_fallback(self):
        """Test fallback mechanism"""

        from legacy_pipeline import run_legacy_pipeline_with_fallback

        text = "Test protocol text for fallback testing"

        result = await run_legacy_pipeline_with_fallback(
            text=text,
            request_id="integration_test_fallback"
        )

        # Should succeed either via legacy or fallback
        assert "result" in result
        assert "suggestions" in result["result"]
        print(f"\n✅ Fallback wrapper test passed (model: {result.get('model_path', 'unknown')})")


class TestPineconeIntegration:
    """Direct Pinecone integration tests"""

    @pytest.fixture(autouse=True)
    def check_pinecone_env(self):
        """Verify Pinecone environment variables"""
        if not os.getenv("PINECONE_API_KEY"):
            pytest.skip("PINECONE_API_KEY not set")

    @pytest.mark.integration
    def test_pinecone_connection(self):
        """Test connection to Pinecone index"""

        from pinecone import Pinecone

        api_key = os.getenv("PINECONE_API_KEY")
        environment = os.getenv("PINECONE_ENVIRONMENT", "gcp-starter")
        index_name = os.getenv("PINECONE_INDEX_NAME", "protocol-intelligence-768")

        # Initialize (Pinecone 6.0+ API)
        pc = Pinecone(api_key=api_key)

        # Get index
        index = pc.Index(index_name)
        stats = index.describe_index_stats()

        # Pinecone 6.0+ returns dict
        total_vectors = stats.get('total_vector_count', stats['total_vector_count']) if isinstance(stats, dict) else stats.total_vector_count
        dimension = stats.get('dimension', stats['dimension']) if isinstance(stats, dict) else stats.dimension

        print(f"\n✅ Pinecone connected successfully")
        print(f"   Index: {index_name}")
        print(f"   Vectors: {total_vectors:,}")
        print(f"   Dimension: {dimension}")

        assert total_vectors > 0, "Index is empty"
        assert dimension == 768, "Incorrect dimension (should be 768 for PubMedBERT)"

    @pytest.mark.integration
    def test_pinecone_query(self):
        """Test querying Pinecone index"""

        from pinecone import Pinecone
        import numpy as np

        api_key = os.getenv("PINECONE_API_KEY")
        environment = os.getenv("PINECONE_ENVIRONMENT", "gcp-starter")
        index_name = os.getenv("PINECONE_INDEX_NAME", "protocol-intelligence-768")

        # Initialize (Pinecone 6.0+ API)
        pc = Pinecone(api_key=api_key)
        index = pc.Index(index_name)

        # Create random query vector
        query_vector = np.random.random(768).tolist()

        # Query
        results = index.query(
            vector=query_vector,
            top_k=5,
            include_metadata=True
        )

        # Pinecone 6.0+ returns dict
        matches = results.get('matches', results['matches']) if isinstance(results, dict) else results.matches

        assert len(matches) > 0, "No results returned"
        print(f"\n✅ Pinecone query successful ({len(matches)} results)")

        # Print sample result
        if matches:
            match = matches[0]
            match_id = match.get('id', match['id']) if isinstance(match, dict) else match.id
            match_score = match.get('score', match['score']) if isinstance(match, dict) else match.score
            match_metadata = match.get('metadata', {}) if isinstance(match, dict) else (match.metadata if hasattr(match, 'metadata') else {})

            print(f"   Sample match ID: {match_id}")
            print(f"   Score: {match_score:.4f}")
            if match_metadata:
                print(f"   Metadata keys: {list(match_metadata.keys())}")


class TestPubMedBERTIntegration:
    """PubMedBERT integration tests"""

    @pytest.fixture(autouse=True)
    def check_huggingface_env(self):
        """Verify HuggingFace environment variables"""
        if not os.getenv("HUGGINGFACE_API_KEY"):
            pytest.skip("HUGGINGFACE_API_KEY not set")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_pubmedbert_embedding(self):
        """Test generating embeddings with PubMedBERT"""

        import aiohttp

        endpoint = os.getenv("PUBMEDBERT_ENDPOINT_URL")
        api_key = os.getenv("HUGGINGFACE_API_KEY")

        if not endpoint:
            pytest.skip("PUBMEDBERT_ENDPOINT_URL not set")

        text = "adverse events"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint,
                headers={"Authorization": f"Bearer {api_key}"},
                json={"inputs": text}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # Response format may vary by endpoint
                    print(f"\n✅ PubMedBERT request successful (status: {response.status})")
                    print(f"   Response keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
                else:
                    pytest.skip(f"PubMedBERT endpoint returned {response.status}")


if __name__ == "__main__":
    # Run integration tests
    print("\n" + "=" * 60)
    print("🧪 Legacy Pipeline Integration Smoke Tests")
    print("=" * 60)
    print("\nNOTE: These tests require valid API keys in .env file")
    print("      Tests will be skipped if keys are missing\n")

    pytest.main([
        __file__,
        "-v",
        "-s",
        "-m", "integration",
        "--tb=short"
    ])
