from __future__ import annotations

import hmac
import os
import time
from collections import defaultdict

from fastapi import Header, HTTPException, Request, status

from app.config import GOOGLE_FORM_WEBHOOK_SECRET


def provider_status() -> dict[str, dict[str, str]]:
    """Report whether each external provider looks configured, WITHOUT ever
    returning the credential value itself."""

    def _status(*env_vars: str) -> str:
        return "configured" if all(os.environ.get(v) for v in env_vars) else "not_configured"

    return {
        "llm": {
            "status": _status("OPENAI_API_KEY"),
            "detail": "OpenAI-compatible endpoint used to personalize lead-magnet reports",
        },
        "mailerlite": {
            "status": _status(
                "MAILERLITE_API_TOKEN", "MAILERLITE_SENDER_EMAIL", "MAILERLITE_SENDER_NAME"
            ),
            "detail": "Sends lead-magnet and team-notification emails (default EMAIL_PROVIDER)",
        },
        "gmail": {
            "status": _status("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD"),
            "detail": "Optional -- only used if EMAIL_PROVIDER=gmail is set explicitly",
        },
        "google_form_webhook": {
            "status": _status("GOOGLE_FORM_WEBHOOK_SECRET"),
            "detail": "Shared secret for POST /api/leads/google-form (optional Google Form path)",
        },
    }


# --------------------------------------------------------------------------
# MGA inbound Google Form webhook auth + basic rate limiting.
# --------------------------------------------------------------------------


def verify_google_form_webhook_secret(
    x_mga_webhook_secret: str | None = Header(default=None, alias="X-MGA-Webhook-Secret"),
) -> None:
    """FastAPI dependency: rejects the request unless it carries the shared
    secret configured for the Google Apps Script forwarder. Constant-time
    comparison to avoid timing leaks. Re-reads app.config's module-level
    value (not a cached copy) so tests that monkeypatch the env var and
    reload app.config (see tests/conftest.py's client fixture) see the
    change take effect."""
    import app.config as config  # local import: picks up monkeypatched/reloaded config in tests

    expected = config.GOOGLE_FORM_WEBHOOK_SECRET
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GOOGLE_FORM_WEBHOOK_SECRET is not configured on the server.",
        )
    if not x_mga_webhook_secret or not hmac.compare_digest(x_mga_webhook_secret, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret.")


# Minimal in-memory, per-process, fixed-window rate limiter. Good enough
# for a single-process backend; swap for a shared store only if this
# backend is ever scaled to multiple processes.
_RATE_WINDOW_SECONDS = 60
_RATE_MAX_PER_WINDOW = 30
_rate_hits: dict[str, list[float]] = defaultdict(list)


def rate_limit_webhook(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window_start = now - _RATE_WINDOW_SECONDS
    hits = [t for t in _rate_hits[client_ip] if t >= window_start]
    hits.append(now)
    _rate_hits[client_ip] = hits
    if len(hits) > _RATE_MAX_PER_WINDOW:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests.")
