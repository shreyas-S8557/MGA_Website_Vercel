Fonts bundled for the lead-magnet PDF (app/services/pdf_service.py), so the
PDF matches the website's two-font system without any network access at
render time.

- Poppins (headings) — SIL Open Font License 1.1, see OFL-Poppins.txt.
  Latin subset, converted to TTF from the @fontsource/poppins package.
- Roboto (body) — Roboto v3.012 static TTFs from
  github.com/googlefonts/roboto-3-classic, SIL Open Font License 1.1.
- DejaVu Sans — fallback only, for characters outside the Latin subset
  (e.g. accented names). Bitstream Vera / DejaVu free license.
