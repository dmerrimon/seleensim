"""
Super Admin API Routes for Ilana

Handles cross-tenant administration:
- View all tenants and their status
- Global user search
- Trial extensions
- Platform-wide statistics
- Super admin management

Only accessible by users with is_super_admin=True in the database.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

# Stripe is optional - will be None if not installed
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    stripe = None
    STRIPE_AVAILABLE = False

from database import (
    get_db,
    User,
    Tenant,
    Subscription,
    SeatAssignment,
    AuditEvent,
)
from auth import TokenClaims, get_current_user

# Initialize Stripe
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
if STRIPE_AVAILABLE and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/super-admin", tags=["super-admin"])


# =============================================================================
# Response Models
# =============================================================================

class TenantSummary(BaseModel):
    """Summary of a tenant for the super admin dashboard"""
    id: str
    name: Optional[str]
    azure_tenant_id: str
    created_at: str
    user_count: int
    seats_used: int
    seats_total: int
    subscription_status: str  # trial, active, expired, cancelled
    trial_days_remaining: Optional[int]
    has_stripe_subscription: bool


class TenantDetailUser(BaseModel):
    """User info for tenant detail view"""
    id: str
    email: Optional[str]
    display_name: Optional[str]
    is_admin: bool
    has_seat: bool
    last_active_at: Optional[str]
    created_at: str


class TenantDetail(BaseModel):
    """Full tenant detail"""
    id: str
    name: Optional[str]
    azure_tenant_id: str
    created_at: str
    subscription: dict
    users: List[TenantDetailUser]
    audit_summary: dict


class UserSearchResult(BaseModel):
    """Result from global user search"""
    id: str
    email: Optional[str]
    display_name: Optional[str]
    tenant_id: str
    tenant_name: Optional[str]
    is_admin: bool
    is_super_admin: bool
    has_seat: bool
    last_active_at: Optional[str]


class SuperAdminStats(BaseModel):
    """Platform-wide statistics"""
    total_tenants: int
    total_users: int
    active_subscriptions: int
    trials_active: int
    mrr: float  # Monthly recurring revenue estimate


class SuperAdminInfo(BaseModel):
    """Info about a super admin user"""
    id: str
    email: Optional[str]
    display_name: Optional[str]
    tenant_id: str
    tenant_name: Optional[str]


class ExtendTrialRequest(BaseModel):
    """Request to extend a tenant's trial"""
    days: int = 14


class ExtendTrialResponse(BaseModel):
    """Response from trial extension"""
    success: bool
    new_trial_ends_at: Optional[str]
    days_remaining: Optional[int]
    error: Optional[str]


class GrantSuperAdminRequest(BaseModel):
    """Request to grant super admin by email"""
    email: str


class SuperAdminActionResponse(BaseModel):
    """Response from super admin grant/revoke actions"""
    success: bool
    user_email: Optional[str]
    error: Optional[str]


class UpdateTenantRequest(BaseModel):
    """Request to update tenant info"""
    name: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None


class UpdateSeatsRequest(BaseModel):
    """Request to update seat count"""
    seat_count: int


class SubscriptionActionRequest(BaseModel):
    """Request to change subscription status"""
    action: str  # "cancel", "activate", "convert_to_paid"
    plan_type: Optional[str] = None  # For convert_to_paid


class UserSeatActionRequest(BaseModel):
    """Request to manage a user's seat"""
    action: str  # "revoke", "restore"


class ActivityLogEntry(BaseModel):
    """Single activity log entry"""
    id: str
    tenant_id: str
    tenant_name: Optional[str]
    user_id: Optional[str]
    user_email: Optional[str]
    action: str
    details: Optional[str]
    created_at: str


class AnalyticsData(BaseModel):
    """Analytics data for charts"""
    signups_by_day: List[dict]  # [{date, count}]
    active_users_by_day: List[dict]  # [{date, count}]
    trials_converted: int
    trials_expired: int
    avg_trial_duration_days: float
    top_tenants_by_users: List[dict]  # [{tenant_name, user_count}]


class TenantNote(BaseModel):
    """Internal note on a tenant"""
    id: str
    tenant_id: str
    content: str
    created_by: str
    created_at: str


# =============================================================================
# Super Admin Verification
# =============================================================================

