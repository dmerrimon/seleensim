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
    Text,
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
    B2B subscription for a tenant

    Tracks seat count, plan type, and trial status.

    Plan Types:
    - trial: 14-day free trial
    - corporate: Universities, Non-Profits ($75/user/mo, $750/user/yr)
    - enterprise: Pharma, CRO, Biotech ($149/user/mo, $1,490/user/yr)
    - expired: Trial or subscription ended

    Trial Model:
    - All signups get 14-day free trial (min 5 users)
    - After trial: show conversion page with card/invoice/demo options
    - After conversion: seats active immediately (card) or after payment (invoice)
    """
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    seat_count = Column(Integer, nullable=False, default=5)  # Minimum 5 users for B2B
    plan_type = Column(String(50), default="trial")  # trial, corporate, enterprise, expired
    status = Column(String(50), default="active")  # active, cancelled, expired
    appsource_subscription_id = Column(String(255))
    stripe_customer_id = Column(String(255))  # Stripe customer ID (cus_xxx)
    stripe_subscription_id = Column(String(255))  # Stripe subscription ID (sub_xxx)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)

    # Organization type for pricing
    org_type = Column(String(50))  # pharmaceutical, cro, biotech, university, nonprofit
    email_domain = Column(String(255))  # Primary email domain (e.g., pfizer.com)
    detected_plan = Column(String(50))  # corporate or enterprise (auto-detected from email)
    is_verified = Column(Boolean, default=False)  # Admin verified org type
    needs_review = Column(Boolean, default=False)  # Flagged for manual review (mismatch)

    # Trial tracking
    trial_started_at = Column(DateTime)  # Set on first user login
    trial_ends_at = Column(DateTime)     # trial_started_at + 14 days
    converted_at = Column(DateTime)      # When they subscribed (null = trial/expired)

    # Enterprise billing fields
    collection_method = Column(String(50), default="charge_automatically")  # charge_automatically, send_invoice
    billing_interval = Column(String(20), default="month")  # month, year
    payment_status = Column(String(50), default="paid")  # paid, pending_payment, overdue

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
    is_super_admin = Column(Boolean, default=False)  # Cross-tenant admin access
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


class PendingTrial(Base):
    """
    Trial signup from ilanaimmersive.com/trial before Azure AD login.

    When someone fills out the trial signup form on the marketing site,
    we create a PendingTrial with their org details. When they sign in
    via Azure AD for the first time, we match by email domain and convert
    to an active Subscription.

    Flow:
    1. User fills out trial form on ilanaimmersive.com/trial
    2. PendingTrial created with org details, auto-detected plan
    3. Welcome email sent with instructions to sign in via Word Add-in
    4. User signs into Word Add-in via Azure AD SSO
    5. seat_manager matches email domain to PendingTrial
    6. Creates Tenant + Subscription (trial), links PendingTrial
    7. After 14 days, user sees conversion page with payment options
    """
    __tablename__ = "pending_trials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Organization details
    org_name = Column(String(255), nullable=False)
    org_type = Column(String(50), nullable=False)  # pharmaceutical, cro, biotech, university, nonprofit

    # Contact info
    contact_name = Column(String(255), nullable=False)
    contact_email = Column(String(255), nullable=False, index=True)
    contact_title = Column(String(255))
    contact_phone = Column(String(50))
    email_domain = Column(String(255), index=True)  # extracted from email for matching

    # Plan determination (auto-detected from email domain)
    # .edu or .org → corporate ($75/user), otherwise → enterprise ($149/user)
    detected_plan = Column(String(50))  # corporate or enterprise
    requested_seats = Column(Integer, default=5)  # minimum 5 users

    # Status tracking
    status = Column(String(50), default="pending")  # pending, activated, expired, converted

    # Linking to tenant when user signs in
    linked_tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True)
    linked_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # created_at + 14 days
    converted_at = Column(DateTime)  # when they paid

    # Referral tracking (for AppSource and other traffic sources)
    referral_source = Column(String(50))  # 'appsource', 'google', 'direct', etc.
    team_size_selection = Column(String(50))  # 'individual', 'team', 'department' (qualification step)
    utm_source = Column(String(255))
    utm_medium = Column(String(255))
    utm_campaign = Column(String(255))

    # Relationships
    linked_tenant = relationship("Tenant", foreign_keys=[linked_tenant_id])

    # Indexes
    __table_args__ = (
        Index("idx_pending_trials_domain_status", "email_domain", "status"),
        Index("idx_pending_trials_email", "contact_email"),
    )

    def __repr__(self):
        return f"<PendingTrial {self.org_name} ({self.status})>"


class InvoiceRequest(Base):
    """
    Invoice request from customers who can't pay with credit card.

    When a user requests an invoice instead of paying via Stripe Checkout,
    we create this record and notify the ops team. The ops team then
    creates an invoice in Stripe and sends it to the customer.

    Status flow:
    1. pending → Created, waiting for ops to review
    2. invoice_sent → Stripe invoice created and sent
    3. paid → Invoice paid, subscription activated
    4. cancelled → Request cancelled
    """
    __tablename__ = "invoice_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Tenant info
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=True)
    requested_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Plan details
    plan_type = Column(String(50), nullable=False)  # corporate or enterprise
    billing_interval = Column(String(20), nullable=False)  # month or year
    seat_count = Column(Integer, nullable=False)
    amount_cents = Column(Integer, nullable=False)  # total amount in cents

    # Billing contact
    billing_contact_name = Column(String(255), nullable=False)
    billing_contact_email = Column(String(255), nullable=False)
    po_number = Column(String(100))  # optional purchase order number

    # Billing address
    billing_address = Column(Text, nullable=False)  # street address (multi-line)
    billing_city = Column(String(100), nullable=False)
    billing_state = Column(String(100), nullable=False)
    billing_zip = Column(String(20), nullable=False)
    billing_country = Column(String(100), nullable=False, default="United States")

    # Payment terms
    payment_terms = Column(String(20), nullable=False, default="net_30")  # net_30, net_60

    # Additional notes
    notes = Column(Text)

    # Status tracking
    status = Column(String(50), nullable=False, default="pending")
    # pending, invoice_sent, paid, cancelled

    # Stripe references (filled when invoice is created)
    stripe_invoice_id = Column(String(255))
    stripe_invoice_url = Column(String(500))

    # Processing notes (from ops team)
    ops_notes = Column(Text)
    processed_by = Column(String(255))  # email of ops team member

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    invoice_sent_at = Column(DateTime)
    paid_at = Column(DateTime)
    cancelled_at = Column(DateTime)

    # Relationships
    tenant = relationship("Tenant", foreign_keys=[tenant_id])
    subscription = relationship("Subscription", foreign_keys=[subscription_id])
    requested_by = relationship("User", foreign_keys=[requested_by_user_id])

    # Indexes
    __table_args__ = (
        Index("idx_invoice_requests_tenant", "tenant_id"),
        Index("idx_invoice_requests_status", "status"),
        Index("idx_invoice_requests_created", "created_at"),
    )

    def __repr__(self):
        return f"<InvoiceRequest {self.id} ({self.status})>"


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
    "PendingTrial",
    "AuditEvent",
    "get_tenant_by_azure_id",
    "get_user_by_azure_id",
    "get_active_subscription",
    "get_active_seat_assignment",
    "count_active_seats",
    "get_users_with_seats",
]
