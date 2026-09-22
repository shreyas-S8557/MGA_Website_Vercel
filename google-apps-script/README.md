# Google Apps Script — MGA Form Forwarder

`Code.gs` runs inside the Google Form's response spreadsheet and forwards
every new submission to the MGA lead-magnet backend's
`POST /api/leads/google-form` webhook.

## Setup

1. Build the Google Form (whatever questions the business wants — the
   backend does not hard-code question text; see `backend/app/services/
   lead_profile_service.py`'s `FIELD_ALIASES`, and the optional
   `field_map` field in the webhook payload for an explicit override).
2. Form → **Responses** → the green Sheets icon → create the linked
   response spreadsheet.
3. Open that spreadsheet → **Extensions → Apps Script** → replace the
   default `Code.gs` with this file's contents.
4. **Project Settings → Script Properties**, add:
   | Property | Value |
   |---|---|
   | `MGA_WEBHOOK_URL` | `https://<your-backend-domain>/api/leads/google-form` |
   | `MGA_WEBHOOK_SECRET` | same value as the backend's `GOOGLE_FORM_WEBHOOK_SECRET` env var |
5. **Triggers** (clock icon) → **+ Add Trigger** → function `onFormSubmit`,
   event source `From spreadsheet`, event type `On form submit`.
6. Submit a test response and confirm: the sheet gets a new "MGA Webhook
   Status" column showing `sent`, and the lead shows up in the backend's
   dashboard under "MGA Leads".

See `../README.md` at the repo root for the full pipeline this feeds into.

## Why Apps Script instead of a native Google Forms webhook

Google Forms has no built-in "POST to a URL" action — PART 14 of the
migration brief anticipated this ("If Google Forms cannot directly POST the
required payload, implement a Google Apps Script integration"), so this is
the standard, supported way to bridge Forms -> an external API.

## Idempotency

Two layers, per PART 4:
1. **Apps Script side** (this file): a "MGA Webhook Status" column is added
   to the response sheet; a row already marked `sent` is skipped on any
   re-run of `onFormSubmit`.
2. **Backend side** (the real safety net): every request carries
   `form_submission_id` (Google's own response ID), which is a UNIQUE
   column in the backend's database — a duplicate POST for the same
   submission is a no-op that returns the existing lead instead of
   creating a new one or re-sending an email.
