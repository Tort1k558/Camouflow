"""Owned default-RGBA8 WebGL isolation and PNG gate; not full GPU admission."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import platform
import shutil
import sys
import tempfile
import threading
import traceback
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt6.QtGui import QImage

from app.core.native.runtime import NativeRuntime
from scripts.verify_native_canvas import CONTEXTS, observe
from scripts.verify_native_gpu import (
    GPU_READ,
    SHADER_PIXELS,
    GpuFixtureHandler,
    validate_observations,
    validate_shader_readback,
)
from scripts.verify_native_runtime import FixtureServer, measure_runtime_core
from scripts.verify_native_surfaces import SAME_PARTITION, SurfaceConfiguration
from scripts.verify_native_surfaces import validate_receipt as validate_surface_receipt
from scripts.verify_native_worker_startup import (
    FEATURE_ARGUMENT,
    browser_arguments,
    partitioning_argument,
)

READBACK_FEATURE = "GlintWebGLReadbackCandidate"
GPU_PATCH = "0034-native-gpu-metadata-minimization.patch"
# Decode outside the browser: a 2D getImageData read would apply the Canvas seed
# a second time and hide or fabricate WebGL/PNG domain consistency.
READBACK_READ = GPU_READ.replace(
    "{antialias: false}", "{antialias: false, preserveDrawingBuffer: true}").replace(
    "      scene = {pixels:", "      const state = () => ({alignment: gl.getParameter(gl.PACK_ALIGNMENT),\n"
    "        framebuffer: gl.getParameter(gl.FRAMEBUFFER_BINDING) === null,\n"
    "        rowLength: name === 'webgl2' ? gl.getParameter(gl.PACK_ROW_LENGTH) : 0,\n"
    "        skipRows: name === 'webgl2' ? gl.getParameter(gl.PACK_SKIP_ROWS) : 0,\n"
    "        skipPixels: name === 'webgl2' ? gl.getParameter(gl.PACK_SKIP_PIXELS) : 0,\n"
    "        packBound: name === 'webgl2' ? gl.getParameter(gl.PIXEL_PACK_BUFFER_BINDING) !== null : false});\n"
    "      const beforeExport = state();\n      scene = {pixels:").replace(
    "    } finally {\n      if (name === 'webgl2') {",
    "      scene.packState = state();\n"
    "      const blob = await canvas.convertToBlob({type: 'image/png'});\n"
    "      scene.png = Array.from(new Uint8Array(await blob.arrayBuffer()));\n"
    "      scene.exportState = state();\n"
    "      scene.initialState = beforeExport;\n"
    "    } finally {\n      if (name === 'webgl2') {")


class ReadbackFixtureHandler(GpuFixtureHandler):
    worker_read = READBACK_READ


@dataclass(frozen=True)
class ReadbackConfiguration(SurfaceConfiguration):
    def launch_arguments(self) -> list[str]:
        arguments = super().launch_arguments()
        if self.probe_mode == "ready":
            arguments = [argument + "," + READBACK_FEATURE if argument == FEATURE_ARGUMENT else argument
                         for argument in arguments]
        return arguments


def validate_receipt(executable: Path, core: dict) -> bytes:
    raw = validate_surface_receipt(executable, core)
    patch = ROOT / "native/patches" / GPU_PATCH
    if not patch.is_file() or patch.is_symlink():
        raise ValueError("GPU readback requires a registered compiled patch, not a draft")
    expected = {"name": GPU_PATCH, "sha256": hashlib.sha256(patch.read_bytes()).hexdigest()}
    if expected not in json.loads(raw.decode("utf-8-sig"))["patches"]:
        raise ValueError("Receipt lacks the exact compiled WebGL readback patch")
    return raw


def decode_png(value: list[int]) -> list[int]:
    if (not isinstance(value, list) or not 33 <= len(value) <= 65536
            or any(type(byte) is not int or not 0 <= byte <= 255 for byte in value)
            or bytes(value[:8]) != b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Missing or malformed bounded PNG export")
    if (bytes(value[8:16]) != b"\x00\x00\x00\rIHDR"
            or bytes(value[16:24]) != b"\x00\x00\x00\x04\x00\x00\x00\x04"):
        raise ValueError("PNG dimensions must be bounded before decoding")
    image = QImage.fromData(bytes(value), "PNG")
    if image.isNull() or image.width() != 4 or image.height() != 4:
        raise ValueError("PNG export dimensions changed")
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    data = image.constBits().asstring(image.sizeInBytes())
    # PNG is top-down; GL readPixels is bottom-up.
    return [byte for row in range(3, -1, -1)
            for byte in data[row * image.bytesPerLine():row * image.bytesPerLine() + 16]]


def validate_readback(observed: dict, *, protected: bool, baseline: dict | None = None) -> dict:
    if not isinstance(observed, dict) or set(observed) != CONTEXTS:
        raise ValueError("Readback must cover all document and worker contexts")
    normalized = copy.deepcopy(observed)
    for context, values in observed.items():
        if not isinstance(values, dict) or set(values) != {"webgl", "webgpu"} or not isinstance(values.get("webgl"), dict):
            raise ValueError("Missing WebGL observations")
        for api in ("webgl", "webgl2"):
            gl = values["webgl"].get(api)
            if not isinstance(gl, dict) or gl.get("available") is not True:
                raise ValueError("WebGL readback coverage is unavailable: " + context + "/" + api)
            scene = gl.get("scene")
            fields = {"pixels", "repeat", "crop", "pbo", "packed", "png", "packState",
                      "exportState", "initialState"}
            if not isinstance(scene, dict) or set(scene) != fields:
                raise ValueError("Readback/export/state observations are incomplete")
            full = scene["pixels"]
            read_scene = {key: scene[key] for key in ("pixels", "repeat", "crop", "pbo", "packed")}
            validate_shader_readback(read_scene, api, expected_pixels=full)
            if any((byte != reference if not protected or index % 4 == 3 else
                    byte >> 1 != reference >> 1) for index, (byte, reference) in enumerate(zip(full, SHADER_PIXELS))):
                raise ValueError("Readback changed alpha, upper colour bits or baseline pixels")
            if decode_png(scene["png"]) != full:
                raise ValueError("Native PNG export disagrees with WebGL pixels")
            initial = {"alignment": 4, "framebuffer": True, "rowLength": 0,
                       "skipRows": 0, "skipPixels": 0, "packBound": False}
            packed = {**initial, "rowLength": 6, "skipRows": 1, "skipPixels": 1} if api == "webgl2" else initial
            for field in ("initialState", "packState", "exportState"):
                state = scene[field]
                if (not isinstance(state, dict) or set(state) != set(initial)
                        or any(type(state[key]) is not type(value) for key, value in initial.items())):
                    raise ValueError("Readback GL-state evidence is malformed")
            if scene["initialState"] != initial or scene["packState"] != packed or scene["exportState"] != packed:
                raise ValueError("Readback/export changed pack state or framebuffer binding")
            # Reuse the existing GPU capability/operation validator independently
            # of the candidate's allowed pixel changes.
            normal_scene = copy.deepcopy(read_scene)
            normal_scene.update(pixels=SHADER_PIXELS.copy(), repeat=SHADER_PIXELS.copy(),
                                crop=SHADER_PIXELS[20:28] + SHADER_PIXELS[36:44])
            if api == "webgl2":
                normal_scene["pbo"] = [165] * 12 + SHADER_PIXELS + [165] * 8
                normal_scene["packed"] = [165] * 120
                for row in range(4):
                    start = (row + 1) * 24 + 4
                    normal_scene["packed"][start:start + 16] = SHADER_PIXELS[row * 16:(row + 1) * 16]
            normalized[context]["webgl"][api]["scene"] = normal_scene
    coverage = validate_observations(normalized, baseline=baseline)
    if coverage["webgl"] != len(CONTEXTS) or coverage["webgl2"] != len(CONTEXTS):
        raise ValueError("Incomplete native WebGL coverage")
    if protected:
        if any(row["webgl"]["webgl"]["scene"]["pixels"] != row["webgl"]["webgl2"]["scene"]["pixels"]
               for row in observed.values()):
            raise ValueError("WebGL1 and WebGL2 surface domains disagree")
        for api in ("webgl", "webgl2"):
            reference = observed["document"]["webgl"][api]["scene"]["pixels"]
            if reference == SHADER_PIXELS:
                raise ValueError("Protected readback did not change the nonuniform scene")
            if any(observed[name]["webgl"][api]["scene"]["pixels"] != reference for name in SAME_PARTITION):
                raise ValueError("Same-partition WebGL contexts disagree")
            if observed["cross_origin_frame"]["webgl"][api]["scene"]["pixels"] == reference:
                raise ValueError("Cross-origin WebGL partition was not isolated")
    return normalized


def probe_inputs() -> dict[str, str]:
    from scripts.verify_native_gpu import probe_inputs as gpu_inputs
    from scripts.verify_native_surfaces import probe_inputs as surface_inputs
    return {**gpu_inputs(), **surface_inputs(),
            "scripts/verify_native_gpu_readback.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def restart_state(observed: dict) -> dict:
    result = copy.deepcopy(observed)
    # ANGLE may reuse its shader cache on restart and emit a shorter translated
    # debug source. Presence/error semantics are checked separately; its length
    # is not part of the protected pixel identity.
    for row in result.values():
        for gl in row["webgl"].values():
            gl.pop("translatedShaderLength")
    return result


async def verify(executable: Path, owned: Path, server: FixtureServer, report: dict,
                 runtimes: list[NativeRuntime]) -> None:
    discovery = NativeRuntime(owned / "driver-arguments", executable, ReadbackConfiguration())
    runtimes.append(discovery)
    try:
        context = await discovery.start(headless=True)
        arguments = await browser_arguments(context)
        replacement = partitioning_argument(arguments)
        original = next(argument for argument in arguments if argument.startswith("--disable-features="))
    finally:
        await discovery.close()
    baseline = None
    results = {}
    for name in ("baseline", "profile-a", "profile-b"):
        protected = name != "baseline"
        configuration = ReadbackConfiguration(probe_mode="ready" if protected else "baseline",
            disabled_features_argument=replacement, ignored_driver_argument=original)
        runtime = NativeRuntime(owned / name, executable, configuration)
        runtimes.append(runtime)
        previous = None
        for phase in ("initial", "restart"):
            try:
                context = await runtime.start(headless=True)
                effective = await browser_arguments(context)
                expected = FEATURE_ARGUMENT + ("," + READBACK_FEATURE if protected else "")
                if (partitioning_argument(effective) != replacement
                        or replacement not in effective or expected not in effective
                        or any(argument not in effective for argument in configuration.launch_arguments())):
                    raise ValueError("Effective arguments do not request the expected partition/readback mode")
                observed = await observe(context, f"http://127.0.0.1:{server.server_port}", read=READBACK_READ)
                check = {"name": f"{name}-{phase}", "passed": False, "observed": observed}
                report["checks"].append(check)
                normalized = validate_readback(observed, protected=protected, baseline=baseline)
                if previous is not None and restart_state(observed) != restart_state(previous):
                    raise ValueError("Readback/export/metadata changed across profile restart")
                previous = observed
                if baseline is None:
                    baseline = normalized
                results[name] = observed
                check["passed"] = True
            finally:
                await runtime.close()
    for context in CONTEXTS:
        for api in ("webgl", "webgl2"):
            pixels = [tuple(results[name][context]["webgl"][api]["scene"]["pixels"])
                      for name in ("baseline", "profile-a", "profile-b")]
            if len(set(pixels)) != 3:
                raise ValueError("WebGL scene did not isolate both profiles from baseline")
    report["cross_profile_isolation_passed"] = True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.report.is_symlink():
        parser.error("Refusing to overwrite GPU readback evidence")
    report = {"schema": 1, "passed": False, "privacy_admitted": False, "checks": [],
              "platform": platform.platform(), "scope": __doc__}
    server = thread = owned = None
    runtimes = []
    try:
        executable = args.executable.resolve(strict=True)
        core = measure_runtime_core(executable)
        receipt = validate_receipt(executable, core)
        inputs = probe_inputs()
        report.update(runtime_core_sha256_measured=core, probe_inputs_sha256=inputs,
                      receipt_sha256=hashlib.sha256(receipt).hexdigest(),
                      javascript_sha256=hashlib.sha256(READBACK_READ.encode("utf-8")).hexdigest())
        if args.work_dir.resolve().is_relative_to(ROOT):
            raise ValueError("GPU profiles must remain outside the public checkout")
        args.work_dir.mkdir(parents=True, exist_ok=True)
        server = FixtureServer(("127.0.0.1", 0), ReadbackFixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        owned = Path(tempfile.mkdtemp(prefix="glint-gpu-readback-", dir=args.work_dir.resolve()))
        asyncio.run(verify(executable, owned, server, report, runtimes))
        if (measure_runtime_core(executable) != core or validate_receipt(executable, core) != receipt
                or probe_inputs() != inputs):
            raise ValueError("GPU runtime, receipt or probe changed during verification")
        expected = {f"{name}-{phase}" for name in ("baseline", "profile-a", "profile-b")
                    for phase in ("initial", "restart")}
        if {check["name"] for check in report["checks"]} != expected or len(report["checks"]) != len(expected):
            raise ValueError("GPU readback phases are incomplete")
        report["passed"] = True
    except Exception as error:  # noqa: BLE001 - retain failed diagnostic evidence
        report.update(error=str(error), traceback=traceback.format_exc())
    finally:
        if server is not None:
            if thread is not None and thread.is_alive():
                server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)
        if owned is not None:
            try:
                if any(runtime.has_resources for runtime in runtimes):
                    raise ValueError("Live resources remain; owned profiles retained")
                if owned != owned.resolve() or not owned.is_relative_to(args.work_dir.resolve()):
                    raise ValueError("Refusing cleanup outside owned workspace")
                shutil.rmtree(owned)
            except (OSError, ValueError) as error:
                report.update(passed=False, cleanup_error=str(error), retained_profile_directory=str(owned))
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2)
    print(json.dumps({"passed": report["passed"], "report": str(args.report), "error": report.get("error")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
