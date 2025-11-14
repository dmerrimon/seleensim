"""
Unit Tests for Legacy Pipeline
Tests the legacy pipeline with mocked Pinecone and PubMedBERT dependencies
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestLegacyPipelineWrapper:
    """Test the legacy_pipeline.py wrapper module"""

    @pytest.mark.asyncio
    async def test_run_legacy_pipeline_success(self):
        """Test successful legacy pipeline execution"""

        with patch('legacy_pipeline._get_or_create_legacy_service') as mock_service_getter:
            # Create mock service
            mock_service = Mock()
            mock_service.enable_pinecone = True
            mock_service.enable_pubmedbert = True
            mock_service.enable_ta_detection = True

            # Mock analyze_comprehensive method
            mock_suggestion = Mock()
            mock_suggestion.type = "medical_terminology"
            mock_suggestion.subtype = "adverse_event"
            mock_suggestion.originalText = "side effects"
            mock_suggestion.suggestedText = "adverse events"
            mock_suggestion.rationale = "FDA-compliant terminology"
            mock_suggestion.backendConfidence = "high"
            mock_suggestion.fdaReference = "FDA Guidance 2020"
            mock_suggestion.emaReference = None
            mock_suggestion.guidanceSource = None
            mock_suggestion.readabilityScore = 8.5
            mock_suggestion.operationalImpact = "medium"
            mock_suggestion.retentionRisk = "low"

            mock_metadata = {
                "ta_detected": "oncology",
                "pinecone_matches": 10,
                "pubmedbert_confidence": 0.95
            }

            mock_service.analyze_comprehensive = AsyncMock(
                return_value=([mock_suggestion], mock_metadata)
            )

            mock_service_getter.return_value = mock_service

            # Import and test
            from legacy_pipeline import run_legacy_pipeline

            result = await run_legacy_pipeline(
                text="Patients may experience side effects",
                ta="oncology",
                phase="Phase III",
                request_id="test_123"
            )

            # Assertions
            assert result["request_id"] == "test_123"
            assert result["model_path"] == "legacy_pipeline"
            assert "suggestions" in result["result"]
            assert len(result["result"]["suggestions"]) == 1

            suggestion = result["result"]["suggestions"][0]
            assert suggestion["type"] == "medical_terminology"
            assert suggestion["text"] == "side effects"
            assert suggestion["suggestion"] == "adverse events"
            assert suggestion["confidence"] == 0.9

            metadata = result["result"]["metadata"]
            assert metadata["pipeline_used"] == "legacy_pipeline"
            assert metadata["pinecone_enabled"] is True
            assert metadata["pubmedbert_enabled"] is True
            assert "latency_ms" in metadata

    @pytest.mark.asyncio
    async def test_run_legacy_pipeline_disabled(self):
        """Test legacy pipeline when disabled by feature flag"""

        with patch.dict('os.environ', {'ENABLE_LEGACY_PIPELINE': 'false'}):
            # Re-import to pick up env change
            import importlib
            import legacy_pipeline
            importlib.reload(legacy_pipeline)

            from legacy_pipeline import run_legacy_pipeline

            with pytest.raises(ValueError, match="Legacy pipeline disabled"):
                await run_legacy_pipeline(
                    text="Test text",
                    request_id="test_disabled"
                )

    @pytest.mark.asyncio
    async def test_run_legacy_pipeline_timeout(self):
        """Test legacy pipeline timeout handling"""

        with patch('legacy_pipeline._get_or_create_legacy_service') as mock_service_getter:
            mock_service = Mock()
            mock_service.enable_pinecone = True
            mock_service.enable_pubmedbert = True
            mock_service.enable_ta_detection = True

            # Mock slow analyze_comprehensive that times out
            async def slow_analyze(*args, **kwargs):
                await asyncio.sleep(15)  # Longer than MAX_TIMEOUT_SECONDS
                return ([], {})

            mock_service.analyze_comprehensive = slow_analyze
            mock_service_getter.return_value = mock_service

            from legacy_pipeline import run_legacy_pipeline

            with pytest.raises(asyncio.TimeoutError):
                await run_legacy_pipeline(
                    text="Test text",
                    request_id="test_timeout"
                )

    @pytest.mark.asyncio
    async def test_run_legacy_pipeline_with_fallback_success(self):
        """Test fallback wrapper with successful pipeline"""

        with patch('legacy_pipeline.run_legacy_pipeline') as mock_run:
            mock_run.return_value = {
                "request_id": "test_fallback",
                "model_path": "legacy_pipeline",
                "result": {
                    "suggestions": [],
                    "metadata": {}
                }
            }

            from legacy_pipeline import run_legacy_pipeline_with_fallback

            result = await run_legacy_pipeline_with_fallback(
                text="Test text",
                request_id="test_fallback"
            )

            assert result["request_id"] == "test_fallback"
            mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_legacy_pipeline_with_fallback_error(self):
        """Test fallback to simple mode when legacy fails"""

        with patch('legacy_pipeline.run_legacy_pipeline') as mock_run, \
             patch('legacy_pipeline.recommend_language_simple') as mock_simple:

            # Make legacy pipeline fail
            mock_run.side_effect = Exception("Pinecone connection failed")

            # Mock simple mode
            mock_simple.return_value = {
                "suggestions": [],
                "metadata": {"ta": "general_medicine"}
            }

            from legacy_pipeline import run_legacy_pipeline_with_fallback

            result = await run_legacy_pipeline_with_fallback(
                text="Test text",
                request_id="test_fallback_error"
            )

            assert result["model_path"] == "simple_fallback"
            assert result["result"]["metadata"]["pipeline_used"] == "simple_pipeline_fallback"
            assert result["result"]["metadata"]["legacy_pipeline_failed"] is True
            mock_simple.assert_called_once()


class TestLegacyServiceIntegration:
    """Test legacy AI service components with mocks"""

    @pytest.mark.asyncio
    async def test_pinecone_query_mock(self):
        """Test Pinecone querying with mocked client"""

        with patch('pinecone.init') as mock_init, \
             patch('pinecone.Index') as mock_index_class:

            # Mock Pinecone index
            mock_index = Mock()
            mock_match = Mock()
            mock_match.id = "proto_001"
            mock_match.score = 0.95
            mock_match.metadata = {
                "text": "Sample protocol text",
                "protocol_id": "NCT12345",
                "type": "inclusion_criteria"
            }

            mock_results = Mock()
            mock_results.matches = [mock_match]
            mock_index.query.return_value = mock_results
            mock_index_class.return_value = mock_index

            # Import and initialize
            import pinecone
            pinecone.init(api_key="test_key", environment="test")
            index = pinecone.Index("test-index")

            # Test query
            import numpy as np
            query_vector = np.random.random(768).tolist()
            results = index.query(
                vector=query_vector,
                top_k=10,
                include_metadata=True
            )

            assert len(results.matches) == 1
            assert results.matches[0].id == "proto_001"
            assert results.matches[0].score == 0.95

    @pytest.mark.asyncio
    async def test_pubmedbert_embedding_mock(self):
        """Test PubMedBERT embedding generation with mock"""

        with patch('aiohttp.ClientSession') as mock_session_class:
            # Mock HTTP response
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "embeddings": [[0.1] * 768]
            })

            mock_session = Mock()
            mock_session.post = AsyncMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session

            # Test embedding generation
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.huggingface.co/models",
                    json={"inputs": "adverse events"}
                ) as response:
                    data = await response.json()
                    embeddings = data["embeddings"][0]

                    assert len(embeddings) == 768
                    assert response.status == 200


class TestConfigLoader:
    """Test configuration loading"""

    def test_production_config_structure(self):
        """Test that production config has required fields"""

        with patch('legacy_pipeline_backup.config_loader.get_config') as mock_config:
            mock_config.return_value = {
                "azure_openai": {
                    "api_key": "test_key",
                    "endpoint": "https://test.openai.azure.com/",
                    "deployment_name": "gpt-4"
                },
                "pinecone": {
                    "api_key": "test_pinecone_key",
                    "environment": "gcp-starter",
                    "index_name": "protocol-intelligence-768"
                },
                "pubmedbert": {
                    "endpoint_url": "https://test.huggingface.co",
                    "api_key": "test_hf_key"
                },
                "features": {
                    "enable_pinecone": True,
                    "enable_pubmedbert": True,
                    "enable_ta_detection": True
                }
            }

            from legacy_pipeline_backup.config_loader import get_config
            config = get_config("production")

            assert "azure_openai" in config
            assert "pinecone" in config
            assert "pubmedbert" in config
            assert config["features"]["enable_pinecone"] is True


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
