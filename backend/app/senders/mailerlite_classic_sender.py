"""MailerLite *Classic* (Legacy) sending adapter -- EMAIL_PROVIDER=mailerlite_classic.

MailerLite Classic accounts (created before March 2022) use a completely
separate API from the new MailerLite: a different base URL
(https://api.mailerlite.com/api/v2), a different auth header
(X-MailerLite-ApiKey) and different campaign steps. A Classic API key does
not work against the new API (app/senders/mailerlite_sender.py), and vice
versa. Docs: https://developers-classic.mailerlite.com/

Like the new-MailerLite adapter, there is no "send one email to one person"
endpoint, so each send is an isolated one-subscriber group + campaign:

  1. POST /groups                          -- a brand-new, empty outbox group
  2. POST /groups/{id}/subscribers         -- add ONLY the recipient to it
                                              (autoresponders=false, so none of
                                              the account's own automations fire)
  3. POST /campaigns                       -- regular campaign to that group only
  4. PUT  /campaigns/{id}/content          -- the HTML + plain-text body
  5. POST /campaigns/{id}/actions/send     -- send now

Classic requires every campaign to carry an unsubscribe link ({$unsubscribe})
in the HTML and plain text, plus a web-version link ({$url}) in the plain
text; this adapter adds a small footer with them. Campaigns can't carry
attachments, so the PDF goes out as the download link in the body. Old
outbox groups are deleted after OUTBOX_MAX_AGE_HOURS so the account's group
list never grows without limit.
"""
from __future__ import annotations

import html as _html
import os
import re
import uuid
from typing import Any, Callable

import httpx

from app.senders.mailerlite_sender import (
    OUTBOX_MAX_AGE_HOURS,
    OUTBOX_PREFIX,
    MailerLiteCredentialsError,
    SendResult,
    _error_detail,
    _parse_time,
)

BASE_URL = "https://api.mailerlite.com/api/v2"
DEFAULT_TIMEOUT_SECONDS = 12.0

_CLEANUP_EVERY_SECONDS = 30 * 60
_MAX_DELETES_PER_RUN = 10
_LAST_CLEANUP = -1e12  # monotonic time of the last outbox cleanup


def _env(name: str) -> str:
    return os.environ.get(name, "") or ""


def _html_document(body_html: str) -> str:
    """Full HTML document (Classic requires <head> and <body>) with the
    mandatory {$unsubscribe} link in a small footer. HTML bodies are used
    as-is (they're built with every visitor value already escaped); plain
    text is escaped and its newlines turned into <br>."""
    body = body_html.strip()
    if not re.search(r"<(html|body|div|p|table|h[1-6]|a|ul|br)\b", body, re.I):
        body = "<p>" + _html.escape(body).replace("\n", "<br>\n") + "</p>"
    body = re.sub(r"(?is)^.*?<body[^>]*>|</body>.*$", "", body)  # unwrap if already a document
    footer = (
        '<p style="color:#8F8F8F;font-size:12px;font-family:sans-serif;'
        'text-align:center;margin-top:32px;">'
        '<a href="{$unsubscribe}" style="color:#8F8F8F;">Unsubscribe</a></p>'
    )
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"></head>'
        f"<body>{body}{footer}</body></html>"
    )


