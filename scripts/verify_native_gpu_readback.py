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

ERROR_READ = """
      if (gl.getError() !== gl.NO_ERROR) throw new Error(name + ': pre-error-fixture failure');
      if (name === 'webgl2') {
        gl.pixelStorei(gl.PACK_ROW_LENGTH, 0); gl.pixelStorei(gl.PACK_SKIP_PIXELS, 0);
        gl.pixelStorei(gl.PACK_SKIP_ROWS, 0); gl.bindBuffer(gl.PIXEL_PACK_BUFFER, null);
      }
      const attempt = (width, height, destination, format = gl.RGBA) => {
        gl.readPixels(0, 0, width, height, format, gl.UNSIGNED_BYTE, destination);
        return {error: gl.getError(), nextError: gl.getError(), pixels: Array.from(destination)};
      };
      const validation = {
        zero: attempt(0, 0, new Uint8Array(4).fill(165)),
        negative: attempt(-1, 1, new Uint8Array(4).fill(165)),
        short: attempt(1, 1, new Uint8Array(3).fill(165)),
        wrongType: attempt(1, 1, new Uint16Array(2).fill(165)),
        invalidFormat: attempt(1, 1, new Uint8Array(4).fill(165), 0)
      };
      const incomplete = gl.createFramebuffer();
      if (!incomplete) throw new Error(name + ': framebuffer fixture allocation failed');
      try {
        gl.bindFramebuffer(gl.FRAMEBUFFER, incomplete);
        validation.incomplete = attempt(1, 1, new Uint8Array(4).fill(165));
      } finally { gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.deleteFramebuffer(incomplete); }
      gl.enable(0); // Deliberately leave INVALID_ENUM pending during a valid read.
      validation.pending = attempt(1, 1, new Uint8Array(4).fill(165));
      validation.noPackBuffer = null; validation.overlappingPack = null;
      if (name === 'webgl2') {
        gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, 0);
        validation.noPackBuffer = {error: gl.getError(), nextError: gl.getError()};
        gl.pixelStorei(gl.PACK_SKIP_PIXELS, 1);
        validation.overlappingPack = attempt(1, 1, new Uint8Array(8).fill(165));
        gl.pixelStorei(gl.PACK_SKIP_PIXELS, 0);
      }
      scene.validation = validation;
"""
READBACK_READ = READBACK_READ.replace(
    "      scene.initialState = beforeExport;", "      scene.initialState = beforeExport;" + ERROR_READ)
READBACK_READ = READBACK_READ.replace(
    "    gl.getExtension('WEBGL_lose_context')?.loseContext();",
    "    const loss = gl.getExtension('WEBGL_lose_context');\n"
    "    if (!loss) throw new Error(name + ': context-loss fixture unavailable');\n"
    "    loss.loseContext();\n"
    "    const lostPixels = new Uint8Array(4).fill(165);\n"
    "    gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, lostPixels);\n"
    "    scene.lost = {lost: gl.isContextLost(), error: gl.getError(),\n"
    "      nextError: gl.getError(), pixels: Array.from(lostPixels)};")

