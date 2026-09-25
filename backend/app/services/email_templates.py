"""The lead-magnet delivery email: the branded message a visitor gets with
their personalised Growth Blueprint.

Built for real inboxes (Gmail, Apple Mail, Outlook): table layout, every
style inline, no web fonts required, a hidden preview line, and buttons
that still work where images are blocked. Same palette as the website and
the PDF (navy / coral / cream / mint).

Layout:
    cream header ........................ MGA logo
    navy hero ........................... pill + title + "Prepared for <name>"
    greeting + intro
    [ Download your Growth Blueprint ]    (mint button -> the PDF)
    navy band ........................... "Want to talk it through?" [ Book a Free Call ]
    sign-off from Kanth & Shaku
    footer .............................. site link, why you got this

Every visitor-supplied value is HTML-escaped before it goes in.
"""
from __future__ import annotations

import html as _html
from typing import Any

NAVY = "#36488F"
CORAL = "#C84739"
CREAM = "#FFF6EF"
PAGE_BG = "#F3EEE9"
MINT = "#63D0A2"
TEXT = "#424242"
MUTED = "#8F8F8F"

HEADING_FONT = "'Poppins','Segoe UI',Helvetica,Arial,sans-serif"
BODY_FONT = "'Roboto','Segoe UI',Helvetica,Arial,sans-serif"


def _esc(value: Any) -> str:
    return _html.escape(str(value or "").strip())


def _button(href: str, label: str, bg: str, *, full_width: bool = False) -> str:
    """A 'bulletproof' button: a padded table cell, so it renders as a
    button even in Outlook and with images off."""
    width = ' width="100%"' if full_width else ""
    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0"{width} style="border-collapse:separate;">
  <tr>
    <td align="center" bgcolor="{bg}" style="background:{bg};border-radius:8px;">
      <a href="{_esc(href)}" target="_blank"
         style="display:block;padding:15px 28px;font-family:{HEADING_FONT};font-size:16px;font-weight:700;
                color:#FFFFFF;text-decoration:none;border-radius:8px;">{_esc(label)}</a>
    </td>
  </tr>
</table>"""


def build_report_email(
    *,
    name: str,
    content: dict[str, Any],
    download_url: str,
    booking_url: str,
    booking_label: str,
    site_url: str,
    site_display: str,
    logo_url: str,
    pdf_attached: bool = False,
) -> tuple[str, str]:
    """Returns (subject, html_body)."""
    first_name = (name or "").strip().split()[0] if (name or "").strip() else ""
    greeting = f"Hi {_esc(first_name)}," if first_name else "Hi there,"
    title = content.get("title") or "Your Personalised Growth Blueprint"

    subject = (
        f"{first_name}, your Growth Blueprint is ready"
        if first_name
        else "Your Growth Blueprint is ready"
    )
    preheader = (
        "Your personalised 3-year snapshot from Kanth & Shaku is ready to download."
    )

    attachment_note = (
        "It's also attached to this email as a PDF, so you can print it."
        if pdf_attached
        else "Save it or print it. There's a 30-day habit tracker inside."
    )
    download_block = (
        f"""
<tr><td align="center" style="padding:8px 40px 4px;">{_button(download_url, "Download Your Growth Blueprint", MINT, full_width=True)}</td></tr>
<tr><td align="center" style="padding:6px 40px 0;font-family:{BODY_FONT};font-size:13px;color:{MUTED};">{_esc(attachment_note)}</td></tr>"""
        if download_url
        else ""
    )

    logo_html = (
        f'<img src="{_esc(logo_url)}" width="180" alt="My Growth Academy" '
        f'style="display:block;width:180px;max-width:180px;height:auto;border:0;outline:none;'
        f'font-family:{HEADING_FONT};font-size:20px;font-weight:700;color:{NAVY};">'
    )

    body_html = f"""
