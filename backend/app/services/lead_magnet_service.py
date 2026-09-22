"""
Raw lead profile -> personalized lead-magnet content.

Personalization uses the OpenAI-compatible client in app/llm.py (configured
via OPENAI_API_KEY/OPENAI_BASE_URL/LLM_MODEL -- see the repo root
.env.example). A failed/unparsable LLM call never raises -- it falls back
to a fully deterministic, template-based generator, so lead-magnet
generation (and therefore the whole pipeline) works with zero LLM
configuration and is fully unit-testable offline.
"""
from __future__ import annotations

import json
import os
import secrets
import sys
from typing import Any

from app.llm import extract_json_object, get_llm_client

LEAD_MAGNET_TYPES = [
    "budgeting",
    "investing",
    "income_growth",
    "financial_goals",
    "couple_financial_planning",
    "habit_accountability",
    "future_state_planning",
]

# Keyword -> lead magnet type. Deliberately simple/deterministic -- swap
# for something smarter once real form data shows which signals actually
# predict which magnet converts best.
_KEYWORD_MAP: list[tuple[str, str]] = [
    ("budget", "budgeting"), ("spending", "budgeting"), ("save", "budgeting"),
    ("invest", "investing"), ("stock", "investing"), ("portfolio", "investing"),
    ("income", "income_growth"), ("salary", "income_growth"), ("side hustle", "income_growth"),
    ("business skills", "income_growth"),
    ("goal", "financial_goals"), ("financial growth", "financial_goals"),
    ("couple", "couple_financial_planning"), ("partner", "couple_financial_planning"), ("spouse", "couple_financial_planning"),
    ("relationship", "couple_financial_planning"),
    ("habit", "habit_accountability"), ("accountab", "habit_accountability"), ("consisten", "habit_accountability"),
    ("discipline", "habit_accountability"), ("time management", "habit_accountability"),
]

_REQUIRED_KEYS = {
    "starting_point", "desired_future_state", "biggest_constraint",
    "priority_1", "priority_2", "priority_3", "next_30_days", "next_90_days", "one_habit",
}

_PROMPT_TEMPLATE = """You are one of the two mentors at My Growth Academy (Kanth and Shaku). \
Someone has just answered a short questionnaire about where they want their life to be \
in 3 years. Write a short, personal summary for them, as if you had sat with them for \
half an hour, listened carefully, and are now writing back.

Their answers:
{profile_json}

Return ONLY valid JSON with exactly these keys (all string values):
starting_point, desired_future_state, biggest_constraint,
priority_1, priority_2, priority_3, next_30_days, next_90_days, one_habit.

What each key is for:
- starting_point: where they are right now, from what they told you (their readiness
  score and reason, the areas they picked).
- desired_future_state: where they said they'd like to be in 3 years.
- biggest_constraint: the thing they said is in their way.
- priority_1..3: the first three things you'd suggest.
- next_30_days / next_90_days: what to do this month, and by the end of month three.
- one_habit: one small daily habit to start today.

How to write:
- Plain, everyday words. Warm and encouraging, but calm. Write like a real person
  talking to them ("you said...", "you told us...").
- Refer to their actual answers. Quote their own words where it helps, and keep them
  as they wrote them, even if short or rough. Don't polish them into corporate language.
- 1-3 short sentences per key.
- Don't invent anything they didn't say: no goals, numbers, money, traits or history.
- Never use dashes as punctuation (no em dashes, no en dashes, no double hyphens).
  Use commas, full stops, colons or a new sentence.
- Never use contrast set-ups like "not X, but Y", "this isn't about X, it's about Y",
  "it's not just X, it's Y", "rather than X, focus on Y" or "you're not doing X,
  you're doing Y".
- Avoid coaching jargon and hype, for example: trajectory, journey, transformation,
  transform, unlock, potential, empower, elevate, optimize, leverage, intentional,
  strategic, holistic, actionable, "best self", "better version of yourself",
  "move the needle", "lasting change", "take ownership", "small steps compound",
  "measurable target", "design around".
- Before answering, reread every sentence and ask: would a good mentor actually say
  this out loud? If it sounds like a motivational poster, say it more simply."""



