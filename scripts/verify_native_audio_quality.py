"""Validate measured OfflineAudio samples against the unprotected browser baseline."""

from __future__ import annotations

import copy
import hashlib
import math
import struct

PHASES = ("signal", "repeat", "silence")
FRAMES = 4096


def strip_quality(observed: dict) -> dict:
    """Bind actual float bits to the existing digest before validating API semantics."""
    clean = copy.deepcopy(observed)
    for name, values in clean.items():
        if not isinstance(values, dict) or type(values.get("available")) is not bool:
            raise ValueError(f"Invalid Audio availability: {name}")
        if not values["available"]:
            continue
        for phase in PHASES:
            result = values.get(phase)
            if not isinstance(result, dict):
                raise TypeError(f"Missing Audio quality phase: {name}/{phase}")
            bits = result.pop("sampleBits", None)
            elapsed = result.pop("renderMilliseconds", None)
            if (not isinstance(bits, list) or len(bits) != FRAMES
                    or any(type(value) is not int or not 0 <= value <= 0xffffffff for value in bits)):
                raise ValueError(f"Invalid measured float bits: {name}/{phase}")
            if (type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0):
                raise ValueError(f"Invalid measured render duration: {name}/{phase}")
            packed = struct.pack(f"<{FRAMES}I", *bits)
            if hashlib.sha256(packed).hexdigest() != result.get("hash"):
                raise ValueError(f"Audio sample bits do not match the measured digest: {name}/{phase}")
    return clean


def compare_samples(baseline: list[int], protected: list[int], *, silence: bool = False) -> dict:
    if (not isinstance(baseline, list) or not isinstance(protected, list)
            or len(baseline) != FRAMES or len(protected) != FRAMES
            or any(type(value) is not int or not 0 <= value <= 0xffffffff
                   for row in (baseline, protected) for value in row)):
        raise ValueError("Audio quality requires exactly 4096 measured float32 samples")
    changed = 0
    max_error = 0.0
    noise_power = signal_power = 0.0
    for before, after in zip(baseline, protected, strict=True):
        magnitude = before & 0x7fffffff
        exponent = magnitude & 0x7f800000
        preserve = exponent in (0, 0x7f800000) or magnitude >= 0x3f800000
        if (preserve or silence) and before != after:
            raise ValueError("Audio changed a preserved sample or signed silence")
        if (before ^ after) not in (0, 1):
            raise ValueError("Audio perturbation exceeded the single mantissa bit budget")
        left = struct.unpack("<f", struct.pack("<I", before))[0]
        right = struct.unpack("<f", struct.pack("<I", after))[0]
        if not math.isfinite(left) or not math.isfinite(right):
            raise ValueError("Owned Audio fixture produced non-finite samples")
        if silence and left != 0:
            raise ValueError("Silent Audio fixture contains a nonzero sample")
        changed += before != after
        error = abs(left - right)
        max_error = max(max_error, error)
        noise_power += error * error
        signal_power += left * left
    if not silence and (changed == 0 or signal_power == 0 or noise_power == 0):
        raise ValueError("Protected Audio did not change the measured nonzero signal")
    snr = 10 * math.log10(signal_power / noise_power) if noise_power else None
    if snr is not None and snr < 130:
        raise ValueError("Audio signal-to-noise ratio is below the 130 dB quality budget")
    return {"frames": FRAMES, "changed_samples": changed, "max_absolute_error": max_error,
            "signal_to_noise_db": snr, "single_mantissa_bit_budget_passed": True}


def compare_quality(baseline: dict, protected: dict) -> dict:
    strip_quality(baseline)
    strip_quality(protected)
    if set(baseline) != set(protected):
        raise ValueError("Audio quality context coverage changed")
    metrics = {}
    for name, original in baseline.items():
        candidate = protected[name]
        if original["available"] != candidate["available"]:
            raise ValueError("Audio quality capability changed")
        if not original["available"]:
            continue
        metrics[name] = {}
        for phase in PHASES:
            metric = compare_samples(original[phase]["sampleBits"], candidate[phase]["sampleBits"],
                                     silence=phase == "silence")
            metric.update(baseline_render_ms=original[phase]["renderMilliseconds"],
                          protected_render_ms=candidate[phase]["renderMilliseconds"])
            metrics[name][phase] = metric
    return metrics
