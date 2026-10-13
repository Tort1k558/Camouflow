from __future__ import annotations

import copy
import json
import sys

import pytest

from scripts.verify_native_gpu import (
    CONTEXTS,
    WEBGL_LIMITS,
    WEBGPU_LIMITS,
    validate_observations,
    validate_shader_readback,
)


def observation(*, minimized=False, webgpu=True):
    gl = {"available": True, "extensions": ["EXT_color_buffer_float"], "debug": False,
          "vendor": None, "renderer": None, "unavailableParameter": {"value": None, "error": 1280},
          "pixels": [17, 34, 51, 255], "error": 0, "contextLost": False,
          "limits": dict.fromkeys(WEBGL_LIMITS, 16), "debugShaders": False, "translatedShaderLength": 0}
    if not minimized:
        gl.update(extensions=["EXT_color_buffer_float", "WEBGL_debug_renderer_info", "WEBGL_debug_shaders"], debug=True,
                  debugShaders=True, translatedShaderLength=256,
                  vendor="Actual vendor", renderer="Actual renderer", unavailableParameter=None)
    info = {"vendor": "", "architecture": "", "device": "", "description": "",
            "subgroupMinSize": 4, "subgroupMaxSize": 32, "isFallbackAdapter": False}
    if not minimized:
        info.update(vendor="actual", architecture="actual", device="actual", description="actual")
    gpu = {"available": True, "info": info, "repeat": copy.deepcopy(info), "deviceInfo": copy.deepcopy(info),
           "features": ["depth-clip-control"], "limits": dict.fromkeys(WEBGPU_LIMITS, 256),
           "roundtrip": [17, 34, 51, 255], "compute": [18, 35, 52, 256], "validationError": None, "errors": []}
    if not webgpu:
        gpu = {"available": False, "reason": "No adapter"}
    full = [value for y in range(1, 5) for x in range(1, 5) for value in (x, y, 85, 255)]
    cropped = [value for y in range(2, 4) for x in range(2, 4) for value in (x, y, 85, 255)]
    packed = [165] * 120
    for row in range(4):
        start = (row + 1) * 24 + 4
        packed[start:start + 16] = full[row * 16:(row + 1) * 16]
    variants = {}
    for api in ("webgl", "webgl2"):
        variants[api] = copy.deepcopy(gl)
        variants[api]["scene"] = {"pixels": full.copy(), "repeat": full.copy(), "crop": cropped.copy(),
            "pbo": [165] * 12 + full + [165] * 8 if api == "webgl2" else None,
            "packed": packed.copy() if api == "webgl2" else None}
    return {name: {"webgl": copy.deepcopy(variants), "webgpu": copy.deepcopy(gpu)} for name in CONTEXTS}


def test_baseline_and_minimized_preserve_capabilities():
    baseline = observation()
    assert validate_observations(baseline) == {"webgl": 8, "webgl2": 8, "webgpu": 8}
    assert validate_observations(observation(minimized=True), minimized=True, baseline=baseline) == {
        "webgl": 8, "webgl2": 8, "webgpu": 8}


def test_unavailable_webgpu_is_not_counted_as_coverage():
    assert validate_observations(observation(webgpu=False))["webgpu"] == 0


@pytest.mark.parametrize("field,index,value", [
    ("pixels", 0, 2), ("repeat", 0, 2), ("crop", 0, 0),
    ("pbo", 0, 0), ("pbo", 12, 0), ("pbo", 83, 0),
    ("packed", 0, 0), ("packed", 28, 0), ("packed", 119, 0),
    ("pixels", 0, True),
])
def test_shader_readback_and_untouched_padding_cannot_be_corrupted(field, index, value):
    observed = observation()
    observed["document"]["webgl"]["webgl2"]["scene"][field][index] = value
    with pytest.raises(ValueError, match="readback mismatch"):
        validate_observations(observed)


def test_webgl1_cannot_claim_webgl2_pack_operations():
    observed = observation()
    observed["document"]["webgl"]["webgl"]["scene"]["pbo"] = []
    with pytest.raises(ValueError, match="WebGL1 claimed"):
        validate_observations(observed)


def test_unknown_webgl_variant_cannot_pass_readback_validation():
    scene = observation()["document"]["webgl"]["webgl"]["scene"]
    with pytest.raises(ValueError, match="Unknown WebGL"):
        validate_shader_readback(scene, "webgl3")


@pytest.mark.parametrize("field,value", [("debugShaders", True), ("translatedShaderLength", 8),
                                        ("translatedShaderLength", True), ("translatedShaderLength", -1)])
