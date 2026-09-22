/**
 * MGA Google Form -> backend webhook forwarder (PART 14).
 *
 * SETUP (see ./README.md in this folder for the full walkthrough):
 *   1. Open the Google Form's linked response Spreadsheet.
 *   2. Extensions -> Apps Script, paste this file's contents in as Code.gs.
 *   3. Project Settings -> Script Properties, add:
 *        MGA_WEBHOOK_URL    = https://api.mygrowthacademy.coach/api/leads/google-form
 *        MGA_WEBHOOK_SECRET = <same value as backend's GOOGLE_FORM_WEBHOOK_SECRET>
 *   4. Triggers (clock icon) -> Add Trigger -> onFormSubmit -> "From spreadsheet" -> "On form submit".
 *   5. Submit a test form response and confirm a 202 in Executions log.
 *
 * Never hard-code MGA_WEBHOOK_SECRET into this file (PART 14/PART 16) —
 * always read it from PropertiesService as done below.
 */

function onFormSubmit(e) {
  var props = PropertiesService.getScriptProperties();
  var webhookUrl = props.getProperty('MGA_WEBHOOK_URL');
  var webhookSecret = props.getProperty('MGA_WEBHOOK_SECRET');

  if (!webhookUrl || !webhookSecret) {
    Logger.log('MGA_WEBHOOK_URL / MGA_WEBHOOK_SECRET script properties are not set.');
    return;
  }

  // Idempotency guard #1 (cheap, local): mark the row as "sent" so a
  // manual re-run of this function, or Apps Script's own execution retry,
  // does not re-POST a row already forwarded. The webhook itself is ALSO
  // idempotent by form_submission_id (PART 4), so this is defense in depth,
  // not the only safeguard.
  var sheet = e.range.getSheet();
  var row = e.range.getRow();
  var statusColumn = ensureStatusColumn_(sheet);
  var currentStatus = sheet.getRange(row, statusColumn).getValue();
  if (currentStatus === 'sent') {
    return;
  }

  var payload = buildPayload_(e, sheet, row);

  try {
    var response = UrlFetchApp.fetch(webhookUrl, {
      method: 'post',
      contentType: 'application/json',
      headers: { 'X-MGA-Webhook-Secret': webhookSecret },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true,
    });

    var code = response.getResponseCode();
    if (code >= 200 && code < 300) {
      sheet.getRange(row, statusColumn).setValue('sent');
    } else {
      // Leave status blank (not "sent") so it can be retried; the backend
      // will treat a retry of the same formSubmissionId as a no-op if it
      // actually did succeed the first time (idempotency).
      sheet.getRange(row, statusColumn).setValue('error: HTTP ' + code);
      Logger.log('Webhook returned HTTP ' + code + ': ' + response.getContentText());
    }
  } catch (err) {
    sheet.getRange(row, statusColumn).setValue('error: ' + err.message);
    Logger.log('Webhook POST failed: ' + err.message);
  }
}

/**
 * Builds the JSON payload the backend expects
 * (see backend/app/api/schemas.py: GoogleFormWebhookPayload).
 *
 * Maps every column header -> its value into `answers` (PART 3: never lose
 * raw answers), and separately lifts out name/email/phone if a column
 * header matches common phrasings, so the backend doesn't have to guess.
 */
function buildPayload_(e, sheet, row) {
  var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  var rowValues = sheet.getRange(row, 1, 1, sheet.getLastColumn()).getValues()[0];

  var answers = {};
  var name = null, email = null, phone = null, timestamp = null;

  for (var i = 0; i < headers.length; i++) {
    var header = String(headers[i] || '').trim();
    var value = rowValues[i];
    if (!header || header === 'MGA Webhook Status') continue; // skip our own bookkeeping column

    var lower = header.toLowerCase();
    if (lower === 'timestamp') {
      timestamp = value;
      continue;
    }
    if (!name && (lower === 'name' || lower === 'full name')) name = String(value);
    if (!email && (lower === 'email' || lower === 'e-mail')) email = String(value);
    if (!phone && (lower.indexOf('phone') !== -1 || lower.indexOf('whatsapp') !== -1)) phone = String(value);

    answers[header] = value;
  }

  // form_submission_id: prefer the Form's own response ID (stable, unique,
  // exactly what PART 4 asks idempotency to key on) when available via the
  // form response object; fall back to a spreadsheet-row-based ID.
  var formSubmissionId;
  try {
    formSubmissionId = e.response.getId();
  } catch (err) {
    formSubmissionId = sheet.getSheetId() + '-row-' + row;
  }

  return {
    form_submission_id: formSubmissionId,
    submitted_at: timestamp ? new Date(timestamp).toISOString() : new Date().toISOString(),
    name: name,
    email: email,
    phone: phone,
    source_campaign: 'mygrowthacademy.coach',
    answers: answers,
  };
}

/** Adds (once) a "MGA Webhook Status" bookkeeping column and returns its index. */
function ensureStatusColumn_(sheet) {
  var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  var existingIndex = headers.indexOf('MGA Webhook Status');
  if (existingIndex !== -1) return existingIndex + 1;

  var newColumn = sheet.getLastColumn() + 1;
  sheet.getRange(1, newColumn).setValue('MGA Webhook Status');
  return newColumn;
}