async def verify_super_admin(
    claims: TokenClaims = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> tuple[TokenClaims, User]:
    """
    Verify the current user is a super admin.

    Checks the is_super_admin flag in the database.
    Returns both claims and the user object for convenience.
    """
    # Super admin can be in any tenant, so we search across all users
    user = db.query(User).filter(
        User.azure_user_id == claims.user_id
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_super_admin:
        logger.warning(f"Non-super-admin user {claims.email} attempted super admin access")
        raise HTTPException(status_code=403, detail="Super admin access required")

    logger.info(f"Super admin access granted to {claims.email}")
    return claims, user


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/tenants", response_model=List[TenantSummary])
async def list_all_tenants(
    auth: tuple = Depends(verify_super_admin),
    db: Session = Depends(get_db),
):
    """
    List all tenants with summary statistics.

    Returns tenant name, user count, seat usage, and subscription status.
    """
    claims, admin_user = auth

    tenants = db.query(Tenant).order_by(Tenant.created_at.desc()).all()

    results = []
    for tenant in tenants:
        # Get subscription
        subscription = db.query(Subscription).filter(
            Subscription.tenant_id == tenant.id,
            Subscription.status == "active"
        ).first()

        # Count users and seats
        user_count = db.query(User).filter(User.tenant_id == tenant.id).count()

        seats_used = 0
        seats_total = 0
        subscription_status = "none"
        trial_days_remaining = None
        has_stripe = False

        if subscription:
            seats_total = subscription.seat_count or 0
            seats_used = db.query(SeatAssignment).filter(
                SeatAssignment.subscription_id == subscription.id,
                SeatAssignment.status == "active"
            ).count()

            subscription_status = subscription.plan_type or "unknown"
            has_stripe = bool(subscription.stripe_subscription_id)

            # Calculate trial days remaining
            if subscription.plan_type == "trial" and subscription.trial_ends_at:
                delta = subscription.trial_ends_at - datetime.utcnow()
                trial_days_remaining = max(0, delta.days)

        results.append(TenantSummary(
            id=str(tenant.id),
            name=tenant.name,
            azure_tenant_id=tenant.azure_tenant_id,
            created_at=tenant.created_at.isoformat() if tenant.created_at else "",
            user_count=user_count,
            seats_used=seats_used,
            seats_total=seats_total,
            subscription_status=subscription_status,
            trial_days_remaining=trial_days_remaining,
            has_stripe_subscription=has_stripe,
        ))

    return results


@router.get("/tenants/{tenant_id}", response_model=TenantDetail)
async def get_tenant_detail(
    tenant_id: str,
    auth: tuple = Depends(verify_super_admin),
    db: Session = Depends(get_db),
):
    """
    Get full details for a specific tenant.

    Includes all users, subscription info, and audit summary.
    """
    claims, admin_user = auth

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Get subscription
    subscription = db.query(Subscription).filter(
        Subscription.tenant_id == tenant.id,
        Subscription.status == "active"
    ).first()

    subscription_data = {}
    if subscription:
        seats_used = db.query(SeatAssignment).filter(
            SeatAssignment.subscription_id == subscription.id,
            SeatAssignment.status == "active"
        ).count()

        trial_days_remaining = None
        if subscription.plan_type == "trial" and subscription.trial_ends_at:
            delta = subscription.trial_ends_at - datetime.utcnow()
            trial_days_remaining = max(0, delta.days)

        subscription_data = {
            "id": str(subscription.id),
            "plan_type": subscription.plan_type,
            "status": subscription.status,
            "seats_total": subscription.seat_count,
            "seats_used": seats_used,
            "trial_started_at": subscription.trial_started_at.isoformat() if subscription.trial_started_at else None,
            "trial_ends_at": subscription.trial_ends_at.isoformat() if subscription.trial_ends_at else None,
            "trial_days_remaining": trial_days_remaining,
            "converted_at": subscription.converted_at.isoformat() if subscription.converted_at else None,
            "stripe_customer_id": subscription.stripe_customer_id,
            "stripe_subscription_id": subscription.stripe_subscription_id,
            "has_stripe": bool(subscription.stripe_subscription_id),
        }

    # Get users
    users = db.query(User).filter(User.tenant_id == tenant.id).all()
    user_list = []
    for user in users:
        has_seat = False
        if subscription:
            seat = db.query(SeatAssignment).filter(
                SeatAssignment.user_id == user.id,
                SeatAssignment.subscription_id == subscription.id,
                SeatAssignment.status == "active"
            ).first()
            has_seat = seat is not None

        user_list.append(TenantDetailUser(
            id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            is_admin=user.is_admin,
            has_seat=has_seat,
            last_active_at=user.last_active_at.isoformat() if user.last_active_at else None,
            created_at=user.created_at.isoformat() if user.created_at else "",
        ))

    # Audit summary
    total_events = db.query(AuditEvent).filter(
        AuditEvent.tenant_id == tenant.id
    ).count()

    recent_events = db.query(AuditEvent).filter(
        AuditEvent.tenant_id == tenant.id,
        AuditEvent.created_at >= datetime.utcnow() - timedelta(days=7)
    ).count()

    audit_summary = {
        "total_events": total_events,
        "events_last_7_days": recent_events,
    }

    return TenantDetail(
        id=str(tenant.id),
        name=tenant.name,
        azure_tenant_id=tenant.azure_tenant_id,
        created_at=tenant.created_at.isoformat() if tenant.created_at else "",
        subscription=subscription_data,
        users=user_list,
        audit_summary=audit_summary,
    )


@router.get("/users/search", response_model=List[UserSearchResult])
async def search_users(
    email: str = Query(..., min_length=3, description="Email to search for"),
    auth: tuple = Depends(verify_super_admin),
    db: Session = Depends(get_db),
):
    """
    Search for users across all tenants by email.

    Partial matching is supported.
    """
    claims, admin_user = auth

    users = db.query(User).filter(
        User.email.ilike(f"%{email}%")
    ).limit(50).all()

    results = []
    for user in users:
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()

        # Check if user has a seat
        has_seat = False
        subscription = db.query(Subscription).filter(
            Subscription.tenant_id == user.tenant_id,
            Subscription.status == "active"
        ).first()
        if subscription:
            seat = db.query(SeatAssignment).filter(
                SeatAssignment.user_id == user.id,
                SeatAssignment.subscription_id == subscription.id,
                SeatAssignment.status == "active"
            ).first()
            has_seat = seat is not None

        results.append(UserSearchResult(
            id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            tenant_id=str(user.tenant_id),
            tenant_name=tenant.name if tenant else None,
            is_admin=user.is_admin,
            is_super_admin=user.is_super_admin,
            has_seat=has_seat,
            last_active_at=user.last_active_at.isoformat() if user.last_active_at else None,
        ))

    return results


@router.post("/tenants/{tenant_id}/extend-trial", response_model=ExtendTrialResponse)
async def extend_trial(
    tenant_id: str,
    request: ExtendTrialRequest,
    auth: tuple = Depends(verify_super_admin),
    db: Session = Depends(get_db),
):
    """
    Extend a tenant's trial period.

    Can be used for expired trials or to add time to active trials.
    """
    claims, admin_user = auth

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    subscription = db.query(Subscription).filter(
        Subscription.tenant_id == tenant.id
    ).first()

    if not subscription:
        return ExtendTrialResponse(
            success=False,
            error="No subscription found for this tenant"
        )

    # Extend the trial
    if subscription.trial_ends_at:
        # If trial already ended, start from now
        if subscription.trial_ends_at < datetime.utcnow():
            new_end = datetime.utcnow() + timedelta(days=request.days)
        else:
            new_end = subscription.trial_ends_at + timedelta(days=request.days)
    else:
        new_end = datetime.utcnow() + timedelta(days=request.days)

    subscription.trial_ends_at = new_end
    subscription.plan_type = "trial"  # Revert to trial if was expired
    subscription.status = "active"

    db.commit()

    delta = new_end - datetime.utcnow()
    days_remaining = max(0, delta.days)

    logger.info(f"Super admin {claims.email} extended trial for tenant {tenant.name} by {request.days} days")

    return ExtendTrialResponse(
        success=True,
        new_trial_ends_at=new_end.isoformat(),
        days_remaining=days_remaining,
    )


@router.get("/stats", response_model=SuperAdminStats)
async def get_platform_stats(
    auth: tuple = Depends(verify_super_admin),
    db: Session = Depends(get_db),
):
    """
    Get platform-wide statistics.

    Includes total tenants, users, subscriptions, and estimated MRR.
    """
    claims, admin_user = auth

    total_tenants = db.query(Tenant).count()
    total_users = db.query(User).count()

    # Active paid subscriptions
    active_subscriptions = db.query(Subscription).filter(
        Subscription.status == "active",
        Subscription.plan_type == "active",
        Subscription.stripe_subscription_id.isnot(None)
    ).count()

    # Active trials
    trials_active = db.query(Subscription).filter(
        Subscription.status == "active",
        Subscription.plan_type == "trial",
        Subscription.trial_ends_at > datetime.utcnow()
    ).count()

    # Estimate MRR (assuming $50/seat/month as placeholder)
    # In production, you'd fetch actual prices from Stripe
    total_paid_seats = db.query(func.sum(Subscription.seat_count)).filter(
        Subscription.status == "active",
        Subscription.plan_type == "active",
        Subscription.stripe_subscription_id.isnot(None)
    ).scalar() or 0

    estimated_mrr = float(total_paid_seats) * 50.0  # $50/seat placeholder

    return SuperAdminStats(
        total_tenants=total_tenants,
        total_users=total_users,
        active_subscriptions=active_subscriptions,
        trials_active=trials_active,
        mrr=estimated_mrr,
    )


# =============================================================================
# Super Admin Management
# =============================================================================

@router.get("/super-admins", response_model=List[SuperAdminInfo])
async def list_super_admins(
    auth: tuple = Depends(verify_super_admin),
    db: Session = Depends(get_db),
):
    """
    List all current super admins.
    """
    claims, admin_user = auth

    super_admins = db.query(User).filter(User.is_super_admin == True).all()

    results = []
    for user in super_admins:
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        results.append(SuperAdminInfo(
            id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            tenant_id=str(user.tenant_id),
            tenant_name=tenant.name if tenant else None,
        ))

    return results


@router.post("/super-admins", response_model=SuperAdminActionResponse)
async def grant_super_admin(
    request: GrantSuperAdminRequest,
    auth: tuple = Depends(verify_super_admin),
    db: Session = Depends(get_db),
):
    """
    Grant super admin privileges to a user by email.

    The user must already exist in the system (have signed in at least once).
    """
    claims, admin_user = auth

    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        return SuperAdminActionResponse(
            success=False,
            error=f"No user found with email {request.email}. They must sign in to Ilana first."
        )

    if user.is_super_admin:
        return SuperAdminActionResponse(
            success=False,
            error=f"{request.email} is already a super admin."
        )

    user.is_super_admin = True
    db.commit()

    logger.info(f"Super admin {claims.email} granted super admin to {request.email}")

    return SuperAdminActionResponse(
        success=True,
        user_email=user.email,
    )


@router.delete("/super-admins/{user_id}", response_model=SuperAdminActionResponse)
async def revoke_super_admin(
    user_id: str,
    auth: tuple = Depends(verify_super_admin),
    db: Session = Depends(get_db),
):
    """
    Revoke super admin privileges from a user.

    Cannot revoke your own super admin access.
    """
    claims, admin_user = auth

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if str(user.id) == str(admin_user.id):
        return SuperAdminActionResponse(
            success=False,
            error="You cannot revoke your own super admin access."
        )

    if not user.is_super_admin:
        return SuperAdminActionResponse(
            success=False,
            error=f"{user.email} is not a super admin."
        )

    user.is_super_admin = False
    db.commit()

    logger.info(f"Super admin {claims.email} revoked super admin from {user.email}")

    return SuperAdminActionResponse(
        success=True,
        user_email=user.email,
    )


# =============================================================================
# Tenant Management
# =============================================================================

@router.patch("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: str,
    request: UpdateTenantRequest,
    auth: tuple = Depends(verify_super_admin),
    db: Session = Depends(get_db),
):
    """
    Update tenant information (name, notes, tags).
    """
    claims, admin_user = auth

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if request.name is not None:
        old_name = tenant.name
        tenant.name = request.name
        logger.info(f"Super admin {claims.email} renamed tenant from '{old_name}' to '{request.name}'")

    # Note: notes and tags would require adding columns to Tenant model
    # For now, we'll store them in a JSON field if it exists, or skip

    db.commit()

    return {"success": True, "tenant_id": str(tenant.id), "name": tenant.name}


@router.post("/tenants/{tenant_id}/seats")
async def update_seat_count(
    tenant_id: str,
    request: UpdateSeatsRequest,
    auth: tuple = Depends(verify_super_admin),
    db: Session = Depends(get_db),
):
    """
    Update the seat count for a tenant's subscription.

    If the subscription has a Stripe subscription ID, this will also
    update the quantity in Stripe (which may trigger prorated charges).
    """
    claims, admin_user = auth

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    subscription = db.query(Subscription).filter(
        Subscription.tenant_id == tenant.id,
        Subscription.status == "active"
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="No active subscription found")

    old_seats = subscription.seat_count
    stripe_updated = False
    stripe_error = None

    # Update Stripe subscription quantity if linked
    if subscription.stripe_subscription_id and STRIPE_AVAILABLE and STRIPE_SECRET_KEY:
        try:
            # Get the subscription to find the item ID
            stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
            if stripe_sub.get("items", {}).get("data"):
                item_id = stripe_sub["items"]["data"][0]["id"]
                # Update the quantity (this triggers proration by default)
                stripe.SubscriptionItem.modify(
                    item_id,
                    quantity=request.seat_count,
                    proration_behavior="create_prorations"  # Bill immediately for changes
                )
                stripe_updated = True
                logger.info(f"Updated Stripe subscription {subscription.stripe_subscription_id} to {request.seat_count} seats")
        except stripe.error.StripeError as e:
            stripe_error = str(e)
            logger.error(f"Failed to update Stripe subscription seats: {e}")
            # Still update local DB even if Stripe fails

    subscription.seat_count = request.seat_count
    db.commit()

    logger.info(f"Super admin {claims.email} changed seats for {tenant.name} from {old_seats} to {request.seat_count}")

    return {
        "success": True,
        "tenant_id": str(tenant.id),
        "old_seats": old_seats,
        "new_seats": request.seat_count,
        "stripe_updated": stripe_updated,
        "stripe_error": stripe_error
    }


@router.post("/tenants/{tenant_id}/subscription")
async def manage_subscription(
    tenant_id: str,
    request: SubscriptionActionRequest,
    auth: tuple = Depends(verify_super_admin),
    db: Session = Depends(get_db),
):
    """
    Manage subscription: cancel, activate, or convert to paid.

    If the subscription has a Stripe subscription ID, this will also
    update Stripe directly (cancel/reactivate the Stripe subscription).
    """
    claims, admin_user = auth

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    subscription = db.query(Subscription).filter(
        Subscription.tenant_id == tenant.id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="No subscription found")

    stripe_updated = False
    stripe_error = None

    if request.action == "cancel":
        # Cancel in Stripe if has Stripe subscription
        if subscription.stripe_subscription_id and STRIPE_AVAILABLE and STRIPE_SECRET_KEY:
            try:
                # Cancel at period end (graceful) or immediately based on request
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=True  # Graceful cancellation
                )
                stripe_updated = True
                logger.info(f"Cancelled Stripe subscription {subscription.stripe_subscription_id}")
            except stripe.error.StripeError as e:
                stripe_error = str(e)
                logger.error(f"Failed to cancel Stripe subscription: {e}")

        subscription.status = "cancelled"
        logger.info(f"Super admin {claims.email} cancelled subscription for {tenant.name}")

    elif request.action == "cancel_immediately":
        # Cancel immediately in Stripe
        if subscription.stripe_subscription_id and STRIPE_AVAILABLE and STRIPE_SECRET_KEY:
            try:
                stripe.Subscription.cancel(subscription.stripe_subscription_id)
                stripe_updated = True
                logger.info(f"Immediately cancelled Stripe subscription {subscription.stripe_subscription_id}")
            except stripe.error.StripeError as e:
                stripe_error = str(e)
                logger.error(f"Failed to cancel Stripe subscription: {e}")

        subscription.status = "cancelled"
        logger.info(f"Super admin {claims.email} immediately cancelled subscription for {tenant.name}")

    elif request.action == "activate":
        # Reactivate in Stripe if it was scheduled for cancellation
        if subscription.stripe_subscription_id and STRIPE_AVAILABLE and STRIPE_SECRET_KEY:
            try:
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=False  # Remove scheduled cancellation
                )
                stripe_updated = True
                logger.info(f"Reactivated Stripe subscription {subscription.stripe_subscription_id}")
            except stripe.error.StripeError as e:
                stripe_error = str(e)
                logger.error(f"Failed to reactivate Stripe subscription: {e}")

        subscription.status = "active"
        logger.info(f"Super admin {claims.email} activated subscription for {tenant.name}")

    elif request.action == "convert_to_paid":
        subscription.plan_type = request.plan_type or "active"
        subscription.status = "active"
        subscription.converted_at = datetime.utcnow()
        logger.info(f"Super admin {claims.email} converted {tenant.name} to paid subscription")
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {request.action}")

    db.commit()

    return {
        "success": True,
        "tenant_id": str(tenant.id),
        "status": subscription.status,
        "plan_type": subscription.plan_type,
        "stripe_updated": stripe_updated,
        "stripe_error": stripe_error
    }


