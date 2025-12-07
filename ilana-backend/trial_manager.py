"""
Trial Management for Ilana

Handles 14-day trial logic:
- Trial status checking
- Grace period handling
- Conversion tracking

Trial States:
- trial: Active trial, full features (14 days)
- expired: Trial ended, read-only grace period (7 days)
- blocked: Grace period ended, no access
- active: Paid subscription (converted)
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from database import Subscription

logger = logging.getLogger(__name__)

# Configuration (can be overridden via environment variables)
TRIAL_DURATION_DAYS = int(os.getenv("TRIAL_DURATION_DAYS", "14"))
GRACE_PERIOD_DAYS = int(os.getenv("TRIAL_GRACE_PERIOD_DAYS", "7"))
TRIAL_SEAT_COUNT = int(os.getenv("TRIAL_SEAT_COUNT", "10"))


def get_trial_status(subscription: Subscription) -> Dict[str, Any]:
    """
    Get the current trial status for a subscription.

    Returns:
        dict with keys:
        - status: 'trial', 'expired', 'blocked', or 'active'
        - is_trial: True if in trial/expired state, False if paid
        - days_remaining: Days left in trial (negative if expired)
        - can_access: True if user can use the add-in
        - read_only: True if in grace period (can view but not analyze)
        - grace_days_remaining: Days left in grace period (if expired)
        - trial_ends_at: Trial end date (ISO string)
        - message: User-friendly status message
    """
    now = datetime.utcnow()

    # Already converted to paid subscription
    if subscription.converted_at:
        return {
            "status": "active",
            "is_trial": False,
            "days_remaining": None,
            "can_access": True,
            "read_only": False,
            "grace_days_remaining": None,
            "trial_ends_at": None,
            "message": "Active subscription",
        }

    # Check trial dates
    trial_ends = subscription.trial_ends_at

    if not trial_ends:
        # No trial info - shouldn't happen, but treat as new trial
        logger.warning(f"Subscription {subscription.id} missing trial_ends_at")
        return {
            "status": "trial",
            "is_trial": True,
            "days_remaining": TRIAL_DURATION_DAYS,
            "can_access": True,
            "read_only": False,
            "grace_days_remaining": None,
            "trial_ends_at": None,
            "message": f"{TRIAL_DURATION_DAYS} days remaining in trial",
        }

    # Active trial
    if now < trial_ends:
        days_left = (trial_ends - now).days + 1  # +1 to include current day
        return {
            "status": "trial",
            "is_trial": True,
            "days_remaining": days_left,
            "can_access": True,
            "read_only": False,
            "grace_days_remaining": None,
            "trial_ends_at": trial_ends.isoformat(),
            "message": f"{days_left} days remaining in trial",
        }

    # Trial expired - check grace period
    grace_ends = trial_ends + timedelta(days=GRACE_PERIOD_DAYS)

    if now < grace_ends:
        # In grace period - read only
        days_expired = (now - trial_ends).days
        grace_days_left = (grace_ends - now).days + 1

        return {
            "status": "expired",
            "is_trial": True,
            "days_remaining": -days_expired,  # Negative = days since expiry
            "can_access": True,
            "read_only": True,
            "grace_days_remaining": grace_days_left,
            "trial_ends_at": trial_ends.isoformat(),
            "message": f"Trial expired. {grace_days_left} days to subscribe before access is blocked.",
        }

    # Fully expired - blocked
    return {
        "status": "blocked",
        "is_trial": True,
        "days_remaining": None,
        "can_access": False,
        "read_only": False,
        "grace_days_remaining": 0,
        "trial_ends_at": trial_ends.isoformat(),
        "message": "Trial and grace period have ended. Subscribe to continue using Ilana.",
    }


def is_trial_active(subscription: Subscription) -> bool:
    """Quick check if trial is still active (not expired)."""
    status = get_trial_status(subscription)
    return status["status"] == "trial"


def can_access(subscription: Subscription) -> bool:
    """Check if user can access the add-in (trial, grace, or paid)."""
    status = get_trial_status(subscription)
    return status["can_access"]


def is_read_only(subscription: Subscription) -> bool:
    """Check if user is in read-only grace period."""
    status = get_trial_status(subscription)
    return status["read_only"]


def get_days_remaining(subscription: Subscription) -> Optional[int]:
    """Get days remaining in trial (None if paid or blocked)."""
    status = get_trial_status(subscription)
    return status["days_remaining"]


def calculate_trial_end_date(start_date: Optional[datetime] = None) -> datetime:
    """Calculate when a trial should end given a start date."""
    if start_date is None:
        start_date = datetime.utcnow()
    return start_date + timedelta(days=TRIAL_DURATION_DAYS)


# Export
__all__ = [
    "get_trial_status",
    "is_trial_active",
    "can_access",
    "is_read_only",
    "get_days_remaining",
    "calculate_trial_end_date",
    "TRIAL_DURATION_DAYS",
    "GRACE_PERIOD_DAYS",
    "TRIAL_SEAT_COUNT",
]
