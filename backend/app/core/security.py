from __future__ import annotations

import os
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse


UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def configure_security(app: FastAPI) -> None:
    configured_hosts = [
        host.strip()
        for host in os.getenv("ALLOWED_HOSTS", "").split(",")
        if host.strip()
    ]
    trusted_origins = {
        origin.strip().rstrip("/")
        for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
        if origin.strip()
    }
    # Same-origin /api requests arrive through the frontend proxy with the
    # frontend hostname. Keep older production compose files compatible by
    # trusting the hostnames of the already-approved CSRF origins as well.
    origin_hosts = {
        urlparse(origin).netloc
        for origin in trusted_origins
        if urlparse(origin).netloc
    }
    allowed_hosts = list(dict.fromkeys([*configured_hosts, *sorted(origin_hosts)]))

    if allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method in UNSAFE_METHODS and origin:
            if not _is_allowed_origin(origin, request.headers.get("host"), trusted_origins):
                return JSONResponse(
                    {"detail": "Origem da requisicao nao permitida."},
                    status_code=403,
                )

        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response


def _is_allowed_origin(origin: str, host: str | None, trusted_origins: set[str]) -> bool:
    parsed = urlparse(origin)
    if not parsed.scheme or not parsed.netloc:
        return False
    return parsed.netloc == host or origin.rstrip("/") in trusted_origins
