"""
AppSource Webhook Handlers

Handles license update notifications from Microsoft AppSource.
When customers purchase, upgrade, or cancel subscriptions, Microsoft
calls these webhooks to notify us of the changes.

Webhook Types:
- Subscription Created: New customer purchased
- Subscription Updated: Seat count or plan changed
- Subscription Cancelled: Customer cancelled

Security: Webhooks are validated using a shared secret
"""

import os
import hmac
import hashlib
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db_session, get_tenant_by_azure_id
from seat_manager import update_seat_count

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

# Webhook secret for validation
APPSOURCE_WEBHOOK_SECRET = os.getenv("APPSOURCE_WEBHOOK_SECRET", "")


# =============================================================================
# Request Models
# =============================================================================

class AppSourceWebhookPayload(BaseModel):
    """
    AppSource SaaS webhook payload

    Reference: https://docs.microsoft.com/en-us/azure/marketplace/partner-center-portal/pc-saas-fulfillment-webhook
    """
    id: str  # Webhook notification ID
    activityId: str  # Correlation ID
    publisherId: str  # Your publisher ID
    offerId: str  # Your offer ID
    planId: str  # Plan ID (e.g., "free", "pro")
    quantity: Optional[int] = None  # Number of seats
    subscriptionId: str  # AppSource subscription ID
    timeStamp: str  # ISO timestamp
    action: str  # Action type
    status: str  # Current status

    # Purchaser info (optional)
    purchaser: Optional[dict] = None

    # Beneficiary info (the tenant using the product)
    beneficiary: Optional[dict] = None


class WebhookResponse(BaseModel):
    """Response to webhook"""
    success: bool
    message: str


# =============================================================================
# Webhook Validation
# =============================================================================

def validate_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str
) -> bool:
    """
    Validate webhook signature using HMAC-SHA256

    Microsoft signs webhooks with the shared secret.
    """
    if not secret:
        logger.warning("APPSOURCE_WEBHOOK_SECRET not configured")
        return False

    expected = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


# =============================================================================
# Webhook Endpoints
# =============================================================================

@router.post("/appsource", response_model=WebhookResponse)
async def appsource_webhook(
    request: Request,
    x_ms_signature: Optional[str] = Header(None, alias="x-ms-signature"),
):
    """
    Handle AppSource SaaS fulfillment webhooks

    Called by Microsoft when:
    - New subscription created
    - Subscription quantity changed
    - Subscription cancelled/suspended/reinstated
    """
    # Get raw body for signature validation
    body = await request.body()

    # Validate signature (skip in development if secret not set)
    if APPSOURCE_WEBHOOK_SECRET:
        if not x_ms_signature:
            logger.warning("Webhook received without signature")
            raise HTTPException(status_code=401, detail="Missing signature")

        if not validate_webhook_signature(body, x_ms_signature, APPSOURCE_WEBHOOK_SECRET):
            logger.warning("Webhook signature validation failed")
            raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload
    try:
        payload = AppSourceWebhookPayload.parse_raw(body)
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")

    logger.info(
        f"AppSource webhook received: action={payload.action}, "
        f"subscription={payload.subscriptionId}, quantity={payload.quantity}"
    )

    # Handle different actions
    try:
        if payload.action == "Subscribe":
            return await handle_subscribe(payload)

        elif payload.action == "ChangeQuantity":
            return await handle_change_quantity(payload)

        elif payload.action in ("Unsubscribe", "Suspend"):
            return await handle_cancel(payload)

        elif payload.action == "Reinstate":
            return await handle_reinstate(payload)

        else:
            logger.warning(f"Unknown webhook action: {payload.action}")
            return WebhookResponse(
                success=True,
                message=f"Acknowledged unknown action: {payload.action}"
            )

    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail="Processing failed")


async def handle_subscribe(payload: AppSourceWebhookPayload) -> WebhookResponse:
    """Handle new subscription creation"""
    logger.info(f"New subscription: {payload.subscriptionId}")

    # Extract tenant ID from beneficiary
    tenant_id = None
    if payload.beneficiary:
        tenant_id = payload.beneficiary.get("tenantId")

    if not tenant_id:
        logger.warning("No tenant ID in subscription webhook")
        return WebhookResponse(
            success=True,
            message="Subscription acknowledged (no tenant ID)"
        )

    # Update seat count
    quantity = payload.quantity or 20  # Default to free tier
    plan_type = payload.planId or "free"

    with get_db_session() as db:
        result = update_seat_count(
            db=db,
            azure_tenant_id=tenant_id,
            new_seat_count=quantity,
            appsource_subscription_id=payload.subscriptionId,
            plan_type=plan_type,
        )

    if result.get("success"):
        logger.info(f"Subscription created: {quantity} seats for tenant {tenant_id[:8]}")
        return WebhookResponse(success=True, message="Subscription created")

    return WebhookResponse(success=True, message="Subscription acknowledged")


async def handle_change_quantity(payload: AppSourceWebhookPayload) -> WebhookResponse:
    """Handle seat quantity change"""
    logger.info(f"Quantity change: {payload.subscriptionId} -> {payload.quantity}")

    tenant_id = None
    if payload.beneficiary:
        tenant_id = payload.beneficiary.get("tenantId")

    if not tenant_id or not payload.quantity:
        return WebhookResponse(
            success=True,
            message="Quantity change acknowledged (missing data)"
        )

    with get_db_session() as db:
        result = update_seat_count(
            db=db,
            azure_tenant_id=tenant_id,
            new_seat_count=payload.quantity,
        )

    if result.get("success"):
        logger.info(
            f"Seat count updated: {result.get('old_seat_count')} -> "
            f"{result.get('new_seat_count')} for tenant {tenant_id[:8]}"
        )
        return WebhookResponse(success=True, message="Quantity updated")

    return WebhookResponse(success=True, message="Quantity change acknowledged")


async def handle_cancel(payload: AppSourceWebhookPayload) -> WebhookResponse:
    """Handle subscription cancellation or suspension"""
    logger.info(f"Subscription cancelled/suspended: {payload.subscriptionId}")

    # For now, just log - could set seat count to 0 or mark subscription inactive
    # In production, you might want to give a grace period

    return WebhookResponse(
        success=True,
        message=f"Subscription {payload.action.lower()} acknowledged"
    )


async def handle_reinstate(payload: AppSourceWebhookPayload) -> WebhookResponse:
    """Handle subscription reinstatement"""
    logger.info(f"Subscription reinstated: {payload.subscriptionId}")

    tenant_id = None
    if payload.beneficiary:
        tenant_id = payload.beneficiary.get("tenantId")

    if tenant_id and payload.quantity:
        with get_db_session() as db:
            update_seat_count(
                db=db,
                azure_tenant_id=tenant_id,
                new_seat_count=payload.quantity,
            )

    return WebhookResponse(success=True, message="Subscription reinstated")


# =============================================================================
# Health Check
# =============================================================================

@router.get("/health")
async def webhook_health():
    """Health check for webhook endpoint"""
    return {
        "status": "ok",
        "webhook_secret_configured": bool(APPSOURCE_WEBHOOK_SECRET),
    }


# Export
__all__ = ["router"]
