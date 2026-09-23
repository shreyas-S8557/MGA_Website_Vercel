"""MailerLite REST API sending adapter (the default EMAIL_PROVIDER -- see
app/services/sending_service.py).

Used for the lead-magnet delivery email and the team new-lead
notification. MailerLite has no SMTP relay and no "send one transactional
email to one address" endpoint: its REST API
(https://connect.mailerlite.com/api) is built around subscribers, groups
and campaigns. To send ONE email to ONE address without touching any other
subscriber in the account, `send()` does exactly this, in order:

  1. POST /api/groups              -- create a brand-new, empty group that
                                       exists for this single send only
                                       (name embeds a uuid so it can never
                                       collide with a real marketing group).
  2. POST /api/subscribers          -- upsert the recipient and add them to
                                       that new group (non-destructive: it
                                       only adds groups, never removes the
                                       recipient from existing ones).
  3. POST /api/campaigns            -- create a `regular` campaign whose
                                       *only* target is that group, with the
                                       email's subject/body as its content.
  4. POST /api/campaigns/{id}/schedule  -- {"delivery": "instant"}.

Because the group contains exactly one subscriber, the campaign can only
ever reach that one person.

KNOWN CONSEQUENCES:
  - Every send costs 3-4 API calls against MailerLite's 120 req/min global
    rate limit (see RATE_LIMIT_PER_MINUTE below).
  - The sender address must already be verified in MailerLite -- MailerLite
    rejects the campaign (422) otherwise. See MailerLiteSenderNotVerified.
  - MailerLite appends its own unsubscribe footer to every message.
  - MailerLite campaigns cannot carry file attachments, so the PDF is
    delivered as a download link in the email body instead.
  - The one-subscriber groups are not deleted automatically (see
    `cleanup_group` below for the opt-in, best-effort alternative).
  - "sent" means "MailerLite accepted the campaign and scheduled it for
    instant delivery," not "the recipient's inbox has it yet".
"""

from __future__ import annotations

import html
import os
import uuid
from dataclasses import dataclass
from typing import Any, Callable

import httpx

BASE_URL = "https://connect.mailerlite.com/api"
RATE_LIMIT_PER_MINUTE = 120  # MailerLite's documented global rate limit
OUTBOX_PREFIX = "mga-outbox-"
# MailerLite allows at most 1,000 groups per account, so the one-off outbox
# groups are deleted once they're this old (long after an instant campaign
# has gone out). See _cleanup_old_outbox_groups.
OUTBOX_MAX_AGE_HOURS = 24
DEFAULT_TIMEOUT_SECONDS = 20.0


class MailerLiteCredentialsError(RuntimeError):
    """Raised when MAILERLITE_API_TOKEN / MAILERLITE_SENDER_EMAIL /
    MAILERLITE_SENDER_NAME aren't available -- mirrors
    GmailCredentialsError's role for the Gmail adapter."""


class MailerLiteSenderNotVerified(RuntimeError):
    """Raised when MailerLite rejects the configured sender address because
    it hasn't been verified on the MailerLite account. Deliberately its own
    exception (rather than a generic API error) so callers can surface the
    exact message the migration brief asks for: "MailerLite sender email is
    not verified." Never silently falls back to a different sender."""


@dataclass
class SendResult:
    """Outcome of one send attempt. Same shape/contract as
    gmail_sender.SendResult (success/message_id/error) so callers don't
    care which provider is active, plus one additive field:

    `retryable` -- whether retrying could plausibly help. Defaults to True
    (unknown-cause failures are assumed possibly transient). Set False for
    failures a retry can never fix (bad credentials, an unverified sender,
    a MailerLite-rejected recipient).
    """

    success: bool
    message_id: str = ""
    error: str = ""
    retryable: bool = True


def _env(name: str) -> str:
    return os.environ.get(name, "") or ""