RENDERBUFFER_READ = """
      scene.renderbuffer = null;
      if (name === 'webgl2') {
        const framebuffer = gl.createFramebuffer(), first = gl.createRenderbuffer(), second = gl.createRenderbuffer();
        const multiFramebuffer = gl.createFramebuffer(), multi = gl.createRenderbuffer();
        if (!framebuffer || !first || !second || !multiFramebuffer || !multi) throw new Error('Renderbuffer allocation failed');
        const viewport = Array.from(gl.getParameter(gl.VIEWPORT));
        const scissor = Array.from(gl.getParameter(gl.SCISSOR_BOX));
        const fill = (width, height) => {
          for (const buffer of [first, second]) {
            gl.bindRenderbuffer(gl.RENDERBUFFER, buffer);
            gl.renderbufferStorage(gl.RENDERBUFFER, gl.RGBA8, width, height);
          }
          if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) throw new Error('Renderbuffer framebuffer incomplete');
          gl.disable(gl.SCISSOR_TEST);
          gl.clearBufferfv(gl.COLOR, 0, new Float32Array([17 / 255, 34 / 255, 51 / 255, 1]));
          gl.enable(gl.SCISSOR_TEST);
          for (let y = 0; y < height; ++y) for (let x = 0; x < width; ++x) {
            gl.scissor(x, y, 1, 1);
            gl.clearBufferfv(gl.COLOR, 1, new Float32Array([(x + 1) / 255, (y + 1) / 255, 85 / 255, 1]));
          }
          gl.disable(gl.SCISSOR_TEST); gl.readBuffer(gl.COLOR_ATTACHMENT1);
        };
        const read = (width, height) => {
          gl.pixelStorei(gl.PACK_ROW_LENGTH, 0); gl.pixelStorei(gl.PACK_SKIP_ROWS, 0); gl.pixelStorei(gl.PACK_SKIP_PIXELS, 0);
          const pixels = new Uint8Array(width * height * 4), repeat = new Uint8Array(pixels.length), crop = new Uint8Array(16);
          gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
          gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, repeat);
          gl.readPixels(1, 1, 2, 2, gl.RGBA, gl.UNSIGNED_BYTE, crop);
          const boundaryReads = [];
          for (const bounds of [[0, 0, 1, 1], [-1, -1, 2, 2], [width - 1, height - 1, 2, 2],
                                [-4, -4, 2, 2], [width + 1, height + 1, 2, 2], [1, 1, 0, 2]]) {
            const [x, y, w, h] = bounds, size = Math.max(4, w * h * 4);
            const cpu = new Uint8Array(size).fill(165), buffer = gl.createBuffer();
            if (!buffer) throw new Error('Boundary PBO allocation failed');
            let pbo, bound, packedCpu, packedPbo;
            gl.readPixels(x, y, w, h, gl.RGBA, gl.UNSIGNED_BYTE, cpu);
            try {
              gl.bindBuffer(gl.PIXEL_PACK_BUFFER, buffer);
              gl.bufferData(gl.PIXEL_PACK_BUFFER, new Uint8Array(size + 32).fill(165), gl.STREAM_READ);
              gl.readPixels(x, y, w, h, gl.RGBA, gl.UNSIGNED_BYTE, 12);
              bound = gl.getParameter(gl.PIXEL_PACK_BUFFER_BINDING) === buffer;
              const output = new Uint8Array(size + 32);
              gl.getBufferSubData(gl.PIXEL_PACK_BUFFER, 0, output); pbo = Array.from(output);
              gl.bindBuffer(gl.PIXEL_PACK_BUFFER, null);
              gl.pixelStorei(gl.PACK_ALIGNMENT, 8); gl.pixelStorei(gl.PACK_ROW_LENGTH, w + 2);
              gl.pixelStorei(gl.PACK_SKIP_ROWS, 1); gl.pixelStorei(gl.PACK_SKIP_PIXELS, 1);
              const stride = Math.ceil((w + 2) * 4 / 8) * 8, packedSize = 32 + (h + 2) * stride;
              const packed = new Uint8Array(packedSize).fill(165);
              gl.readPixels(x, y, w, h, gl.RGBA, gl.UNSIGNED_BYTE, packed); packedCpu = Array.from(packed);
              gl.bindBuffer(gl.PIXEL_PACK_BUFFER, buffer);
              gl.bufferData(gl.PIXEL_PACK_BUFFER, new Uint8Array(packedSize + 32).fill(165), gl.STREAM_READ);
              gl.readPixels(x, y, w, h, gl.RGBA, gl.UNSIGNED_BYTE, 12);
              bound = bound && gl.getParameter(gl.PIXEL_PACK_BUFFER_BINDING) === buffer;
              const packedOutput = new Uint8Array(packedSize + 32);
              gl.getBufferSubData(gl.PIXEL_PACK_BUFFER, 0, packedOutput); packedPbo = Array.from(packedOutput);
            } finally { gl.bindBuffer(gl.PIXEL_PACK_BUFFER, null); gl.deleteBuffer(buffer); }
            gl.pixelStorei(gl.PACK_ALIGNMENT, 4); gl.pixelStorei(gl.PACK_ROW_LENGTH, 0);
            gl.pixelStorei(gl.PACK_SKIP_ROWS, 0); gl.pixelStorei(gl.PACK_SKIP_PIXELS, 0);
            boundaryReads.push({bounds, cpu: Array.from(cpu), pbo, packedCpu, packedPbo,
              bound, error: gl.getError(), nextError: gl.getError()});
          }
          gl.pixelStorei(gl.PACK_ROW_LENGTH, 10); gl.pixelStorei(gl.PACK_SKIP_ROWS, 1); gl.pixelStorei(gl.PACK_SKIP_PIXELS, 1);
          const packed = new Uint8Array(400).fill(165);
          gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, packed);
          gl.pixelStorei(gl.PACK_ROW_LENGTH, 0); gl.pixelStorei(gl.PACK_SKIP_ROWS, 0); gl.pixelStorei(gl.PACK_SKIP_PIXELS, 0);
          const buffer = gl.createBuffer();
          if (!buffer) throw new Error('Framebuffer PBO allocation failed');
          let pbo, packBinding;
          try {
            gl.bindBuffer(gl.PIXEL_PACK_BUFFER, buffer);
            gl.bufferData(gl.PIXEL_PACK_BUFFER, new Uint8Array(pixels.length + 32).fill(165), gl.STREAM_READ);
            gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, 12);
            packBinding = gl.getParameter(gl.PIXEL_PACK_BUFFER_BINDING) === buffer;
            const output = new Uint8Array(pixels.length + 32);
            gl.getBufferSubData(gl.PIXEL_PACK_BUFFER, 0, output); pbo = Array.from(output);
          } finally { gl.bindBuffer(gl.PIXEL_PACK_BUFFER, null); gl.deleteBuffer(buffer); }
          return {width: gl.getRenderbufferParameter(gl.RENDERBUFFER, gl.RENDERBUFFER_WIDTH),
            height: gl.getRenderbufferParameter(gl.RENDERBUFFER, gl.RENDERBUFFER_HEIGHT),
            pixels: Array.from(pixels), repeat: Array.from(repeat), crop: Array.from(crop),
            packed: Array.from(packed), pbo, packBinding, boundaryReads,
            bindings: {read: gl.getParameter(gl.READ_FRAMEBUFFER_BINDING) === framebuffer,
              draw: gl.getParameter(gl.DRAW_FRAMEBUFFER_BINDING) === framebuffer,
              selected: gl.getParameter(gl.READ_BUFFER) === gl.COLOR_ATTACHMENT1}, error: gl.getError()};
        };
        try {
          gl.bindFramebuffer(gl.FRAMEBUFFER, framebuffer);
          gl.bindRenderbuffer(gl.RENDERBUFFER, first);
          gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.RENDERBUFFER, first);
          gl.bindRenderbuffer(gl.RENDERBUFFER, second);
          gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT1, gl.RENDERBUFFER, second);
          gl.drawBuffers([gl.COLOR_ATTACHMENT0, gl.COLOR_ATTACHMENT1]);
          fill(8, 8); const initial = read(8, 8);
          gl.readBuffer(gl.COLOR_ATTACHMENT0);
          const uniform = new Uint8Array(4);
          gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, uniform);
          fill(6, 5); const resized = read(6, 5);
          gl.bindFramebuffer(gl.FRAMEBUFFER, multiFramebuffer);
          gl.bindRenderbuffer(gl.RENDERBUFFER, multi);
          gl.renderbufferStorageMultisample(gl.RENDERBUFFER, 1, gl.RGBA8, 4, 4);
          gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.RENDERBUFFER, multi);
          gl.drawBuffers([gl.COLOR_ATTACHMENT0]); gl.readBuffer(gl.COLOR_ATTACHMENT0);
          if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) throw new Error('Multisample framebuffer incomplete');
          const samples = gl.getRenderbufferParameter(gl.RENDERBUFFER, gl.RENDERBUFFER_SAMPLES);
          const rejected = new Uint8Array(4).fill(165);
          gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, rejected);
          const multisample = {error: gl.getError(), nextError: gl.getError(), pixels: Array.from(rejected)};
          scene.renderbuffer = {viewport, initial, resized, uniform: Array.from(uniform), samples, multisample};
        } finally {
          gl.disable(gl.SCISSOR_TEST); gl.scissor(...scissor);
          gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.readBuffer(gl.BACK); gl.drawBuffers([gl.BACK]);
          gl.bindRenderbuffer(gl.RENDERBUFFER, null); gl.bindBuffer(gl.PIXEL_PACK_BUFFER, null);
          gl.pixelStorei(gl.PACK_ROW_LENGTH, 6); gl.pixelStorei(gl.PACK_SKIP_ROWS, 1); gl.pixelStorei(gl.PACK_SKIP_PIXELS, 1);
          for (const buffer of [first, second, multi]) gl.deleteRenderbuffer(buffer);
          gl.deleteFramebuffer(framebuffer); gl.deleteFramebuffer(multiFramebuffer);
        }
      }
"""
READBACK_READ = READBACK_READ.replace(
    "      scene.initialState = beforeExport;", "      scene.initialState = beforeExport;" + RENDERBUFFER_READ)


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


