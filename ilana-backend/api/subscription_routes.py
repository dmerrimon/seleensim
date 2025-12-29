"""
Subscription Status API

Lightweight endpoint for Word Add-in to check trial/subscription status.
Works with optional authentication - returns sensible defaults without token.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import (
    get_db,
    get_tenant_by_azure_id,
    get_active_subscription,
)
from auth import get_optional_current_user, TokenClaims
from trial_manager import get_trial_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/subscription", tags=["subscription"])


# =============================================================================
# Response Models
# =============================================================================

class SubscriptionStatus(BaseModel):
    """Simplified subscription status for Word Add-in"""
    is_trial: bool
    days_remaining: Optional[int] = None
    status: str  # 'active', 'expired', 'grace', 'blocked'
    is_blocked: bool


# =============================================================================
# Optional Auth Dependency
# =============================================================================

async def get_optional_current_user_from_header(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Optional[TokenClaims]:
    """
    Extract user claims from Authorization header if present.
    Returns None if no token or invalid token.
    """
    if not authorization:
        return None

    if not authorization.startswith("Bearer "):
        return None

    token = authorization[7:]  # Remove "Bearer " prefix

    try:
        from auth import validate_token
        claims = validate_token(token)
        return claims
    except Exception as e:
        logger.debug(f"Token validation failed: {e}")
        return None


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/status", response_model=SubscriptionStatus)
async def get_subscription_status(
    claims: Optional[TokenClaims] = Depends(get_optional_current_user_from_header),
    db: Session = Depends(get_db),
):
    """
    Get subscription status for Word Add-in.

    This endpoint works with optional authentication:
    - With valid token: Returns actual subscription status
    - Without token: Returns default active trial (to allow Add-in to work initially)

    Used by the Word Add-in to determine if paywall should be shown.
    """
    # If no authentication, return default active status
    # This prevents blocking users who haven't set up auth yet
    if not claims:
        logger.debug("No claims provided - returning default active status")
        return SubscriptionStatus(
            is_trial=True,
            days_remaining=14,
            status="active",
            is_blocked=False,
        )

    # Get tenant and subscription
    tenant = get_tenant_by_azure_id(db, claims.tenant_id)
    if not tenant:
        logger.warning(f"Tenant not found for Azure ID: {claims.tenant_id}")
        return SubscriptionStatus(
            is_trial=True,
            days_remaining=14,
            status="active",
            is_blocked=False,
        )

    subscription = get_active_subscription(db, tenant.id)
    if not subscription:
        logger.warning(f"No subscription found for tenant: {tenant.id}")
        return SubscriptionStatus(
            is_trial=True,
            days_remaining=0,
            status="expired",
            is_blocked=True,
        )

    # Get trial status from trial_manager
    trial_info = get_trial_status(subscription)

    # Map trial_manager status to frontend expected values
    # trial_manager returns: 'active', 'expired', 'blocked'
    # Frontend expects: 'active', 'expired', 'grace', 'blocked'
    status = trial_info["status"]
    is_blocked = trial_info.get("is_blocked", False)

    # If in grace period (expired but not blocked), status is 'grace'
    if status == "expired" and not is_blocked:
        status = "grace"

    # If actively blocked, ensure is_blocked is True
    if status == "blocked":
        is_blocked = True

    return SubscriptionStatus(
        is_trial=trial_info["is_trial"],
        days_remaining=trial_info.get("days_remaining"),
        status=status,
        is_blocked=is_blocked,
    )


# =============================================================================
# Health Check
# =============================================================================

@router.get("/health")
async def subscription_health():
    """Health check for subscription endpoints"""
    return {"status": "ok"}


# Export
__all__ = ["router"]
