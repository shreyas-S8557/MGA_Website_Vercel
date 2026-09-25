"""Database access for the backend.

One table, `mga_leads`. Each row is one website-quiz / Google Form
submission and tracks it through the lead-magnet pipeline (see
app/services/mga_lead_service.py).

Two interchangeable backends, same SQL:

  * Turso (hosted, SQLite-compatible) -- used when TURSO_DATABASE_URL is
    set. Required on Vercel, whose functions have no persistent disk: a
    local SQLite file in /tmp would vanish within hours. Talks to Turso's
    HTTP API with httpx (already a dependency), so no native driver is
    needed in the Vercel bundle.
  * A local SQLite file (app.config.DB_PATH) -- local development, tests,
    and any host with a real disk.

We use raw SQL rather than an ORM -- it's one table.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from typing import Any

import httpx

from app.config import DB_PATH

_APP_SCHEMA = """
-- One row per inbound submission (website quiz or Google Form). The
-- lifecycle is: received -> normalized -> profiled -> lead-magnet
-- generation -> delivery. See app/services/mga_lead_service.py.
CREATE TABLE IF NOT EXISTS mga_leads (
    id TEXT PRIMARY KEY,
    -- Google's own response id -- the idempotency key. A retried Apps
    -- Script POST for the same submission must never create a second row.
    form_submission_id TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL DEFAULT 'inbound_google_form',
    status TEXT NOT NULL DEFAULT 'received',
    -- Last stage that actually completed. Distinct from `status` (which
    -- becomes "failed" on an error) so a retry always knows exactly where
    -- to resume from -- see mga_lead_service.run_pipeline().
    last_completed_stage TEXT NOT NULL DEFAULT 'received',
    failed_stage TEXT NOT NULL DEFAULT '',
    error_message TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    source_campaign TEXT NOT NULL DEFAULT '',
    -- Never lose the raw form answers, whatever else happens downstream.
    raw_answers_json TEXT NOT NULL DEFAULT '{}',
    profile_json TEXT NOT NULL DEFAULT '',
    lead_magnet_type TEXT NOT NULL DEFAULT '',
    lead_magnet_id TEXT NOT NULL DEFAULT '',
    lead_magnet_path TEXT NOT NULL DEFAULT '',
    -- The generated report's actual content (starting_point/priority_1/...
    -- -- see lead_magnet_service.generate_personalized_content), kept
    -- alongside the rendered PDF so the delivery email can embed the same
    -- text inline rather than re-deriving it or shipping only a link.
    lead_magnet_content_json TEXT NOT NULL DEFAULT '',
    delivered_at TEXT NOT NULL DEFAULT '',
    -- Whether the personalized-report EMAIL (not just the PDF becoming
    -- available for download) actually went out -- see
    -- mga_lead_service._send_report_email. Independent of `status`/
    -- `delivered_at`: a lead can be status=delivered (PDF ready, download
    -- link live) with email_sent=0 if live sending is disabled or the
    -- send failed -- delivery of the magnet itself never blocks on email.
    email_sent INTEGER NOT NULL DEFAULT 0,
    email_sent_at TEXT NOT NULL DEFAULT '',
    email_error TEXT NOT NULL DEFAULT '',
    submitted_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_mga_leads_status ON mga_leads (status);