def test_translated_shader_debug_metadata_cannot_leak_in_minimized_mode(field, value):
    observed = observation(minimized=True)
    observed["document"]["webgl"]["webgl"][field] = value
    with pytest.raises(ValueError):
        validate_observations(observed, minimized=True)


@pytest.mark.parametrize("field,value", [
    ("pixels", [0, 0, 0, 0]), ("error", 1282), ("contextLost", True),
    ("available", 1), ("debug", 0), ("extensions", ["WEBGL_debug_renderer_info"]),
    ("unavailableParameter", {"value": None, "error": 0}), ("vendor", "leak"),
    ("limits", {}),
])
def test_rejects_invalid_webgl(field, value):
    observed = observation(minimized=True)
    observed["document"]["webgl"]["webgl"][field] = value
    with pytest.raises(ValueError):
        validate_observations(observed, minimized=True)


@pytest.mark.parametrize("field,value", [
    ("roundtrip", [0, 0, 0, 0]), ("compute", [0, 0, 0, 0]), ("validationError", "Validation failed"),
    ("errors", ["Device lost"]), ("available", 1), ("features", [1]),
    ("limits", {}), ("repeat", {}), ("deviceInfo", {}),
])
def test_rejects_invalid_webgpu(field, value):
    observed = observation(minimized=True)
    observed["document"]["webgpu"][field] = value
    with pytest.raises(ValueError):
        validate_observations(observed, minimized=True)


@pytest.mark.parametrize("api", ["webgl", "webgl2", "webgpu"])
def test_rejects_lost_baseline_capability(api):
    observed = observation(minimized=True)
    target = observed["document"]["webgpu"] if api == "webgpu" else observed["document"]["webgl"][api]
    target.update(available=False, reason="Unavailable")
    with pytest.raises(ValueError):
        validate_observations(observed, minimized=True, baseline=observation())


def test_minimized_rejects_ignored_feature_flag():
    with pytest.raises(ValueError):
        validate_observations(observation(), minimized=True)


def test_missing_context_and_all_unavailable_cannot_pass():
    observed = observation()
    del observed["document"]
    with pytest.raises(ValueError):
        validate_observations(observed)
    observed = observation()
    for value in observed.values():
        value["webgl"] = {api: {"available": False} for api in ("webgl", "webgl2")}
    with pytest.raises(ValueError):
        validate_observations(observed)


def test_changed_capability_is_not_accepted():
    observed = observation(minimized=True)
    observed["document"]["webgpu"]["limits"]["maxBufferSize"] += 1
    with pytest.raises(ValueError):
        validate_observations(observed, minimized=True, baseline=observation())


def test_gpu_cli_preserves_existing_evidence(tmp_path, monkeypatch):
    from scripts import verify_native_gpu as gpu

    report = tmp_path / "existing.json"
    report.write_text("existing evidence", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["probe", "--executable", str(tmp_path / "chrome.exe"),
                                     "--work-dir", str(tmp_path / "owned"), "--report", str(report)])
    with pytest.raises(SystemExit) as failure:
        gpu.main()
    assert failure.value.code == 2
    assert report.read_text(encoding="utf-8") == "existing evidence"


def test_gpu_cli_records_failure_without_admission(tmp_path, monkeypatch):
    from scripts import verify_native_gpu as gpu

    report = tmp_path / "failed.json"
    monkeypatch.setattr(sys, "argv", ["probe", "--executable", str(tmp_path / "missing.exe"),
                                     "--work-dir", str(tmp_path / "owned"), "--report", str(report)])
    assert gpu.main() == 1
    evidence = json.loads(report.read_text(encoding="utf-8"))
    assert evidence["passed"] is False and evidence["privacy_admitted"] is False
    assert evidence["error"] and not evidence["checks"]


