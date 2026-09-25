"""Picks the email provider used for the lead-magnet delivery email and the
team new-lead notification.

    EmailSender
        +-- MailerLiteSender   (default -- EMAIL_PROVIDER=mailerlite)
        +-- MailerLiteClassicSender (EMAIL_PROVIDER=mailerlite_classic --
        |                             Legacy/Classic MailerLite accounts)
        +-- GmailSender        (optional -- EMAIL_PROVIDER=gmail)
        +-- DryRunEmailSender  (never touches the network)

All three share the same `.send(to, subject, body, *, from_name="", ...)
-> SendResult` contract, so callers don't care which one is active.
"""
from __future__ import annotations

import uuid

from app.config import ALLOW_LIVE_SEND, EMAIL_PROVIDER
from app.senders.gmail_sender import GmailCredentialsError, GmailSender
from app.senders.mailerlite_classic_sender import MailerLiteClassicSender
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
    "mailerlite_classic": MailerLiteClassicSender,
    "gmail": GmailSender,
}


def get_sender(
    send_mode: str, provider: str | None = None
) -> GmailSender | MailerLiteSender | DryRunEmailSender:
    """"live" honors PROSPECT_ALLOW_LIVE_SEND + the provider (EMAIL_PROVIDER
    unless `provider` is given, e.g. TEAM_EMAIL_PROVIDER for team alerts)
    and raises SendModeNotAllowed if either isn't configured (or the
    provider's credentials are missing); anything else returns a
    DryRunEmailSender."""
    if send_mode == "live":
        provider_name = (provider or EMAIL_PROVIDER).strip().lower()
        if not ALLOW_LIVE_SEND:
            raise SendModeNotAllowed(
                "Live sending is turned off on this backend (PROSPECT_ALLOW_LIVE_SEND is "
                "false). Set it to true to email leads -- see README.md."
            )
        provider_cls = _PROVIDERS.get(provider_name)
        if provider_cls is None:
            raise SendModeNotAllowed(
                f"Unknown email provider {provider_name!r}. Must be one of: "
                f"{', '.join(sorted(_PROVIDERS))}."
            )
        sender = provider_cls()
        try:
            sender.validate_credentials()
        except (MailerLiteCredentialsError, GmailCredentialsError) as exc:
            raise SendModeNotAllowed(str(exc)) from exc
        return sender
    return DryRunEmailSender()