def select_lead_magnet(profile: dict[str, Any]) -> str:
    blob = " ".join(str(v) for v in profile.values() if v).lower()
    for keyword, magnet_type in _KEYWORD_MAP:
        if keyword in blob:
            return magnet_type
    return "future_state_planning"


def select_lead_magnet_title(magnet_type: str) -> str:
    return {
        "budgeting": "Your Personalized Budgeting Growth Map",
        "investing": "Your Personalized Investing Growth Map",
        "income_growth": "Your Personalized Income Growth Map",
        "financial_goals": "Your Personalized Financial Goals Map",
        "couple_financial_planning": "Your Personalized Couple Financial Planning Map",
        "habit_accountability": "Your Personalized Accountability Growth Map",
        "future_state_planning": "Your Personalized Financial Growth Map",
    }.get(magnet_type, "Your Personalized Financial Growth Map")


def generate_personalized_content(profile: dict[str, Any]) -> dict[str, str]:
    content = _generate_via_llm(profile)
    if not (content and _REQUIRED_KEYS.issubset(content.keys())):
        content = _fallback_content(profile)
    return {k: _no_dashes(str(v)) for k, v in content.items()}


def _no_dashes(text: str) -> str:
    """House style: no em/en dashes (or '--') used as punctuation. A spaced
    dash becomes a comma; number ranges like 30-45 keep their hyphen."""
    import re

    text = re.sub(r"\s+(?:--|\u2014|\u2013)\s+", ", ", text)
    return text.replace("\u2014", ", ").replace("--", ", ")


def _generate_via_llm(profile: dict[str, Any]) -> dict[str, Any] | None:
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        client = get_llm_client()
        model = os.environ.get("LLM_MODEL", "auto")
        prompt = _PROMPT_TEMPLATE.format(profile_json=json.dumps(profile, indent=2))
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.5,
        )
        return extract_json_object(resp.choices[0].message.content or "")
    except Exception as exc:  # noqa: BLE001 -- an LLM hiccup degrades personalization, it must never break delivery
        print(f"  lead_magnet_service llm warn: {exc}", file=sys.stderr)
        return None


def _as_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if v]
    return [str(value)]


def _strip_end(text: Any) -> str:
    """Trim whitespace and trailing punctuation from a free-text answer so
    it can sit inside a templated sentence without doubling up ('..')."""
    return str(text or "").strip().rstrip(".!?;:, ")


