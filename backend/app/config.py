from __future__ import annotations

import os
from pathlib import Path

from app import env  # noqa: F401  (loads .env)

REPO_ROOT = env.REPO_ROOT

# True when running on Render (Render sets RENDER=true on every service).
ON_RENDER = os.environ.get("RENDER", "").lower() == "true"

# Folder for everything this backend writes (the SQLite file + generated
# PDFs). On Render the app's own folder is wiped on every deploy/restart,
# so point DATA_DIR at the mount path of a Render persistent disk (e.g.
# /var/data). PROSPECT_DB_PATH / MGA_LEAD_MAGNET_DIR still override the
# individual locations.
DATA_DIR = Path(os.environ.get("DATA_DIR", "").strip() or str(REPO_ROOT / "data"))

# SQLite file holding the mga_leads table. Override with PROSPECT_DB_PATH
# (e.g. for tests or a persistent-disk path in production).
DB_PATH = Path(
    os.environ.get("PROSPECT_DB_PATH", "").strip() or str(DATA_DIR / "pipeline_state.db")
)
# SQLite can't create its own parent folder; a freshly mounted disk is empty.
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

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
# Browsers send the Origin without a trailing slash, so "https://site.com/"
# in the env var would never match -- strip it.
CORS_ORIGINS = [
    o.strip().rstrip("/")
    for o in (os.environ.get("PROSPECT_CORS_ORIGINS", "").strip() or _default_origins).split(",")
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
# "mailerlite" (default, new MailerLite), "mailerlite_classic" (Legacy/Classic
# MailerLite accounts, which use a different API and API key) or "gmail".
EMAIL_PROVIDER = os.environ.get("EMAIL_PROVIDER", "mailerlite").strip().lower()

# Provider for the internal new-lead alert to LEAD_NOTIFY_EMAILS. Defaults to
# EMAIL_PROVIDER; set TEAM_EMAIL_PROVIDER=gmail to send visitor reports
# through MailerLite but team alerts from a Google Workspace mailbox (no
# unsubscribe footer, and the team isn't added as MailerLite subscribers).
TEAM_EMAIL_PROVIDER = (
    os.environ.get("TEAM_EMAIL_PROVIDER", "").strip().lower() or EMAIL_PROVIDER
)

# MailerLite group every website lead is also added to (with their name and
# phone), e.g. "MGA New Website Subs". Empty = don't add leads to a list.
MAILERLITE_LEADS_GROUP_ID = os.environ.get("MAILERLITE_LEADS_GROUP_ID", "").strip()
# Whether joining that group may start the group's own MailerLite
# automations (e.g. a welcome sequence). Off by default, so a lead only gets
# their report unless you decide otherwise. (Classic accounts only; in the
# new MailerLite, automations on the group always run.)
MAILERLITE_LEADS_TRIGGER_AUTOMATIONS = os.environ.get(
    "MAILERLITE_LEADS_TRIGGER_AUTOMATIONS", "false"
).lower() in ("1", "true", "yes")

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
    os.environ.get("MGA_LEAD_MAGNET_DIR", "").strip() or str(DATA_DIR / "mga_lead_magnets")
)

# This backend's own public HTTPS URL, embedded into the lead-magnet
# download link served via the dashboard/API (see
# mga_lead_service.build_delivery_url) -- no email involved.
# On Render, falls back to the service's own https://<name>.onrender.com
# address (RENDER_EXTERNAL_URL, set by Render) so emailed download links
# never point at localhost. Set PUBLIC_API_BASE_URL explicitly when the API
# has a custom domain (e.g. https://api.mygrowthacademy.coach).
PUBLIC_API_BASE_URL = (
    os.environ.get("PUBLIC_API_BASE_URL", "").strip()
    or os.environ.get("RENDER_EXTERNAL_URL", "").strip()
    or "http://localhost:8000"
).rstrip("/")

# The public website that lead magnets (PDF + delivery email) link back to.
# Change this one value (e.g. to https://mygrowthacademy.coach) when the
# site moves to its own domain -- nothing else needs editing.
PUBLIC_SITE_URL = os.environ.get(
    "PUBLIC_SITE_URL", "https://mygrowthacademy.vercel.app"
).strip().rstrip("/")
# The same address without "https://", for display text.
PUBLIC_SITE_DISPLAY = PUBLIC_SITE_URL.split("://", 1)[-1]

# The website itself must always be able to call the API, even when
# PROSPECT_CORS_ORIGINS is set to something that forgets it. Covers both
# the bare and www. forms of the site's domain.
def _site_origins(url: str) -> list[str]:
    scheme, _, host = url.partition("://")
    if not host:
        return []
    host = host.split("/", 1)[0]
    bare = host[4:] if host.startswith("www.") else host
    return [f"{scheme}://{bare}", f"{scheme}://www.{bare}"]


for _origin in _site_origins(PUBLIC_SITE_URL):
    if _origin not in CORS_ORIGINS:
        CORS_ORIGINS.append(_origin)

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
