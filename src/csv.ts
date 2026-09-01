/**
 * CSV cell sanitizer — neutralizes spreadsheet formula injection.
 * A value starting with =, +, -, @, tab or CR would execute as a formula
 * when the export is opened in Excel/Sheets, so we prefix a single quote.
 * Shared by every CSV generation site (server routes + storage exports).
 */
export function csvCell(value: any): string {
  if (value === null || value === undefined) return "";
  let s = String(value).replace(/"/g, '""');
  if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
  if (s.includes(",") || s.includes("\n") || s.includes('"')) s = `"${s}"`;
  return s;
}

/** Build a CSV document from a list of row objects (uniform headers). */
export function toCsv(rows: Record<string, any>[], headers?: string[]): string {
  if (!rows.length) return "";
  const cols = headers || Object.keys(rows[0]);
  const lines = [cols.map(csvCell).join(",")];
  for (const row of rows) {
    lines.push(cols.map((h) => csvCell(row[h])).join(","));
  }
  return lines.join("\n");
}
