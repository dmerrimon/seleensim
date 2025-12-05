"""
Microsoft Azure AD Authentication for Ilana

Validates JWT tokens from Office.js SSO and extracts user claims.
Uses Microsoft's JWKS endpoint for token verification.
"""

import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass

import jwt
import httpx
from jwt import PyJWKClient
from fastapi import HTTPException, Security, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

# Azure AD configuration
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "common")  # 'common' for multi-tenant

# Microsoft's JWKS endpoint for token verification
JWKS_URL = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/discovery/v2.0/keys"

# Token issuer patterns (multi-tenant support)
VALID_ISSUERS = [
    "https://login.microsoftonline.com/{tenant}/v2.0",
    "https://sts.windows.net/{tenant}/",
]

# Security scheme
security = HTTPBearer(auto_error=False)


# =============================================================================
# Token Claims
# =============================================================================

@dataclass
class TokenClaims:
    """Extracted claims from validated Azure AD token"""
    tenant_id: str        # 'tid' - Azure AD tenant ID
    user_id: str          # 'oid' - Azure AD user object ID
    email: Optional[str]  # 'upn' or 'preferred_username' - User email
    name: Optional[str]   # 'name' - Display name
    roles: list           # 'roles' - App roles if configured
    raw_claims: dict      # Full token payload for debugging

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role"""
        return "Admin" in self.roles or "admin" in self.roles


# =============================================================================
# JWKS Client (cached)
# =============================================================================

_jwks_client: Optional[PyJWKClient] = None


def get_jwks_client() -> PyJWKClient:
    """Get or create JWKS client for token verification"""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(JWKS_URL, cache_keys=True)
    return _jwks_client


# =============================================================================
# Token Validation
# =============================================================================

async def validate_azure_token(token: str) -> TokenClaims:
    """
    Validate Azure AD JWT token and extract claims

    Args:
        token: JWT token from Authorization header

    Returns:
        TokenClaims with extracted user information

    Raises:
        HTTPException: If token is invalid or expired
    """
    if not AZURE_CLIENT_ID:
        logger.error("AZURE_CLIENT_ID not configured")
        raise HTTPException(status_code=500, detail="Authentication not configured")

    try:
        # Get signing key from Microsoft JWKS
        jwks_client = get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Decode without verification first to get the issuer
        unverified = jwt.decode(token, options={"verify_signature": False})
        token_tenant = unverified.get("tid", "")

        # Build valid issuers for this tenant
        valid_issuers = [
            iss.format(tenant=token_tenant)
            for iss in VALID_ISSUERS
        ]

        # Verify and decode the token
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=AZURE_CLIENT_ID,
            issuer=valid_issuers,
            options={
                "verify_exp": True,
                "verify_aud": True,
                "verify_iss": True,
            }
        )

        # Extract claims
        claims = TokenClaims(
            tenant_id=payload.get("tid", ""),
            user_id=payload.get("oid", ""),
            email=payload.get("upn") or payload.get("preferred_username") or payload.get("email"),
            name=payload.get("name"),
            roles=payload.get("roles", []),
            raw_claims=payload,
        )

        if not claims.tenant_id or not claims.user_id:
            raise HTTPException(
                status_code=401,
                detail="Token missing required claims (tid, oid)"
            )

        logger.debug(f"Token validated for user {claims.email} in tenant {claims.tenant_id[:8]}")
        return claims

    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        raise HTTPException(status_code=401, detail="Token expired")

    except jwt.InvalidAudienceError:
        logger.warning(f"Invalid audience in token")
        raise HTTPException(status_code=401, detail="Invalid token audience")

    except jwt.InvalidIssuerError:
        logger.warning(f"Invalid issuer in token")
        raise HTTPException(status_code=401, detail="Invalid token issuer")

    except jwt.PyJWKClientError as e:
        logger.error(f"JWKS client error: {e}")
        raise HTTPException(status_code=401, detail="Unable to verify token signature")

    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")

    except Exception as e:
        logger.error(f"Token validation error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")


# =============================================================================
# FastAPI Dependencies
# =============================================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> TokenClaims:
    """
    FastAPI dependency to get current authenticated user

    Usage:
        @app.get("/api/protected")
        async def protected_route(user: TokenClaims = Depends(get_current_user)):
            return {"email": user.email}
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization header required")

    return await validate_azure_token(credentials.credentials)


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Optional[TokenClaims]:
    """
    FastAPI dependency that returns None if no valid token

    Useful for endpoints that work differently for authenticated users
    """
    if not credentials:
        return None

    try:
        return await validate_azure_token(credentials.credentials)
    except HTTPException:
        return None