# =============================================================================
# Cross-Tenant User Seat Management
# =============================================================================

@router.post("/users/{user_id}/seat")
async def manage_user_seat(
    user_id: str,
    request: UserSeatActionRequest,
    auth: tuple = Depends(verify_super_admin),
    db: Session = Depends(get_db),
):
    """
    Revoke or restore a user's seat across any tenant.
    """
    claims, admin_user = auth

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    subscription = db.query(Subscription).filter(
        Subscription.tenant_id == user.tenant_id,
        Subscription.status == "active"
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="No active subscription for user's tenant")

    seat = db.query(SeatAssignment).filter(
        SeatAssignment.user_id == user.id,
        SeatAssignment.subscription_id == subscription.id
    ).first()

    if request.action == "revoke":
        if seat and seat.status == "active":
            seat.status = "revoked"
            seat.revoked_at = datetime.utcnow()
            seat.revoked_by = str(admin_user.id)
            db.commit()
            logger.info(f"Super admin {claims.email} revoked seat for {user.email}")
            return {"success": True, "action": "revoked", "user_email": user.email}
        else:
            return {"success": False, "error": "User does not have an active seat"}

    elif request.action == "restore":
        # Check seat availability
        active_seats = db.query(SeatAssignment).filter(
            SeatAssignment.subscription_id == subscription.id,
            SeatAssignment.status == "active"
        ).count()

        if active_seats >= subscription.seat_count:
            return {"success": False, "error": "No seats available"}

        if seat:
            seat.status = "active"
            seat.revoked_at = None
            seat.revoked_by = None
        else:
            # Create new seat assignment
            seat = SeatAssignment(
                user_id=user.id,
                subscription_id=subscription.id,
                status="active",
                assigned_at=datetime.utcnow()
            )
            db.add(seat)

        db.commit()
        logger.info(f"Super admin {claims.email} restored seat for {user.email}")
        return {"success": True, "action": "restored", "user_email": user.email}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {request.action}")


