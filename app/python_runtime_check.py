"""Opt-in packaged Python runtime checks; initialize data paths before service imports."""

import json
import os
import threading
from pathlib import Path


def check_runtime(engine, report_path):
    """Opt-in packaged diagnostic with fixed code and disposable profile data."""
    import tempfile
    if engine not in {"camoufox", "cloakbrowser"}:
        raise ValueError("Choose camoufox or cloakbrowser")
    report = Path(report_path).resolve()
    results = []
    directory = tempfile.mkdtemp(prefix="camouflow-python-runtime-")
    previous_root = os.environ.get("CAMOUFLOW_DATA_DIR")
    try:
        os.environ["CAMOUFLOW_DATA_DIR"] = directory
        from app.storage import db
        from app.services.scenario_worker import run_worker
        db.init_db()
        account = {"name": "runtime-check", "_browser_engine": engine,
                   "camoufox_settings": {"headless": True}, "cloakbrowser_settings": {"headless": True}}
        code = ('async def main(ctx):\n'
                '    import asyncio, csv, datetime, json, math, pathlib, re\n'
                '    await ctx.page.goto("data:text/html,<h1>Runtime check</h1>")\n'
                '    text = await ctx.page.locator("h1").inner_text()\n'
                '    assert text == "Runtime check"\n'
                '    return {"text": text, "sqrt": math.sqrt(9)}\n')
        for name, source, expected in [("browser-and-imports", code, "success"),
                                        ("hard-timeout", "async def main(ctx):\n    while True:\n        pass\n", "failed")]:
            job = {"scenario": name, "library": {}, "steps": [
                {"action": "start"}, {"action": "python", "script_api_version": 1,
                 "code": source, "timeout_ms": 3000}]}
            result = run_worker(account, job, threading.Event())
            passed = result["status"] == expected and (name != "hard-timeout" or result["error"] == "Python timeout")
            results.append({"name": name, "passed": passed, "status": result["status"], "error": result["error"]})
    except Exception as exc:
        results.append({"name": "runtime", "passed": False, "error": str(exc)})
    finally:
        if previous_root is None:
            os.environ.pop("CAMOUFLOW_DATA_DIR", None)
        else:
            os.environ["CAMOUFLOW_DATA_DIR"] = previous_root
    passed = bool(results) and all(result["passed"] for result in results)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"passed": passed, "engine": engine, "data_directory": directory, "checks": results}, indent=2), encoding="utf-8")
    return 0 if passed else 1

