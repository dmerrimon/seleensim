"""
Stripe Webhook Handlers

Handles subscription events from Stripe for self-serve and sales-led billing.

Self-Serve Flow (ilanaimmersive.com):
1. User clicks subscribe → POST /api/stripe/create-checkout-session
2. User completes Stripe Checkout
3. checkout.session.completed webhook → create/update subscription

Sales-Led Flow (manual):
- Create subscriptions in Stripe Dashboard
- Webhooks sync the payment status to backend

Webhook Events (Core):
- checkout.session.completed: Self-serve checkout completion (NEW)
- customer.subscription.created: Link Stripe customer to tenant, set seats
- customer.subscription.updated: Update seat count or status
- customer.subscription.deleted: Expire subscription
- invoice.paid: Confirm payment, ensure access active
- invoice.payment_failed: Flag subscription at risk

Webhook Events (Extended):
- customer.created: Track when customer is created in Stripe
- customer.updated: Handle email/metadata changes
- invoice.finalized: Log when invoice is ready to send
- invoice.payment_action_required: Alert when 3D Secure needed
- payment_intent.succeeded: Track successful one-time payments
- payment_intent.payment_failed: Track failed payment intents

Pricing Tiers:
- Individual: 1 seat - $79/mo or $805/yr
- Team (2-5): $69/seat/mo or $703/seat/yr
- Team+ (6-15): $49/seat/mo or $500/seat/yr

Matching Stripe to Tenant:
- For self-serve: Create tenant/user on first Word Add-in login
- Customer email domain matches tenant
- OR explicit tenant_domain metadata
"""

import os
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

# Stripe is optional - will be None if not installed
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    stripe = None
    STRIPE_AVAILABLE = False