# =============================================================================
# Activity Logs
# =============================================================================

@router.get("/activity-logs", response_model=List[ActivityLogEntry])
async def get_activity_logs(
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    tenant_id: Optional[str] = Query(None),
    auth: tuple = Depends(verify_super_admin),
    db: Session = Depends(get_db),
):
    """
    Get activity logs across all tenants or for a specific tenant.
    """
    claims, admin_user = auth

    query = db.query(AuditEvent).order_by(AuditEvent.created_at.desc())

    if tenant_id:
        query = query.filter(AuditEvent.tenant_id == tenant_id)

    events = query.offset(offset).limit(limit).all()

    results = []
    tenant_cache = {}

    for event in events:
        # Cache tenant lookups
        if event.tenant_id not in tenant_cache:
            tenant = db.query(Tenant).filter(Tenant.id == event.tenant_id).first()
            tenant_cache[event.tenant_id] = tenant.name if tenant else None

        results.append(ActivityLogEntry(
            id=str(event.id),
            tenant_id=str(event.tenant_id),
            tenant_name=tenant_cache.get(event.tenant_id),
            user_id=str(event.user_id) if event.user_id else None,
            user_email=event.user_email,
            action=event.action or event.event_type or "unknown",
            details=str(event.metadata) if hasattr(event, 'metadata') and event.metadata else None,
            created_at=event.created_at.isoformat() if event.created_at else "",
        ))

    return results


