#!/usr/bin/env python3
"""
Adapter for config_loader.py
Routes to legacy pipeline only when USE_SIMPLE_AZURE_PROMPT=false
"""

import os
import logging

logger = logging.getLogger(__name__)

# TODO: legacy pipeline — safe mode; remove after validation
# This adapter routes to the complex legacy configuration when USE_SIMPLE_AZURE_PROMPT=false

def should_use_legacy_pipeline() -> bool:
    """Check if we should use legacy pipeline based on environment flag"""
    return os.getenv("USE_SIMPLE_AZURE_PROMPT", "true").lower() != "true"

if should_use_legacy_pipeline():
    logger.info("🔄 CONFIG ADAPTER: Using legacy configuration system")
    try:
        from legacy_pipeline_backup.config_loader import (
            IlanaConfig,
            ConfigLoader, 
            get_config_loader,
            get_config
        )
        logger.info("✅ CONFIG ADAPTER: Legacy configuration imported successfully")
    except ImportError as e:
        logger.error(f"❌ CONFIG ADAPTER: Failed to import legacy config: {e}")
        raise ImportError(f"Legacy configuration not available: {e}")
else:
    logger.info("🚀 CONFIG ADAPTER: Using simple configuration mode")
    # Simple configuration for direct Azure OpenAI usage
    from dataclasses import dataclass
    from pathlib import Path
    from dotenv import load_dotenv
    
    # Load environment from simple location
    # Note: In managed deployments (Render, Heroku, AWS, etc.), environment variables
    # should be set via the platform dashboard, not via .env files.
    env_path = os.getenv(
        "PRODUCTION_ENV_PATH",
        str(Path(__file__).parent / "config" / "environments" / "production.env")
    )
    env_path = Path(env_path)

    if env_path.exists():
        load_dotenv(env_path)
        # Silent success - main.py already logs this
    else:
        # Silent fallback - main.py already logs this
        pass
    
    @dataclass
    class IlanaConfig:
        """Simplified configuration for direct Azure OpenAI usage"""
        environment: str = "production"
        azure_openai_endpoint: str = ""
        azure_openai_api_key: str = ""
        azure_openai_deployment: str = ""
        
        def __post_init__(self):
            self.azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
            self.azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
            self.azure_openai_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-deployment")
    
    class ConfigLoader:
        """Simplified configuration loader"""
        def load_config(self, environment: str = None) -> IlanaConfig:
            return IlanaConfig()
    
    def get_config_loader() -> ConfigLoader:
        return ConfigLoader()
    
    def get_config(environment: str = None) -> IlanaConfig:
        return IlanaConfig()