from __future__ import annotations

import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import env  # noqa: F401 -- loads .env
from app.api import email_provider, health, mga_leads, settings
from app.config import CORS_ORIGINS
from app.db import database
from app.utils.logging import configure_logging

configure_logging()
logger = logging.getLogger("mga.backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_app_tables()
    logger.info("Backend started. Database: %s", database.DB_PATH)
    yield


app = FastAPI(
    title="MGA Lead Magnet API",
    version="2.0.0",
    description=(
        "Receives My Growth Academy quiz submissions and generates, delivers and "
        "tracks each visitor's personalized lead-magnet PDF. "
        "See /docs for the interactive schema."
    ),
    lifespan=lifespan,
)

# --------------------------------------------------------------------------
# Dashboard access key. Registered BEFORE the CORS middleware so CORS ends
# up as the outer layer -- a 401 from here still carries CORS headers, so
# the browser dashboard can read the error instead of seeing a CORS failure.
# --------------------------------------------------------------------------

import hmac as _hmac
import re as _re

# Routes the public website (and the Google Form forwarder) must reach
# without the dashboard key. Everything else under /api/ is dashboard-only.
_PUBLIC_API_PATTERNS = [
    _re.compile(r"^/api/health/?$"),
    _re.compile(r"^/api/leads/website/?$"),  # visitor's quiz submission
    _re.compile(r"^/api/leads/google-form/?$"),  # has its own shared secret
    _re.compile(r"^/api/leads/[^/]+/retry/?$"),  # has its own shared secret
    _re.compile(r"^/api/lead-magnets/[^/]+/?$"),  # PDF download by unguessable id
]


def _is_public(path: str) -> bool:
    if not path.startswith("/api/"):
        return True  # "/", "/docs", "/openapi.json" -- no lead data
    return any(p.match(path) for p in _PUBLIC_API_PATTERNS)


@app.middleware("http")
async def require_dashboard_key(request: Request, call_next):
    import app.config as config  # re-read so tests/env reloads take effect

    if (
        request.method == "OPTIONS"
        or config.DASHBOARD_AUTH_DISABLED
        or _is_public(request.url.path)
    ):
        return await call_next(request)

    expected = config.DASHBOARD_API_KEY
    if not expected:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "DASHBOARD_API_KEY is not configured on the server, so "
                "dashboard routes are locked. Set it in the backend's .env."
            },
        )
    supplied = request.headers.get("X-Dashboard-Key", "")
    if not supplied or not _hmac.compare_digest(supplied, expected):
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing dashboard key."})
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Lets a cross-origin fetch() read the server-provided filename on a
    # file download (browsers hide this header from JS by default).
    expose_headers=["Content-Disposition"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never leak a Python stack trace to the frontend (PHASE 29). Full
    # detail goes to the server log only, redacted of anything
    # secret-shaped first.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. See server logs for details."},
    )


app.include_router(health.router)
app.include_router(settings.router)
app.include_router(email_provider.router)
app.include_router(mga_leads.router)


@app.get("/")
def root() -> dict:
    return {"name": "MGA Lead Magnet API", "docs": "/docs", "health": "/api/health"}
