"""
Admin API Routes for Ilana

Handles:
- User listing with seat status
- Seat revocation and restoration
- Dashboard data for admin portal
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, get_tenant_by_azure_id, get_user_by_azure_id
from auth import TokenClaims, get_current_user
from seat_manager import (
    revoke_user_seat,
    restore_user_seat,
    get_admin_dashboard_data,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# =============================================================================
# Response Models
# =============================================================================

class AdminUserResponse(BaseModel):
    """User info for admin portal"""
    id: str
    email: Optional[str]
    display_name: Optional[str]
    is_admin: bool
    last_active_at: Optional[str]
    has_seat: bool
    seat_assigned_at: Optional[str]


class SubscriptionResponse(BaseModel):
    """Subscription info for admin portal"""
    plan_type: str
    seats_total: int
    seats_used: int
    seats_available: int


class StatsResponse(BaseModel):
    """Usage statistics"""
    total_users: int
    users_with_seats: int
    inactive_users: int
    inactive_threshold_days: int


class DashboardResponse(BaseModel):
    """Full dashboard data"""
    tenant: dict
    subscription: SubscriptionResponse
    users: List[AdminUserResponse]
    stats: StatsResponse


class SeatActionResponse(BaseModel):
    """Response from seat actions (revoke/restore)"""
    success: bool
    seats_used: Optional[int] = None
    seats_total: Optional[int] = None
    user_email: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# Admin Verification Middleware
# =============================================================================

async def verify_admin(
    claims: TokenClaims = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TokenClaims:
    """
    Verify the current user is an admin

    Checks database for is_admin flag, not just token roles.
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
# Endpoints
# =============================================================================

@router.get("/users", response_model=DashboardResponse)
async def list_users(
    claims: TokenClaims = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    List all users with seat status (admin only)

    Returns full dashboard data including:
    - User list with seat assignments
    - Subscription info (seats used/total)
    - Usage statistics
    """
    data = get_admin_dashboard_data(db, claims.tenant_id, claims.user_id)

    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])

    return DashboardResponse(
        tenant=data["tenant"],
        subscription=SubscriptionResponse(**data["subscription"]),
        users=[AdminUserResponse(**u) for u in data["users"]],
        stats=StatsResponse(**data["stats"]),
    )


@router.post("/users/{user_id}/revoke", response_model=SeatActionResponse)
async def revoke_seat(
    user_id: str,
    claims: TokenClaims = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    Revoke a user's seat (admin only)

    The user will see "No seats available" on their next use.
    """
    result = revoke_user_seat(
        db=db,
        admin_tenant_id=claims.tenant_id,
        admin_user_id=claims.user_id,
        target_user_id=user_id,
    )

    if not result["success"]:
        return SeatActionResponse(
            success=False,
            error=result.get("error", "Unknown error"),
        )

    return SeatActionResponse(
        success=True,
        seats_used=result["seats_used"],
        seats_total=result["seats_total"],
        user_email=result.get("user_email"),
    )


@router.post("/users/{user_id}/restore", response_model=SeatActionResponse)
async def restore_seat(
    user_id: str,
    claims: TokenClaims = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    Restore a revoked user's seat (admin only)

    Only succeeds if seats are available.
    """
    result = restore_user_seat(
        db=db,
        admin_tenant_id=claims.tenant_id,
        admin_user_id=claims.user_id,
        target_user_id=user_id,
    )

    if not result["success"]:
        return SeatActionResponse(
            success=False,
            error=result.get("error", "Unknown error"),
        )

    return SeatActionResponse(
        success=True,
        seats_used=result["seats_used"],
        seats_total=result["seats_total"],
        user_email=result.get("user_email"),
    )


@router.get("/stats")
async def get_stats(
    claims: TokenClaims = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    Get quick stats for admin dashboard header
    """
    data = get_admin_dashboard_data(db, claims.tenant_id, claims.user_id)

    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])

    return {
        "seats_used": data["subscription"]["seats_used"],
        "seats_total": data["subscription"]["seats_total"],
        "inactive_users": data["stats"]["inactive_users"],
    }


# Export
__all__ = ["router"]