def _plain_text(body_html: str) -> str:
    """Plain-text alternative, with the {$url} and {$unsubscribe} tags
    Classic requires."""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", body_html)
    text = re.sub(r'(?is)<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"\2 (\1)", text)
    text = re.sub(r"(?i)<br\s*/?>|</(p|div|h[1-6]|li|tr)>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = _html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return f"{text}\n\nView this email in your browser: {{$url}}\nUnsubscribe: {{$unsubscribe}}"


def _split_name(name: str) -> tuple[str, str]:
    parts = (name or "").strip().split(None, 1)
    return (parts[0] if parts else "", parts[1] if len(parts) > 1 else "")


class MailerLiteClassicSender:
    """Same interface as MailerLiteSender / GmailSender: validate_credentials(),
    check_configuration(), send(), send_test_email()."""

    provider = "mailerlite_classic"

    def __init__(
        self,
        api_key: str | None = None,
        sender_email: str | None = None,
        sender_name: str | None = None,
        *,
        base_url: str = BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        http_client_factory: Callable[..., httpx.Client] = httpx.Client,
    ) -> None:
        self.api_key = api_key if api_key is not None else _env("MAILERLITE_API_TOKEN")
        self.sender_email = (
            sender_email if sender_email is not None else _env("MAILERLITE_SENDER_EMAIL")
        )
        self.sender_name = (
            sender_name if sender_name is not None else _env("MAILERLITE_SENDER_NAME")
        )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._http_client_factory = http_client_factory
        self._client = None

    # -- config ------------------------------------------------------------------

    def validate_credentials(self) -> None:
        missing = [
            name for name, value in (
                ("MAILERLITE_API_TOKEN", self.api_key),
                ("MAILERLITE_SENDER_EMAIL", self.sender_email),
                ("MAILERLITE_SENDER_NAME", self.sender_name),
            ) if not value
        ]
        if missing:
            raise MailerLiteCredentialsError(
                "Missing MailerLite Classic configuration: " + ", ".join(missing)
                + ". MAILERLITE_API_TOKEN is the Classic API key from MailerLite "
                "Classic -> Integrations -> Developer API."
            )

    # -- HTTP --------------------------------------------------------------------

    def _request(self, method: str, path: str, *, json: dict[str, Any] | None = None) -> Any:
        headers = {
            "X-MailerLite-ApiKey": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        # One pooled connection per sender: a send is 5-6 API calls, and a
        # fresh TLS handshake for each one added seconds per lead.
        if self._client is None:
            self._client = self._http_client_factory(
                base_url=self.base_url, headers=headers, timeout=self.timeout
            )
        resp = self._client.request(method, path, json=json)
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    def check_configuration(self) -> dict[str, Any]:
        """Read-only: confirms the key authenticates. Never returns the key."""
        result: dict[str, Any] = {
            "provider": self.provider,
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
            self._request("GET", "/groups?limit=1")
            result["authenticated"] = True
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            result["error"] = (
                "MailerLite Classic rejected the API key (unauthorized)."
                if status in (401, 403) else f"MailerLite Classic API error (HTTP {status})."
            )
        except httpx.RequestError as exc:
            result["error"] = f"Could not reach the MailerLite Classic API: {exc}"
        return result

    # -- housekeeping --------------------------------------------------------------

    def _cleanup_old_outbox_groups(self) -> int:
        """Delete this adapter's one-off outbox groups once they're older than
        OUTBOX_MAX_AGE_HOURS. Only groups named OUTBOX_PREFIX...; never raises."""
        from datetime import datetime, timedelta, timezone

        import time

        global _LAST_CLEANUP
        # At most once every 30 minutes per running instance, and at most
        # _MAX_DELETES_PER_RUN deletions: housekeeping used to run on every
        # single send and could eat most of a request's time limit.
        if time.monotonic() - _LAST_CLEANUP < _CLEANUP_EVERY_SECONDS:
            return 0
        _LAST_CLEANUP = time.monotonic()

        deleted = 0
        try:
            groups = self._request("GET", "/groups?limit=1000") or []
            if isinstance(groups, dict):
                groups = groups.get("data", [])
            cutoff = datetime.now(timezone.utc) - timedelta(hours=OUTBOX_MAX_AGE_HOURS)
            for group in groups:
                if not str(group.get("name", "")).startswith(OUTBOX_PREFIX):
                    continue
                created = _parse_time(group.get("date_created") or group.get("created_at"))
                if created is None or created > cutoff:
                    continue
                if deleted >= _MAX_DELETES_PER_RUN:
                    break
                try:
                    self._request("DELETE", f"/groups/{group['id']}")
                    deleted += 1
                except Exception:  # noqa: BLE001
                    pass
        except Exception:  # noqa: BLE001 -- housekeeping must never block a send
            pass
        return deleted

    # -- sending -------------------------------------------------------------------

    def send(
        self,
        to_address: str,
        subject: str,
        body_html: str,
        *,
        body_text: str | None = None,  # noqa: ARG002 -- interface parity
        from_name: str = "",
        attachments: list[str] | None = None,  # noqa: ARG002 -- campaigns can't carry attachments
    ) -> SendResult:
        if not to_address or not to_address.strip():
            return SendResult(success=False, error="Empty recipient address", retryable=False)
        if not subject.strip() or not body_html.strip():
            return SendResult(success=False, error="Empty subject or body", retryable=False)
        try:
            self.validate_credentials()
        except MailerLiteCredentialsError as exc:
            return SendResult(success=False, error=str(exc), retryable=False)

        self._cleanup_old_outbox_groups()

        try:
            group = self._request("POST", "/groups", json={"name": f"{OUTBOX_PREFIX}{uuid.uuid4().hex}"})
            group_id = (group or {}).get("id")
            if not group_id:
                return SendResult(success=False, error="MailerLite did not return a group id")

            self._request(
                "POST",
                f"/groups/{group_id}/subscribers",
                json={"email": to_address.strip(), "resubscribe": False, "autoresponders": False},
            )

            campaign = self._request(
                "POST",
                "/campaigns",
                json={
                    "type": "regular",
                    "name": f"mga-{uuid.uuid4().hex[:12]}",
                    "subject": subject,
                    "from": self.sender_email,
                    "from_name": from_name or self.sender_name,
                    "groups": [group_id],
                },
            )
            campaign_id = (campaign or {}).get("id")
            if not campaign_id:
                return SendResult(success=False, error="MailerLite did not return a campaign id")

            self._request(
                "PUT",
                f"/campaigns/{campaign_id}/content",
                json={"html": _html_document(body_html), "plain": _plain_text(body_html), "auto_inline": True},
            )
            self._request("POST", f"/campaigns/{campaign_id}/actions/send")
            return SendResult(success=True, message_id=str(campaign_id))

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            detail = _error_detail(exc)
            if status in (401, 403):
                return SendResult(
                    success=False,
                    error=f"MailerLite Classic authentication failed (HTTP {status}): {detail}",
                    retryable=False,
                )
            if status in (400, 422):
                if self.sender_email and ("sender" in detail.lower() or "from" in detail.lower()):
                    return SendResult(
                        success=False,
                        error=f"MailerLite rejected the sender {self.sender_email} "
                              f"(is it verified in MailerLite?): {detail}",
                        retryable=False,
                    )
                return SendResult(
                    success=False, error=f"MailerLite rejected the request: {detail}", retryable=False
                )
            if status == 429:
                return SendResult(success=False, error="MailerLite rate limit exceeded (429).")
            return SendResult(success=False, error=f"MailerLite API error (HTTP {status}): {detail}")
        except httpx.RequestError as exc:
            return SendResult(success=False, error=f"Network error contacting MailerLite: {exc}")

    def send_many(
        self, to_addresses: list[str], subject: str, body_html: str, *, from_name: str = ""
    ) -> SendResult:
        """One campaign to several people (the team alert), instead of one
        full group + campaign round per recipient. Never raises."""
        recipients = [a.strip() for a in to_addresses if a and a.strip()]
        if not recipients:
            return SendResult(success=False, error="No recipients", retryable=False)
        if len(recipients) == 1:
            return self.send(recipients[0], subject, body_html, from_name=from_name)
        try:
            self.validate_credentials()
        except MailerLiteCredentialsError as exc:
            return SendResult(success=False, error=str(exc), retryable=False)
        self._cleanup_old_outbox_groups()
        try:
            group = self._request("POST", "/groups", json={"name": f"{OUTBOX_PREFIX}{uuid.uuid4().hex}"})
            group_id = (group or {}).get("id")
            if not group_id:
                return SendResult(success=False, error="MailerLite did not return a group id")
            for r in recipients:
                self._request(
                    "POST",
                    f"/groups/{group_id}/subscribers",
                    json={"email": r, "resubscribe": False, "autoresponders": False},
                )
            campaign = self._request(
                "POST",
                "/campaigns",
                json={
                    "type": "regular",
                    "name": f"mga-{uuid.uuid4().hex[:12]}",
                    "subject": subject,
                    "from": self.sender_email,
                    "from_name": from_name or self.sender_name,
                    "groups": [group_id],
                },
            )
            campaign_id = (campaign or {}).get("id")
            if not campaign_id:
                return SendResult(success=False, error="MailerLite did not return a campaign id")
            self._request(
                "PUT",
                f"/campaigns/{campaign_id}/content",
                json={"html": _html_document(body_html), "plain": _plain_text(body_html), "auto_inline": True},
            )
            self._request("POST", f"/campaigns/{campaign_id}/actions/send")
            return SendResult(success=True, message_id=str(campaign_id))
        except httpx.HTTPStatusError as exc:
            return SendResult(
                success=False,
                error=f"MailerLite API error (HTTP {exc.response.status_code}): {_error_detail(exc)}",
            )
        except httpx.RequestError as exc:
            return SendResult(success=False, error=f"Network error contacting MailerLite: {exc}")

    def add_to_list(
        self, email: str, name: str = "", phone: str = "", *, group_id: str,
        trigger_automations: bool = False,
    ) -> SendResult:
        """Add (or update) the lead in one of the account's real groups, e.g.
        "MGA New Website Subs", with their name and phone. Never raises."""
        first, last = _split_name(name)
        fields = {k: v for k, v in (("last_name", last), ("phone", (phone or "").strip())) if v}
        payload: dict[str, Any] = {
            "email": email.strip(),
            "resubscribe": False,
            "autoresponders": bool(trigger_automations),
        }
        if first:
            payload["name"] = first
        if fields:
            payload["fields"] = fields
        try:
            self.validate_credentials()
            data = self._request("POST", f"/groups/{group_id}/subscribers", json=payload) or {}
            return SendResult(success=True, message_id=str(data.get("id", "")))
        except MailerLiteCredentialsError as exc:
            return SendResult(success=False, error=str(exc), retryable=False)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            hint = " (check MAILERLITE_LEADS_GROUP_ID)" if status == 404 else ""
            return SendResult(
                success=False,
                error=f"Adding to MailerLite group {group_id} failed (HTTP {status}): "
                      f"{_error_detail(exc)}{hint}",
            )
        except httpx.RequestError as exc:
            return SendResult(success=False, error=f"Network error contacting MailerLite: {exc}")

    def send_test_email(self, to_address: str | None = None) -> SendResult:
        target = to_address or self.sender_email
        return self.send(
            target,
            subject="My Growth Academy - MailerLite test email",
            body_html=(
                "This is a test email from the My Growth Academy website backend.\n\n"
                "If you received this, MailerLite sending is set up correctly."
            ),
        )
