"""
Authentication API Routes for Ilana

Handles:
- Token validation and seat assignment
- User info retrieval
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from auth import TokenClaims, get_current_user, get_optional_user
from seat_manager import validate_and_assign_seat, SeatValidationResult

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


class ValidateResponse(BaseModel):
    """Response from /api/auth/validate"""
    status: str  # 'ok', 'no_seats', 'revoked', 'new_seat'
    user: Optional[UserResponse]
    tenant: Optional[TenantResponse]
    message: Optional[str] = None


class MeResponse(BaseModel):
    """Response from /api/auth/me"""
    user: UserResponse
    tenant: TenantResponse
    has_seat: bool


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/validate", response_model=ValidateResponse)
async def validate_token_and_seat(
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
                ),
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
                ) if result.tenant_id else None,
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
            ),
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
