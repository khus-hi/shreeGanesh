/**
 * Paste this into your Google Sheet: Extensions -> Apps Script -> replace everything -> Save.
 * Then Deploy -> New deployment -> type "Web app" -> Execute as: Me, Who has access: Anyone -> Deploy.
 * Copy the Web app URL and save it as the GitHub secret SHEETS_WEBHOOK_URL.
 *
 * Every scanner run POSTs new jobs here. Newest jobs go to the top, new rows are highlighted,
 * and your own edits (like the Status column) are never touched.
 */
const SHEET_NAME = "Jobs";
const TOP_MATCH = 60;

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const data = JSON.parse(e.postData.contents);
    const cols = data.columns;
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let sh = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME, 0);

    if (sh.getLastRow() === 0) {
      sh.getRange(1, 1, 1, cols.length).setValues([cols])
        .setFontWeight("bold").setBackground("#1F3A6B").setFontColor("#FFFFFF");
      sh.setFrozenRows(1);
      const widths = {"Title": 320, "Company": 150, "Location": 200, "Matched Skills": 260,
                      "Missing Skills": 200, "URL": 260, "Found On": 130, "Status": 110};
      cols.forEach((c, i) => sh.setColumnWidth(i + 1, widths[c] || 95));
    }

    // skip jobs already in the sheet
    const urlCol = cols.indexOf("URL") + 1;
    const last = sh.getLastRow();
    const existing = new Set(last > 1 ? sh.getRange(2, urlCol, last - 1, 1).getValues().flat() : []);
    const rows = data.rows.filter(r => r[urlCol - 1] && !existing.has(r[urlCol - 1]));
    if (!rows.length) return json({added: 0});

    // clear the previous batch's highlight, then insert the new batch at the top
    if (last > 1) sh.getRange(2, 1, last - 1, cols.length).setBackground(null);
    sh.insertRowsBefore(2, rows.length);
    const range = sh.getRange(2, 1, rows.length, cols.length);
    range.setValues(rows).setBackground("#FFF2CC").setFontWeight("normal").setFontColor("#000000");

    const matchCol = cols.indexOf("Match %") + 1;
    const sponsorCol = cols.indexOf("Sponsorship") + 1;
    rows.forEach((r, i) => {
      if (matchCol && Number(r[matchCol - 1]) >= TOP_MATCH) sh.getRange(2 + i, matchCol).setBackground("#C6EFCE");
      if (sponsorCol && r[sponsorCol - 1] === "No") sh.getRange(2 + i, sponsorCol).setFontColor("#C00000").setFontWeight("bold");
    });

    if (!sh.getFilter()) sh.getRange(1, 1, sh.getMaxRows(), cols.length).createFilter();
    return json({added: rows.length});
  } finally {
    lock.releaseLock();
  }
}

function doGet() {
  return json({ok: true, message: "Job scanner sheet is connected."});
}

function json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
