"""
Trial Signup API

Public endpoints for B2B trial signups from ilanaimmersive.com/trial.
No authentication required - this is for new prospects.

Flow:
1. Prospect fills out trial form on marketing site
2. POST /api/trial/signup creates PendingTrial
3. Auto-detect plan based on email domain:
   - .edu or .org → Corporate ($75/user)
   - All others → Enterprise ($149/user)
4. Send welcome email with login instructions
5. Prospect signs into Word Add-in via Azure AD SSO
6. seat_manager matches email domain to PendingTrial
"""

import os
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, validator, field_validator
from sqlalchemy.orm import Session

from database import get_db, get_db_session, PendingTrial

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trial", tags=["trial"])


# =============================================================================
# Constants
# =============================================================================

TRIAL_DURATION_DAYS = 14
MIN_SEATS = 5
MAX_SEATS = 100

VALID_ORG_TYPES = [
    "pharmaceutical",
    "cro",
    "biotech",
    "university",
    "nonprofit",
]

# Domains that qualify for corporate pricing
CORPORATE_TLDS = [".edu", ".org"]


# =============================================================================
# Request/Response Models
# =============================================================================

class TrialSignupRequest(BaseModel):
    """Request body for trial signup form"""
    org_name: str
    org_type: str
    requested_seats: int
    contact_name: str
    contact_email: str
    contact_title: Optional[str] = None
    contact_phone: Optional[str] = None
    terms_accepted: bool

    # Referral tracking (for AppSource and other traffic sources)
    referral_source: Optional[str] = None  # 'appsource', 'google', 'direct', etc.
    team_size_selection: Optional[str] = None  # 'individual', 'team', 'department'
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None

    @validator("contact_email")
    def validate_email(cls, v):
        """Validate email format without requiring email-validator package."""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()

    @validator("org_type")
    def validate_org_type(cls, v):
        if v.lower() not in VALID_ORG_TYPES:
            raise ValueError(f"org_type must be one of: {', '.join(VALID_ORG_TYPES)}")
        return v.lower()

    @validator("requested_seats")
    def validate_seats(cls, v):
        if v < MIN_SEATS:
            raise ValueError(f"Minimum {MIN_SEATS} seats required")
        if v > MAX_SEATS:
            raise ValueError(f"Maximum {MAX_SEATS} seats. Contact sales for larger teams.")
        return v

    @validator("terms_accepted")
    def validate_terms(cls, v):
        if not v:
            raise ValueError("You must accept the terms and conditions")
        return v


class TrialSignupResponse(BaseModel):
    """Response after successful trial signup"""
    success: bool
    trial_id: str
    detected_plan: str  # "corporate" or "enterprise"
    pricing: dict  # {"monthly": "$X/user", "annual": "$X/user"}
    expires_at: str
    message: str


class TrialStatusResponse(BaseModel):
    """Response for trial status check"""
    exists: bool
    trial_id: Optional[str] = None
    org_name: Optional[str] = None
    status: Optional[str] = None
    detected_plan: Optional[str] = None
    requested_seats: Optional[int] = None
    expires_at: Optional[str] = None
    days_remaining: Optional[int] = None


class PendingTrialInfo(BaseModel):
    """Info about a pending trial for ops portal"""
    id: str
    org_name: str
    org_type: str
    contact_name: str
    contact_email: str
    contact_title: Optional[str]
    contact_phone: Optional[str]
    email_domain: str
    detected_plan: str
    requested_seats: int
    status: str
    created_at: str
    expires_at: str
    days_remaining: int


class PendingTrialsListResponse(BaseModel):
    """Response for listing pending trials"""
    trials: List[PendingTrialInfo]
    total: int


# =============================================================================
# Helper Functions
# =============================================================================

def detect_plan_from_email(email: str) -> str:
    """
    Determine plan type based on email domain.

    .edu and .org → Corporate ($75/user/mo)
    All others → Enterprise ($149/user/mo)
    """
    domain = email.lower().split("@")[1] if "@" in email else ""

    for tld in CORPORATE_TLDS:
        if domain.endswith(tld):
            return "corporate"

    return "enterprise"


def get_pricing_for_plan(plan: str) -> dict:
    """Get pricing details for a plan."""
    if plan == "corporate":
        return {
            "monthly": "$75/user/mo",
            "annual": "$750/user/yr",
            "monthly_amount": 75,
            "annual_amount": 750,
        }
    else:  # enterprise
        return {
            "monthly": "$149/user/mo",
            "annual": "$1,490/user/yr",
            "monthly_amount": 149,
            "annual_amount": 1490,
        }


