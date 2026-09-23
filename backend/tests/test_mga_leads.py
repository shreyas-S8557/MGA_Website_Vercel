"""
The lead-magnet pipeline (see app/services/mga_lead_service.py). Uses the
shared `client` fixture (tests/conftest.py), which isolates
PROSPECT_DB_PATH per test and sets GOOGLE_FORM_WEBHOOK_SECRET/
MGA_LEAD_MAGNET_DIR to test-safe values. Live email sending is always off
in tests, so delivery here means the PDF becoming downloadable.

Failure is exercised by making lead-magnet *generation* itself fail (e.g.
the PDF renderer raising): the lead must land in status=failed with a
clear error rather than crashing or silently losing the row, and a retry
must resume from the failed stage.
"""
from __future__ import annotations

AUTH = {"X-MGA-Webhook-Secret": "test-secret"}


def _payload(**overrides):
    base = {
        "form_submission_id": "sub-001",
        "name": "Alex Rivera",
        "email": "alex@example.com",
        "phone": "+1-555-0100",
        "answers": {
            "What is your financial goal?": "Build a $20k emergency fund",
            "What's your biggest challenge?": "We overspend on eating out",
        },
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------- ingestion


def test_valid_submission_is_accepted(client):
    resp = client.post("/api/leads/google-form", json=_payload(), headers=AUTH)
    assert resp.status_code == 202
    body = resp.json()
    assert body["form_submission_id"] == "sub-001"
    assert body["duplicate"] is False


def test_missing_secret_is_rejected(client):
    resp = client.post("/api/leads/google-form", json=_payload())
    assert resp.status_code == 401


def test_wrong_secret_is_rejected(client):
    resp = client.post(
        "/api/leads/google-form", json=_payload(), headers={"X-MGA-Webhook-Secret": "nope"}
    )
    assert resp.status_code == 401


def test_missing_answers_is_invalid(client):
    payload = _payload()
    payload["answers"] = {}
    resp = client.post("/api/leads/google-form", json=payload, headers=AUTH)
    assert resp.status_code == 422


def test_malicious_unexpected_input_is_rejected_not_500(client):
    payload = {
        "form_submission_id": "sub-evil",
        "answers": {"<script>": "</script>", "'; DROP TABLE mga_leads;--": "x"},
        "email": "not-an-email",
    }
    resp = client.post("/api/leads/google-form", json=payload, headers=AUTH)
    assert resp.status_code == 422  # clean validation error, not a crash


def test_duplicate_submission_is_idempotent(client):
    first = client.post("/api/leads/google-form", json=_payload(), headers=AUTH)
    second = client.post("/api/leads/google-form", json=_payload(), headers=AUTH)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["lead_id"] == second.json()["lead_id"]
    assert second.json()["duplicate"] is True

    listing = client.get("/api/dashboard/mga-leads").json()
    matching = [l for l in listing["items"] if l["form_submission_id"] == "sub-001"]
    assert len(matching) == 1


def test_retry_of_same_submission_id_never_duplicates(client):
    for _ in range(5):
        client.post("/api/leads/google-form", json=_payload(), headers=AUTH)

    listing = client.get("/api/dashboard/mga-leads").json()
    matching = [l for l in listing["items"] if l["form_submission_id"] == "sub-001"]
    assert len(matching) == 1


# ---------------------------------------------------------------- profiling


def test_known_answer_combinations_map_to_canonical_keys():
    from app.services.lead_profile_service import analyze_answers

    answers = {
        "What is your financial goal?": "Pay off $10k in credit card debt",
        "What's your biggest challenge?": "We don't talk about money enough",
    }
    profile = analyze_answers(answers)
    assert profile["financial_goal"] == "Pay off $10k in credit card debt"
    assert profile["primary_challenge"] == "We don't talk about money enough"


def test_unknown_question_is_ignored_not_crashing():
    from app.services.lead_profile_service import analyze_answers

    profile = analyze_answers({"Favorite color?": "Blue"})
    assert profile["financial_goal"] is None


def test_missing_answer_defaults_to_none():
    from app.services.lead_profile_service import analyze_answers

    profile = analyze_answers({})
    assert all(v is None for v in profile.values())


def test_field_map_override_takes_priority():
    from app.services.lead_profile_service import analyze_answers

    profile = analyze_answers({"Q7": "Retire early"}, field_map={"Q7": "financial_goal"})
    assert profile["financial_goal"] == "Retire early"


# ------------------------------------------------------------- lead magnet


def test_select_lead_magnet_matches_budgeting_keyword():
    from app.services.lead_magnet_service import select_lead_magnet

    assert select_lead_magnet({"primary_challenge": "We overspend and never budget"}) == "budgeting"


def test_select_lead_magnet_falls_back_to_future_state():
    from app.services.lead_magnet_service import select_lead_magnet

    assert select_lead_magnet({"primary_challenge": "not sure"}) == "future_state_planning"


def test_generate_personalized_content_without_llm_key_uses_fallback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from app.services.lead_magnet_service import _REQUIRED_KEYS, generate_personalized_content

    content = generate_personalized_content({"financial_goal": "Save $10k"})
    assert _REQUIRED_KEYS.issubset(content.keys())


def test_generate_personalized_content_falls_back_on_llm_failure(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    import app.services.lead_magnet_service as svc

    monkeypatch.setattr(svc, "_generate_via_llm", lambda profile: None)
    content = svc.generate_personalized_content({"financial_goal": "Save $10k"})
    assert svc._REQUIRED_KEYS.issubset(content.keys())


def test_render_lead_magnet_writes_a_pdf(tmp_path, monkeypatch):
    import app.services.pdf_service as pdf_service

    monkeypatch.setattr(pdf_service, "MGA_LEAD_MAGNET_DIR", str(tmp_path))
    from app.services.lead_magnet_service import _fallback_content, generate_secure_lead_magnet_id

    content = _fallback_content({"financial_goal": "Save $10k"})
    magnet_id = generate_secure_lead_magnet_id()
    path = pdf_service.render_lead_magnet(
        magnet_id, "Your Personalized Financial Growth Map", content, "Alex"
    )
    import os

    assert os.path.exists(path)
    assert os.path.getsize(path) > 0


# ----------------------------------------------------------------- delivery


def test_pipeline_runs_end_to_end_and_delivers_without_any_email_provider(client, monkeypatch):
    """DELIVERED must never depend on an email provider being configured:
    the test client fixture leaves PROSPECT_ALLOW_LIVE_SEND unset/false, so
    the best-effort delivery-email send is skipped (email_sent stays
    False), and the lead must still land in status=delivered purely from
    the PDF existing and being downloadable via the dashboard/API."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    resp = client.post("/api/leads/google-form", json=_payload(), headers=AUTH)
    lead_id = resp.json()["lead_id"]

    detail = client.get(f"/api/dashboard/mga-leads/{lead_id}").json()
    assert detail["status"] == "delivered"
    assert detail["profile"] is not None
    assert detail["lead_magnet_id"]
    assert detail["lead_magnet_delivery_url"]
    assert detail["delivered_at"]
    assert detail["email_sent"] is False
    assert detail["email_error"]


def test_pipeline_fails_closed_when_lead_magnet_generation_fails(client, monkeypatch):
    """A failure in lead-magnet generation (the stage before delivery) must
    land the lead in status=failed with a clear error, never crash the
    request or silently mark it delivered. Profiling (the stage before
    that) must still have completed."""
    import app.services.mga_lead_service as svc

    def _boom(*args, **kwargs):
        raise RuntimeError("PDF renderer exploded")

    monkeypatch.setattr(svc.pdf_service, "render_lead_magnet", _boom)

    resp = client.post("/api/leads/google-form", json=_payload(), headers=AUTH)
    lead_id = resp.json()["lead_id"]

    detail = client.get(f"/api/dashboard/mga-leads/{lead_id}").json()
    assert detail["status"] == "failed"
    assert detail["failed_stage"] == "lead_magnet_generating"
    assert "PDF renderer exploded" in detail["error_message"]
    # Earlier stage still completed and is visible for support/debugging.
    assert detail["profile"] is not None
    assert not detail["lead_magnet_id"]
    assert not detail["delivered_at"]


def test_retry_recovers_from_lead_magnet_generation_failure(client, monkeypatch):
    import app.services.mga_lead_service as svc

    def _boom(*args, **kwargs):
        raise RuntimeError("PDF renderer exploded")

    monkeypatch.setattr(svc.pdf_service, "render_lead_magnet", _boom)
    resp = client.post("/api/leads/google-form", json=_payload(), headers=AUTH)
    lead_id = resp.json()["lead_id"]
    assert client.get(f"/api/dashboard/mga-leads/{lead_id}").json()["status"] == "failed"

    monkeypatch.undo()  # restore the real render_lead_magnet
    retry_resp = client.post(f"/api/leads/{lead_id}/retry", headers=AUTH)
    assert retry_resp.status_code == 200
    assert retry_resp.json()["status"] == "delivered"

    detail = client.get(f"/api/dashboard/mga-leads/{lead_id}").json()
    assert detail["lead_magnet_id"]
    assert detail["delivered_at"]


def test_successful_delivery_makes_lead_magnet_downloadable(client):
    resp = client.post("/api/leads/google-form", json=_payload(email="jordan@example.com"), headers=AUTH)
    lead_id = resp.json()["lead_id"]

    detail = client.get(f"/api/dashboard/mga-leads/{lead_id}").json()
    assert detail["status"] == "delivered"
    assert detail["delivered_at"]

    download = client.get(detail["lead_magnet_delivery_url"])
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"


def test_retry_on_already_delivered_lead_is_idempotent(client):
    """Re-running the pipeline on an already-DELIVERED lead (e.g. via a
    manual retry click) must not regenerate the lead magnet or otherwise
    redo work that already finished."""
    resp = client.post("/api/leads/google-form", json=_payload(email="jordan@example.com"), headers=AUTH)
    lead_id = resp.json()["lead_id"]
    first_detail = client.get(f"/api/dashboard/mga-leads/{lead_id}").json()
    assert first_detail["status"] == "delivered"

    retry_resp = client.post(f"/api/leads/{lead_id}/retry", headers=AUTH)
    assert retry_resp.status_code == 200
    assert retry_resp.json()["status"] == "delivered"

    second_detail = client.get(f"/api/dashboard/mga-leads/{lead_id}").json()
    assert second_detail["lead_magnet_id"] == first_detail["lead_magnet_id"]
    assert second_detail["delivered_at"] == first_detail["delivered_at"]


# --------------------------------------------------------- health


def test_health_route_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200


def test_fallback_copy_reads_naturally():
    """Regression: the template copy used to produce 'Protect yes of focused
    time', doubled full stops ('It is good..') and the same sentence twice."""
    from app.services.lead_magnet_service import _fallback_content

    content = _fallback_content({
        "primary_challenge": "lack of discipline.",
        "desired_future_state": "It is good.",
        "growth_areas": ["Discipline", "Time Management"],
        "support_preferences": ["New skills or knowledge"],
        "time_commitment": "Yes",
        "seriousness_score": "7",
        "seriousness_reason": "I want to change",
    })
    text = " ".join(content.values())
    assert ".." not in text
    assert "Protect yes" not in text
    assert "30 to 45 minutes a day" in content["priority_3"]
    # the person's own words are kept as written
    assert "\u201cI want to change.\u201d" in content["starting_point"]
    assert "\u201cIt is good.\u201d" in content["desired_future_state"]
    assert content["starting_point"] != content["biggest_constraint"]


def test_branded_pdf_renders_unicode_names_and_long_text(tmp_path, monkeypatch):
    monkeypatch.setenv("MGA_LEAD_MAGNET_DIR", str(tmp_path))
    import importlib

    import app.config
    import app.services.pdf_service as pdf_service

    importlib.reload(app.config)
    importlib.reload(pdf_service)
    content = {k: ("Zoë & Łukasz — “quoted” ✨ " * 12) for k in (
        "starting_point", "desired_future_state", "biggest_constraint", "priority_1",
        "priority_2", "priority_3", "next_30_days", "next_90_days", "one_habit")}
    path = pdf_service.render_lead_magnet("unicode", "Your Personalized Growth Map", content, "Zoë")
    data = open(path, "rb").read()
    assert data.startswith(b"%PDF") and len(data) > 10_000


def test_copy_follows_house_style():
    """No dashes as punctuation, no coaching jargon, no 'not X, but Y'
    set-ups, in either the template copy or the fixed PDF text."""
    import re
    from pathlib import Path

    from app.services.lead_magnet_service import _fallback_content, generate_personalized_content

    profiles = [
        {},
        {"primary_challenge": "time", "desired_future_state": "Debt free and a house",
         "growth_areas": ["Financial Growth"], "time_commitment": "Not right now"},
        {"primary_challenge": "lack of discipline.", "desired_future_state": "It is good.",
         "growth_areas": ["Discipline", "Time Management", "Business Skills"],
         "support_preferences": ["Mentorship from people who have already achieved results"],
         "time_commitment": "Most days", "seriousness_score": "7",
         "seriousness_reason": "I want to change but keep procrastinating"},
    ]
    pdf_src = Path("app/services/pdf_service.py").read_text()
    pdf_strings = " ".join(re.findall(r'"([^"\n]{25,})"', pdf_src))
    banned = ["trajectory", "journey", "transform", "unlock", "empower", "elevate",
              "optimi", "leverage", "intentional", "strategic", "holistic", "actionable",
              "compound", "measurable", "design around", "designing around", "best self",
              "better version", "move the needle", "lasting change", "take ownership",
              "the real product", "who you become", "\u2014", "\u2013", " -- "]
    for profile in profiles:
        text = " ".join(_fallback_content(profile).values()) + " " + " ".join(
            generate_personalized_content(profile).values())
        for bad in banned:
            assert bad not in text.lower(), (bad, text)
        assert not re.search(r"\bnot just\b|\bisn't about\b|\brather than\b", text.lower())
    for bad in banned:
        assert bad not in pdf_strings.lower(), bad


def test_small_numbers_are_written_as_words_outside_quotes():
    from app.services.lead_magnet_service import numbers_to_words

    # the readiness score is the one exception: it keeps its digit
    assert numbers_to_words("You rated yourself 7 out of 10.") == "You rated yourself 7 out of 10."
    assert numbers_to_words("7 things") == "Seven things"
    assert numbers_to_words("3 years") == "Three years"
    assert numbers_to_words("a 3-year plan, 30 to 45 minutes") == "a three-year plan, 30 to 45 minutes"
    # the person's own words stay exactly as written; scores/money/decimals untouched
    assert numbers_to_words("\u201cI have 2 kids\u201d") == "\u201cI have 2 kids\u201d"
    for kept in ("7/10", "$5", "3.5 hours", "9am", "10 minutes"):
        assert numbers_to_words(kept) == kept


def test_lead_magnet_copy_is_short():
    from app.services.lead_magnet_service import _fallback_content

    long = " ".join(["word"] * 80)
    content = _fallback_content({
        "primary_challenge": long, "desired_future_state": long, "seriousness_reason": long,
        "growth_areas": ["Discipline"], "support_preferences": ["New skills or knowledge"],
        "time_commitment": "Yes", "seriousness_score": "7",
    })
    for key, value in content.items():
        assert len(value.split()) <= 35, (key, value)
    assert "7 out of 10" in content["starting_point"]


def test_llm_copy_is_capped(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    import app.services.lead_magnet_service as svc

    chatty = "One sentence here. Another one. And a third. And a fourth."
    monkeypatch.setattr(svc, "_generate_via_llm", lambda p: {k: chatty for k in svc._REQUIRED_KEYS})
    content = svc.generate_personalized_content({})
    assert all(v == "One sentence here. Another one." for v in content.values())
