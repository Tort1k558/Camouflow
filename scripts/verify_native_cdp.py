"""Verify Error preview side effects and intact native stack traces, not CDP invisibility."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright  # noqa: E402

COUNTERS = ("ownStack", "inheritedStack", "inheritedName", "inheritedMessage")
SETUP = """() => {
  globalThis.__ownedHits = {ownStack: 0, inheritedStack: 0, inheritedName: 0, inheritedMessage: 0};
  globalThis.__ownedErrors = [];
  for (const [label, property, inherited] of [
      ['ownStack', 'stack', false], ['inheritedStack', 'stack', true],
      ['inheritedName', 'name', true], ['inheritedMessage', 'message', true]]) {
    const error = new Error('Owned CDP fixture');
    if (inherited) delete error[property];
    const target = inherited ? Object.create(Error.prototype) : error;
    Object.defineProperty(target, property, {configurable: true, get() {
      globalThis.__ownedHits[label]++; return 'Owned ' + label;
    }});
    if (inherited) Object.setPrototypeOf(error, target);
    globalThis.__ownedErrors.push({label, error});
  }
  function ownedNativePlainError() { return new Error('Owned normal preview'); }
  globalThis.__ownedPlainError = ownedNativePlainError();
  globalThis.__ownedPlainStack = globalThis.__ownedPlainError.stack;
}"""


def validate_observation(observed: dict) -> None:
    hits, controls = observed["serialization_hits"], observed["explicit_read_controls"]
    if set(hits) != set(COUNTERS) or set(controls) != set(COUNTERS):
        raise ValueError("All four Error accessor fixtures must be observed")
    if any(type(values[key]) is not int or values[key] < 0 for values in (hits, controls) for key in COUNTERS):
        raise ValueError("Invalid Error accessor counters")
    if observed["console_events"] != 5:
        raise ValueError("All five native console events must be observed")
    expected = observed["expected_native_preview"]
    if not isinstance(expected, str) or "Owned normal preview" not in expected or "ownedNativePlainError" not in expected:
        raise ValueError("A genuine native Error message and stack trace are required")
    if observed["native_preview"] != expected:
        raise ValueError("Native Error message or stack trace was changed")
    if any(controls[key] != hits[key] + 1 for key in COUNTERS):
        raise ValueError("Explicit accessor reads did not prove the counters work")
    if any(hits.values()):
        raise ValueError("CDP Error serialization invoked custom JavaScript accessors")


async def verify(executable: Path, work_dir: Path, checks: list) -> dict:
    async with async_playwright() as driver:
        with tempfile.TemporaryDirectory(prefix="native-cdp-", dir=work_dir) as owned:
            context = await driver.chromium.launch_persistent_context(
                owned, executable_path=str(executable), headless=True, chromium_sandbox=True)
            try:
                version = context.browser.version
                page = context.pages[0]
                session = await context.new_cdp_session(page)
                await session.send("Runtime.enable")
                events = []
                ready = asyncio.Event()
                def capture(event):
                    events.append(event["args"][0].get("description"))
                    if len(events) >= 5:
                        ready.set()
                session.on("Runtime.consoleAPICalled", capture)
                await page.evaluate(SETUP)
                await page.evaluate("() => { for (const {error} of globalThis.__ownedErrors) console.debug(error); console.debug(globalThis.__ownedPlainError); }")
                await asyncio.wait_for(ready.wait(), timeout=10)
                hits = await page.evaluate("() => ({...globalThis.__ownedHits})")
                await page.evaluate("() => { for (const {label,error} of globalThis.__ownedErrors) Reflect.get(error, label.includes('Stack') ? 'stack' : label.includes('Name') ? 'name' : 'message'); }")
                controls = await page.evaluate("() => ({...globalThis.__ownedHits})")
                expected = await page.evaluate("() => globalThis.__ownedPlainStack")
                observed = {"serialization_hits": hits, "explicit_read_controls": controls,
                            "console_events": len(events), "native_preview": events[-1], "expected_native_preview": expected}
                checks.extend([
                    {"name": "console-events", "passed": len(events) == 5},
                    {"name": "native-message-and-stack-preserved", "passed": events[-1] == expected},
                    {"name": "explicit-accessor-read-controls", "passed": all(controls[key] == hits[key] + 1 for key in COUNTERS)},
                    {"name": "custom-error-accessors-not-invoked", "observed": observed, "passed": False},
                ])
                validate_observation(observed)
                checks[-1]["passed"] = True
                await session.detach()
            finally:
                await context.close()
    with executable.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"passed": True, "platform": platform.system(), "version": version,
            "binary_sha256_measured": checksum, "checks": checks,
            "scope": "Owned Error accessor side effects and normal error previews; not general CDP invisibility or CAPTCHA resistance"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    checks = []
    try:
        args.work_dir.mkdir(parents=True, exist_ok=True)
        report = asyncio.run(verify(args.executable.resolve(), args.work_dir, checks))
    except Exception as error:
        report = {"passed": False, "platform": platform.system(), "checks": checks,
                  "error_type": type(error).__name__, "error": str(error)}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