def extract_email_domain(email: str) -> str:
    """Extract domain from email address."""
    if "@" not in email:
        raise ValueError("Invalid email format")
    return email.lower().split("@")[1]


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/signup", response_model=TrialSignupResponse)
async def create_trial(
    request: TrialSignupRequest,
    db: Session = Depends(get_db),
):
    """
    Create a new trial signup.

    Called from ilanaimmersive.com/trial form.
    No authentication required.

    Auto-detects plan based on email domain:
    - .edu or .org → Corporate ($75/user)
    - All others → Enterprise ($149/user)

    Creates PendingTrial record and sends welcome email.
    """
    # Extract email domain
    try:
        email_domain = extract_email_domain(request.contact_email)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid email format")

    # Check for existing pending trial with same email
    existing = db.query(PendingTrial).filter(
        PendingTrial.contact_email == request.contact_email.lower(),
        PendingTrial.status.in_(["pending", "activated"]),
    ).first()

    if existing:
        # Return existing trial info instead of creating duplicate
        pricing = get_pricing_for_plan(existing.detected_plan)
        return TrialSignupResponse(
            success=True,
            trial_id=str(existing.id),
            detected_plan=existing.detected_plan,
            pricing=pricing,
            expires_at=existing.expires_at.isoformat() if existing.expires_at else "",
            message=f"You already have an active trial. Check your email ({request.contact_email}) for login instructions.",
        )

    # Auto-detect plan based on email domain
    detected_plan = detect_plan_from_email(request.contact_email)
    pricing = get_pricing_for_plan(detected_plan)

    # Calculate expiration
    now = datetime.utcnow()
    expires_at = now + timedelta(days=TRIAL_DURATION_DAYS)

    # Create pending trial
    trial = PendingTrial(
        org_name=request.org_name,
        org_type=request.org_type,
        contact_name=request.contact_name,
        contact_email=request.contact_email.lower(),
        contact_title=request.contact_title,
        contact_phone=request.contact_phone,
        email_domain=email_domain,
        detected_plan=detected_plan,
        requested_seats=request.requested_seats,
        status="pending",
        created_at=now,
        expires_at=expires_at,
        # Referral tracking
        referral_source=request.referral_source,
        team_size_selection=request.team_size_selection,
        utm_source=request.utm_source,
        utm_medium=request.utm_medium,
        utm_campaign=request.utm_campaign,
    )

    db.add(trial)
    db.commit()
    db.refresh(trial)

    logger.info(
        f"Trial signup created: {request.org_name} ({request.org_type}), "
        f"{request.requested_seats} seats, plan={detected_plan}, email={request.contact_email}, "
        f"source={request.referral_source or 'direct'}"
    )

    # TODO: Send welcome email with login instructions
    # await send_welcome_email(trial)

    plan_name = "Corporate" if detected_plan == "corporate" else "Enterprise"

    return TrialSignupResponse(
        success=True,
        trial_id=str(trial.id),
        detected_plan=detected_plan,
        pricing=pricing,
        expires_at=expires_at.isoformat(),
        message=f"Welcome to Ilana! Your {TRIAL_DURATION_DAYS}-day {plan_name} trial for {request.requested_seats} users is ready. Check your email for login instructions.",
    )


@router.get("/status", response_model=TrialStatusResponse)
async def check_trial_status(
    email: str = Query(..., description="Email to check for existing trial"),
    db: Session = Depends(get_db),
):
    """
    Check if a trial exists for an email address.

    Used by marketing site to show appropriate messaging.
    """
    email_lower = email.lower()

    trial = db.query(PendingTrial).filter(
        PendingTrial.contact_email == email_lower,
    ).order_by(PendingTrial.created_at.desc()).first()

    if not trial:
        return TrialStatusResponse(exists=False)

    now = datetime.utcnow()
    days_remaining = 0
    if trial.expires_at and trial.expires_at > now:
        days_remaining = (trial.expires_at - now).days

    return TrialStatusResponse(
        exists=True,
        trial_id=str(trial.id),
        org_name=trial.org_name,
        status=trial.status,
        detected_plan=trial.detected_plan,
        requested_seats=trial.requested_seats,
        expires_at=trial.expires_at.isoformat() if trial.expires_at else None,
        days_remaining=days_remaining,
    )