def validate_readback(observed: dict, *, protected: bool, baseline: dict | None = None,
                      derivation_mode: str = "partitioned-privacy", previous: dict | None = None) -> dict:
    if not isinstance(derivation_mode, str) or derivation_mode not in {
            "partitioned-privacy", "profile-identity"}:
        raise ValueError("Unknown WebGL readback derivation mode")
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
                      "exportState", "initialState", "validation", "lost", "renderbuffer"}
            if not isinstance(scene, dict) or set(scene) != fields:
                raise ValueError("Readback/export/state observations are incomplete")
            full = scene["pixels"]
            read_scene = {key: scene[key] for key in ("pixels", "repeat", "crop", "pbo", "packed")}
            validate_shader_readback(read_scene, api, expected_pixels=full)
            validate_errors(scene["validation"], api, full[:4], scene["lost"])
            if api == "webgl2":
                try:
                    validate_renderbuffer(scene["renderbuffer"], protected=protected)
                except ValueError as error:
                    raise ValueError(f"{context}/{api}/renderbuffer: {error}") from error
            elif scene["renderbuffer"] is not None:
                raise ValueError("WebGL1 claimed WebGL2 renderbuffer coverage")
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
        stable_identity = derivation_mode == "profile-identity"
        contexts = CONTEXTS if stable_identity else SAME_PARTITION
        if any(row["webgl"]["webgl"]["scene"]["pixels"] != row["webgl"]["webgl2"]["scene"]["pixels"]
               for row in observed.values()):
            raise ValueError("WebGL1 and WebGL2 surface domains disagree")
        for api in ("webgl", "webgl2"):
            reference = observed["document"]["webgl"][api]["scene"]["pixels"]
            if reference == SHADER_PIXELS:
                raise ValueError("Protected readback did not change the nonuniform scene")
            if any(observed[name]["webgl"][api]["scene"]["pixels"] != reference for name in contexts):
                raise ValueError("Profile identity WebGL contexts disagree" if stable_identity
                                 else "Same-partition WebGL contexts disagree")
            if not stable_identity and observed["cross_origin_frame"]["webgl"][api]["scene"]["pixels"] == reference:
                raise ValueError("Cross-origin WebGL partition was not isolated")
        for phase in ("initial", "resized"):
            pixels = {name: row["webgl"]["webgl2"]["scene"]["renderbuffer"][phase]["pixels"]
                      for name, row in observed.items()}
            reference = pixels["document"]
            if any(pixels[name] != reference for name in contexts):
                raise ValueError("Profile identity renderbuffer contexts disagree" if stable_identity
                                 else "Same-partition renderbuffer contexts disagree")
            if not stable_identity and pixels["cross_origin_frame"] == reference:
                raise ValueError("Cross-origin renderbuffer partition was not isolated")
    if previous is not None:
        validate_readback(previous, protected=protected, baseline=baseline, derivation_mode=derivation_mode)
        if restart_state(observed) != restart_state(previous):
            raise ValueError("Readback/export/metadata changed across profile restart")
    return normalized


