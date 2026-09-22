"""
Raw Google Form answers -> normalized MGA lead profile.

This works off a small set of CANONICAL PROFILE KEYS and maps to them
either by:

  1. fuzzy substring match against common header phrasings for those keys
     (FIELD_ALIASES below), or
  2. an explicit `field_map` supplied in the webhook payload (see
     google-apps-script/Code.gs and schemas/mga_lead.py) that pins down
     which question -> which canonical key without editing this file.

The real form is now finalized -- "Your 3-Year Future Snapshot" (see the
website's own on-page version of it, website/components/LeadMagnetModal.tsx,
and the original Google Form it replaces). Its question text is what
FIELD_ALIASES below is written against, so the website form's questions
match these aliases automatically with no field_map needed. The original,
more generic aliases (financial_goal/current_stage's "your goal"/"current
situation" etc.) are kept too, purely for backward compatibility with any
already-recorded Google Form submissions that used older question
phrasing.
"""
from __future__ import annotations

import re
from typing import Any

CANONICAL_KEYS = [
    # Kept from the original placeholder form -- no longer asked by the
    # real form, but still supported for old submissions / a field_map.
    "financial_goal",
    "current_stage",
    # The real form's questions:
    "primary_challenge",
    "desired_future_state",
    "growth_areas",
    "support_preferences",
    "time_commitment",
    "seriousness_score",
    "seriousness_reason",
    "mentorship_interest",
    # Derived (not asked directly) -- see determine_lead_profile below.
    "urgency",
    "engagement_level",
]

FIELD_ALIASES: dict[str, list[str]] = {
    "financial_goal": ["financial goal", "what do you want to achieve", "your goal"],
    "current_stage": ["current situation", "where are you now", "current stage"],
    "primary_challenge": [
        "biggest challenge", "obstacle", "what's stopping you", "struggle",
        "standing between where you are today", "biggest thing standing",
    ],
    "desired_future_state": [
        "future state", "dream life", "where do you want to be", "vision",
        "3 years from now", "where would you like your life to be",
    ],
    "growth_areas": ["areas would you most like to grow", "which areas would you like to grow"],
    "support_preferences": [
        "kind of support", "support do you think would help", "help you make progress faster",
    ],
    "time_commitment": [
        "45 minutes a day", "minutes a day toward improving", "realistically commit",
    ],
    "seriousness_score": ["how serious are you", "changing your current trajectory"],
    "seriousness_reason": ["what made you choose the above number", "made you choose the above number"],
    "mentorship_interest": ["open to exploring mentorship", "exploring mentorship if we believe"],
    "urgency": ["how soon", "timeframe", "when do you want", "urgency"],
    "engagement_level": ["how ready", "commitment", "how committed", "engagement"],
}

CONTACT_ALIASES = {
    "name": ["name", "full name"],
    "email": ["email", "e-mail"],
    "phone": ["phone", "mobile", "whatsapp"],
}


def _match_key(question: str, aliases: dict[str, list[str]]) -> str | None:
    q = question.strip().lower()
    for key, fragments in aliases.items():
        for frag in fragments:
            if frag in q:
                return key
    return None


def extract_contact_fields(answers: dict[str, Any]) -> dict[str, str | None]:
    """Best-effort pull of name/email/phone out of the raw answers dict,
    used only as a fallback when the webhook payload doesn't already carry
    top-level name/email/phone fields."""
    found: dict[str, str | None] = {"name": None, "email": None, "phone": None}
    for question, value in answers.items():
        key = _match_key(str(question), CONTACT_ALIASES)
        if key and not found[key]:
            found[key] = str(value) if value is not None else None
    return found


def analyze_answers(
    answers: dict[str, Any], field_map: dict[str, str] | None = None
) -> dict[str, Any]:
    """Map raw form answers onto the canonical profile keys. `field_map`
    (an exact question-text -> canonical-key dict) takes priority over the
    fuzzy alias matching below."""
    field_map = field_map or {}
    profile: dict[str, Any] = {key: None for key in CANONICAL_KEYS}

    for question, value in answers.items():
        if question == "__field_map__":
            continue
        key = field_map.get(question) or _match_key(str(question), FIELD_ALIASES)
        if key in profile and value not in (None, ""):
            profile[key] = value

    return profile


def determine_lead_profile(
    answers: dict[str, Any], field_map: dict[str, str] | None = None
) -> dict[str, Any]:
    """Full profiling step: analyze answers, then classify engagement/
    urgency. The real form asks for these directly (a 1-10 "how serious"
    scale -> urgency, a "could you commit 30-45 min/day" question ->
    engagement_level), so those are used first when present; only when
    they're missing does this fall back to the original cheap,
    deterministic keyword-based inference -- no LLM call needed for this
    stage either way."""
    profile = analyze_answers(answers, field_map)

    if not profile.get("urgency"):
        profile["urgency"] = _urgency_from_score(profile.get("seriousness_score")) or _infer_urgency(
            answers
        )
    if not profile.get("engagement_level"):
        profile["engagement_level"] = _engagement_from_commitment(
            profile.get("time_commitment")
        ) or _infer_engagement(answers)

    return profile


def _urgency_from_score(score: Any) -> str | None:
    """Maps the real form's 1 (just thinking about it) - 10 (ready now)
    scale onto the existing low/medium/high urgency levels."""
    if score in (None, ""):
        return None
    match = re.search(r"\d+", str(score))
    if not match:
        return None
    value = int(match.group())
    if value >= 8:
        return "high"
    if value >= 5:
        return "medium"
    return "low"


def _engagement_from_commitment(commitment: Any) -> str | None:
    """Maps the real form's "could you commit 30-45 min/day" answer onto
    the existing low/medium/high engagement levels."""
    if not commitment:
        return None
    text = str(commitment).strip().lower()
    if text.startswith("yes") or "most days" in text:
        return "high"
    if "few days" in text:
        return "medium"
    if "not right now" in text:
        return "low"
    return None


def _infer_urgency(answers: dict[str, Any]) -> str:
    blob = " ".join(str(v) for v in answers.values()).lower()
    if re.search(r"\basap\b|immediately|this month|urgent", blob):
        return "high"
    if re.search(r"few months|this year|soon", blob):
        return "medium"
    return "low"


def _infer_engagement(answers: dict[str, Any]) -> str:
    relevant = {k: v for k, v in answers.items() if k != "__field_map__"}
    answered = sum(1 for v in relevant.values() if str(v).strip())
    total = max(len(relevant), 1)
    ratio = answered / total
    if ratio >= 0.9:
        return "high"
    if ratio >= 0.5:
        return "medium"
    return "low"
