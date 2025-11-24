"""
RL Feedback Module for Ilana Word Add-in

This module handles reinforcement learning feedback events from the frontend,
including accept/undo actions with strict PHI protection.

Features:
- Pydantic validation for RL feedback events
- Strict PHI redaction enforcement
- Event storage to shadow/feedback/ directory for replay
- Validation of required fields
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, Field, field_validator


class RLFeedbackEvent(BaseModel):
    """
    Reinforcement learning feedback event schema (OpenAPI v1.2 compliant).

    All events must have redactPHI=true and use hashed text instead of raw proprietary content.
    """
    # Required fields
    event: Literal[
        "suggestion_accepted",
        "suggestion_undone",
        "suggestion_inserted_as_comment",
        "suggestion_dismissed",
        "analysis_requested",
        "suggestions_returned",
        "suggestion_shown",
        "comment_resolved"
    ] = Field(..., description="Event type")
    suggestion_id: str = Field(..., description="Unique suggestion identifier")
    request_id: str = Field(..., description="Original request ID")
    user_id_hash: str = Field(..., description="Hashed user identifier (SHA-256)")

    # Optional metadata fields
    tenant_id: Optional[str] = Field(default="default", description="Tenant identifier for B2B multi-tenancy")
    ta: Optional[str] = Field(None, description="Therapeutic area")
    phase: Optional[str] = Field(None, description="Deployment phase")
    model_path: Optional[str] = Field(None, description="Model path used for suggestion")
    latency_ms: Optional[int] = Field(None, description="API response latency in milliseconds")
    accepted_at: Optional[str] = Field(None, description="ISO 8601 timestamp of acceptance")
    timestamp: Optional[str] = Field(None, description="ISO 8601 timestamp")

    # Comment tracking (for comment insertion events)
    comment_id: Optional[str] = Field(None, description="Word comment ID (if available)")

    # Proprietary content-protected fields (hashes only)
    original_text_hash: Optional[str] = Field(None, description="SHA-256 hash of original text")
    context_snippet_hash: Optional[str] = Field(None, description="SHA-256 hash of context snippet")

    # Backward compatibility
    action: Optional[str] = Field(None, description="Legacy action field (deprecated, use 'event' instead)")
    reason: Optional[str] = Field(None, description="Reason for action (e.g., 'user_undo', 'manual_dismiss')")
    improved_text_hash: Optional[str] = Field(None, description="SHA-256 hash of improved text")
    context_snippet: Optional[str] = Field(None, description="Redacted context snippet")

    # Content protection flag (REQUIRED)
    redactPHI: bool = Field(default=True, description="Must be true - confirms content redaction")

    @field_validator('redactPHI')
    @classmethod
    def validate_phi_redacted(cls, v):
        """Enforce that redactPHI flag is always true."""
        if not v:
            raise ValueError("redactPHI must be true for all RL feedback events")
        return v

    @field_validator('user_id_hash', 'original_text_hash', 'improved_text_hash')
    @classmethod
    def validate_hash_format(cls, v):
        """Ensure hashes are valid SHA-256 format (64 hex chars)."""
        if v and not re.match(r'^[a-f0-9]{64}$', v):
            # Allow special values like 'anonymous' or 'hash_error'
            if v not in ['anonymous', 'hash_error', 'unknown']:
                raise ValueError(f"Hash must be 64 hex characters (SHA-256), got: {v[:20]}...")
        return v

    @field_validator('context_snippet')
    @classmethod
    def validate_no_phi_patterns(cls, v):
        """
        Basic PHI pattern detection in context snippets.
        Warns if potentially sensitive patterns are detected.
        """
        if not v:
            return v

        # Basic PHI patterns (names, dates, SSN-like patterns)
        phi_patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN pattern
            r'\b\d{2}/\d{2}/\d{4}\b',  # Date pattern
            r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',  # Name-like pattern
        ]

        for pattern in phi_patterns:
            if re.search(pattern, v):
                # Don't raise error, but log warning
                print(f"⚠️ Potential PHI pattern detected in context_snippet: {pattern}")

        return v


class ReinforcementEvent(BaseModel):
    """
    Legacy reinforcement event schema for /api/reinforce endpoint.
    More permissive than RLFeedbackEvent for backward compatibility.
    """
    suggestion_id: str
    request_id: str
    user_id_hash: str
    tenant_id: str = "default"
    ta: str = "general_medicine"
    phase: str = "production"
    action: str = "accept"
    timestamp: str

    # Text fields (may contain PHI in legacy calls, but discouraged)
    original_text: Optional[str] = None
    improved_text: Optional[str] = None
    context_snippet: Optional[str] = None

    # Optional PHI protection flag
    redactPHI: bool = Field(default=False, description="PHI redaction flag")
    analysis_mode: Optional[str] = Field(default="simple", description="Analysis mode")


def validate_phi_redacted(payload: dict) -> Tuple[bool, Optional[str]]:
    """
    Validate that PHI is properly redacted in payload.

    Returns:
        (is_valid, error_message)
    """
    if not payload.get('redactPHI'):
        return False, "redactPHI flag must be true"

    # Check for raw text fields (should not be present in RL feedback)
    sensitive_fields = ['original_text', 'improved_text']
    found_fields = [f for f in sensitive_fields if f in payload]

    if found_fields:
        return False, f"Raw text fields not allowed: {', '.join(found_fields)}. Use hashes instead."

    return True, None


def store_feedback_event(event: RLFeedbackEvent, event_type: str = "rl_feedback") -> dict:
    """
    Store RL feedback event to shadow/feedback/ directory as JSON.

    Args:
        event: Validated RLFeedbackEvent
        event_type: Type of event (default: "rl_feedback")

    Returns:
        dict with storage result
    """
    try:
        # Create shadow/feedback directory if it doesn't exist
        feedback_dir = Path(__file__).parent / "shadow" / "feedback"
        feedback_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp and suggestion_id
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{event_type}_{timestamp}_{event.suggestion_id}.json"
        filepath = feedback_dir / filename

        # Write event to file
        with open(filepath, 'w') as f:
            json.dump(event.model_dump(), f, indent=2)

        print(f"✅ Stored RL feedback event: {filepath}")

        return {
            "success": True,
            "filepath": str(filepath),
            "event_type": event_type,
            "suggestion_id": event.suggestion_id
        }

    except Exception as e:
        print(f"❌ Failed to store RL feedback event: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def store_reinforcement_event(event: ReinforcementEvent) -> dict:
    """
    Store legacy reinforcement event to shadow/feedback/ directory.

    Args:
        event: Validated ReinforcementEvent

    Returns:
        dict with storage result
    """
    try:
        # Create shadow/feedback directory if it doesn't exist
        feedback_dir = Path(__file__).parent / "shadow" / "feedback"
        feedback_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp and suggestion_id
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"reinforcement_{timestamp}_{event.suggestion_id}.json"
        filepath = feedback_dir / filename

        # Write event to file (exclude raw PHI if redactPHI is true)
        event_data = event.model_dump()
        if event.redactPHI:
            # Remove raw text fields if PHI redaction is enabled
            for field in ['original_text', 'improved_text']:
                event_data.pop(field, None)

        with open(filepath, 'w') as f:
            json.dump(event_data, f, indent=2)

        print(f"✅ Stored reinforcement event: {filepath}")

        return {
            "success": True,
            "filepath": str(filepath),
            "event_type": "reinforcement",
            "suggestion_id": event.suggestion_id
        }

    except Exception as e:
        print(f"❌ Failed to store reinforcement event: {e}")
        return {
            "success": False,
            "error": str(e)
        }
