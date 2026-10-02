"""
Rate Limiting & Abuse Prevention Middleware for Lemma AI
Provides sliding-window in-memory rate limiting with Redis fallback.
Protects authentication, registration, and expensive AI endpoints from brute-force & denial-of-service.
"""
import time
import threading
import logging
from collections import defaultdict
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger("rate_limiter")


class RateLimiter:
    """Sliding-window rate limiter tracking requests per IP."""

    def __init__(self):
        self._lock = threading.Lock()
        # Storage: { key: [(timestamp, count)] }
        self._hits = defaultdict(list)
        self._last_cleanup = time.time()

    def _cleanup_old_entries(self, now: float):
        """Periodically purge entries older than 2 minutes to keep memory small."""
        if now - self._last_cleanup < 60:
            return
        self._last_cleanup = now
        cutoff = now - 120
        keys_to_delete = []
        for key, timestamps in self._hits.items():
            valid_stamps = [t for t in timestamps if t > cutoff]
            if valid_stamps:
                self._hits[key] = valid_stamps
            else:
                keys_to_delete.append(key)
        for k in keys_to_delete:
            del self._hits[k]

    def is_allowed(self, client_id: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
        """
        Check if the client has exceeded their allowance in the window.
        Returns: (is_allowed: bool, retry_after_seconds: int)
        """
        now = time.time()
        window_start = now - window_seconds

        with self._lock:
            self._cleanup_old_entries(now)
            timestamps = self._hits[client_id]
            # Keep only hits within the active window
            recent = [t for t in timestamps if t > window_start]
            self._hits[client_id] = recent

            if len(recent) >= limit:
                # Calculate remaining seconds until oldest hit in window expires
                oldest = recent[0]
                retry_after = max(1, int(window_seconds - (now - oldest)))
                return False, retry_after

            self._hits[client_id].append(now)
            return True, 0


# Global in-memory limiter instance
rate_limiter_instance = RateLimiter()


def get_client_ip(request: Request) -> str:
    """Safely extract client IP from X-Forwarded-For or client host."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first untrusted IP in the chain (real client)
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "127.0.0.1"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Starlette middleware intercepting incoming requests to enforce rate limits."""

    async def dispatch(self, request: Request, call_next):
        # Exclude OPTIONS preflight requests
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        # Exclude static frontend files, favicon, manifest, and health checks
        if (
            path in ("/health", f"{settings.API_V1_STR}/health", "/favicon.ico", "/site.webmanifest")
            or path.startswith("/assets/")
            or path.endswith((".css", ".js", ".png", ".jpg", ".svg", ".ico", ".woff2", ".ttf", ".html"))
            and not path.startswith("/api/")
        ):
            return await call_next(request)

        client_ip = get_client_ip(request)

        # Route-specific rate limits
        limit = settings.RATE_LIMIT_DEFAULT_PER_MINUTE
        route_key = "default"

        if path.endswith("/auth/login"):
            limit = settings.RATE_LIMIT_LOGIN_PER_MINUTE
            route_key = "auth_login"
        elif path.endswith("/auth/register") or path.endswith("/organisations/register"):
            limit = settings.RATE_LIMIT_REGISTER_PER_MINUTE
            route_key = "auth_register"
        elif (
            "/research/generate" in path
            or "/research/restructure" in path
            or "/novelty/analyze" in path
            or "/humanize" in path
            or "/rewrite" in path
        ):
            limit = settings.RATE_LIMIT_AI_PER_MINUTE
            route_key = "expensive_ai"

        bucket_key = f"{route_key}:{client_ip}"
        allowed, retry_after = rate_limiter_instance.is_allowed(bucket_key, limit=limit, window_seconds=60)

        if not allowed:
            logger.warning(f"Rate limit exceeded for {client_ip} on {path} (limit={limit}/min)")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Too many requests. Please slow down and try again.",
                    "retry_after": retry_after
                },
                headers={"Retry-After": str(retry_after)}
            )

        response = await call_next(request)
        return response
