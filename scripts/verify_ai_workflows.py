"""Real-browser AI extraction -> parameterized replay smoke; local fixture LLM only."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def main():
    engine = sys.argv[1] if len(sys.argv) > 1 else "camoufox"
    root = Path(tempfile.mkdtemp(prefix="camouflow-ai-workflow-"))
    os.environ["CAMOUFLOW_DATA_DIR"] = str(root)
    from app.core.browser_interface import BrowserInterface
    from app.services.ai_agent.llm import LLMClient, LLMConfig
    from app.services.ai_agent.loop import AgentSession, DOM_JS_PATH, save_transcript
    from app.services.ai_agent.templates import DEMO_HTML
    from app.services.ai_agent.to_steps import compile_workflow
    from app.services.scenario_engine import ScenarioExecutor
    from app.storage import db

    db.init_db()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            html = DEMO_HTML.replace(
                "Notebook", "Notebook v2" if "v2" in self.path else "Notebook"
            )
            html += '<table data-testid="private"><tr><th>Label</th></tr><tr><td>Public<textarea>PRIVATE-EDITABLE</textarea></td></tr></table>'
            if self.path == "/scroll":
                html = '<h1>Top</h1><div style="height:1500px"></div><p>Middle target</p><div style="height:1500px"></div><p>Bottom</p>'
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert "PRIVATE-EDITABLE" not in json.dumps(body)
            observation = body["messages"][-1]["content"]
            if any(
                message["content"].startswith("EXTRACTED DATA:")
                for message in body["messages"]
            ):
                action = {
                    "name": "done",
                    "status": "success",
                    "result": "3 catalog rows extracted",
                }
            else:
                index = int(re.search(r"^(\d+) table", observation, re.MULTILINE)[1])
                action = {
                    "name": "extract",
                    "index": index,
                    "variable": "catalog",
                    "format": "table",
                }
            response = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"thought": "Read catalog", "action": action}
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/catalog"

    async def run():
        browser = BrowserInterface(
            "ai-source", browser_engine=engine, browser_settings={"headless": True}
        )
        try:
            await browser.start()
            client = LLMClient(
                LLMConfig(
                    base_url=url.rsplit("/", 1)[0] + "/v1", api_key="", model="fixture"
                )
            )
            session = AgentSession(
                browser.page,
                client,
                "Extract catalog",
                start_url=url,
                allowed_host="127.0.0.1",
            )
            result = await session.run()
            assert result["status"] == "success", result
            assert len(result["outputs"]["catalog"]) == 3
            assert result["requests"] == 2 and result["prompt_tokens"] == 200
            transcript = save_transcript(result, root / "outputs" / "ai-runs" / "smoke")
            assert "PRIVATE-EDITABLE" not in transcript.read_text(encoding="utf-8")
            snapshot = await browser.page.evaluate(
                DOM_JS_PATH.read_text(encoding="utf-8")
            )
            assert "PRIVATE-EDITABLE" not in json.dumps(snapshot)
            for element in snapshot["elements"]:
                assert await browser.page.locator(element["selector"]).count() == 1
            await browser.page.goto(
                url.rsplit("/", 1)[0] + "/scroll", wait_until="domcontentloaded"
            )
            await browser.page.locator("p").first.scroll_into_view_if_needed()
            snapshot = await browser.page.evaluate(
                DOM_JS_PATH.read_text(encoding="utf-8")
            )
            assert "Middle target" in snapshot["text"]
        finally:
            await browser.close(force=True)
        steps = compile_workflow(
            result["steps"], {"catalog_url": url}, result["outputs"]
        )
        scenario = db.Scenario("AI extraction replay", steps)
        account = {
            "name": "ai-replay",
            "_browser_engine": engine,
            "_browser_settings": {"headless": True},
            "extra_fields": {"catalog_url": url + "?v2"},
        }
        executor = ScenarioExecutor(account, "", scenario, keep_browser_open=False)
        try:
            await executor.start()
            assert await executor.run()
            rows = json.loads(executor.variables["catalog"])
            assert rows[0]["Name"] == "Notebook v2", rows
            exported = list((root / "outputs" / "ai-results").rglob("*.json"))
            assert (
                len(exported) == 1
                and json.loads(exported[0].read_text(encoding="utf-8")) == rows
            )
        finally:
            await executor.close(force=True)
        db.db_add_account(
            {
                "name": "cli-smoke",
                "browser_engine": engine,
                f"{engine}_settings": {"headless": True},
                "extra_fields": {"catalog_url": url + "?v2"},
            }
        )
        db.db_save_scenario(scenario.name, steps, "Synthetic extraction smoke")

    try:
        asyncio.run(run())
        import subprocess

        process = subprocess.run(
            [
                sys.executable,
                "main.py",
                "--cli",
                "run",
                "--scenario",
                "AI extraction replay",
                "--profile",
                "cli-smoke",
                "--confirm",
                "--timeout",
                "90",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        assert process.returncode == 0, process.stdout + process.stderr
        assert json.loads(process.stdout)["run"]["status"] == "success"
        mcp_python = os.environ.get("CAMOUFLOW_MCP_PYTHON")
        if mcp_python:
            subprocess.run(
                [
                    mcp_python,
                    "integrations/verify_mcp.py",
                    "--python",
                    sys.executable,
                    "--data-dir",
                    str(root),
                    "--scenario",
                    "AI extraction replay",
                    "--profile",
                    "cli-smoke",
                ],
                check=True,
                timeout=180,
            )
        print(
            json.dumps(
                {
                    "passed": True,
                    "engine": engine,
                    "data_root": str(root),
                    "checks": [
                        "fixture HTTP LLM",
                        "structured extraction",
                        "editable privacy",
                        "unique selectors",
                        "viewport scrolling",
                        "parameterized fresh replay",
                        "JSON artifact",
                        "CLI queue run",
                    ],
                }
            )
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    main()
