"""Google Sheets mirror, the redesigned delivery email, the Calendly
booking link and the Gemini LLM settings. No network: the sheet's HTTP
call and the LLM are stubbed out."""
from __future__ import annotations

import json

WEBSITE_PAYLOAD = {
    "name": "Priya Shah",
    "email": "priya@example.com",
    "phone": "+91 98765 43210",
    "answers": {
        "Where would you like to be in 3 years?": "Own our first home",
        "What's in the way?": "<script>alert(1)</script>",
    },
}


def test_leads_are_mirrored_to_google_sheet(client, monkeypatch):
    import app.config as config
    from app.services import sheets_sync

    monkeypatch.setattr(config, "GOOGLE_SHEETS_WEBHOOK_URL", "https://script.google.com/x/exec")
    monkeypatch.setattr(config, "GOOGLE_SHEETS_WEBHOOK_SECRET", "s3cret")
    posted: list[list[dict]] = []
    monkeypatch.setattr(sheets_sync, "_post", lambda rows: posted.append(rows) or "")

    r = client.post("/api/leads/website", json=WEBSITE_PAYLOAD)
    assert r.status_code == 202
    lead_id = r.json()["lead_id"]

    assert len(posted) == 1
    row = posted[0][0]
    assert row["Lead ID"] == lead_id
    assert row["Name"] == "Priya Shah"
    assert row["Phone"] == "+91 98765 43210"
    assert row["Status"] == "delivered"
    assert "/api/lead-magnets/" in row["PDF Link"]
    assert row["Q: Where would you like to be in 3 years?"] == "Own our first home"

    detail = client.get(f"/api/dashboard/mga-leads/{lead_id}").json()
    assert detail["sheet_synced_at"]
    assert detail["sheet_sync_error"] == ""


def test_sheet_failure_never_breaks_the_lead(client, monkeypatch):
    import app.config as config
    from app.services import sheets_sync

    monkeypatch.setattr(config, "GOOGLE_SHEETS_WEBHOOK_URL", "https://script.google.com/x/exec")
    monkeypatch.setattr(config, "GOOGLE_SHEETS_WEBHOOK_SECRET", "s3cret")

    def boom(rows):
        raise RuntimeError("sheet down")

    monkeypatch.setattr(sheets_sync, "_post", boom)
    r = client.post("/api/leads/website", json=WEBSITE_PAYLOAD)
    assert r.status_code == 202
    assert r.json()["status"] == "delivered"
    detail = client.get(f"/api/dashboard/mga-leads/{r.json()['lead_id']}").json()
    assert "sheet down" in detail["sheet_sync_error"]


def test_sheet_sync_off_by_default(client, monkeypatch):
    from app.services import sheets_sync

    called = []
    monkeypatch.setattr(sheets_sync, "_post", lambda rows: called.append(rows) or "")
    client.post("/api/leads/website", json=WEBSITE_PAYLOAD)
    assert called == []


def test_sync_all_backfills_oldest_first(client, monkeypatch):
    import app.config as config
    from app.services import sheets_sync

    for i in range(3):
        client.post("/api/leads/website", json={**WEBSITE_PAYLOAD, "name": f"Lead {i}"})

    monkeypatch.setattr(config, "GOOGLE_SHEETS_WEBHOOK_URL", "https://script.google.com/x/exec")
    monkeypatch.setattr(config, "GOOGLE_SHEETS_WEBHOOK_SECRET", "s3cret")
    posted: list[list[dict]] = []
    monkeypatch.setattr(sheets_sync, "_post", lambda rows: posted.append(rows) or "")

    r = client.post("/api/dashboard/sheets/sync-all")
    assert r.status_code == 200
    assert r.json()["synced"] == 3
    assert [row["Name"] for row in posted[0]] == ["Lead 0", "Lead 1", "Lead 2"]


def test_sync_all_needs_dashboard_key(client):
    r = client.post("/api/dashboard/sheets/sync-all", headers={"X-Dashboard-Key": "wrong"})
    assert r.status_code == 401


def test_delivery_email_design_and_booking_link(client):
    import app.config as config
    from app.services.email_templates import build_report_email

    subject, body = build_report_email(
        name="Priya <b>Shah</b>",
        content={
            "title": "Your Personalized Financial Growth Map",
            "starting_point": "You rated yourself 7 out of 10.",
            "biggest_constraint": "<script>alert(1)</script>",
            "priority_1": "Start with money.",
            "priority_2": "Get support.",
            "priority_3": "Use your time.",
            "next_30_days": "One step a day.",
            "one_habit": "Note one win.",
        },
        download_url="https://api.example.com/api/lead-magnets/abc",
        booking_url=config.BOOKING_URL,
        booking_label=config.BOOKING_LABEL,
        site_url="https://mygrowthacademy.coach",
        site_display="mygrowthacademy.coach",
        logo_url="https://mygrowthacademy.coach/images/logo.png",
    )
    assert subject == "Priya, your Growth Blueprint is ready"
    assert "https://calendly.com/shaku-c-miriyala/mygrowth-academy" in body
    assert "Book a Free Call" in body
    assert "https://api.example.com/api/lead-magnets/abc" in body
    assert "<script>" not in body and "<b>Shah</b>" not in body
    assert "Your first three priorities" not in body  # the PDF has the details
    assert "—" not in body  # house style: no em dashes


def test_pdf_cta_links_to_calendly(client):
    r = client.post("/api/leads/website", json=WEBSITE_PAYLOAD)
    url = r.json()["lead_magnet_delivery_url"]
    pdf = client.get(url).content
    assert b"calendly.com/shaku-c-miriyala/mygrowth-academy" in pdf


def test_gemini_settings(monkeypatch):
    from app import llm

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert llm.llm_settings() is None

    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    s = llm.llm_settings()
    assert s.is_gemini
    assert s.base_url == "https://generativelanguage.googleapis.com/v1beta/openai/"
    assert s.model == llm.GEMINI_DEFAULT_MODEL

    monkeypatch.setenv("LLM_MODEL", "gemini-3.5-flash-lite")
    assert llm.llm_settings().model == "gemini-3.5-flash-lite"


def test_gemini_request_shape(monkeypatch):
    """The call asks Gemini for low thinking and enough tokens for the JSON."""
    from app.services import lead_magnet_service as svc

    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    captured = {}
    answer = {k: "Short line." for k in svc._REQUIRED_KEYS}

    class _Msg:
        content = json.dumps(answer)

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    class _Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _Resp()

    class _Client:
        chat = type("C", (), {"completions": _Completions()})()

    monkeypatch.setattr(svc, "get_llm_client", lambda settings=None: _Client())
    out = svc._generate_via_llm({"desired_future_state": "a home"})
    assert out == answer
    assert captured["extra_body"] == {"reasoning_effort": "low"}
    assert captured["max_tokens"] >= 2048
