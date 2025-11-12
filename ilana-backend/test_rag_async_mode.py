"""
Tests for RAG_ASYNC_MODE configuration and gating behavior.

Tests verify that:
1. RAG_ASYNC_MODE=true blocks synchronous RAG operations
2. RAG_ASYNC_ALLOW_SYNC=true permits sync operations with warnings
3. RAG_ASYNC_MODE=false allows all sync operations
4. check_rag_async_mode_gate() raises/warns correctly
5. Endpoints return standardized HTTP 202 responses
6. Startup logging explains RAG behavior correctly
7. Vector DB query respects gating
8. TA-aware rewrite respects gating

Run with: pytest test_rag_async_mode.py -v
"""

import os
import pytest
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock
import importlib
import sys

# Ensure we import from the correct directory (ilana-backend, not parent)
backend_dir = Path(__file__).parent.absolute()
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


class TestRAGAsyncModeGate:
    """Test suite for check_rag_async_mode_gate() function."""

    def test_gate_blocks_when_rag_async_mode_true_and_allow_sync_false(self):
        """Test that gate blocks operations when RAG_ASYNC_MODE=true and ALLOW_SYNC=false"""
        with patch.dict(os.environ, {
            "RAG_ASYNC_MODE": "true",
            "RAG_ASYNC_ALLOW_SYNC": "false"
        }, clear=False):
            # Reload main to pick up env changes
            if 'main' in sys.modules:
                del sys.modules['main']
            import main
            importlib.reload(main)

            # Should raise RAGAsyncModeException
            with pytest.raises(main.RAGAsyncModeException) as exc_info:
                main.check_rag_async_mode_gate("Test operation")

            assert "blocked" in str(exc_info.value).lower()
            assert "RAG_ASYNC_MODE is enabled" in str(exc_info.value)

    def test_gate_warns_when_rag_async_mode_true_and_allow_sync_true(self, caplog):
        """Test that gate warns but permits when RAG_ASYNC_MODE=true and ALLOW_SYNC=true"""
        with patch.dict(os.environ, {
            "RAG_ASYNC_MODE": "true",
            "RAG_ASYNC_ALLOW_SYNC": "true"
        }, clear=False):
            if 'main' in sys.modules:
                del sys.modules['main']
            import main
            importlib.reload(main)

            with caplog.at_level(logging.WARNING):
                # Should NOT raise exception
                main.check_rag_async_mode_gate("Test operation")

            # Verify WARNING was logged
            warnings = [r for r in caplog.records if r.levelname == "WARNING"]
            assert len(warnings) > 0
            assert any("RAG_ASYNC_ALLOW_SYNC=true" in r.message for r in warnings)
            assert any("Not recommended in production" in r.message for r in warnings)

    def test_gate_allows_when_rag_async_mode_false(self):
        """Test that gate allows operations when RAG_ASYNC_MODE=false"""
        with patch.dict(os.environ, {
            "RAG_ASYNC_MODE": "false"
        }, clear=False):
            if 'main' in sys.modules:
                del sys.modules['main']
            import main
            importlib.reload(main)

            # Should not raise exception or warn
            try:
                main.check_rag_async_mode_gate("Test operation")
            except main.RAGAsyncModeException:
                pytest.fail("Gate should not block when RAG_ASYNC_MODE=false")


