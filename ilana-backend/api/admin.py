"""
Admin API Routes for Ilana

Handles:
- User listing with seat status
- Seat revocation and restoration
- Dashboard data for admin portal
- 21 CFR Part 11 audit trail export
"""

import logging
import io
import csv
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, get_tenant_by_azure_id, get_user_by_azure_id, AuditEvent
from auth import TokenClaims, get_current_user
from seat_manager import (
    revoke_user_seat,
    restore_user_seat,
    get_admin_dashboard_data,
    transfer_admin,
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


class TrialResponse(BaseModel):
    """Trial status for admin dashboard"""
    status: str  # trial, expired, blocked, active
    is_trial: bool
    days_remaining: Optional[int]
    grace_days_remaining: Optional[int] = None
    ends_at: Optional[str] = None
    message: str


class DashboardResponse(BaseModel):
    """Full dashboard data"""
    tenant: dict
    subscription: SubscriptionResponse
    users: List[AdminUserResponse]
    stats: StatsResponse
    trial: Optional[TrialResponse] = None


class SeatActionResponse(BaseModel):
    """Response from seat actions (revoke/restore)"""
    success: bool
    seats_used: Optional[int] = None
    seats_total: Optional[int] = None
    user_email: Optional[str] = None
    error: Optional[str] = None


class TransferAdminResponse(BaseModel):
    """Response from admin transfer action"""
    success: bool
    previous_admin: Optional[dict] = None
    new_admin: Optional[dict] = None
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
        trial=TrialResponse(**data["trial"]) if data.get("trial") else None,
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


@router.post("/users/{user_id}/make-admin", response_model=TransferAdminResponse)
async def transfer_admin_role(
    user_id: str,
    claims: TokenClaims = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    Transfer admin role to another user (admin only)

    The current admin loses admin access after transfer.
    This is useful when the admin is leaving the organization.
    """
    result = transfer_admin(
        db=db,
        admin_tenant_id=claims.tenant_id,
        admin_user_id=claims.user_id,
        target_user_id=user_id,
    )

    if not result["success"]:
        return TransferAdminResponse(
            success=False,
            error=result.get("error", "Unknown error"),
        )

    return TransferAdminResponse(
        success=True,
        previous_admin=result.get("previous_admin"),
        new_admin=result.get("new_admin"),
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


# =============================================================================
# 21 CFR Part 11 Audit Trail Export
# =============================================================================

@router.get("/audit-trail")
async def get_audit_trail(
    start_date: Optional[datetime] = Query(None, description="Filter events from this date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="Filter events until this date (ISO format)"),
    user_email: Optional[str] = Query(None, description="Filter by user email"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    format: str = Query("json", description="Output format: json or csv"),
    limit: int = Query(10000, description="Maximum number of events to return", le=50000),
    claims: TokenClaims = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    Export audit trail for 21 CFR Part 11 compliance.

    This endpoint provides a complete audit trail of all user actions for
    regulatory compliance and inspections. Only tenant admins can access.

    Supported filters:
    - start_date: ISO datetime (e.g., 2024-01-01T00:00:00)
    - end_date: ISO datetime
    - user_email: Filter by specific user
    - event_type: Filter by event type (e.g., suggestion_accepted)

    Output formats:
    - json: JSON array of audit events
    - csv: CSV file download for spreadsheet analysis
    """
    # Get tenant
    tenant = get_tenant_by_azure_id(db, claims.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Build query
    query = db.query(AuditEvent).filter(AuditEvent.tenant_id == tenant.id)

    # Apply filters
    if start_date:
        query = query.filter(AuditEvent.created_at >= start_date)
    if end_date:
        query = query.filter(AuditEvent.created_at <= end_date)
    if user_email:
        query = query.filter(AuditEvent.user_email.ilike(f"%{user_email}%"))
    if event_type:
        query = query.filter(AuditEvent.event_type == event_type)

    # Order by most recent first and apply limit
    events = query.order_by(AuditEvent.created_at.desc()).limit(limit).all()

    # CSV export
    if format.lower() == "csv":
        output = io.StringIO()
        writer = csv.writer(output)

        # Header row
        writer.writerow([
            "Timestamp (UTC)",
            "User Email",
            "User Name",
            "Event Type",
            "Action",
            "Request ID",
            "Suggestion ID",
            "Confidence",
            "Therapeutic Area",
            "Suggestion Type",
            "Original Text Hash",
            "Improved Text Hash",
            "IP Address",
        ])

        # Data rows
        for event in events:
            writer.writerow([
                event.created_at.isoformat() if event.created_at else "",
                event.user_email or "anonymous",
                event.user_display_name or "",
                event.event_type or "",
                event.action or "",
                event.request_id or "",
                event.suggestion_id or "",
                str(event.confidence) if event.confidence is not None else "",
                event.therapeutic_area or "",
                event.suggestion_type or "",
                event.original_text_hash or "",
                event.improved_text_hash or "",
                event.ip_address or "",
            ])

        # Generate filename with date range
        filename = f"ilana_audit_trail_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    # JSON export (default)
    return {
        "audit_events": [
            {
                "id": str(event.id),
                "timestamp": event.created_at.isoformat() if event.created_at else None,
                "user_email": event.user_email,
                "user_display_name": event.user_display_name,
                "event_type": event.event_type,
                "action": event.action,
                "request_id": event.request_id,
                "suggestion_id": event.suggestion_id,
                "confidence": event.confidence,
                "therapeutic_area": event.therapeutic_area,
                "suggestion_type": event.suggestion_type,
                "original_text_hash": event.original_text_hash,
                "improved_text_hash": event.improved_text_hash,
                "ip_address": event.ip_address,
            }
            for event in events
        ],
        "total_count": len(events),
        "tenant_id": str(tenant.id),
        "tenant_name": tenant.name,
        "exported_at": datetime.utcnow().isoformat(),
        "filters": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "user_email": user_email,
            "event_type": event_type,
        }
    }


@router.get("/audit-trail/summary")
async def get_audit_trail_summary(
    claims: TokenClaims = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    Get summary statistics for the audit trail.

    Useful for compliance dashboards and quick health checks.
    """
    tenant = get_tenant_by_azure_id(db, claims.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Get total event count
    total_events = db.query(AuditEvent).filter(AuditEvent.tenant_id == tenant.id).count()

    # Get event count by type
    from sqlalchemy import func
    event_counts = (
        db.query(AuditEvent.event_type, func.count(AuditEvent.id))
        .filter(AuditEvent.tenant_id == tenant.id)
        .group_by(AuditEvent.event_type)
        .all()
    )

    # Get unique users
    unique_users = (
        db.query(AuditEvent.user_email)
        .filter(AuditEvent.tenant_id == tenant.id)
        .filter(AuditEvent.user_email.isnot(None))
        .distinct()
        .count()
    )

    # Get date range
    first_event = (
        db.query(AuditEvent)
        .filter(AuditEvent.tenant_id == tenant.id)
        .order_by(AuditEvent.created_at.asc())
        .first()
    )
    last_event = (
        db.query(AuditEvent)
        .filter(AuditEvent.tenant_id == tenant.id)
        .order_by(AuditEvent.created_at.desc())
        .first()
    )

    return {
        "total_events": total_events,
        "events_by_type": {event_type: count for event_type, count in event_counts},
        "unique_users": unique_users,
        "date_range": {
            "first_event": first_event.created_at.isoformat() if first_event else None,
            "last_event": last_event.created_at.isoformat() if last_event else None,
        },
        "tenant_id": str(tenant.id),
        "compliance_status": "21 CFR Part 11 audit trail active",
    }


# Export
__all__ = ["router"]
