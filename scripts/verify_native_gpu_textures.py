"""Owned texture framebuffer diagnostics; never admit a privacy capability."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright

from scripts.verify_native_canvas import CONTEXTS, CanvasFixtureHandler, observe
from scripts.verify_native_runtime import FixtureServer, measure_runtime_core

TEXTURE_READ = """async () => {
  const observed = {};
  for (const api of ['webgl', 'webgl2']) {
    const gl = new OffscreenCanvas(4, 4).getContext(api, {antialias: false});
    if (!gl) { observed[api] = {available: false}; continue; }
    const es3 = api === 'webgl2', textures = [], framebuffers = [], cases = [];
    const makeTexture = target => {
      const texture = gl.createTexture(); textures.push(texture);
      gl.bindTexture(target, texture);
      gl.texParameteri(target, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
      gl.texParameteri(target, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
      gl.texParameteri(target, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(target, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      return texture;
    };
    const pixels = (w, h, depth, color) => {
      const data = new Uint8Array(w * h * depth * 4);
      for (let i = 0; i < data.length; i += 4) data.set(color, i);
      return data;
    };
    const bindingState = () => [
      gl.getParameter(gl.FRAMEBUFFER_BINDING), gl.getParameter(gl.ACTIVE_TEXTURE),
      gl.getParameter(gl.TEXTURE_BINDING_2D), gl.getParameter(gl.TEXTURE_BINDING_CUBE_MAP),
      gl.getParameter(gl.PACK_ALIGNMENT),
      ...(es3 ? [gl.getParameter(gl.READ_FRAMEBUFFER_BINDING),
        gl.getParameter(gl.READ_BUFFER), gl.getParameter(gl.TEXTURE_BINDING_3D),
        gl.getParameter(gl.TEXTURE_BINDING_2D_ARRAY)] : [])];
    const read = (name, width, height, color) => {
      const status = gl.checkFramebufferStatus(gl.FRAMEBUFFER);
      if (status !== gl.FRAMEBUFFER_COMPLETE) throw new Error(name + ': incomplete framebuffer ' + status);
      gl.viewport(0, 0, 1, 1); gl.pixelStorei(gl.PACK_ALIGNMENT, 1);
      const before = bindingState(), first = new Uint8Array(width * height * 4);
      const repeat = new Uint8Array(first.length); first.fill(165); repeat.fill(165);
      gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, first);
      const firstError = gl.getError();
      gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, repeat);
      const secondError = gl.getError(), after = bindingState();
      cases.push({name, width, height, color, pixels: Array.from(first),
        repeat: Array.from(repeat), errors: [firstError, secondError],
        bindingsPreserved: before.every((value, index) => value === after[index])});
    };
    const framebuffer = () => {
      const value = gl.createFramebuffer(); framebuffers.push(value);
      gl.bindFramebuffer(gl.FRAMEBUFFER, value); return value;
    };
    try {
      const color = [31, 67, 93, 255];
      const two = makeTexture(gl.TEXTURE_2D); framebuffer();
      for (const [name, width, height] of [['2d-base', 9, 3], ['2d-redefined', 6, 2]]) {
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, width, height, 0, gl.RGBA,
          gl.UNSIGNED_BYTE, pixels(width, height, 1, color));
        gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, two, 0);
        read(name, width, height, color);
      }
      if (es3) {
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, 8, 4, 0, gl.RGBA,
          gl.UNSIGNED_BYTE, pixels(8, 4, 1, color));
        gl.texImage2D(gl.TEXTURE_2D, 1, gl.RGBA8, 4, 2, 0, gl.RGBA,
          gl.UNSIGNED_BYTE, pixels(4, 2, 1, color));
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAX_LEVEL, 1);
        gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, two, 1);
        read('2d-mip-level', 4, 2, color);
      }
      const cube = makeTexture(gl.TEXTURE_CUBE_MAP); framebuffer();
      for (let face = 0; face < 6; ++face) {
        const tint = [20 + face, 50 + face, 80 + face, 255];
        gl.texImage2D(gl.TEXTURE_CUBE_MAP_POSITIVE_X + face, 0, gl.RGBA, 3, 3, 0,
          gl.RGBA, gl.UNSIGNED_BYTE, pixels(3, 3, 1, tint));
      }
      for (const face of [0, 3]) {
        gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0,
          gl.TEXTURE_CUBE_MAP_POSITIVE_X + face, cube, 0);
        read('cube-face-' + face, 3, 3, [20 + face, 50 + face, 80 + face, 255]);
      }
      if (es3) {
        for (const [label, target] of [['array', gl.TEXTURE_2D_ARRAY], ['3d', gl.TEXTURE_3D]]) {
          const texture = makeTexture(target), data = pixels(5, 3, 2, color);
          const other = [111, 71, 41, 255];
          data.set(pixels(5, 3, 1, other), 5 * 3 * 4);
          gl.texImage3D(target, 0, gl.RGBA8, 5, 3, 2, 0, gl.RGBA, gl.UNSIGNED_BYTE, data);
          framebuffer();
          gl.drawBuffers([gl.NONE, gl.COLOR_ATTACHMENT1]); gl.readBuffer(gl.COLOR_ATTACHMENT1);
          for (const layer of [0, 1]) {
            gl.framebufferTextureLayer(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT1, texture, 0, layer);
            read(label + '-layer-' + layer, 5, 3, layer === 0 ? color : other);
          }
        }
      }
      observed[api] = {available: true, cases, finalError: gl.getError()};
    } finally {
      for (const value of framebuffers) gl.deleteFramebuffer(value);
      for (const value of textures) gl.deleteTexture(value);
    }
  }
  return observed;
}"""

CASES = {"webgl": {"2d-base", "2d-redefined", "cube-face-0", "cube-face-3"},
         "webgl2": {"2d-base", "2d-redefined", "2d-mip-level", "cube-face-0", "cube-face-3",
                    "array-layer-0", "array-layer-1", "3d-layer-0", "3d-layer-1"}}
CASE_CONFIG = {
    "2d-base": (9, 3, [31, 67, 93, 255]),
    "2d-redefined": (6, 2, [31, 67, 93, 255]),
    "2d-mip-level": (4, 2, [31, 67, 93, 255]),
    "cube-face-0": (3, 3, [20, 50, 80, 255]),
    "cube-face-3": (3, 3, [23, 53, 83, 255]),
    "array-layer-0": (5, 3, [31, 67, 93, 255]),
    "array-layer-1": (5, 3, [111, 71, 41, 255]),
    "3d-layer-0": (5, 3, [31, 67, 93, 255]),
    "3d-layer-1": (5, 3, [111, 71, 41, 255]),
}


class TextureFixtureHandler(CanvasFixtureHandler):
    worker_read = TEXTURE_READ


def validate(observed: dict) -> None:
    if set(observed) != set(CONTEXTS):
        raise ValueError("Texture diagnostics require every document/frame/worker context")
    for context, apis in observed.items():
        if set(apis) != set(CASES):
            raise ValueError("Missing texture APIs: " + context)
        for api, expected_names in CASES.items():
            value = apis[api]
            if (value.get("available") is not True or type(value.get("finalError")) is not int
                    or value["finalError"] != 0):
                raise ValueError("Texture API unavailable or errored: " + context + "/" + api)
            cases = value.get("cases", [])
            if len(cases) != len(expected_names) or {item["name"] for item in cases} != expected_names:
                raise ValueError("Missing or repeated texture lifecycle cases")
            for item in cases:
                width, height, color = item["width"], item["height"], item["color"]
                if (width, height, color) != CASE_CONFIG[item["name"]]:
                    raise ValueError("Texture fixture does not match its defined upload")
                if (type(width) is not int or type(height) is not int or not 0 < width <= 9
                        or not 0 < height <= 4 or len(color) != 4
                        or any(type(byte) is not int or not 0 <= byte <= 255 for byte in color)):
                    raise ValueError("Invalid texture fixture dimensions or bytes")
                expected = color * (width * height)
                if (item["pixels"] != expected or item["repeat"] != expected
                        or any(type(byte) is not int for byte in item["pixels"] + item["repeat"])
                        or item["errors"] != [0, 0] or any(type(code) is not int for code in item["errors"])
                        or item["bindingsPreserved"] is not True):
                    raise ValueError("Texture readback/state mismatch: " + context + "/" + item["name"])


async def verify(executable: Path, profile: Path, origin: str, report: dict) -> None:
    previous = None
    async with async_playwright() as driver:
        for phase in ("initial", "restart"):
            context = await driver.chromium.launch_persistent_context(
                str(profile), executable_path=str(executable), headless=True,
                chromium_sandbox=True, timeout=30000,
                args=["--disable-features=GlintWebGLReadbackCandidate,GlintGpuMetadataMinimization,GlintReadbackMetadataCandidate"])
            check = {"name": phase, "passed": False}
            report["checks"].append(check)
            try:
                observed = await observe(context, origin, read=TEXTURE_READ)
                check["observed"] = observed
                validate(observed)
                if previous is not None and previous != observed:
                    raise ValueError("Texture lifecycle observations changed after restart")
                previous = observed
                check["passed"] = True
            finally:
                await context.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("A new diagnostic report is required")
    report = {"passed": False, "privacy_admitted": False, "checks": [],
              "scope": "Feature-off texture lifecycle baseline; not protected runtime proof"}
    server = None
    thread = None
    try:
        executable = args.executable.resolve(strict=True)
        core = measure_runtime_core(executable)
        inputs = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (
            Path(__file__), ROOT / "scripts/verify_native_canvas.py", ROOT / "scripts/verify_native_runtime.py")}
        report.update(runtime_core_sha256_measured=core, probe_inputs_sha256=inputs,
                      javascript_sha256=hashlib.sha256(TEXTURE_READ.encode()).hexdigest())
        args.work_dir.mkdir(parents=True, exist_ok=True)
        server = FixtureServer(("127.0.0.1", 0), TextureFixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        with tempfile.TemporaryDirectory(prefix="glint-textures-owned-", dir=args.work_dir.resolve()) as owned:
            asyncio.run(verify(executable, Path(owned), f"http://127.0.0.1:{server.server_port}", report))
        if core != measure_runtime_core(executable) or any(
                hashlib.sha256(Path(path).read_bytes()).hexdigest() != value for path, value in inputs.items()):
            raise ValueError("Runtime or texture probe inputs changed during diagnostics")
        report["passed"] = True
    except Exception as error:  # noqa: BLE001 - retain diagnostic failures
        report["error"] = str(error)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as output:
            output.write(json.dumps(report, indent=2))
    print(json.dumps({"passed": report["passed"], "error": report.get("error")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
