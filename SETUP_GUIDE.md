# Setup guide: Calendly, Google Sheets, Gemini, live email

What changed in this version, and what to click to switch each part on.
All settings go in **Vercel → backend project → Settings → Environment
Variables**, and each change needs a **Redeploy** (Deployments → ⋯ →
Redeploy) before it takes effect.

---

## 0. Calendly "Book a Free Call" (already done, no setup)

- **PDF:** the button in the navy "Want to talk it through?" band now says
  **Book a Free Call** and opens
  `https://calendly.com/shaku-c-miriyala/mygrowth-academy`.
- **Email:** the delivery email has the same button.
- **Website:** the quiz's success screen has a **Book a Free Call** button
  under the download button.

The `?month=2026-09` part of the link was left off on purpose. Calendly
opens on the current month by itself, and a fixed month would show an old
calendar from October onwards.

To change the link or the wording later: `BOOKING_URL` / `BOOKING_LABEL`
(backend) and `NEXT_PUBLIC_BOOKING_URL` (website project).

---

## 1. Google Sheets (as well as Turso)

Turso stays the main database; every lead is also copied to a Google Sheet,
one row per lead, kept up to date. Full step-by-step instructions
are in `google-apps-script/README.md` → "Leads Google Sheet". Short version:

1. New Google Sheet → **Extensions → Apps Script** → paste
   `google-apps-script/LeadsSheet.gs` → Save.
2. **Project Settings → Script Properties**: `SHEET_SECRET` = a long random string.
3. **Deploy → New deployment → Web app**, Execute as **Me**, Who has access
   **Anyone** → Deploy → authorize → copy the `/exec` URL.
4. Vercel backend env vars: `GOOGLE_SHEETS_WEBHOOK_URL` = that URL,
   `GOOGLE_SHEETS_WEBHOOK_SECRET` = the same random string. Redeploy.
5. Take the quiz once to test, then dashboard → Settings → **Sync all
   leads to Google Sheet** to copy the leads you already have.

---

## 2. Gemini API key (free) in place of the old LLM key

1. Go to **https://aistudio.google.com/apikey** and sign in with the
   business Google account.
2. Click **Create API key**. If asked, let it create a new project. Copy
   the key (starts with `AIza...`).
3. Vercel → backend → Environment Variables:
   - **Add** `GEMINI_API_KEY` = the key.
   - **Delete** `OPENAI_API_KEY`, `OPENAI_BASE_URL` and `LLM_MODEL`
     (the old provider's settings). The default model is
     `gemini-3.5-flash`, so `LLM_MODEL` isn't needed.
4. Redeploy.
5. Test: take the quiz. The report should quote the answers back in
   natural sentences. If it reads like a fixed template, the key isn't
   being used: check the Vercel function logs for a line starting
   `lead_magnet_service llm warn:`.

Worth knowing:

- **Free tier limits** are per minute and per day, far above what a quiz
  gets. If you ever hit them, set `LLM_MODEL=gemini-3.5-flash-lite`
  (higher limits), or turn on billing in AI Studio. When Gemini is
  unavailable for any reason, the lead still gets a report (the built-in
  template), so nothing breaks.
- **Privacy:** on the free tier, Google may use what you send (the quiz
  answers) to improve its products. The paid tier doesn't. If that
  matters for your leads, enable billing on the project; the cost at this
  volume is pennies.
- **Model names change.** If Google retires `gemini-3.5-flash`, pick a
  current one from https://ai.google.dev/gemini-api/docs/models and set
  it as `LLM_MODEL`.

---

## 3. Live email: on

`PROSPECT_ALLOW_LIVE_SEND` now defaults to **true** in the code and in
`.env.example`. **Vercel's setting wins over the code**, so in the backend
project make sure `PROSPECT_ALLOW_LIVE_SEND` is `true` (or delete it), then
redeploy. Before relying on it, open the dashboard → Settings → **Send
test email** to yourself.

### A dedicated email address for the lead magnet

Use an address on your own domain that exists only for this, e.g.
`blueprint@mygrowthacademy.coach` (or `hello@`, `growth@`). Emails from
your own domain land in inboxes far more reliably than from a
`@gmail.com` address, and replies go somewhere you read.

**Step 1: create the address.**

- *If you use Google Workspace for mygrowthacademy.coach* (free way):
  admin.google.com → Directory → Users → click Shaku (or whoever should
  get the replies) → **User information → Alternate email addresses
  (aliases)** → add `blueprint`. Replies to it land in that person's inbox.
- *If you don't use Workspace:* most domain registrars (GoDaddy, Namecheap,
  Cloudflare, etc.) offer free **email forwarding**. Forward
  `blueprint@mygrowthacademy.coach` to the inbox you read.

