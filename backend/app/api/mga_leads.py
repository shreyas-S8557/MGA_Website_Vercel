"""
Lead-magnet routes: the website quiz submission, the optional Google Form
webhook, retry, the PDF download, and the dashboard reads behind the
frontend's "MGA Leads" section (see frontend/index.html). See
app/services/mga_lead_service.py for the pipeline itself.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.schemas.mga_lead import (
    GoogleFormWebhookPayload,
    LeadAcceptedResponse,
    MGALeadDetailOut,
    MGALeadListOut,
    MGALeadSummaryOut,
    WebsiteLeadPayload,
    WebsiteLeadResponse,
)
from app.services import mga_lead_service
from app.utils.security import rate_limit_webhook, verify_google_form_webhook_secret

router = APIRouter(tags=["mga-inbound-leads"])


@router.post(
    "/api/leads/website",
    response_model=WebsiteLeadResponse,
    status_code=202,
    dependencies=[Depends(rate_limit_webhook)],
)
def receive_website_lead_magnet_submission(payload: WebsiteLeadPayload) -> WebsiteLeadResponse:
    """Public endpoint the website's own on-page lead-magnet form POSTs to
    directly from the visitor's browser -- no Google Form, no Apps Script
    hop, no shared secret (this is the whole point: it replaces that
    lead-generation middleman with a same-page lead magnet). Only
    IP-based rate limiting guards it, same as the webhook.

    Runs the identical profile -> personalized PDF -> download-link
    pipeline as the Google Form path (mga_lead_service.run_pipeline), just
    tagged with source_type="inbound_website_form" and keyed by a
    server-generated id instead of a Google Form response id."""
    submission_payload = {
        "form_submission_id": f"website-{uuid.uuid4().hex}",
        "name": payload.name,
        "email": payload.email,
        "phone": payload.phone,
        "source_campaign": payload.source_campaign,
        "answers": payload.answers,
    }
    row, duplicate = mga_lead_service.create_or_get_existing(
        submission_payload, source_type="inbound_website_form"
    )
    if not duplicate:
        row = mga_lead_service.process_new_lead(row["id"])

    delivery_url = (
        f"/api/lead-magnets/{row['lead_magnet_id']}" if row.get("lead_magnet_id") else None
    )
    email_sent = bool(row.get("email_sent"))
    if row["status"] == "failed":
        message = "We couldn't generate your personalized report just now — please try again in a moment."
    elif delivery_url and email_sent:
        message = "Your personalized Growth Blueprint is ready — we also emailed you a copy."
    elif delivery_url:
        message = "Your personalized Growth Blueprint is ready."
    else:
        message = "Got it — your Growth Blueprint is being generated."

    return WebsiteLeadResponse(
        lead_id=row["id"],
        status=row["status"],
        lead_magnet_delivery_url=delivery_url,
        email_sent=email_sent,
        message=message,
    )


@router.post(
    "/api/leads/google-form",
    response_model=LeadAcceptedResponse,
    status_code=202,
    dependencies=[Depends(verify_google_form_webhook_secret), Depends(rate_limit_webhook)],
)
def receive_google_form_submission(payload: GoogleFormWebhookPayload) -> LeadAcceptedResponse:
    row, duplicate = mga_lead_service.create_or_get_existing(payload.model_dump())
    if not duplicate:
        # Runs synchronously -- see mga_lead_service's module docstring for
        # why this doesn't need a background job for a single-lead pipeline.
        row = mga_lead_service.process_new_lead(row["id"])
    return LeadAcceptedResponse(
        lead_id=row["id"],
        form_submission_id=row["form_submission_id"],
        status=row["status"],
        duplicate=duplicate,
    )


@router.post(
    "/api/leads/{lead_id}/retry",
    response_model=LeadAcceptedResponse,
    dependencies=[Depends(verify_google_form_webhook_secret)],
)
def retry_lead(lead_id: str) -> LeadAcceptedResponse:
    try:
        row = mga_lead_service.retry(lead_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return LeadAcceptedResponse(
        lead_id=row["id"], form_submission_id=row["form_submission_id"], status=row["status"]
    )


@router.get("/api/lead-magnets/{lead_magnet_id}")
def download_lead_magnet(lead_magnet_id: str):
    from app.db import database

    row = database.get_mga_lead_by_magnet_id(lead_magnet_id)
    # Re-renders the PDF from the stored content if the file is gone (Render
    # wipes the filesystem on every deploy/restart unless a disk is attached).
    path = mga_lead_service.ensure_lead_magnet_file(row) if row else None
    if not path:
        raise HTTPException(status_code=404, detail="Lead magnet not found.")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename="My-Growth-Academy-Personalized-Growth-Map.pdf",
    )


# --------------------------------------------------------------------------
# Dashboard reads (consumed by frontend/index.html's "MGA Leads" section).
# Protected by the X-Dashboard-Key middleware in app/main.py.
# --------------------------------------------------------------------------


@router.get("/api/dashboard/mga-leads/summary", response_model=MGALeadSummaryOut)
def mga_leads_summary() -> MGALeadSummaryOut:
    return MGALeadSummaryOut(**mga_lead_service.summary())


@router.get("/api/dashboard/mga-leads", response_model=MGALeadListOut)
def list_mga_leads(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> MGALeadListOut:
    items, total = mga_lead_service.list_leads(status=status, limit=limit, offset=offset)
    return MGALeadListOut(items=items, total=total)


@router.get("/api/dashboard/mga-leads/{lead_id}", response_model=MGALeadDetailOut)
def get_mga_lead(lead_id: str) -> MGALeadDetailOut:
    detail = mga_lead_service.get_lead_detail(lead_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Lead not found.")
    return MGALeadDetailOut(**detail)


@router.post("/api/dashboard/sheets/sync-all")
def sync_all_leads_to_sheet() -> dict:
    """Re-send every lead to the Google Sheet (dashboard key required).
    Run once after connecting the sheet to backfill existing leads."""
    from app.services import sheets_sync

    return sheets_sync.sync_all()
