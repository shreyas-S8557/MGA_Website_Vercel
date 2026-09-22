from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class GoogleFormWebhookPayload(BaseModel):
    """Payload google-apps-script/Code.gs POSTs on every form submission.

    Field names match what Apps Script can trivially build from a form
    response row (see Code.gs's buildPayload_). The real Google Form's
    exact questions weren't available when this was built, so `answers`
    carries every raw question/value pair untouched, and `field_map` lets
    the caller pin exact question text -> canonical profile key without
    touching lead_profile_service.py's fuzzy matching at all.
    """

    form_submission_id: str = Field(..., min_length=1)
    submitted_at: Optional[datetime] = None
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    source_campaign: Optional[str] = None
    answers: dict[str, Any] = Field(default_factory=dict)
    field_map: Optional[dict[str, str]] = None

    @field_validator("answers")
    @classmethod
    def answers_not_empty(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not v:
            raise ValueError("answers must contain at least one question/answer pair")
        return v


class WebsiteLeadPayload(BaseModel):
    """Payload the website's own on-page lead-magnet form POSTs directly
    (see website/components/LeadMagnetModal.tsx) -- no Google Form, no Apps
    Script, no shared secret. This is the visitor's browser talking to this
    backend directly, so it carries no `field_map`: the quiz's question
    text is written to match `lead_profile_service.FIELD_ALIASES` exactly,
    so the existing fuzzy matching picks the answers up unchanged."""

    # The original "3-Year Future Snapshot" Google Form only ever asked for
    # email -- by request, the on-page version now also collects name
    # (required, for a personal greeting in the PDF/email) and phone
    # (optional, for follow-up outreach).
    name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    phone: Optional[str] = Field(default="", max_length=50)
    answers: dict[str, Any] = Field(default_factory=dict)
    source_campaign: Optional[str] = Field(default="website_lead_magnet")

    @field_validator("answers")
    @classmethod
    def answers_not_empty(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not v:
            raise ValueError("answers must contain at least one question/answer pair")
        return v


class WebsiteLeadResponse(BaseModel):
    lead_id: str
    status: str
    lead_magnet_delivery_url: Optional[str] = None
    email_sent: bool = False
    message: str


class LeadAcceptedResponse(BaseModel):
    lead_id: str
    form_submission_id: str
    status: str
    duplicate: bool = False


class MGALeadOut(BaseModel):
    id: str
    form_submission_id: str
    source_type: str
    status: str
    failed_stage: str = ""
    name: str = ""
    email: str = ""
    lead_magnet_type: str = ""
    email_sent: bool = False
    submitted_at: str = ""
    created_at: str = ""


class MGALeadDetailOut(MGALeadOut):
    phone: str = ""
    source_campaign: str = ""
    raw_answers: dict[str, Any] = Field(default_factory=dict)
    profile: Optional[dict[str, Any]] = None
    lead_magnet_id: str = ""
    lead_magnet_delivery_url: Optional[str] = None
    delivered_at: str = ""
    email_sent: bool = False
    email_sent_at: str = ""
    email_error: str = ""
    team_notified_at: str = ""
    team_notify_error: str = ""
    error_message: str = ""
    updated_at: str = ""


class MGALeadListOut(BaseModel):
    items: list[MGALeadOut]
    total: int


class MGALeadSummaryOut(BaseModel):
    total_submissions: int = 0
    new_leads: int = 0
    profiled_leads: int = 0
    lead_magnets_generated: int = 0
    lead_magnets_delivered: int = 0
    failed: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
