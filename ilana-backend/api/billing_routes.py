"""
Billing Status API

Read-only endpoints for Admin Portal to display billing status.
No self-serve modifications - all changes happen in Stripe Dashboard.
"""

import os
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
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
    InvoiceRequest as InvoiceRequestModel,
    Subscription,
)
from auth import TokenClaims, get_current_user
from trial_manager import get_trial_status
from email_service import send_email

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
    status: str  # "trial", "active", "past_due", "cancelled", "expired", "pending_payment"
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

    # Enterprise billing info
    collection_method: Optional[str] = None  # "charge_automatically" or "send_invoice"
    is_invoice_customer: bool = False
    payment_status: Optional[str] = None  # "paid", "pending_payment", "overdue"
    tenant_name: Optional[str] = None  # For mailto subject lines

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

    # Check for pending payment (invoice customers)
    is_invoice_customer = subscription.collection_method == "send_invoice"
    if is_invoice_customer and subscription.payment_status == "pending_payment":
        status = "pending_payment"

    # Build message
    if status == "trial":
        message = f"Trial: {trial_info['days_remaining']} days remaining"
    elif status == "pending_payment":
        message = "Waiting for invoice payment. Seats activate after payment."
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
        billing_interval=billing_interval or subscription.billing_interval,
        collection_method=subscription.collection_method,
        is_invoice_customer=is_invoice_customer,
        payment_status=subscription.payment_status,
        tenant_name=tenant.name,
        message=message,
    )


# =============================================================================
# Customer Portal (for Individual plan users)
# =============================================================================

class PortalResponse(BaseModel):
    """Response with Stripe Customer Portal URL"""
    url: str


class Invoice(BaseModel):
    """Invoice record from Stripe"""
    id: str
    invoice_number: Optional[str] = None
    created_at: str
    amount_due: int  # in cents
    amount_paid: int  # in cents
    currency: str
    status: str  # draft, open, paid, void, uncollectible
    invoice_pdf: Optional[str] = None
    hosted_invoice_url: Optional[str] = None
    due_date: Optional[str] = None


class InvoiceListResponse(BaseModel):
    """Response for invoice list endpoint"""
    invoices: List[Invoice]
    has_more: bool


def get_plan_tier(seat_count: int) -> str:
    """Derive plan tier from seat count"""
    if seat_count == 1:
        return "individual"
    elif seat_count <= 5:
        return "team"
    else:
        return "team_plus"


