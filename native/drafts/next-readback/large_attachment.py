"""Owned 64-MiB WebGL2 readback control, not a benchmark or capability admission."""

from __future__ import annotations

import asyncio
import math
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from app.core.native.identity import IDENTITY_FILE
from app.core.native.runtime import NativeRuntime
from scripts.verify_native_gpu_readback import READBACK_FEATURES, ReadbackConfiguration
from scripts.verify_native_surfaces import IDENTITY_ARGUMENT
from scripts.verify_native_worker_startup import FEATURE_ARGUMENT, browser_arguments, partitioning_argument

SAMPLE = (HERE / "large_attachment.js").read_text(encoding="utf-8-sig")


def validate(value: dict) -> None:
    if (not isinstance(value, dict) or type(value.get("size")) is not int
            or type(value.get("byteLength")) is not int
            or value["size"] != 4096 or value["byteLength"] != 67108864):
        raise ValueError("Large readback did not cover the exact 64-MiB attachment")
    if any(not isinstance(value.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", value[key])
           for key in ("cpuHash", "cpuRepeatHash", "pboHash")):
        raise ValueError("Incomplete large readback hashes")
    if value["cpuHash"] != value["cpuRepeatHash"] or value["cpuHash"] != value["pboHash"]:
        raise ValueError("Full CPU/PBO/repeated pixels disagree")
    expected_state = {"viewport": [0, 0, 2, 2], "framebuffer": True, "renderbuffer": True,
                      "packBound": False, "alignment": 4, "rowLength": 0, "skipRows": 0, "skipPixels": 0}
    if value.get("before") != expected_state or value.get("after") != expected_state:
        raise ValueError("Large readback changed GL bindings/pack/viewport state")
    for state in (value["before"], value["after"]):
        if (any(type(state[key]) is not type(expected) for key, expected in expected_state.items())
                or any(type(axis) is not int for axis in state["viewport"])):
            raise ValueError("Large readback GL state has invalid value types")
    pixels = value.get("cropFromFull")
    if not isinstance(pixels, list) or len(pixels) != 64 or any(type(byte) is not int or not 0 <= byte <= 255 for byte in pixels):
        raise ValueError("Incomplete full-frame crop reference")
    if not isinstance(value.get("crops"), list) or len(value["crops"]) != 3:
        raise ValueError("Three repeated crops are required")
    if any(not isinstance(crop, dict) or crop.get("pixels") != pixels
           or any(type(byte) is not int for byte in crop["pixels"]) for crop in value["crops"]):
        raise ValueError("Small crop differs from full attachment")
    if value.get("clipped") != [165] * 64:
        raise ValueError("Outside-only crop overwrote caller bytes")
    durations = [value.get("cpuMilliseconds"), value.get("pboMilliseconds"),
                 *(crop.get("milliseconds") for crop in value["crops"])]
    if any(type(duration) not in (int, float) or not 0 <= duration <= sys.float_info.max
           or not math.isfinite(duration) for duration in durations):
        raise ValueError("Readback timings are incomplete")


async def capture(executable: Path, owned: Path, server, report: dict, save) -> None:
    runtimes = []
    report.update(phases=[], privacy_admitted=False, production_admitted=False,
        scope="One owned document/WebGL2 RGBA8 renderbuffer, 4096x4096; CPU/PBO/crop consistency; loaded-host timings, not isolated latency or memory measurements")
    try:
        discovery = NativeRuntime(owned / "discovery", executable, ReadbackConfiguration())
        runtimes.append(discovery)
        context = await discovery.start(headless=True)
        arguments = await browser_arguments(context)
        replacement = partitioning_argument(arguments)
        original = next(argument for argument in arguments if argument.startswith("--disable-features="))
        await discovery.close()
        identities = {}
        for name, protected, phase in (("baseline", False, "initial"), ("profile-a", True, "initial"),
                                       ("profile-a", True, "restart"), ("profile-b", True, "initial")):
            configuration = ReadbackConfiguration(probe_mode="ready" if protected else "baseline",
                derivation_mode="profile-identity", disabled_features_argument=replacement,
                ignored_driver_argument=original)
            runtime = NativeRuntime(owned / name, executable, configuration)
            runtimes.append(runtime)
            try:
                context = await runtime.start(headless=True)
                effective = await browser_arguments(context)
                expected = FEATURE_ARGUMENT + ("," + READBACK_FEATURES if protected else "")
                if expected not in effective or partitioning_argument(effective) != replacement or original in effective:
                    raise ValueError("Readback feature/partitioning arguments differ from the explicit diagnostic")
                if protected and IDENTITY_ARGUMENT not in effective:
                    raise ValueError("Readback profile-identity derivation was not enabled")
                page = context.pages[0]
                await page.goto(f"http://127.0.0.1:{server.server_port}/", timeout=10000)
                identity = (runtime.profile_dir / IDENTITY_FILE).read_bytes()
                if name in identities and identities[name] != identity:
                    raise ValueError("Large readback restart changed the private identity")
                identities[name] = identity
                row = {"name": name, "phase": phase, "protected": protected, "passed": False}
                report["phases"].append(row)
                save()
                row["observed"] = await asyncio.wait_for(page.evaluate(SAMPLE), timeout=90)
                validate(row["observed"])
                row["passed"] = True
                save()
            finally:
                await runtime.close()
        if identities["profile-a"] == identities["profile-b"]:
            raise ValueError("Independent readback profiles share identity bytes")
        hashes = [row["observed"]["cpuHash"] for row in report["phases"]]
        report["protected_changed_from_baseline"] = hashes[0] != hashes[1] and hashes[0] != hashes[3]
        report["protected_restart_stable"] = hashes[1] == hashes[2]
        report["two_profiles_distinct"] = hashes[1] != hashes[3]
        report["measurement_complete"] = True
        report["passed"] = (report["protected_changed_from_baseline"] and report["protected_restart_stable"]
                            and report["two_profiles_distinct"])
    finally:
        for runtime in runtimes:
            if runtime.has_resources:
                await runtime.close()
        report["owned_runtimes_resource_free"] = not any(runtime.has_resources for runtime in runtimes)
        report["passed"] = report.get("passed", False) and report["owned_runtimes_resource_free"]
        save()
