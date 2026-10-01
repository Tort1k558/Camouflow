"""Bounded DOM extraction shared by AI tasks and deterministic scenarios."""

from __future__ import annotations

import csv
import io
import json

TABLE_SCRIPT = """table => {
    if (table.tagName !== 'TABLE') throw new Error('Select a HTML table');
    const rows = [...table.rows];
    if (rows.length > 201) throw new Error('Table exceeds 200 data rows');
    if (rows.some(row => [...row.cells].some(cell => cell.colSpan !== 1 || cell.rowSpan !== 1)))
        throw new Error('Merged table cells are not supported');
    const clean = cell => {
        const copy = cell.cloneNode(true);
        copy.querySelectorAll('input,textarea,[contenteditable],script,style').forEach(el => el.remove());
        return (copy.textContent || '').replace(/\\s+/g, ' ').trim();
    };
    const cells = rows.map(row => [...row.cells].map(clean));
    if (JSON.stringify(cells).length > 1024 * 1024) throw new Error('Table exceeds 1 MiB');
    return cells;
}"""


async def extract_table(locator) -> list[dict[str, str]]:
    cells = await locator.evaluate(TABLE_SCRIPT)
    if len(cells) < 2:
        raise ValueError("Table needs a header and at least one data row")
    headers = cells[0]
    if not 1 <= len(headers) <= 30:
        raise ValueError("Table must have 1-30 columns")
    if any(not name for name in headers) or len(set(headers)) != len(headers):
        raise ValueError("Table headers must be non-empty and unique")
    if any(len(row) != len(headers) for row in cells[1:]):
        raise ValueError("Merged or inconsistent table cells are not supported")
    result = [dict(zip(headers, row)) for row in cells[1:]]
    if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > 1024 * 1024:
        raise ValueError("Extracted table exceeds 1 MiB")
    return result


def table_csv(rows: list[dict]) -> str:
    if not rows:
        raise ValueError("No table rows to export")
    output = io.StringIO(newline="")
    headers = list(rows[0])
    writer = csv.writer(output)

    def safe_cell(value):
        text = str(value)
        return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text

    writer.writerow([safe_cell(header) for header in headers])
    for row in rows:
        if set(row) != set(headers):
            raise ValueError("CSV rows must have consistent columns")
        writer.writerow([safe_cell(row[header]) for header in headers])
    return output.getvalue()
