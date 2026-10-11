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

COUNTERS = ("ownStack", "inheritedStack", "ownName", "inheritedName", "ownMessage", "inheritedMessage")
ERROR_TYPES = ("Error", "TypeError", "RangeError", "SyntaxError", "ReferenceError", "URIError", "EvalError")
SETUP = """() => {
  globalThis.__ownedHits = {ownStack: 0, inheritedStack: 0, ownName: 0, inheritedName: 0, ownMessage: 0, inheritedMessage: 0};
  globalThis.__ownedErrors = [];
  for (const [label, property, inherited] of [
      ['ownStack', 'stack', false], ['inheritedStack', 'stack', true],
      ['ownName', 'name', false], ['inheritedName', 'name', true],
      ['ownMessage', 'message', false], ['inheritedMessage', 'message', true]]) {
    const error = new Error('Owned CDP fixture');
    if (inherited) delete error[property];
    const target = inherited ? Object.create(Error.prototype) : error;
    Object.defineProperty(target, property, {configurable: true, get() {
      globalThis.__ownedHits[label]++; return 'Owned ' + label;
    }});
    if (inherited) Object.setPrototypeOf(error, target);
    globalThis.__ownedErrors.push({label, error});
  }
  function ownedNativePlainError(Constructor) { return new Constructor('Owned normal preview'); }
  globalThis.__ownedPlainErrors = [Error, TypeError, RangeError, SyntaxError, ReferenceError, URIError, EvalError]
    .map(Constructor => {
      const error = ownedNativePlainError(Constructor);
      return {type: Constructor.name, error, stack: error.stack};
    });
}"""


def native_previews_preserved(observed: dict) -> bool:
    previews, expected = observed["native_previews"], observed["expected_native_previews"]
    return (set(previews) == set(ERROR_TYPES) and set(expected) == set(ERROR_TYPES)
            and all(isinstance(expected[name], str)
                    and expected[name].startswith(name + ": Owned normal preview\n")
                    and "ownedNativePlainError" in expected[name]
                    and previews[name] == expected[name] for name in ERROR_TYPES))


def validate_observation(observed: dict) -> None:
    hits, controls = observed["serialization_hits"], observed["explicit_read_controls"]
    if set(hits) != set(COUNTERS) or set(controls) != set(COUNTERS):
        raise ValueError("All six Error accessor fixtures must be observed")
    if any(type(values[key]) is not int or values[key] < 0 for values in (hits, controls) for key in COUNTERS):
        raise ValueError("Invalid Error accessor counters")
    if observed["console_events"] != len(COUNTERS) + len(ERROR_TYPES):
        raise ValueError("All native console events must be observed")
    if not native_previews_preserved(observed):
        raise ValueError("Genuine native messages and stack traces of all Error types must be preserved")
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
                    if len(events) >= len(COUNTERS) + len(ERROR_TYPES):
                        ready.set()
                session.on("Runtime.consoleAPICalled", capture)
                await page.evaluate(SETUP)
                await page.evaluate("() => { for (const {error} of [...globalThis.__ownedErrors, ...globalThis.__ownedPlainErrors]) console.debug(error); }")
                await asyncio.wait_for(ready.wait(), timeout=10)
                hits = await page.evaluate("() => ({...globalThis.__ownedHits})")
                await page.evaluate("() => { for (const {label,error} of globalThis.__ownedErrors) Reflect.get(error, label.includes('Stack') ? 'stack' : label.includes('Name') ? 'name' : 'message'); }")
                controls = await page.evaluate("() => ({...globalThis.__ownedHits})")
                expected = await page.evaluate("() => Object.fromEntries(globalThis.__ownedPlainErrors.map(({type,stack}) => [type,stack]))")
                observed = {"serialization_hits": hits, "explicit_read_controls": controls,
                            "console_events": len(events), "native_previews": dict(zip(ERROR_TYPES, events[len(COUNTERS):])),
                            "expected_native_previews": expected}
                checks.extend([
                    {"name": "console-events", "passed": len(events) == len(COUNTERS) + len(ERROR_TYPES)},
                    {"name": "native-message-and-stack-preserved", "passed": native_previews_preserved(observed)},
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