<div style="display:none;max-height:0;overflow:hidden;opacity:0;mso-hide:all;font-size:1px;line-height:1px;color:{PAGE_BG};">
  {_esc(preheader)}&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;
</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{PAGE_BG}" style="background:{PAGE_BG};">
<tr><td align="center" style="padding:24px 12px;">

<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
       style="width:100%;max-width:600px;background:#FFFFFF;border-radius:14px;overflow:hidden;border-collapse:separate;">

  <!-- Logo -->
  <tr><td align="center" bgcolor="{CREAM}" style="background:{CREAM};padding:26px 40px 22px;">
    <a href="{_esc(site_url)}" target="_blank" style="text-decoration:none;">{logo_html}</a>
  </td></tr>

  <!-- Hero -->
  <tr><td bgcolor="{NAVY}" style="background:{NAVY};padding:34px 40px 36px;">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
      <td bgcolor="{CORAL}" style="background:{CORAL};border-radius:20px;padding:5px 14px;font-family:{HEADING_FONT};
          font-size:11px;font-weight:700;letter-spacing:1.2px;color:#FFFFFF;text-transform:uppercase;">
        Your 3-Year Future Snapshot
      </td>
    </tr></table>
    <div style="font-family:{HEADING_FONT};font-size:26px;line-height:34px;font-weight:700;color:#FFFFFF;padding-top:16px;">
      {_esc(title)}
    </div>
    <div style="font-family:{BODY_FONT};font-size:15px;line-height:22px;color:#D6DCF0;padding-top:8px;">
      {"Prepared for " + _esc(name) + " by Kanth &amp; Shaku" if name.strip() else "Prepared for you by Kanth &amp; Shaku"}
    </div>
  </td></tr>

  <!-- Intro -->
  <tr><td style="padding:32px 40px 8px;font-family:{BODY_FONT};font-size:16px;line-height:25px;color:{TEXT};">
    <p style="margin:0 0 14px;">{greeting}</p>
    <p style="margin:0 0 8px;">
      Thank you for answering our questions. Your personal Growth Blueprint is ready: where
      you are today, where you'd like to be in three years, and your first steps to get there.
    </p>
  </td></tr>

  {download_block}

  <!-- Book a call -->
  <tr><td style="padding:34px 40px 8px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{NAVY}"
           style="background:{NAVY};border-radius:12px;border-collapse:separate;">
      <tr><td style="padding:26px 28px 8px;font-family:{HEADING_FONT};font-size:20px;font-weight:700;color:#FFFFFF;">
        Want to talk it through?
      </td></tr>
      <tr><td style="padding:0 28px 18px;font-family:{BODY_FONT};font-size:15px;line-height:23px;color:#D6DCF0;">
        Book a free call with Kanth &amp; Shaku and we'll go through your blueprint with you.
      </td></tr>
      <tr><td style="padding:0 28px 26px;">{_button(booking_url, booking_label, CORAL)}</td></tr>
    </table>
  </td></tr>

  <!-- Sign-off -->
  <tr><td style="padding:26px 40px 34px;font-family:{BODY_FONT};font-size:16px;line-height:25px;color:{TEXT};">
    Rooting for you,<br>
    <span style="font-family:{HEADING_FONT};font-weight:700;color:{NAVY};">Kanth &amp; Shaku</span><br>
    <span style="font-size:14px;color:{MUTED};">My Growth Academy</span>
  </td></tr>

  <!-- Footer -->
  <tr><td bgcolor="{CREAM}" style="background:{CREAM};padding:20px 40px;font-family:{BODY_FONT};font-size:12px;line-height:19px;color:{MUTED};text-align:center;">
    You're getting this email because you asked for your free Future Snapshot at
    <a href="{_esc(site_url)}" target="_blank" style="color:{NAVY};text-decoration:underline;">{_esc(site_display)}</a>.<br>
    Just reply to this email if you have any questions. A starting point, not financial advice.
  </td></tr>

</table>

</td></tr>
</table>
"""
    return subject, body_html
