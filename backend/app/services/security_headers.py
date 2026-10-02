"""
Production Security Headers Middleware for Lemma AI
Enforces defense-in-depth HTTP response headers across all API and static requests.
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds standard OWASP production security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # 1. Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 2. Clickjacking protection: only allow same origin framing (e.g. for preview panels)
        response.headers["X-Frame-Options"] = "SAMEORIGIN"

        # 3. Cross-Site Scripting (XSS) legacy filter for older browsers
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # 4. Strict Referrer Policy: only send origin on cross-origin requests
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 5. Restrict unnecessary browser features & hardware access
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"

        # 6. HTTP Strict Transport Security (HSTS) on HTTPS connections
        if request.url.scheme == "https" or settings.IS_PRODUCTION:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        # 7. Disable caching on sensitive API and authentication endpoints
        path = request.url.path
        if path.startswith("/api/v1/auth") or path.startswith("/api/v1/payment") or path.startswith("/api/v1/admin"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"

        return response