@router.post("/portal", response_model=PortalResponse)
async def create_portal_session(
    claims: TokenClaims = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a Stripe Customer Portal session for the current user.

    Only available for Individual plan users (1 seat).
    Team and Team+ users should manage billing through their org admin.
    """
    if not STRIPE_AVAILABLE or not STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Billing portal not available"
        )

    # Get tenant and subscription
    tenant = get_tenant_by_azure_id(db, claims.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    subscription = get_active_subscription(db, tenant.id)
    if not subscription:
        raise HTTPException(status_code=404, detail="No subscription found")

    # Only allow Individual plan users (1 seat) to access portal
    plan_tier = get_plan_tier(subscription.seat_count)
    if plan_tier != "individual":
        raise HTTPException(
            status_code=403,
            detail="Billing portal only available for Individual plan users. Contact your organization admin for billing changes."
        )

    # Need Stripe customer ID
    if not subscription.stripe_customer_id:
        raise HTTPException(
            status_code=404,
            detail="No billing account found. Please contact support."
        )

    try:
        # Create portal session
        session = stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url="https://ilanaimmersive.com/billing-updated"
        )

        logger.info(f"Created portal session for customer {subscription.stripe_customer_id}")
        return PortalResponse(url=session.url)

    except stripe.error.InvalidRequestError as e:
        logger.error(f"Stripe error creating portal session: {e}")
        raise HTTPException(
            status_code=400,
            detail="Unable to create billing portal session"
        )
    except Exception as e:
        logger.error(f"Error creating portal session: {e}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while creating the billing portal"
        )


# =============================================================================
# Invoice History (for Admin Portal)
# =============================================================================

@router.get("/invoices", response_model=InvoiceListResponse)
async def get_invoices(
    claims: TokenClaims = Depends(verify_admin),
    db: Session = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=100),
    starting_after: Optional[str] = Query(default=None),
):
    """
    Get invoice history from Stripe for the current tenant.

    Returns list of invoices with status, amounts, and download links.
    Admin access required.
    """
    if not STRIPE_AVAILABLE or not STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Billing service not available"
        )

    tenant = get_tenant_by_azure_id(db, claims.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    subscription = get_active_subscription(db, tenant.id)
    if not subscription:
        raise HTTPException(status_code=404, detail="No subscription found")

    if not subscription.stripe_customer_id:
        # No Stripe customer yet - return empty list
        return InvoiceListResponse(invoices=[], has_more=False)

    try:
        # Fetch invoices from Stripe
        list_params = {
            "customer": subscription.stripe_customer_id,
            "limit": limit,
        }
        if starting_after:
            list_params["starting_after"] = starting_after

        stripe_invoices = stripe.Invoice.list(**list_params)

        invoices = []
        for inv in stripe_invoices.data:
            invoices.append(Invoice(
                id=inv.id,
                invoice_number=inv.number,
                created_at=datetime.fromtimestamp(inv.created).isoformat(),
                amount_due=inv.amount_due,
                amount_paid=inv.amount_paid,
                currency=inv.currency,
                status=inv.status or "draft",
                invoice_pdf=inv.invoice_pdf,
                hosted_invoice_url=inv.hosted_invoice_url,
                due_date=datetime.fromtimestamp(inv.due_date).isoformat() if inv.due_date else None,
            ))

        return InvoiceListResponse(
            invoices=invoices,
            has_more=stripe_invoices.has_more,
        )

    except stripe.error.InvalidRequestError as e:
        logger.error(f"Stripe error fetching invoices: {e}")
        raise HTTPException(
            status_code=400,
            detail="Unable to fetch invoices"
        )
    except Exception as e:
        logger.error(f"Error fetching invoices: {e}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while fetching invoices"
        )


# =============================================================================
# Trial Conversion Endpoints (B2B)
# =============================================================================

# Stripe Price IDs - set in environment or Stripe Dashboard
# TODO: Replace these with actual Stripe price IDs from Dashboard
STRIPE_PRICES = {
    "corporate": {
        "month": os.getenv("STRIPE_PRICE_CORPORATE_MONTHLY", "price_corporate_monthly"),
        "year": os.getenv("STRIPE_PRICE_CORPORATE_ANNUAL", "price_corporate_annual"),
    },
    "enterprise": {
        "month": os.getenv("STRIPE_PRICE_ENTERPRISE_MONTHLY", "price_enterprise_monthly"),
        "year": os.getenv("STRIPE_PRICE_ENTERPRISE_ANNUAL", "price_enterprise_annual"),
    },
}

# Pricing amounts for display
PRICING = {
    "corporate": {
        "month": 75,   # $75/user/mo
        "year": 750,   # $750/user/yr (save $150/user)
    },
    "enterprise": {
        "month": 149,  # $149/user/mo
        "year": 1490,  # $1,490/user/yr (save $298/user)
    },
}

# Common commercial email domains (should NOT qualify for corporate pricing)
COMMERCIAL_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "icloud.com", "protonmail.com", "mail.com", "live.com", "msn.com",
    "ymail.com", "zoho.com", "me.com", "mac.com", "comcast.net",
}


def detect_plan_from_email(email: str) -> tuple[str, str]:
    """
    Detect plan type based on email domain.

    Returns:
        tuple: (detected_plan, email_domain)
        - detected_plan: "corporate" or "enterprise"
        - email_domain: the domain part of the email

    Rules:
        - .edu domain → Corporate ($75/user)
        - .org domain → Corporate ($75/user)
        - Commercial emails (@gmail, @yahoo, etc.) → Enterprise
        - Everything else → Enterprise ($149/user)
    """
    if not email or "@" not in email:
        return ("enterprise", "")

    domain = email.split("@")[1].lower()

    # Check for .edu or .org TLDs
    if domain.endswith(".edu"):
        return ("corporate", domain)
    if domain.endswith(".org"):
        return ("corporate", domain)

    # Everything else is enterprise
    return ("enterprise", domain)


def check_org_type_mismatch(org_type: str, email_domain: str) -> bool:
    """
    Check if organization type claims don't match the email domain.

    Flags for manual review when:
    - User claims university/nonprofit but has commercial email
    - User claims university but doesn't have .edu domain
    - User claims nonprofit but doesn't have .org domain

    Returns:
        bool: True if there's a mismatch that needs review
    """
    if not org_type or not email_domain:
        return False

    org_type = org_type.lower()
    email_domain = email_domain.lower()

    # Commercial email claiming academic/nonprofit status
    if email_domain in COMMERCIAL_EMAIL_DOMAINS:
        if org_type in ["university", "nonprofit"]:
            return True  # Flag: commercial email claiming discount eligibility

    # University claim without .edu domain
    if org_type == "university" and not email_domain.endswith(".edu"):
        return True  # Flag: claiming university without .edu email

    # Nonprofit claim without .org domain (but allow - some nonprofits use other domains)
    # This is a softer check - just flag for review, don't block

    return False


def get_effective_plan(subscription) -> tuple[str, bool]:
    """
    Get the effective plan for pricing, considering verified status.

    Returns:
        tuple: (effective_plan, is_discount_applied)
        - effective_plan: "corporate" or "enterprise"
        - is_discount_applied: True if .edu/.org discount is applied
    """
    # If verified, use the admin-verified plan
    if subscription.is_verified and subscription.detected_plan:
        return (subscription.detected_plan, subscription.detected_plan == "corporate")

    # If not verified but detected plan exists, use it
    if subscription.detected_plan:
        is_discount = subscription.detected_plan == "corporate"
        return (subscription.detected_plan, is_discount)

    # Fall back to org_type-based detection
    org_type = subscription.org_type or "enterprise"
    if org_type in ["university", "nonprofit"]:
        return ("corporate", True)

    return ("enterprise", False)


class CheckoutRequest(BaseModel):
    """Request body for creating a Stripe Checkout session"""
    billing_interval: str  # "month" or "year"


class CheckoutResponse(BaseModel):
    """Response with Stripe Checkout URL"""
    checkout_url: str
    session_id: str


class InvoiceRequestInput(BaseModel):
    """Request body for invoice billing - full form"""
    billing_interval: str  # "month" or "year"

    # Billing contact (required)
    billing_contact_name: str
    billing_contact_email: str

    # Billing address (required)
    billing_address: str  # Street address (can be multi-line)
    billing_city: str
    billing_state: str
    billing_zip: str
    billing_country: str = "United States"

    # Optional fields
    po_number: Optional[str] = None
    payment_terms: str = "net_30"  # net_30 or net_60
    notes: Optional[str] = None


class InvoiceRequestResponse(BaseModel):
    """Response for invoice request"""
    success: bool
    message: str
    request_id: str
    invoice_amount: int  # Total in cents
    seats: int
    billing_interval: str


class ConversionInfo(BaseModel):
    """Pricing info for conversion page"""
    detected_plan: str  # "corporate" or "enterprise"
    seats: int
    monthly_per_user: int
    annual_per_user: int
    monthly_total: int
    annual_total: int
    annual_savings: int  # Savings vs monthly

    # Verification info
    email_domain: Optional[str] = None  # e.g., "harvard.edu"
    org_type: Optional[str] = None  # e.g., "university"
    is_discount_applied: bool = False  # True if .edu/.org discount
    is_verified: bool = False  # True if admin verified
    needs_review: bool = False  # True if mismatch detected
    discount_reason: Optional[str] = None  # e.g., "Education/Non-Profit (.edu domain)"


@router.get("/conversion-info", response_model=ConversionInfo)
async def get_conversion_info(
    claims: TokenClaims = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    Get pricing info for the conversion page.

    Returns plan type, seat count, pricing options, and verification status.
    Admin access required.

    Plan detection:
    - .edu domain → Corporate ($75/user) with education discount
    - .org domain → Corporate ($75/user) with non-profit discount
    - All other domains → Enterprise ($149/user)
    """
    tenant = get_tenant_by_azure_id(db, claims.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    subscription = get_active_subscription(db, tenant.id)
    if not subscription:
        raise HTTPException(status_code=404, detail="No subscription found")

    # Get admin user's email for plan detection
    user = get_user_by_azure_id(db, tenant.id, claims.user_id)
    admin_email = user.email if user else None

    # Detect plan from email if not already set
    email_domain = subscription.email_domain
    stored_detected_plan = subscription.detected_plan

    if not email_domain and admin_email:
        # First time - detect from admin's email
        stored_detected_plan, email_domain = detect_plan_from_email(admin_email)
        subscription.email_domain = email_domain
        subscription.detected_plan = stored_detected_plan

        # Check for mismatch
        if subscription.org_type:
            subscription.needs_review = check_org_type_mismatch(
                subscription.org_type, email_domain
            )

        db.commit()

    # Get effective plan (considering verification)
    effective_plan, is_discount_applied = get_effective_plan(subscription)

    # Build discount reason
    discount_reason = None
    if is_discount_applied:
        if email_domain and email_domain.endswith(".edu"):
            discount_reason = f"Education discount (.edu domain: {email_domain})"
        elif email_domain and email_domain.endswith(".org"):
            discount_reason = f"Non-profit discount (.org domain: {email_domain})"
        elif subscription.org_type in ["university", "nonprofit"]:
            discount_reason = f"Verified {subscription.org_type.replace('_', ' ').title()}"

    seats = subscription.seat_count
    pricing = PRICING[effective_plan]

    monthly_per_user = pricing["month"]
    annual_per_user = pricing["year"]
    monthly_total = monthly_per_user * seats
    annual_total = annual_per_user * seats
    # Annual savings = (monthly * 12) - annual
    annual_savings = (monthly_per_user * 12 * seats) - annual_total

    return ConversionInfo(
        detected_plan=effective_plan,
        seats=seats,
        monthly_per_user=monthly_per_user,
        annual_per_user=annual_per_user,
        monthly_total=monthly_total,
        annual_total=annual_total,
        annual_savings=annual_savings,
        email_domain=email_domain,
        org_type=subscription.org_type,
        is_discount_applied=is_discount_applied,
        is_verified=subscription.is_verified or False,
        needs_review=subscription.needs_review or False,
        discount_reason=discount_reason,
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    request: CheckoutRequest,
    claims: TokenClaims = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    Create a Stripe Checkout session for subscription payment.

    Used by admins to convert from trial to paid subscription.
    Price based on detected plan and billing interval.
    """
    if not STRIPE_AVAILABLE or not STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Payment processing not available"
        )

    if request.billing_interval not in ["month", "year"]:
        raise HTTPException(
            status_code=400,
            detail="billing_interval must be 'month' or 'year'"
        )

    tenant = get_tenant_by_azure_id(db, claims.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    subscription = get_active_subscription(db, tenant.id)
    if not subscription:
        raise HTTPException(status_code=404, detail="No subscription found")

    # Determine plan type
    detected_plan = subscription.org_type or "enterprise"
    if detected_plan not in ["corporate", "enterprise"]:
        if detected_plan in ["university", "nonprofit"]:
            detected_plan = "corporate"
        else:
            detected_plan = "enterprise"

    price_id = STRIPE_PRICES[detected_plan][request.billing_interval]

    try:
        # Create or get Stripe customer
        if subscription.stripe_customer_id:
            customer_id = subscription.stripe_customer_id
        else:
            customer = stripe.Customer.create(
                email=claims.email if hasattr(claims, 'email') else None,
                name=tenant.name,
                metadata={
                    "tenant_id": str(tenant.id),
                    "subscription_id": str(subscription.id),
                },
            )
            customer_id = customer.id
            subscription.stripe_customer_id = customer_id
            db.commit()

        # Create Checkout session
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{
                "price": price_id,
                "quantity": subscription.seat_count,
            }],
            success_url="https://ilanaimmersive.com/billing-success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://ilanaimmersive.com/billing?cancelled=true",
            metadata={
                "tenant_id": str(tenant.id),
                "subscription_id": str(subscription.id),
                "plan": detected_plan,
                "billing_interval": request.billing_interval,
            },
            subscription_data={
                "metadata": {
                    "tenant_id": str(tenant.id),
                    "subscription_id": str(subscription.id),
                },
            },
        )

        logger.info(
            f"Created checkout session for tenant {tenant.id}: "
            f"plan={detected_plan}, interval={request.billing_interval}, "
            f"seats={subscription.seat_count}"
        )

        return CheckoutResponse(
            checkout_url=session.url,
            session_id=session.id,
        )

    except stripe.error.InvalidRequestError as e:
        logger.error(f"Stripe error creating checkout: {e}")
        raise HTTPException(
            status_code=400,
            detail="Unable to create checkout session"
        )
    except Exception as e:
        logger.error(f"Error creating checkout: {e}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while creating checkout"
        )


@router.post("/request-invoice", response_model=InvoiceRequestResponse)
async def request_invoice_billing(
    request: InvoiceRequestInput,
    claims: TokenClaims = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    Request invoice billing instead of credit card.

    Creates an InvoiceRequest record and notifies the ops team.
    Trial is extended by 7 days while invoice is being processed.

    Typically used by larger enterprises with NET 30 terms.
    """
    if request.billing_interval not in ["month", "year"]:
        raise HTTPException(
            status_code=400,
            detail="billing_interval must be 'month' or 'year'"
        )

    if request.payment_terms not in ["net_30", "net_60"]:
        raise HTTPException(
            status_code=400,
            detail="payment_terms must be 'net_30' or 'net_60'"
        )

    tenant = get_tenant_by_azure_id(db, claims.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    subscription = get_active_subscription(db, tenant.id)
    if not subscription:
        raise HTTPException(status_code=404, detail="No subscription found")

    user = get_user_by_azure_id(db, tenant.id, claims.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check for existing pending invoice request
    existing_request = db.query(InvoiceRequestModel).filter(
        InvoiceRequestModel.tenant_id == tenant.id,
        InvoiceRequestModel.status == "pending",
    ).first()
    if existing_request:
        raise HTTPException(
            status_code=400,
            detail="An invoice request is already pending. Please wait for it to be processed."
        )

    # Determine plan type and pricing
    detected_plan = subscription.org_type or "enterprise"
    if detected_plan not in ["corporate", "enterprise"]:
        if detected_plan in ["university", "nonprofit"]:
            detected_plan = "corporate"
        else:
            detected_plan = "enterprise"

    pricing = PRICING[detected_plan]
    unit_price = pricing[request.billing_interval]
    total_amount = unit_price * subscription.seat_count * 100  # cents

    # Create InvoiceRequest record
    invoice_request = InvoiceRequestModel(
        tenant_id=tenant.id,
        subscription_id=subscription.id,
        requested_by_user_id=user.id,
        plan_type=detected_plan,
        billing_interval=request.billing_interval,
        seat_count=subscription.seat_count,
        amount_cents=total_amount,
        billing_contact_name=request.billing_contact_name,
        billing_contact_email=request.billing_contact_email,
        po_number=request.po_number,
        billing_address=request.billing_address,
        billing_city=request.billing_city,
        billing_state=request.billing_state,
        billing_zip=request.billing_zip,
        billing_country=request.billing_country,
        payment_terms=request.payment_terms,
        notes=request.notes,
        status="pending",
    )
    db.add(invoice_request)

    # Extend trial by 7 days while invoice is being processed
    # This gives time for invoice to be sent and paid
    if subscription.trial_ends_at:
        from datetime import timedelta
        new_trial_end = max(
            subscription.trial_ends_at,
            datetime.utcnow() + timedelta(days=7)
        )
        subscription.trial_ends_at = new_trial_end
        logger.info(f"Extended trial to {new_trial_end} for invoice processing")

    db.commit()
    db.refresh(invoice_request)

    # Send notification email to ops team
    try:
        await send_invoice_request_notification(
            tenant_name=tenant.name or "Unknown",
            invoice_request=invoice_request,
            subscription=subscription,
        )
    except Exception as e:
        logger.error(f"Failed to send invoice notification email: {e}")
        # Don't fail the request if email fails

    interval_label = "monthly" if request.billing_interval == "month" else "annual"

    return InvoiceRequestResponse(
        success=True,
        message=f"Invoice request submitted. We'll send your invoice within 1 business day. You'll continue to have access during processing.",
        request_id=str(invoice_request.id),
        invoice_amount=total_amount,
        seats=subscription.seat_count,
        billing_interval=request.billing_interval,
    )


async def send_invoice_request_notification(
    tenant_name: str,
    invoice_request: InvoiceRequestModel,
    subscription: Subscription,
):
    """Send notification email to ops team about new invoice request."""

    # Format amount
    amount_dollars = invoice_request.amount_cents / 100
    interval_label = "monthly" if invoice_request.billing_interval == "month" else "annual"
    payment_terms_label = "NET 30" if invoice_request.payment_terms == "net_30" else "NET 60"

    subject = f"New Invoice Request from {tenant_name}"

    html_body = f"""
    <h2>New Invoice Request</h2>

    <h3>Organization</h3>
    <ul>
        <li><strong>Company:</strong> {tenant_name}</li>
        <li><strong>Plan:</strong> {invoice_request.plan_type.title()} ({invoice_request.seat_count} seats)</li>
        <li><strong>Billing:</strong> {interval_label.title()}</li>
        <li><strong>Amount:</strong> ${amount_dollars:,.2f}</li>
        <li><strong>Payment Terms:</strong> {payment_terms_label}</li>
    </ul>

    <h3>Billing Contact</h3>
    <ul>
        <li><strong>Name:</strong> {invoice_request.billing_contact_name}</li>
        <li><strong>Email:</strong> {invoice_request.billing_contact_email}</li>
        {f'<li><strong>PO Number:</strong> {invoice_request.po_number}</li>' if invoice_request.po_number else ''}
    </ul>

    <h3>Billing Address</h3>
    <p>
        {invoice_request.billing_address}<br>
        {invoice_request.billing_city}, {invoice_request.billing_state} {invoice_request.billing_zip}<br>
        {invoice_request.billing_country}
    </p>

    {f'<h3>Additional Notes</h3><p>{invoice_request.notes}</p>' if invoice_request.notes else ''}

    <hr>
    <p>
        <a href="https://ops.ilanaimmersive.com/invoices/{invoice_request.id}">
            View in Ops Portal →
        </a>
    </p>
    """

    text_body = f"""
New Invoice Request from {tenant_name}

Organization:
- Company: {tenant_name}
- Plan: {invoice_request.plan_type.title()} ({invoice_request.seat_count} seats)
- Billing: {interval_label.title()}
- Amount: ${amount_dollars:,.2f}
- Payment Terms: {payment_terms_label}

Billing Contact:
- Name: {invoice_request.billing_contact_name}
- Email: {invoice_request.billing_contact_email}
{f'- PO Number: {invoice_request.po_number}' if invoice_request.po_number else ''}

Billing Address:
{invoice_request.billing_address}
{invoice_request.billing_city}, {invoice_request.billing_state} {invoice_request.billing_zip}
{invoice_request.billing_country}

{f'Additional Notes: {invoice_request.notes}' if invoice_request.notes else ''}

View in Ops Portal: https://ops.ilanaimmersive.com/invoices/{invoice_request.id}
    """

    await send_email(
        to="ops@ilanaimmersive.com",
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )


# Export
__all__ = ["router"]
