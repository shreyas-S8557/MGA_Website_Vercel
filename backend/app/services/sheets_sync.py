"""Mirror every lead into a Google Sheet.

Turso (or the local SQLite file) stays the source of truth -- the pipeline,
retries and dashboard all read from it. On top of that, each lead is
written to a Google Sheet as one row, and that same row is updated in place
(matched on "Lead ID") whenever the lead changes, so the sheet always shows
the latest status.

How it talks to Google: a tiny Apps Script web app that lives inside the
spreadsheet (google-apps-script/LeadsSheet.gs) receives a JSON POST and
writes the rows. That needs no Google Cloud project, service account or
extra Python packages -- just two env vars:

  GOOGLE_SHEETS_WEBHOOK_URL     the web app's .../exec URL
  GOOGLE_SHEETS_WEBHOOK_SECRET  any long random string, also saved in the
                                script's Script Properties as SHEET_SECRET

Best-effort, like email: a sheet problem never fails or slows down a lead
beyond the short timeout below. The outcome is recorded on the lead
(sheet_synced_at / sheet_sync_error), and POST /api/dashboard/sheets/sync-all
re-sends everything (use it once to backfill leads you already have).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import httpx

_TIMEOUT_SECONDS = 10.0
_BATCH_SIZE = 50

_SOURCE_LABELS = {
    "inbound_website_form": "Website quiz",
    "inbound_google_form": "Google Form",
}


def is_enabled() -> bool:
    import app.config as config

    return bool(config.GOOGLE_SHEETS_WEBHOOK_URL and config.GOOGLE_SHEETS_WEBHOOK_SECRET)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def lead_to_sheet_row(row: dict[str, Any]) -> dict[str, Any]:
    """The lead as {column header: value}. Fixed columns first, then one
    column per quiz question (the Apps Script adds new question columns
    automatically the first time it sees them)."""
    from app.services.mga_lead_service import build_delivery_url

    try:
        answers = json.loads(row.get("raw_answers_json") or "{}")
    except (TypeError, ValueError):
        answers = {}

    magnet_id = row.get("lead_magnet_id") or ""
    fields: dict[str, Any] = {
        "Lead ID": row.get("id") or "",
        "Submitted": row.get("submitted_at") or row.get("created_at") or "",
        "Name": row.get("name") or "",
        "Email": row.get("email") or "",
        "Phone": row.get("phone") or "",
        "Source": _SOURCE_LABELS.get(row.get("source_type") or "", row.get("source_type") or ""),
        "Campaign": row.get("source_campaign") or "",
        "Status": row.get("status") or "",
        "Report Type": row.get("lead_magnet_type") or "",
        "PDF Link": build_delivery_url(magnet_id) if magnet_id else "",
        "Email Sent": "Yes" if row.get("email_sent") else "No",
        "Email Error": row.get("email_error") or "",
        "Team Notified": row.get("team_notified_at") or "",
        "Error": row.get("error_message") or "",
        "Last Updated": row.get("updated_at") or "",
    }
    for question, answer in answers.items():
        if str(question).startswith("__") or answer in (None, "", []):
            continue
        header = f"Q: {question}"
        fields[header] = ", ".join(map(str, answer)) if isinstance(answer, list) else str(answer)
    return fields


def _post(rows: list[dict[str, Any]]) -> str:
    """Send rows to the Apps Script. Returns "" on success, else an error."""
    import app.config as config

    payload = {"secret": config.GOOGLE_SHEETS_WEBHOOK_SECRET, "leads": rows}
    try:
        # Apps Script answers a POST with a 302 to the actual response;
        # follow it to read whether the write worked.
        with httpx.Client(timeout=_TIMEOUT_SECONDS, follow_redirects=True) as client:
            resp = client.post(config.GOOGLE_SHEETS_WEBHOOK_URL, json=payload)
    except httpx.HTTPError as exc:
        return f"Could not reach the Google Sheet: {exc}"[:500]
    if resp.status_code >= 400:
        return f"Google Sheet HTTP {resp.status_code}: {resp.text[:200]}"
    try:
        body = resp.json()
    except ValueError:
        # Usually an HTML sign-in page: the web app isn't deployed with
        # "Who has access: Anyone".
        return (
            "Google Sheet did not return JSON. Check the web app is deployed with "
            "'Execute as: Me' and 'Who has access: Anyone'."
        )
    if not body.get("ok"):
        return f"Google Sheet refused the write: {body.get('error') or 'unknown error'}"[:500]
    return ""


def sync_lead(row: dict[str, Any] | None) -> str:
    """Upsert one lead into the sheet and record the outcome on the lead.
    Never raises. Returns "" on success (or when the sheet is switched off),
    else the error message."""
    if not row or not is_enabled():
        return ""
    from app.db import database

    try:
        error = _post([lead_to_sheet_row(row)])
    except Exception as exc:  # noqa: BLE001 -- the sheet must never break lead intake
        error = f"Google Sheet sync failed: {exc}"[:500]
    try:
        updates = {"sheet_sync_error": error}
        if not error:
            updates["sheet_synced_at"] = _now()
        database.update_mga_lead(row["id"], updates)
    except Exception:  # noqa: BLE001
        pass
    return error


def sync_all() -> dict[str, Any]:
    """Re-send every lead in the database (in batches). For backfilling
    leads collected before the sheet was connected, or repairing a sheet
    someone edited by hand."""
    if not is_enabled():
        return {"enabled": False, "synced": 0, "errors": ["GOOGLE_SHEETS_WEBHOOK_URL / _SECRET not set."]}
    from app.db import database

    all_rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        rows, total = database.list_mga_leads(limit=200, offset=offset)
        all_rows.extend(rows)
        offset += len(rows)
        if not rows or offset >= total:
            break
    # The database lists newest first; send oldest first so new rows land
    # in the sheet top-to-bottom in submission order.
    all_rows.reverse()

    synced, errors = 0, []
    for i in range(0, len(all_rows), _BATCH_SIZE):
        batch = all_rows[i : i + _BATCH_SIZE]
        error = _post([lead_to_sheet_row(r) for r in batch])
        if error:
            errors.append(error)
        else:
            synced += len(batch)
    return {"enabled": True, "synced": synced, "total": len(all_rows), "errors": errors}