# =============================================================================
# Analytics
# =============================================================================

@router.get("/analytics", response_model=AnalyticsData)
async def get_analytics(
    days: int = Query(30, le=365),
    auth: tuple = Depends(verify_super_admin),
    db: Session = Depends(get_db),
):
    """
    Get analytics data for charts and reporting.
    """
    claims, admin_user = auth

    start_date = datetime.utcnow() - timedelta(days=days)

    # Signups by day (tenant creations)
    signups_raw = db.query(
        func.date(Tenant.created_at).label('date'),
        func.count(Tenant.id).label('count')
    ).filter(
        Tenant.created_at >= start_date
    ).group_by(
        func.date(Tenant.created_at)
    ).order_by(
        func.date(Tenant.created_at)
    ).all()

    signups_by_day = [{"date": str(row.date), "count": row.count} for row in signups_raw]

    # Active users by day (based on last_active_at)
    active_raw = db.query(
        func.date(User.last_active_at).label('date'),
        func.count(func.distinct(User.id)).label('count')
    ).filter(
        User.last_active_at >= start_date
    ).group_by(
        func.date(User.last_active_at)
    ).order_by(
        func.date(User.last_active_at)
    ).all()

    active_users_by_day = [{"date": str(row.date), "count": row.count} for row in active_raw]

    # Trials converted
    trials_converted = db.query(Subscription).filter(
        Subscription.converted_at.isnot(None),
        Subscription.converted_at >= start_date
    ).count()

    # Trials expired (trial ended but not converted)
    trials_expired = db.query(Subscription).filter(
        Subscription.plan_type == "trial",
        Subscription.trial_ends_at < datetime.utcnow(),
        Subscription.converted_at.is_(None)
    ).count()

    # Average trial duration
    converted_subs = db.query(Subscription).filter(
        Subscription.converted_at.isnot(None),
        Subscription.trial_started_at.isnot(None)
    ).all()

    if converted_subs:
        total_days = sum(
            (s.converted_at - s.trial_started_at).days
            for s in converted_subs
            if s.converted_at and s.trial_started_at
        )
        avg_trial_duration = total_days / len(converted_subs)
    else:
        avg_trial_duration = 0.0

    # Top tenants by user count
    top_tenants_raw = db.query(
        Tenant.name,
        func.count(User.id).label('user_count')
    ).join(
        User, User.tenant_id == Tenant.id
    ).group_by(
        Tenant.id, Tenant.name
    ).order_by(
        func.count(User.id).desc()
    ).limit(10).all()

    top_tenants = [{"tenant_name": row.name or "Unnamed", "user_count": row.user_count} for row in top_tenants_raw]

    return AnalyticsData(
        signups_by_day=signups_by_day,
        active_users_by_day=active_users_by_day,
        trials_converted=trials_converted,
        trials_expired=trials_expired,
        avg_trial_duration_days=avg_trial_duration,
        top_tenants_by_users=top_tenants,
    )


