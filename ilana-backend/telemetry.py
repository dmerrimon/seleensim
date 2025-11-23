"""
Telemetry Module for Ilana Protocol Intelligence API
Provides structured logging with schema validation and performance tracing

Environment Controls:
- ANALYSIS_MODE=hybrid (simple|hybrid|legacy)
- RAG_ASYNC_MODE=true (true|false) 
- ENABLE_TA_ON_DEMAND=true (true|false)
- ENABLE_TA_SHADOW=false (true|false)
"""

import json
import logging
import hashlib
import time
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Union
from pathlib import Path
from logging.handlers import RotatingFileHandler
import threading
from contextlib import contextmanager

# ===== ENVIRONMENT CONFIGURATION =====
# Core Analysis Mode
ANALYSIS_MODE = os.getenv("ANALYSIS_MODE", "simple").lower()  # simple | hybrid | legacy

# RAG and Processing Controls
RAG_ASYNC_MODE = os.getenv("RAG_ASYNC_MODE", "true").lower() == "true"
ENABLE_TA_ON_DEMAND = os.getenv("ENABLE_TA_ON_DEMAND", "true").lower() == "true"
ENABLE_TA_SHADOW = os.getenv("ENABLE_TA_SHADOW", "false").lower() == "true"

# Performance Controls
CHUNK_MAX_CHARS = int(os.getenv("CHUNK_MAX_CHARS", "3500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
SHADOW_TRIGGER_THRESHOLD = float(os.getenv("SHADOW_TRIGGER_THRESHOLD", "0.3"))

# Telemetry Controls
TELEMETRY_ENABLED = os.getenv("TELEMETRY_ENABLED", "true").lower() == "true"
TELEMETRY_LOG_LEVEL = os.getenv("TELEMETRY_LOG_LEVEL", "INFO").upper()

# Load telemetry schema
SCHEMA_PATH = Path(__file__).parent / "telemetry_schema.json"

try:
    with open(SCHEMA_PATH, 'r') as f:
        TELEMETRY_SCHEMA = json.load(f)
except Exception as e:
    print(f"Warning: Could not load telemetry schema: {e}")
    TELEMETRY_SCHEMA = None

# Configure telemetry logger
telemetry_logger = logging.getLogger("ilana_telemetry")
telemetry_logger.setLevel(getattr(logging, TELEMETRY_LOG_LEVEL, logging.INFO))

# Prevent duplicate handlers
if not telemetry_logger.handlers:
    # Console handler (structured JSON to stdout)
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)
    telemetry_logger.addHandler(console_handler)

    # Rotating file handler
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    file_handler = RotatingFileHandler(
        log_dir / "telemetry.log",
        maxBytes=50 * 1024 * 1024,  # 50MB
        backupCount=10,
        encoding='utf-8'
    )
    file_formatter = logging.Formatter('%(asctime)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    telemetry_logger.addHandler(file_handler)

# Thread-local storage for trace context
trace_context = threading.local()

class TelemetryError(Exception):
    """Custom exception for telemetry validation errors"""
    pass

class EnvironmentConfigError(Exception):
    """Custom exception for environment configuration errors"""
    pass

def validate_environment_config() -> Dict[str, Any]:
    """
    Validate environment configuration and return configuration summary
    
    Returns:
        Dict containing configuration status and values
    
    Raises:
        EnvironmentConfigError: If critical configuration is invalid
    """
    config = {
        "ANALYSIS_MODE": ANALYSIS_MODE,
        "RAG_ASYNC_MODE": RAG_ASYNC_MODE,
        "ENABLE_TA_ON_DEMAND": ENABLE_TA_ON_DEMAND,
        "ENABLE_TA_SHADOW": ENABLE_TA_SHADOW,
        "CHUNK_MAX_CHARS": CHUNK_MAX_CHARS,
        "CHUNK_OVERLAP": CHUNK_OVERLAP,
        "SHADOW_TRIGGER_THRESHOLD": SHADOW_TRIGGER_THRESHOLD,
        "TELEMETRY_ENABLED": TELEMETRY_ENABLED,
        "TELEMETRY_LOG_LEVEL": TELEMETRY_LOG_LEVEL
    }
    
    errors = []
    warnings = []
    
    # Validate ANALYSIS_MODE
    if ANALYSIS_MODE not in ["simple", "hybrid", "legacy"]:
        errors.append(f"Invalid ANALYSIS_MODE: {ANALYSIS_MODE}. Must be: simple, hybrid, legacy")
    
    # Validate numeric ranges
    if CHUNK_MAX_CHARS < 100:
        errors.append(f"CHUNK_MAX_CHARS too small: {CHUNK_MAX_CHARS}. Must be >= 100")
    elif CHUNK_MAX_CHARS > 50000:
        warnings.append(f"CHUNK_MAX_CHARS very large: {CHUNK_MAX_CHARS}. May impact performance")
    
    if CHUNK_OVERLAP < 0 or CHUNK_OVERLAP >= CHUNK_MAX_CHARS:
        errors.append(f"Invalid CHUNK_OVERLAP: {CHUNK_OVERLAP}. Must be 0 <= overlap < max_chars")
    
    if not 0 <= SHADOW_TRIGGER_THRESHOLD <= 1:
        errors.append(f"Invalid SHADOW_TRIGGER_THRESHOLD: {SHADOW_TRIGGER_THRESHOLD}. Must be 0-1")
    
    # Validate log level
    if TELEMETRY_LOG_LEVEL not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        warnings.append(f"Unknown TELEMETRY_LOG_LEVEL: {TELEMETRY_LOG_LEVEL}. Defaulting to INFO")
    
    # Configuration logic warnings (suppressed - this is expected behavior)
    # if RAG_ASYNC_MODE and ENABLE_TA_ON_DEMAND:
    #     warnings.append("RAG_ASYNC_MODE=true will block synchronous TA operations")
    
    if ENABLE_TA_SHADOW and not ENABLE_TA_ON_DEMAND:
        warnings.append("ENABLE_TA_SHADOW=true but ENABLE_TA_ON_DEMAND=false - shadow worker may not trigger")
    
    if errors:
        raise EnvironmentConfigError(f"Environment validation failed: {'; '.join(errors)}")
    
    return {
        "valid": True,
        "config": config,
        "warnings": warnings,
        "schema_loaded": TELEMETRY_SCHEMA is not None
    }

def log_environment_config() -> None:
    """Log current environment configuration"""
    try:
        config_info = validate_environment_config()
        
        telemetry_logger.info("🔧 Environment Configuration Validated")
        telemetry_logger.info(f"   ANALYSIS_MODE: {ANALYSIS_MODE}")
        telemetry_logger.info(f"   RAG_ASYNC_MODE: {RAG_ASYNC_MODE}")
        telemetry_logger.info(f"   ENABLE_TA_ON_DEMAND: {ENABLE_TA_ON_DEMAND}")
        telemetry_logger.info(f"   ENABLE_TA_SHADOW: {ENABLE_TA_SHADOW}")
        telemetry_logger.info(f"   CHUNK_MAX_CHARS: {CHUNK_MAX_CHARS}")
        telemetry_logger.info(f"   TELEMETRY_ENABLED: {TELEMETRY_ENABLED}")
        telemetry_logger.info(f"   Schema Loaded: {config_info['schema_loaded']}")
        
        # Log warnings
        for warning in config_info['warnings']:
            telemetry_logger.warning(f"⚠️  {warning}")
            
    except EnvironmentConfigError as e:
        telemetry_logger.error(f"❌ Environment Configuration Error: {e}")
        raise
    except Exception as e:
        telemetry_logger.error(f"❌ Failed to log environment config: {e}")

def get_analysis_mode_metadata() -> Dict[str, Any]:
    """Get metadata about current analysis mode configuration"""
    return {
        "analysis_mode": ANALYSIS_MODE,
        "rag_async_enabled": RAG_ASYNC_MODE,
        "ta_on_demand_enabled": ENABLE_TA_ON_DEMAND,
        "shadow_worker_enabled": ENABLE_TA_SHADOW,
        "shadow_trigger_threshold": SHADOW_TRIGGER_THRESHOLD,
        "chunking_enabled": True,
        "chunk_max_chars": CHUNK_MAX_CHARS,
        "chunk_overlap": CHUNK_OVERLAP
    }

def hash_string(value: Union[str, None]) -> Optional[str]:
    """Generate MD5 hash of string for privacy"""
    if value is None:
        return None
    return hashlib.md5(str(value).encode('utf-8')).hexdigest()

def validate_event_schema(event: Dict[str, Any]) -> None:
    """Validate telemetry event against schema"""
    if not TELEMETRY_SCHEMA:
        return  # Skip validation if schema not loaded
    
    required_fields = TELEMETRY_SCHEMA.get("required", [])
    
    # Check required fields
    for field in required_fields:
        if field not in event:
            raise TelemetryError(f"Missing required field: {field}")
    
    # Validate field types and enums
    properties = TELEMETRY_SCHEMA.get("properties", {})
    
    for field, value in event.items():
        if field not in properties:
            continue
            
        field_schema = properties[field]
        
        # Type validation
        expected_types = field_schema.get("type")
        if isinstance(expected_types, str):
            expected_types = [expected_types]
        
        if expected_types and value is not None:
            python_type_map = {
                "string": str,
                "integer": int,
                "boolean": bool,
                "object": dict,
                "array": list,
                "number": (int, float)
            }
            
            valid_type = False
            for expected_type in expected_types:
                if expected_type == "null" and value is None:
                    valid_type = True
                    break
                elif expected_type in python_type_map:
                    if isinstance(value, python_type_map[expected_type]):
                        valid_type = True
                        break
            
            if not valid_type:
                raise TelemetryError(f"Invalid type for {field}: expected {expected_types}, got {type(value).__name__}")
        
        # Enum validation
        if "enum" in field_schema and value is not None:
            if value not in field_schema["enum"]:
                raise TelemetryError(f"Invalid value for {field}: {value}. Must be one of {field_schema['enum']}")
        
        # Minimum value validation
        if "minimum" in field_schema and isinstance(value, (int, float)):
            if value < field_schema["minimum"]:
                raise TelemetryError(f"Value for {field} below minimum: {value} < {field_schema['minimum']}")

def extract_user_id_from_request(request_data: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> str:
    """Extract and hash user identifier from request"""
    # Try multiple sources for user identification
    user_id = None
    
    # Check headers first
    if headers:
        user_id = headers.get('X-User-ID') or headers.get('Authorization')
    
    # Fallback to request IP or generate from request content
    if not user_id:
        user_id = request_data.get('client_ip', 'unknown')
    
    # Use request data hash as fallback
    if user_id == 'unknown':
        content_hash = hash_string(json.dumps(request_data, sort_keys=True))
        user_id = f"anonymous_{content_hash[:8]}"
    
    return hash_string(user_id)

def count_suggestions(response_data: Any) -> int:
    """Count suggestions in response data"""
    if not response_data:
        return 0
    
    try:
        # Handle different response formats
        if isinstance(response_data, dict):
            # Direct suggestions array
            if "suggestions" in response_data:
                suggestions = response_data["suggestions"]
                if isinstance(suggestions, list):
                    return len(suggestions)
                elif isinstance(suggestions, dict) and "raw" in suggestions:
                    # Parse nested JSON
                    try:
                        raw_data = json.loads(suggestions["raw"])
                        if "suggestions" in raw_data:
                            return len(raw_data["suggestions"])
                    except (json.JSONDecodeError, TypeError):
                        pass
            
            # Check nested result
            if "result" in response_data:
                return count_suggestions(response_data["result"])
        
        return 0
        
    except Exception:
        return 0

def log_model_call(event: Dict[str, Any]) -> None:
    """
    Log telemetry event with schema validation
    
    Args:
        event: Dictionary containing telemetry data
    """
    # Skip logging if telemetry is disabled
    if not TELEMETRY_ENABLED:
        return
        
    try:
        # Add timestamp if not provided
        if "timestamp" not in event:
            event["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        # Add environment metadata to event
        if "metadata" not in event:
            event["metadata"] = {}
        
        # Add analysis mode configuration to metadata
        env_metadata = get_analysis_mode_metadata()
        event["metadata"].update(env_metadata)
        
        # Validate against schema
        validate_event_schema(event)
        
        # Log structured JSON
        telemetry_json = json.dumps(event, separators=(',', ':'))
        telemetry_logger.info(telemetry_json)
        
    except TelemetryError as e:
        telemetry_logger.error(f"Telemetry validation error: {e}")
    except Exception as e:
        telemetry_logger.error(f"Telemetry logging error: {e}")

def start_trace(
    analyze_mode: str,
    model_path: str,
    request_data: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None
) -> str:
    """
    Start performance trace and return request_id
    
    Args:
        analyze_mode: Type of analysis being performed
        model_path: Model/pipeline path being used
        request_data: Request payload
        headers: Request headers
        
    Returns:
        request_id: Unique identifier for this trace
    """
    import uuid
    
    request_id = str(uuid.uuid4())
    
    # Store trace context
    trace_context.request_id = request_id
    trace_context.start_time = time.time()
    trace_context.analyze_mode = analyze_mode
    trace_context.model_path = model_path
    
    # Extract metadata
    text_content = request_data.get('text', '')
    doc_id = request_data.get('doc_id')
    
    # Log start event
    start_event = {
        "request_id": request_id,
        "user_id_hash": extract_user_id_from_request(request_data, headers),
        "doc_id_hash": hash_string(doc_id),
        "analyze_mode": analyze_mode,
        "model_path": model_path,
        "prompt_hash": hash_string(text_content),
        "latency_ms": 0,
        "parse_success": True,
        "suggestion_count": 0,
        "error_message": None,
        "event_type": "start",
        "metadata": {
            "text_length": len(text_content),
            "shadow_triggered": False
        }
    }
    
    log_model_call(start_event)
    
    return request_id

def end_trace(
    request_id: Optional[str] = None,
    response_data: Any = None,
    error_message: Optional[str] = None,
    additional_metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    End performance trace and log completion event
    
    Args:
        request_id: Request ID (uses current trace if None)
        response_data: Response data to analyze
        error_message: Error message if request failed
        additional_metadata: Additional metadata to include
    """
    try:
        # Get trace context
        if request_id is None:
            request_id = getattr(trace_context, 'request_id', None)
        
        if not request_id:
            telemetry_logger.warning("No request_id found for end_trace")
            return
        
        start_time = getattr(trace_context, 'start_time', time.time())
        analyze_mode = getattr(trace_context, 'analyze_mode', 'unknown')
        model_path = getattr(trace_context, 'model_path', 'unknown')
        
        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Determine success/error
        event_type = "error" if error_message else "success"
        parse_success = error_message is None
        
        # Count suggestions
        suggestion_count = count_suggestions(response_data) if response_data else 0
        
        # Build metadata
        metadata = {
            "response_size": len(json.dumps(response_data)) if response_data else 0
        }
        
        if additional_metadata:
            metadata.update(additional_metadata)
        
        # Log completion event
        completion_event = {
            "request_id": request_id,
            "user_id_hash": getattr(trace_context, 'user_id_hash', hash_string('unknown')),
            "doc_id_hash": getattr(trace_context, 'doc_id_hash', None),
            "analyze_mode": analyze_mode,
            "model_path": model_path,
            "prompt_hash": getattr(trace_context, 'prompt_hash', None),
            "latency_ms": latency_ms,
            "parse_success": parse_success,
            "suggestion_count": suggestion_count,
            "error_message": error_message,
            "event_type": event_type,
            "metadata": metadata
        }
        
        log_model_call(completion_event)
        
    except Exception as e:
        telemetry_logger.error(f"Error in end_trace: {e}")
    finally:
        # Clean up trace context
        for attr in ['request_id', 'start_time', 'analyze_mode', 'model_path', 'user_id_hash', 'doc_id_hash', 'prompt_hash']:
            if hasattr(trace_context, attr):
                delattr(trace_context, attr)

@contextmanager
def trace_request(
    analyze_mode: str,
    model_path: str,
    request_data: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None
):
    """
    Context manager for automatic request tracing
    
    Usage:
        with trace_request("selection", "simple_inproc", request_data) as request_id:
            # ... perform work ...
            response_data = some_operation()
        # Automatically logs completion
    """
    request_id = start_trace(analyze_mode, model_path, request_data, headers)
    
    try:
        yield request_id
    except Exception as e:
        end_trace(request_id, None, str(e))
        raise
    else:
        # Success case will be logged by the caller using end_trace
        pass

# Export main functions
__all__ = [
    'log_model_call',
    'start_trace',
    'end_trace',
    'trace_request',
    'hash_string',
    'extract_user_id_from_request',
    'count_suggestions',
    'validate_environment_config',
    'log_environment_config',
    'get_analysis_mode_metadata',
    'ANALYSIS_MODE',
    'RAG_ASYNC_MODE',
    'ENABLE_TA_ON_DEMAND',
    'ENABLE_TA_SHADOW'
]

# Initialize and log configuration on import
try:
    log_environment_config()
except EnvironmentConfigError:
    # Let startup continue even if config has errors
    pass