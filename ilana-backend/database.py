"""
Database models and connection for Ilana Seat Management

PostgreSQL database with SQLAlchemy ORM for:
- Tenant management (Microsoft 365 organizations)
- User tracking (Azure AD users)
- Subscription management (AppSource licenses)
- Seat assignments (who occupies which seats)
"""

import os
import logging
from datetime import datetime
from typing import Optional, List, Generator
from contextlib import contextmanager

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import (
    declarative_base,
    relationship,
    sessionmaker,
    Session,
)
from sqlalchemy.sql import func
import uuid

logger = logging.getLogger(__name__)

# Database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

# SQLAlchemy setup
Base = declarative_base()
engine = None
SessionLocal = None


def init_database():
    """Initialize database connection and create tables"""
    global engine, SessionLocal

    if not DATABASE_URL:
        logger.warning("DATABASE_URL not set - database features disabled")
        return False

    try:
        # Handle Render's postgres:// vs postgresql:// URL format
        db_url = DATABASE_URL
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        engine = create_engine(
            db_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Verify connections before use
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        # Create tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False


def get_db() -> Generator[Session, None, None]:
    """Get database session - use as dependency in FastAPI"""
    if SessionLocal is None:
        raise RuntimeError("Database not initialized")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Session:
    """Context manager for database sessions"""
    if SessionLocal is None:
        raise RuntimeError("Database not initialized")
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# =============================================================================
# Models
# =============================================================================

class Tenant(Base):
    """
    Microsoft 365 tenant (organization)

    One tenant per Azure AD directory. Created automatically when
    first user from that organization signs in.
    """
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    azure_tenant_id = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    subscriptions = relationship("Subscription", back_populates="tenant")
    users = relationship("User", back_populates="tenant")

    def __repr__(self):
        return f"<Tenant {self.name or self.azure_tenant_id[:8]}>"


class Subscription(Base):
    """
    AppSource subscription for a tenant

    Tracks seat count, plan type, and trial status. Updated via AppSource webhook
    when licenses change.

    Trial Model:
    - New tenants start with 14-day trial (10 seats, full features)
    - After trial: 7-day read-only grace period
    - After grace: blocked until subscription
    - AppSource purchase sets converted_at and updates plan_type to "active"
    """
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    seat_count = Column(Integer, nullable=False, default=10)  # Trial: 10 seats
    plan_type = Column(String(50), default="trial")  # trial, active, expired, cancelled
    status = Column(String(50), default="active")  # active, cancelled, expired
    appsource_subscription_id = Column(String(255))
    stripe_customer_id = Column(String(255))  # Stripe customer ID (cus_xxx)
    stripe_subscription_id = Column(String(255))  # Stripe subscription ID (sub_xxx)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)

    # Trial tracking
    trial_started_at = Column(DateTime)  # Set on first user login
    trial_ends_at = Column(DateTime)     # trial_started_at + 14 days
    converted_at = Column(DateTime)      # When they subscribed (null = trial/expired)

    # Relationships
    tenant = relationship("Tenant", back_populates="subscriptions")
    seat_assignments = relationship("SeatAssignment", back_populates="subscription")

    def __repr__(self):
        return f"<Subscription {self.plan_type} ({self.seat_count} seats)>"


class User(Base):
    """
    User from Azure AD who has signed into the add-in

    Created on first sign-in. Tracks activity for admin portal.
    """
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    azure_user_id = Column(String(255), nullable=False)  # 'oid' from token
    email = Column(String(255))
    display_name = Column(String(255))
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    seat_assignments = relationship(
        "SeatAssignment",
        back_populates="user",
        foreign_keys="SeatAssignment.user_id"
    )

    # Composite unique constraint
    __table_args__ = (
        Index("idx_users_tenant_azure", "tenant_id", "azure_user_id", unique=True),
        Index("idx_users_last_active", "last_active_at"),
    )

    def __repr__(self):
        return f"<User {self.email or self.azure_user_id[:8]}>"


class SeatAssignment(Base):
    """
    Links users to subscription seats

    First-come-first-served: users get seats when they sign in
    if seats are available. Admins can revoke seats.
    """
    __tablename__ = "seat_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False)
    status = Column(String(50), default="active")  # active, revoked
    assigned_at = Column(DateTime, default=datetime.utcnow)
    revoked_at = Column(DateTime)
    revoked_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Relationships
    user = relationship("User", back_populates="seat_assignments", foreign_keys=[user_id])
    subscription = relationship("Subscription", back_populates="seat_assignments")
    revoker = relationship("User", foreign_keys=[revoked_by])

    __table_args__ = (
        Index("idx_seats_subscription_status", "subscription_id", "status"),
    )

    def __repr__(self):
        return f"<SeatAssignment {self.status} for user {self.user_id}>"


class PendingSubscription(Base):
    """
    Stores Stripe subscriptions before Azure AD tenant is known.

    When someone pays via Stripe on ilanaimmersive.com, we may not yet have
    their Azure AD tenant (they haven't signed in to Word Add-in yet).

    This table stores the Stripe purchase info. When they sign in via Azure AD,
    we match by email domain and migrate to an active Subscription.

    Flow:
    1. User pays via Stripe with user@acme.com
    2. Webhook creates PendingSubscription (email_domain: "acme.com")
    3. User signs in to Word Add-in with Microsoft
    4. seat_manager checks for PendingSubscription matching "acme.com"
    5. Found → Migrates to active Subscription with Stripe IDs
    """
    __tablename__ = "pending_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Stripe identifiers
    stripe_customer_id = Column(String(255), unique=True, index=True)
    stripe_subscription_id = Column(String(255), unique=True, index=True)

    # Customer info from Stripe
    customer_email = Column(String(255), index=True)
    customer_email_domain = Column(String(255), index=True)  # "acme.com"

    # Subscription details
    seat_count = Column(Integer, default=1)
    plan_type = Column(String(50), default="active")  # individual/team/team+

    # Status tracking
    status = Column(String(50), default="pending")  # pending, linked, expired
    linked_tenant_id = Column(UUID(as_uuid=True), nullable=True)
    linked_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_pending_domain_status", "customer_email_domain", "status"),
    )

    def __repr__(self):
        return f"<PendingSubscription {self.customer_email} ({self.status})>"


