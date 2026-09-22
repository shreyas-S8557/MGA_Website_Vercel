"""Database access for the backend.

One table, `mga_leads`, in a single SQLite file (app.config.DB_PATH). Each
row is one website-quiz / Google Form submission and tracks it through the
lead-magnet pipeline (see app/services/mga_lead_service.py).

We use raw sqlite3 rather than an ORM -- it's one table.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterator

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
# locked" retries entirely for a single-process backend.
_WRITE_LOCK = threading.Lock()


# Columns added to mga_leads after it first shipped. `CREATE TABLE IF NOT
# EXISTS` above only creates the table on a brand-new DB file; an existing
# DB file (anyone who already has leads in it) needs these added in place.
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
]


def _migrate_mga_leads_columns(conn: sqlite3.Connection) -> None:
    for column_def in _MGA_LEADS_ADDED_COLUMNS:
        try:
            conn.execute(f"ALTER TABLE mga_leads ADD COLUMN {column_def}")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                raise


def init_app_tables() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    try:
        conn.execute("PRAGMA busy_timeout=30000;")
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.executescript(_APP_SCHEMA)
        _migrate_mga_leads_columns(conn)
        conn.commit()
    finally:
        conn.close()


# Also run at import time (not just FastAPI startup) so this module works
# correctly under test clients / scripts that never fire the ASGI startup
# event.
init_app_tables()


@contextmanager
def _app_cursor() -> Iterator[sqlite3.Cursor]:
    # busy_timeout: a new connection is opened per call, and a read may
    # land while another request is writing to the same file.
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    finally:
        conn.close()


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
    "submitted_at", "created_at", "updated_at",
]


def insert_mga_lead(row: dict[str, Any]) -> None:
    payload = {c: row.get(c, "") for c in _MGA_LEAD_COLUMNS}
    placeholders = ", ".join("?" for _ in _MGA_LEAD_COLUMNS)
    with _WRITE_LOCK, _app_cursor() as cur:
        cur.execute(
            f"INSERT INTO mga_leads ({', '.join(_MGA_LEAD_COLUMNS)}) VALUES ({placeholders})",
            [payload[c] for c in _MGA_LEAD_COLUMNS],
        )


def update_mga_lead(lead_id: str, updates: dict[str, Any]) -> None:
    if not updates:
        return
    columns = [c for c in updates if c in _MGA_LEAD_COLUMNS]
    set_clause = ", ".join(f"{c}=?" for c in columns)
    values = [updates[c] for c in columns] + [lead_id]
    with _WRITE_LOCK, _app_cursor() as cur:
        cur.execute(f"UPDATE mga_leads SET {set_clause} WHERE id = ?", values)


def get_mga_lead(lead_id: str) -> dict[str, Any] | None:
    with _app_cursor() as cur:
        cur.execute("SELECT * FROM mga_leads WHERE id = ?", (lead_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_mga_lead_by_submission_id(form_submission_id: str) -> dict[str, Any] | None:
    with _app_cursor() as cur:
        cur.execute(
            "SELECT * FROM mga_leads WHERE form_submission_id = ?", (form_submission_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_mga_lead_by_magnet_id(lead_magnet_id: str) -> dict[str, Any] | None:
    with _app_cursor() as cur:
        cur.execute("SELECT * FROM mga_leads WHERE lead_magnet_id = ?", (lead_magnet_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def list_mga_leads(
    *, status: str | None = None, limit: int = 50, offset: int = 0
) -> tuple[list[dict[str, Any]], int]:
    with _app_cursor() as cur:
        if status:
            cur.execute("SELECT COUNT(*) AS n FROM mga_leads WHERE status = ?", (status,))
        else:
            cur.execute("SELECT COUNT(*) AS n FROM mga_leads")
        total = cur.fetchone()["n"]

        if status:
            cur.execute(
                "SELECT * FROM mga_leads WHERE status = ? "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (status, limit, offset),
            )
        else:
            cur.execute(
                "SELECT * FROM mga_leads ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        return [dict(r) for r in cur.fetchall()], total


def count_mga_leads_by_status() -> dict[str, int]:
    with _app_cursor() as cur:
        cur.execute("SELECT status, COUNT(*) AS n FROM mga_leads GROUP BY status")
        return {r["status"]: r["n"] for r in cur.fetchall()}
