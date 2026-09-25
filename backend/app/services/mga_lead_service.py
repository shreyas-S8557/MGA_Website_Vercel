"""
The MGA lead-magnet pipeline.

A visitor fills out the website's "3-Year Future Snapshot" quiz (or the
optional Google Form); this module profiles their answers, generates a
personalized lead-magnet PDF, and delivers it.

    RECEIVED -> NORMALIZED -> PROFILED -> LEAD_MAGNET_GENERATING
             -> LEAD_MAGNET_READY -> DELIVERY_QUEUED -> DELIVERED

"Delivery" here means two things, both handled by `_deliver` below: the
personalized PDF is made available for download through this backend's own
API/dashboard (see `build_delivery_url` / `GET /api/lead-magnets/
{lead_magnet_id}` in app/api/mga_leads.py) AND, best-effort, emailed
straight to the lead via app.services.sending_service. The email send is
gated by the PROSPECT_ALLOW_LIVE_SEND/EMAIL_PROVIDER safety switches, is
never allowed to fail this stage (an ESP hiccup must not make
an already-generated report disappear), and its outcome is recorded
separately on the row (email_sent/email_sent_at/email_error) rather than
folded into `status`.

Runs synchronously inside the request: it processes exactly one lead per
call and finishes in low single-digit seconds even with a live LLM call,
well inside Google Apps Script's own request timeout. A failure at any stage is caught, recorded on the row (status
-> "failed", failed_stage + error_message set, last_completed_stage left
untouched), and is safe to retry: run_pipeline() always resumes from
last_completed_stage, never redoing a stage that already succeeded and
never re-marking an already-delivered lead.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import PUBLIC_API_BASE_URL, PUBLIC_SITE_DISPLAY, PUBLIC_SITE_URL
from app.db import database
from app.services import lead_magnet_service, lead_profile_service, pdf_service

_STAGE_ORDER = [
    "received",
    "normalized",
    "profiled",
    "lead_magnet_generating",
    "lead_magnet_ready",
    "delivery_queued",
    "delivered",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_delivery_url(lead_magnet_id: str) -> str:
    return f"{PUBLIC_API_BASE_URL.rstrip('/')}/api/lead-magnets/{lead_magnet_id}"


# --------------------------------------------------------------------------
# Row <-> dict helpers (raw sqlite3 rows are already dicts via
# database.py's sqlite3.Row factory; these just add the JSON (de)serialize
# step).
# --------------------------------------------------------------------------


def _load_json(text: str, default: Any) -> Any:
    import json

    if not text:
        return default
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return default


def _dump_json(value: Any) -> str:
    import json

    return json.dumps(value)


def to_summary_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "form_submission_id": row["form_submission_id"],
        "source_type": row["source_type"],
        "status": row["status"],
        "failed_stage": row.get("failed_stage") or "",
        "name": row.get("name") or "",
        "email": row.get("email") or "",
        "lead_magnet_type": row.get("lead_magnet_type") or "",
        "email_sent": bool(row.get("email_sent")),
        "submitted_at": row.get("submitted_at") or "",
        "created_at": row.get("created_at") or "",
    }


def to_detail_dict(row: dict[str, Any]) -> dict[str, Any]:
    data = to_summary_dict(row)
    lead_magnet_id = row.get("lead_magnet_id") or ""
    data.update(
        {
            "phone": row.get("phone") or "",
            "source_campaign": row.get("source_campaign") or "",
            "raw_answers": _load_json(row.get("raw_answers_json", ""), {}),
            "profile": _load_json(row.get("profile_json", ""), None),
            "lead_magnet_id": lead_magnet_id,
            "lead_magnet_delivery_url": (
                f"/api/lead-magnets/{lead_magnet_id}" if lead_magnet_id else None
            ),
            "delivered_at": row.get("delivered_at") or "",
            "email_sent": bool(row.get("email_sent")),
            "email_sent_at": row.get("email_sent_at") or "",
            "email_error": row.get("email_error") or "",
            "team_notified_at": row.get("team_notified_at") or "",
            "team_notify_error": row.get("team_notify_error") or "",
            "sheet_synced_at": row.get("sheet_synced_at") or "",
            "sheet_sync_error": row.get("sheet_sync_error") or "",
            "error_message": row.get("error_message") or "",
            "updated_at": row.get("updated_at") or "",
        }
    )
    return data


# --------------------------------------------------------------------------
# Ingestion
# --------------------------------------------------------------------------


def create_or_get_existing(
    payload: dict[str, Any], *, source_type: str = "inbound_google_form"
) -> tuple[dict[str, Any], bool]:
    """Idempotent create. Returns (row, was_duplicate). A retried Apps
    Script POST for the same form_submission_id returns the existing row
    untouched -- never a second insert, never a second pipeline run.

    `source_type` distinguishes the two inbound sources that share this
    same pipeline: "inbound_google_form" (Apps Script webhook, requires the
    shared secret) and "inbound_website_form" (the website's own on-page
    lead-magnet form, posted directly by the visitor's browser -- see
    app/api/mga_leads.py's POST /api/leads/website)."""
    existing = database.get_mga_lead_by_submission_id(payload["form_submission_id"])
    if existing:
        return existing, True

    now = _utc_now_iso()
    answers = dict(payload.get("answers") or {})
    if payload.get("field_map"):
        answers["__field_map__"] = payload["field_map"]

    row = {
        "id": uuid.uuid4().hex,
        "form_submission_id": payload["form_submission_id"],
        "source_type": source_type,
        "status": "received",
        "last_completed_stage": "received",
        "failed_stage": "",
        "error_message": "",
        "name": payload.get("name") or "",
        "email": payload.get("email") or "",
        "phone": payload.get("phone") or "",
        "source_campaign": payload.get("source_campaign") or "",
        "raw_answers_json": _dump_json(answers),
        "profile_json": "",
        "lead_magnet_type": "",
        "lead_magnet_id": "",
        "lead_magnet_path": "",
        "lead_magnet_content_json": "",
        "delivered_at": "",
        "email_sent": 0,
        "email_sent_at": "",
        "email_error": "",
        "submitted_at": (
            payload["submitted_at"].isoformat()
            if payload.get("submitted_at")
            else now
        ),
        "created_at": now,
        "updated_at": now,
    }
    database.insert_mga_lead(row)
    return row, False


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------


def run_pipeline(lead_id: str) -> dict[str, Any]:
    """Advances the lead through every remaining stage, resuming from
    `last_completed_stage`. Safe to call repeatedly: calling it on an
    already-DELIVERED lead is a no-op (no duplicate email); calling it on a
    FAILED lead re-runs only the stage(s) that never finished."""
    row = database.get_mga_lead(lead_id)
    if row is None:
        raise LookupError(f"MGA lead {lead_id!r} not found")

    last_completed = row.get("last_completed_stage") or "received"
    start_index = _STAGE_ORDER.index(last_completed) if last_completed in _STAGE_ORDER else 0

    try:
        if start_index < _STAGE_ORDER.index("normalized"):
            row = _normalize(row)
            row = _advance(row, "normalized")

        if start_index < _STAGE_ORDER.index("profiled"):
            row = _profile(row)
            row = _advance(row, "profiled")

        if start_index < _STAGE_ORDER.index("lead_magnet_ready"):
            database.update_mga_lead(row["id"], {"status": "lead_magnet_generating"})
            row = _generate_lead_magnet(row)
            row = _advance(row, "lead_magnet_ready")

        if start_index < _STAGE_ORDER.index("delivered"):
            database.update_mga_lead(row["id"], {"status": "delivery_queued"})
            row = _deliver(row)
            row = _advance(row, "delivered")

    except Exception as exc:  # noqa: BLE001 -- a failure must be recorded, never silently swallowed, and must never take the webhook request down with it
        next_stage = _stage_after(row.get("last_completed_stage") or "received")
        database.update_mga_lead(
            row["id"],
            {
                "status": "failed",
                "failed_stage": next_stage,
                "error_message": str(exc)[:2000],
                "updated_at": _utc_now_iso(),
            },
        )
        return database.get_mga_lead(row["id"])

    return row


def retry(lead_id: str) -> dict[str, Any]:
    row = run_pipeline(lead_id)
    _sync_sheet(row["id"])
    return database.get_mga_lead(row["id"]) or row


def _sync_sheet(lead_id: str) -> None:
    """Best-effort copy of the lead's latest state into the Google Sheet
    (a no-op unless GOOGLE_SHEETS_WEBHOOK_URL is set). Never raises."""
    from app.services import sheets_sync

    try:
        sheets_sync.sync_lead(database.get_mga_lead(lead_id))
    except Exception:  # noqa: BLE001 -- the sheet must never affect the lead
        pass


def _advance(row: dict[str, Any], stage: str) -> dict[str, Any]:
    updates = {
        "status": stage,
        "last_completed_stage": stage,
        "failed_stage": "",
        "error_message": "",
        "updated_at": _utc_now_iso(),
    }
    database.update_mga_lead(row["id"], updates)
    return database.get_mga_lead(row["id"])


def _stage_after(last_completed: str) -> str:
    idx = _STAGE_ORDER.index(last_completed) if last_completed in _STAGE_ORDER else 0
    return _STAGE_ORDER[min(idx + 1, len(_STAGE_ORDER) - 1)]


def _normalize(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("name") and row.get("email"):
        return row
    answers = _load_json(row.get("raw_answers_json", ""), {})
    contact = lead_profile_service.extract_contact_fields(answers)
    updates = {}
    if not row.get("name") and contact.get("name"):
        updates["name"] = contact["name"]
    if not row.get("email") and contact.get("email"):
        updates["email"] = contact["email"]
    if not row.get("phone") and contact.get("phone"):
        updates["phone"] = contact["phone"]
    if updates:
        database.update_mga_lead(row["id"], updates)
        return database.get_mga_lead(row["id"])
    return row


def _profile(row: dict[str, Any]) -> dict[str, Any]:
    answers = _load_json(row.get("raw_answers_json", ""), {})
    field_map = answers.get("__field_map__")
    profile = lead_profile_service.determine_lead_profile(answers, field_map)
    database.update_mga_lead(row["id"], {"profile_json": _dump_json(profile)})
    return database.get_mga_lead(row["id"])


def _generate_lead_magnet(row: dict[str, Any]) -> dict[str, Any]:
    profile = _load_json(row.get("profile_json", ""), {})
    magnet_type = lead_magnet_service.select_lead_magnet(profile)
    content = lead_magnet_service.generate_personalized_content(profile)
    magnet_id = row.get("lead_magnet_id") or lead_magnet_service.generate_secure_lead_magnet_id()
    title = lead_magnet_service.select_lead_magnet_title(magnet_type)
    path = pdf_service.render_lead_magnet(
        magnet_id, title, content, recipient_name=row.get("name"), profile=profile
    )

    database.update_mga_lead(
        row["id"],
        {
            "lead_magnet_type": magnet_type,
            "lead_magnet_id": magnet_id,
            "lead_magnet_path": path,
            # Kept alongside the rendered PDF so _deliver can embed the same
            # copy inline in the delivery email without re-generating it.
            "lead_magnet_content_json": _dump_json({"title": title, **content}),
        },
    )
    return database.get_mga_lead(row["id"])


def _deliver(row: dict[str, Any]) -> dict[str, Any]:
    """Makes the already-generated lead magnet available via this
    backend's own download route/dashboard, AND (best-effort) emails the
    personalized report straight to the lead.

    The download link is the part that must never fail this stage: it
    only needs the PDF to already exist on disk, has no external network
    dependency, and fails closed (raises, so run_pipeline marks the lead
    FAILED) if the prior stage somehow didn't leave a usable
    lead_magnet_id/path.

    The email send is additive and deliberately NOT allowed to fail this
    stage or flip the lead to FAILED -- an ESP hiccup must never make an
    already-generated report disappear or block a retry loop. Whether it
    went out is recorded on the row (email_sent/email_sent_at/email_error)
    independently of `status`/`delivered_at` so the dashboard can show
    "magnet ready, email not sent yet" distinctly from a real failure."""
    if not row.get("lead_magnet_id") or not row.get("lead_magnet_path"):
        raise ValueError("Cannot make lead magnet available: it was not generated.")

    # build_delivery_url is exercised here (and by app/api/mga_leads.py's
    # to_detail_dict) purely to confirm the id resolves to a servable
    # link; nothing is sent anywhere with it.
    build_delivery_url(row["lead_magnet_id"])

    updates: dict[str, Any] = {"delivered_at": _utc_now_iso()}
    updates.update(_send_report_email(row))
    list_error = _add_to_mailerlite_list(row)
    if list_error:
        updates["email_error"] = "; ".join(
            e for e in (updates.get("email_error", ""), list_error) if e
        )[:2000]

    database.update_mga_lead(row["id"], updates)
    return database.get_mga_lead(row["id"])


def ensure_lead_magnet_file(row: dict[str, Any]) -> str | None:
    """Path to the lead's PDF, re-rendering it first if the file is gone.

    On Render the filesystem is wiped on every deploy/restart unless a
    persistent disk is attached (DATA_DIR), so a PDF generated yesterday
    can be missing today even though the lead row still exists. Everything
    needed to rebuild it (content, profile, name) is stored on the row, so
    the same PDF is rebuilt on demand instead of the download link 404ing.
    Also copes with a stored absolute path that moved (e.g. DATA_DIR
    changed). Returns None if the lead never had a report generated."""
    import os

    import app.config as config

    magnet_id = row.get("lead_magnet_id") or ""
    if not magnet_id:
        return None

    stored = row.get("lead_magnet_path") or ""
    if stored and os.path.isfile(stored):
        return stored
    expected = os.path.join(config.MGA_LEAD_MAGNET_DIR, f"{magnet_id}.pdf")
    if os.path.isfile(expected):
        path = expected
    else:
        content = _load_json(row.get("lead_magnet_content_json", ""), {})
        if not content:
            return None
        title = content.pop("title", "") or lead_magnet_service.select_lead_magnet_title(
            row.get("lead_magnet_type") or ""
        )
        profile = _load_json(row.get("profile_json", ""), {})
        path = pdf_service.render_lead_magnet(
            magnet_id, title, content, recipient_name=row.get("name"), profile=profile
        )
    if path != stored and row.get("id"):
        database.update_mga_lead(row["id"], {"lead_magnet_path": path})
    return path


def _add_to_mailerlite_list(row: dict[str, Any]) -> str:
    """Best-effort: add the lead (name, email, phone) to the MailerLite group
    in MAILERLITE_LEADS_GROUP_ID, e.g. "MGA New Website Subs". Only when live
    sending is on and a MailerLite provider is in use. Returns an error
    message, or "" on success / when switched off. Never raises."""
    import app.config as config

    group_id = config.MAILERLITE_LEADS_GROUP_ID
    email = (row.get("email") or "").strip()
    if not group_id or not email or not config.ALLOW_LIVE_SEND:
        return ""
    if config.EMAIL_PROVIDER not in ("mailerlite", "mailerlite_classic"):
        return ""
    from app.services.sending_service import SendModeNotAllowed, get_sender

    try:
        sender = get_sender("live")
        result = sender.add_to_list(
            email, row.get("name") or "", row.get("phone") or "",
            group_id=group_id,
            trigger_automations=config.MAILERLITE_LEADS_TRIGGER_AUTOMATIONS,
        )
    except SendModeNotAllowed:
        return ""
    except Exception as exc:  # noqa: BLE001 -- list sync must never affect delivery
        return f"Adding to MailerLite list failed: {exc}"[:500]
    return "" if result.success else (result.error or "Adding to MailerLite list failed.")


def _send_report_email(row: dict[str, Any]) -> dict[str, Any]:
    """Best-effort send of the personalized report to the lead's email.
    Never raises -- always returns a dict of column updates
    (email_sent/email_sent_at/email_error) for the caller to persist.

    Uses app.services.sending_service -- PROSPECT_ALLOW_LIVE_SEND gates any
    real network send, EMAIL_PROVIDER picks MailerLite vs. Gmail."""
    to_email = (row.get("email") or "").strip()
    if not to_email:
        return {"email_sent": 0, "email_error": "No email address on file."}

    from app.services.sending_service import SendModeNotAllowed, get_sender

    try:
        sender = get_sender("live")
    except SendModeNotAllowed as exc:
        # Not a failure worth alarming over -- this is the deliberate
        # "live sending is off by default" safety switch (see README.md).
        # The PDF is still available for download either way.
        return {"email_sent": 0, "email_error": str(exc)}

    content = _load_json(row.get("lead_magnet_content_json", ""), {})
    # Gmail can carry the PDF as an attachment; MailerLite campaigns can't,
    # so there the email's big button is the way to get it.
    from app.senders.gmail_sender import GmailSender

    pdf_path = _safe_pdf_path(row) if isinstance(sender, GmailSender) else None
    subject, body_html = _build_report_email(row, content, pdf_attached=bool(pdf_path))

    try:
        result = sender.send(
            to_email,
            subject,
            body_html,
            from_name=_email_from_name(),
            attachments=(
                [(pdf_path, "My-Growth-Academy-Growth-Blueprint.pdf")] if pdf_path else None
            ),
        )
    except Exception as exc:  # noqa: BLE001 -- an ESP/network error must never break delivery
        return {"email_sent": 0, "email_error": str(exc)[:2000]}

    if result.success:
        return {"email_sent": 1, "email_sent_at": _utc_now_iso(), "email_error": ""}
    return {"email_sent": 0, "email_error": (result.error or "Send failed.")[:2000]}


def _email_from_name() -> str:
    import app.config as config

    return config.EMAIL_FROM_NAME


def _safe_pdf_path(row: dict[str, Any]) -> str | None:
    """ensure_lead_magnet_file, but an attachment problem never blocks the
    email itself (the body still carries the download link)."""
    try:
        return ensure_lead_magnet_file(row)
    except Exception:  # noqa: BLE001
        return None


def _build_report_email(
    row: dict[str, Any], content: dict[str, Any], *, pdf_attached: bool = False
) -> tuple[str, str]:
    """Subject + HTML body of the delivery email: a short note, a button to
    the PDF, and a "Book a Free Call" button to Kanth & Shaku's Calendly.
    The design lives in app/services/email_templates.py."""
    import app.config as config
    from app.services.email_templates import build_report_email

    magnet_id = row.get("lead_magnet_id", "")
    return build_report_email(
        name=(row.get("name") or "").strip(),
        content=content,
        download_url=build_delivery_url(magnet_id) if magnet_id else "",
        booking_url=config.BOOKING_URL,
        booking_label=config.BOOKING_LABEL,
        site_url=PUBLIC_SITE_URL,
        site_display=PUBLIC_SITE_DISPLAY,
        logo_url=f"{PUBLIC_SITE_URL}/images/logo.png",
        pdf_attached=pdf_attached,
    )


# --------------------------------------------------------------------------
# Team notification (LEAD_NOTIFY_EMAILS)
# --------------------------------------------------------------------------


def process_new_lead(lead_id: str) -> dict[str, Any]:
    """What both inbound routes run for a brand-new (non-duplicate) lead:
    the full pipeline, then one heads-up email to the team. The
    notification goes out whatever the pipeline outcome -- a lead whose
    PDF failed to generate is still a real person who asked to hear from
    you, and the email says so."""
    row = run_pipeline(lead_id)
    notify_team(row)
    _sync_sheet(lead_id)
    return database.get_mga_lead(lead_id) or row


def notify_team(row: dict[str, Any]) -> dict[str, Any]:
    """Best-effort email to everyone in LEAD_NOTIFY_EMAILS about a new
    lead. Never raises, and never touches the lead's `status`: a
    notification problem must not affect the visitor's own report. Sent at
    most once per lead (guarded by team_notified_at), so pipeline retries
    never re-notify. The outcome is recorded on the row
    (team_notified_at / team_notify_error) and returned."""
    import app.config as config  # re-read so tests/env reloads take effect

    recipients = list(config.LEAD_NOTIFY_EMAILS)
    if not recipients or row.get("team_notified_at"):
        return {}

    from app.services.sending_service import SendModeNotAllowed, get_sender

    try:
        sender = get_sender("live", provider=config.TEAM_EMAIL_PROVIDER)
    except SendModeNotAllowed as exc:
        updates = {"team_notify_error": str(exc)[:2000]}
        database.update_mga_lead(row["id"], updates)
        return updates

    subject, body_html = _build_team_notification(row)
    errors: list[str] = []
    sent_any = False
    for to_email in recipients:
        try:
            result = sender.send(to_email, subject, body_html, from_name="MGA Website Leads")
        except Exception as exc:  # noqa: BLE001 -- never break lead intake over a notification
            errors.append(f"{to_email}: {exc}")
            continue
        if result.success:
            sent_any = True
        else:
            errors.append(f"{to_email}: {result.error or 'Send failed.'}")

    updates: dict[str, Any] = {"team_notify_error": "; ".join(errors)[:2000]}
    if sent_any:
        updates["team_notified_at"] = _utc_now_iso()
    database.update_mga_lead(row["id"], updates)
    return updates


def _build_team_notification(row: dict[str, Any]) -> tuple[str, str]:
    import html as _html

    esc = lambda v: _html.escape(str(v or ""))  # noqa: E731
    name = (row.get("name") or "").strip() or "(no name given)"
    email = (row.get("email") or "").strip()
    phone = (row.get("phone") or "").strip()
    source = {
        "inbound_website_form": "Website quiz",
        "inbound_google_form": "Google Form",
    }.get(row.get("source_type") or "", row.get("source_type") or "")

    answers = _load_json(row.get("raw_answers_json", ""), {})
    answer_rows = "".join(
        f'<tr><td style="padding:6px 12px 6px 0;color:#36488F;vertical-align:top;'
        f'font-weight:bold;">{esc(q)}</td><td style="padding:6px 0;color:#424242;">'
        f"{esc(', '.join(map(str, a)) if isinstance(a, list) else a)}</td></tr>"
        for q, a in answers.items()
        if not str(q).startswith("__") and a not in (None, "", [])
    )

    if row.get("status") == "failed":
        report_line = (
            '<p style="color:#C84739;">Their personalised report could not be '
            f"generated ({esc(row.get('error_message'))[:300]}). You can retry it "
            "from the leads dashboard.</p>"
        )
    elif row.get("lead_magnet_id"):
        url = build_delivery_url(row["lead_magnet_id"])
        emailed = "was also emailed to them" if row.get("email_sent") else "was NOT emailed to them (email sending is off or failed)"
        report_line = (
            f'<p style="color:#424242;">Their personalised Growth Blueprint is ready and {emailed}. '
            f'<a href="{esc(url)}">Open the PDF they received</a>.</p>'
        )
    else:
        report_line = ""

    contact_bits = [f'<a href="mailto:{esc(email)}">{esc(email)}</a>' if email else ""]
    if phone:
        contact_bits.append(esc(phone))
    contact = " &middot; ".join(b for b in contact_bits if b) or "(no contact details)"

    body_html = f"""
    <div style="max-width:600px;margin:0 auto;font-family:sans-serif;">
      <h1 style="color:#36488F;font-size:20px;margin-bottom:4px;">New lead: {esc(name)}</h1>
      <p style="color:#424242;margin-top:0;">{contact}</p>
      <p style="color:#8F8F8F;font-size:13px;">Source: {esc(source)} &middot; Submitted: {esc(row.get("submitted_at"))}</p>
      {report_line}
      {'<h3 style="color:#36488F;margin-top:24px;">Their answers</h3><table style="border-collapse:collapse;font-size:14px;">' + answer_rows + '</table>' if answer_rows else ''}
      <p style="color:#8F8F8F;font-size:12px;margin-top:32px;">
        Sent automatically by the My Growth Academy website because this
        address is listed in LEAD_NOTIFY_EMAILS.
      </p>
    </div>
    """
    return f"New MGA lead: {name}", body_html


# --------------------------------------------------------------------------
# Dashboard reads
# --------------------------------------------------------------------------


def list_leads(*, status: str | None = None, limit: int = 50, offset: int = 0):
    rows, total = database.list_mga_leads(status=status, limit=limit, offset=offset)
    return [to_summary_dict(r) for r in rows], total


def get_lead_detail(lead_id: str) -> dict[str, Any] | None:
    row = database.get_mga_lead(lead_id)
    return to_detail_dict(row) if row else None


def summary() -> dict[str, Any]:
    counts = database.count_mga_leads_by_status()
    by_status = {stage: counts.get(stage, 0) for stage in _STAGE_ORDER + ["failed"]}
    total = sum(by_status.values())
    return {
        "total_submissions": total,
        "new_leads": by_status["received"] + by_status["normalized"],
        "profiled_leads": by_status["profiled"],
        "lead_magnets_generated": (
            by_status["lead_magnet_ready"] + by_status["delivery_queued"] + by_status["delivered"]
        ),
        "lead_magnets_delivered": by_status["delivered"],
        "failed": by_status["failed"],
        "by_status": by_status,
    }
