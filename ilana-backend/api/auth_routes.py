"""
Authentication API Routes for Ilana

Handles:
- Token validation and seat assignment
- User info retrieval
- Trial status reporting
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

# Rate limiter for auth endpoints
limiter = Limiter(key_func=get_remote_address)

from database import get_db, get_tenant_by_azure_id, get_active_subscription
from auth import TokenClaims, get_current_user, get_optional_user
from seat_manager import validate_and_assign_seat, SeatValidationResult
from trial_manager import get_trial_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


# =============================================================================
# Response Models
# =============================================================================

class UserResponse(BaseModel):
    """User information in API response"""
    id: str
    email: Optional[str]
    name: Optional[str]
    is_admin: bool


class TenantResponse(BaseModel):
    """Tenant information in API response"""
    name: Optional[str]
    seats_used: int
    seats_total: int
    plan_type: str = "trial"


class TrialResponse(BaseModel):
    """Trial status information for 14-day trial model"""
    is_trial: bool  # True if in trial/expired state, False if paid
    status: str  # 'trial', 'expired', 'blocked', 'active'
    days_remaining: Optional[int]  # Days left in trial (negative if expired)
    grace_days_remaining: Optional[int] = None  # Days left in grace period
    ends_at: Optional[str] = None  # Trial end date (ISO string)
    can_access: bool = True  # True if user can use the add-in
    read_only: bool = False  # True if in grace period


class ValidateResponse(BaseModel):
    """Response from /api/auth/validate"""
    status: str  # 'ok', 'no_seats', 'revoked', 'new_seat'
    user: Optional[UserResponse]
    tenant: Optional[TenantResponse]
    trial: Optional[TrialResponse] = None
    message: Optional[str] = None


class MeResponse(BaseModel):
    """Response from /api/auth/me"""
    user: UserResponse
    tenant: TenantResponse
    trial: Optional[TrialResponse] = None
    has_seat: bool


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/validate", response_model=ValidateResponse)
@limiter.limit("60/minute")
async def validate_token_and_seat(
    request: Request,
    claims: TokenClaims = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Validate user token and check/assign seat

    This is the main entry point for the add-in:
    1. Validates Azure AD token
    2. Gets or creates tenant
    3. Gets or creates user
    4. Checks if user has seat
    5. Assigns seat if available

    Returns:
        ValidateResponse with seat status
    """
    try:
        result: SeatValidationResult = validate_and_assign_seat(db, claims)

        # Get subscription for trial status
        plan_type = "trial"  # Default for new tenants
        trial_response = None
        subscription = None

        if result.tenant_id:
            tenant = get_tenant_by_azure_id(db, claims.tenant_id)
            if tenant:
                subscription = get_active_subscription(db, tenant.id)
                if subscription:
                    plan_type = subscription.plan_type or "trial"

                    # Get trial status
                    trial_status = get_trial_status(subscription)
                    trial_response = TrialResponse(
                        is_trial=trial_status["is_trial"],
                        status=trial_status["status"],
                        days_remaining=trial_status["days_remaining"],
                        grace_days_remaining=trial_status.get("grace_days_remaining"),
                        ends_at=trial_status.get("trial_ends_at"),
                        can_access=trial_status["can_access"],
                        read_only=trial_status["read_only"],
                    )

        # Build response based on result
        if result.has_seat:
            return ValidateResponse(
                status=result.status,
                user=UserResponse(
                    id=result.user_id,
                    email=claims.email,
                    name=claims.name,
                    is_admin=result.is_admin,
                ),
                tenant=TenantResponse(
                    name=None,  # We can add tenant name later
                    seats_used=result.seats_used,
                    seats_total=result.seats_total,
                    plan_type=plan_type,
                ),
                trial=trial_response,
                message=result.message,
            )
        else:
            # No seat available
            return ValidateResponse(
                status=result.status,
                user=UserResponse(
                    id=result.user_id,
                    email=claims.email,
                    name=claims.name,
                    is_admin=result.is_admin,
                ) if result.user_id else None,
                tenant=TenantResponse(
                    name=None,
                    seats_used=result.seats_used,
                    seats_total=result.seats_total,
                    plan_type=plan_type,
                ) if result.tenant_id else None,
                trial=trial_response,
                message=result.message,
            )

    except Exception as e:
        logger.error(f"Seat validation error: {e}")
        raise HTTPException(status_code=500, detail="Internal error during seat validation")


@router.get("/me", response_model=MeResponse)
async def get_current_user_info(
    claims: TokenClaims = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current user's information and seat status

    Requires valid authentication token.
    """
    try:
        result: SeatValidationResult = validate_and_assign_seat(db, claims)

        # Get subscription for trial status
        plan_type = "trial"
        trial_response = None

        if result.tenant_id:
            tenant = get_tenant_by_azure_id(db, claims.tenant_id)
            if tenant:
                subscription = get_active_subscription(db, tenant.id)
                if subscription:
                    plan_type = subscription.plan_type or "trial"

                    # Get trial status
                    trial_status = get_trial_status(subscription)
                    trial_response = TrialResponse(
                        is_trial=trial_status["is_trial"],
                        status=trial_status["status"],
                        days_remaining=trial_status["days_remaining"],
                        grace_days_remaining=trial_status.get("grace_days_remaining"),
                        ends_at=trial_status.get("trial_ends_at"),
                        can_access=trial_status["can_access"],
                        read_only=trial_status["read_only"],
                    )

        return MeResponse(
            user=UserResponse(
                id=result.user_id,
                email=claims.email,
                name=claims.name,
                is_admin=result.is_admin,
            ),
            tenant=TenantResponse(
                name=None,
                seats_used=result.seats_used,
                seats_total=result.seats_total,
                plan_type=plan_type,
            ),
            trial=trial_response,
            has_seat=result.has_seat,
        )

    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        raise HTTPException(status_code=500, detail="Internal error")


@router.get("/health")
async def auth_health():
    """Health check for auth system"""
    return {
        "status": "ok",
        "auth_configured": True,  # We could check AZURE_CLIENT_ID here
    }


# Export
__all__ = ["router"]
