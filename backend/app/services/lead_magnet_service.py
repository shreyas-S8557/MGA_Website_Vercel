"""
Raw lead profile -> personalized lead-magnet content.

Personalization uses Google Gemini through the client in app/llm.py
(configured via GEMINI_API_KEY and optionally LLM_MODEL -- see the repo root
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

from app.llm import extract_json_object, get_llm_client, llm_settings

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
in three years. Write a short, personal summary for them, as if you had sat with them for \
half an hour, listened carefully, and are now writing back.

Their answers:
{profile_json}

Return ONLY valid JSON with exactly these keys (all string values):
starting_point, desired_future_state, biggest_constraint,
priority_1, priority_2, priority_3, next_30_days, next_90_days, one_habit.

What each key is for:
- starting_point: where they are right now, from what they told you (their readiness
  score and reason, the areas they picked).
- desired_future_state: where they said they'd like to be in three years.
- biggest_constraint: the thing they said is in their way.
- priority_1..3: the first three things you'd suggest (one short line each).
- next_30_days / next_90_days: what to do this month, and by the end of month three.
- one_habit: one small daily habit to start today.

How to write:
- Plain, everyday words. Warm and encouraging, but calm. Write like a real person
  talking to them ("you said...", "you told us...").
- Refer to their actual answers. Quote their own words where it helps, and keep them
  as they wrote them, even if short or rough. Don't polish them into corporate language.
- Keep it short: one sentence per key, 20 words at most. The PDF shows the
  visuals, so the words only need to carry the point.
- Write whole numbers below ten as words ("three years"); 10 and above stay as
  digits. The readiness score is the one exception: write it as digits ("7 out of 10"). Inside quotes, keep their words exactly as written.
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
    else:
        content = {k: _keep_short(str(v)) for k, v in content.items()}
    return {k: numbers_to_words(_no_dashes(str(v))) for k, v in content.items()}


def _keep_short(text: str, max_sentences: int = 2, max_words: int = 40) -> str:
    """Safety net for AI-written copy: keep at most two sentences (and about
    40 words), so a chatty reply can't push the PDF onto extra pages."""
    import re

    sentences = re.split(r"(?<=[.!?\u201d])\s+(?=[A-Z\u201c])", text.strip())
    out: list[str] = []
    for sentence in sentences[:max_sentences]:
        if out and len(" ".join(out + [sentence]).split()) > max_words:
            break
        out.append(sentence)
    return " ".join(out)


def _no_dashes(text: str) -> str:
    """House style: no em/en dashes (or '--') used as punctuation. A spaced
    dash becomes a comma; number ranges like 30-45 keep their hyphen."""
    import re

    text = re.sub(r"\s+(?:--|\u2014|\u2013)\s+", ", ", text)
    return text.replace("\u2014", ", ").replace("--", ", ")


def _generate_via_llm(profile: dict[str, Any]) -> dict[str, Any] | None:
    settings = llm_settings()
    if settings is None:
        return None
    try:
        client = get_llm_client(settings)
        prompt = _PROMPT_TEMPLATE.format(profile_json=json.dumps(profile, indent=2))
        kwargs: dict[str, Any] = {}
        if settings.is_gemini:
            # Gemini 3 models always "think" first, and those thinking tokens
            # count against max_tokens. Keep the thinking short and leave
            # plenty of room so the JSON answer is never cut off.
            kwargs["extra_body"] = {"reasoning_effort": "low"}
        resp = client.chat.completions.create(
            model=settings.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096 if settings.is_gemini else 800,
            temperature=0.5,
            **kwargs,
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
        return "Use your 30 to 45 minutes a day, at the same time each day."
    if "most days" in text:
        return "Aim for 30 to 45 minutes on most days. Pick the days in advance."
    if "few days" in text:
        return "Start with a few days a week, 30 to 45 minutes each time."
    if "not right now" in text:
        return "Start with 10 minutes a day to keep some momentum."
    return "Set aside a little time each day, at a time that suits you."


# Short names for the form's support options, so they fit on one line.
_SUPPORT_SHORT = {
    "mentorship from people who have already achieved results": "mentorship",
    "a clearer plan or system": "a clear plan",
    "better habits and consistency": "better habits",
    "new skills or knowledge": "new skills",
    "a supportive environment or community": "a supportive community",
}


def _quote(text: str, max_words: int = 20) -> str:
    """Wrap the person's own words in quotes, keeping them as written (only
    surrounding whitespace and trailing punctuation are trimmed). Very long
    answers are cut to their first `max_words` words with an ellipsis so the
    PDF stays short; the full answer is still in the team's lead alert."""
    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words]).rstrip(".,;:!?") + "\u2026"
    return f"\u201c{text}\u201d"


_NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]


def numbers_to_words(text: str) -> str:
    """House style: whole numbers below ten are written as words
    ("three-year"); 10 and above stay as digits. Exception: the readiness
    score keeps its digit ("7 out of 10"). Text inside quote marks is the
    person's own words and is left exactly as they wrote it. Scores like
    7/10, decimals, times and money are left alone too."""
    import re

    parts = re.split(r"(\u201c[^\u201d]*\u201d|\"[^\"]*\")", str(text))
    pattern = re.compile(
        r"(?<![\d.,/:$\u00a3\u20b9\u20ac-])\b([0-9])\b(?![\d/:%]|[.,]\d|\s*(?:am|pm)\b|\s+out\s+of\s+10\b)"
    )

    def repl(match: "re.Match[str]") -> str:
        word = _NUMBER_WORDS[int(match.group(1))]
        before = match.string[: match.start()].rstrip()
        if not before or before.endswith((".", "!", "?")):
            word = word.capitalize()
        return word

    for i in range(0, len(parts), 2):
        parts[i] = pattern.sub(repl, parts[i])
    return "".join(parts)


def _fallback_content(profile: dict[str, Any]) -> dict[str, str]:
    """Deterministic, template-based content used when no LLM is configured
    or the LLM call fails. Deliberately short: each value is one line plus,
    where there is one, the person's own words quoted as-is. The PDF adds
    the visuals (readiness meter, focus-area tags, icons). Prefers the real
    form's fields (growth_areas / support_preferences / time_commitment /
    seriousness_*), falling back to the older placeholder-form fields
    (financial_goal/current_stage) for pre-existing submissions."""
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
        starting = f"You rated yourself {score} out of 10"
        starting += f": {_quote(reason + '.')}" if reason else "."
    elif growth_areas:
        starting = f"You'd most like to grow in {growth_text}."
    else:
        starting = "Filling this in was a good first step."

    # Where you'd like to be
    if future:
        desired = f"In 3 years, you'd like: {_quote(future + '.')}"
        if len(future.split()) <= 5:
            desired += " Let's picture what that looks like day to day."
    else:
        desired = "You didn't say yet, and that's okay. We can work it out together."

    # What's in the way
    if challenge:
        constraint = (
            f"You named {_quote(challenge)}. It's common, and a simple routine with "
            "regular check-ins helps."
        )
    else:
        constraint = "Nothing named yet. It often gets clearer once you start."

    # Priorities
    if growth_areas:
        p1 = f"Start with {growth_areas[0]}, your first pick."
    else:
        p1 = "Pick the one area you'd most like to improve."
    if support:
        bits: list[str] = []
        for s_ in support:
            short = _SUPPORT_SHORT.get(s_.strip().lower(), s_[0].lower() + s_[1:])
            if short not in bits:
                bits.append(short)
        p2 = f"Get support: {_join_human(bits)}."
    else:
        p2 = "Get a mentor and a clear plan, so you're not doing it alone."

    next_30 = (
        f"One small step a day on {growth_text}."
        if growth_areas else
        "One small step a day toward your goal."
    )

    content = {
        "starting_point": starting,
        "desired_future_state": desired,
        "biggest_constraint": constraint,
        "priority_1": p1,
        "priority_2": p2,
        "priority_3": _commitment_sentence(profile.get("time_commitment") or profile.get("current_stage")),
        "next_30_days": next_30,
        "next_90_days": "Turn what you've learned into a 90-day plan with one clear goal.",
        "one_habit": "Before bed, note one win and one thing you're grateful for.",
    }
    return {k: numbers_to_words(v) for k, v in content.items()}


def generate_secure_lead_magnet_id() -> str:
    """Non-guessable identifier used both as the on-disk filename stem and
    the public delivery URL segment -- never the DB primary key."""
    return secrets.token_urlsafe(24)
