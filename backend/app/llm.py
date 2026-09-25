"""LLM client + a tolerant JSON-object extractor, used by
lead_magnet_service to personalize each lead's report.

Google Gemini (free tier) is the default, through Google's
OpenAI-compatible endpoint, so the same `openai` client library works
unchanged. Configured entirely through environment variables:

  GEMINI_API_KEY   -- a Google AI Studio key (https://aistudio.google.com/apikey).
                      When set, Gemini is used.
  LLM_MODEL        -- model name (default "gemini-3.5-flash" for Gemini).

Any other OpenAI-compatible provider still works instead of Gemini:
  OPENAI_API_KEY   -- that provider's key (used only if GEMINI_API_KEY is unset)
  OPENAI_BASE_URL  -- its endpoint
  LLM_MODEL        -- its model name

With no key at all, the deterministic template fallback is used instead.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
# A stable model on Gemini's free tier. Override with LLM_MODEL (e.g.
# gemini-3.5-flash-lite for higher free-tier limits).
GEMINI_DEFAULT_MODEL = "gemini-3.5-flash"


@dataclass(frozen=True)
class LLMSettings:
    api_key: str
    base_url: str
    model: str
    is_gemini: bool


def llm_settings() -> LLMSettings | None:
    """Which LLM to call, or None when no key is configured."""
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if gemini_key:
        model = os.environ.get("LLM_MODEL", "").strip()
        # "auto" was the old provider's setting; Gemini needs a real name.
        if not model or model.lower() == "auto" or not model.lower().startswith("gemini"):
            model = GEMINI_DEFAULT_MODEL
        return LLMSettings(
            api_key=gemini_key,
            base_url=os.environ.get("GEMINI_BASE_URL", "").strip() or GEMINI_BASE_URL,
            model=model,
            is_gemini=True,
        )
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key:
        base_url = os.environ.get("OPENAI_BASE_URL", "").strip() or GEMINI_BASE_URL
        return LLMSettings(
            api_key=openai_key,
            base_url=base_url,
            model=os.environ.get("LLM_MODEL", "").strip()
            or (GEMINI_DEFAULT_MODEL if "generativelanguage.googleapis.com" in base_url else "auto"),
            is_gemini="generativelanguage.googleapis.com" in base_url,
        )
    return None


def get_llm_client(settings: LLMSettings | None = None) -> OpenAI:
    settings = settings or llm_settings()
    if settings is None:
        raise RuntimeError("No LLM configured: set GEMINI_API_KEY.")
    return OpenAI(api_key=settings.api_key, base_url=settings.base_url, timeout=20.0, max_retries=0)


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Pull the first {...} JSON object out of an LLM reply, tolerating
    ```json fences and surrounding prose. Returns None if there isn't a
    parseable object."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    if text.lower() == "null":
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
