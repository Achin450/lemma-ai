import os
import uuid
import logging
import urllib.parse
from datetime import datetime, timezone
from typing import Optional

import httpx
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.responses import RedirectResponse

from app.config import settings
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


# ===========================================================================
# OAuth 2.0 Social Authentication (Google & GitHub)
# ===========================================================================

def _upsert_oauth_user(email: str, full_name: str, provider: str, provider_id: str, avatar_url: Optional[str] = None) -> dict:
    """Create or return existing user for OAuth social logins."""
    with DatabaseService.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Ensure columns exist dynamically on live database
            cur.execute("""
                DO $$ 
                BEGIN 
                    BEGIN
                        ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;
                    EXCEPTION WHEN others THEN NULL; END;
                    BEGIN
                        ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider VARCHAR(32) DEFAULT 'email';
                    EXCEPTION WHEN others THEN NULL; END;
                    BEGIN
                        ALTER TABLE users ADD COLUMN IF NOT EXISTS provider_id TEXT;
                    EXCEPTION WHEN others THEN NULL; END;
                    BEGIN
                        ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT;
                    EXCEPTION WHEN others THEN NULL; END;
                END $$;
            """)

            cur.execute("SELECT * FROM users WHERE email = %s", (email.lower().strip(),))
            user = cur.fetchone()

            if user:
                # Update provider details if missing
                cur.execute(
                    """UPDATE users 
                       SET auth_provider = COALESCE(auth_provider, %s),
                           provider_id = COALESCE(provider_id, %s),
                           avatar_url = COALESCE(avatar_url, %s),
                           email_verified = TRUE
                       WHERE id = %s RETURNING *""",
                    (provider, provider_id, avatar_url, user["id"])
                )
                user = cur.fetchone()
            else:
                # Create brand new user without requiring password
                new_id = str(uuid.uuid4())
                cur.execute(
                    """INSERT INTO users (id, email, password_hash, full_name, role, auth_provider, provider_id, avatar_url, email_verified)
                       VALUES (%s, %s, %s, %s, 'student', %s, %s, %s, TRUE)
                       RETURNING *""",
                    (new_id, email.lower().strip(), "", full_name or email.split("@")[0], provider, provider_id, avatar_url)
                )
                user = cur.fetchone()
        conn.commit()
    return user


@router.get("/oauth/{provider}/login")
async def oauth_login(provider: str, req: Request):
    """Initiate OAuth flow by redirecting to Google or GitHub consent screen."""
    provider = provider.lower()
    callback_base = settings.BACKEND_PUBLIC_URL.rstrip("/")
    redirect_uri = f"{callback_base}/api/v1/auth/oauth/{provider}/callback"

    if provider == "google":
        client_id = os.getenv("GOOGLE_CLIENT_ID") or settings.GOOGLE_CLIENT_ID
        if not client_id:
            raise HTTPException(status_code=400, detail="Google OAuth is not configured on this server.")
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "select_account",
        }
        url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
        return RedirectResponse(url=url)

    elif provider == "github":
        client_id = os.getenv("GITHUB_CLIENT_ID") or settings.GITHUB_CLIENT_ID
        if not client_id:
            # Fallback if GitHub credentials not provided yet: Inform user cleanly
            frontend_target = f"{settings.FRONTEND_URL.rstrip('/')}/login.html?error=" + urllib.parse.quote("GitHub OAuth is pending client_id configuration.")
            return RedirectResponse(url=frontend_target)
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
        }
        url = f"https://github.com/login/oauth/authorize?{urllib.parse.urlencode(params)}"
        return RedirectResponse(url=url)

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported OAuth provider: {provider}")


