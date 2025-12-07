"""
Seat Management for Ilana Freemium Model

Handles:
- First-come-first-served seat allocation
- Seat validation on API requests
- Admin seat revocation/restoration
- Tenant and subscription creation
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
import uuid

from sqlalchemy.orm import Session

from database import (
    Tenant,
    Subscription,
    User,
    SeatAssignment,
    get_tenant_by_azure_id,
    get_user_by_azure_id,
    get_active_subscription,
    get_active_seat_assignment,
    count_active_seats,
    get_users_with_seats,
)
from auth import TokenClaims
from trial_manager import (
    TRIAL_DURATION_DAYS,
    TRIAL_SEAT_COUNT,
    calculate_trial_end_date,
    get_trial_status,
)

logger = logging.getLogger(__name__)

# Default seat count for trial
DEFAULT_TRIAL_SEATS = TRIAL_SEAT_COUNT  # 10 seats during trial

# Days of inactivity to flag user
INACTIVE_DAYS_THRESHOLD = 30


@dataclass
class SeatValidationResult:
    """Result of seat validation check"""
    has_seat: bool
    status: str  # 'ok', 'no_seats', 'revoked', 'new_seat'
    user_id: Optional[str]
    tenant_id: Optional[str]
    seats_used: int
    seats_total: int
    is_admin: bool
    message: Optional[str] = None


@dataclass
class UserInfo:
    """User information for API responses"""
    id: str
    email: Optional[str]
    display_name: Optional[str]
    is_admin: bool
    last_active: Optional[str]
    has_seat: bool


@dataclass
class TenantInfo:
    """Tenant information for API responses"""
    id: str
    name: Optional[str]
    seats_used: int
    seats_total: int
    plan_type: str


# =============================================================================
# Core Seat Management
# =============================================================================

def validate_and_assign_seat(
    db: Session,
    claims: TokenClaims
) -> SeatValidationResult:
    """
    Main entry point: validate user and assign seat if available

    This implements the first-come-first-served model:
    1. Get or create tenant
    2. Get or create user
    3. Check if user has seat
    4. If not, try to assign one

    Args:
        db: Database session
        claims: Validated token claims

    Returns:
        SeatValidationResult with seat status
    """
    # Step 1: Get or create tenant
    tenant = get_or_create_tenant(db, claims.tenant_id)
    logger.debug(f"Tenant: {tenant.id} ({tenant.name or 'unnamed'})")

    # Step 2: Get or create subscription
    subscription = get_or_create_subscription(db, tenant.id)
    logger.debug(f"Subscription: {subscription.seat_count} seats, {subscription.plan_type}")

    # Step 3: Get or create user
    user, is_new_user = get_or_create_user(db, tenant.id, claims)
    logger.debug(f"User: {user.email} (new={is_new_user})")

    # Update last active timestamp
    user.last_active_at = datetime.utcnow()

    # Step 4: Check current seat status
    seats_used = count_active_seats(db, subscription.id)
    existing_seat = get_active_seat_assignment(db, user.id, subscription.id)

    if existing_seat:
        # User already has a seat
        db.commit()
        return SeatValidationResult(
            has_seat=True,
            status="ok",
            user_id=str(user.id),
            tenant_id=str(tenant.id),
            seats_used=seats_used,
            seats_total=subscription.seat_count,
            is_admin=user.is_admin,
        )

    # Check if user's seat was revoked
    revoked_seat = db.query(SeatAssignment).filter(
        SeatAssignment.user_id == user.id,
        SeatAssignment.subscription_id == subscription.id,
        SeatAssignment.status == "revoked"
    ).first()

    if revoked_seat:
        # User had seat but was revoked by admin
        db.commit()
        return SeatValidationResult(
            has_seat=False,
            status="revoked",
            user_id=str(user.id),
            tenant_id=str(tenant.id),
            seats_used=seats_used,
            seats_total=subscription.seat_count,
            is_admin=user.is_admin,
            message="Your seat has been revoked. Contact your admin.",
        )

    # Step 5: Try to assign a new seat
    if seats_used < subscription.seat_count:
        # Seats available - assign one
        seat = SeatAssignment(
            user_id=user.id,
            subscription_id=subscription.id,
            status="active",
        )
        db.add(seat)
        db.commit()

        logger.info(f"Assigned seat to {user.email} ({seats_used + 1}/{subscription.seat_count})")

        return SeatValidationResult(
            has_seat=True,
            status="new_seat",
            user_id=str(user.id),
            tenant_id=str(tenant.id),
            seats_used=seats_used + 1,
            seats_total=subscription.seat_count,
            is_admin=user.is_admin,
            message="Welcome! A seat has been assigned to you.",
        )

    # No seats available
    db.commit()
    logger.info(f"No seats available for {user.email} ({seats_used}/{subscription.seat_count})")

    return SeatValidationResult(
        has_seat=False,
        status="no_seats",
        user_id=str(user.id),
        tenant_id=str(tenant.id),
        seats_used=seats_used,
        seats_total=subscription.seat_count,
        is_admin=user.is_admin,
        message=f"No seats available. All {subscription.seat_count} seats are occupied.",
    )


def get_or_create_tenant(db: Session, azure_tenant_id: str) -> Tenant:
    """Get existing tenant or create new one"""
    tenant = get_tenant_by_azure_id(db, azure_tenant_id)

    if not tenant:
        tenant = Tenant(
            azure_tenant_id=azure_tenant_id,
        )
        db.add(tenant)
        db.flush()  # Get the ID without committing
        logger.info(f"Created new tenant: {azure_tenant_id[:8]}...")

    return tenant


def get_or_create_subscription(db: Session, tenant_id: uuid.UUID) -> Subscription:
    """Get existing subscription or create 14-day trial"""
    subscription = get_active_subscription(db, tenant_id)

    if not subscription:
        now = datetime.utcnow()
        trial_end = calculate_trial_end_date(now)

        subscription = Subscription(
            tenant_id=tenant_id,
            seat_count=DEFAULT_TRIAL_SEATS,
            plan_type="trial",
            status="active",
            trial_started_at=now,
            trial_ends_at=trial_end,
        )
        db.add(subscription)
        db.flush()
        logger.info(
            f"Started {TRIAL_DURATION_DAYS}-day trial for tenant {tenant_id} "
            f"(ends {trial_end.strftime('%Y-%m-%d')})"
        )

    return subscription


def get_or_create_user(
    db: Session,
    tenant_id: uuid.UUID,
    claims: TokenClaims
) -> Tuple[User, bool]:
    """
    Get existing user or create new one

    First user in a tenant automatically becomes admin.

    Returns:
        Tuple of (User, is_new_user)
    """
    user = get_user_by_azure_id(db, tenant_id, claims.user_id)

    if user:
        # Update user info in case it changed
        user.email = claims.email or user.email
        user.display_name = claims.name or user.display_name
        return user, False

    # Check if this is the first user in the tenant
    existing_users = db.query(User).filter(User.tenant_id == tenant_id).count()
    is_first_user = existing_users == 0

    user = User(
        tenant_id=tenant_id,
        azure_user_id=claims.user_id,
        email=claims.email,
        display_name=claims.name,
        is_admin=is_first_user,  # First user becomes admin
    )
    db.add(user)
    db.flush()

    if is_first_user:
        logger.info(f"First user {claims.email} in tenant - granted admin")

    return user, True


# =============================================================================
# Admin Operations
# =============================================================================

def revoke_user_seat(
    db: Session,
    admin_tenant_id: str,
    admin_user_id: str,
    target_user_id: str,
) -> Dict[str, Any]:
    """
    Revoke a user's seat (admin only)

    Args:
        db: Database session
        admin_tenant_id: Azure tenant ID of admin
        admin_user_id: User ID of admin performing action
        target_user_id: ID of user to revoke

    Returns:
        Result dict with success status
    """
    # Get admin's tenant
    tenant = get_tenant_by_azure_id(db, admin_tenant_id)
    if not tenant:
        return {"success": False, "error": "Tenant not found"}

    # Verify admin is actually admin
    admin = get_user_by_azure_id(db, tenant.id, admin_user_id)
    if not admin or not admin.is_admin:
        return {"success": False, "error": "Admin access required"}

    # Get target user
    target_user = db.query(User).filter(User.id == target_user_id).first()
    if not target_user or target_user.tenant_id != tenant.id:
        return {"success": False, "error": "User not found in your organization"}

    # Prevent self-revocation
    if str(target_user.id) == str(admin.id):
        return {"success": False, "error": "Cannot revoke your own seat"}

    # Get subscription and seat
    subscription = get_active_subscription(db, tenant.id)
    if not subscription:
        return {"success": False, "error": "No active subscription"}

    seat = get_active_seat_assignment(db, target_user.id, subscription.id)
    if not seat:
        return {"success": False, "error": "User does not have an active seat"}

    # Revoke the seat
    seat.status = "revoked"
    seat.revoked_at = datetime.utcnow()
    seat.revoked_by = admin.id
    db.commit()

    seats_used = count_active_seats(db, subscription.id)
    logger.info(f"Admin {admin.email} revoked seat for {target_user.email}")

    return {
        "success": True,
        "seats_used": seats_used,
        "seats_total": subscription.seat_count,
        "user_email": target_user.email,
    }


def restore_user_seat(
    db: Session,
    admin_tenant_id: str,
    admin_user_id: str,
    target_user_id: str,
) -> Dict[str, Any]:
    """
    Restore a revoked user's seat (admin only)

    Only works if seats are available.
    """
    # Get admin's tenant
    tenant = get_tenant_by_azure_id(db, admin_tenant_id)
    if not tenant:
        return {"success": False, "error": "Tenant not found"}

    # Verify admin
    admin = get_user_by_azure_id(db, tenant.id, admin_user_id)
    if not admin or not admin.is_admin:
        return {"success": False, "error": "Admin access required"}

    # Get target user
    target_user = db.query(User).filter(User.id == target_user_id).first()
    if not target_user or target_user.tenant_id != tenant.id:
        return {"success": False, "error": "User not found in your organization"}

    # Get subscription
    subscription = get_active_subscription(db, tenant.id)
    if not subscription:
        return {"success": False, "error": "No active subscription"}

    # Check if user already has active seat
    existing_seat = get_active_seat_assignment(db, target_user.id, subscription.id)
    if existing_seat:
        return {"success": False, "error": "User already has an active seat"}

    # Check seat availability
    seats_used = count_active_seats(db, subscription.id)
    if seats_used >= subscription.seat_count:
        return {"success": False, "error": "No seats available"}

    # Find revoked seat or create new one
    revoked_seat = db.query(SeatAssignment).filter(
        SeatAssignment.user_id == target_user.id,
        SeatAssignment.subscription_id == subscription.id,
        SeatAssignment.status == "revoked"
    ).first()

    if revoked_seat:
        # Restore the revoked seat
        revoked_seat.status = "active"
        revoked_seat.revoked_at = None
        revoked_seat.revoked_by = None
    else:
        # Create new seat assignment
        seat = SeatAssignment(
            user_id=target_user.id,
            subscription_id=subscription.id,
            status="active",
        )
        db.add(seat)

    db.commit()

    seats_used = count_active_seats(db, subscription.id)
    logger.info(f"Admin {admin.email} restored seat for {target_user.email}")

    return {
        "success": True,
        "seats_used": seats_used,
        "seats_total": subscription.seat_count,
        "user_email": target_user.email,
    }


def get_admin_dashboard_data(
    db: Session,
    tenant_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """
    Get dashboard data for admin portal

    Returns user list with seat status, usage stats, etc.
    """
    # Get tenant
    tenant = get_tenant_by_azure_id(db, tenant_id)
    if not tenant:
        return {"error": "Tenant not found"}

    # Verify admin
    admin = get_user_by_azure_id(db, tenant.id, user_id)
    if not admin or not admin.is_admin:
        return {"error": "Admin access required"}

    # Get subscription
    subscription = get_active_subscription(db, tenant.id)
    if not subscription:
        return {"error": "No active subscription"}

    # Get all users with seat info
    users = get_users_with_seats(db, tenant.id)

    # Calculate stats
    seats_used = count_active_seats(db, subscription.id)
    inactive_threshold = datetime.utcnow() - timedelta(days=INACTIVE_DAYS_THRESHOLD)

    inactive_users = [
        u for u in users
        if u["has_seat"] and u["last_active_at"]
        and datetime.fromisoformat(u["last_active_at"]) < inactive_threshold
    ]

    # Get trial status for admin dashboard
    trial_status = get_trial_status(subscription)

    return {
        "tenant": {
            "id": str(tenant.id),
            "name": tenant.name,
        },
        "subscription": {
            "plan_type": subscription.plan_type,
            "seats_total": subscription.seat_count,
            "seats_used": seats_used,
            "seats_available": subscription.seat_count - seats_used,
        },
        "users": users,
        "stats": {
            "total_users": len(users),
            "users_with_seats": len([u for u in users if u["has_seat"]]),
            "inactive_users": len(inactive_users),
            "inactive_threshold_days": INACTIVE_DAYS_THRESHOLD,
        },
        "trial": {
            "status": trial_status["status"],
            "is_trial": trial_status["is_trial"],
            "days_remaining": trial_status["days_remaining"],
            "grace_days_remaining": trial_status.get("grace_days_remaining"),
            "ends_at": trial_status.get("trial_ends_at"),
            "message": trial_status["message"],
        },
    }


def update_seat_count(
    db: Session,
    azure_tenant_id: str,
    new_seat_count: int,
    appsource_subscription_id: Optional[str] = None,
    plan_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update seat count from AppSource webhook

    Called when Microsoft notifies us of license changes.
    """
    tenant = get_tenant_by_azure_id(db, azure_tenant_id)
    if not tenant:
        return {"success": False, "error": "Tenant not found"}

    subscription = get_active_subscription(db, tenant.id)
    if not subscription:
        return {"success": False, "error": "No active subscription"}

    old_count = subscription.seat_count
    subscription.seat_count = new_seat_count

    if appsource_subscription_id:
        subscription.appsource_subscription_id = appsource_subscription_id

    if plan_type:
        subscription.plan_type = plan_type

    db.commit()

    logger.info(
        f"Updated seat count for tenant {azure_tenant_id[:8]}: "
        f"{old_count} -> {new_seat_count}"
    )

    return {
        "success": True,
        "old_seat_count": old_count,
        "new_seat_count": new_seat_count,
    }


# Export
__all__ = [
    "SeatValidationResult",
    "UserInfo",
    "TenantInfo",
    "validate_and_assign_seat",
    "revoke_user_seat",
    "restore_user_seat",
    "get_admin_dashboard_data",
    "update_seat_count",
    "DEFAULT_TRIAL_SEATS",
    "INACTIVE_DAYS_THRESHOLD",
]
