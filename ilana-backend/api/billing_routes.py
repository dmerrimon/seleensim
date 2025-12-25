"""
Billing Status API

Read-only endpoints for Admin Portal to display billing status.
No self-serve modifications - all changes happen in Stripe Dashboard.
"""

import os
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Stripe is optional - will be None if not installed
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    stripe = None
    STRIPE_AVAILABLE = False

from database import (
    get_db,
    get_db_session,
    get_tenant_by_azure_id,
    get_active_subscription,
    get_user_by_azure_id,
    count_active_seats,
)
from auth import TokenClaims, get_current_user
from trial_manager import get_trial_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["billing"])

# Stripe configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
if STRIPE_SECRET_KEY and STRIPE_AVAILABLE:
    stripe.api_key = STRIPE_SECRET_KEY


# =============================================================================
# Admin Verification
# =============================================================================

async def verify_admin(
    claims: TokenClaims = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TokenClaims:
    """
    Verify the current user is an admin.

    Checks database for is_admin flag.
    """
    tenant = get_tenant_by_azure_id(db, claims.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    user = get_user_by_azure_id(db, tenant.id, claims.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    return claims


# =============================================================================
# Response Models
# =============================================================================

class BillingStatus(BaseModel):
    """Billing status for Admin Portal display"""

    # Subscription status
    status: str  # "trial", "active", "past_due", "cancelled", "expired"
    plan_type: str  # "trial", "active", "expired"

    # Seat allocation
    seats_used: int
    seats_total: int

    # Trial info (if applicable)
    is_trial: bool
    trial_days_remaining: Optional[int] = None
    trial_ends_at: Optional[str] = None

    # Stripe info (if connected)
    has_stripe_subscription: bool
    next_billing_date: Optional[str] = None
    billing_interval: Optional[str] = None  # "month" or "year"

    # Contact info
    contact_email: str = "sales@ilanaimmersive.com"
    message: Optional[str] = None


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/status", response_model=BillingStatus)
async def get_billing_status(
    claims: TokenClaims = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    Get billing status for the current tenant.

    Returns subscription details, seat usage, and trial status.
    Admin access required.
    """
    tenant = get_tenant_by_azure_id(db, claims.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    subscription = get_active_subscription(db, tenant.id)
    if not subscription:
        raise HTTPException(status_code=404, detail="No subscription found")

    # Get trial status
    trial_info = get_trial_status(subscription)

    # Count seats
    seats_used = count_active_seats(db, subscription.id)

    # Determine overall status
    if subscription.plan_type == "trial":
        if trial_info["status"] == "active":
            status = "trial"
        elif trial_info["status"] == "expired":
            status = "expired"
        else:
            status = trial_info["status"]
    elif subscription.status == "cancelled":
        status = "cancelled"
    elif subscription.plan_type == "expired":
        status = "expired"
    else:
        status = "active"

    # Get Stripe subscription details if available
    next_billing_date = None
    billing_interval = None

    if subscription.stripe_subscription_id and STRIPE_SECRET_KEY and STRIPE_AVAILABLE:
        try:
            stripe_sub = stripe.Subscription.retrieve(
                subscription.stripe_subscription_id
            )
            # Get next billing date
            if stripe_sub.get("current_period_end"):
                next_billing_date = datetime.fromtimestamp(
                    stripe_sub["current_period_end"]
                ).isoformat()

            # Get billing interval from first item
            items = stripe_sub.get("items", {}).get("data", [])
            if items:
                price = items[0].get("price", {})
                recurring = price.get("recurring", {})
                billing_interval = recurring.get("interval", "month")

            # Check for past_due status
            if stripe_sub.get("status") == "past_due":
                status = "past_due"

        except Exception as e:
            logger.warning(f"Failed to fetch Stripe subscription: {e}")

    # Build message
    if status == "trial":
        message = f"Trial: {trial_info['days_remaining']} days remaining"
    elif status == "past_due":
        message = "Payment past due - please update billing"
    elif status == "expired":
        message = "Subscription expired - contact sales to renew"
    elif status == "cancelled":
        message = "Subscription cancelled"
    else:
        message = None

    return BillingStatus(
        status=status,
        plan_type=subscription.plan_type,
        seats_used=seats_used,
        seats_total=subscription.seat_count,
        is_trial=subscription.plan_type == "trial",
        trial_days_remaining=trial_info.get("days_remaining") if trial_info["is_trial"] else None,
        trial_ends_at=trial_info.get("trial_ends_at") if trial_info["is_trial"] else None,
        has_stripe_subscription=bool(subscription.stripe_subscription_id),
        next_billing_date=next_billing_date,
        billing_interval=billing_interval,
        message=message,
    )


# Export
__all__ = ["router"]