class TestRAGAsyncModeStartupLogging:
    """Test suite for startup logging of RAG configuration."""

    def test_startup_logs_info_when_rag_async_mode_true_and_allow_sync_false(self, caplog):
        """Test startup INFO log explains blocking behavior"""
        with patch.dict(os.environ, {
            "RAG_ASYNC_MODE": "true",
            "RAG_ASYNC_ALLOW_SYNC": "false"
        }, clear=False):
            with caplog.at_level(logging.INFO):
                if 'main' in sys.modules:
                    del sys.modules['main']
                import main
                importlib.reload(main)

            # Verify INFO was logged
            info_logs = [r for r in caplog.records if r.levelname == "INFO"]
            messages = [r.message for r in info_logs]

            # Should mention RAG_ASYNC_MODE=true and explain behavior
            assert any("RAG_ASYNC_MODE=true" in msg for msg in messages)
            assert any("HTTP 202" in msg or "queued" in msg.lower() for msg in messages)
            assert any("RAG_ASYNC_ALLOW_SYNC=true" in msg for msg in messages)

    def test_startup_warns_when_allow_sync_true(self, caplog):
        """Test startup WARNING when ALLOW_SYNC=true (dangerous in prod)"""
        with patch.dict(os.environ, {
            "RAG_ASYNC_MODE": "true",
            "RAG_ASYNC_ALLOW_SYNC": "true"
        }, clear=False):
            with caplog.at_level(logging.WARNING):
                if 'main' in sys.modules:
                    del sys.modules['main']
                import main
                importlib.reload(main)

            # Verify WARNING was logged
            warnings = [r for r in caplog.records if r.levelname == "WARNING"]
            messages = [r.message for r in warnings]

            assert any("RAG_ASYNC_ALLOW_SYNC=true" in msg for msg in messages)
            assert any("Not recommended in production" in msg for msg in messages)

    def test_startup_logs_info_when_rag_async_mode_false(self, caplog):
        """Test startup INFO log explains synchronous behavior"""
        with patch.dict(os.environ, {
            "RAG_ASYNC_MODE": "false"
        }, clear=False):
            with caplog.at_level(logging.INFO):
                if 'main' in sys.modules:
                    del sys.modules['main']
                import main
                importlib.reload(main)

            # Verify INFO was logged
            info_logs = [r for r in caplog.records if r.levelname == "INFO"]
            messages = [r.message for r in info_logs]

            # Should mention RAG_ASYNC_MODE=false and synchronous operations
            assert any("RAG_ASYNC_MODE=false" in msg for msg in messages)
            assert any("synchronously" in msg.lower() for msg in messages)


class TestVectorDBQueryGating:
    """Test suite for vector DB query gating."""

    @pytest.mark.asyncio
    async def test_query_vector_db_blocked_when_rag_async_mode_true(self):
        """Test that query_vector_db raises exception when RAG_ASYNC_MODE=true"""
        with patch.dict(os.environ, {
            "RAG_ASYNC_MODE": "true",
            "RAG_ASYNC_ALLOW_SYNC": "false"
        }, clear=False):
            if 'main' in sys.modules:
                del sys.modules['main']
            import main
            importlib.reload(main)

            # Should raise RAGAsyncModeException
            with pytest.raises(main.RAGAsyncModeException):
                await main.query_vector_db("test text", "oncology", "phase3")

    @pytest.mark.asyncio
    async def test_query_vector_db_warns_when_allow_sync_true(self, caplog):
        """Test that query_vector_db warns but executes when ALLOW_SYNC=true"""
        with patch.dict(os.environ, {
            "RAG_ASYNC_MODE": "true",
            "RAG_ASYNC_ALLOW_SYNC": "true"
        }, clear=False):
            if 'main' in sys.modules:
                del sys.modules['main']
            import main
            importlib.reload(main)

            with caplog.at_level(logging.WARNING):
                # Should execute without exception
                result = await main.query_vector_db("test text", "oncology", "phase3")

            # Verify result is returned
            assert result is not None
            assert isinstance(result, list)

            # Verify WARNING was logged
            warnings = [r for r in caplog.records if r.levelname == "WARNING"]
            assert len(warnings) > 0


class TestTARewriteGating:
    """Test suite for TA-aware rewrite gating."""

    @pytest.mark.asyncio
    async def test_ta_rewrite_blocked_when_rag_async_mode_true(self):
        """Test that generate_ta_aware_rewrite raises exception when RAG_ASYNC_MODE=true"""
        with patch.dict(os.environ, {
            "RAG_ASYNC_MODE": "true",
            "RAG_ASYNC_ALLOW_SYNC": "false"
        }, clear=False):
            if 'main' in sys.modules:
                del sys.modules['main']
            import main
            importlib.reload(main)

            # Should raise RAGAsyncModeException
            with pytest.raises(main.RAGAsyncModeException):
                await main.generate_ta_aware_rewrite(
                    "test text", "oncology", "phase3", [], []
                )

    @pytest.mark.asyncio
    async def test_ta_rewrite_warns_when_allow_sync_true(self, caplog):
        """Test that generate_ta_aware_rewrite warns but executes when ALLOW_SYNC=true"""
        with patch.dict(os.environ, {
            "RAG_ASYNC_MODE": "true",
            "RAG_ASYNC_ALLOW_SYNC": "true",
            "USE_SIMPLE_AZURE_PROMPT": "true"  # Use simple mode to avoid Azure dependencies
        }, clear=False):
            if 'main' in sys.modules:
                del sys.modules['main']
            import main
            importlib.reload(main)

            with caplog.at_level(logging.WARNING):
                # Should execute without exception
                result = await main.generate_ta_aware_rewrite(
                    "test text", "oncology", "phase3", [], []
                )

            # Verify result is returned
            assert result is not None
            assert isinstance(result, dict)

            # Verify WARNING was logged
            warnings = [r for r in caplog.records if r.levelname == "WARNING"]
            assert len(warnings) > 0


