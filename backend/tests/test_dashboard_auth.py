"""Dashboard access key (DASHBOARD_API_KEY) -- see app/main.py's
require_dashboard_key middleware. Lead data must never be readable
without the key, while the routes the public website needs stay open."""
from __future__ import annotations

NO_KEY = {"X-Dashboard-Key": ""}


def test_leads_list_rejected_without_key(client):
    resp = client.get("/api/dashboard/mga-leads", headers=NO_KEY)
    assert resp.status_code == 401


def test_lead_detail_rejected_with_wrong_key(client):
    resp = client.get("/api/dashboard/mga-leads/anything", headers={"X-Dashboard-Key": "nope"})
    assert resp.status_code == 401


def test_other_dashboard_routes_also_protected(client):
    assert client.get("/api/settings", headers=NO_KEY).status_code == 401
    assert client.get("/api/dashboard/mga-leads/summary", headers=NO_KEY).status_code == 401


def test_leads_list_allowed_with_key(client):
    resp = client.get("/api/dashboard/mga-leads")  # client sends the test key by default
    assert resp.status_code == 200


def test_public_routes_need_no_key(client):
    assert client.get("/api/health", headers=NO_KEY).status_code == 200
    resp = client.post(
        "/api/leads/website",
        headers=NO_KEY,
        json={"name": "Sam", "email": "sam@example.com", "answers": {"goal": "Save more"}},
    )
    assert resp.status_code == 202
    url = resp.json()["lead_magnet_delivery_url"]
    assert url
    assert client.get(url, headers=NO_KEY).status_code == 200


def test_preflight_is_not_blocked(client):
    resp = client.options(
        "/api/dashboard/mga-leads",
        headers={
            "X-Dashboard-Key": "",
            "Origin": "http://localhost:8080",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-dashboard-key",
        },
    )
    assert resp.status_code == 200


def test_unset_key_locks_dashboard(client, monkeypatch):
    import app.config as config

    monkeypatch.setattr(config, "DASHBOARD_API_KEY", "")
    resp = client.get("/api/dashboard/mga-leads")
    assert resp.status_code == 503


def test_local_dev_opt_out(client, monkeypatch):
    import app.config as config

    monkeypatch.setattr(config, "DASHBOARD_AUTH_DISABLED", True)
    assert client.get("/api/dashboard/mga-leads", headers=NO_KEY).status_code == 200