@router.get("/by-domain/{domain}", response_model=TrialStatusResponse)
async def get_trial_by_domain(
    domain: str,
    db: Session = Depends(get_db),
):
    """
    Get pending trial by email domain.

    Used by seat_manager to match Azure AD logins to trials.
    Internal endpoint - should be called from backend only.
    """
    trial = db.query(PendingTrial).filter(
        PendingTrial.email_domain == domain.lower(),
        PendingTrial.status == "pending",
    ).order_by(PendingTrial.created_at.desc()).first()

    if not trial:
        return TrialStatusResponse(exists=False)

    now = datetime.utcnow()
    days_remaining = 0
    if trial.expires_at and trial.expires_at > now:
        days_remaining = (trial.expires_at - now).days

    return TrialStatusResponse(
        exists=True,
        trial_id=str(trial.id),
        org_name=trial.org_name,
        status=trial.status,
        detected_plan=trial.detected_plan,
        requested_seats=trial.requested_seats,
        expires_at=trial.expires_at.isoformat() if trial.expires_at else None,
        days_remaining=days_remaining,
    )


# =============================================================================
# Ops Portal Endpoints (requires super admin auth)
# =============================================================================

@router.get("/list", response_model=PendingTrialsListResponse)
async def list_pending_trials(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    List all pending trials for ops portal.

    TODO: Add super admin authentication
    """
    query = db.query(PendingTrial)

    if status:
        query = query.filter(PendingTrial.status == status)

    total = query.count()
    trials = query.order_by(PendingTrial.created_at.desc()).offset(offset).limit(limit).all()

    now = datetime.utcnow()
    trial_list = []
    for t in trials:
        days_remaining = 0
        if t.expires_at and t.expires_at > now:
            days_remaining = (t.expires_at - now).days

        trial_list.append(PendingTrialInfo(
            id=str(t.id),
            org_name=t.org_name,
            org_type=t.org_type,
            contact_name=t.contact_name,
            contact_email=t.contact_email,
            contact_title=t.contact_title,
            contact_phone=t.contact_phone,
            email_domain=t.email_domain,
            detected_plan=t.detected_plan,
            requested_seats=t.requested_seats,
            status=t.status,
            created_at=t.created_at.isoformat() if t.created_at else "",
            expires_at=t.expires_at.isoformat() if t.expires_at else "",
            days_remaining=days_remaining,
        ))

    return PendingTrialsListResponse(trials=trial_list, total=total)


@router.post("/{trial_id}/extend")
async def extend_trial(
    trial_id: str,
    days: int = Query(7, ge=1, le=30, description="Days to extend"),
    db: Session = Depends(get_db),
):
    """
    Extend a trial's expiration date.

    TODO: Add super admin authentication
    """
    trial = db.query(PendingTrial).filter(PendingTrial.id == trial_id).first()
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")

    old_expires = trial.expires_at
    trial.expires_at = trial.expires_at + timedelta(days=days)
    db.commit()

    logger.info(f"Trial {trial_id} extended by {days} days: {old_expires} -> {trial.expires_at}")

    return {
        "success": True,
        "trial_id": trial_id,
        "new_expires_at": trial.expires_at.isoformat(),
    }


@router.post("/{trial_id}/override-plan")
async def override_trial_plan(
    trial_id: str,
    new_plan: str = Query(..., description="New plan: 'corporate' or 'enterprise'"),
    db: Session = Depends(get_db),
):
    """
    Override the auto-detected plan for a trial.

    Used when a company uses a .com email but qualifies for corporate pricing.

    TODO: Add super admin authentication
    """
    if new_plan not in ["corporate", "enterprise"]:
        raise HTTPException(status_code=400, detail="Plan must be 'corporate' or 'enterprise'")

    trial = db.query(PendingTrial).filter(PendingTrial.id == trial_id).first()
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")

    old_plan = trial.detected_plan
    trial.detected_plan = new_plan
    db.commit()

    logger.info(f"Trial {trial_id} plan overridden: {old_plan} -> {new_plan}")

    return {
        "success": True,
        "trial_id": trial_id,
        "old_plan": old_plan,
        "new_plan": new_plan,
    }


# =============================================================================
# Health Check
# =============================================================================

@router.get("/health")
async def trial_health():
    """Health check for trial endpoints"""
    return {
        "status": "ok",
        "trial_duration_days": TRIAL_DURATION_DAYS,
        "min_seats": MIN_SEATS,
        "max_seats": MAX_SEATS,
    }


# Export
__all__ = ["router"]
