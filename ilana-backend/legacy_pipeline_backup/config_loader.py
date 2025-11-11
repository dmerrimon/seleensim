"""
Configuration Loader for Ilana Protocol Intelligence
Securely loads and manages API keys and environment settings
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class IlanaConfig:
    """Ilana configuration dataclass"""
    
    # Environment
    environment: str
    
    # PubmedBERT
    pubmedbert_endpoint_url: str
    huggingface_api_key: str
    
    # Azure OpenAI
    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_deployment: str
    
    # Pinecone
    pinecone_api_key: str
    pinecone_environment: str
    pinecone_index_name: str
    
    # Azure ML
    azure_ml_key_identifier: str
    ml_endpoint_auth_key: str
    
    # Azure Static Apps
    azure_static_app_token: str
    appsource_webhook_secret: str
    
    # Paths
    protocol_database_path: str
    regulatory_database_path: str
    embeddings_cache_path: str
    model_cache_dir: str
    log_file: str
    
    # Performance
    max_sequence_length: int = 512
    batch_size: int = 32
    max_workers: int = 4
    timeout_seconds: int = 30
    embedding_dimensions: int = 768
    
    # Security
    cors_origins: str = "*"
    api_rate_limit: int = 100
    max_payload_size: int = 10485760
    
    # Features
    enable_continuous_learning: bool = True
    enable_advanced_analytics: bool = True
    enable_pinecone_integration: bool = True
    enable_azure_openai: bool = True


class ConfigLoader:
    """Loads configuration from environment files and environment variables"""
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path(__file__).parent
        self.environments_dir = self.config_dir / "environments"
        self._config_cache = {}
        
    def load_config(self, environment: str = None) -> IlanaConfig:
        """
        Load configuration for specified environment
        
        Args:
            environment: Environment name (development, production, testing)
            
        Returns:
            IlanaConfig object with all settings
        """
        
        # Determine environment
        if environment is None:
            environment = os.getenv("ENVIRONMENT", "development")
            
        # Check cache
        if environment in self._config_cache:
            return self._config_cache[environment]
            
        # Load environment file
        env_file = self.environments_dir / f"{environment}.env"
        env_vars = {}
        
        if env_file.exists():
            env_vars = self._load_env_file(env_file)
            logger.info(f"Loaded configuration from {env_file}")
        else:
            logger.info(f"Environment file not found: {env_file}; falling back to environment variables.")
            
        # Override with actual environment variables
        env_vars.update(os.environ)
        
        # Create configuration
        config = self._create_config(environment, env_vars)
        
        # Validate configuration
        self._validate_config(config)
        
        # Cache and return
        self._config_cache[environment] = config
        return config
        
    def _load_env_file(self, env_file: Path) -> Dict[str, str]:
        """Load environment variables from .env file"""
        
        env_vars = {}
        
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                    
                # Parse key=value
                if '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
                    
        return env_vars
        
    def _create_config(self, environment: str, env_vars: Dict[str, str]) -> IlanaConfig:
        """Create IlanaConfig from environment variables"""
        
        def get_env(key: str, default: Any = None, required: bool = False) -> Any:
            value = env_vars.get(key, default)
            
            if key.startswith('AZURE_OPENAI'):
                logger.info(f"🔍 CONFIG DEBUG: {key} = {value[:20] + '...' if isinstance(value, str) and len(value) > 20 else value}")
            
            if required and value is None:
                raise ValueError(f"Required environment variable missing: {key}")
                
            # Convert string booleans
            if isinstance(value, str):
                if value.lower() in ('true', 'yes', '1'):
                    return True
                elif value.lower() in ('false', 'no', '0'):
                    return False
                    
            # Convert string integers
            if isinstance(value, str) and value.isdigit():
                return int(value)
                
            return value
            
        # Create configuration object
        config = IlanaConfig(
            # Environment
            environment=environment,
            
            # PubmedBERT
            pubmedbert_endpoint_url=get_env("PUBMEDBERT_ENDPOINT_URL", required=True),
            huggingface_api_key=get_env("HUGGINGFACE_API_KEY", required=True),
            
            # Azure OpenAI
            azure_openai_endpoint=get_env("AZURE_OPENAI_ENDPOINT", required=True),
            azure_openai_api_key=get_env("AZURE_OPENAI_API_KEY", required=True),
            azure_openai_deployment=get_env("AZURE_OPENAI_DEPLOYMENT", required=True),
            
            # Pinecone
            pinecone_api_key=get_env("PINECONE_API_KEY", required=True),
            pinecone_environment=get_env("PINECONE_ENVIRONMENT", required=True),
            pinecone_index_name=get_env("PINECONE_INDEX_NAME", "protocol-intelligence-768"),
            
            # Azure ML
            azure_ml_key_identifier=get_env("AZURE_ML_KEY_IDENTIFIER", ""),
            ml_endpoint_auth_key=get_env("ML_ENDPOINT_AUTH_KEY", ""),
            
            # Azure Static Apps
            azure_static_app_token=get_env("AZURE_STATIC_APP_TOKEN", ""),
            appsource_webhook_secret=get_env("APPSOURCE_WEBHOOK_SECRET", ""),
            
            # Paths
            protocol_database_path=get_env("PROTOCOL_DATABASE_PATH", "./data/protocols/"),
            regulatory_database_path=get_env("REGULATORY_DATABASE_PATH", "./data/regulatory/"),
            embeddings_cache_path=get_env("EMBEDDINGS_CACHE_PATH", "./data/embeddings/"),
            model_cache_dir=get_env("MODEL_CACHE_DIR", "./ml-models/cache/"),
            log_file=get_env("LOG_FILE", "./logs/ilana.log"),
            
            # Performance
            max_sequence_length=get_env("MAX_SEQUENCE_LENGTH", 512),
            batch_size=get_env("BATCH_SIZE", 32),
            max_workers=get_env("MAX_WORKERS", 4),
            timeout_seconds=get_env("TIMEOUT_SECONDS", 30),
            embedding_dimensions=get_env("EMBEDDING_DIMENSIONS", 768),
            
            # Security
            cors_origins=get_env("CORS_ORIGINS", "*"),
            api_rate_limit=get_env("API_RATE_LIMIT", 100),
            max_payload_size=get_env("MAX_PAYLOAD_SIZE", 10485760),
            
            # Features
            enable_continuous_learning=get_env("ENABLE_CONTINUOUS_LEARNING", True),
            enable_advanced_analytics=get_env("ENABLE_ADVANCED_ANALYTICS", True),
            enable_pinecone_integration=get_env("ENABLE_PINECONE_INTEGRATION", True),
            enable_azure_openai=get_env("ENABLE_AZURE_OPENAI", True)
        )
        
        return config
        
    def _validate_config(self, config: IlanaConfig):
        """Validate configuration settings"""
        
        # Validate URLs
        required_urls = [
            config.pubmedbert_endpoint_url,
            config.azure_openai_endpoint
        ]
        
        for url in required_urls:
            if not url.startswith(('http://', 'https://')):
                raise ValueError(f"Invalid URL format: {url}")
                
        # Validate API keys (basic check)
        required_keys = [
            config.huggingface_api_key,
            config.azure_openai_api_key,
            config.pinecone_api_key
        ]
        
        for key in required_keys:
            if not key or len(key) < 10:
                logger.warning("API key appears to be invalid or missing")
                
        # Validate numeric values
        if config.embedding_dimensions != 768:
            logger.warning(f"Non-standard embedding dimensions: {config.embedding_dimensions}")
            
        if config.max_sequence_length < 128:
            logger.warning(f"Very small max sequence length: {config.max_sequence_length}")
            
        logger.info("Configuration validation completed")
        
    def get_azure_openai_config(self, environment: str = None) -> Dict[str, str]:
        """Get Azure OpenAI configuration for easy integration"""
        
        config = self.load_config(environment)
        
        return {
            "api_type": "azure",
            "api_base": config.azure_openai_endpoint,
            "api_key": config.azure_openai_api_key,
            "api_version": "2024-02-01",
            "deployment": config.azure_openai_deployment
        }
        
    def get_pinecone_config(self, environment: str = None) -> Dict[str, str]:
        """Get Pinecone configuration for vector database integration"""
        
        config = self.load_config(environment)
        
        return {
            "api_key": config.pinecone_api_key,
            "environment": config.pinecone_environment,
            "index_name": config.pinecone_index_name,
            "dimension": config.embedding_dimensions
        }
        
    def get_pubmedbert_config(self, environment: str = None) -> Dict[str, str]:
        """Get PubmedBERT configuration for ML integration"""
        
        config = self.load_config(environment)
        
        return {
            "endpoint_url": config.pubmedbert_endpoint_url,
            "api_key": config.huggingface_api_key,
            "max_sequence_length": config.max_sequence_length,
            "timeout_seconds": config.timeout_seconds
        }
        
    def create_environment_summary(self, environment: str = None) -> Dict[str, Any]:
        """Create environment summary for debugging and monitoring"""
        
        config = self.load_config(environment)
        
        return {
            "environment": config.environment,
            "endpoints": {
                "pubmedbert": config.pubmedbert_endpoint_url,
                "azure_openai": config.azure_openai_endpoint,
                "pinecone_env": config.pinecone_environment
            },
            "features": {
                "continuous_learning": config.enable_continuous_learning,
                "advanced_analytics": config.enable_advanced_analytics,
                "pinecone_integration": config.enable_pinecone_integration,
                "azure_openai": config.enable_azure_openai
            },
            "performance": {
                "max_sequence_length": config.max_sequence_length,
                "batch_size": config.batch_size,
                "max_workers": config.max_workers,
                "embedding_dimensions": config.embedding_dimensions
            },
            "security": {
                "cors_origins": config.cors_origins,
                "api_rate_limit": config.api_rate_limit,
                "max_payload_size": config.max_payload_size
            }
        }


# Global configuration loader instance
_config_loader = None

def get_config_loader() -> ConfigLoader:
    """Get global configuration loader instance"""
    global _config_loader
    
    if _config_loader is None:
        _config_loader = ConfigLoader()
        
    return _config_loader

def get_config(environment: str = None) -> IlanaConfig:
    """Get configuration for specified environment"""
    return get_config_loader().load_config(environment)


# Example usage and testing
if __name__ == "__main__":
    # Test configuration loading
    print("🔧 Testing Ilana Configuration Loader")
    print("=" * 50)
    
    try:
        # Load production configuration
        config = get_config("production")
        
        print(f"✅ Environment: {config.environment}")
        print(f"✅ PubmedBERT Endpoint: {config.pubmedbert_endpoint_url}")
        print(f"✅ Azure OpenAI Endpoint: {config.azure_openai_endpoint}")
        print(f"✅ Pinecone Environment: {config.pinecone_environment}")
        print(f"✅ Embedding Dimensions: {config.embedding_dimensions}")
        
        # Test specific configurations
        azure_config = get_config_loader().get_azure_openai_config("production")
        pinecone_config = get_config_loader().get_pinecone_config("production")
        
        print("\n📊 Azure OpenAI Config:")
        for key, value in azure_config.items():
            if "key" in key.lower():
                print(f"  {key}: {'*' * 20}")
            else:
                print(f"  {key}: {value}")
                
        print("\n🗂️ Pinecone Config:")
        for key, value in pinecone_config.items():
            if "key" in key.lower():
                print(f"  {key}: {'*' * 20}")
            else:
                print(f"  {key}: {value}")
                
        print("\n🎉 Configuration loaded successfully!")
        
    except Exception as e:
        print(f"❌ Configuration loading failed: {str(e)}")
        
    # Generate environment summary
    try:
        summary = get_config_loader().create_environment_summary("production")
        
        print("\n📋 Environment Summary:")
        print(json.dumps(summary, indent=2))
        
    except Exception as e:
        print(f"❌ Environment summary failed: {str(e)}")