def readback_observation(*, protected=False):
    from PyQt6.QtCore import QBuffer, QIODevice
    from PyQt6.QtGui import QColor, QImage

    observed = observation()
    for name, row in observed.items():
        for api, gl in row["webgl"].items():
            scene = gl["scene"]
            full = scene["pixels"]
            if protected:
                full = [byte ^ (int(name != "cross_origin_frame") if index % 4 == 0 else int(index % 4 == 1))
                        for index, byte in enumerate(full)]
            scene.update(pixels=full, repeat=full.copy(), crop=full[20:28] + full[36:44])
            if api == "webgl2":
                scene["pbo"] = [165] * 12 + full + [165] * 8
                for y in range(4):
                    start = (y + 1) * 24 + 4
                    scene["packed"][start:start + 16] = full[y * 16:(y + 1) * 16]
            image = QImage(4, 4, QImage.Format.Format_RGBA8888)
            for y in range(4):
                for x in range(4):
                    offset = (y * 4 + x) * 4
                    image.setPixelColor(x, 3 - y, QColor(*full[offset:offset + 4]))
            buffer = QBuffer()
            assert buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            assert image.save(buffer, "PNG")
            scene["png"] = list(bytes(buffer.data()))
            initial = {"alignment": 4, "framebuffer": True, "rowLength": 0,
                       "skipRows": 0, "skipPixels": 0, "packBound": False}
            scene["initialState"] = initial
            scene["packState"] = {**initial, "rowLength": 6, "skipRows": 1, "skipPixels": 1} if api == "webgl2" else initial.copy()
            scene["exportState"] = scene["packState"].copy()
            scene["validation"] = {
                case: {"error": error, "nextError": 0, "pixels": [165] * count}
                for case, error, count in (("zero", 0, 4), ("negative", 1281, 4), ("short", 1282, 3),
                    ("wrongType", 1282, 2), ("invalidFormat", 1280, 4), ("incomplete", 1286, 4))}
            scene["validation"].update(pending={"error": 1280, "nextError": 0, "pixels": full[:4]},
                noPackBuffer={"error": 1282, "nextError": 0} if api == "webgl2" else None,
                overlappingPack={"error": 1282, "nextError": 0, "pixels": [165] * 8} if api == "webgl2" else None)
            scene["lost"] = {"lost": True, "error": 37442, "nextError": 0, "pixels": [165] * 4}
            scene["renderbuffer"] = renderbuffer_observation(protected=protected, cross=name == "cross_origin_frame") if api == "webgl2" else None
    return observed


def renderbuffer_observation(*, protected=False, cross=False):
    result = {"viewport": [0, 0, 4, 4], "uniform": [17, 34, 51, 255], "samples": 4,
              "multisample": {"error": 1282, "nextError": 0, "pixels": [165] * 4}}
    for name, width, height in (("initial", 8, 8), ("resized", 6, 5)):
        full = [value for y in range(1, height + 1) for x in range(1, width + 1) for value in (x, y, 85, 255)]
        if protected:
            full = [byte if index % 4 == 3 else (byte & 254) | (int(not cross) if index % 4 == 0 else int(index % 4 == 1))
                    for index, byte in enumerate(full)]
        row_bytes = width * 4
        packed = [165] * 400
        for row in range(height):
            start = (row + 1) * 40 + 4
            packed[start:start + row_bytes] = full[row * row_bytes:(row + 1) * row_bytes]
        result[name] = {"width": width, "height": height, "error": 0, "pixels": full,
            "repeat": full.copy(), "crop": full[row_bytes + 4:row_bytes + 12] + full[2 * row_bytes + 4:2 * row_bytes + 12],
            "pbo": [165] * 12 + full + [165] * 20, "packed": packed, "packBinding": True,
            "bindings": {"read": True, "draw": True, "selected": True}}
    return result


def test_readback_gate_checks_native_png_without_canvas_remasking():
    from scripts.verify_native_gpu_readback import validate_readback

    baseline = validate_readback(readback_observation(), protected=False)
    assert validate_readback(readback_observation(protected=True), protected=True, baseline=baseline) == baseline


@pytest.mark.parametrize("value", [None, [], [True] * 33, [0] * 65537])
def test_readback_png_requires_bounded_typed_bytes(value):
    from scripts.verify_native_gpu_readback import decode_png

    with pytest.raises(ValueError):
        decode_png(value)


def test_readback_png_checks_dimensions_before_native_decoder(monkeypatch):
    from scripts import verify_native_gpu_readback as gate

    value = readback_observation()["document"]["webgl"]["webgl"]["scene"]["png"]
    value[16:20] = [127, 255, 255, 255]
    class ForbiddenDecoder:
        @staticmethod
        def fromData(*args):
            pytest.fail("Unbounded dimensions reached the native image decoder")
    monkeypatch.setattr(gate, "QImage", ForbiddenDecoder)
    with pytest.raises(ValueError, match="before decoding"):
        gate.decode_png(value)


