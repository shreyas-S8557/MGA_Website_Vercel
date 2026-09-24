Fonts bundled for the lead-magnet PDF (app/services/pdf_service.py), so the
PDF matches the website's two-font system without any network access at
render time.

- Poppins (headings) — SIL Open Font License 1.1, see OFL-Poppins.txt.
  Bold / SemiBold / Medium TTFs from github.com/google/fonts (ofl/poppins).
- Roboto (body) — Roboto v3.012 static TTFs from
  github.com/googlefonts/roboto-3-classic (hinted/static), SIL Open Font License 1.1.
- Roboto Bold Italic (the PDF's intro line) — Roboto v2.137, converted to TTF
  from the roboto-fontface npm package, Apache License 2.0.
- DejaVu Sans — fallback only, for characters outside the Latin subset
  (e.g. accented names). Bitstream Vera / DejaVu free license, see LICENSE-DejaVu.txt.