class TestEndpoint202Responses:
    """Test suite for standardized 202 responses from endpoints."""

    @pytest.mark.asyncio
    async def test_generate_rewrite_ta_returns_202_when_blocked(self):
        """Test /api/generate-rewrite-ta returns standardized 202 when RAG_ASYNC_MODE blocks"""
        with patch.dict(os.environ, {
            "RAG_ASYNC_MODE": "true",
            "RAG_ASYNC_ALLOW_SYNC": "false"
        }, clear=False):
            if 'main' in sys.modules:
                del sys.modules['main']
            import main
            importlib.reload(main)

            from fastapi.testclient import TestClient
            client = TestClient(main.app)

            # Make request
            response = client.post("/api/generate-rewrite-ta", json={
                "text": "test text",
                "ta": "oncology",
                "phase": "phase3",
                "doc_id": "test_doc",
                "suggestion_id": "test_suggestion"
            })

            # Verify 202 response
            assert response.status_code == 202
            data = response.json()

            # Verify standardized format
            assert "request_id" in data
            assert "result" in data
            assert data["result"]["status"] == "queued"
            assert "message" in data
            assert "RAG is in async mode" in data["message"]

    def test_202_response_format_validity(self):
        """Test that 202 response matches expected schema"""
        # Expected schema
        expected_keys = {"request_id", "result", "message"}
        expected_result_keys = {"status"}

        # Simulate a 202 response
        response_data = {
            "request_id": "test_123",
            "result": {"status": "queued"},
            "message": "RAG is in async mode — operations queued to prevent timeouts."
        }

        # Verify schema
        assert set(response_data.keys()) == expected_keys
        assert set(response_data["result"].keys()) == expected_result_keys
        assert response_data["result"]["status"] == "queued"
        assert isinstance(response_data["message"], str)
        assert len(response_data["message"]) > 0


class TestConfigurationValidation:
    """Test suite for RAG configuration validation."""

    def test_rag_async_mode_defaults_to_true(self):
        """Test that RAG_ASYNC_MODE defaults to true when not set"""
        with patch.dict(os.environ, {}, clear=False):
            # Remove RAG_ASYNC_MODE if it exists
            os.environ.pop("RAG_ASYNC_MODE", None)

            if 'main' in sys.modules:
                del sys.modules['main']
            import main
            importlib.reload(main)

            # Should default to True
            assert main.RAG_ASYNC_MODE is True

    def test_rag_async_allow_sync_defaults_to_false(self):
        """Test that RAG_ASYNC_ALLOW_SYNC defaults to false when not set"""
        with patch.dict(os.environ, {}, clear=False):
            # Remove RAG_ASYNC_ALLOW_SYNC if it exists
            os.environ.pop("RAG_ASYNC_ALLOW_SYNC", None)

            if 'main' in sys.modules:
                del sys.modules['main']
            import main
            importlib.reload(main)

            # Should default to False
            assert main.RAG_ASYNC_ALLOW_SYNC is False

    def test_rag_async_mode_respects_env_var(self):
        """Test that RAG_ASYNC_MODE respects environment variable"""
        with patch.dict(os.environ, {
            "RAG_ASYNC_MODE": "false"
        }, clear=False):
            if 'main' in sys.modules:
                del sys.modules['main']
            import main
            importlib.reload(main)

            # Should be False
            assert main.RAG_ASYNC_MODE is False

    def test_rag_async_allow_sync_respects_env_var(self):
        """Test that RAG_ASYNC_ALLOW_SYNC respects environment variable"""
        with patch.dict(os.environ, {
            "RAG_ASYNC_ALLOW_SYNC": "true"
        }, clear=False):
            if 'main' in sys.modules:
                del sys.modules['main']
            import main
            importlib.reload(main)

            # Should be True
            assert main.RAG_ASYNC_ALLOW_SYNC is True


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