@pytest.mark.parametrize("field,change", [
    ("pixels", lambda value: value.__setitem__(0, value[0] + 4)),
    ("pixels", lambda value: value.__setitem__(3, 254)),
    ("repeat", lambda value: value.__setitem__(0, value[0] ^ 1)),
    ("crop", lambda value: value.__setitem__(0, value[0] ^ 1)),
    ("pbo", lambda value: value.__setitem__(0, 0)),
    ("packed", lambda value: value.__setitem__(0, 0)),
    ("png", lambda value: value.__setitem__(0, 0)),
    ("packState", lambda value: value.__setitem__("alignment", 1)),
    ("exportState", lambda value: value.__setitem__("rowLength", 0)),
    ("initialState", lambda value: value.__setitem__("framebuffer", 1)),
])
def test_readback_gate_rejects_pixels_padding_export_and_state_corruption(field, change):
    from scripts.verify_native_gpu_readback import validate_readback

    observed = readback_observation(protected=True)
    change(observed["document"]["webgl"]["webgl2"]["scene"][field])
    with pytest.raises(ValueError):
        validate_readback(observed, protected=True)


def test_readback_gate_rejects_unprotected_runtime_and_partition_alias():
    from scripts.verify_native_gpu_readback import validate_readback

    with pytest.raises(ValueError):
        validate_readback(readback_observation(), protected=True)
    observed = readback_observation(protected=True)
    observed["cross_origin_frame"] = copy.deepcopy(observed["document"])
    with pytest.raises(ValueError):
        validate_readback(observed, protected=True)


def test_readback_restart_ignores_driver_debug_cache_length_but_not_pixels():
    from scripts.verify_native_gpu_readback import restart_state

    initial = readback_observation()
    restarted = copy.deepcopy(initial)
    restarted["document"]["webgl"]["webgl"]["translatedShaderLength"] = 10
    assert restart_state(initial) == restart_state(restarted)
    restarted["document"]["webgl"]["webgl"]["scene"]["pixels"][0] ^= 1
    assert restart_state(initial) != restart_state(restarted)


@pytest.mark.parametrize("case", ["zero", "negative", "short", "wrongType", "invalidFormat",
                                 "incomplete", "pending", "noPackBuffer", "overlappingPack"])
def test_readback_error_gate_requires_exact_errors_and_no_extra_pending_error(case):
    from scripts.verify_native_gpu_readback import validate_readback

    observed = readback_observation(protected=True)
    observed["document"]["webgl"]["webgl2"]["scene"]["validation"][case]["nextError"] = 1282
    with pytest.raises(ValueError):
        validate_readback(observed, protected=True)


@pytest.mark.parametrize("case", ["zero", "negative", "short", "wrongType", "invalidFormat",
                                 "incomplete", "overlappingPack"])
def test_readback_error_gate_rejects_destination_mutation_on_failure_or_empty_read(case):
    from scripts.verify_native_gpu_readback import validate_readback

    observed = readback_observation(protected=True)
    observed["document"]["webgl"]["webgl2"]["scene"]["validation"][case]["pixels"][0] = 0
    with pytest.raises(ValueError):
        validate_readback(observed, protected=True)


@pytest.mark.parametrize("field,value", [("lost", False), ("error", 0), ("nextError", 1282),
                                       ("pixels", [0] * 4), ("lost", 1), ("error", True)])
def test_readback_error_gate_rejects_lost_context_semantic_changes(field, value):
    from scripts.verify_native_gpu_readback import validate_readback

    observed = readback_observation(protected=True)
    observed["document"]["webgl"]["webgl2"]["scene"]["lost"][field] = value
    with pytest.raises(ValueError):
        validate_readback(observed, protected=True)


def test_readback_feature_merges_existing_partition_flag():
    from scripts.verify_native_gpu_readback import (
        READBACK_FEATURE,
        ReadbackConfiguration,
    )
    from scripts.verify_native_worker_startup import FEATURE_ARGUMENT

    arguments = ReadbackConfiguration(probe_mode="ready").launch_arguments()
    enabled = [argument for argument in arguments if argument.startswith("--enable-features=")]
    assert enabled == [FEATURE_ARGUMENT + "," + READBACK_FEATURE]
    assert FEATURE_ARGUMENT in ReadbackConfiguration().launch_arguments()


def test_readback_cli_rejects_old_receipt_before_creating_profiles(tmp_path, monkeypatch):
    from scripts import verify_native_gpu_readback as gpu

    executable = tmp_path / "chrome.exe"
    executable.write_bytes(b"not executed")
    monkeypatch.setattr(gpu, "measure_runtime_core", lambda path: {"chrome.exe": "fixture"})
    def reject_receipt(*args):
        raise ValueError("uncompiled readback")
    monkeypatch.setattr(gpu, "validate_receipt", reject_receipt)
    owned = tmp_path / "owned"
    report = tmp_path / "failed.json"
    monkeypatch.setattr(sys, "argv", ["probe", "--executable", str(executable),
                                     "--work-dir", str(owned), "--report", str(report)])
    assert gpu.main() == 1
    assert not owned.exists()
    evidence = json.loads(report.read_text(encoding="utf-8"))
    assert evidence["passed"] is False and evidence["privacy_admitted"] is False
    assert evidence["error"] == "uncompiled readback" and not evidence["checks"]