def _join_human(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + ", and " + items[-1]


def _lc_first(text: str) -> str:
    """Lower-case the first letter so an answer reads naturally mid-sentence,
    but leave 'I', "I'm", acronyms etc. alone."""
    if not text:
        return text
    first = text.split(" ", 1)[0]
    if first == "I" or first.startswith("I'") or first.startswith("I’") or (len(first) > 1 and first.isupper()):
        return text
    return text[0].lower() + text[1:]


def _commitment_sentence(commitment: Any) -> str:
    """priority_3, from the real form's 'could you commit 30-45 minutes a
    day?' answer (Yes / Most days / A few days a week / Not right now)."""
    text = str(commitment or "").strip().lower()
    if text.startswith("yes"):
        return ("You said you could find 30 to 45 minutes a day, so let's use it. "
                "Try to keep it at the same time each day. A little bit each day adds up quickly.")
    if "most days" in text:
        return ("You said you could manage 30 to 45 minutes on most days. Decide which days "
                "those are ahead of time, so it doesn't depend on how you feel that morning.")
    if "few days" in text:
        return ("You said a few days a week feels realistic, so start there with 30 to 45 "
                "minutes each time. Once that feels normal, add another day.")
    if "not right now" in text:
        return ("You mentioned that 30 to 45 minutes a day isn't possible right now, and that's "
                "fine. Start with 10 minutes a day so you keep some momentum going.")
    return "Set aside a small, fixed amount of time for this each day, at a time that suits you."


def _quote(text: str) -> str:
    """Wrap the person's own words in quotes, keeping them as written
    (only surrounding whitespace and trailing punctuation are trimmed)."""
    return f"\u201c{text}\u201d"


def _fallback_content(profile: dict[str, Any]) -> dict[str, str]:
    """Deterministic, template-based content used when no LLM is configured
    or the LLM call fails. Written to read like a mentor responding to the
    person's actual answers: their own words are quoted as-is rather than
    rephrased. Prefers the real form's fields (growth_areas /
    support_preferences / time_commitment / seriousness_*), falling back to
    the older placeholder-form fields (financial_goal/current_stage) for
    pre-existing submissions that only have those."""
    challenge = _strip_end(profile.get("primary_challenge"))
    future = _strip_end(profile.get("desired_future_state") or profile.get("financial_goal"))
    growth_areas = [a for a in _as_list(profile.get("growth_areas")) if a.lower() != "other"]
    support = [
        s for s in _as_list(profile.get("support_preferences"))
        if s.lower() not in ("other", "i'm not sure yet")
    ]
    score = str(profile.get("seriousness_score") or "").strip()
    reason = _strip_end(profile.get("seriousness_reason"))
    growth_text = _join_human(growth_areas)

    # Where you are now
    if score:
        starting = (
            f"You put yourself at {score} out of 10 for how serious you are about making "
            "changes over the next 3 years"
        )
        if reason:
            starting += f", and you told us why: {_quote(reason + '.')} "
            starting += "That's an honest answer, and it gives us somewhere specific to start."
        else:
            starting += "."
        if growth_areas:
            starting += f" The areas you picked were {growth_text}."
    elif growth_areas:
        starting = f"You told us you'd most like to grow in {growth_text}, so that's where we'll start."
    else:
        starting = "Filling this in was a good first step, and it gives us something to start from."

    # Where you'd like to be
    if future:
        short = len(future.split()) <= 5
        desired = f"When we asked where you'd like your life to be in 3 years, you wrote: {_quote(future + '.')}"
        if short:
            desired += (
                " Short and simple, which is fine. As we go, it'll help to picture what that "
                "looks like day to day, so you'll know when you've got there."
            )
    else:
        desired = (
            "You didn't say much about where you'd like to be in 3 years, and that's okay. "
            "It's something we can work out together."
        )

    # What's in the way
    if challenge:
        constraint = (
            f"You said the biggest thing in your way right now is {_quote(challenge)}. "
            "That's a really common one, and it usually gets easier once you have a simple "
            "routine and someone checking in with you."
        )
    else:
        constraint = (
            "You didn't name one thing that's holding you back. That's fine. "
            "It often becomes clearer once you get started."
        )

    # Priorities
    if growth_areas:
        p1 = f"Start with {growth_areas[0]}. It was the first area you picked, so let's begin there."
    else:
        p1 = "Pick the one area of your life you'd most like to improve, and start there."
    if support:
        support_bits = [s[0].lower() + s[1:] for s in support]
        p2 = (
            f"Get some help along the way. You mentioned {_join_human(support_bits)}. "
            "Having that around you means you won't be working it all out on your own."
        )
    else:
        p2 = ("Get some help along the way, through a mentor and a clear plan, so you're not "
              "working it all out on your own.")

    next_30 = (
        f"For the next month, do something small for {growth_text} each day. "
        "It doesn't need to be big. Showing up regularly is what counts."
        if growth_areas else
        "For the next month, do something small toward your goal each day. "
        "It doesn't need to be big. Showing up regularly is what counts."
    )

    return {
        "starting_point": starting,
        "desired_future_state": desired,
        "biggest_constraint": constraint,
        "priority_1": p1,
        "priority_2": p2,
        "priority_3": _commitment_sentence(profile.get("time_commitment") or profile.get("current_stage")),
        "next_30_days": next_30,
        "next_90_days": (
            "By the end of month three, take what you've learned and turn it into a 90-day plan "
            "with one clear goal you can actually check off."
        ),
        "one_habit": "Before bed, write down one small win from the day and one thing you're grateful for.",
    }


def generate_secure_lead_magnet_id() -> str:
    """Non-guessable identifier used both as the on-disk filename stem and
    the public delivery URL segment -- never the DB primary key."""
    return secrets.token_urlsafe(24)