CREATE INDEX IF NOT EXISTS idx_mga_leads_created_at ON mga_leads (created_at);
"""

# A single process-wide write lock. SQLite in WAL mode supports concurrent
# readers fine, but serializing writes from Python avoids "database is
# locked" retries entirely for a single-process backend. (Harmless with
# Turso, which serializes writes itself.)
_WRITE_LOCK = threading.Lock()


# Columns added to mga_leads after it first shipped. `CREATE TABLE IF NOT
# EXISTS` above only creates the table on a brand-new database; an existing
# one (anyone who already has leads in it) needs these added in place.
# Each is idempotent (ALTER TABLE ADD COLUMN fails harmlessly with
# "duplicate column name" if it already ran, which is swallowed below) --
# no separate migration runner needed for a change this small.
_MGA_LEADS_ADDED_COLUMNS = [
    "lead_magnet_content_json TEXT NOT NULL DEFAULT ''",
    "email_sent INTEGER NOT NULL DEFAULT 0",
    "email_sent_at TEXT NOT NULL DEFAULT ''",
    "email_error TEXT NOT NULL DEFAULT ''",
    # Team notification email (LEAD_NOTIFY_EMAILS) -- see
    # mga_lead_service.notify_team. Sent once per lead, never on retries.
    "team_notified_at TEXT NOT NULL DEFAULT ''",
    "team_notify_error TEXT NOT NULL DEFAULT ''",
    # Google Sheets mirror -- see app/services/sheets_sync.py.
    "sheet_synced_at TEXT NOT NULL DEFAULT ''",
    "sheet_sync_error TEXT NOT NULL DEFAULT ''",
]


class DatabaseError(RuntimeError):
    """A statement failed (either backend)."""


# --------------------------------------------------------------------------
# Turso (HTTP) backend
# --------------------------------------------------------------------------


def _turso_config() -> tuple[str, str] | None:
    url = os.environ.get("TURSO_DATABASE_URL", "").strip()
    if not url:
        return None
    for prefix in ("libsql://", "turso://", "wss://", "ws://"):
        if url.startswith(prefix):
            url = "https://" + url[len(prefix):]
            break
    return url.rstrip("/"), os.environ.get("TURSO_AUTH_TOKEN", "").strip()


def using_turso() -> bool:
    return _turso_config() is not None


def describe() -> str:
    """Where the data lives, for logs/health (never includes the token)."""
    cfg = _turso_config()
    return f"turso:{cfg[0]}" if cfg else str(DB_PATH)


def _to_turso_arg(value: Any) -> dict[str, Any]:
    if value is None:
        return {"type": "null", "value": None}
    if isinstance(value, bool):
        return {"type": "integer", "value": str(int(value))}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float", "value": value}
    return {"type": "text", "value": str(value)}


def _from_turso_value(cell: dict[str, Any]) -> Any:
    kind = cell.get("type")
    if kind == "null":
        return None
    if kind == "integer":
        return int(cell["value"])
    if kind == "float":
        return float(cell["value"])
    if kind == "blob":
        import base64

        return base64.b64decode(cell.get("base64", ""))
    return cell.get("value")


_http_client: httpx.Client | None = None


def _turso_client() -> httpx.Client:
    # One pooled client per process: warm Vercel instances reuse the TLS
    # connection instead of re-handshaking on every query.
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(timeout=20.0)
    return _http_client


def _turso_run(
    statements: list[tuple[str, Any]], *, ignore_errors: tuple[str, ...] = ()
) -> list[list[dict[str, Any]]]:
    """Runs statements in one HTTP round trip; returns one row list per
    statement. An error whose message contains one of `ignore_errors` is
    treated as an empty result (used for idempotent migrations)."""
    url, token = _turso_config()  # type: ignore[misc]
    requests = [
        {"type": "execute", "stmt": {"sql": sql, "args": [_to_turso_arg(v) for v in (params or ())]}}
        for sql, params in statements
    ]
    requests.append({"type": "close"})
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        resp = _turso_client().post(f"{url}/v2/pipeline", json={"requests": requests}, headers=headers)
    except httpx.HTTPError as exc:
        raise DatabaseError(f"Could not reach Turso: {exc}") from exc
    if resp.status_code >= 400:
        raise DatabaseError(f"Turso HTTP {resp.status_code}: {resp.text[:300]}")

    out: list[list[dict[str, Any]]] = []
    for result in resp.json().get("results", [])[: len(statements)]:
        if result.get("type") != "ok":
            message = (result.get("error") or {}).get("message", "unknown error")
            if any(marker in message.lower() for marker in ignore_errors):
                out.append([])
                continue
            raise DatabaseError(f"Turso query failed: {message}")
        res = result["response"]["result"]
        names = [c.get("name") for c in res.get("cols", [])]
        out.append(
            [dict(zip(names, (_from_turso_value(cell) for cell in row))) for row in res.get("rows", [])]
        )
    return out


# --------------------------------------------------------------------------
# Local SQLite backend
# --------------------------------------------------------------------------


def _sqlite_connect() -> sqlite3.Connection:
    # busy_timeout: a new connection is opened per call, and a read may
    # land while another request is writing to the same file.
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.row_factory = sqlite3.Row
    return conn


def _sqlite_run(statements: list[tuple[str, Any]]) -> list[list[dict[str, Any]]]:
    conn = _sqlite_connect()
    try:
        out = []
        for sql, params in statements:
            cur = conn.execute(sql, tuple(params or ()))
            out.append([dict(r) for r in cur.fetchall()])
        conn.commit()
        return out
    except sqlite3.Error as exc:
        raise DatabaseError(str(exc)) from exc
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Shared entry points
# --------------------------------------------------------------------------


# Databases whose tables are known to exist, keyed by where they live.
# Tables are created lazily on first use rather than only at import, so a
# brief Turso outage during a Vercel cold start doesn't crash the whole
# function -- the next request simply tries again.
_READY: set[str] = set()


def _ensure_ready() -> None:
    key = describe() + "|" + os.environ.get("TURSO_AUTH_TOKEN", "")
    if key not in _READY:
        init_app_tables()
        _READY.add(key)


def _query(sql: str, params: Any = ()) -> list[dict[str, Any]]:
    _ensure_ready()
    if using_turso():
        return _turso_run([(sql, params)])[0]
    return _sqlite_run([(sql, params)])[0]


def init_app_tables() -> None:
    statements = [s.strip() for s in _APP_SCHEMA.split(";")]
    # Drop comment-only chunks; keep each CREATE statement intact.
    statements = [
        s for s in statements
        if "\n".join(l for l in s.splitlines() if not l.strip().startswith("--")).strip()
    ]
    alters = [f"ALTER TABLE mga_leads ADD COLUMN {c}" for c in _MGA_LEADS_ADDED_COLUMNS]

    if using_turso():
        _turso_run([(s, ()) for s in statements])
        _turso_run([(a, ()) for a in alters], ignore_errors=("duplicate column",))
        return

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    try:
        conn.execute("PRAGMA busy_timeout=30000;")
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.executescript(_APP_SCHEMA)
        for alter in alters:
            try:
                conn.execute(alter)
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise
        conn.commit()
    finally:
        conn.close()


# Local SQLite: also create the tables at import time (cheap, no network)
# so scripts that never fire the ASGI startup event work as before. Turso
# is initialised lazily on first query instead -- see _ensure_ready().
if not using_turso():
    _ensure_ready()


# --------------------------------------------------------------------------
# mga_leads CRUD (see the table's own comment above and
# app/services/mga_lead_service.py).
# --------------------------------------------------------------------------

_MGA_LEAD_COLUMNS = [
    "id", "form_submission_id", "source_type", "status", "last_completed_stage",
    "failed_stage", "error_message", "name", "email", "phone", "source_campaign",
    "raw_answers_json", "profile_json", "lead_magnet_type", "lead_magnet_id",
    "lead_magnet_path", "lead_magnet_content_json", "delivered_at",
    "email_sent", "email_sent_at", "email_error",
    "team_notified_at", "team_notify_error",
    "sheet_synced_at", "sheet_sync_error",
    "submitted_at", "created_at", "updated_at",
]


def insert_mga_lead(row: dict[str, Any]) -> None:
    payload = {c: row.get(c, "") for c in _MGA_LEAD_COLUMNS}
    placeholders = ", ".join("?" for _ in _MGA_LEAD_COLUMNS)
    with _WRITE_LOCK:
        _query(
            f"INSERT INTO mga_leads ({', '.join(_MGA_LEAD_COLUMNS)}) VALUES ({placeholders})",
            [payload[c] for c in _MGA_LEAD_COLUMNS],
        )


def update_mga_lead(lead_id: str, updates: dict[str, Any]) -> None:
    columns = [c for c in (updates or {}) if c in _MGA_LEAD_COLUMNS]
    if not columns:
        return
    set_clause = ", ".join(f"{c}=?" for c in columns)
    values = [updates[c] for c in columns] + [lead_id]
    with _WRITE_LOCK:
        _query(f"UPDATE mga_leads SET {set_clause} WHERE id = ?", values)


def _one(sql: str, params: Any) -> dict[str, Any] | None:
    rows = _query(sql, params)
    return rows[0] if rows else None


def get_mga_lead(lead_id: str) -> dict[str, Any] | None:
    return _one("SELECT * FROM mga_leads WHERE id = ?", (lead_id,))


def get_mga_lead_by_submission_id(form_submission_id: str) -> dict[str, Any] | None:
    return _one("SELECT * FROM mga_leads WHERE form_submission_id = ?", (form_submission_id,))


def get_mga_lead_by_magnet_id(lead_magnet_id: str) -> dict[str, Any] | None:
    return _one("SELECT * FROM mga_leads WHERE lead_magnet_id = ?", (lead_magnet_id,))


def list_mga_leads(
    *, status: str | None = None, limit: int = 50, offset: int = 0
) -> tuple[list[dict[str, Any]], int]:
    if status:
        total = _query("SELECT COUNT(*) AS n FROM mga_leads WHERE status = ?", (status,))[0]["n"]
        rows = _query(
            "SELECT * FROM mga_leads WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (status, limit, offset),
        )
    else:
        total = _query("SELECT COUNT(*) AS n FROM mga_leads")[0]["n"]
        rows = _query(
            "SELECT * FROM mga_leads ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
    return rows, total


def count_mga_leads_by_status() -> dict[str, int]:
    rows = _query("SELECT status, COUNT(*) AS n FROM mga_leads GROUP BY status")
    return {r["status"]: r["n"] for r in rows}