# =============================================================================
# Data Export
# =============================================================================

@router.get("/export/tenants")
async def export_tenants(
    format: str = Query("json", regex="^(json|csv)$"),
    auth: tuple = Depends(verify_super_admin),
    db: Session = Depends(get_db),
):
    """
    Export all tenant data as JSON or CSV.
    """
    from fastapi.responses import Response
    import csv
    import io

    claims, admin_user = auth

    tenants = db.query(Tenant).order_by(Tenant.created_at.desc()).all()

    data = []
    for tenant in tenants:
        subscription = db.query(Subscription).filter(
            Subscription.tenant_id == tenant.id,
            Subscription.status == "active"
        ).first()

        user_count = db.query(User).filter(User.tenant_id == tenant.id).count()

        row = {
            "id": str(tenant.id),
            "name": tenant.name or "",
            "azure_tenant_id": tenant.azure_tenant_id,
            "created_at": tenant.created_at.isoformat() if tenant.created_at else "",
            "user_count": user_count,
            "seats_total": subscription.seat_count if subscription else 0,
            "plan_type": subscription.plan_type if subscription else "none",
            "status": subscription.status if subscription else "none",
            "has_stripe": bool(subscription.stripe_subscription_id) if subscription else False,
        }
        data.append(row)

    if format == "csv":
        output = io.StringIO()
        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        csv_content = output.getvalue()
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=tenants_export.csv"}
        )

    return data


