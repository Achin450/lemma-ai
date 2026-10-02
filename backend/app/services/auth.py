import os
import uuid
import hashlib
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings

logger = logging.getLogger(__name__)

# HTTP Bearer security scheme
bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Password utilities
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT utilities
# ---------------------------------------------------------------------------

def create_access_token(user_id: str, email: str, role: str, institution_id: Optional[str] = None) -> str:
    """Create a short-lived JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "institution_id": institution_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived JWT refresh token (7 days)."""
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token signature.",
            headers={"WWW-Authenticate": "Bearer"}
        )


def validate_password_strength(plain: str) -> None:
    """Ensure password meets production security criteria."""
    if not plain or len(plain) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long."
        )
    has_letter = any(c.isalpha() for c in plain)
    has_digit_or_symbol = any(c.isdigit() or not c.isalnum() for c in plain)
    if not (has_letter and has_digit_or_symbol):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one letter and at least one number or symbol."
        )


# ---------------------------------------------------------------------------
# Domain & institution helpers
# ---------------------------------------------------------------------------

EDU_SUFFIXES = {".edu", ".ac.uk", ".ac.in", ".edu.au", ".ac.nz", ".edu.sg",
                ".ac.za", ".edu.cn", ".ac.jp", ".edu.br"}

def is_edu_email(email: str) -> bool:
    """Return True if the email domain ends with a recognised academic TLD."""
    try:
        domain = email.split("@", 1)[1].lower()
        return any(domain.endswith(suf) for suf in EDU_SUFFIXES)
    except Exception:
        return False


def generate_institution_code() -> str:
    """Generate a unique 8-character institution onboarding code."""
    return secrets.token_urlsafe(6).upper()[:8]


# ---------------------------------------------------------------------------
# API Key utilities
# ---------------------------------------------------------------------------

def generate_api_key() -> tuple[str, str]:
    """Generate a new API key and its SHA-256 hash.
    Returns (raw_key, hashed_key) — store only the hash."""
    raw = f"lma_{secrets.token_urlsafe(32)}"
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def hash_api_key(raw_key: str) -> str:
    """Hash a raw API key for DB storage."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Authentication Dependencies
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    """
    FastAPI dependency that enforces strict JWT authentication.
    Returns decoded token payload if valid, otherwise raises HTTP 401 Unauthorized.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type: access token required.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not payload.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed token: missing subject identity.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Authentication token validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[dict]:
    """Optional authentication dependency: returns user payload if valid token provided, else None."""
    if credentials is None or not credentials.credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") == "access" and payload.get("sub"):
            return payload
    except Exception:
        pass
    return None


def require_role(*roles: str):
    """FastAPI dependency factory — requires authenticated caller to have one of the specified roles."""
    def dependency(current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role")
        if user_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: required role not met.",
            )
        return current_user
    return dependency


# Convenience pre-built role dependencies
require_admin = require_role("super_admin", "institution_admin")
require_instructor = require_role("super_admin", "institution_admin", "instructor")
require_any_user = require_role("super_admin", "institution_admin", "instructor", "student", "organisation_admin")

