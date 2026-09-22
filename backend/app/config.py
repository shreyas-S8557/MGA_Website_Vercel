from __future__ import annotations

import os
from pathlib import Path

from app import env  # noqa: F401  (loads .env)

REPO_ROOT = env.REPO_ROOT

# SQLite file holding the mga_leads table. Override with PROSPECT_DB_PATH
# (e.g. for tests or a persistent-disk path in production).
DB_PATH = Path(
    os.environ.get("PROSPECT_DB_PATH", str(REPO_ROOT / "data" / "pipeline_state.db"))
)

# CORS: the frontend is a static file (see frontend/index.html — no build
# step), so it can be served from any static file server / port during
# local dev. Allow the common ones plus configurable extras.
_default_origins = (
    "http://localhost:5173,http://127.0.0.1:5173,"
    "http://localhost:8080,http://127.0.0.1:8080,"
    "http://localhost:3000,http://127.0.0.1:3000,"
    "http://localhost:5500,http://127.0.0.1:5500,"  # VS Code Live Server / `python -m http.server 5500` default
    "null"  # file:// origins send "null" -- opening index.html directly still works
)
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("PROSPECT_CORS_ORIGINS", _default_origins).split(",")
    if o.strip()
]

# Global safety switch: no real email (lead-magnet delivery or team
# notification) is ever sent unless this is explicitly enabled. This is
# what keeps automated tests and local development from sending real email.
ALLOW_LIVE_SEND = os.environ.get("PROSPECT_ALLOW_LIVE_SEND", "false").lower() in (
    "1",
    "true",
    "yes",
)

# Which email provider is used for live sends (see sending_service._PROVIDERS).
# "mailerlite" is the default; "gmail" is an explicit, opt-in alternative.
EMAIL_PROVIDER = os.environ.get("EMAIL_PROVIDER", "mailerlite").strip().lower()

LOG_LEVEL = os.environ.get("PROSPECT_LOG_LEVEL", "INFO")

# --------------------------------------------------------------------------
# Lead-magnet pipeline (see app/services/mga_lead_service.py).
# --------------------------------------------------------------------------

# Shared secret the Google Apps Script (google-apps-script/Code.gs) sends
# in the X-MGA-Webhook-Secret header on every POST /api/leads/google-form.
# No default -- an unset/placeholder value must refuse every request
# rather than silently accepting unauthenticated webhooks.
GOOGLE_FORM_WEBHOOK_SECRET = os.environ.get("GOOGLE_FORM_WEBHOOK_SECRET", "")

# Generated lead-magnet PDFs live under data/, next to the SQLite file.
MGA_LEAD_MAGNET_DIR = Path(
    os.environ.get("MGA_LEAD_MAGNET_DIR", str(REPO_ROOT / "data" / "mga_lead_magnets"))
)

# This backend's own public HTTPS URL, embedded into the lead-magnet
# download link served via the dashboard/API (see
# mga_lead_service.build_delivery_url) -- no email involved.
PUBLIC_API_BASE_URL = os.environ.get("PUBLIC_API_BASE_URL", "http://localhost:8000")

# --------------------------------------------------------------------------
# Team notification for new website/Google Form leads.
# --------------------------------------------------------------------------

# Comma-separated list of people who get an email the moment a new lead
# comes in (name, contact details, their answers, and a link to the PDF
# they were given). Leave empty to turn notifications off. Sent through
# the same EMAIL_PROVIDER / PROSPECT_ALLOW_LIVE_SEND switches as every
# other email this backend sends.
LEAD_NOTIFY_EMAILS = [
    e.strip()
    for e in os.environ.get("LEAD_NOTIFY_EMAILS", "").split(",")
    if e.strip()
]

# --------------------------------------------------------------------------
# Dashboard access key.
# --------------------------------------------------------------------------

# Every /api/ route except the few public ones the website itself needs
# (health, lead submission, PDF download, and the secret-protected
# Google Form webhook/retry) requires this key in an X-Dashboard-Key
# header. Those routes expose lead names, emails, phone numbers and
# answers, so there is NO default: if this is unset the protected routes
# refuse every request. Generate one with:
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
DASHBOARD_API_KEY = os.environ.get("DASHBOARD_API_KEY", "")

# Local-development escape hatch ONLY. Set to "true" to skip the key check
# entirely (e.g. running the dashboard on your own laptop). Never set this
# on a server that is reachable from the internet.
DASHBOARD_AUTH_DISABLED = os.environ.get("DASHBOARD_AUTH_DISABLED", "false").lower() in (
    "1",
    "true",
    "yes",
)
