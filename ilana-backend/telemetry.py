#!/usr/bin/env python3
"""
Telemetry logging helper for Ilana model calls
Provides structured logging with rotation and schema validation
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from logging.handlers import RotatingFileHandler


class TelemetryLogger:
    """
    Telemetry logger with rotating file handler and structured output
    """
    
    def __init__(self, log_dir: str = "./logs", max_bytes: int = 10*1024*1024, backup_count: int = 5):
        """
        Initialize telemetry logger
        
        Args:
            log_dir: Directory for log files
            max_bytes: Maximum bytes per log file (default 10MB)
            backup_count: Number of backup files to keep
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Set up structured logger
        self.logger = logging.getLogger('ilana_telemetry')
        self.logger.setLevel(logging.INFO)
        
        # Prevent duplicate handlers
        if not self.logger.handlers:
            self._setup_handlers(max_bytes, backup_count)
    
    def _setup_handlers(self, max_bytes: int, backup_count: int):
        """Setup file and console handlers"""
        
        # JSON formatter for structured logs
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Rotating file handler
        log_file = self.log_dir / "ilana_telemetry.log"
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=max_bytes, 
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        
        # Console handler for stdout
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        
        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def log_model_call(self, schema_dict: Dict[str, Any]):
        """
        Log a model call with schema validation and structured output
        
        Args:
            schema_dict: Dictionary containing telemetry data matching schema
        """
        try:
            # Validate required fields
            self._validate_schema(schema_dict)
            
            # Create structured log entry
            log_entry = {
                "event_type": "model_call",
                "telemetry": schema_dict,
                "logged_at": datetime.utcnow().isoformat()
            }
            
            # Log as JSON for structured processing
            json_log = json.dumps(log_entry, separators=(',', ':'))
            
            # Determine log level based on success/failure
            if schema_dict.get('error_message'):
                self.logger.error(f"MODEL_CALL_ERROR: {json_log}")
            else:
                self.logger.info(f"MODEL_CALL_SUCCESS: {json_log}")
                
        except Exception as e:
            # Log validation errors
            error_entry = {
                "event_type": "telemetry_error",
                "error": str(e),
                "raw_data": schema_dict,
                "logged_at": datetime.utcnow().isoformat()
            }
            self.logger.error(f"TELEMETRY_ERROR: {json.dumps(error_entry)}")
    
    def _validate_schema(self, data: Dict[str, Any]):
        """
        Validate telemetry data against schema
        
        Args:
            data: Dictionary to validate
            
        Raises:
            ValueError: If validation fails
        """
        required_fields = [
            'request_id', 'user_id_hash', 'doc_id_hash', 'model_path',
            'prompt_hash', 'latency_ms', 'parse_success', 'suggestion_count', 'timestamp'
        ]
        
        # Check required fields
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")
        
        # Validate model_path enum
        if data['model_path'] not in ['simple', 'legacy']:
            raise ValueError(f"Invalid model_path: {data['model_path']}. Must be 'simple' or 'legacy'")
        
        # Validate data types
        if not isinstance(data['latency_ms'], int) or data['latency_ms'] < 0:
            raise ValueError("latency_ms must be a non-negative integer")
        
        if not isinstance(data['parse_success'], bool):
            raise ValueError("parse_success must be a boolean")
        
        if not isinstance(data['suggestion_count'], int) or data['suggestion_count'] < 0:
            raise ValueError("suggestion_count must be a non-negative integer")
        
        # Validate timestamp format
        try:
            datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            raise ValueError("timestamp must be a valid ISO 8601 format")


# Global telemetry logger instance
_telemetry_logger: Optional[TelemetryLogger] = None


def get_telemetry_logger() -> TelemetryLogger:
    """Get or create global telemetry logger instance"""
    global _telemetry_logger
    if _telemetry_logger is None:
        _telemetry_logger = TelemetryLogger()
    return _telemetry_logger


def log_model_call(schema_dict: Dict[str, Any]):
    """
    Log a model call using the global telemetry logger
    
    Args:
        schema_dict: Dictionary containing telemetry data matching schema
    """
    logger = get_telemetry_logger()
    logger.log_model_call(schema_dict)


def create_telemetry_entry(
    request_id: str,
    user_id_hash: str,
    doc_id_hash: str,
    model_path: str,
    prompt_hash: str,
    latency_ms: int,
    parse_success: bool,
    suggestion_count: int,
    error_message: Optional[str] = None,
    timestamp: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a telemetry entry dictionary with proper formatting
    
    Args:
        request_id: UUID string for request
        user_id_hash: SHA-256 hash of user ID
        doc_id_hash: SHA-256 hash of document ID
        model_path: "simple" or "legacy"
        prompt_hash: SHA-256 hash of prompt
        latency_ms: Response latency in milliseconds
        parse_success: Whether parsing succeeded
        suggestion_count: Number of suggestions generated
        error_message: Error message if any (optional)
        timestamp: ISO 8601 timestamp (optional, defaults to now)
        
    Returns:
        Dictionary matching telemetry schema
    """
    return {
        "request_id": request_id,
        "user_id_hash": user_id_hash,
        "doc_id_hash": doc_id_hash,
        "model_path": model_path,
        "prompt_hash": prompt_hash,
        "latency_ms": latency_ms,
        "parse_success": parse_success,
        "suggestion_count": suggestion_count,
        "error_message": error_message,
        "timestamp": timestamp or datetime.utcnow().isoformat()
    }


# Example usage and testing
if __name__ == "__main__":
    import uuid
    import hashlib
    
    print("🔍 Testing Ilana Telemetry Logger")
    print("=" * 50)
    
    # Test successful model call
    success_entry = create_telemetry_entry(
        request_id=str(uuid.uuid4()),
        user_id_hash=hashlib.sha256("test_user_123".encode()).hexdigest(),
        doc_id_hash=hashlib.sha256("protocol_document_456".encode()).hexdigest(),
        model_path="simple",
        prompt_hash=hashlib.sha256("test prompt text".encode()).hexdigest(),
        latency_ms=1250,
        parse_success=True,
        suggestion_count=3
    )
    
    print("✅ Logging successful model call:")
    log_model_call(success_entry)
    
    # Test failed model call
    error_entry = create_telemetry_entry(
        request_id=str(uuid.uuid4()),
        user_id_hash=hashlib.sha256("test_user_456".encode()).hexdigest(),
        doc_id_hash=hashlib.sha256("protocol_document_789".encode()).hexdigest(),
        model_path="legacy",
        prompt_hash=hashlib.sha256("another test prompt".encode()).hexdigest(),
        latency_ms=2100,
        parse_success=False,
        suggestion_count=0,
        error_message="Azure OpenAI timeout after 30 seconds"
    )
    
    print("\n❌ Logging failed model call:")
    log_model_call(error_entry)
    
    # Test validation error
    print("\n🚫 Testing validation error:")
    try:
        invalid_entry = {
            "request_id": "invalid-uuid",
            "model_path": "invalid_path"  # Missing required fields
        }
        log_model_call(invalid_entry)
    except Exception as e:
        print(f"Validation error caught: {e}")
    
    print("\n🎉 Telemetry logging test completed!")
    print(f"📁 Log files written to: ./logs/ilana_telemetry.log")