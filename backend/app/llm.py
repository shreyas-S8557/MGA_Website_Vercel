"""OpenAI-compatible LLM client + a tolerant JSON-object extractor, used by
lead_magnet_service to personalize each lead's report.

Configured entirely through environment variables:
  OPENAI_API_KEY   -- required for LLM personalization (without it the
                      deterministic template fallback is used instead)
  OPENAI_BASE_URL  -- any OpenAI-compatible endpoint (defaults below)
  LLM_MODEL        -- model name (default "auto")
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI

DEFAULT_BASE_URL = "https://freellmapiserver-production-df6f.up.railway.app/v1"


def get_llm_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL),
    )


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
