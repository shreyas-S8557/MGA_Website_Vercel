# My Growth Academy — Website + Lead Magnet

The website for **mygrowthacademy.coach** plus the backend behind its lead
magnet: a visitor takes the on-page "3-Year Future Snapshot" quiz, gets a
personalized Growth Blueprint PDF, and it's emailed to them. Your team
gets notified about each new lead.

```
                 MGA WEBSITE (website/, Next.js on Vercel)
                 "Get My Free 3-Year Snapshot"  (LeadMagnetModal.tsx)
                              │
                              ▼
          POST /api/leads/website   (public, IP rate-limited)
                              │
                              │   optional: Google Form → Apps Script
                              │   (google-apps-script/Code.gs)
                              │   → POST /api/leads/google-form (shared secret)
                              ▼
   RECEIVED → NORMALIZED → PROFILED → LEAD_MAGNET_GENERATING
           → LEAD_MAGNET_READY → DELIVERY_QUEUED → DELIVERED
                              │
          ┌──────────────┬────┴─────────┬───────────────────┐
          ▼              ▼              ▼                   ▼
   lead_profile_   lead_magnet_     PDF download      Emails (best-effort)
   service         service + LLM    GET /api/lead-    • report → the visitor
   (answers →      + pdf_service    magnets/{id}      • new-lead alert → team
    profile)       (personalized                      (MailerLite or Gmail)
                    PDF)
```

## What's in this repo

| Path | What it is |
|---|---|
| `website/` | The Next.js site (deploys to Vercel). `components/LeadMagnetModal.tsx` is the quiz. |
| `backend/` | FastAPI service: receives submissions, generates the PDF, sends the emails, serves the dashboard API. |
| `frontend/index.html` | A single-file admin dashboard for browsing leads, downloading their PDFs and retrying failures. No build step. |
| `google-apps-script/` | Optional forwarder if you want to collect answers through a Google Form instead of (or as well as) the website quiz. |

## 1. Run the backend

```bash
cd backend
pip install -r requirements-dev.txt
cp ../.env.example ../.env        # then fill it in -- see section 3
uvicorn app.main:app --reload --port 8000
```

Interactive API docs are at `http://localhost:8000/docs`.

Leads are stored in a SQLite file (`data/pipeline_state.db` by default) and
PDFs in `data/mga_lead_magnets/`. Both are created on first run.

Try a submission:

```bash
curl -X POST http://localhost:8000/api/leads/website \
  -H "Content-Type: application/json" \
  -d '{
        "name": "Alex Rivera",
        "email": "alex@example.com",
        "answers": {
          "What is your financial goal?": "Build a $20k emergency fund",
          "What is your biggest challenge?": "We overspend on eating out"
        }
      }'
```

The response includes a `lead_magnet_delivery_url` for the PDF.

## 2. Run the website

```bash
cd website
cp .env.example .env.local   # set NEXT_PUBLIC_API_URL to the backend's URL
npm install
npm run dev
```

The quiz posts straight to `${NEXT_PUBLIC_API_URL}/api/leads/website`, so
the website's origin must be listed in the backend's
`PROSPECT_CORS_ORIGINS`.

## 3. Configuration

Everything is set through environment variables. `.env.example` at the repo
root lists all of them with comments. The important ones:

| Variable | Purpose |
|---|---|
| `DASHBOARD_API_KEY` | **Required.** Protects the dashboard and every dashboard API route (lead names, emails, phones). If it's unset those routes are locked. |
| `PUBLIC_API_BASE_URL` | This backend's public URL, used in the PDF download links. Must be set before going live. |
| `PROSPECT_CORS_ORIGINS` | Browser origins allowed to call the API. Add the live website origin. |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `LLM_MODEL` | Optional LLM personalization of the report. Without a key, a deterministic template is used. |
| `PROSPECT_ALLOW_LIVE_SEND` | Master switch for real email. Off by default. |
| `EMAIL_PROVIDER` | `mailerlite` (default) or `gmail`. |
| `MAILERLITE_API_TOKEN` / `MAILERLITE_SENDER_EMAIL` / `MAILERLITE_SENDER_NAME` | MailerLite credentials (sender must be verified in MailerLite). |
| `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` | Gmail credentials, if `EMAIL_PROVIDER=gmail`. |
| `LEAD_NOTIFY_EMAILS` | Comma-separated team addresses to alert about each new lead. |
| `GOOGLE_FORM_WEBHOOK_SECRET` | Only for the Google Form path and the dashboard's Retry button. |
| `PROSPECT_DB_PATH` / `MGA_LEAD_MAGNET_DIR` | Override where leads and PDFs are stored. |

### Emails

