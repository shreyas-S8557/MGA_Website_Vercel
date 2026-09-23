"""Team notification email for new leads (LEAD_NOTIFY_EMAILS) -- see
mga_lead_service.notify_team. Never touches the network: the sender is
replaced with an in-memory fake."""
from __future__ import annotations

from dataclasses import dataclass

AUTH = {"X-MGA-Webhook-Secret": "test-secret"}


@dataclass
class _Result:
    success: bool
    error: str = ""
    message_id: str = "fake"


class _FakeSender:
    def __init__(self, fail_for: set[str] | None = None):
        self.sent: list[tuple[str, str, str]] = []
        self.fail_for = fail_for or set()

    def send(self, to, subject, body, *, from_name="", attachments=None):
        if to in self.fail_for:
            return _Result(success=False, error="boom")
        self.sent.append((to, subject, body))
        return _Result(success=True)


def _enable(monkeypatch, recipients, sender):
    import app.config as config
    from app.services import sending_service

    monkeypatch.setattr(config, "LEAD_NOTIFY_EMAILS", recipients)
    monkeypatch.setattr(sending_service, "get_sender", lambda mode, **kw: sender)


def _website_lead(client, **overrides):
    body = {
        "name": "Priya Shah",
        "email": "priya@example.com",
        "phone": "+91 98765 43210",
        "answers": {"3 years from now": "Own our first home", "biggest thing standing": "Debt"},
    }
    body.update(overrides)
    resp = client.post("/api/leads/website", json=body)
    assert resp.status_code == 202
    return resp.json()["lead_id"]


def test_new_lead_notifies_every_recipient(client, monkeypatch):
    sender = _FakeSender()
    _enable(monkeypatch, ["kanth@example.com", "shaku@example.com"], sender)

    lead_id = _website_lead(client)

    team_mails = [m for m in sender.sent if m[0] in ("kanth@example.com", "shaku@example.com")]
    assert {m[0] for m in team_mails} == {"kanth@example.com", "shaku@example.com"}
    to, subject, body = team_mails[0]
    assert "Priya Shah" in subject
    assert "priya@example.com" in body
    assert "+91 98765 43210" in body
    assert "Own our first home" in body
    assert "/api/lead-magnets/" in body

    detail = client.get(f"/api/dashboard/mga-leads/{lead_id}").json()
    assert detail["team_notified_at"]
    assert detail["team_notify_error"] == ""


def test_no_recipients_means_no_notification(client, monkeypatch):
    sender = _FakeSender()
    _enable(monkeypatch, [], sender)
    lead_id = _website_lead(client)
    assert not [m for m in sender.sent if m[1].startswith("New MGA lead")]
    assert client.get(f"/api/dashboard/mga-leads/{lead_id}").json()["team_notified_at"] == ""


def test_duplicate_or_retry_never_renotifies(client, monkeypatch):
    sender = _FakeSender()
    _enable(monkeypatch, ["kanth@example.com"], sender)
    payload = {
        "form_submission_id": "sub-dup",
        "name": "Alex",
        "email": "alex@example.com",
        "answers": {"goal": "Emergency fund"},
    }
    first = client.post("/api/leads/google-form", json=payload, headers=AUTH).json()
    client.post("/api/leads/google-form", json=payload, headers=AUTH)
    client.post(f"/api/leads/{first['lead_id']}/retry", headers=AUTH)
    notes = [m for m in sender.sent if m[0] == "kanth@example.com"]
    assert len(notes) == 1


def test_failed_notification_never_breaks_the_lead(client, monkeypatch):
    sender = _FakeSender(fail_for={"kanth@example.com"})
    _enable(monkeypatch, ["kanth@example.com"], sender)
    lead_id = _website_lead(client)
    detail = client.get(f"/api/dashboard/mga-leads/{lead_id}").json()
    assert detail["status"] == "delivered"
    assert detail["team_notified_at"] == ""
    assert "boom" in detail["team_notify_error"]


def test_live_sending_off_is_recorded_not_raised(client, monkeypatch):
    import app.config as config

    monkeypatch.setattr(config, "LEAD_NOTIFY_EMAILS", ["kanth@example.com"])
    lead_id = _website_lead(client)  # real get_sender: live sending is off in tests
    detail = client.get(f"/api/dashboard/mga-leads/{lead_id}").json()
    assert detail["status"] == "delivered"
    assert detail["team_notified_at"] == ""
    assert "PROSPECT_ALLOW_LIVE_SEND" in detail["team_notify_error"]


def test_notification_escapes_visitor_input(client, monkeypatch):
    sender = _FakeSender()
    _enable(monkeypatch, ["kanth@example.com"], sender)
    _website_lead(client, name="<script>x</script>", answers={"goal": "<b>hi</b>"})
    body = [m for m in sender.sent if m[0] == "kanth@example.com"][0][2]
    assert "<script>" not in body and "<b>hi</b>" not in body


def test_team_alert_can_use_a_different_provider(monkeypatch):
    """Visitor reports via MailerLite, team alerts via Gmail/Workspace."""
    import app.config as config
    from app.services import sending_service

    monkeypatch.setattr(sending_service, "ALLOW_LIVE_SEND", True)
    monkeypatch.setattr(sending_service, "EMAIL_PROVIDER", "mailerlite")
    monkeypatch.setenv("GMAIL_ADDRESS", "team@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "abcdabcdabcdabcd")
    monkeypatch.setenv("MAILERLITE_API_TOKEN", "tok")
    monkeypatch.setenv("MAILERLITE_SENDER_EMAIL", "hello@example.com")
    monkeypatch.setenv("MAILERLITE_SENDER_NAME", "MGA")
    assert type(sending_service.get_sender("live")).__name__ == "MailerLiteSender"
    assert type(sending_service.get_sender("live", provider="gmail")).__name__ == "GmailSender"