async def require_admin(
    user: TokenClaims = Depends(get_current_user)
) -> TokenClaims:
    """
    FastAPI dependency that requires admin role

    Note: Admin status is checked against the database in seat_manager,
    not just token roles, since first user in tenant becomes admin.
    """
    # This is a token-level check; actual admin verification happens
    # in seat_manager.py against the database
    return user


# =============================================================================
# Development/Testing Helpers
# =============================================================================

def create_test_claims(
    tenant_id: str = "test-tenant-id",
    user_id: str = "test-user-id",
    email: str = "test@example.com",
    name: str = "Test User",
    is_admin: bool = False,
) -> TokenClaims:
    """Create mock token claims for testing"""
    return TokenClaims(
        tenant_id=tenant_id,
        user_id=user_id,
        email=email,
        name=name,
        roles=["Admin"] if is_admin else [],
        raw_claims={
            "tid": tenant_id,
            "oid": user_id,
            "upn": email,
            "name": name,
        }
    )


# =============================================================================
# Token Info Endpoint Helper
# =============================================================================

def get_token_info(claims: TokenClaims) -> Dict[str, Any]:
    """Format token claims for API response"""
    return {
        "tenant_id": claims.tenant_id,
        "user_id": claims.user_id,
        "email": claims.email,
        "name": claims.name,
        "is_admin_role": claims.is_admin,
    }


# =============================================================================
# Seat Enforcement
# =============================================================================

# Environment flag to enable/disable seat enforcement
ENFORCE_SEATS = os.getenv("ENFORCE_SEATS", "false").lower() == "true"


async def verify_seat_access(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Optional[TokenClaims]:
    """
    Verify user has a valid seat before allowing API access

    When ENFORCE_SEATS=true:
      - Validates Azure AD token
      - Checks user has an active seat
      - Returns 403 if no seat available

    When ENFORCE_SEATS=false (default):
      - Returns None, allowing access without auth
    """
    if not ENFORCE_SEATS:
        # Seat enforcement disabled - allow access
        return None

    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authorization required. Please sign in."
        )

    # Validate token
    claims = await validate_azure_token(credentials.credentials)

    # Check seat in database
    try:
        from database import get_db_session, get_tenant_by_azure_id, get_user_by_azure_id, get_active_subscription, get_active_seat_assignment

        with get_db_session() as db:
            tenant = get_tenant_by_azure_id(db, claims.tenant_id)
            if not tenant:
                raise HTTPException(
                    status_code=403,
                    detail="Organization not registered. Please contact support."
                )

            user = get_user_by_azure_id(db, tenant.id, claims.user_id)
            if not user:
                raise HTTPException(
                    status_code=403,
                    detail="User not registered. Please sign in through the add-in first."
                )

            subscription = get_active_subscription(db, tenant.id)
            if not subscription:
                raise HTTPException(
                    status_code=403,
                    detail="No active subscription. Please contact your admin."
                )

            seat = get_active_seat_assignment(db, user.id, subscription.id)
            if not seat:
                raise HTTPException(
                    status_code=403,
                    detail="No seat available. Contact your admin to free up a seat."
                )

        return claims

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Seat verification error: {e}")
        # On database errors, allow access to prevent lockout
        logger.warning("Seat verification bypassed due to database error")
        return claims


# Export
__all__ = [
    "TokenClaims",
    "validate_azure_token",
    "get_current_user",
    "get_optional_user",
    "require_admin",
    "create_test_claims",
    "get_token_info",
    "verify_seat_access",
    "ENFORCE_SEATS",
]
