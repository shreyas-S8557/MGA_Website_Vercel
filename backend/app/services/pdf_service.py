"""
render_lead_magnet(): structured content dict -> branded PDF file on disk
under app.config.MGA_LEAD_MAGNET_DIR.

Styled to match the My Growth Academy website: the same navy / coral /
cream / mint palette (sampled from the live Wix site, mirrored in
website/tailwind.config.js), the same two fonts (Poppins headings, Roboto
body -- bundled under app/assets/fonts so rendering never needs the
network), and the MGA logo.

Layout (A4, two pages; long text flows onto extra pages safely):

  Page 1 -- the snapshot
    logo ........................................ PERSONALISED GROWTH BLUEPRINT
    [ navy hero: coral pill, title, "Prepared for <name> · <date>", arrow ]
    intro line
    [ WHERE YOU ARE NOW ]  ->  [ WHERE YOU'D LIKE TO BE ]
    [ WHAT'S IN THE WAY  (coral callout) ]
    Your first 3 priorities   (numbered navy dots, like the site's steps)
    [ short note from Kanth & Shaku, anchored to the bottom ]

  Page 2 -- the action plan
    Your roadmap              [ 30 days ] [ 90 days ] [ start today ]
    Your 30-day habit tracker (printable tick boxes, weekly milestones)
    3 gratitudes a day        (from the site's gratitude section)
    [ navy CTA band: "Want to talk it through?" / 10-Day Vetting Experience ]

  footer on every page: My Growth Academy · mygrowthacademy.coach   page n

Isolated in its own module so swapping fpdf2 for a hosted PDF-rendering
service later only touches this file.
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF

from app.config import MGA_LEAD_MAGNET_DIR

_ASSETS = Path(__file__).resolve().parents[1] / "assets"
_FONTS = _ASSETS / "fonts"
_LOGO = _ASSETS / "logo.png"

SITE_URL = "https://mygrowthacademy.coach"

# MGA palette (RGB) -- same values as website/tailwind.config.js `mga`.
NAVY = (54, 72, 143)  # #36488F
NAVY_DARK = (38, 51, 107)
CORAL = (200, 71, 57)  # #C84739
CORAL_TINT = (250, 228, 224)
CREAM = (255, 246, 239)  # #FFF6EF
MINT = (99, 208, 162)  # #63D0A2
MINT_DARK = (58, 160, 118)
ACCENT_BLUE = (42, 54, 144)  # #2A3690
GRAY = (143, 143, 143)  # #8F8F8F
GRAY_DARK = (66, 66, 66)  # #424242
WHITE = (255, 255, 255)
CARD_BORDER = (236, 224, 214)

# Kept for backwards compatibility with anything importing it; the new
# layout places each of these explicitly.
SECTION_ORDER = [
    ("Your current starting point", "starting_point"),
    ("Your desired future state", "desired_future_state"),
    ("Your biggest constraint", "biggest_constraint"),
    ("Your first 3 priorities", None),
    ("Your next 30 days", "next_30_days"),
    ("Your next 90 days", "next_90_days"),
    ("One habit to begin immediately", "one_habit"),
]

PAGE_W = 210
PAGE_H = 297
MARGIN = 16
CONTENT_W = PAGE_W - 2 * MARGIN
BOTTOM_LIMIT = PAGE_H - 19  # keep clear of the footer


def _clean(text: Any) -> str:
    """Normalise free text (LLM output / form answers) for the PDF: drop
    characters outside the Basic Multilingual Plane (emoji -- no bundled
    font has them), collapse whitespace, and fix doubled full stops that
    come from templated sentences wrapping answers which already ended in
    one."""
    text = str(text or "")
    text = "".join(ch for ch in text if ord(ch) <= 0xFFFF)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\.{2}(?!\.)", ".", text)
    # No em/en dashes used as punctuation anywhere in the PDF: a spaced
    # dash becomes a comma (ranges like 30-45 keep their plain hyphen).
    text = re.sub(r"\s+(?:--|\u2014|\u2013)\s+", ", ", text)
    text = text.replace("\u2014", ", ").replace("--", ", ")
    return text


class _BlueprintPDF(FPDF):
    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_margins(MARGIN, MARGIN, MARGIN)
        self.set_auto_page_break(False)
        self.add_font("Poppins", "B", str(_FONTS / "Poppins-Bold.ttf"))
        self.add_font("PoppinsSemi", "", str(_FONTS / "Poppins-SemiBold.ttf"))
        self.add_font("PoppinsMed", "", str(_FONTS / "Poppins-Medium.ttf"))
        self.add_font("Roboto", "", str(_FONTS / "Roboto-Regular.ttf"))
        self.add_font("Roboto", "B", str(_FONTS / "Roboto-Bold.ttf"))
        self.add_font("Roboto", "I", str(_FONTS / "Roboto-Italic.ttf"))
        self.add_font("RobotoMed", "", str(_FONTS / "Roboto-Medium.ttf"))
        self.add_font("DejaVu", "", str(_FONTS / "DejaVuSans.ttf"))
        self.set_fallback_fonts(["DejaVu"], exact_match=False)
        self.set_title("My Growth Academy - Personalised Growth Blueprint")
        self.set_author("My Growth Academy")
        self.set_creator("My Growth Academy")

    # Cream page background + slim header on continuation pages.
    def header(self) -> None:
        self.set_fill_color(*CREAM)
        self.rect(0, 0, PAGE_W, PAGE_H, style="F")
        if self.page_no() > 1:
            if _LOGO.exists():
                self.image(str(_LOGO), x=MARGIN, y=10, h=8)
            self.set_draw_color(*CARD_BORDER)
            self.set_line_width(0.3)
            self.line(MARGIN, 22, PAGE_W - MARGIN, 22)
            self.set_y(30)

    def footer(self) -> None:
        self.set_y(-13)
        self.set_draw_color(*CARD_BORDER)
        self.set_line_width(0.3)
        self.line(MARGIN, PAGE_H - 16, PAGE_W - MARGIN, PAGE_H - 16)
        self.set_font("Roboto", "", 8)
        self.set_text_color(*GRAY)
        self.set_x(MARGIN)
        self.cell(CONTENT_W / 2, 5, "My Growth Academy  ·  mygrowthacademy.coach", link=SITE_URL)
        self.cell(CONTENT_W / 2, 5, f"Page {self.page_no()}", align="R")


# --------------------------------------------------------------------------
# Small drawing helpers
# --------------------------------------------------------------------------


def _text_height(pdf: FPDF, w: float, line_h: float, text: str) -> float:
    lines = pdf.multi_cell(w, line_h, text, align="L", dry_run=True, output="LINES")
    return max(1, len(lines)) * line_h


def _body(pdf: FPDF, x: float, y: float, w: float, text: str, size: float = 10.5,
          line_h: float = 5.4, color=GRAY_DARK, font=("Roboto", "")) -> float:
    pdf.set_font(font[0], font[1], size)
    pdf.set_text_color(*color)
    pdf.set_xy(x, y)
    pdf.multi_cell(w, line_h, text, align="L")
    return pdf.get_y()


def _label(pdf: FPDF, x: float, y: float, text: str, color, size: float = 7.5) -> None:
    pdf.set_font("PoppinsSemi", "", size)
    pdf.set_text_color(*color)
    pdf.set_char_spacing(0.9)
    pdf.set_xy(x, y)
    pdf.cell(0, 4, text.upper())
    pdf.set_char_spacing(0)


def _card(pdf: FPDF, x: float, y: float, w: float, h: float, fill=WHITE,
          border=CARD_BORDER, radius: float = 3) -> None:
    pdf.set_fill_color(*fill)
    pdf.set_draw_color(*border)
    pdf.set_line_width(0.3)
    pdf.rect(x, y, w, h, style="DF", round_corners=True, corner_radius=radius)


def _accent_top(pdf: FPDF, x: float, y: float, w: float, color, radius: float = 3) -> None:
    """Colored cap on top of a card (rounded top, square bottom)."""
    pdf.set_fill_color(*color)
    pdf.rect(x, y, w, 2.2, style="F", round_corners=("TOP_LEFT", "TOP_RIGHT"), corner_radius=radius)


def _section_heading(pdf: FPDF, y: float, text: str) -> float:
    pdf.set_font("PoppinsSemi", "", 14)
    pdf.set_text_color(*NAVY)
    pdf.set_xy(MARGIN, y)
    pdf.cell(0, 8, text)
    pdf.set_fill_color(*CORAL)
    pdf.rect(MARGIN, y + 9, 14, 0.9, style="F")
    return y + 12


def _ensure_space(pdf: _BlueprintPDF, y: float, needed: float) -> float:
    if y + needed > BOTTOM_LIMIT:
        pdf.add_page()
        return pdf.get_y()
    return y


def _growth_arrow(pdf: FPDF, x: float, y: float, w: float, h: float) -> None:
    """Rising line with milestone dots and an arrowhead -- echoes the arrow
    in the MGA logo. Drawn inside the navy hero."""
    pts = [
        (x, y + h),
        (x + w * 0.28, y + h * 0.62),
        (x + w * 0.46, y + h * 0.74),
        (x + w * 0.74, y + h * 0.28),
        (x + w, y),
    ]
    with pdf.local_context(stroke_opacity=0.9):
        pdf.set_draw_color(*MINT)
        pdf.set_line_width(1.1)
        pdf.polyline(pts)
    pdf.set_fill_color(*MINT)
    ax, ay = pts[-1]
    pdf.polygon([(ax + 1.2, ay - 1.2), (ax - 4.2, ay - 0.6), (ax + 0.4, ay + 4.3)], style="F")
    for px, py in pts[1:-1]:
        pdf.set_fill_color(*WHITE)
        pdf.circle(x=px, y=py, radius=1.3, style="F")


# --------------------------------------------------------------------------
# Main renderer
# --------------------------------------------------------------------------


def render_lead_magnet(
    lead_magnet_id: str,
    title: str,
    content: dict[str, Any],
    recipient_name: str | None = None,
) -> str:
    """Writes a PDF to MGA_LEAD_MAGNET_DIR/<lead_magnet_id>.pdf and returns
    the absolute path. The filesystem path is never exposed externally --
    only `lead_magnet_id` is, via GET /api/lead-magnets/{id}."""
    os.makedirs(MGA_LEAD_MAGNET_DIR, exist_ok=True)
    path = os.path.join(MGA_LEAD_MAGNET_DIR, f"{lead_magnet_id}.pdf")

    c = {k: _clean(v) for k, v in (content or {}).items()}
    title = _clean(title) or "Your Personalised Growth Blueprint"
    first_name = _clean(recipient_name).split(" ")[0] if recipient_name else ""

    pdf = _BlueprintPDF()
    pdf.add_page()

    # ---- Top bar: logo + document label ---------------------------------
    if _LOGO.exists():
        pdf.image(str(_LOGO), x=MARGIN, y=11, h=11)
    pdf.set_font("PoppinsMed", "", 7.5)
    pdf.set_text_color(*GRAY)
    pdf.set_char_spacing(1.2)
    pdf.set_xy(MARGIN, 15)
    pdf.cell(CONTENT_W, 4, "PERSONALISED GROWTH BLUEPRINT", align="R")
    pdf.set_char_spacing(0)

    # ---- Hero ------------------------------------------------------------
    hero_y = 27
    text_w = CONTENT_W - 62  # leave room for the arrow motif on the right
    pdf.set_font("Poppins", "B", 21)
    title_h = _text_height(pdf, text_w, 9.5, title)
    hero_h = max(40, 19 + title_h + 11)
    pdf.set_fill_color(*NAVY)
    pdf.rect(MARGIN, hero_y, CONTENT_W, hero_h, style="F", round_corners=True, corner_radius=5)
    # soft decorative circles behind the arrow
    with pdf.local_context(fill_opacity=0.08):
        pdf.set_fill_color(*WHITE)
        pdf.circle(x=PAGE_W - MARGIN - 22, y=hero_y + hero_h / 2, radius=19, style="F")
        pdf.circle(x=PAGE_W - MARGIN - 22, y=hero_y + hero_h / 2, radius=12, style="F")
    _growth_arrow(pdf, PAGE_W - MARGIN - 44, hero_y + 10, 38, hero_h - 20)

    # coral pill
    pill_text = "YOUR 3-YEAR FUTURE SNAPSHOT"
    pdf.set_font("PoppinsSemi", "", 7)
    pdf.set_char_spacing(0.9)
    pill_w = pdf.get_string_width(pill_text) + 8
    pdf.set_fill_color(*CORAL)
    pdf.rect(MARGIN + 10, hero_y + 8, pill_w, 6, style="F", round_corners=True, corner_radius=3)
    pdf.set_text_color(*WHITE)
    pdf.set_xy(MARGIN + 10, hero_y + 8)
    pdf.cell(pill_w, 6, pill_text, align="C")
    pdf.set_char_spacing(0)

    pdf.set_font("Poppins", "B", 21)
    pdf.set_text_color(*WHITE)
    pdf.set_xy(MARGIN + 10, hero_y + 17)
    pdf.multi_cell(text_w, 9.5, title, align="L")

    prepared = f"Prepared for {first_name}" if first_name else "Prepared for you"
    prepared += f"  ·  {datetime.now().strftime('%d %B %Y').lstrip('0')}"
    pdf.set_font("Roboto", "", 9.5)
    pdf.set_text_color(214, 220, 240)
    pdf.set_xy(MARGIN + 10, pdf.get_y() + 2.5)
    pdf.cell(text_w, 5, prepared)

    y = hero_y + hero_h + 6

    # ---- Intro -----------------------------------------------------------
    greeting = f"Hi {first_name}, thanks" if first_name else "Thanks"
    intro = (
        f"{greeting} for answering our questions so honestly. We've gone through what you "
        "told us and put this together for you: where you are right now, where you'd like "
        "to be, and what we'd suggest doing first."
    )
    y = _body(pdf, MARGIN, y, CONTENT_W, intro, size=10.5, line_h=5.4,
              color=ACCENT_BLUE, font=("Roboto", "I")) + 4

    # ---- From -> To ------------------------------------------------------
    gap = 12
    card_w = (CONTENT_W - gap) / 2
    inner_w = card_w - 12
    pdf.set_font("Roboto", "", 10)
    h_left = _text_height(pdf, inner_w, 5.2, c.get("starting_point", ""))
    h_right = _text_height(pdf, inner_w, 5.2, c.get("desired_future_state", ""))
    card_h = max(h_left, h_right) + 15
    y = _ensure_space(pdf, y, card_h)

    for i, (label, key, color) in enumerate([
        ("Where you are now", "starting_point", CORAL),
        ("Where you'd like to be", "desired_future_state", MINT_DARK),
    ]):
        cx = MARGIN + i * (card_w + gap)
        _card(pdf, cx, y, card_w, card_h)
        _accent_top(pdf, cx, y, card_w, CORAL if i == 0 else MINT)
        _label(pdf, cx + 6, y + 6, label, color)
        _body(pdf, cx + 6, y + 11.5, inner_w, c.get(key, ""), size=10, line_h=5.2)

    # arrow bubble between the cards
    bx, by = MARGIN + card_w + gap / 2, y + card_h / 2
    pdf.set_fill_color(*NAVY)
    pdf.circle(x=bx, y=by, radius=4.6, style="F")
    pdf.set_fill_color(*WHITE)
    pdf.polygon([(bx - 1.4, by - 2.2), (bx + 2.2, by), (bx - 1.4, by + 2.2)], style="F")
    y += card_h + 5

    # ---- Constraint callout ---------------------------------------------
    pdf.set_font("Roboto", "", 10)
    ch = _text_height(pdf, CONTENT_W - 16, 5.2, c.get("biggest_constraint", "")) + 15
    y = _ensure_space(pdf, y, ch)
    pdf.set_fill_color(*CORAL_TINT)
    pdf.rect(MARGIN, y, CONTENT_W, ch, style="F", round_corners=True, corner_radius=3)
    pdf.set_fill_color(*CORAL)
    pdf.rect(MARGIN, y, 1.8, ch, style="F", round_corners=("TOP_LEFT", "BOTTOM_LEFT"), corner_radius=3)
    _label(pdf, MARGIN + 8, y + 5, "What's in the way", CORAL)
    _body(pdf, MARGIN + 8, y + 10.5, CONTENT_W - 16, c.get("biggest_constraint", ""), size=10, line_h=5.2)
    y += ch + 6

    # ---- Priorities ------------------------------------------------------
    pdf.set_font("Roboto", "", 10.5)
    pri = [c.get(f"priority_{i}", "") for i in (1, 2, 3)]
    pri_heights = [max(8.4, _text_height(pdf, CONTENT_W - 14, 5.4, t)) for t in pri]
    y = _ensure_space(pdf, y, 14 + pri_heights[0] + 4)
    y = _section_heading(pdf, y, "Your first 3 priorities")
    for n, (text, h) in enumerate(zip(pri, pri_heights), start=1):
        y = _ensure_space(pdf, y, h + 4)
        pdf.set_fill_color(*NAVY)
        pdf.circle(x=MARGIN + 4.2, y=y + 4.2, radius=4.2, style="F")
        pdf.set_font("PoppinsSemi", "", 9.5)
        pdf.set_text_color(*WHITE)
        pdf.set_xy(MARGIN, y + 1.9)
        pdf.cell(8.4, 4.6, str(n), align="C")
        _body(pdf, MARGIN + 14, y + 1.4, CONTENT_W - 14, text, size=10.5, line_h=5.4)
        y += h + 2.5
    y += 2

    # ---- Page 1 closing note from the mentors (anchored to page bottom) ---
    note = (
        "Thank you for being so open with your answers. If anything here doesn't "
        "sound quite like you, let us know and we'll sort it out together."
    )
    pdf.set_font("PoppinsMed", "", 11)
    note_h = _text_height(pdf, CONTENT_W - 26, 5.6, note)
    q_h = note_h + 16
    if y + q_h + 4 <= BOTTOM_LIMIT:
        qy = max(y + 4, BOTTOM_LIMIT - q_h)
        pdf.set_fill_color(*WHITE)
        pdf.set_draw_color(*CARD_BORDER)
        pdf.set_line_width(0.3)
        pdf.rect(MARGIN, qy, CONTENT_W, q_h, style="DF", round_corners=True, corner_radius=3)
        pdf.set_font("Poppins", "B", 30)
        pdf.set_text_color(*CORAL)
        pdf.set_xy(MARGIN + 6, qy + 1)
        pdf.cell(10, 14, "\u201c")
        _body(pdf, MARGIN + 18, qy + 5.5, CONTENT_W - 26, note, size=11, line_h=5.6,
              color=NAVY, font=("PoppinsMed", ""))
        pdf.set_font("Roboto", "", 8.5)
        pdf.set_text_color(*GRAY)
        pdf.set_xy(MARGIN + 18, qy + 6.5 + note_h)
        pdf.cell(CONTENT_W - 26, 5, "Kanth & Shaku, your mentors at My Growth Academy")

    # ==== Page 2: the action plan ==========================================
    pdf.add_page()
    y = pdf.get_y()

    pdf.set_font("Poppins", "B", 20)
    pdf.set_text_color(*NAVY)
    pdf.set_xy(MARGIN, y)
    pdf.cell(0, 9, "Your action plan")
    y += 9.5
    y = _body(pdf, MARGIN, y, CONTENT_W,
              "Here's what we'd work on first, plus a simple tracker so you can see how you're getting on.",
              size=10, line_h=5.2, color=ACCENT_BLUE, font=("Roboto", "I")) + 5

    # ---- Roadmap ---------------------------------------------------------
    cols = [
        ("Next 30 days", "next_30_days", NAVY),
        ("Next 90 days", "next_90_days", NAVY),
        ("Start today", "one_habit", CORAL),
    ]
    rgap = 6
    rw = (CONTENT_W - 2 * rgap) / 3
    pdf.set_font("Roboto", "", 9.8)
    rh = max(_text_height(pdf, rw - 10, 5, c.get(k, "")) + (5 if k == "one_habit" else 0)
             for _, k, _ in cols) + 15
    y = _ensure_space(pdf, y, 12 + 7 + rh)
    y = _section_heading(pdf, y, "Your roadmap")

    # timeline rail with milestone dots above the cards
    rail_y = y + 1.5
    pdf.set_draw_color(*MINT)
    pdf.set_line_width(0.8)
    pdf.set_dash_pattern(dash=1.4, gap=1.4)
    pdf.line(MARGIN + rw / 2, rail_y, MARGIN + CONTENT_W - rw / 2, rail_y)
    pdf.set_dash_pattern()
    y = rail_y + 5
    for i, (label, key, color) in enumerate(cols):
        cx = MARGIN + i * (rw + rgap)
        pdf.set_fill_color(*MINT)
        pdf.circle(x=cx + rw / 2, y=rail_y, radius=2, style="F")
        _card(pdf, cx, y, rw, rh)
        pdf.set_fill_color(*color)
        pdf.rect(cx, y, rw, 9, style="F", round_corners=("TOP_LEFT", "TOP_RIGHT"), corner_radius=3)
        pdf.set_font("PoppinsSemi", "", 8)
        pdf.set_char_spacing(0.8)
        pdf.set_text_color(*WHITE)
        pdf.set_xy(cx, y + 2.3)
        pdf.cell(rw, 4.6, label.upper(), align="C")
        pdf.set_char_spacing(0)
        if key == "one_habit":
            _label(pdf, cx + 5, y + 12.5, "One daily habit", CORAL, size=6.8)
            _body(pdf, cx + 5, y + 17.5, rw - 10, c.get(key, ""), size=9.8, line_h=5)
        else:
            _body(pdf, cx + 5, y + 13, rw - 10, c.get(key, ""), size=9.8, line_h=5)
    y += rh + 7

    # ---- 30-day habit tracker -------------------------------------------
    cols_n, rows_n, tgap = 10, 3, 2.2
    box = (CONTENT_W - 12 - (cols_n - 1) * tgap) / cols_n
    box_h = 9
    tracker_h = 13 + rows_n * box_h + (rows_n - 1) * tgap + 6
    y = _ensure_space(pdf, y, 12 + tracker_h)
    y = _section_heading(pdf, y, "Your 30-day habit tracker")
    _card(pdf, MARGIN, y, CONTENT_W, tracker_h)
    pdf.set_font("Roboto", "I", 9.5)
    pdf.set_text_color(*ACCENT_BLUE)
    pdf.set_xy(MARGIN + 6, y + 5)
    pdf.cell(CONTENT_W - 12, 4.8,
             "Tick a box on each day you do your daily habit. The green boxes mark the end of each week.")
    gy = y + 13
    for rrow in range(rows_n):
        for ccol in range(cols_n):
            day = rrow * cols_n + ccol + 1
            bx = MARGIN + 6 + ccol * (box + tgap)
            by = gy + rrow * (box_h + tgap)
            milestone = day in (7, 14, 21, 30)
            pdf.set_fill_color(*(CREAM if not milestone else (234, 248, 241)))
            pdf.set_draw_color(*(CARD_BORDER if not milestone else MINT))
            pdf.set_line_width(0.35)
            pdf.rect(bx, by, box, box_h, style="DF", round_corners=True, corner_radius=1.6)
            pdf.set_font("PoppinsMed", "", 6.5)
            pdf.set_text_color(*(GRAY if not milestone else MINT_DARK))
            pdf.set_xy(bx + 1.2, by + 0.9)
            pdf.cell(6, 3, str(day))
    y += tracker_h + 7

    # ---- 3 gratitudes a day ---------------------------------------------
    g_h = 33
    # Optional block: if the text above ran long, skip it rather than push
    # the call-to-action onto a page of its own.
    show_gratitude = y + (12 + g_h + 5) + (24 + 3 + 5) <= BOTTOM_LIMIT
    if show_gratitude:
        y = _section_heading(pdf, y, "3 gratitudes a day")
        _card(pdf, MARGIN, y, CONTENT_W, g_h)
        _body(pdf, MARGIN + 6, y + 5, CONTENT_W - 12,
              "Each evening, jot down three things you're grateful for, ideally linked to what you're working on.",
              size=9.5, line_h=4.8, color=GRAY_DARK)
        for n in range(3):
            ly = y + 14.5 + n * 6.3
            pdf.set_font("PoppinsSemi", "", 9)
            pdf.set_text_color(*CORAL)
            pdf.set_xy(MARGIN + 6, ly - 4)
            pdf.cell(6, 5, f"{n + 1}.")
            pdf.set_draw_color(*CARD_BORDER)
            pdf.set_line_width(0.4)
            pdf.line(MARGIN + 13, ly, MARGIN + CONTENT_W - 6, ly)
        y += g_h + 5

    # ---- CTA band (anchored to the bottom of page 2 when there's room) ----
    cta_h = 24
    small_print_h = 5
    if y + cta_h + small_print_h <= BOTTOM_LIMIT:
        y = BOTTOM_LIMIT - cta_h - small_print_h
    y = _ensure_space(pdf, y, cta_h)
    pdf.set_fill_color(*NAVY)
    pdf.rect(MARGIN, y, CONTENT_W, cta_h, style="F", round_corners=True, corner_radius=5)
    pdf.set_font("Poppins", "B", 13.5)
    pdf.set_text_color(*WHITE)
    pdf.set_xy(MARGIN + 9, y + 4.5)
    pdf.cell(110, 7, "Want to talk it through?")
    pdf.set_font("Roboto", "", 9.5)
    pdf.set_text_color(214, 220, 240)
    pdf.set_xy(MARGIN + 9, y + 11.8)
    pdf.multi_cell(
        100, 4.8, align="L", text="Kanth & Shaku would be glad to go through this with you. The next step is the 10-Day Vetting Experience."
    )
    btn_w, btn_h = 60, 11
    bx = MARGIN + CONTENT_W - btn_w - 9
    byy = y + (cta_h - btn_h) / 2
    pdf.set_fill_color(*CORAL)
    pdf.rect(bx, byy, btn_w, btn_h, style="F", round_corners=True, corner_radius=2.5)
    pdf.set_font("PoppinsSemi", "", 8.5)
    pdf.set_text_color(*WHITE)
    pdf.set_xy(bx, byy + 3.2)
    pdf.cell(btn_w, 4.8, "Visit mygrowthacademy.coach", align="C", link=SITE_URL)
    pdf.link(bx, byy, btn_w, btn_h, SITE_URL)
    y += cta_h + 3

    # ---- Small print (one line; never forces a page on its own) ----------
    pdf.set_font("Roboto", "", 7.5)
    pdf.set_text_color(*GRAY)
    pdf.set_xy(MARGIN, min(y, BOTTOM_LIMIT))
    pdf.cell(CONTENT_W, 4,
             "Put together for you by My Growth Academy from your answers. "
             "It's a starting point for a conversation and isn't financial advice.")

    pdf.output(path)
    return path
