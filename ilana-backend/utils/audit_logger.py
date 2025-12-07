"""
Audit Logger for SOC 2 Compliance

Provides structured security event logging for:
- Authentication events (success/failure)
- Authorization decisions
- Data access events
- Administrative actions
- Security events (rate limiting, invalid tokens)

Logs are structured in JSON format for SIEM ingestion.
"""

import logging
import json
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class AuditEventType(Enum):
    """Categories of audit events"""
    # Authentication
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILURE = "auth.failure"
    AUTH_TOKEN_EXPIRED = "auth.token_expired"
    AUTH_TOKEN_INVALID = "auth.token_invalid"

    # Authorization
    AUTHZ_GRANTED = "authz.granted"
    AUTHZ_DENIED = "authz.denied"

    # Seat Management
    SEAT_ASSIGNED = "seat.assigned"
    SEAT_REVOKED = "seat.revoked"
    SEAT_DENIED = "seat.denied"

    # Data Access
    DATA_ACCESS = "data.access"
    DATA_ANALYSIS = "data.analysis"

    # Administrative
    ADMIN_ACTION = "admin.action"
    ADMIN_USER_LIST = "admin.user_list"
    ADMIN_SEAT_REVOKE = "admin.seat_revoke"
    ADMIN_SEAT_RESTORE = "admin.seat_restore"

    # Security
    SECURITY_RATE_LIMIT = "security.rate_limit"
    SECURITY_INVALID_REQUEST = "security.invalid_request"
    SECURITY_SUSPICIOUS = "security.suspicious"

    # System
    SYSTEM_ERROR = "system.error"
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"


class AuditLogger:
    """
    Structured audit logger for security events.

    All events are logged in JSON format with consistent fields
    for easy parsing and SIEM integration.
    """

    def __init__(self, name: str = "ilana.audit"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

        # Ensure we have a handler
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(handler)

    def _hash_pii(self, value: Optional[str]) -> Optional[str]:
        """Hash PII values for logging (one-way, for correlation only)"""
        if not value:
            return None
        return hashlib.sha256(value.encode()).hexdigest()[:16]

    def _create_event(
        self,
        event_type: AuditEventType,
        success: bool,
        details: Dict[str, Any],
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
        resource: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a structured audit event"""
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type.value,
            "success": success,
            "user_id_hash": self._hash_pii(user_id),
            "tenant_id": tenant_id,
            "ip_address": ip_address,
            "request_id": request_id,
            "resource": resource,
            "details": details,
            "service": "ilana-backend",
            "version": "1.0"
        }

    def log_event(
        self,
        event_type: AuditEventType,
        success: bool,
        details: Dict[str, Any],
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
        resource: Optional[str] = None
    ):
        """Log an audit event"""
        event = self._create_event(
            event_type=event_type,
            success=success,
            details=details,
            user_id=user_id,
            tenant_id=tenant_id,
            ip_address=ip_address,
            request_id=request_id,
            resource=resource
        )

        # Log as JSON for structured logging
        self.logger.info(json.dumps(event))

    # Convenience methods for common events

    def auth_success(
        self,
        user_id: str,
        tenant_id: str,
        ip_address: str,
        request_id: Optional[str] = None,
        method: str = "sso"
    ):
        """Log successful authentication"""
        self.log_event(
            event_type=AuditEventType.AUTH_SUCCESS,
            success=True,
            details={"method": method},
            user_id=user_id,
            tenant_id=tenant_id,
            ip_address=ip_address,
            request_id=request_id,
            resource="/api/auth/validate"
        )

    def auth_failure(
        self,
        ip_address: str,
        reason: str,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """Log failed authentication"""
        self.log_event(
            event_type=AuditEventType.AUTH_FAILURE,
            success=False,
            details={"reason": reason},
            user_id=user_id,
            ip_address=ip_address,
            request_id=request_id,
            resource="/api/auth/validate"
        )

    def seat_assigned(
        self,
        user_id: str,
        tenant_id: str,
        ip_address: str,
        seat_id: Optional[str] = None
    ):
        """Log seat assignment"""
        self.log_event(
            event_type=AuditEventType.SEAT_ASSIGNED,
            success=True,
            details={"seat_id": seat_id},
            user_id=user_id,
            tenant_id=tenant_id,
            ip_address=ip_address
        )

    def seat_denied(
        self,
        user_id: str,
        tenant_id: str,
        ip_address: str,
        reason: str
    ):
        """Log seat denial"""
        self.log_event(
            event_type=AuditEventType.SEAT_DENIED,
            success=False,
            details={"reason": reason},
            user_id=user_id,
            tenant_id=tenant_id,
            ip_address=ip_address
        )

    def admin_action(
        self,
        admin_user_id: str,
        tenant_id: str,
        action: str,
        target_user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log administrative action"""
        self.log_event(
            event_type=AuditEventType.ADMIN_ACTION,
            success=True,
            details={
                "action": action,
                "target_user_hash": self._hash_pii(target_user_id),
                **(details or {})
            },
            user_id=admin_user_id,
            tenant_id=tenant_id,
            ip_address=ip_address
        )

    def data_analysis(
        self,
        user_id: str,
        tenant_id: str,
        ip_address: str,
        text_length: int,
        request_id: Optional[str] = None
    ):
        """Log protocol analysis request (without storing content)"""
        self.log_event(
            event_type=AuditEventType.DATA_ANALYSIS,
            success=True,
            details={
                "text_length": text_length,
                "analysis_type": "protocol"
            },
            user_id=user_id,
            tenant_id=tenant_id,
            ip_address=ip_address,
            request_id=request_id,
            resource="/api/analyze"
        )

    def rate_limit_exceeded(
        self,
        ip_address: str,
        endpoint: str,
        limit: str
    ):
        """Log rate limit exceeded event"""
        self.log_event(
            event_type=AuditEventType.SECURITY_RATE_LIMIT,
            success=False,
            details={
                "endpoint": endpoint,
                "limit": limit
            },
            ip_address=ip_address,
            resource=endpoint
        )

    def security_event(
        self,
        event_subtype: str,
        ip_address: str,
        details: Dict[str, Any],
        user_id: Optional[str] = None
    ):
        """Log general security event"""
        self.log_event(
            event_type=AuditEventType.SECURITY_SUSPICIOUS,
            success=False,
            details={"subtype": event_subtype, **details},
            user_id=user_id,
            ip_address=ip_address
        )


# Global audit logger instance
audit_logger = AuditLogger()


# Helper function to get client IP from request
def get_client_ip(request) -> str:
    """Extract client IP from request, handling proxies"""
    # Check for forwarded headers (from reverse proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP in the chain (original client)
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct connection IP
    if hasattr(request, "client") and request.client:
        return request.client.host

    return "unknown"
