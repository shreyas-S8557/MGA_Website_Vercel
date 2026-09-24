"""MailerLite Classic (Legacy) adapter -- never touches the network: the
httpx client is replaced with a scripted fake."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from app.senders.mailerlite_classic_sender import MailerLiteClassicSender


class _Resp:
    def __init__(self, status: int, payload=None):
        self.status_code = status
        self._payload = payload
        self.content = b"1" if payload is not None else b""
        self.headers: dict = {}
        self.text = ""

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request("POST", "https://api.mailerlite.com/api/v2/x")
            raise httpx.HTTPStatusError("err", request=req, response=self)  # type: ignore[arg-type]


class _Client:
    def __init__(self, routes, calls, headers=None, **_):
        self.routes, self.calls, self.headers = routes, calls, headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def request(self, method, path, json=None):
        self.calls.append((method, path, json, self.headers))
        for (m, prefix), resp in self.routes.items():
            if m == method and path.split("?")[0] == prefix:
                return resp
        for (m, prefix), resp in self.routes.items():
            if m == method and prefix.endswith("*") and path.startswith(prefix[:-1]):
                return resp
        return _Resp(404, {"error": {"message": "not found"}})


def _routes(extra=None):
    routes = {
        ("GET", "/groups"): _Resp(200, []),
        ("POST", "/groups"): _Resp(200, {"id": 11, "name": "mga-outbox-x"}),
        ("POST", "/groups/11/subscribers"): _Resp(200, {"id": 5, "email": "lead@example.com"}),
        ("POST", "/campaigns"): _Resp(200, {"id": 77}),
        ("PUT", "/campaigns/77/content"): _Resp(200, {"success": True}),
        ("POST", "/campaigns/77/actions/send"): _Resp(200, {"id": 77, "status": "outbox"}),
    }
    routes.update(extra or {})
    return routes


def _sender(routes, calls):
    return MailerLiteClassicSender(
        api_key="classic-key", sender_email="hello@example.com", sender_name="MGA",
        http_client_factory=lambda **kw: _Client(routes, calls, **kw),
    )


def test_classic_send_flow_uses_classic_api_and_isolated_group():
    calls: list = []
    result = _sender(_routes(), calls).send(
        "lead@example.com", "Your report", '<div><p style="color:red">Hi &amp; welcome</p></div>'
    )
    assert result.success and result.message_id == "77"
    steps = [(m, p.split("?")[0]) for m, p, _, _ in calls]
    assert steps == [
        ("GET", "/groups"),
        ("POST", "/groups"),
        ("POST", "/groups/11/subscribers"),
        ("POST", "/campaigns"),
        ("PUT", "/campaigns/77/content"),
        ("POST", "/campaigns/77/actions/send"),
    ]
    # Classic auth header, never a Bearer token
    assert calls[0][3]["X-MailerLite-ApiKey"] == "classic-key"
    # only the recipient, and none of the account's own automations fire
    sub = calls[2][2]
    assert sub == {"email": "lead@example.com", "resubscribe": False, "autoresponders": False}
    campaign = calls[3][2]
    assert campaign["groups"] == [11] and campaign["from"] == "hello@example.com"
    content = calls[4][2]
    assert "<head>" in content["html"] and "<body>" in content["html"]
    assert '<p style="color:red">Hi &amp; welcome</p>' in content["html"]  # not double-escaped
    assert "{$unsubscribe}" in content["html"]
    assert "{$unsubscribe}" in content["plain"] and "{$url}" in content["plain"]
    assert "Hi & welcome" in content["plain"]


def test_classic_bad_key_is_reported_not_raised():
    calls: list = []
    routes = _routes({("POST", "/groups"): _Resp(401, {"error": {"message": "Unauthorized"}})})
    result = _sender(routes, calls).send("lead@example.com", "S", "Body")
    assert not result.success and not result.retryable
    assert "authentication failed" in result.error


def test_classic_deletes_only_old_outbox_groups():
    old = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    new = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    routes = _routes({
        ("GET", "/groups"): _Resp(200, [
            {"id": 1, "name": "mga-outbox-old", "date_created": old},
            {"id": 2, "name": "mga-outbox-new", "date_created": new},
            {"id": 3, "name": "Newsletter subscribers", "date_created": old},
        ]),
        ("DELETE", "/groups/*"): _Resp(204, None),
    })
    calls: list = []
    assert _sender(routes, calls).send("lead@example.com", "S", "Body").success
    assert [p for m, p, _, _ in calls if m == "DELETE"] == ["/groups/1"]


def test_classic_provider_is_selectable(monkeypatch):
    from app.services import sending_service

    monkeypatch.setattr(sending_service, "ALLOW_LIVE_SEND", True)
    monkeypatch.setenv("MAILERLITE_API_TOKEN", "k")
    monkeypatch.setenv("MAILERLITE_SENDER_EMAIL", "hello@example.com")
    monkeypatch.setenv("MAILERLITE_SENDER_NAME", "MGA")
    sender = sending_service.get_sender("live", provider="mailerlite_classic")
    assert type(sender).__name__ == "MailerLiteClassicSender"


def test_classic_adds_lead_to_real_group_with_name_and_phone():
    routes = _routes({("POST", "/groups/112974522/subscribers"): _Resp(200, {"id": 9})})
    calls: list = []
    result = _sender(routes, calls).add_to_list(
        "priya@example.com", "Priya Shah", "+91 98765 43210", group_id="112974522"
    )
    assert result.success
    method, path, payload, headers = calls[0]
    assert (method, path) == ("POST", "/groups/112974522/subscribers")
    assert payload == {
        "email": "priya@example.com", "name": "Priya",
        "fields": {"last_name": "Shah", "phone": "+91 98765 43210"},
        "resubscribe": False, "autoresponders": False,  # group automations off by default
    }


def test_classic_wrong_group_id_is_reported():
    calls: list = []
    result = _sender(_routes(), calls).add_to_list("a@example.com", group_id="999")
    assert not result.success and "MAILERLITE_LEADS_GROUP_ID" in result.error


def test_pipeline_adds_lead_to_group_only_when_configured(monkeypatch):
    import app.config as config
    from app.services import mga_lead_service, sending_service

    added = []

    class _Fake:
        def add_to_list(self, email, name="", phone="", *, group_id, trigger_automations=False):
            added.append((email, name, phone, group_id, trigger_automations))
            from app.senders.mailerlite_sender import SendResult
            return SendResult(success=True)

    monkeypatch.setattr(sending_service, "get_sender", lambda mode, **kw: _Fake())
    row = {"email": "priya@example.com", "name": "Priya Shah", "phone": "123"}

    monkeypatch.setattr(config, "MAILERLITE_LEADS_GROUP_ID", "")
    monkeypatch.setattr(config, "ALLOW_LIVE_SEND", True)
    monkeypatch.setattr(config, "EMAIL_PROVIDER", "mailerlite_classic")
    assert mga_lead_service._add_to_mailerlite_list(row) == "" and added == []

    monkeypatch.setattr(config, "MAILERLITE_LEADS_GROUP_ID", "112974522")
    monkeypatch.setattr(config, "ALLOW_LIVE_SEND", False)
    assert mga_lead_service._add_to_mailerlite_list(row) == "" and added == []

    monkeypatch.setattr(config, "ALLOW_LIVE_SEND", True)
    assert mga_lead_service._add_to_mailerlite_list(row) == ""
    assert added == [("priya@example.com", "Priya Shah", "123", "112974522", False)]