def validate_profile_isolation(baseline: dict, first: dict, second: dict, *,
                               derivation_mode: str = "partitioned-privacy") -> None:
    normalized = validate_readback(baseline, protected=False, derivation_mode=derivation_mode)
    validate_readback(first, protected=True, baseline=normalized, derivation_mode=derivation_mode)
    validate_readback(second, protected=True, baseline=normalized, derivation_mode=derivation_mode)
    for context in CONTEXTS:
        for api in ("webgl", "webgl2"):
            pixels = [tuple(row[context]["webgl"][api]["scene"]["pixels"])
                      for row in (baseline, first, second)]
            if len(set(pixels)) != 3:
                raise ValueError("WebGL scene did not isolate both profiles from baseline")
        for phase in ("initial", "resized"):
            pixels = [tuple(row[context]["webgl"]["webgl2"]["scene"]["renderbuffer"][phase]["pixels"])
                      for row in (baseline, first, second)]
            if len(set(pixels)) != 3:
                raise ValueError("Renderbuffer scene did not isolate both profiles from baseline")


def validate_renderbuffer(observed: dict, *, protected: bool) -> None:
    if (not isinstance(observed, dict) or set(observed) != {"viewport", "initial", "resized", "uniform", "samples", "multisample"}
            or observed["viewport"] != [0, 0, 4, 4] or any(type(value) is not int for value in observed["viewport"])
            or observed["uniform"] != [17, 34, 51, 255] or any(type(value) is not int for value in observed["uniform"])
            or type(observed["samples"]) is not int or observed["samples"] < 1):
        raise ValueError("Renderbuffer setup or uniform attachment changed")
    palette = {}
    for name, width, height in (("initial", 8, 8), ("resized", 6, 5)):
        frame = observed[name]
        fields = {"width", "height", "pixels", "repeat", "crop", "packed", "pbo", "packBinding", "bindings", "error", "boundaryReads"}
        if (not isinstance(frame, dict) or set(frame) != fields or type(frame["width"]) is not int or frame["width"] != width
                or type(frame["height"]) is not int or frame["height"] != height or type(frame["error"]) is not int or frame["error"] != 0
                or frame["packBinding"] is not True or not isinstance(frame["bindings"], dict)
                or set(frame["bindings"]) != {"read", "draw", "selected"} or any(value is not True for value in frame["bindings"].values())):
            raise ValueError("Selected framebuffer extent, bindings or operation failed: " + name)
        full = frame["pixels"]
        reference = [value for y in range(1, height + 1) for x in range(1, width + 1) for value in (x, y, 85, 255)]
        if (not isinstance(full, list) or len(full) != len(reference)
                or any(type(byte) is not int or not 0 <= byte <= 255 for byte in full)
                or any((byte != expected if not protected or index % 4 == 3 else byte >> 1 != expected >> 1)
                       for index, (byte, expected) in enumerate(zip(full, reference)))):
            raise ValueError("Renderbuffer pixels changed alpha, upper colour bits or baseline")
        row_bytes = width * 4
        expected = {"repeat": full, "crop": full[row_bytes + 4:row_bytes + 12] + full[row_bytes * 2 + 4:row_bytes * 2 + 12],
                    "pbo": [165] * 12 + full + [165] * 20, "packed": [165] * 400}
        for row in range(height):
            start = (row + 1) * 40 + 4
            expected["packed"][start:start + row_bytes] = full[row * row_bytes:(row + 1) * row_bytes]
        for field, value in expected.items():
            actual = frame[field]
            if (not isinstance(actual, list) or any(type(byte) is not int for byte in actual) or actual != value):
                raise ValueError("Renderbuffer repeat/crop/PBO/pack padding mismatch: " + field)
        if protected and full == reference:
            raise ValueError("Renderbuffer readback was not protected")
        try:
            validate_boundary_reads(frame["boundaryReads"], full, width, height)
        except ValueError as error:
            raise ValueError(f"{name}: {error}") from error
        if protected:
            # Every pixel in this opaque two-pixel colour-cell gradient has a
            # different quantized neighbour. The candidate therefore selects
            # one RGB value per quantized colour, also across the resize.
            # Merely changing a viewport-sized prefix cannot satisfy this.
            for offset in range(0, len(full), 4):
                colour = tuple(byte >> 1 for byte in reference[offset:offset + 3])
                chosen = tuple(full[offset:offset + 3])
                if colour in palette and palette[colour] != chosen:
                    raise ValueError("Renderbuffer colour policy is inconsistent outside viewport or after resize")
                palette[colour] = chosen
    multi = observed["multisample"]
    if (not isinstance(multi, dict) or set(multi) != {"error", "nextError", "pixels"}
            or type(multi["error"]) is not int or type(multi["nextError"]) is not int
            or not isinstance(multi["pixels"], list) or any(type(byte) is not int for byte in multi["pixels"])
            or multi != {"error": 1282, "nextError": 0, "pixels": [165] * 4}):
        raise ValueError("Multisample read did not preserve native rejection and destination")


