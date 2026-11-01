"""Owned Audio completion/iframe lifecycle checks, not DSP or privacy admission."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import threading

from scripts import native_build as build
from scripts import verify_native_audio_compatibility as compatibility
from scripts.native_driver_stage import verify as verify_driver
from scripts.verify_native_privacy_units import require_idle_builder
from scripts.verify_native_surfaces import validate_receipt

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "native/fixtures/audio/lifecycle.js"
DRIVER_MANIFEST = ROOT / "native/drafts/environment/playwright-driver-stage-binding-close.json"
MODES = ("baseline", "legacy", "math")


def validate_lifecycle(value, mode):
    if type(mode) is not str or mode not in MODES:
        raise ValueError('Unknown lifecycle mode')
    if not isinstance(value, dict) or type(value.get('schema')) is not int or value['schema'] != 1 or value.get('mode') != mode or value.get('passed') is not True:
        raise ValueError('Lifecycle result did not pass')
    expected = set()
    for rate in (44100, 48000):
        expected.update(('event-promise', rate, frames, reenter, None) for frames in (128, 4096, 65536) for reenter in (False, True))
        expected.update((kind, rate, None, None, repetition) for kind in ('detach-pending', 'detach-in-completion') for repetition in range(3))
        if mode == 'legacy':
            expected.add(('budget-retry', rate, None, None, None))
    checks = {
        'event-promise': {'oneEvent', 'sameMutableBuffer', 'closed', 'format', 'sourceUnchanged', 'repeatRejected'},
        'detach-pending': {'noEventInObservationWindow', 'noFulfillmentInObservationWindow', 'frameRemoved'},
        'detach-in-completion': {'oneEvent', 'frameRemoved', 'retainedMutation', 'fulfilledBufferAgreesIfDelivered'},
        'budget-retry': {'allRejectBeforeRendering', 'contextStillSuspended'},
    }
    rows = value.get('rows')
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError('Incomplete lifecycle case coverage')
    seen = set()
    total = 0
    for row in rows:
        if not isinstance(row, dict) or row.get('passed') is not True or type(row.get('rate')) is not int:
            raise ValueError('Failed lifecycle row')
        kind = row.get('kind')
        if type(kind) is not str or kind not in checks:
            raise ValueError('Unknown lifecycle case')
        fields = {'kind', 'rate', 'passed', 'checks'}
        if kind == 'event-promise':
            fields.update({'frames', 'reenter'})
        elif kind in ('detach-pending', 'detach-in-completion'):
            fields.add('repetition')
        if set(row) != fields:
            raise ValueError('Unexpected lifecycle row fields')
        if kind == 'event-promise' and (type(row.get('frames')) is not int or type(row.get('reenter')) is not bool):
            raise ValueError('Malformed lifecycle event identity')
        if kind in ('detach-pending', 'detach-in-completion') and type(row.get('repetition')) is not int:
            raise ValueError('Malformed lifecycle detach identity')
        key = (kind, row.get('rate'), row.get('frames'), row.get('reenter'), row.get('repetition'))
        if key not in expected or key in seen:
            raise ValueError('Unexpected or duplicate lifecycle row')
        seen.add(key)
        observed = row.get('checks')
        if not isinstance(observed, dict) or set(observed) != checks[kind] or any(flag is not True for flag in observed.values()):
            raise ValueError('Incomplete or failed lifecycle checks')
        total += len(observed)
    return {'cases': len(expected), 'checks': total, 'pending_detach_window_ms': 150}


async def collect(context, server, mode: str) -> dict:
    result = {"passed": False, "probes": {"lifecycle": {"passed": False}}}
    check = result["probes"]["lifecycle"]

    async def route(request):
        if request.request.url.startswith(server.origin + "/"):
            await request.continue_()
        else:
            await request.abort("blockedbyclient")

    await context.route("**/*", route)
    try:
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(server.origin + "/audio", timeout=10000)
        observed = await asyncio.wait_for(page.evaluate(FIXTURE.read_text(encoding="utf-8"), {"mode": mode}), timeout=90)
        check["observed"] = observed
        check["coverage"] = validate_lifecycle(observed, mode)
        check["passed"] = result["passed"] = True
    except Exception as error:
        check.update(error_type=type(error).__name__, error=str(error))
    finally:
        try:
            await context.unroute("**/*", route)
        except Exception as error:
            result.update(passed=False, cleanup_error_type=type(error).__name__, cleanup_error=str(error))
    return result


def diagnostic_inputs(candidate: dict) -> set[Path]:
    return compatibility.probe_paths(candidate) | {Path(__file__).resolve(), FIXTURE, DRIVER_MANIFEST}


def verify(workspace: Path, executable: Path, owned: Path, *, candidate_name: str, driver_root: Path) -> dict:
    if sys.platform != "win32" or candidate_name not in build.CANDIDATES:
        raise ValueError("Audio lifecycle requires an explicit Windows Chromium 156 candidate")
    source = workspace / "chromium/src"
    if (workspace.drive.upper() != "D:" or workspace != workspace.resolve()
            or not workspace.is_dir()):
        raise ValueError("Select the canonical candidate workspace on D:")
    if (not executable.is_absolute() or executable.drive.upper() != "D:"
            or executable != executable.resolve() or not executable.is_file()
            or executable.is_relative_to(source) or executable.is_relative_to(ROOT)):
        raise ValueError("Use an independent canonical runtime on D:, not the writable build output")
    if (not owned.is_absolute() or owned.drive.upper() != "D:" or owned != owned.resolve()
            or owned.exists() or not owned.parent.is_dir() or owned.is_relative_to(workspace)
            or owned.is_relative_to(ROOT) or owned.is_relative_to(executable.parent)
            or owned.is_relative_to(driver_root)):
        raise ValueError("Select a fresh canonical evidence directory on D: outside runtime and source trees")
    if (not driver_root.is_absolute() or driver_root.drive.upper() != "D:"
            or driver_root != driver_root.resolve() or not driver_root.is_dir()
            or driver_root.is_relative_to(ROOT) or driver_root.is_relative_to(workspace)
            or driver_root.is_relative_to(executable.parent)):
        raise ValueError("Select the independent verified driver stage on D:")
    driver = verify_driver(driver_root, DRIVER_MANIFEST)
    spec = importlib.util.find_spec("playwright")
    if spec is None or spec.origin is None or Path(spec.origin).resolve() != driver_root / "playwright/__init__.py":
        raise ValueError("The active Playwright import must come from the explicit verified driver stage")
    candidate = build.load_candidate(candidate_name)
    if not any(row["file"] == "0067-native-audio-math-context-candidate.patch" for row in candidate["manifest"]["patches"]):
        raise ValueError("Audio lifecycle requires the selected AudioMath patch")
    build.candidate_workspace(workspace, candidate)
    with build.workspace_lock(workspace):
        require_idle_builder(workspace)
        owned.mkdir()
        report = dict(schema=1, passed=False, candidate=candidate_name, requested_modes=list(MODES),
            candidate_manifest_sha256=candidate["manifest_sha256"], modes={}, cleanup_errors=[],
            postguards_passed=False, native_seed_erasure_proven=False, legacy_audio_repaired=False,
            production_admitted=False,
            scope="Owned completion/iframe lifecycle only; 150ms pending-detach window, not all future scheduling, DSP fidelity, private-key erasure or privacy admission")
        server = thread = None
        core = receipt = files = inputs = None
        try:
            core = build.measure_runtime_core(executable)
            receipt = validate_receipt(executable, core, derivation_mode="profile-identity", candidate_name=candidate_name)
            files = diagnostic_inputs(candidate)
            inputs = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
            report.update(runtime_core_sha256_measured=core, receipt_sha256=hashlib.sha256(receipt).hexdigest(),
                measured_inputs_sha256={path.relative_to(ROOT).as_posix(): digest for path, digest in inputs.items()})
            server = compatibility.AudioFixtureServer(compatibility.fixture_sources())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            phases = iter(MODES)

            async def collector(context, fixture_server):
                return await collect(context, fixture_server, next(phases))

            asyncio.run(compatibility.measure_modes(executable, owned, server, MODES, report,
                candidate["lock"]["chromium_revision"], candidate["lock"]["chromium_version"], collector=collector))
            report["passed"] = set(report["modes"]) == set(MODES) and all(row["passed"] for row in report["modes"].values())
        except Exception as error:
            report.update(passed=False, error_type=type(error).__name__, error=str(error))
        finally:
            try:
                if server is not None:
                    if thread is not None and thread.is_alive():
                        server.shutdown()
                    server.server_close()
                if thread is not None:
                    thread.join(timeout=5)
                    if thread.is_alive():
                        raise RuntimeError("Owned Audio lifecycle server remains")
            except Exception as error:
                report["cleanup_errors"].append(dict(error_type=type(error).__name__, error=str(error)))
            if inputs is not None:
                try:
                    if (build.measure_runtime_core(executable) != core
                            or validate_receipt(executable, core, derivation_mode="profile-identity", candidate_name=candidate_name) != receipt
                            or diagnostic_inputs(candidate) != files
                            or any(not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest for path, digest in inputs.items())
                            or verify_driver(driver_root, DRIVER_MANIFEST) != driver):
                        raise ValueError("Runtime, receipt, driver or diagnostic inputs changed")
                    report["postguards_passed"] = True
                except Exception as error:
                    report.update(postguard_error_type=type(error).__name__, postguard_error=str(error))
            report["passed"] = report["passed"] and report["postguards_passed"] and not report["cleanup_errors"]
            (owned / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--driver-root", type=Path, required=True)
    parser.add_argument("--candidate", choices=build.CANDIDATES, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.driver_root))
    try:
        report = verify(args.workspace, args.executable, args.work_dir,
                        candidate_name=args.candidate, driver_root=args.driver_root)
    except Exception as error:
        print(f"Audio lifecycle verification failed ({type(error).__name__}): {error}", file=sys.stderr)
        return 1
    print(json.dumps(dict(passed=report["passed"], report=str(args.work_dir / "report.json"))))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