class AuditEvent(Base):
    """
    21 CFR Part 11 compliant audit trail

    Stores ALL user actions with full attribution for regulatory compliance.
    Records are NEVER deleted (Part 11 requirement).

    Event types:
    - analysis_requested: User initiated protocol analysis
    - suggestions_returned: Backend returned AI suggestions
    - suggestion_shown: User viewed a specific suggestion
    - suggestion_inserted_as_comment: Inserted as Word comment
    - suggestion_accepted: User applied suggestion (replaced text)
    - suggestion_undone: User undid an applied suggestion
    - suggestion_dismissed: User dismissed a suggestion
    - comment_resolved: User resolved a Word comment
    """
    __tablename__ = "audit_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # User attribution (stored in plain text for Part 11 compliance)
    user_email = Column(String(255))
    user_display_name = Column(String(255))

    # Event details
    event_type = Column(String(100), nullable=False)
    action = Column(String(100))  # apply, dismiss, insert_comment, undo, resolve_comment

    # Content hashes (not actual content - privacy protection)
    original_text_hash = Column(String(64))
    improved_text_hash = Column(String(64))

    # Metadata
    request_id = Column(String(100))
    suggestion_id = Column(String(100))
    confidence = Column(Float)
    therapeutic_area = Column(String(100))
    suggestion_type = Column(String(100))
    comment_id = Column(String(100))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Client info for attribution
    ip_address = Column(String(50))
    user_agent = Column(String(500))

    # Relationships (optional - for joins)
    tenant = relationship("Tenant", foreign_keys=[tenant_id])
    user = relationship("User", foreign_keys=[user_id])

    # Indexes for query performance
    __table_args__ = (
        Index("idx_audit_tenant_created", "tenant_id", "created_at"),
        Index("idx_audit_user_created", "user_id", "created_at"),
        Index("idx_audit_event_type", "event_type"),
        Index("idx_audit_request_id", "request_id"),
    )

    def __repr__(self):
        return f"<AuditEvent {self.event_type} by {self.user_email or 'anonymous'}>"


# =============================================================================
# Query Helpers
# =============================================================================

def get_tenant_by_azure_id(db: Session, azure_tenant_id: str) -> Optional[Tenant]:
    """Get tenant by Azure AD tenant ID"""
    return db.query(Tenant).filter(Tenant.azure_tenant_id == azure_tenant_id).first()


def get_user_by_azure_id(
    db: Session,
    tenant_id: uuid.UUID,
    azure_user_id: str
) -> Optional[User]:
    """Get user by Azure AD user ID within a tenant"""
    return db.query(User).filter(
        User.tenant_id == tenant_id,
        User.azure_user_id == azure_user_id
    ).first()


def get_active_subscription(db: Session, tenant_id: uuid.UUID) -> Optional[Subscription]:
    """Get the active subscription for a tenant"""
    return db.query(Subscription).filter(
        Subscription.tenant_id == tenant_id,
        Subscription.status == "active"
    ).first()


def get_active_seat_assignment(
    db: Session,
    user_id: uuid.UUID,
    subscription_id: uuid.UUID
) -> Optional[SeatAssignment]:
    """Get active seat assignment for a user"""
    return db.query(SeatAssignment).filter(
        SeatAssignment.user_id == user_id,
        SeatAssignment.subscription_id == subscription_id,
        SeatAssignment.status == "active"
    ).first()


def count_active_seats(db: Session, subscription_id: uuid.UUID) -> int:
    """Count active seat assignments for a subscription"""
    return db.query(SeatAssignment).filter(
        SeatAssignment.subscription_id == subscription_id,
        SeatAssignment.status == "active"
    ).count()


def get_users_with_seats(
    db: Session,
    tenant_id: uuid.UUID
) -> List[dict]:
    """Get all users with their seat status for admin portal"""
    subscription = get_active_subscription(db, tenant_id)
    if not subscription:
        return []

    users = db.query(User).filter(User.tenant_id == tenant_id).all()

    result = []
    for user in users:
        seat = get_active_seat_assignment(db, user.id, subscription.id)
        result.append({
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "is_admin": user.is_admin,
            "last_active_at": user.last_active_at.isoformat() if user.last_active_at else None,
            "has_seat": seat is not None,
            "seat_assigned_at": seat.assigned_at.isoformat() if seat else None,
        })

    return result


# Export
__all__ = [
    "init_database",
    "get_db",
    "get_db_session",
    "Base",
    "Tenant",
    "Subscription",
    "User",
    "SeatAssignment",
    "PendingSubscription",
    "AuditEvent",
    "get_tenant_by_azure_id",
    "get_user_by_azure_id",
    "get_active_subscription",
    "get_active_seat_assignment",
    "count_active_seats",
    "get_users_with_seats",
]
