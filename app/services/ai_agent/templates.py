"""Reviewed local starters; no accounts, credentials or executable code."""

from __future__ import annotations

import copy
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TEMPLATES = {
    "catalog": {
        "name": "Catalog to JSON",
        "description": "Set catalog_url in profile variables. Extracts a HTML table with unique headers; exports JSON.",
        "steps": [
            {"action": "start", "_required_inputs": ["catalog_url"]},
            {"action": "goto", "value": "{{catalog_url}}"},
            {"action": "wait_element", "selector": "table", "timeout_ms": 15000},
            {
                "action": "extract_text",
                "selector": "table",
                "format": "table",
                "to_var": "catalog",
                "require_nonempty": True,
            },
            {
                "action": "write_file",
                "filename": "catalog-{{timestamp}}.json",
                "value": "{{catalog}}",
            },
        ],
    },
    "report": {
        "name": "Page to text report",
        "description": "Set page_url. Extracts non-editable page text into a timestamped report; one URL per run.",
        "steps": [
            {"action": "start", "_required_inputs": ["page_url"]},
            {"action": "goto", "value": "{{page_url}}"},
            {
                "action": "extract_text",
                "selector": "body",
                "to_var": "page_text",
                "exclude_editable": True,
                "require_nonempty": True,
            },
            {
                "action": "write_file",
                "filename": "page-{{timestamp}}.txt",
                "value": "{{page_text}}",
            },
        ],
    },
    "form": {
        "name": "Fill form without submitting",
        "description": "Set form_url, field_selector and field_value. Stops after filling; no submission. Review the destination first.",
        "steps": [
            {
                "action": "start",
                "_required_inputs": ["form_url", "field_selector", "field_value"],
            },
            {"action": "goto", "value": "{{form_url}}"},
            {
                "action": "type",
                "selector": "{{field_selector}}",
                "value": "{{field_value}}",
                "clear": True,
            },
            {
                "action": "log",
                "message": "Form filled. Review manually; nothing was submitted.",
            },
        ],
    },
}


def template(key: str) -> dict:
    if key not in TEMPLATES:
        raise ValueError("Unknown starter template")
    result = copy.deepcopy(TEMPLATES[key])
    for index, step in enumerate(result["steps"]):
        step["tag"] = "Start" if index == 0 else f"Step{index}"
    return result


DEMO_HTML = """<!doctype html><meta charset="utf-8"><title>CamouFlow demo catalog</title>
<style>body{font:16px system-ui;max-width:900px;margin:50px auto;color:#222e25;background:#f5f5ef}
table{border-collapse:collapse;width:100%;background:white}th,td{padding:18px;border:1px solid #d6ddcc;text-align:left}</style>
<h1>Demo catalog</h1><p>Synthetic data. No login, payments or external requests.</p>
<table data-testid="catalog"><thead><tr><th>Name</th><th>Price</th><th>Link</th></tr></thead><tbody>
<tr><td>Notebook</td><td>12</td><td>/products/notebook</td></tr>
<tr><td>Desk lamp</td><td>34</td><td>/products/lamp</td></tr>
<tr><td>Keyboard</td><td>59</td><td>/products/keyboard</td></tr>
</tbody></table><p>Ask the assistant to extract this table into the catalog variable.</p>"""


class DemoServer:
    def __init__(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/catalog":
                    self.send_error(404)
                    return
                body = DEMO_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'none'; style-src 'unsafe-inline'",
                )
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True, name="ai-demo"
        )
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/catalog"

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
