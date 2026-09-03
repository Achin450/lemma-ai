import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks

from app.services.database import DatabaseService
from app.services.auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    is_edu_email, generate_institution_code,
    get_current_user,
)
from app.schemas.auth import (
    UserRegister, UserLogin, TokenResponse, RefreshRequest,
    UserProfile, EmailVerifyRequest, PasswordChangeRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


def _get_user_by_email(email: str) -> Optional[dict]:
    """Fetch a user record by email from PostgreSQL."""
    with DatabaseService.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT u.*, i.name AS institution_name
                   FROM users u
                   LEFT JOIN institutions i ON u.institution_id = i.id
                   WHERE u.email = %s""",
                (email,),
            )
            return cur.fetchone()


def _get_user_by_id(user_id: str) -> Optional[dict]:
    """Fetch a user record by ID from PostgreSQL."""
    with DatabaseService.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT u.*, i.name AS institution_name
                   FROM users u
                   LEFT JOIN institutions i ON u.institution_id = i.id
                   WHERE u.id = %s""",
                (user_id,),
            )
            return cur.fetchone()


def _build_profile(row: dict) -> UserProfile:
    return UserProfile(
        id=str(row["id"]),
        email=row["email"],
        full_name=row["full_name"],
        role=row["role"],
        institution_id=str(row["institution_id"]) if row.get("institution_id") else None,
        institution_name=row.get("institution_name"),
        email_verified=row.get("email_verified", False),
        created_at=str(row.get("created_at", "")),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, background_tasks: BackgroundTasks):
    """
    Register a new user.
    - If email is a recognised .edu domain, institution lookup is automatic by domain.
    - Otherwise, an `institution_code` is required.
    """
    email = payload.email.lower().strip()

    # Check duplicate
    existing = _get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.")

    institution_id: Optional[str] = None

    with DatabaseService.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if is_edu_email(email):
                # Try to find matching institution by domain
                domain = email.split("@", 1)[1].lower()
                cur.execute("SELECT id FROM institutions WHERE domain = %s", (domain,))
                inst = cur.fetchone()
                if inst:
                    institution_id = str(inst["id"])
            elif payload.institution_code:
                cur.execute("SELECT id FROM institutions WHERE institution_code = %s", (payload.institution_code.upper(),))
                inst = cur.fetchone()
                if not inst:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid institution code.")
                institution_id = str(inst["id"])
            # else: no institution — solo/demo account

            user_id = str(uuid.uuid4())
            pw_hash = hash_password(payload.password)
            # For demo: auto-verify email (a real app would send a verification email)
            cur.execute(
                """INSERT INTO users (id, email, password_hash, full_name, role, institution_id, email_verified)
                   VALUES (%s, %s, %s, %s, 'student', %s, TRUE)""",
                (user_id, email, pw_hash, payload.full_name, institution_id),
            )
        conn.commit()

    row = _get_user_by_id(user_id)
    profile = _build_profile(row)
    access_token = create_access_token(user_id, email, row["role"], institution_id)
    refresh_token = create_refresh_token(user_id)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token, user=profile)


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin):
    """Authenticate with email + password, returns JWT tokens."""
    email = payload.email.lower().strip()
    row = _get_user_by_email(email)
    if not row or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    profile = _build_profile(row)
    access_token = create_access_token(
        str(row["id"]), email, row["role"],
        str(row["institution_id"]) if row.get("institution_id") else None,
    )
    refresh_token = create_refresh_token(str(row["id"]))
    return TokenResponse(access_token=access_token, refresh_token=refresh_token, user=profile)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshRequest):
    """Exchange a valid refresh token for new access + refresh tokens."""
    token_data = decode_token(payload.refresh_token)
    if token_data.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type.")

    user_id = token_data["sub"]
    row = _get_user_by_id(user_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

    profile = _build_profile(row)
    access_token = create_access_token(
        user_id, row["email"], row["role"],
        str(row["institution_id"]) if row.get("institution_id") else None,
    )
    new_refresh = create_refresh_token(user_id)
    return TokenResponse(access_token=access_token, refresh_token=new_refresh, user=profile)


@router.get("/me", response_model=UserProfile)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    row = _get_user_by_id(current_user["sub"])
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return _build_profile(row)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(payload: PasswordChangeRequest, current_user: dict = Depends(get_current_user)):
    """Change the current user''s password."""
    row = _get_user_by_id(current_user["sub"])
    if not row or not verify_password(payload.current_password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")

    new_hash = hash_password(payload.new_password)
    with DatabaseService.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, current_user["sub"]))
        conn.commit()
