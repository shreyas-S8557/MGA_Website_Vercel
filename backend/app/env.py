"""Loads environment variables from .env files, once, at import time.

Looked up in order (earlier files win, since python-dotenv never
overrides a variable that is already set):
  1. <repo root>/.env
  2. backend/.env
  3. ~/.hermes/.env and %LOCALAPPDATA%/hermes/.env, if present
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


def load_env() -> None:
    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(BACKEND_DIR / ".env")
    hermes_env = Path.home() / ".hermes" / ".env"
    if hermes_env.exists():
        load_dotenv(hermes_env)
    local_hermes = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / ".env"
    if local_hermes.exists():
        load_dotenv(local_hermes)


load_env()
