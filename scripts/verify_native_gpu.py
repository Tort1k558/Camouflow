"""Diagnose GPU metadata and real operations; never admit a privacy capability."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import sys
import tempfile
import threading
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright

from scripts.verify_native_canvas import CONTEXTS, CanvasFixtureHandler, observe
from scripts.verify_native_runtime import FixtureServer, measure_runtime_core

WEBGL_LIMITS = {"MAX_TEXTURE_SIZE", "MAX_CUBE_MAP_TEXTURE_SIZE", "MAX_RENDERBUFFER_SIZE",
                "MAX_VERTEX_ATTRIBS", "MAX_TEXTURE_IMAGE_UNITS", "MAX_VERTEX_TEXTURE_IMAGE_UNITS"}
WEBGPU_LIMITS = {"maxTextureDimension2D", "maxBufferSize", "maxComputeWorkgroupSizeX",
                 "maxComputeInvocationsPerWorkgroup"}
SHADER_PIXELS = [value for y in range(1, 5) for x in range(1, 5) for value in (x, y, 85, 255)]
SHADER_CROP = [value for y in range(2, 4) for x in range(2, 4) for value in (x, y, 85, 255)]


def probe_inputs() -> dict[str, str]:
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
        "scripts/verify_native_gpu.py", "scripts/verify_native_canvas.py",
        "scripts/verify_native_hardware.py", "scripts/verify_native_runtime.py")}

GPU_READ = """async () => {
  const result = {webgl: {}, webgpu: {available: false, reason: 'API unavailable'}};
  for (const name of ['webgl', 'webgl2']) {
    const canvas = new OffscreenCanvas(4, 4);
    const gl = canvas.getContext(name, {antialias: false});
    if (!gl) { result.webgl[name] = {available: false}; continue; }
    const extensions = gl.getSupportedExtensions().slice().sort();
    const debug = gl.getExtension('WEBGL_debug_renderer_info');
    const vendor = debug ? gl.getParameter(debug.UNMASKED_VENDOR_WEBGL) : null;
    const renderer = debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : null;
    if (gl.getError() !== gl.NO_ERROR) throw new Error(name + ': metadata error');
    let unavailableParameter = null;
    if (!debug) {
      unavailableParameter = {value: gl.getParameter(0x9245), error: gl.getError()};
    }
    gl.disable(gl.DITHER);
    gl.clearColor(17 / 255, 34 / 255, 51 / 255, 1);
    gl.clear(gl.COLOR_BUFFER_BIT);
    const pixels = new Uint8Array(4);
    gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
    const limits = {};
    for (const key of ['MAX_TEXTURE_SIZE', 'MAX_CUBE_MAP_TEXTURE_SIZE',
                      'MAX_RENDERBUFFER_SIZE', 'MAX_VERTEX_ATTRIBS',
                      'MAX_TEXTURE_IMAGE_UNITS', 'MAX_VERTEX_TEXTURE_IMAGE_UNITS']) {
      limits[key] = gl.getParameter(gl[key]);
    }
    const debugShaders = gl.getExtension('WEBGL_debug_shaders');
    const shaders = [];
    let program = null, vertices = null, pack = null;
    let scene, translatedShaderLength;
    try {
      const version = name === 'webgl2' ? '#version 300 es\\n' : '';
      const compile = (type, source) => {
        const shader = gl.createShader(type);
        if (!shader) throw new Error(name + ': shader allocation failed');
        shaders.push(shader); gl.shaderSource(shader, source); gl.compileShader(shader);
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
          throw new Error(name + ': shader compilation failed: ' + gl.getShaderInfoLog(shader));
        }
        return shader;
      };
      const vertex = compile(gl.VERTEX_SHADER, version +
        (name === 'webgl2' ? 'in' : 'attribute') +
        ' vec2 position; void main() { gl_Position = vec4(position, 0.0, 1.0); }');
      const fragment = compile(gl.FRAGMENT_SHADER, version + 'precision highp float;' +
        (name === 'webgl2' ? 'out vec4 colour;' : '') + 'void main() {' +
        (name === 'webgl2' ? 'colour' : 'gl_FragColor') +
        '= vec4((gl_FragCoord.x + 0.5) / 255.0, (gl_FragCoord.y + 0.5) / 255.0, 85.0 / 255.0, 1.0); }');
      program = gl.createProgram(); vertices = gl.createBuffer();
      if (!program || !vertices) throw new Error(name + ': scene allocation failed');
      gl.attachShader(program, vertex); gl.attachShader(program, fragment); gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
        throw new Error(name + ': program link failed: ' + gl.getProgramInfoLog(program));
      }
      translatedShaderLength = debugShaders ? debugShaders.getTranslatedShaderSource(fragment).length : 0;
      gl.useProgram(program); gl.bindBuffer(gl.ARRAY_BUFFER, vertices);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
      const position = gl.getAttribLocation(program, 'position');
      if (position < 0) throw new Error(name + ': position attribute unavailable');
      gl.enableVertexAttribArray(position); gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
      gl.viewport(0, 0, 4, 4); gl.drawArrays(gl.TRIANGLES, 0, 3);
      const full = new Uint8Array(64), repeat = new Uint8Array(64), crop = new Uint8Array(16);
      gl.readPixels(0, 0, 4, 4, gl.RGBA, gl.UNSIGNED_BYTE, full);
      gl.readPixels(0, 0, 4, 4, gl.RGBA, gl.UNSIGNED_BYTE, repeat);
      gl.readPixels(1, 1, 2, 2, gl.RGBA, gl.UNSIGNED_BYTE, crop);
      scene = {pixels: Array.from(full), repeat: Array.from(repeat), crop: Array.from(crop),
        pbo: null, packed: null};
      if (name === 'webgl2') {
        pack = gl.createBuffer();
        if (!pack) throw new Error(name + ': pixel pack allocation failed');
        gl.bindBuffer(gl.PIXEL_PACK_BUFFER, pack);
        gl.bufferData(gl.PIXEL_PACK_BUFFER, new Uint8Array(84).fill(165), gl.STREAM_READ);
        gl.readPixels(0, 0, 4, 4, gl.RGBA, gl.UNSIGNED_BYTE, 12);
        const pbo = new Uint8Array(84);
        gl.getBufferSubData(gl.PIXEL_PACK_BUFFER, 0, pbo);
        scene.pbo = Array.from(pbo);
        gl.bindBuffer(gl.PIXEL_PACK_BUFFER, null);
        gl.pixelStorei(gl.PACK_ROW_LENGTH, 6);
        gl.pixelStorei(gl.PACK_SKIP_PIXELS, 1);
        gl.pixelStorei(gl.PACK_SKIP_ROWS, 1);
        const packed = new Uint8Array(120).fill(165);
        gl.readPixels(0, 0, 4, 4, gl.RGBA, gl.UNSIGNED_BYTE, packed);
        scene.packed = Array.from(packed);
      }
    } finally {
      if (name === 'webgl2') {
        gl.bindBuffer(gl.PIXEL_PACK_BUFFER, null);
        gl.pixelStorei(gl.PACK_ROW_LENGTH, 0); gl.pixelStorei(gl.PACK_SKIP_PIXELS, 0);
        gl.pixelStorei(gl.PACK_SKIP_ROWS, 0);
      }
      if (pack) gl.deleteBuffer(pack);
      if (vertices) gl.deleteBuffer(vertices);
      if (program) gl.deleteProgram(program);
      for (const shader of shaders) gl.deleteShader(shader);
    }
    result.webgl[name] = {available: true, extensions, debug: Boolean(debug),
      debugShaders: Boolean(debugShaders), translatedShaderLength, scene,
      vendor, renderer, unavailableParameter, pixels: Array.from(pixels), limits,
      error: gl.getError(), contextLost: gl.isContextLost()};
    gl.getExtension('WEBGL_lose_context')?.loseContext();
  }
  if (!navigator.gpu) return result;
  const adapter = await navigator.gpu.requestAdapter();
  if (!adapter) { result.webgpu.reason = 'No adapter'; return result; }
  const info = value => ({vendor: value.vendor, architecture: value.architecture,
    device: value.device, description: value.description,
    subgroupMinSize: value.subgroupMinSize, subgroupMaxSize: value.subgroupMaxSize,
    isFallbackAdapter: value.isFallbackAdapter});
  const limits = {};
  for (const key of ['maxTextureDimension2D', 'maxBufferSize',
                    'maxComputeWorkgroupSizeX', 'maxComputeInvocationsPerWorkgroup']) {
    limits[key] = adapter.limits[key];
  }
  const first = info(adapter.info), repeat = info(adapter.info);
  const device = await adapter.requestDevice();
  const source = device.createBuffer({size: 16,
    usage: GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST | GPUBufferUsage.STORAGE});
  const target = device.createBuffer({size: 16, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ});
  const computed = device.createBuffer({size: 16, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC});
  const errors = [];
  device.addEventListener('uncapturederror', event => errors.push(event.error.message));
  device.pushErrorScope('validation');
  try {
    const input = new Uint32Array([17, 34, 51, 255]);
    device.queue.writeBuffer(source, 0, input);
    const encoder = device.createCommandEncoder();
    encoder.copyBufferToBuffer(source, 0, target, 0, 16);
    device.queue.submit([encoder.finish()]);
    await target.mapAsync(GPUMapMode.READ);
    const roundtrip = Array.from(new Uint32Array(target.getMappedRange()));
    target.unmap();
    const pipeline = await device.createComputePipelineAsync({layout: 'auto', compute: {
      module: device.createShaderModule({code: `
        @group(0) @binding(0) var<storage, read> input: array<u32>;
        @group(0) @binding(1) var<storage, read_write> output: array<u32>;
        @compute @workgroup_size(4) fn main(@builtin(global_invocation_id) id: vec3u) {
          output[id.x] = input[id.x] + 1u;
        }`}), entryPoint: 'main'}});
    const bindGroup = device.createBindGroup({layout: pipeline.getBindGroupLayout(0), entries: [
      {binding: 0, resource: {buffer: source}}, {binding: 1, resource: {buffer: computed}}]});
    const computeEncoder = device.createCommandEncoder();
    const pass = computeEncoder.beginComputePass();
    pass.setPipeline(pipeline); pass.setBindGroup(0, bindGroup); pass.dispatchWorkgroups(1); pass.end();
    computeEncoder.copyBufferToBuffer(computed, 0, target, 0, 16);
    device.queue.submit([computeEncoder.finish()]);
    await target.mapAsync(GPUMapMode.READ);
    const compute = Array.from(new Uint32Array(target.getMappedRange()));
    target.unmap();
    const validation = await device.popErrorScope();
    result.webgpu = {available: true, info: first, repeat,
      deviceInfo: info(device.adapterInfo), features: Array.from(adapter.features).sort(),
      limits, roundtrip, compute, validationError: validation?.message ?? null, errors};
  } finally { source.destroy(); target.destroy(); computed.destroy(); device.destroy(); }
  return result;
}"""


class GpuFixtureHandler(CanvasFixtureHandler):
    worker_read = GPU_READ


def validate_shader_readback(scene: dict, api: str, *, expected_pixels: list[int] | None = None) -> None:
    if api not in {"webgl", "webgl2"}:
        raise ValueError("Unknown WebGL readback API: " + api)
    if not isinstance(scene, dict) or set(scene) != {"pixels", "repeat", "crop", "pbo", "packed"}:
        raise ValueError("Missing shader readback observations: " + api)
    full = SHADER_PIXELS if expected_pixels is None else expected_pixels
    if (not isinstance(full, list) or len(full) != 64
            or any(type(byte) is not int or not 0 <= byte <= 255 for byte in full)):
        raise ValueError("Invalid expected shader pixels")
    crop = full[20:28] + full[36:44]
    expected = {"pixels": full, "repeat": full, "crop": crop}
    if api == "webgl2":
        expected["pbo"] = [165] * 12 + full + [165] * 8
        packed = [165] * 120
        for row in range(4):
            start = (row + 1) * 24 + 4
            packed[start:start + 16] = full[row * 16:(row + 1) * 16]
        expected["packed"] = packed
    elif scene["pbo"] is not None or scene["packed"] is not None:
        raise ValueError("WebGL1 claimed WebGL2 pack operations")
    for name, reference in expected.items():
        value = scene[name]
        if (not isinstance(value, list) or any(type(byte) is not int or not 0 <= byte <= 255 for byte in value)
                or value != reference):
            raise ValueError("Shader/crop/PBO/padding readback mismatch: " + api + "/" + name)


def validate_observations(observed: dict, *, minimized: bool = False,
                          baseline: dict | None = None) -> dict:
    if not isinstance(observed, dict) or set(observed) != CONTEXTS:
        raise ValueError("GPU probe must observe every document and worker context")
    if baseline is not None:
        validate_observations(baseline)
    coverage = {"webgl": 0, "webgl2": 0, "webgpu": 0}
    for context, values in observed.items():
        if not isinstance(values, dict) or set(values) != {"webgl", "webgpu"}:
            raise ValueError(f"Malformed GPU observation: {context}")
        if not isinstance(values["webgl"], dict) or set(values["webgl"]) != {"webgl", "webgl2"}:
            raise ValueError(f"Missing WebGL variants: {context}")
        for api, gl in values["webgl"].items():
            if not isinstance(gl, dict) or type(gl.get("available")) is not bool:
                raise ValueError(f"Missing availability: {context}/{api}")
            if not gl["available"]:
                if baseline is not None and baseline[context]["webgl"][api]["available"]:
                    raise ValueError(f"GPU context disappeared: {context}/{api}")
                continue
            coverage[api] += 1
            validate_shader_readback(gl.get("scene"), api)
            if (gl.get("pixels") != [17, 34, 51, 255] or type(gl.get("error")) is not int or gl["error"] != 0
                    or gl.get("contextLost") is not False):
                raise ValueError(f"WebGL operation failed: {context}/{api}")
            extensions = gl.get("extensions")
            limits = gl.get("limits")
            if (not isinstance(extensions, list) or any(not isinstance(item, str) for item in extensions)
                    or len(extensions) != len(set(extensions))
                    or not isinstance(limits, dict) or set(limits) != WEBGL_LIMITS
                    or any(type(value) is not int or value <= 0 for value in limits.values())
                    or type(gl.get("debug")) is not bool):
                raise ValueError(f"Invalid WebGL metadata: {context}/{api}")
            if gl["debug"] != ("WEBGL_debug_renderer_info" in extensions):
                raise ValueError(f"Inconsistent debug extension: {context}/{api}")
            if (type(gl.get("debugShaders")) is not bool
                    or gl["debugShaders"] != ("WEBGL_debug_shaders" in extensions)
                    or type(gl.get("translatedShaderLength")) is not int
                    or gl["translatedShaderLength"] < 0
                    or (not gl["debugShaders"] and gl["translatedShaderLength"] != 0)):
                raise ValueError(f"Inconsistent translated-shader debug extension: {context}/{api}")
            if minimized and gl["debugShaders"]:
                raise ValueError(f"Translated shader metadata still exposed: {context}/{api}")
            if minimized and gl["debug"]:
                raise ValueError(f"GPU debug metadata still exposed: {context}/{api}")
            if not gl["debug"] and (gl.get("vendor") is not None or gl.get("renderer") is not None
                    or gl.get("unavailableParameter") != {"value": None, "error": 1280}):
                raise ValueError(f"Unavailable extension changed API semantics: {context}/{api}")
            if baseline is not None:
                previous = baseline[context]["webgl"][api]
                if not previous["available"] or previous["limits"] != limits:
                    raise ValueError(f"WebGL availability/limits changed: {context}/{api}")
                previous_extensions = [item for item in previous["extensions"]
                                       if not minimized or item not in {"WEBGL_debug_renderer_info", "WEBGL_debug_shaders"}]
                if previous_extensions != extensions:
                    raise ValueError(f"Unrelated WebGL extensions changed: {context}/{api}")
        gpu = values["webgpu"]
        if not isinstance(gpu, dict) or type(gpu.get("available")) is not bool:
            raise ValueError(f"Missing WebGPU availability: {context}")
        if not gpu["available"]:
            if not isinstance(gpu.get("reason"), str) or not gpu["reason"]:
                raise ValueError(f"Missing WebGPU unavailability reason: {context}")
            if baseline is not None and baseline[context]["webgpu"]["available"]:
                raise ValueError(f"WebGPU adapter disappeared: {context}")
            continue
        coverage["webgpu"] += 1
        info = gpu.get("info")
        if (not isinstance(info, dict) or set(info) != {"vendor", "architecture", "device",
                "description", "subgroupMinSize", "subgroupMaxSize", "isFallbackAdapter"}
                or any(not isinstance(info[key], str) for key in ("vendor", "architecture", "device", "description"))
                or any(type(info[key]) is not int or info[key] < 0 for key in ("subgroupMinSize", "subgroupMaxSize"))
                or info["subgroupMinSize"] > info["subgroupMaxSize"]
                or type(info["isFallbackAdapter"]) is not bool):
            raise ValueError(f"Invalid WebGPU adapter info: {context}")
        if gpu.get("repeat") != info or gpu.get("deviceInfo") != info:
            raise ValueError(f"Inconsistent adapter/device info: {context}")
        if minimized and any(info[key] for key in ("vendor", "architecture", "device", "description")):
            raise ValueError(f"WebGPU identifying strings still exposed: {context}")
        if (gpu.get("roundtrip") != [17, 34, 51, 255] or gpu.get("compute") != [18, 35, 52, 256]
                or gpu.get("validationError") is not None or gpu.get("errors") != []):
            raise ValueError(f"WebGPU buffer/compute operation failed: {context}")
        if (not isinstance(gpu.get("features"), list)
                or any(not isinstance(item, str) for item in gpu["features"])
                or len(gpu["features"]) != len(set(gpu["features"]))
                or not isinstance(gpu.get("limits"), dict) or set(gpu["limits"]) != WEBGPU_LIMITS
                or any(type(value) is not int or value <= 0 for value in gpu["limits"].values())):
            raise ValueError(f"Invalid WebGPU features/limits: {context}")
        if baseline is not None:
            previous = baseline[context]["webgpu"]
            if (not previous["available"] or previous["limits"] != gpu["limits"]
                    or previous["features"] != gpu["features"]
                    or any(previous["info"][key] != info[key] for key in
                           ("subgroupMinSize", "subgroupMaxSize", "isFallbackAdapter"))):
                raise ValueError(f"WebGPU capabilities changed: {context}")
    if not coverage["webgl"] or not coverage["webgl2"]:
        raise ValueError("No working WebGL1/2 coverage; this cannot pass diagnostics")
    return coverage


async def verify(executable: Path, profile: Path, origin: str, report: dict, minimized: bool) -> None:
    baseline = None
    phases = [("feature-off", False), ("feature-off-restart", False)]
    if minimized:
        phases.extend([("feature-on", True), ("feature-on-restart", True)])
    async with async_playwright() as driver:
        for name, enabled in phases:
            flag = "--enable-features=" if enabled else "--disable-features="
            context = await driver.chromium.launch_persistent_context(
                str(profile), executable_path=str(executable), headless=True,
                chromium_sandbox=True, timeout=30000,
                args=[flag + "GlintGpuMetadataMinimization"])
            try:
                report["browser_version"] = context.browser.version
                observed = await observe(context, origin, read=GPU_READ)
                check = {"name": name, "observed": observed, "passed": False}
                report["checks"].append(check)
                check["coverage"] = validate_observations(observed, minimized=enabled, baseline=baseline)
                check["passed"] = True
                if baseline is None:
                    baseline = observed
            finally:
                await context.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--minimized", action="store_true", help="Also check candidate feature-on semantics")
    parser.add_argument("--windows-library-directory", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Refusing to overwrite existing GPU evidence")
    report = {"schema": 1, "platform": platform.platform(), "passed": False, "checks": [],
              "privacy_admitted": False, "contexts": sorted(CONTEXTS),
              "scope": "Local GPU metadata, real GLSL draw/crop/repeat, WebGL2 PBO/pack padding and WebGPU buffer/compute diagnostics; no GPU readback privacy or anti-bot claim"}
    server = None
    thread = None
    try:
        executable = args.executable.resolve(strict=True)
        if not executable.is_file():
            raise ValueError("An explicit Chromium executable is required")
        core = measure_runtime_core(executable, args.windows_library_directory)
        report["runtime_core_sha256_measured"] = core
        inputs = probe_inputs()
        report["probe_inputs_sha256"] = inputs
        report["javascript_sha256"] = hashlib.sha256(GPU_READ.encode("utf-8")).hexdigest()
        args.work_dir.mkdir(parents=True, exist_ok=True)
        server = FixtureServer(("127.0.0.1", 0), GpuFixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        with tempfile.TemporaryDirectory(prefix="glint-gpu-owned-", dir=args.work_dir.resolve()) as owned:
            asyncio.run(verify(executable, Path(owned), f"http://127.0.0.1:{server.server_port}", report, args.minimized))
        if measure_runtime_core(executable, args.windows_library_directory) != core:
            raise ValueError("Chromium runtime core changed during GPU verification")
        if probe_inputs() != inputs:
            raise ValueError("GPU probe inputs changed during verification")
        report["passed"] = True
    except Exception as error:  # noqa: BLE001 - persist failed diagnostic evidence before exiting
        report.update(error=str(error), traceback=traceback.format_exc())
    finally:
        if server is not None:
            if thread is not None and thread.is_alive():
                server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as output:
            output.write(json.dumps(report, indent=2))
    print(json.dumps({"passed": report["passed"], "report": str(args.report), "error": report.get("error")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