@pytest.mark.parametrize("field,value", [("width", 4), ("height", 4), ("width", True),
                                        ("packBinding", False), ("bindings", {"read": True, "draw": True, "selected": False}),
                                        ("error", 1282)])
def test_renderbuffer_gate_rejects_viewport_extent_and_binding_substitution(field, value):
    from scripts.verify_native_gpu_readback import validate_renderbuffer

    observed = renderbuffer_observation(protected=True)
    observed["initial"][field] = value
    with pytest.raises(ValueError):
        validate_renderbuffer(observed, protected=True)


@pytest.mark.parametrize("field,index", [("repeat", 0), ("crop", 0), ("packed", 0), ("packed", 399),
                                      ("pbo", 0), ("pbo", 287), ("pixels", 3)])
def test_renderbuffer_gate_rejects_mutated_reads_padding_or_alpha(field, index):
    from scripts.verify_native_gpu_readback import validate_renderbuffer

    observed = renderbuffer_observation(protected=True)
    observed["initial"][field][index] ^= 1
    with pytest.raises(ValueError):
        validate_renderbuffer(observed, protected=True)


def synchronize_renderbuffer_reads(frame):
    full = frame["pixels"]
    row_bytes = frame["width"] * 4
    frame.update(repeat=full.copy(), pbo=[165] * 12 + full + [165] * 20,
                 crop=full[row_bytes + 4:row_bytes + 12] + full[2 * row_bytes + 4:2 * row_bytes + 12],
                 packed=[165] * 400)
    for row in range(frame["height"]):
        start = (row + 1) * 40 + 4
        frame["packed"][start:start + row_bytes] = full[row * row_bytes:(row + 1) * row_bytes]


def test_renderbuffer_gate_rejects_protection_limited_to_viewport_even_when_reads_agree():
    from scripts.verify_native_gpu_readback import validate_renderbuffer

    observed = renderbuffer_observation(protected=True)
    raw = renderbuffer_observation()["initial"]["pixels"]
    frame = observed["initial"]
    for y in range(8):
        for x in range(8):
            if x >= 4 or y >= 4:
                offset = (y * 8 + x) * 4
                frame["pixels"][offset:offset + 4] = raw[offset:offset + 4]
    synchronize_renderbuffer_reads(frame)
    with pytest.raises(ValueError, match="outside viewport or after resize"):
        validate_renderbuffer(observed, protected=True)


def test_renderbuffer_gate_rejects_palette_rekey_after_resize_even_when_reads_agree():
    from scripts.verify_native_gpu_readback import validate_renderbuffer

    observed = renderbuffer_observation(protected=True)
    frame = observed["resized"]
    frame["pixels"] = [byte ^ int(index % 4 == 1) for index, byte in enumerate(frame["pixels"])]
    synchronize_renderbuffer_reads(frame)
    with pytest.raises(ValueError, match="outside viewport or after resize"):
        validate_renderbuffer(observed, protected=True)


@pytest.mark.parametrize("context,source", [("same_origin_frame", "cross_origin_frame"), ("cross_origin_frame", "document")])
def test_renderbuffer_gate_requires_own_partition_isolation(context, source):
    from scripts.verify_native_gpu_readback import validate_readback

    observed = readback_observation(protected=True)
    observed[context]["webgl"]["webgl2"]["scene"]["renderbuffer"] = copy.deepcopy(
        observed[source]["webgl"]["webgl2"]["scene"]["renderbuffer"])
    with pytest.raises(ValueError):
        validate_readback(observed, protected=True)


@pytest.mark.parametrize("field,value", [("samples", 0), ("samples", True), ("uniform", [0] * 4),
                                       ("multisample", {"error": 0, "nextError": 0, "pixels": [165] * 4})])
def test_renderbuffer_gate_rejects_missing_multisample_or_modified_uniform_attachment(field, value):
    from scripts.verify_native_gpu_readback import validate_renderbuffer

    observed = renderbuffer_observation(protected=True)
    observed[field] = value
    with pytest.raises(ValueError):
        validate_renderbuffer(observed, protected=True)
