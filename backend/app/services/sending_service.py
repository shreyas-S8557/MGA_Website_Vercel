"""Picks the email provider used for the lead-magnet delivery email and the
team new-lead notification.

    EmailSender
        +-- MailerLiteSender   (default -- EMAIL_PROVIDER=mailerlite)
        +-- GmailSender        (optional -- EMAIL_PROVIDER=gmail)
        +-- DryRunEmailSender  (never touches the network)

All three share the same `.send(to, subject, body, *, from_name="", ...)
-> SendResult` contract, so callers don't care which one is active.
"""
from __future__ import annotations

import uuid

from app.config import ALLOW_LIVE_SEND, EMAIL_PROVIDER
from app.senders.gmail_sender import GmailCredentialsError, GmailSender
from app.senders.mailerlite_sender import (
    MailerLiteCredentialsError,
    MailerLiteSender,
    SendResult,
)


class SendModeNotAllowed(PermissionError):
    pass


class DryRunEmailSender:
    """Drop-in replacement for a real sender that never touches the network.
    Used for any non-"live" send mode, and always in automated tests."""

    def send(
        self, to_email: str, subject: str, body: str, *, from_name: str = "", **_: object
    ) -> SendResult:
        return SendResult(success=True, message_id=f"dry-run-{uuid.uuid4().hex}", error="")


_PROVIDERS = {
    "mailerlite": MailerLiteSender,
    "gmail": GmailSender,
}


def get_sender(send_mode: str) -> GmailSender | MailerLiteSender | DryRunEmailSender:
    """"live" honors PROSPECT_ALLOW_LIVE_SEND + EMAIL_PROVIDER and raises
    SendModeNotAllowed if either isn't configured (or the provider's
    credentials are missing); anything else returns a DryRunEmailSender."""
    if send_mode == "live":
        if not ALLOW_LIVE_SEND:
            raise SendModeNotAllowed(
                "Live sending is disabled on this backend (PROSPECT_ALLOW_LIVE_SEND is not "
                "set). This is a deliberate safety default -- see README.md."
            )
        provider_cls = _PROVIDERS.get(EMAIL_PROVIDER)
        if provider_cls is None:
            raise SendModeNotAllowed(
                f"Unknown EMAIL_PROVIDER={EMAIL_PROVIDER!r}. Must be one of: "
                f"{', '.join(sorted(_PROVIDERS))}."
            )
        sender = provider_cls()
        try:
            sender.validate_credentials()
        except (MailerLiteCredentialsError, GmailCredentialsError) as exc:
            raise SendModeNotAllowed(str(exc)) from exc
        return sender
    return DryRunEmailSender()
