"""Gmail (SMTP + App Password) sending adapter -- optional alternative to
MailerLite, used only when EMAIL_PROVIDER=gmail is set explicitly.

Credentials are only ever read from environment variables
(GMAIL_ADDRESS / GMAIL_APP_PASSWORD) or explicit constructor args (used by
tests) -- never hard-coded. GMAIL_APP_PASSWORD must be a 16-character
Gmail "App Password" (Google Account -> Security -> 2-Step Verification ->
App passwords); a normal account password no longer works over SMTP.

`send()` never raises for send-time failures; it always returns a
`SendResult`, so callers can record the failure and carry on. Unlike
MailerLite, this adapter can attach the lead-magnet PDF directly.
"""

from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email import encoders
from email import utils as email_utils
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Callable

DEFAULT_SMTP_HOST = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 465


class GmailCredentialsError(RuntimeError):
    """Raised when GMAIL_ADDRESS / GMAIL_APP_PASSWORD aren't available."""


@dataclass
class SendResult:
    """Outcome of one send attempt.

    `message_id` is the RFC 5322 Message-ID header this adapter generated
    and put on the outgoing message *before* sending it -- plain SMTP
    (unlike the Gmail API) doesn't hand back a provider-confirmed ID in
    its response, so this self-generated, globally-unique ID is the
    closest thing available in SMTP mode, and is what's recorded as
    `provider_message_id` downstream. It's still useful for tracing a
    specific send (it's the same value Gmail stores in the sent message's
    own Message-ID header), just not a delivery receipt.
    """

    success: bool
    message_id: str = ""
    error: str = ""