**Step 2: send from it. Pick the provider you're on.**

*Option A: MailerLite Classic (what you use now).*

1. In MailerLite, add `blueprint@mygrowthacademy.coach` as a sender email
   and click the verification link MailerLite emails to it.
2. In MailerLite's domain settings, **authenticate the domain** (it gives
   you SPF and DKIM DNS records to add at your registrar). This is what
   keeps the email out of spam.
3. Vercel backend env vars:
   `MAILERLITE_SENDER_EMAIL=blueprint@mygrowthacademy.coach`,
   `EMAIL_FROM_NAME=Kanth & Shaku | My Growth Academy`. Redeploy.

MailerLite can't attach files, so the PDF arrives via the big **Download
Your Growth Blueprint** button (the email also shows the whole summary).

*Option B: Gmail / Google Workspace (the PDF is attached to the email).*

1. On the Google account that owns the alias: turn on 2-Step Verification,
   then create an **App password** (myaccount.google.com → Security →
   App passwords).
2. Gmail → Settings → **Accounts → Send mail as → Add another email
   address** → `blueprint@mygrowthacademy.coach` (only needed if it's an
   alias, not the account's main address).
3. Vercel backend env vars: `EMAIL_PROVIDER=gmail`,
   `GMAIL_ADDRESS=<the account's main address>`,
   `GMAIL_APP_PASSWORD=<16-character app password>`,
   `GMAIL_FROM_ADDRESS=blueprint@mygrowthacademy.coach`,
   `EMAIL_FROM_NAME=Kanth & Shaku | My Growth Academy`. Redeploy.

Gmail allows about 500 emails a day (2,000 on Workspace).

### The email itself

A short, branded note that matches the website and PDF (the file is
`backend/app/services/email_templates.py`). The details live in the PDF,
so the email doesn't repeat them:

- Subject: **"Priya, your Growth Blueprint is ready"**
- Logo header, navy title band with "Prepared for <name> by Kanth & Shaku"
- A two-line thank-you and a big **Download Your Growth Blueprint** button
- Navy **Want to talk it through?** box with the **Book a Free Call** button
- Sign-off from Kanth & Shaku, small footer

It's built with tables and inline styles, so it looks right in Gmail,
Apple Mail and Outlook, on phones and desktops. The logo loads from
`<PUBLIC_SITE_URL>/images/logo.png`, so keep `PUBLIC_SITE_URL` pointing at
the live website.

---

## Checklist of backend env vars to add or change on Vercel

| Variable | Value |
|---|---|
| `GEMINI_API_KEY` | from aistudio.google.com/apikey |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `LLM_MODEL` | **delete** |
| `GOOGLE_SHEETS_WEBHOOK_URL` | Apps Script `/exec` URL |
| `GOOGLE_SHEETS_WEBHOOK_SECRET` | same string as `SHEET_SECRET` |
| `PROSPECT_ALLOW_LIVE_SEND` | `true` |
| `MAILERLITE_SENDER_EMAIL` (or the `GMAIL_*` set) | your dedicated address |
| `EMAIL_FROM_NAME` | e.g. `Kanth & Shaku \| My Growth Academy` |

Then redeploy the backend. The website project needs no changes (the
Calendly link is built in), but redeploy it too so the new success-screen
button goes live.