def _body_to_html(body: str) -> str:
    """MailerLite requires `emails.*.content` to be a full, valid HTML
    document. The report email and the team alert are already HTML (built
    in mga_lead_service with every visitor-supplied value escaped there),
    so those are wrapped as-is -- escaping them again would show the raw
    tags to the recipient. Plain text (e.g. the test email) is escaped and
    its newlines turned into <br>."""
    import re

    stripped = body.strip()
    if re.search(r"<(html|body|div|p|table|h[1-6]|a|ul|br)\b", stripped, re.I):
        if stripped.lower().startswith("<html"):
            return stripped
        return "<html><body>" + stripped + "</body></html>"
    escaped = html.escape(body)
    return "<html><body><p>" + escaped.replace("\n", "<br>\n") + "</p></body></html>"


class MailerLiteSender:
    """Thin, mockable adapter around the MailerLite REST API.

    Credentials are only ever read from environment variables (or passed
    explicitly, which is how tests inject fake ones) -- never hard-coded,
    same convention as GmailSender. `http_client_factory` is injectable so
    tests can swap in a fake HTTP client and never touch the network.
    """

    def __init__(
        self,
        api_token: str | None = None,
        sender_email: str | None = None,
        sender_name: str | None = None,
        *,
        base_url: str = BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        http_client_factory: Callable[..., httpx.Client] = httpx.Client,
        cleanup_group: bool = False,
    ) -> None:
        self.api_token = api_token if api_token is not None else _env("MAILERLITE_API_TOKEN")
        self.sender_email = (
            sender_email if sender_email is not None else _env("MAILERLITE_SENDER_EMAIL")
        )
        self.sender_name = (
            sender_name if sender_name is not None else _env("MAILERLITE_SENDER_NAME")
        )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._http_client_factory = http_client_factory
        # Best-effort cleanup of the one-off group after a successful send.
        # Off by default -- see the module docstring's "KNOWN CONSEQUENCES"
        # note on why immediate deletion risks dropping an in-flight send.
        self.cleanup_group = cleanup_group

    # -- credential / config validation --------------------------------------

    def validate_credentials(self) -> None:
        """Raise MailerLiteCredentialsError if required config isn't set.
        Pure config check -- no network call."""
        missing = []
        if not self.api_token:
            missing.append("MAILERLITE_API_TOKEN")
        if not self.sender_email:
            missing.append("MAILERLITE_SENDER_EMAIL")
        if not self.sender_name:
            missing.append("MAILERLITE_SENDER_NAME")
        if missing:
            raise MailerLiteCredentialsError(
                "Missing MailerLite configuration: "
                + ", ".join(missing)
                + ". Set these as environment variables (e.g. in a .env file). "
                "MAILERLITE_API_TOKEN is a Bearer API token generated from "
                "MailerLite -> Integrations -> Developer API, not your "
                "account email/password."
            )

    # -- low-level HTTP -------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _client(self) -> httpx.Client:
        return self._http_client_factory(
            base_url=self.base_url, headers=self._headers(), timeout=self.timeout
        )

    def _request(self, method: str, path: str, *, json: dict[str, Any] | None = None) -> Any:
        """One HTTP call against the MailerLite API. Never raises the
        underlying httpx exception to callers of `send()` -- see `send()`'s
        try/except, which is the only place this is called from during a
        send. Used directly (with its own error handling) by
        check_configuration() for the lightweight, read-only connectivity
        test.
        """
        with self._client() as client:
            resp = client.request(method, path, json=json)
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    # -- connectivity / configuration check (no writes) ------------------------

    def check_configuration(self) -> dict[str, Any]:
        """Read-only verification for the settings/"test connection" API
        (item 12 of the migration brief): confirms the token authenticates
        and the API is reachable, WITHOUT creating any subscriber, group, or
        campaign, and WITHOUT ever returning the token itself.

        MailerLite's API has no dedicated "is this sender domain verified"
        GET endpoint, so `sender_verified` here reflects only that a
        MAILERLITE_SENDER_EMAIL is configured (format-checked), not that
        MailerLite has actually verified it -- an unverified sender is only
        discoverable by MailerLite rejecting an actual campaign/send with a
        422 (see MailerLiteSenderNotVerified). This is surfaced explicitly
        in the returned dict rather than glossed over.
        """
        result: dict[str, Any] = {
            "provider": "mailerlite",
            "configured": False,
            "authenticated": False,
            "sender": self.sender_email,
            "sender_verified_checked": False,
            "error": "",
        }
        try:
            self.validate_credentials()
        except MailerLiteCredentialsError as exc:
            result["error"] = str(exc)
            return result
        result["configured"] = True
        try:
            # Cheapest authenticated GET available: fetch a single
            # subscriber page. Read-only, no side effects.
            self._request("GET", "/subscribers", json=None)
            result["authenticated"] = True
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in (401, 403):
                result["error"] = "MailerLite rejected the API token (unauthorized)."
            else:
                result["error"] = f"MailerLite API error (HTTP {status})."
        except httpx.RequestError as exc:
            result["error"] = f"Could not reach the MailerLite API: {exc}"
        return result

    # -- sending ---------------------------------------------------------------

    def send(
        self,
        to_address: str,
        subject: str,
        body_html: str,
        *,
        body_text: str | None = None,  # noqa: ARG002 -- kept for interface parity with GmailSender
        from_name: str = "",
        attachments: list[str] | None = None,  # noqa: ARG002 -- MailerLite campaigns don't support ad-hoc attachments
    ) -> SendResult:
        """Send one individualized email to `to_address` via an isolated,
        single-subscriber MailerLite group + campaign (see module
        docstring). Never raises for send-time failures -- always returns a
        SendResult, matching GmailSender.send()'s contract exactly.
        """
        if not to_address or not to_address.strip():
            return SendResult(success=False, error="Empty recipient address", retryable=False)
        if not subject.strip() or not body_html.strip():
            return SendResult(success=False, error="Empty subject or body", retryable=False)

        try:
            self.validate_credentials()
        except MailerLiteCredentialsError as exc:
            return SendResult(success=False, error=str(exc), retryable=False)

        self._cleanup_old_outbox_groups()

        group_id: str | None = None
        try:
            group_name = f"{OUTBOX_PREFIX}{uuid.uuid4().hex}"
            group = self._request("POST", "/groups", json={"name": group_name})
            group_id = (group or {}).get("data", {}).get("id")
            if not group_id:
                return SendResult(
                    success=False, error="MailerLite did not return a group id", retryable=True
                )

            self._request(
                "POST",
                "/subscribers",
                json={"email": to_address, "groups": [group_id]},
            )

            sender_name = from_name or self.sender_name
            content_html = _body_to_html(body_html)
            campaign_payload = {
                "name": f"mga-{uuid.uuid4().hex[:12]}",
                "type": "regular",
                "emails": [
                    {
                        "subject": subject,
                        "from_name": sender_name,
                        "from": self.sender_email,
                        "content": content_html,
                    }
                ],
                "groups": [group_id],
            }
            campaign = self._request("POST", "/campaigns", json=campaign_payload)
            campaign_id = (campaign or {}).get("data", {}).get("id")
            if not campaign_id:
                return SendResult(
                    success=False, error="MailerLite did not return a campaign id", retryable=True
                )

            self._request(
                "POST", f"/campaigns/{campaign_id}/schedule", json={"delivery": "instant"}
            )

            if self.cleanup_group:
                try:
                    self._request("DELETE", f"/groups/{group_id}", json=None)
                except Exception:  # noqa: BLE001 -- cleanup is best-effort, never fails the send
                    pass

            return SendResult(success=True, message_id=str(campaign_id))

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            detail = _error_detail(exc)
            if status in (401, 403):
                return SendResult(
                    success=False,
                    error=f"MailerLite authentication failed (HTTP {status}): {detail}",
                    retryable=False,
                )
            if status == 422:
                if self.sender_email and self.sender_email.lower() in detail.lower():
                    return SendResult(
                        success=False,
                        error="MailerLite sender email is not verified.",
                        retryable=False,
                    )
                return SendResult(
                    success=False,
                    error=f"MailerLite rejected the request (validation error): {detail}",
                    retryable=False,
                )
            if status == 429:
                retry_after = exc.response.headers.get("Retry-After", "")
                return SendResult(
                    success=False,
                    error=f"MailerLite rate limit exceeded (429). Retry-After={retry_after}",
                    retryable=True,
                )
            if status >= 500:
                return SendResult(
                    success=False,
                    error=f"MailerLite server error (HTTP {status}): {detail}",
                    retryable=True,
                )
            return SendResult(
                success=False, error=f"MailerLite API error (HTTP {status}): {detail}", retryable=True
            )
        except httpx.RequestError as exc:
            return SendResult(success=False, error=f"Network error contacting MailerLite: {exc}", retryable=True)

    def _cleanup_old_outbox_groups(self) -> int:
        """Best-effort housekeeping: delete one-off outbox groups older than
        OUTBOX_MAX_AGE_HOURS, so the account never reaches MailerLite's
        1,000-group limit. Only touches groups whose name starts with
        OUTBOX_PREFIX (never real marketing groups). Never raises."""
        from datetime import datetime, timedelta, timezone

        deleted = 0
        try:
            data = self._request(
                "GET",
                f"/groups?filter[name]={OUTBOX_PREFIX}&limit=50&sort=created_at",
                json=None,
            ) or {}
            cutoff = datetime.now(timezone.utc) - timedelta(hours=OUTBOX_MAX_AGE_HOURS)
            for group in data.get("data", []):
                name = str(group.get("name", ""))
                if not name.startswith(OUTBOX_PREFIX):
                    continue
                created = _parse_time(group.get("created_at"))
                if created is None or created > cutoff:
                    continue
                try:
                    self._request("DELETE", f"/groups/{group['id']}", json=None)
                    deleted += 1
                except Exception:  # noqa: BLE001
                    pass
        except Exception:  # noqa: BLE001 -- housekeeping must never block a send
            pass
        return deleted

    def send_test_email(self, to_address: str | None = None) -> SendResult:
        """A real test send to verify MailerLite authentication + sender
        config before going live, mirroring
        GmailSender.send_test_email(). Defaults to sending to the
        configured sender address itself, exactly like the Gmail adapter
        does. Only ever sends to the single `to_address` given -- never a
        lead pulled from the database."""
        target = to_address or self.sender_email
        return self.send(
            target,
            subject="My Growth Academy - MailerLite test email",
            body_html=(
                "This is a test email from the My Growth Academy backend's "
                "MailerLiteSender adapter.\n\n"
                "If you received this, MailerLite sending is configured "
                "correctly."
            ),
        )


def _parse_time(value: Any):
    """MailerLite timestamps look like '2026-09-23 10:15:00' (UTC) or ISO
    8601. Returns an aware datetime, or None if unparsable."""
    from datetime import datetime, timezone

    if not value:
        return None
    text = str(value).strip().replace("T", " ").replace("Z", "")
    text = text.split(".")[0].split("+")[0]
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _error_detail(exc: httpx.HTTPStatusError) -> str:
    try:
        data = exc.response.json()
    except Exception:  # noqa: BLE001
        return exc.response.text[:300]
    if isinstance(data, dict):
        if isinstance(data.get("error"), dict):  # MailerLite Classic: {"error": {"code", "message"}}
            return str(data["error"].get("message") or data["error"])[:300]
        message = data.get("message", "")
        errors = data.get("errors")
        if errors:
            return f"{message} {errors}".strip()
        return message or str(data)[:300]
    return str(data)[:300]
