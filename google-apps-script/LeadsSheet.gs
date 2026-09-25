/**
 * MGA Leads -> Google Sheet (receiver).
 *
 * The backend POSTs every lead here (see backend/app/services/sheets_sync.py).
 * Each lead is ONE row, matched on "Lead ID": a new lead is appended, and
 * the same row is updated in place as the lead moves through the pipeline
 * (status, PDF link, email sent, ...). New quiz questions get their own
 * column automatically.
 *
 * SETUP (full walkthrough in ./README.md, "Leads Google Sheet"):
 *   1. Create a new Google Sheet, e.g. "MGA Website Leads".
 *   2. Extensions -> Apps Script. Delete the sample code, paste this file.
 *   3. Project Settings (gear) -> Script Properties -> Add:
 *        SHEET_SECRET = <same value as the backend's GOOGLE_SHEETS_WEBHOOK_SECRET>
 *   4. Deploy -> New deployment -> type "Web app"
 *        Execute as:      Me
 *        Who has access:  Anyone
 *      Authorize, then copy the Web app URL (ends in /exec) into the
 *      backend's GOOGLE_SHEETS_WEBHOOK_URL.
 *
 * "Anyone" is needed so the backend can reach it without a Google login;
 * every request must still carry SHEET_SECRET or it is refused.
 */

var TAB_NAME = 'Leads';

function doPost(e) {
  try {
    var body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    var expected = PropertiesService.getScriptProperties().getProperty('SHEET_SECRET');
    if (!expected) return json_({ ok: false, error: 'SHEET_SECRET script property is not set.' });
    if (body.secret !== expected) return json_({ ok: false, error: 'Invalid secret.' });

    var leads = body.leads || (body.lead ? [body.lead] : []);
    if (!leads.length) return json_({ ok: true, written: 0 });

    // One writer at a time, so two leads arriving together can't both
    // grab the same empty row or add the same new column twice.
    var lock = LockService.getScriptLock();
    lock.waitLock(20000);
    try {
      var written = upsertLeads_(leads);
      return json_({ ok: true, written: written });
    } finally {
      lock.releaseLock();
    }
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

// Visiting the /exec URL in a browser shows this -- handy to confirm the
// deployment is live.
function doGet() {
  return json_({ ok: true, message: 'MGA leads sheet receiver is running.' });
}

function upsertLeads_(leads) {
  var sheet = getSheet_();
  var headers = ensureHeaders_(sheet, leads);
  var idCol = headers.indexOf('Lead ID') + 1;

  // Existing Lead IDs -> row number.
  var rowById = {};
  var lastRow = sheet.getLastRow();
  if (lastRow > 1) {
    var ids = sheet.getRange(2, idCol, lastRow - 1, 1).getValues();
    for (var i = 0; i < ids.length; i++) {
      if (ids[i][0]) rowById[String(ids[i][0])] = i + 2;
    }
  }

  var written = 0;
  leads.forEach(function (lead) {
    var id = String(lead['Lead ID'] || '');
    if (!id) return;
    var rowNum = rowById[id];
    var values;
    if (rowNum) {
      // Keep any cells not sent this time (e.g. notes someone typed in an
      // extra column) and overwrite the rest.
      values = sheet.getRange(rowNum, 1, 1, headers.length).getValues()[0];
    } else {
      rowNum = sheet.getLastRow() + 1;
      rowById[id] = rowNum;
      values = headers.map(function () { return ''; });
    }
    headers.forEach(function (h, idx) {
      if (Object.prototype.hasOwnProperty.call(lead, h)) {
        values[idx] = lead[h] === null || lead[h] === undefined ? '' : String(lead[h]);
      }
    });
    var range = sheet.getRange(rowNum, 1, 1, headers.length);
    // Plain text: stops Sheets turning "+1 555..." phones or answers
    // starting with "=" into formulas.
    range.setNumberFormat('@');
    range.setValues([values]);
    written++;
  });
  return written;
}

function getSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(TAB_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(TAB_NAME);
  }
  return sheet;
}

// Makes sure every key in the incoming leads has a header column, adding
// new ones at the end. Returns the full header list.
function ensureHeaders_(sheet, leads) {
  var lastCol = sheet.getLastColumn();
  var headers = lastCol > 0
    ? sheet.getRange(1, 1, 1, lastCol).getValues()[0].map(String)
    : [];
  var added = false;
  leads.forEach(function (lead) {
    Object.keys(lead).forEach(function (key) {
      if (headers.indexOf(key) === -1) {
        headers.push(key);
        added = true;
      }
    });
  });
  if (added || lastCol === 0) {
    sheet.getRange(1, 1, 1, headers.length)
      .setValues([headers])
      .setFontWeight('bold')
      .setBackground('#36488F')
      .setFontColor('#FFFFFF');
    sheet.setFrozenRows(1);
  }
  return headers;
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
