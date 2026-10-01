"""Opt-in real provider smoke using only synthetic data and an isolated workspace."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import tempfile
from pathlib import Path


async def verify(engine, config, root, repeats):
    from app.core.browser_interface import BrowserInterface
    from app.services.ai_agent import templates
    from app.services.ai_agent.llm import LLMClient
    from app.services.ai_agent.loop import AgentSession, save_transcript
    from app.services.ai_agent.to_steps import compile_workflow
    from app.services.scenario_engine import ScenarioExecutor
    from app.storage import db

    db.init_db()
    server = templates.DemoServer()
    original_html = templates.DEMO_HTML
    runs = []
    try:
        for index in range(repeats):
            templates.DEMO_HTML = original_html
            browser = BrowserInterface(
                f"provider-{engine}-{index}",
                browser_engine=engine,
                browser_settings={"headless": True},
            )
            client = LLMClient(config)
            try:
                await browser.start()
                session = AgentSession(
                    browser.page,
                    client,
                    "Extract the catalog HTML table into the catalog output variable using table format. "
                    "Use the extract action, then report the row count with done. Do not change the page.",
                    start_url=server.url,
                    allowed_host="127.0.0.1",
                    max_steps=8,
                    session_timeout_s=180,
                )
                result = await session.run()
            finally:
                await browser.close(force=True)
            artifacts = root / "outputs" / "ai-runs" / f"{engine}-{index}"
            save_transcript(result, artifacts)
            row = {
                key: result[key]
                for key in (
                    "status",
                    "requests",
                    "prompt_tokens",
                    "completion_tokens",
                    "duration_s",
                )
            }
            row["artifacts"] = str(artifacts)
            rows = result.get("outputs", {}).get("catalog", [])
            row["extraction_passed"] = (
                result["status"] in {"done", "success"}
                and len(rows) == 3
                and rows[0]
                == {"Name": "Notebook", "Price": "12", "Link": "/products/notebook"}
                and rows[1]
                == {"Name": "Desk lamp", "Price": "34", "Link": "/products/lamp"}
                and rows[2]
                == {"Name": "Keyboard", "Price": "59", "Link": "/products/keyboard"}
            )
            row["replay_passed"] = False
            if row["extraction_passed"]:
                steps = compile_workflow(
                    result["steps"], {"catalog_url": server.url}, result["outputs"]
                )
                templates.DEMO_HTML = original_html.replace(
                    "Notebook", "Notebook updated"
                ).replace("<td>12</td>", "<td>17</td>")
                executor = ScenarioExecutor(
                    {
                        "name": f"replay-{engine}-{index}",
                        "_browser_engine": engine,
                        "_browser_settings": {"headless": True},
                        "extra_fields": {"catalog_url": server.url},
                    },
                    "",
                    db.Scenario("Real provider draft replay", steps),
                    keep_browser_open=False,
                )
                try:
                    await executor.start()
                    replay_ok = await executor.run()
                    actual = json.loads(executor.variables.get("catalog", "[]"))
                    row["replay_passed"] = bool(
                        replay_ok
                        and len(actual) == 3
                        and actual[0]["Name"] == "Notebook updated"
                        and actual[0]["Price"] == "17"
                    )
                finally:
                    await executor.close(force=True)
            runs.append(row)
            if not row["extraction_passed"] or not row["replay_passed"]:
                break
    finally:
        templates.DEMO_HTML = original_html
        server.close()
    return {
        "passed": len(runs) == repeats
        and all(r["extraction_passed"] and r["replay_passed"] for r in runs),
        "engine": engine,
        "model": config.model,
        "data_root": str(root),
        "runs": runs,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings-file", required=True, type=Path)
    parser.add_argument("--engine", choices=("camoufox", "cloakbrowser"), required=True)
    parser.add_argument("--repeats", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    settings = json.loads(args.settings_file.read_text(encoding="utf-8-sig"))
    root = Path(tempfile.mkdtemp(prefix="camouflow-real-provider-"))
    os.environ["CAMOUFLOW_DATA_DIR"] = str(root)
    from app.services.ai_agent.llm import LLMConfig

    config = LLMConfig(
        base_url=str(settings.get("ai_base_url") or ""),
        api_key=str(settings.get("ai_api_key") or ""),
        model=str(settings.get("ai_model") or ""),
    )
    if not config.base_url or not config.model:
        raise SystemExit("AI base URL/model are not configured")
    try:
        report = asyncio.run(verify(args.engine, config, root, args.repeats))
    except Exception:
        # Provider error messages can echo request credentials. Keep the public report generic.
        report = {
            "passed": False,
            "engine": args.engine,
            "model": config.model,
            "data_root": str(root),
            "error": "Verification failed; inspect the isolated transcript",
        }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