def validate_boundary_reads(observed: list, full: list[int], width: int, height: int) -> None:
    bounds = [[0, 0, 1, 1], [-1, -1, 2, 2], [width - 1, height - 1, 2, 2],
              [-4, -4, 2, 2], [width + 1, height + 1, 2, 2], [1, 1, 0, 2]]
    if not isinstance(observed, list) or len(observed) != len(bounds):
        raise ValueError("Framebuffer boundary cases are incomplete")
    for actual, request in zip(observed, bounds):
        x, y, w, h = request
        expected = [165] * max(4, w * h * 4)
        for row in range(h):
            for column in range(w):
                target = (row * w + column) * 4
                if 0 <= x + column < width and 0 <= y + row < height:
                    source = ((y + row) * width + x + column) * 4
                    expected[target:target + 4] = full[source:source + 4]
        stride = ((w + 2) * 4 + 7) // 8 * 8
        packed = [165] * (32 + (h + 2) * stride)
        for row in range(h):
            start = (row + 1) * stride + 4
            packed[start:start + w * 4] = expected[row * w * 4:(row + 1) * w * 4]
        if (not isinstance(actual, dict) or set(actual) != {"bounds", "cpu", "pbo", "packedCpu", "packedPbo", "bound", "error", "nextError"}
                or actual["bound"] is not True or type(actual["error"]) is not int or actual["error"] != 0
                or type(actual["nextError"]) is not int or actual["nextError"] != 0
                or any(not isinstance(actual[field], list) or any(type(value) is not int for value in actual[field])
                       for field in ("bounds", "cpu", "pbo", "packedCpu", "packedPbo"))
                or actual["bounds"] != request or actual["cpu"] != expected
                or actual["pbo"] != [165] * 12 + expected + [165] * 20
                or actual["packedCpu"] != packed or actual["packedPbo"] != [165] * 12 + packed + [165] * 20):
            raise ValueError("Framebuffer boundary read changed pixels, padding, binding or errors: " + str(request))


