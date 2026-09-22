from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A TestClient wired to a fresh, isolated SQLite file per test -- never
    the real data/pipeline_state.db, and never touching the network or
    sending real email (PROSPECT_ALLOW_LIVE_SEND is forced off)."""
    db_path = tmp_path / f"test_{uuid.uuid4().hex}.db"
    monkeypatch.setenv("PROSPECT_DB_PATH", str(db_path))
    monkeypatch.setenv("PROSPECT_ALLOW_LIVE_SEND", "false")
    # A fixed Google Form webhook secret (so webhook tests don't need their
    # own fixture) and an isolated PDF output dir
    # under this test's own tmp_path (never the real data/mga_lead_magnets).
    monkeypatch.setenv("GOOGLE_FORM_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("MGA_LEAD_MAGNET_DIR", str(tmp_path / "mga_lead_magnets"))
    # Dashboard routes require X-Dashboard-Key. The shared client sends it
    # by default; the auth tests in test_dashboard_auth.py strip it to prove it's enforced.
    monkeypatch.setenv("DASHBOARD_API_KEY", "test-dashboard-key")
    monkeypatch.delenv("DASHBOARD_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("LEAD_NOTIFY_EMAILS", raising=False)

    # Reload app.config + app.db.database so they pick up the monkeypatched
    # env var rather than a value cached from a previous test's import.
    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app, headers={"X-Dashboard-Key": "test-dashboard-key"}) as c:
        yield c
