"""Opt-in packaged Python runtime checks; initialize data paths before service imports."""

import json
import os
import threading
from pathlib import Path


def check_runtime(engine, report_path, *, native_store=None):
    """Opt-in packaged diagnostic with fixed code and disposable profile data."""
    import tempfile
    if engine not in {"camoufox", "cloakbrowser", "native"}:
        raise ValueError("Choose camoufox, cloakbrowser or native")
    if (engine == "native") != (native_store is not None):
        raise ValueError("Native runtime checks require an explicit managed binary store")
    report = Path(report_path).resolve()
    if engine == "native":
        store_path = Path(native_store)
        if not store_path.is_absolute() or store_path != store_path.resolve() or not store_path.is_dir():
            raise ValueError("Native managed store must be an existing canonical absolute directory")
        if report.is_relative_to(store_path):
            raise ValueError("Native runtime evidence must stay outside the binary store")
    if engine == "native" and report.exists():
        raise ValueError("Refusing to overwrite Native packaged runtime evidence")
    report.parent.mkdir(parents=True, exist_ok=True)
    results = []
    directory = tempfile.mkdtemp(prefix="camouflow-python-runtime-", dir=report.parent if engine == "native" else None)
    previous_root = os.environ.get("CAMOUFLOW_DATA_DIR")
    try:
        os.environ["CAMOUFLOW_DATA_DIR"] = directory
        from app.storage import db
        from app.services.scenario_worker import run_worker
        db.init_db()
        account = {"name": "runtime-check", "_browser_engine": engine,
                   "camoufox_settings": {"headless": True}, "cloakbrowser_settings": {"headless": True}}
        if engine == "native":
            import asyncio
            from dataclasses import asdict
            from app.core.native.configuration import NativeConfiguration
            from app.core.native.distribution import NativeBinaryStore
            from app.core.native.health import probe_native_profile
            from app.core.native.privacy import NativePrivacyPolicy

            store = NativeBinaryStore(Path(native_store))
            release = store.resolve_active()
            policy = NativePrivacyPolicy(cpu_limit=4, memory_limit=4, fonts=("Arial", "Segoe UI", "Tahoma"),
                                         restrict_webrtc=True, conceal_automation=True, native_user_agent=True,
                                         font_rasterization="grayscale")
            account["native_settings"] = {"binary_source": "managed", "binary_store": str(store.root),
                                          "headless": True, "humanize": False, "privacy_policy": asdict(policy)}
            observed = asyncio.run(probe_native_profile(Path(release["executable_path"]),
                NativeConfiguration(privacy_policy=policy), Path(directory) / "health"))
            if observed["mismatches"] or observed["native_patch_capabilities"] != policy.required_capabilities():
                raise ValueError("Packaged Native health did not confirm the admitted policy")
            results.append({"name": "native-policy-health", "passed": True,
                            "release_sha256": release["release_sha256"],
                            "capabilities": observed["native_patch_capabilities"]})
        native_assertions = (
            '    values = await ctx.page.evaluate("() => ({cpu:navigator.hardwareConcurrency,webdriver:navigator.webdriver,ua:navigator.userAgent})")\n'
            '    assert 0 < values["cpu"] <= 4 and values["webdriver"] is False\n'
            '    assert "HeadlessChrome" not in values["ua"]\n' if engine == "native" else '')
        code = ('async def main(ctx):\n'
                '    import asyncio, csv, datetime, json, math, pathlib, re\n'
                '    await ctx.page.goto("data:text/html,<h1>Runtime check</h1>")\n'
                '    text = await ctx.page.locator("h1").inner_text()\n'
                '    assert text == "Runtime check"\n'
                + native_assertions + '    return {"text": text, "sqrt": math.sqrt(9)}\n')
        for name, source, expected, timeout_ms in [("browser-and-imports", code, "success", 15000),
                                        ("hard-timeout", "async def main(ctx):\n    while True:\n        pass\n", "failed", 3000)]:
            job = {"scenario": name, "library": {}, "steps": [
                {"action": "start"}, {"action": "python", "script_api_version": 1,
                 "code": source, "timeout_ms": timeout_ms}]}
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

