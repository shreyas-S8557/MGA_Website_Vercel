"""Verify MailerLite credentials/configuration, and send one safe,
explicit, one-address-only test email -- so the provider can be validated
before lead-magnet emails go out for real.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from app.services import email_provider_service

router = APIRouter(prefix="/api/email/provider", tags=["email-provider"])


class TestSendRequest(BaseModel):
    to: EmailStr


@router.post("/test")
def test_connection() -> dict:
    return email_provider_service.test_connection()


@router.post("/test-send")
def test_send(payload: TestSendRequest) -> dict:
    try:
        return email_provider_service.send_test_email(str(payload.to))
    except email_provider_service.TestSendNotAllowed as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