@router.get("/oauth/{provider}/callback")
async def oauth_callback(provider: str, code: Optional[str] = None, error: Optional[str] = None):
    """Handle OAuth authorization code callback, fetch user profile, and redirect to frontend with tokens."""
    frontend_base = (os.getenv("FRONTEND_URL") or settings.FRONTEND_URL).rstrip("/")
    provider = provider.lower()

    if error:
        err_target = f"{frontend_base}/login.html?error={urllib.parse.quote(error)}"
        return RedirectResponse(url=err_target)

    if not code:
        err_target = f"{frontend_base}/login.html?error={urllib.parse.quote('No authorization code returned.')}"
        return RedirectResponse(url=err_target)

    callback_base = (os.getenv("BACKEND_PUBLIC_URL") or settings.BACKEND_PUBLIC_URL).rstrip("/")
    redirect_uri = f"{callback_base}/api/v1/auth/oauth/{provider}/callback"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if provider == "google":
                g_client_id = os.getenv("GOOGLE_CLIENT_ID") or settings.GOOGLE_CLIENT_ID
                g_client_secret = os.getenv("GOOGLE_CLIENT_SECRET") or settings.GOOGLE_CLIENT_SECRET
                token_res = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "code": code,
                        "client_id": g_client_id,
                        "client_secret": g_client_secret,
                        "redirect_uri": redirect_uri,
                        "grant_type": "authorization_code",
                    },
                )
                if not token_res.is_success:
                    logger.error(f"Google token exchange failed: {token_res.text}")
                    return RedirectResponse(url=f"{frontend_base}/login.html?error={urllib.parse.quote('Google authorization failed.')}")

                token_json = token_res.json()
                google_access_token = token_json.get("access_token")

                # Fetch userinfo
                user_res = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {google_access_token}"},
                )
                if not user_res.is_success:
                    return RedirectResponse(url=f"{frontend_base}/login.html?error={urllib.parse.quote('Failed to fetch Google profile.')}")

                uinfo = user_res.json()
                email = uinfo.get("email")
                full_name = uinfo.get("name") or uinfo.get("given_name") or email.split("@")[0]
                provider_id = uinfo.get("id") or str(uuid.uuid4())
                avatar_url = uinfo.get("picture")

            elif provider == "github":
                gh_client_id = os.getenv("GITHUB_CLIENT_ID") or settings.GITHUB_CLIENT_ID
                gh_client_secret = os.getenv("GITHUB_CLIENT_SECRET") or settings.GITHUB_CLIENT_SECRET
                token_res = await client.post(
                    "https://github.com/login/oauth/access_token",
                    data={
                        "code": code,
                        "client_id": gh_client_id,
                        "client_secret": gh_client_secret,
                        "redirect_uri": redirect_uri,
                    },
                    headers={"Accept": "application/json"},
                )
                token_json = token_res.json()
                gh_access_token = token_json.get("access_token")

                if not gh_access_token:
                    return RedirectResponse(url=f"{frontend_base}/login.html?error={urllib.parse.quote('GitHub token exchange failed.')}")

                # Fetch GitHub user profile
                user_res = await client.get(
                    "https://api.github.com/user",
                    headers={"Authorization": f"Bearer {gh_access_token}", "Accept": "application/json"},
                )
                uinfo = user_res.json()
                provider_id = str(uinfo.get("id"))
                full_name = uinfo.get("name") or uinfo.get("login")
                avatar_url = uinfo.get("avatar_url")
                email = uinfo.get("email")

                # If email is private, fetch from emails endpoint
                if not email:
                    emails_res = await client.get(
                        "https://api.github.com/user/emails",
                        headers={"Authorization": f"Bearer {gh_access_token}", "Accept": "application/json"},
                    )
                    if emails_res.is_success:
                        for item in emails_res.json():
                            if item.get("primary") and item.get("verified"):
                                email = item.get("email")
                                break
                if not email:
                    email = f"{uinfo.get('login')}@users.noreply.github.com"

            else:
                return RedirectResponse(url=f"{frontend_base}/login.html?error={urllib.parse.quote('Unsupported provider.')}")

            # Upsert user in database
            user = _upsert_oauth_user(email, full_name, provider, provider_id, avatar_url)
            access_token = create_access_token(
                str(user["id"]), user["email"], user["role"],
                str(user["institution_id"]) if user.get("institution_id") else None,
            )
            refresh_token = create_refresh_token(str(user["id"]))

            # Redirect user to login page with tokens in URL hash (secure against browser logs)
            redirect_final = (
                f"{frontend_base}/login.html#oauth_success=1"
                f"&access_token={access_token}"
                f"&refresh_token={refresh_token}"
                f"&user_email={urllib.parse.quote(user['email'])}"
                f"&user_name={urllib.parse.quote(user['full_name'])}"
            )
            return RedirectResponse(url=redirect_final)

    except Exception as exc:
        logger.exception("OAuth callback error:")
        return RedirectResponse(url=f"{frontend_base}/login.html?error={urllib.parse.quote(str(exc))}")