class GmailSender:
    """Thin, mockable adapter around Gmail's SMTP endpoint.

    Credentials are only ever read from environment variables (or passed
    explicitly, which is how tests inject fake ones) -- never hard-coded.
    The backend loads `.env` at startup (see app/env.py), so these are
    picked up automatically.

    `smtp_client_factory` is injectable so tests can swap in a fake SMTP
    client and never touch the network or send a real email.
    """

    def __init__(
        self,
        address: str | None = None,
        app_password: str | None = None,
        *,
        smtp_host: str = DEFAULT_SMTP_HOST,
        smtp_port: int = DEFAULT_SMTP_PORT,
        smtp_client_factory: Callable[[str, int], object] = smtplib.SMTP_SSL,
    ) -> None:
        self.address = address if address is not None else os.environ.get("GMAIL_ADDRESS", "")
        self.app_password = (
            app_password if app_password is not None else os.environ.get("GMAIL_APP_PASSWORD", "")
        )
        # Optional different "From" address, e.g. a lead-magnet alias like
        # blueprint@mygrowthacademy.coach. It must be added to the Gmail
        # account under Settings -> Accounts -> "Send mail as", or Gmail
        # rewrites it back to GMAIL_ADDRESS.
        self.from_address = os.environ.get("GMAIL_FROM_ADDRESS", "").strip() or self.address
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self._smtp_client_factory = smtp_client_factory
        self._conn = None

    # -- credential / config validation --------------------------------------

    def validate_credentials(self) -> None:
        """Raise GmailCredentialsError if address/app_password aren't set.

        Pure config check -- no network call, so this can (and should) run
        before anything ever tries to talk to Gmail.
        """
        missing = []
        if not self.address:
            missing.append("GMAIL_ADDRESS")
        if not self.app_password:
            missing.append("GMAIL_APP_PASSWORD")
        if missing:
            raise GmailCredentialsError(
                "Missing Gmail credentials: "
                + ", ".join(missing)
                + ". Set these as environment variables (e.g. in a .env file) -- "
                "GMAIL_APP_PASSWORD must be a 16-character Gmail App Password "
                "(Google Account -> Security -> 2-Step Verification -> App "
                "passwords), not your regular account password."
            )

    # -- connection lifecycle -------------------------------------------------

    def connect(self) -> None:
        """Open and authenticate the SMTP connection. Idempotent."""
        self.validate_credentials()
        if self._conn is not None:
            return
        conn = self._smtp_client_factory(self.smtp_host, self.smtp_port)
        conn.login(self.address, self.app_password)
        self._conn = conn

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.quit()
            except Exception:
                pass
            self._conn = None

    def __enter__(self) -> "GmailSender":
        self.connect()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def verify_connection(self) -> bool:
        """Log in and immediately disconnect, without sending anything.

        Confirms the credentials actually authenticate against Gmail. Raises
        GmailCredentialsError (missing config) or smtplib.SMTPException /
        OSError (bad credentials, network issue) on failure.
        """
        self.connect()
        self.close()
        return True

    # -- message construction -------------------------------------------------

    def _build_message(
        self,
        *,
        to_address: str,
        subject: str,
        body_html: str,
        body_text: str | None,
        from_name: str,
        attachments: list | None,
    ):
        msg = MIMEMultipart("mixed")
        from_addr = self.from_address or self.address
        msg["From"] = email_utils.formataddr((from_name, from_addr)) if from_name else from_addr
        msg["To"] = to_address
        msg["Subject"] = subject
        message_id = email_utils.make_msgid(domain="gmail.com")
        msg["Message-ID"] = message_id
        msg["Date"] = email_utils.formatdate(localtime=True)

        alt = MIMEMultipart("alternative")
        if body_text:
            alt.attach(MIMEText(body_text, "plain"))
        alt.attach(MIMEText(body_html, "html"))
        msg.attach(alt)

        # Optional attachments (MIMEBase + base64 encoding) -- used to
        # attach the lead-magnet PDF to the delivery email.
        # Each item is a path, or (path, filename to show the recipient).
        for item in attachments or []:
            path, shown_name = item if isinstance(item, tuple) else (item, None)
            p = Path(path)
            with open(p, "rb") as fh:
                is_pdf = p.suffix.lower() == ".pdf"
                part = MIMEBase("application", "pdf" if is_pdf else "octet-stream")
                part.set_payload(fh.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=shown_name or p.name)
            msg.attach(part)

        return msg, message_id

    # -- sending ---------------------------------------------------------------

    def send(
        self,
        to_address: str,
        subject: str,
        body_html: str,
        *,
        body_text: str | None = None,
        from_name: str = "",
        attachments: list[str] | None = None,
    ) -> SendResult:
        """Send one email. Never raises for send-time failures (missing
        credentials, auth errors, refused recipients, network errors, ...)
        -- always returns a SendResult, so a caller sending a batch can
        record a per-recipient failure and keep going instead of aborting
        the whole run, unlike the original script's unguarded loop.
        """
        if not to_address or not to_address.strip():
            return SendResult(success=False, error="Empty recipient address")
        if not subject.strip() or not body_html.strip():
            return SendResult(success=False, error="Empty subject or body")
        try:
            self.connect()
            msg, message_id = self._build_message(
                to_address=to_address,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                from_name=from_name,
                attachments=attachments,
            )
            self._conn.sendmail(self.from_address or self.address, [to_address], msg.as_string())
            return SendResult(success=True, message_id=message_id)
        except GmailCredentialsError as exc:
            return SendResult(success=False, error=str(exc))
        except smtplib.SMTPException as exc:
            return SendResult(success=False, error=f"{type(exc).__name__}: {exc}")
        except OSError as exc:
            return SendResult(success=False, error=f"Connection error: {exc}")

    def send_test_email(self, to_address: str | None = None) -> SendResult:
        """A real test send to verify Gmail authentication before going
        live. Defaults to sending to the configured Gmail
        address itself, so you can verify without emailing a third party.
        """
        target = to_address or self.address
        return self.send(
            target,
            subject="My Growth Academy - Gmail test email",
            body_html=(
                "<p>This is a test email from the My Growth Academy "
                "backend's GmailSender adapter.</p>"
                "<p>If you received this, Gmail sending is configured "
                "correctly.</p>"
            ),
            body_text=(
                "This is a test email from the My Growth Academy "
                "backend's GmailSender adapter. If you received this, "
                "Gmail sending is configured correctly."
            ),
        )