@router.get("/export/users")
async def export_users(
    format: str = Query("json", regex="^(json|csv)$"),
    tenant_id: Optional[str] = Query(None),
    auth: tuple = Depends(verify_super_admin),
    db: Session = Depends(get_db),
):
    """
    Export user data as JSON or CSV.
    """
    from fastapi.responses import Response
    import csv
    import io

    claims, admin_user = auth

    query = db.query(User).order_by(User.created_at.desc())
    if tenant_id:
        query = query.filter(User.tenant_id == tenant_id)

    users = query.all()

    data = []
    tenant_cache = {}

    for user in users:
        if user.tenant_id not in tenant_cache:
            tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
            tenant_cache[user.tenant_id] = tenant.name if tenant else ""

        # Check seat status
        subscription = db.query(Subscription).filter(
            Subscription.tenant_id == user.tenant_id,
            Subscription.status == "active"
        ).first()

        has_seat = False
        if subscription:
            seat = db.query(SeatAssignment).filter(
                SeatAssignment.user_id == user.id,
                SeatAssignment.subscription_id == subscription.id,
                SeatAssignment.status == "active"
            ).first()
            has_seat = seat is not None

        row = {
            "id": str(user.id),
            "email": user.email or "",
            "display_name": user.display_name or "",
            "tenant_id": str(user.tenant_id),
            "tenant_name": tenant_cache.get(user.tenant_id, ""),
            "is_admin": user.is_admin,
            "is_super_admin": user.is_super_admin,
            "has_seat": has_seat,
            "created_at": user.created_at.isoformat() if user.created_at else "",
            "last_active_at": user.last_active_at.isoformat() if user.last_active_at else "",
        }
        data.append(row)

    if format == "csv":
        output = io.StringIO()
        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        csv_content = output.getvalue()
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=users_export.csv"}
        )

    return data


# =============================================================================
# Stripe Management Endpoints
# =============================================================================

class RefundRequest(BaseModel):
    """Request to issue a refund"""
    amount_cents: Optional[int] = None  # None = full refund
    reason: Optional[str] = None


@router.get("/tenants/{tenant_id}/stripe")
async def get_stripe_details(
    tenant_id: str,
    auth: tuple = Depends(verify_super_admin),
    db: Session = Depends(get_db),
):
    """
    Get detailed Stripe subscription and customer information for a tenant.
    """
    claims, admin_user = auth

    if not STRIPE_AVAILABLE or not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    subscription = db.query(Subscription).filter(
        Subscription.tenant_id == tenant.id
    ).first()

    if not subscription or not subscription.stripe_subscription_id:
        return {
            "has_stripe": False,
            "message": "No Stripe subscription linked to this tenant"
        }

    try:
        # Fetch subscription from Stripe
        stripe_sub = stripe.Subscription.retrieve(
            subscription.stripe_subscription_id,
            expand=["customer", "latest_invoice"]
        )

        # Get customer details
        customer = stripe_sub.get("customer", {})
        if isinstance(customer, str):
            customer = stripe.Customer.retrieve(customer)

        # Get payment method
        payment_method = None
        if customer.get("invoice_settings", {}).get("default_payment_method"):
            pm_id = customer["invoice_settings"]["default_payment_method"]
            pm = stripe.PaymentMethod.retrieve(pm_id)
            if pm.get("card"):
                payment_method = {
                    "type": "card",
                    "brand": pm["card"]["brand"],
                    "last4": pm["card"]["last4"],
                    "exp_month": pm["card"]["exp_month"],
                    "exp_year": pm["card"]["exp_year"],
                }

        # Get latest invoice
        latest_invoice = stripe_sub.get("latest_invoice", {})
        if isinstance(latest_invoice, str):
            latest_invoice = stripe.Invoice.retrieve(latest_invoice)

        return {
            "has_stripe": True,
            "subscription": {
                "id": stripe_sub["id"],
                "status": stripe_sub["status"],
                "current_period_start": stripe_sub["current_period_start"],
                "current_period_end": stripe_sub["current_period_end"],
                "cancel_at_period_end": stripe_sub.get("cancel_at_period_end", False),
                "canceled_at": stripe_sub.get("canceled_at"),
                "created": stripe_sub["created"],
                "quantity": stripe_sub["items"]["data"][0]["quantity"] if stripe_sub.get("items", {}).get("data") else 1,
                "plan": {
                    "id": stripe_sub["items"]["data"][0]["price"]["id"] if stripe_sub.get("items", {}).get("data") else None,
                    "amount": stripe_sub["items"]["data"][0]["price"]["unit_amount"] if stripe_sub.get("items", {}).get("data") else None,
                    "interval": stripe_sub["items"]["data"][0]["price"]["recurring"]["interval"] if stripe_sub.get("items", {}).get("data") else None,
                }
            },
            "customer": {
                "id": customer.get("id"),
                "email": customer.get("email"),
                "name": customer.get("name"),
                "created": customer.get("created"),
            },
            "payment_method": payment_method,
            "latest_invoice": {
                "id": latest_invoice.get("id"),
                "status": latest_invoice.get("status"),
                "amount_due": latest_invoice.get("amount_due"),
                "amount_paid": latest_invoice.get("amount_paid"),
                "created": latest_invoice.get("created"),
                "hosted_invoice_url": latest_invoice.get("hosted_invoice_url"),
                "invoice_pdf": latest_invoice.get("invoice_pdf"),
            } if latest_invoice else None
        }

    except stripe.error.StripeError as e:
        logger.error(f"Failed to fetch Stripe details: {e}")
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")


