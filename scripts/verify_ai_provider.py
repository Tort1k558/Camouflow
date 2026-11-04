"""Opt-in real provider smoke using only synthetic data and an isolated workspace."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

async def verify(engine, config, root, repeats, browser_settings=None):
    from app.core.browser_interface import BrowserInterface
    from app.services.ai_agent import templates
    from app.services.ai_agent.llm import LLMClient
    from app.services.ai_agent.loop import AgentSession, save_transcript
    from app.services.ai_agent.to_steps import compile_workflow
    from app.services.scenario_engine import ScenarioExecutor
    from app.storage import db

    browser_settings = {"headless": True, **(browser_settings or {})}
    if engine == "native":
        if db.DATA_ROOT.resolve() != root.resolve() or db.ACCOUNTS_FILE.exists() or db.SETTINGS_FILE.exists():
            raise ValueError("Native provider verification requires fresh isolated application storage")
        for directory in (db.SETTINGS_DIR, db.PROFILES_DIR, db.SCENARIOS_DIR, db.OUTPUTS_DIR):
            directory.mkdir(parents=True, exist_ok=True)
        db.ACCOUNTS_FILE.write_text("[]\n", encoding="utf-8")
        db.SETTINGS_FILE.write_text("{}\n", encoding="utf-8")
    else:
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
                browser_settings=dict(browser_settings),
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
            if config.api_key:
                result = {**result, "redactions": [*result.get("redactions", []), config.api_key]}
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
                        "_browser_settings": dict(browser_settings),
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


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings-file", required=True, type=Path)
    parser.add_argument("--engine", choices=("camoufox", "cloakbrowser", "native"), required=True)
    parser.add_argument("--repeats", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--native-executable", type=Path)
    parser.add_argument("--work-dir", type=Path)
    from scripts.verify_ai_workflows import validate_browser_paths

    args = validate_browser_paths(parser.parse_args(argv), parser)
    if args.engine == "native" and (
            not args.report.is_absolute() or args.report != args.report.resolve()
            or args.report.exists() or not args.report.is_relative_to(args.work_dir)):
        parser.error("Native report must be a new canonical path inside --work-dir")
    return args


def main():
    args = parse_args()
    settings = json.loads(args.settings_file.read_text(encoding="utf-8-sig"))
    root = args.work_dir or Path(tempfile.mkdtemp(prefix="camouflow-real-provider-"))
    os.environ["CAMOUFLOW_DATA_DIR"] = str(root)
    from app.services.ai_agent.llm import LLMConfig

    config = LLMConfig(
        base_url=str(settings.get("ai_base_url") or ""),
        api_key=str(settings.get("ai_api_key") or ""),
        model=str(settings.get("ai_model") or ""),
    )
    if not config.base_url or not config.model:
        raise SystemExit("AI base URL/model are not configured")
    phase = "native-preflight" if args.engine == "native" else "provider-workflow"
    try:
        browser_settings = {"headless": True}
        if args.engine == "native":
            from scripts.verify_native_privacy_units import require_idle_builder
            from scripts.verify_native_runtime import measure_runtime_core

            require_idle_builder(args.native_executable.parent)
            core_before = measure_runtime_core(args.native_executable)
            browser_settings["executable_path"] = str(args.native_executable)
        if args.work_dir is not None:
            root.mkdir()
        phase = "provider-workflow"
        report = asyncio.run(verify(args.engine, config, root, args.repeats, browser_settings))
        if args.engine == "native":
            phase = "native-postguards"
            unchanged = measure_runtime_core(args.native_executable) == core_before
            report.update(executable=str(args.native_executable), runtime_core_sha256_measured=core_before,
                          runtime_core_unchanged=unchanged, privacy_admitted=False,
                          scope="Configured provider extraction/replay only; not native fingerprint or release admission")
            report["passed"] = report["passed"] and unchanged
    except Exception:
        # Provider error messages can echo request credentials. Keep the public report generic.
        report = {
            "passed": False,
            "engine": args.engine,
            "model": config.model,
            "data_root": str(root),
            "error": "Verification failed; inspect the isolated transcript",
            "failed_phase": phase,
        }
    if args.engine == "native" and args.report.exists():
        raise FileExistsError("Refusing to overwrite existing Native verification evidence")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
