"""
Development/Testing Routes for Ilana

ONLY enabled when DEV_MODE=true

Provides endpoints to:
- Create mock tenants/users for testing
- Simulate different trial states
- Test the trial flow without Microsoft SSO
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Only enable in dev mode
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

router = APIRouter(prefix="/api/dev", tags=["development"])


class DevUserResponse(BaseModel):
    """Mock user for dev testing"""
    tenant_id: str
    user_id: str
    email: str
    name: str
    is_admin: bool
    has_seat: bool


class DevTrialResponse(BaseModel):
    """Mock trial status for dev testing"""
    status: str
    is_trial: bool
    days_remaining: Optional[int]
    grace_days_remaining: Optional[int]
    can_access: bool
    read_only: bool
    trial_ends_at: Optional[str]


class DevValidateResponse(BaseModel):
    """Mock validate response for dev testing"""
    status: str
    user: DevUserResponse
    trial: DevTrialResponse
    message: Optional[str]


def check_dev_mode():
    """Raise error if not in dev mode"""
    if not DEV_MODE:
        raise HTTPException(
            status_code=403,
            detail="Dev endpoints disabled. Set DEV_MODE=true to enable."
        )


@router.get("/status")
async def dev_status():
    """Check if dev mode is enabled"""
    return {
        "dev_mode": DEV_MODE,
        "message": "Dev mode enabled - test endpoints available" if DEV_MODE else "Dev mode disabled"
    }


@router.get("/mock-validate")
async def mock_validate(
    trial_status: str = Query("trial", description="Trial status: trial, expired, blocked, active"),
    days_remaining: int = Query(14, description="Days remaining in trial (or negative for expired)"),
    grace_days: int = Query(7, description="Grace days remaining (for expired status)"),
    has_seat: bool = Query(True, description="Whether user has a seat"),
    is_admin: bool = Query(True, description="Whether user is admin"),
) -> DevValidateResponse:
    """
    Mock the /api/auth/validate response for testing

    Use this to test how the frontend handles different trial states
    without needing Microsoft SSO.

    Examples:
    - Active trial: /api/dev/mock-validate?trial_status=trial&days_remaining=10
    - Expired (grace): /api/dev/mock-validate?trial_status=expired&grace_days=3
    - Blocked: /api/dev/mock-validate?trial_status=blocked
    - Paid: /api/dev/mock-validate?trial_status=active
    - No seat: /api/dev/mock-validate?has_seat=false
    """
    check_dev_mode()

    # Calculate trial end date based on status
    now = datetime.utcnow()
    if trial_status == "trial":
        trial_ends = now + timedelta(days=days_remaining)
    elif trial_status == "expired":
        trial_ends = now - timedelta(days=abs(days_remaining) if days_remaining < 0 else 1)
    else:
        trial_ends = now - timedelta(days=30)  # Long expired for blocked

    # Determine access based on status
    can_access = trial_status in ["trial", "expired", "active"]
    read_only = trial_status == "expired"
    is_trial = trial_status in ["trial", "expired", "blocked"]

    # Build mock response
    user = DevUserResponse(
        tenant_id="dev-tenant-12345",
        user_id="dev-user-67890",
        email="developer@test.local",
        name="Dev User",
        is_admin=is_admin,
        has_seat=has_seat,
    )

    trial = DevTrialResponse(
        status=trial_status,
        is_trial=is_trial,
        days_remaining=days_remaining if trial_status == "trial" else (0 if trial_status == "active" else -abs(days_remaining)),
        grace_days_remaining=grace_days if trial_status == "expired" else None,
        can_access=can_access,
        read_only=read_only,
        trial_ends_at=trial_ends.isoformat() if is_trial else None,
    )

    # Determine status and message
    if not has_seat:
        status = "no_seats"
        message = "No seats available in your organization."
    elif trial_status == "blocked":
        status = "ok"  # Has seat, but trial check happens at analyze
        message = "Trial expired. Subscribe to continue."
    else:
        status = "ok"
        message = None

    return DevValidateResponse(
        status=status,
        user=user,
        trial=trial,
        message=message,
    )


@router.post("/create-test-tenant")
async def create_test_tenant(
    trial_days_remaining: int = Query(14, description="Days remaining in trial"),
):
    """
    Create a test tenant with subscription in the database

    This creates actual database records for testing the full flow.
    """
    check_dev_mode()

    try:
        from database import get_db_session, Tenant, Subscription, User, SeatAssignment
        import uuid

        with get_db_session() as db:
            # Create test tenant
            tenant = Tenant(
                azure_tenant_id=f"dev-tenant-{uuid.uuid4().hex[:8]}",
                name="Dev Test Organization",
            )
            db.add(tenant)
            db.flush()

            # Create subscription with trial
            now = datetime.utcnow()
            subscription = Subscription(
                tenant_id=tenant.id,
                seat_count=10,
                plan_type="trial",
                status="active",
                trial_started_at=now,
                trial_ends_at=now + timedelta(days=trial_days_remaining),
            )
            db.add(subscription)
            db.flush()

            # Create test user (admin)
            user = User(
                tenant_id=tenant.id,
                azure_user_id=f"dev-user-{uuid.uuid4().hex[:8]}",
                email="devtest@local.test",
                display_name="Dev Test User",
                is_admin=True,
            )
            db.add(user)
            db.flush()

            # Assign seat
            seat = SeatAssignment(
                user_id=user.id,
                subscription_id=subscription.id,
                status="active",
            )
            db.add(seat)
            db.commit()

            return {
                "success": True,
                "tenant_id": str(tenant.id),
                "azure_tenant_id": tenant.azure_tenant_id,
                "user_id": str(user.id),
                "azure_user_id": user.azure_user_id,
                "subscription_id": str(subscription.id),
                "trial_ends_at": subscription.trial_ends_at.isoformat(),
                "message": f"Test tenant created with {trial_days_remaining} day trial",
            }

    except Exception as e:
        logger.error(f"Failed to create test tenant: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/set-trial-days/{azure_tenant_id}")
async def set_trial_days(
    azure_tenant_id: str,
    days: int = Query(..., description="Days remaining (negative to simulate expired)"),
):
    """
    Adjust trial end date for a tenant

    Use negative days to simulate expired trial.
    Examples:
    - 14 days remaining: /api/dev/set-trial-days/dev-tenant-xxx?days=14
    - Expired 2 days ago: /api/dev/set-trial-days/dev-tenant-xxx?days=-2
    - Grace period (5 days left): /api/dev/set-trial-days/dev-tenant-xxx?days=-2
    """
    check_dev_mode()

    try:
        from database import get_db_session, get_tenant_by_azure_id, get_active_subscription

        with get_db_session() as db:
            tenant = get_tenant_by_azure_id(db, azure_tenant_id)
            if not tenant:
                raise HTTPException(status_code=404, detail="Tenant not found")

            subscription = get_active_subscription(db, tenant.id)
            if not subscription:
                raise HTTPException(status_code=404, detail="No active subscription")

            now = datetime.utcnow()
            subscription.trial_ends_at = now + timedelta(days=days)
            db.commit()

            return {
                "success": True,
                "tenant_id": str(tenant.id),
                "trial_ends_at": subscription.trial_ends_at.isoformat(),
                "days_from_now": days,
                "status": "trial" if days > 0 else ("expired" if days > -7 else "blocked"),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set trial days: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/convert-to-paid/{azure_tenant_id}")
async def convert_to_paid(azure_tenant_id: str):
    """
    Convert a trial tenant to paid subscription
    """
    check_dev_mode()

    try:
        from database import get_db_session, get_tenant_by_azure_id, get_active_subscription

        with get_db_session() as db:
            tenant = get_tenant_by_azure_id(db, azure_tenant_id)
            if not tenant:
                raise HTTPException(status_code=404, detail="Tenant not found")

            subscription = get_active_subscription(db, tenant.id)
            if not subscription:
                raise HTTPException(status_code=404, detail="No active subscription")

            subscription.plan_type = "active"
            subscription.converted_at = datetime.utcnow()
            db.commit()

            return {
                "success": True,
                "tenant_id": str(tenant.id),
                "plan_type": subscription.plan_type,
                "converted_at": subscription.converted_at.isoformat(),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to convert to paid: {e}")
        raise HTTPException(status_code=500, detail=str(e))