from database import (
    get_db_session,
    get_tenant_by_azure_id,
    Tenant,
    Subscription,
    PendingSubscription,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stripe", tags=["stripe"])

# Stripe configuration
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")

if STRIPE_AVAILABLE and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
elif not STRIPE_SECRET_KEY:
    logger.warning("STRIPE_SECRET_KEY not configured - Stripe features disabled")


# =============================================================================
# Response Models
# =============================================================================

class WebhookResponse(BaseModel):
    """Response to webhook"""
    success: bool
    message: str


# =============================================================================
# Helper Functions
# =============================================================================

def get_tenant_domain_from_customer(customer: dict) -> Optional[str]:
    """
    Extract tenant domain from Stripe customer.

    Looks for:
    1. metadata.tenant_domain (explicit)
    2. Email domain from customer email
    """
    metadata = customer.get("metadata", {})

    # Check explicit metadata first
    if metadata.get("tenant_domain"):
        return metadata["tenant_domain"]

    # Fall back to email domain
    email = customer.get("email", "")
    if email and "@" in email:
        return email.split("@")[1]

    return None


def get_seat_count_from_subscription(subscription: dict) -> int:
    """
    Extract seat count from Stripe subscription.

    Looks for:
    1. metadata.seat_count (explicit)
    2. First item quantity
    3. Default to 10
    """
    metadata = subscription.get("metadata", {})

    # Check explicit metadata
    if metadata.get("seat_count"):
        try:
            return int(metadata["seat_count"])
        except (ValueError, TypeError):
            pass

    # Check subscription item quantity
    items = subscription.get("items", {}).get("data", [])
    if items:
        quantity = items[0].get("quantity", 1)
        if quantity:
            return quantity

    # Default
    return 10


def create_or_update_pending_subscription(
    db,
    stripe_customer_id: str,
    stripe_subscription_id: str,
    customer_email: str,
    customer_email_domain: str,
    seat_count: int,
    plan_type: str = "active",
) -> PendingSubscription:
    """
    Create or update a pending subscription for later linking to Azure AD tenant.

    Called when Stripe checkout completes but no matching tenant exists yet.
    The subscription will be linked when the user signs in via Azure AD.
    """
    # Check for existing pending subscription by customer or subscription ID
    existing = db.query(PendingSubscription).filter(
        (PendingSubscription.stripe_customer_id == stripe_customer_id) |
        (PendingSubscription.stripe_subscription_id == stripe_subscription_id)
    ).first()

    if existing:
        # Update existing pending subscription
        existing.stripe_customer_id = stripe_customer_id
        existing.stripe_subscription_id = stripe_subscription_id
        existing.customer_email = customer_email
        existing.customer_email_domain = customer_email_domain
        existing.seat_count = seat_count
        existing.plan_type = plan_type
        existing.updated_at = datetime.utcnow()
        db.commit()

        logger.info(
            f"Updated pending subscription for {customer_email}: "
            f"{seat_count} seats, domain={customer_email_domain}"
        )
        return existing

    # Create new pending subscription
    pending = PendingSubscription(
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_subscription_id,
        customer_email=customer_email,
        customer_email_domain=customer_email_domain,
        seat_count=seat_count,
        plan_type=plan_type,
        status="pending",
    )
    db.add(pending)
    db.commit()

    logger.info(
        f"Created pending subscription for {customer_email}: "
        f"{seat_count} seats, domain={customer_email_domain}"
    )
    return pending


def find_tenant_by_domain(db, domain: str) -> Optional[Tenant]:
    """
    Find tenant by email domain.

    Note: This requires that users from the same domain
    are already in the system from Azure AD login.
    """
    # Look for any user with this email domain
    from database import User

    user = db.query(User).filter(
        User.email.ilike(f"%@{domain}")
    ).first()

    if user:
        return db.query(Tenant).filter(Tenant.id == user.tenant_id).first()

    return None


def update_subscription_from_stripe(
    db,
    tenant: Tenant,
    stripe_sub: dict,
    stripe_customer_id: str,
) -> dict:
    """
    Update or create subscription from Stripe data.
    """
    from database import get_active_subscription

    subscription = get_active_subscription(db, tenant.id)

    seat_count = get_seat_count_from_subscription(stripe_sub)
    stripe_status = stripe_sub.get("status", "active")

    # Map Stripe status to our status
    if stripe_status in ("active", "trialing"):
        plan_type = "active"
        status = "active"
    elif stripe_status == "past_due":
        plan_type = "active"  # Still active, just past due
        status = "active"
    elif stripe_status in ("canceled", "unpaid", "incomplete_expired"):
        plan_type = "expired"
        status = "expired"
    else:
        plan_type = "active"
        status = "active"

    if subscription:
        # Update existing
        old_seat_count = subscription.seat_count
        subscription.seat_count = seat_count
        subscription.stripe_customer_id = stripe_customer_id
        subscription.stripe_subscription_id = stripe_sub.get("id")
        subscription.plan_type = plan_type
        subscription.status = status
        subscription.converted_at = subscription.converted_at or datetime.utcnow()

        db.commit()

        logger.info(
            f"Updated subscription for tenant {tenant.id}: "
            f"{old_seat_count} -> {seat_count} seats, status={status}"
        )

        return {
            "action": "updated",
            "old_seat_count": old_seat_count,
            "new_seat_count": seat_count,
        }
    else:
        # Create new subscription (replacing trial)
        now = datetime.utcnow()
        subscription = Subscription(
            tenant_id=tenant.id,
            seat_count=seat_count,
            plan_type=plan_type,
            status=status,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_sub.get("id"),
            converted_at=now,
        )
        db.add(subscription)
        db.commit()

        logger.info(
            f"Created subscription for tenant {tenant.id}: "
            f"{seat_count} seats, status={status}"
        )

        return {
            "action": "created",
            "seat_count": seat_count,
        }


# =============================================================================
# Webhook Endpoint
# =============================================================================

@router.post("/webhook", response_model=WebhookResponse)
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events.

    Stripe signs webhooks with the webhook secret for security.
    """
    # Get raw body for signature verification
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    # Verify signature (skip in dev if secret not set)
    if STRIPE_WEBHOOK_SECRET:
        if not sig_header:
            logger.warning("Stripe webhook received without signature")
            raise HTTPException(status_code=401, detail="Missing signature")

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            logger.error(f"Invalid payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {e}")
            raise HTTPException(status_code=401, detail="Invalid signature")
    else:
        # Dev mode - parse without verification
        import json
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON")
        logger.warning("STRIPE_WEBHOOK_SECRET not set - skipping signature verification")

    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    logger.info(f"Stripe webhook received: {event_type}")

    # Route to appropriate handler
    try:
        # Self-serve checkout
        if event_type == "checkout.session.completed":
            return await handle_checkout_completed(data)

        elif event_type == "customer.subscription.created":
            return await handle_subscription_created(data)

        elif event_type == "customer.subscription.updated":
            return await handle_subscription_updated(data)

        elif event_type == "customer.subscription.deleted":
            return await handle_subscription_deleted(data)

        elif event_type == "invoice.paid":
            return await handle_invoice_paid(data)

        elif event_type == "invoice.payment_failed":
            return await handle_payment_failed(data)

        # Extended event handlers
        elif event_type == "customer.created":
            return await handle_customer_created(data)

        elif event_type == "customer.updated":
            return await handle_customer_updated(data)

        elif event_type == "invoice.finalized":
            return await handle_invoice_finalized(data)

        elif event_type == "invoice.payment_action_required":
            return await handle_payment_action_required(data)

        elif event_type == "payment_intent.succeeded":
            return await handle_payment_intent_succeeded(data)

        elif event_type == "payment_intent.payment_failed":
            return await handle_payment_intent_failed(data)

        else:
            # Acknowledge unknown events
            logger.debug(f"Ignoring event type: {event_type}")
            return WebhookResponse(
                success=True,
                message=f"Event {event_type} acknowledged"
            )

    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail="Processing failed")


# =============================================================================
# Event Handlers
# =============================================================================

async def handle_checkout_completed(session: dict) -> WebhookResponse:
    """
    Handle self-serve Stripe Checkout completion.

    Called when user completes checkout on ilanaimmersive.com.
    Creates or updates subscription based on checkout details.

    Session contains:
    - customer_email: Customer's email
    - subscription: Stripe subscription ID (for subscription checkouts)
    - customer: Stripe customer ID
    - metadata: { seat_count: "N" }
    - line_items: Contains quantity (seat count)
    """
    session_id = session.get("id")
    customer_email = session.get("customer_email")
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")
    mode = session.get("mode")  # "subscription" or "payment"

    logger.info(
        f"Checkout completed: session={session_id}, "
        f"email={customer_email}, mode={mode}"
    )

    # Only handle subscription checkouts
    if mode != "subscription":
        logger.info(f"Ignoring non-subscription checkout: {mode}")
        return WebhookResponse(
            success=True,
            message=f"Checkout completed (mode={mode}, not subscription)"
        )

    if not subscription_id:
        logger.warning("No subscription ID in checkout session")
        return WebhookResponse(
            success=True,
            message="Checkout completed (no subscription)"
        )

    # Get seat count from line items
    seat_count = 1  # Default
    try:
        line_items = stripe.checkout.Session.list_line_items(session_id, limit=1)
        if line_items.data:
            seat_count = line_items.data[0].quantity or 1
            logger.info(f"Checkout seat count from line items: {seat_count}")
    except Exception as e:
        logger.warning(f"Could not fetch line items: {e}")
        # Fallback to metadata
        metadata = session.get("metadata", {})
        if metadata.get("seat_count"):
            try:
                seat_count = int(metadata["seat_count"])
            except (ValueError, TypeError):
                pass

    # Get full subscription details
    try:
        stripe_sub = stripe.Subscription.retrieve(subscription_id)
    except Exception as e:
        logger.error(f"Failed to retrieve subscription {subscription_id}: {e}")
        return WebhookResponse(
            success=True,
            message="Checkout completed (subscription lookup failed)"
        )

    # Find tenant by email domain
    if not customer_email or "@" not in customer_email:
        logger.warning(f"No valid email in checkout: {customer_email}")
        return WebhookResponse(
            success=True,
            message="Checkout completed (no valid email - will match on login)"
        )

    domain = customer_email.split("@")[1]

    with get_db_session() as db:
        tenant = find_tenant_by_domain(db, domain)

        if not tenant:
            # No tenant yet - create pending subscription for later linking
            create_or_update_pending_subscription(
                db,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                customer_email=customer_email,
                customer_email_domain=domain,
                seat_count=seat_count,
                plan_type="active",
            )

            logger.info(
                f"No tenant found for domain {domain}. "
                f"Created pending subscription for later linking."
            )
            return WebhookResponse(
                success=True,
                message=f"Pending subscription created for {domain} ({seat_count} seats)"
            )

        # Update subscription with checkout details
        # Override seat count from checkout quantity
        stripe_sub_dict = {
            "id": subscription_id,
            "status": stripe_sub.status,
            "metadata": {"seat_count": str(seat_count)},
            "items": {"data": [{"quantity": seat_count}]},
        }

        result = update_subscription_from_stripe(
            db, tenant, stripe_sub_dict, customer_id
        )

        logger.info(
            f"Checkout subscription linked: tenant={tenant.id}, "
            f"seats={seat_count}, action={result['action']}"
        )

    return WebhookResponse(
        success=True,
        message=f"Subscription created for {domain} ({seat_count} seats)"
    )


async def handle_subscription_created(subscription: dict) -> WebhookResponse:
    """
    Handle new subscription creation.

    This is called when you create a subscription in Stripe Dashboard.
    """
    customer_id = subscription.get("customer")
    if not customer_id:
        return WebhookResponse(success=True, message="No customer ID")

    # Get customer details from Stripe
    try:
        customer = stripe.Customer.retrieve(customer_id)
    except Exception as e:
        logger.error(f"Failed to retrieve customer {customer_id}: {e}")
        return WebhookResponse(success=True, message="Customer lookup failed")

    # Find tenant
    domain = get_tenant_domain_from_customer(customer)
    if not domain:
        logger.warning(f"No domain found for customer {customer_id}")
        return WebhookResponse(
            success=True,
            message="Subscription created (no tenant match - add domain metadata)"
        )

    with get_db_session() as db:
        tenant = find_tenant_by_domain(db, domain)

        if not tenant:
            # Create pending subscription for later linking
            seat_count = get_seat_count_from_subscription(subscription)
            customer_email = customer.get("email", "")

            create_or_update_pending_subscription(
                db,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription.get("id"),
                customer_email=customer_email,
                customer_email_domain=domain,
                seat_count=seat_count,
                plan_type="active",
            )

            logger.info(f"No tenant found for domain {domain} - created pending subscription")
            return WebhookResponse(
                success=True,
                message=f"Pending subscription created for {domain} ({seat_count} seats)"
            )

        result = update_subscription_from_stripe(
            db, tenant, subscription, customer_id
        )

    return WebhookResponse(
        success=True,
        message=f"Subscription {result['action']} for {domain}"
    )


async def handle_subscription_updated(subscription: dict) -> WebhookResponse:
    """
    Handle subscription updates (seat count, status changes).
    """
    stripe_sub_id = subscription.get("id")

    with get_db_session() as db:
        # Find by Stripe subscription ID
        existing = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_sub_id
        ).first()

        if not existing:
            # Try to find by customer
            customer_id = subscription.get("customer")
            if customer_id:
                existing = db.query(Subscription).filter(
                    Subscription.stripe_customer_id == customer_id
                ).first()

        if not existing:
            logger.warning(f"No subscription found for Stripe ID {stripe_sub_id}")
            return WebhookResponse(
                success=True,
                message="Subscription update acknowledged (no match)"
            )

        # Update seat count and status
        tenant = db.query(Tenant).filter(Tenant.id == existing.tenant_id).first()
        result = update_subscription_from_stripe(
            db, tenant, subscription, subscription.get("customer")
        )

    return WebhookResponse(
        success=True,
        message=f"Subscription updated: {result.get('new_seat_count')} seats"
    )


async def handle_subscription_deleted(subscription: dict) -> WebhookResponse:
    """
    Handle subscription cancellation.
    """
    stripe_sub_id = subscription.get("id")

    with get_db_session() as db:
        existing = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_sub_id
        ).first()

        if existing:
            existing.status = "cancelled"
            existing.plan_type = "expired"
            db.commit()

            logger.info(f"Subscription {stripe_sub_id} cancelled")
            return WebhookResponse(
                success=True,
                message="Subscription cancelled"
            )

    return WebhookResponse(
        success=True,
        message="Subscription deletion acknowledged"
    )


async def handle_invoice_paid(invoice: dict) -> WebhookResponse:
    """
    Handle successful payment.

    Ensures subscription is active after payment.
    """
    subscription_id = invoice.get("subscription")
    if not subscription_id:
        return WebhookResponse(success=True, message="No subscription on invoice")

    with get_db_session() as db:
        existing = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == subscription_id
        ).first()

        if existing:
            # Ensure subscription is active
            if existing.status != "active":
                existing.status = "active"
                existing.plan_type = "active"
                db.commit()
                logger.info(f"Subscription {subscription_id} reactivated after payment")

    return WebhookResponse(
        success=True,
        message="Invoice payment recorded"
    )


async def handle_payment_failed(invoice: dict) -> WebhookResponse:
    """
    Handle failed payment.

    Logs the failure but doesn't immediately block access.
    Stripe will retry and eventually cancel if payment keeps failing.
    """
    subscription_id = invoice.get("subscription")
    customer_email = invoice.get("customer_email", "unknown")

    logger.warning(
        f"Payment failed for subscription {subscription_id}, "
        f"customer: {customer_email}"
    )

    # Optionally: Mark subscription as at-risk but don't block yet
    # Stripe handles retry logic and eventual cancellation

    return WebhookResponse(
        success=True,
        message="Payment failure recorded"
    )


# =============================================================================
# Extended Event Handlers
# =============================================================================

async def handle_customer_created(customer: dict) -> WebhookResponse:
    """
    Handle customer creation in Stripe.

    Logs when you create a new customer in Stripe Dashboard.
    Can be used to pre-register tenant before subscription.
    """
    customer_id = customer.get("id")
    email = customer.get("email", "unknown")
    name = customer.get("name", "unknown")
    metadata = customer.get("metadata", {})
    tenant_domain = metadata.get("tenant_domain", "not set")

    logger.info(
        f"Stripe customer created: {customer_id}, "
        f"email={email}, name={name}, tenant_domain={tenant_domain}"
    )

    # Optionally: Pre-link to tenant if metadata is set
    domain = get_tenant_domain_from_customer(customer)
    if domain:
        with get_db_session() as db:
            tenant = find_tenant_by_domain(db, domain)
            if tenant:
                # Could pre-link customer_id to tenant here
                logger.info(f"Customer {customer_id} matches tenant for domain {domain}")

    return WebhookResponse(
        success=True,
        message=f"Customer created: {email}"
    )


async def handle_customer_updated(customer: dict) -> WebhookResponse:
    """
    Handle customer updates in Stripe.

    Important for tracking email/metadata changes that affect tenant matching.
    """
    customer_id = customer.get("id")
    email = customer.get("email", "unknown")
    metadata = customer.get("metadata", {})
    tenant_domain = metadata.get("tenant_domain")

    logger.info(
        f"Stripe customer updated: {customer_id}, "
        f"email={email}, tenant_domain={tenant_domain}"
    )

    # Update subscription if customer is linked and domain changed
    with get_db_session() as db:
        existing = db.query(Subscription).filter(
            Subscription.stripe_customer_id == customer_id
        ).first()

        if existing:
            logger.info(f"Customer {customer_id} is linked to subscription {existing.id}")
            # Could update tenant link here if needed

    return WebhookResponse(
        success=True,
        message=f"Customer updated: {email}"
    )


async def handle_invoice_finalized(invoice: dict) -> WebhookResponse:
    """
    Handle invoice finalization.

    Called when invoice is finalized and ready to be sent.
    Useful for logging and tracking billing cycle.
    """
    invoice_id = invoice.get("id")
    subscription_id = invoice.get("subscription")
    customer_email = invoice.get("customer_email", "unknown")
    amount_due = invoice.get("amount_due", 0) / 100  # Convert cents to dollars
    currency = invoice.get("currency", "usd").upper()

    logger.info(
        f"Invoice finalized: {invoice_id}, "
        f"subscription={subscription_id}, "
        f"customer={customer_email}, "
        f"amount={currency} {amount_due:.2f}"
    )

    return WebhookResponse(
        success=True,
        message=f"Invoice finalized: {currency} {amount_due:.2f}"
    )


async def handle_payment_action_required(invoice: dict) -> WebhookResponse:
    """
    Handle payment action required (3D Secure, manual intervention).

    Important for EU customers where 3D Secure is common.
    Logs a warning so you can follow up with the customer if needed.
    """
    invoice_id = invoice.get("id")
    subscription_id = invoice.get("subscription")
    customer_email = invoice.get("customer_email", "unknown")
    hosted_invoice_url = invoice.get("hosted_invoice_url", "")

    logger.warning(
        f"Payment action required for invoice {invoice_id}, "
        f"subscription={subscription_id}, "
        f"customer={customer_email}. "
        f"Invoice URL: {hosted_invoice_url}"
    )

    # This could trigger an alert email to you or the customer
    # For now, just log it prominently

    return WebhookResponse(
        success=True,
        message=f"Payment action required for {customer_email}"
    )


async def handle_payment_intent_succeeded(payment_intent: dict) -> WebhookResponse:
    """
    Handle successful payment intent.

    Useful for one-time payments or manual invoices.
    For subscriptions, invoice.paid is the primary event.
    """
    payment_intent_id = payment_intent.get("id")
    amount = payment_intent.get("amount", 0) / 100  # Convert cents to dollars
    currency = payment_intent.get("currency", "usd").upper()
    customer_id = payment_intent.get("customer")

    logger.info(
        f"Payment intent succeeded: {payment_intent_id}, "
        f"amount={currency} {amount:.2f}, "
        f"customer={customer_id}"
    )

    return WebhookResponse(
        success=True,
        message=f"Payment succeeded: {currency} {amount:.2f}"
    )


async def handle_payment_intent_failed(payment_intent: dict) -> WebhookResponse:
    """
    Handle failed payment intent.

    Logs detailed failure information for debugging payment issues.
    """
    payment_intent_id = payment_intent.get("id")
    amount = payment_intent.get("amount", 0) / 100
    currency = payment_intent.get("currency", "usd").upper()
    customer_id = payment_intent.get("customer")

    # Get failure details
    last_error = payment_intent.get("last_payment_error", {})
    error_code = last_error.get("code", "unknown")
    error_message = last_error.get("message", "Unknown error")

    logger.error(
        f"Payment intent failed: {payment_intent_id}, "
        f"amount={currency} {amount:.2f}, "
        f"customer={customer_id}, "
        f"error={error_code}: {error_message}"
    )

    return WebhookResponse(
        success=True,
        message=f"Payment failed: {error_code}"
    )


# =============================================================================
# Checkout Session Endpoint
# =============================================================================

class CheckoutRequest(BaseModel):
    """Request body for creating checkout session"""
    price_id: str  # Stripe Price ID (e.g., price_individual_monthly)
    quantity: int = 1  # Number of seats
    customer_email: Optional[str] = None  # Pre-fill email if known
    success_url: Optional[str] = None  # Override default success URL
    cancel_url: Optional[str] = None  # Override default cancel URL


class CheckoutResponse(BaseModel):
    """Response with checkout session URL"""
    checkout_url: str
    session_id: str


# Default URLs for checkout redirect
DEFAULT_SUCCESS_URL = "https://ilanaimmersive.com/checkout/success"
DEFAULT_CANCEL_URL = "https://ilanaimmersive.com/pricing"


@router.post("/create-checkout-session", response_model=CheckoutResponse)
async def create_checkout_session(request: CheckoutRequest):
    """
    Create a Stripe Checkout session for subscription purchase.

    Called from ilanaimmersive.com pricing page.

    Request body:
    - price_id: Stripe Price ID (required)
    - quantity: Number of seats (default 1)
    - customer_email: Pre-fill email if known
    - success_url: Redirect after success (default: ilanaimmersive.com/checkout/success)
    - cancel_url: Redirect after cancel (default: ilanaimmersive.com/pricing)

    Returns:
    - checkout_url: Stripe Checkout URL to redirect user to
    - session_id: Session ID for reference
    """
    if not STRIPE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Stripe not configured"
        )

    if not STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Stripe API key not configured"
        )

    # Validate quantity
    if request.quantity < 1 or request.quantity > 15:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be between 1 and 15 seats"
        )

    try:
        # Create checkout session
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{
                "price": request.price_id,
                "quantity": request.quantity,
            }],
            success_url=request.success_url or DEFAULT_SUCCESS_URL,
            cancel_url=request.cancel_url or DEFAULT_CANCEL_URL,
            customer_email=request.customer_email,
            allow_promotion_codes=True,
            metadata={
                "seat_count": str(request.quantity),
            },
            subscription_data={
                "metadata": {
                    "seat_count": str(request.quantity),
                }
            },
        )

        logger.info(
            f"Checkout session created: {session.id}, "
            f"price={request.price_id}, quantity={request.quantity}"
        )

        return CheckoutResponse(
            checkout_url=session.url,
            session_id=session.id,
        )

    except stripe.error.InvalidRequestError as e:
        logger.error(f"Invalid Stripe request: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid request: {str(e)}"
        )
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Payment service error"
        )


# =============================================================================
# Health Check
# =============================================================================

@router.get("/health")
async def stripe_health():
    """Health check for Stripe webhook endpoint"""
    return {
        "status": "ok",
        "webhook_secret_configured": bool(STRIPE_WEBHOOK_SECRET),
        "api_key_configured": bool(STRIPE_SECRET_KEY),
        "stripe_available": STRIPE_AVAILABLE,
    }


# Export
__all__ = ["router"]
