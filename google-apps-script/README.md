# Google Apps Script

Two separate scripts live here:

| File | What it does | Needed? |
|---|---|---|
| `LeadsSheet.gs` | Receives every lead from the backend and keeps a **Google Sheet** of them (one row per lead, updated as it moves along). | Yes, if you want leads in Google Sheets. |
| `Code.gs` | Forwards a **Google Form**'s responses to the backend. | Only if you collect answers through a Google Form. |

---

## Leads Google Sheet (`LeadsSheet.gs`)

Turso stays the main database. On top of that, the backend copies each
lead into this sheet: name, email, phone, source, status, a link to their
PDF, whether the email went out, and one column per quiz question. The
same row is updated if the lead changes (e.g. after a retry), so there are
no duplicates.

### Setup (about 5 minutes)

1. **Make a secret.** Any long random string, e.g. run
   `python -c "import secrets; print(secrets.token_urlsafe(32))"` or use a
   password generator. You'll paste it in two places.
2. **Create the sheet.** In Google Drive: New → Google Sheets. Name it,
   e.g. *MGA Website Leads*. (Use the business Google account; the sheet
   belongs to whoever deploys the script.)
3. **Add the script.** In the sheet: **Extensions → Apps Script**. Delete
   the sample `function myFunction() {}` and paste the whole of
   `LeadsSheet.gs`. Click **Save** (disk icon).
4. **Store the secret.** Left sidebar → **Project Settings** (gear) →
   scroll to **Script Properties** → **Add script property**:
   | Property | Value |
   |---|---|
   | `SHEET_SECRET` | the secret from step 1 |

   Click **Save script properties**.
5. **Deploy it.** Top right → **Deploy → New deployment** → gear next to
   "Select type" → **Web app**. Set:
   - Description: `MGA leads`
   - Execute as: **Me**
   - Who has access: **Anyone**

   Click **Deploy**, then **Authorize access** and allow it (on the
   "Google hasn't verified this app" screen: **Advanced → Go to ...
   (unsafe)**. It's your own script). Copy the **Web app URL**
   (it ends in `/exec`).
6. **Tell the backend.** Vercel → the **backend** project → Settings →
   Environment Variables, add:
   | Name | Value |
   |---|---|
   | `GOOGLE_SHEETS_WEBHOOK_URL` | the Web app URL from step 5 |
   | `GOOGLE_SHEETS_WEBHOOK_SECRET` | the secret from step 1 |

   Then **Deployments → ⋯ → Redeploy** (env var changes only apply after a
   redeploy).
7. **Test.** Open the Web app URL in your browser; it should say
   `"MGA leads sheet receiver is running."` Then take the quiz on the
   website: a **Leads** tab appears in the sheet with your row.
8. **Copy existing leads (once).** Open the admin dashboard
   (`frontend/index.html`) → Settings → **Sync all leads to Google Sheet**.

### Good to know

- "Who has access: Anyone" only means the backend can reach it without a
  Google login. Every request must carry the secret, and the script only
  writes rows, it never reads the sheet back out.
- **If you edit the script later**, publish the change with **Deploy →
  Manage deployments → ✏️ (edit) → Version: New version → Deploy**. That
  keeps the same URL. ("New deployment" would give you a new URL.)
- You can add your own columns (e.g. *Called?*, *Notes*) to the right.
  The backend never overwrites columns it doesn't send.
- Don't rename the header row or the **Leads** tab; the script matches on
  them. Sorting and filtering are fine.
- If a lead didn't show up, the dashboard's lead detail shows a
  **Google Sheet** line with the reason.

---

## Google Form forwarder (`Code.gs`)


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