- **Report to the visitor:** the personalized report inline, plus a button
  linking to the PDF. With Gmail the PDF is also attached (MailerLite
  can't carry attachments).
- **New-lead alert to the team:** name, email, phone, source, all their
  answers, whether their report was generated and emailed, and a link to
  the PDF. It's sent once per lead, even if report generation failed, so
  you can still follow up. Retries never send it again.

Both are best-effort. If live sending is off, or a send fails, the lead
still reaches `DELIVERED` and the PDF is still downloadable. The outcome is
recorded on the lead (`email_sent`, `email_error`, `team_notified_at`,
`team_notify_error`) and shown in the dashboard.

Before going live, use the dashboard's **Settings** panel to test the
MailerLite connection and send yourself a test email.

## 4. Dashboard

Open `frontend/index.html` in a browser (or serve it statically). Paste your
`DASHBOARD_API_KEY` into the box at the top right; the browser remembers it.

The **MGA Leads** section shows counts by status and a filterable list.
Click a lead to see their original answers, the normalized profile, the PDF
download link, delivery and notification status and, for a failed lead,
the error and a **Retry from failed stage** button. Retry asks for the
`GOOGLE_FORM_WEBHOOK_SECRET`.

## 5. API

| Route | Auth | Purpose |
|---|---|---|
| `POST /api/leads/website` | public, rate-limited | Website quiz submission. Runs the full pipeline and returns the PDF link. |
| `POST /api/leads/google-form` | `X-MGA-Webhook-Secret` | Google Form submission (via Apps Script). |
| `POST /api/leads/{id}/retry` | `X-MGA-Webhook-Secret` | Resume a failed lead from its failed stage. |
| `GET /api/lead-magnets/{lead_magnet_id}` | public (unguessable id) | Download the PDF. |
| `GET /api/health` | public | Health check. |
| `GET /api/dashboard/mga-leads[/summary\|/{id}]` | `X-Dashboard-Key` | Lead list, status counts and detail. |
| `GET /api/settings`, `GET /api/health/providers` | `X-Dashboard-Key` | Which providers are configured (never returns secrets). |
| `POST /api/email/provider/test`, `/test-send` | `X-Dashboard-Key` | Check MailerLite and send one test email. |

## 6. Reliability

- **Nothing is lost.** Each stage is saved before the next starts, and the
  raw answers are always kept. If a stage fails, the lead is marked
  `failed` with `failed_stage` and `error_message` set.
- **Retry resumes, never repeats.** Retry picks up from the last completed
  stage. It never re-renders a PDF that already exists and never
  re-delivers a lead that's already delivered.
- **Idempotent Google Form intake.** `form_submission_id` is unique, so a
  retried Apps Script POST returns the existing lead instead of creating a
  duplicate.

## 7. Google Form (optional)

The website quiz doesn't need it. If you also want to collect answers
through a Google Form, see `google-apps-script/README.md`. In short: link
the form to a response spreadsheet, paste `Code.gs` into its Apps Script
editor, set `MGA_WEBHOOK_URL` (`https://<backend>/api/leads/google-form`)
and `MGA_WEBHOOK_SECRET` as Script Properties, and add an `onFormSubmit`
trigger. The question text doesn't have to be fixed: see `FIELD_ALIASES` in
`backend/app/services/lead_profile_service.py`, or send a `field_map`.

## 8. Deploying

- **Website:** deploy `website/` to Vercel (see `website/vercel.json`).
- **Backend:** a second Vercel project with `backend/` as its root, storing
  leads in Turso. Steps below. (It also runs anywhere with a real disk,
  such as a small VM, using the local SQLite file instead.)

### Backend on Vercel

The backend deploys as its own Vercel project from this same repo
(`backend/vercel.json`; Vercel finds the FastAPI app in `app/main.py`).

1. **Create the database.** Vercel functions have no permanent disk, so
   leads live in [Turso](https://turso.tech) (hosted SQLite, free tier).
   Install the Turso integration from the Vercel Marketplace, or create a
   database at turso.tech in **AWS us-east-1** (next to Vercel's default
   `iad1` function region). You need its URL (`libsql://...turso.io`) and
   an auth token. The table is created automatically on first use.
2. **New Vercel project** → import this repo → **Root Directory:
   `backend`**. Framework: FastAPI (auto-detected).
3. **Environment variables** (Project → Settings → Environment Variables):
   `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, `DASHBOARD_API_KEY`,
   `GOOGLE_FORM_WEBHOOK_SECRET`, the MailerLite ones, `OPENAI_API_KEY` (+
   `OPENAI_BASE_URL`, `LLM_MODEL`), `LEAD_NOTIFY_EMAILS`, and
   `PROSPECT_ALLOW_LIVE_SEND=true` once email is tested. See `.env.example`.
4. Deploy, then open `https://<backend>.vercel.app/api/health`. It must
   say `"status": "ok"` with a `turso:` database path. `"degraded"` means
   Turso isn't configured or reachable.
5. In the **website** project, set `NEXT_PUBLIC_API_URL` to the backend's
   URL and redeploy it.

Notes:

- `PUBLIC_API_BASE_URL` defaults to the backend project's production
  domain; set it only if you give the backend a custom domain.
- Generated PDFs go to `/tmp`, which Vercel clears whenever it likes;
  they're rebuilt from the database on the next download, so links never
  break.
- The website's origin (`PUBLIC_SITE_URL`) is always allowed by CORS; add
  any other origins (e.g. your custom domain) to `PROSPECT_CORS_ORIGINS`.
- The per-visitor rate limit is kept in memory, so each running instance
  counts separately. Fine as basic spam protection at this scale.

## 9. Tests

No network or API keys needed. Real email is never sent.

```bash
cd backend
python -m pytest
```