def validate_errors(observed: dict, api: str, first_pixel: list[int], lost: dict) -> None:
    expected = {
        name: {"error": error, "nextError": 0, "pixels": [165] * length}
        for name, error, length in (
            ("zero", 0, 4), ("negative", 1281, 4), ("short", 1282, 3),
            ("wrongType", 1282, 2), ("invalidFormat", 1280, 4), ("incomplete", 1286, 4))}
    expected["pending"] = {"error": 1280, "nextError": 0, "pixels": first_pixel}
    expected["noPackBuffer"] = {"error": 1282, "nextError": 0} if api == "webgl2" else None
    expected["overlappingPack"] = {"error": 1282, "nextError": 0, "pixels": [165] * 8} if api == "webgl2" else None
    if not isinstance(observed, dict) or set(observed) != set(expected):
        raise ValueError("Readback error fixtures are incomplete")
    for name, reference in expected.items():
        value = observed[name]
        if reference is None:
            if value is not None:
                raise ValueError("WebGL1 claimed WebGL2 error coverage")
            continue
        if (not isinstance(value, dict) or set(value) != set(reference)
                or type(value["error"]) is not int or type(value["nextError"]) is not int
                or ("pixels" in reference and (not isinstance(value["pixels"], list)
                    or any(type(byte) is not int for byte in value["pixels"]))) or value != reference):
            raise ValueError("Readback error semantics or untouched destination changed: " + name)
    if (not isinstance(lost, dict) or set(lost) != {"lost", "error", "nextError", "pixels"}
            or lost["lost"] is not True or type(lost["error"]) is not int or type(lost["nextError"]) is not int
            or not isinstance(lost["pixels"], list) or any(type(byte) is not int for byte in lost["pixels"])
            or lost != {"lost": True, "error": 37442, "nextError": 0, "pixels": [165] * 4}):
        raise ValueError("Lost-context read changed destination or error semantics")


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
                normalized = validate_readback(observed, protected=protected, baseline=baseline, previous=previous)
                previous = observed
                if baseline is None:
                    baseline = normalized
                results[name] = observed
                check["passed"] = True
            finally:
                await runtime.close()
    validate_profile_isolation(results["baseline"], results["profile-a"], results["profile-b"])
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
