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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")


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
DEFAULT_LOCAL_USER = {
    "sub": "00000000-0000-0000-0000-000000000001",
    "role": "student",
    "email": "researcher@lemma.local",
    "name": "Researcher",
    "type": "access",
}

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    """FastAPI dependency that validates the JWT or returns local default user if unauthenticated."""
    if credentials is None or not credentials.credentials:
        return DEFAULT_LOCAL_USER
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            return DEFAULT_LOCAL_USER
        return payload
    except Exception:
        return DEFAULT_LOCAL_USER



def require_role(*roles: str):
    """FastAPI dependency factory — requires caller to have one of the given roles."""
    def dependency(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user.get("role") not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access requires one of roles: {roles}. Your role: {current_user.get('role')}",
            )
        return current_user
    return dependency


# Convenience pre-built role dependencies
require_admin = require_role("super_admin", "institution_admin")
require_instructor = require_role("super_admin", "institution_admin", "instructor")
require_any_user = require_role("super_admin", "institution_admin", "instructor", "student")
