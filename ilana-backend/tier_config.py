"""
Tier Configuration for Ilana Protocol Intelligence

Defines feature access and limits for each subscription tier.
Free tier gets basic rule-based analysis (Layers 1-2).
Pro tier gets full analysis with RAG and advanced features (Layers 1-5).
"""

import os
from typing import Dict, Any, Optional

# Tier feature configurations
TIER_CONFIG: Dict[str, Dict[str, Any]] = {
    "free": {
        "max_selection_chars": 5000,
        "token_budget": 1000,
        "max_suggestions": None,  # Unlimited
        "enable_rag": False,
        "enable_amendment_risk": False,
        "enable_table_analysis": False,
        "enable_document_intelligence": False,
        "description": "Basic compliance analysis with rule-based checks",
    },
    "pro": {
        "max_selection_chars": 15000,
        "token_budget": 4000,
        "max_suggestions": None,  # Unlimited
        "enable_rag": True,
        "enable_amendment_risk": True,
        "enable_table_analysis": True,
        "enable_document_intelligence": True,
        "description": "Full analysis with RAG, table analysis, and regulatory citations",
    },
    "enterprise": {
        "max_selection_chars": 50000,
        "token_budget": 8000,
        "max_suggestions": None,
        "enable_rag": True,
        "enable_amendment_risk": True,
        "enable_table_analysis": True,
        "enable_document_intelligence": True,
        "description": "Enterprise-grade analysis with extended limits",
    }
}

# Environment variable to enable tier enforcement
ENFORCE_TIERS = os.getenv("ENFORCE_TIERS", "false").lower() == "true"

# Override tier for testing (set to "free", "pro", or "enterprise")
OVERRIDE_TIER = os.getenv("OVERRIDE_TIER", "")


def get_tier_config(plan_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Get the configuration for a given tier.

    Args:
        plan_type: The subscription plan type (free, pro, enterprise)

    Returns:
        Configuration dict with feature flags and limits
    """
    # Allow override for testing
    if OVERRIDE_TIER:
        plan_type = OVERRIDE_TIER

    # Default to free tier if not specified or invalid
    if not plan_type or plan_type not in TIER_CONFIG:
        plan_type = "free"

    return TIER_CONFIG[plan_type].copy()


def get_default_tier_config() -> Dict[str, Any]:
    """
    Get default (full-featured) config when tier enforcement is disabled.
    Used for backwards compatibility.
    """
    return TIER_CONFIG["pro"].copy()


def is_tier_enforcement_enabled() -> bool:
    """Check if tier enforcement is enabled."""
    return ENFORCE_TIERS


# Export
__all__ = [
    "TIER_CONFIG",
    "ENFORCE_TIERS",
    "get_tier_config",
    "get_default_tier_config",
    "is_tier_enforcement_enabled",
]
