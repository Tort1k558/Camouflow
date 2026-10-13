import hashlib
import math
import struct

import pytest

from scripts.verify_native_audio_quality import FRAMES, compare_samples, strip_quality
from scripts import verify_native_audio_scalar as scalar


def row(bits, elapsed=2):
    digest = hashlib.sha256(struct.pack(f"<{FRAMES}I", *bits)).hexdigest()
    return {"document": {"available": True, **{
        phase: {"hash": digest, "sampleBits": list(bits), "renderMilliseconds": elapsed}
        for phase in ("signal", "repeat", "silence")}}}


@pytest.mark.parametrize("mutation", [None, "missing", "duplicate", "skip", "failure", "foreign", "boolean"])
def test_audio_scalar_requires_exact_completed_native_cases(mutation):
    cases = [{"name": name, "status": "RUN", "result": "COMPLETED"} for name in sorted(scalar.CASES)]
    result = {"tests": len(cases), "failures": 0, "disabled": 0,
              "testsuites": [{"name": scalar.SUITE, "testsuite": cases}]}
    if mutation == "missing":
        cases.pop()
    elif mutation == "duplicate":
        cases[-1] = cases[0]
    elif mutation == "skip":
        cases[0]["result"] = "SKIPPED"
    elif mutation == "failure":
        cases[0]["failures"] = [{"failure": "actual error"}]
    elif mutation == "foreign":
        result["testsuites"][0]["name"] = "GlintReadbackMetadataTest"
    elif mutation == "boolean":
        result["failures"] = False
    if mutation:
        with pytest.raises(ValueError):
            scalar.validate_results(result, required_cases=scalar.CASES, suite_name=scalar.SUITE, label="Audio scalar")
    else:
        scalar.validate_results(result, required_cases=scalar.CASES, suite_name=scalar.SUITE, label="Audio scalar")


@pytest.mark.parametrize("suffix", [".obj", ".o"])
def test_audio_crypto_snapshot_accepts_measured_native_objects(tmp_path, suffix):
    crypto = tmp_path / "crypto"
    crypto.mkdir()
    member = crypto / ("native" + suffix)
    member.write_bytes(b"COFF")
    assert scalar.archive_member_path(crypto, member.name) == member


@pytest.mark.parametrize("name", ["../outside.obj", "nested/../native.obj", "native.lib", "", "missing.obj"])
def test_audio_crypto_snapshot_rejects_escape_and_nonobjects(tmp_path, name):
    crypto = tmp_path / "crypto"
    crypto.mkdir()
    (crypto / "native.obj").write_bytes(b"COFF")
    (crypto / "native.lib").write_bytes(b"archive")
    (tmp_path / "outside.obj").write_bytes(b"COFF")
    with pytest.raises(ValueError):
        scalar.archive_member_path(crypto, name)


def test_audio_crypto_snapshot_rejects_absolute_member(tmp_path):
    member = tmp_path / "native.obj"
    member.write_bytes(b"COFF")
    with pytest.raises(ValueError):
        scalar.archive_member_path(tmp_path, str(member))


def test_measured_one_bit_error_and_snr():
    result = compare_samples([0x3e800000] * FRAMES, [0x3e800001] * FRAMES)
    assert result["changed_samples"] == FRAMES
    assert result["max_absolute_error"] == 2 ** -25
    assert result["signal_to_noise_db"] == pytest.approx(138.47379800543135)
    assert result["single_mantissa_bit_budget_passed"] is True


def test_signed_silence_is_exact_and_no_fake_infinite_snr():
    samples = [0, 0x80000000] * (FRAMES // 2)
    result = compare_samples(samples, samples, silence=True)
    assert result["changed_samples"] == 0
    assert result["signal_to_noise_db"] is None


@pytest.mark.parametrize("value", [0, 0x80000000, 1, 0x80000001, 0x3f800000, 0xbf800000])
def test_preserved_classes_cannot_change(value):
    before = [0x3e800000] * FRAMES
    after = [0x3e800001] * FRAMES
    before[0], after[0] = value, value ^ 1
    with pytest.raises(ValueError, match="preserved"):
        compare_samples(before, after)


@pytest.mark.parametrize("value", [0x7f800000, 0xff800000, 0x7fc00001])
def test_nonfinite_owned_fixture_cannot_pass(value):
    with pytest.raises(ValueError, match="non-finite"):
        compare_samples([value] * FRAMES, [value] * FRAMES)


def test_no_masking_or_excessive_error_cannot_pass():
    with pytest.raises(ValueError, match="did not change"):
        compare_samples([0x3e800000] * FRAMES, [0x3e800000] * FRAMES)
    with pytest.raises(ValueError, match="mantissa bit"):
        compare_samples([0x3e800000] * FRAMES, [0x3e800002] * FRAMES)


@pytest.mark.parametrize("value", [True, -1, 2 ** 32, 0.25])
def test_malformed_bits_cannot_pass(value):
    samples = [value] * FRAMES
    with pytest.raises(ValueError):
        compare_samples(samples, samples)
    with pytest.raises(ValueError):
        strip_quality({"document": {"available": True, "signal": {
            "sampleBits": samples, "renderMilliseconds": 1}}})


@pytest.mark.parametrize("elapsed", [True, -1, math.nan, math.inf, None])
def test_invalid_timing_cannot_pass(elapsed):
    with pytest.raises(ValueError, match="duration"):
        strip_quality(row([0] * FRAMES, elapsed))


def test_float_bits_are_bound_to_measured_digest():
    observed = row([0x3e800000] * FRAMES)
    clean = strip_quality(observed)
    assert "sampleBits" not in clean["document"]["signal"]
    assert "renderMilliseconds" not in clean["document"]["signal"]
    assert "sampleBits" in observed["document"]["signal"]
    observed["document"]["signal"]["sampleBits"][0] ^= 1
    with pytest.raises(ValueError, match="digest"):
        strip_quality(observed)