@router.get("/tenants/{tenant_id}/stripe/invoices")
async def get_stripe_invoices(
    tenant_id: str,
    limit: int = Query(10, le=100),
    auth: tuple = Depends(verify_super_admin),
    db: Session = Depends(get_db),
):
    """
    Get invoice history from Stripe for a tenant.
    """
    claims, admin_user = auth

    if not STRIPE_AVAILABLE or not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    subscription = db.query(Subscription).filter(
        Subscription.tenant_id == tenant.id
    ).first()

    if not subscription or not subscription.stripe_customer_id:
        return {"invoices": [], "message": "No Stripe customer linked"}

    try:
        invoices = stripe.Invoice.list(
            customer=subscription.stripe_customer_id,
            limit=limit
        )

        return {
            "invoices": [
                {
                    "id": inv["id"],
                    "number": inv.get("number"),
                    "status": inv["status"],
                    "amount_due": inv["amount_due"],
                    "amount_paid": inv["amount_paid"],
                    "currency": inv["currency"],
                    "created": inv["created"],
                    "period_start": inv.get("period_start"),
                    "period_end": inv.get("period_end"),
                    "hosted_invoice_url": inv.get("hosted_invoice_url"),
                    "invoice_pdf": inv.get("invoice_pdf"),
                }
                for inv in invoices.get("data", [])
            ]
        }

    except stripe.error.StripeError as e:
        logger.error(f"Failed to fetch Stripe invoices: {e}")
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")


@router.post("/tenants/{tenant_id}/stripe/refund")
async def issue_refund(
    tenant_id: str,
    request: RefundRequest,
    auth: tuple = Depends(verify_super_admin),
    db: Session = Depends(get_db),
):
    """
    Issue a refund for the latest paid invoice.

    If amount_cents is not specified, issues a full refund.
    """
    claims, admin_user = auth

    if not STRIPE_AVAILABLE or not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    subscription = db.query(Subscription).filter(
        Subscription.tenant_id == tenant.id
    ).first()

    if not subscription or not subscription.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer linked")

    try:
        # Find the most recent paid invoice
        invoices = stripe.Invoice.list(
            customer=subscription.stripe_customer_id,
            status="paid",
            limit=1
        )

        if not invoices.get("data"):
            raise HTTPException(status_code=400, detail="No paid invoices found")

        latest_invoice = invoices["data"][0]
        payment_intent_id = latest_invoice.get("payment_intent")

        if not payment_intent_id:
            raise HTTPException(status_code=400, detail="Invoice has no payment to refund")

        # Issue the refund
        refund_params = {"payment_intent": payment_intent_id}

        if request.amount_cents:
            refund_params["amount"] = request.amount_cents

        if request.reason:
            refund_params["reason"] = "requested_by_customer"
            refund_params["metadata"] = {"admin_reason": request.reason}

        refund = stripe.Refund.create(**refund_params)

        logger.info(f"Super admin {claims.email} issued refund {refund['id']} for tenant {tenant.name}")

        return {
            "success": True,
            "refund": {
                "id": refund["id"],
                "amount": refund["amount"],
                "currency": refund["currency"],
                "status": refund["status"],
                "created": refund["created"],
            }
        }

    except stripe.error.StripeError as e:
        logger.error(f"Failed to issue refund: {e}")
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")


@router.post("/tenants/{tenant_id}/stripe/sync")
async def sync_stripe_subscription(
    tenant_id: str,
    auth: tuple = Depends(verify_super_admin),
    db: Session = Depends(get_db),
):
    """
    Sync local subscription data with Stripe.

    Fetches the latest data from Stripe and updates the local database.
    Useful if webhook events were missed.
    """
    claims, admin_user = auth

    if not STRIPE_AVAILABLE or not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    subscription = db.query(Subscription).filter(
        Subscription.tenant_id == tenant.id
    ).first()

    if not subscription or not subscription.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="No Stripe subscription linked")

    try:
        stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)

        # Update local database
        old_status = subscription.status
        old_seats = subscription.seat_count

        # Map Stripe status to our status
        if stripe_sub["status"] in ["active", "trialing"]:
            subscription.status = "active"
        elif stripe_sub["status"] in ["canceled", "unpaid"]:
            subscription.status = "cancelled"
        else:
            subscription.status = stripe_sub["status"]

        # Update seat count from Stripe quantity
        if stripe_sub.get("items", {}).get("data"):
            subscription.seat_count = stripe_sub["items"]["data"][0].get("quantity", 1)

        # Update plan type based on Stripe status
        if stripe_sub["status"] == "trialing":
            subscription.plan_type = "trial"
        elif stripe_sub["status"] == "active":
            subscription.plan_type = "active"

        db.commit()

        logger.info(f"Super admin {claims.email} synced Stripe subscription for {tenant.name}")

        return {
            "success": True,
            "changes": {
                "status": {"old": old_status, "new": subscription.status},
                "seats": {"old": old_seats, "new": subscription.seat_count},
            },
            "stripe_status": stripe_sub["status"],
        }

    except stripe.error.StripeError as e:
        logger.error(f"Failed to sync Stripe subscription: {e}")
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")


# Export
__all__ = ["router"]
