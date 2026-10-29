import copy
import hashlib
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from scripts import verify_native_audio_compatibility as audio


def valid_observation(probe):
    if probe == "realtime":
        return {"schema": 1, "passed": True, "sampleRate": 48000, "errors": [],
                "checks": dict.fromkeys(audio.CHECKS[probe], True)}
    rows = []
    for rate in audio.RATES:
        graphs = audio.FIDELITY_GRAPHS if probe == "fidelity" else audio.GRAPHS
        for graph in graphs:
            for repetition in range(3 if probe == "fidelity" else 2):
                row = {"rate": rate, "repetition": repetition, "passed": True}
                if probe != "fidelity":
                    row.update(graph=graph, checks=dict.fromkeys(audio.CHECKS[probe], True))
                    if probe == "worklet":
                        row["packetCount"] = 16
                else:
                    row.update(kind=graph, frames=512, sampleRate=rate, channelCount=2,
                               closed=True, eventSameBuffer=True, copyMutationExact=True,
                               channels=[{"sha256": hashlib.sha256(f"{rate}-{graph}-{channel if graph == 'stereo' else 0}".encode()).hexdigest(),
                                          "finite": True, "repeatedExact": True, "copiedExact": True, "segmentedExact": True,
                                          "expectedExact": None if graph in {"oscillator", "compressor"} else True,
                                          "nonzero": graph != "silence"} for channel in range(2)])
                rows.append(row)
    return {"schema": 1, "passed": True, "rows": rows, "repeatStable": True}


@pytest.mark.parametrize("probe,cases", [("fidelity", 54), ("analyser", 12), ("worklet", 12), ("realtime", 1)])
def test_audio_compatibility_requires_complete_controlled_coverage(probe, cases):
    assert audio.validate_observation(valid_observation(probe), probe)["cases"] == cases


@pytest.mark.parametrize("probe", audio.PROBES)
@pytest.mark.parametrize("value", [None, {}, {"schema": True, "passed": True}, {"schema": 1, "passed": 1},
                                   {"schema": 1, "passed": False}, {"schema": 1, "passed": True, "rows": []}])
def test_empty_or_failed_audio_report_cannot_pass(probe, value):
    with pytest.raises(ValueError):
        audio.validate_observation(value, probe)


@pytest.mark.parametrize("probe", ["fidelity", "analyser", "worklet"])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "foreign", "failed", "boolean-rate", "malformed-graph"])
def test_audio_case_identifiers_are_exact_and_unique(probe, mutation):
    result = valid_observation(probe)
    row = result["rows"][0]
    if mutation == "missing":
        result["rows"].pop()
    elif mutation == "duplicate":
        result["rows"][-1] = copy.deepcopy(row)
    elif mutation == "foreign":
        row["rate"] = 22050
    elif mutation == "failed":
        row["passed"] = False
    elif mutation == "boolean-rate":
        row["rate"] = True
    else:
        row["kind" if probe == "fidelity" else "graph"] = []
    with pytest.raises(ValueError):
        audio.validate_observation(result, probe)


@pytest.mark.parametrize("probe", ["analyser", "worklet", "realtime"])
@pytest.mark.parametrize("mutation", ["missing", "extra", "false", "truthy"])
def test_audio_check_names_and_boolean_values_cannot_be_forged(probe, mutation):
    result = valid_observation(probe)
    checks = result["checks"] if probe == "realtime" else result["rows"][0]["checks"]
    key = next(iter(checks))
    if mutation == "missing":
        del checks[key]
    elif mutation == "extra":
        checks["unknown"] = True
    else:
        checks[key] = False if mutation == "false" else 1
    with pytest.raises(ValueError):
        audio.validate_observation(result, probe)


@pytest.mark.parametrize("mutation", ["format", "channel-count", "expected-signal", "nonzero", "digest", "unstable", "same-stereo", "all-silent"])
def test_fidelity_rejects_inconsistent_format_samples_and_hashes(mutation):
    result = valid_observation("fidelity")
    row = result["rows"][0]
    if mutation == "format":
        row["frames"] = True
    elif mutation == "channel-count":
        row["channels"].pop()
    elif mutation == "expected-signal":
        row["channels"][0]["expectedExact"] = None
    elif mutation == "nonzero":
        row["channels"][0]["nonzero"] = True
    elif mutation == "digest":
        row["channels"][0]["sha256"] = "a" * 63
    elif mutation == "unstable":
        result["rows"][1]["channels"][0]["sha256"] = "f" * 64
        result["rows"][1]["channels"][1]["sha256"] = "f" * 64
    elif mutation == "same-stereo":
        for row in result["rows"]:
            if row["kind"] == "stereo":
                row["channels"][1]["sha256"] = row["channels"][0]["sha256"]
    else:
        for row in result["rows"]:
            for channel in row["channels"]:
                channel["sha256"] = "f" * 64
    with pytest.raises(ValueError):
        audio.validate_observation(result, "fidelity")


@pytest.mark.parametrize("rate", [True, 0, -1, float("inf"), float("nan"), 10 ** 1000])
def test_realtime_rejects_invalid_sample_rate(rate):
    result = valid_observation("realtime")
    result["sampleRate"] = rate
    with pytest.raises(ValueError):
        audio.validate_observation(result, "realtime")


@pytest.mark.parametrize("packets", [True, 0, -1, 2049, "16"])
def test_worklet_requires_bounded_real_packet_count(packets):
    result = valid_observation("worklet")
    result["rows"][0]["packetCount"] = packets
    with pytest.raises(ValueError):
        audio.validate_observation(result, "worklet")


@pytest.mark.parametrize("mode", audio.MODES)
def test_audio_mode_preserves_existing_features_and_explicit_policy(mode):
    config = audio.AudioConfiguration(audio_mode=mode, probe_mode="baseline" if mode == "baseline" else "ready")
    arguments = config.launch_arguments()
    features = [value for value in arguments if value.startswith("--enable-features=")]
    assert len(features) == 1 and "ThirdPartyStoragePartitioning" in features[0]
    assert ("GlintAudioMathCandidate" in features[0]) is (mode == "math")


def test_audio_mode_cannot_be_mislabeled_baseline_with_enabled_policy():
    with pytest.raises(ValueError, match="disagree"):
        audio.AudioConfiguration(audio_mode="baseline", probe_mode="ready").launch_arguments()


@pytest.mark.parametrize("modes", [(), ("math", "math"), (True,), (["math"],), ("unknown",)])
def test_invalid_audio_modes_reject_before_claiming_workspace(tmp_path, monkeypatch, modes):
    monkeypatch.setattr(audio.build, "workspace_lock", lambda *args: pytest.fail("Unexpected workspace claim"))
    with pytest.raises(ValueError, match="distinct explicit"):
        audio.verify(tmp_path, tmp_path / "chrome.exe", tmp_path / "evidence", candidate_name="upstream-156", modes=modes)


def fake_measurement(*, fidelity_error=None, unroute_error=None):
    observations = [valid_observation(name) for name in audio.PROBES]
    observations[0]["passed"] = fidelity_error is None
    page = SimpleNamespace(goto=AsyncMock(), evaluate=AsyncMock(side_effect=[*observations[:3], None, observations[3]]),
                           get_by_role=Mock(return_value=SimpleNamespace(click=AsyncMock())))
    context = SimpleNamespace(pages=[page], route=AsyncMock(), unroute=AsyncMock(side_effect=unroute_error))
    server = SimpleNamespace(origin="http://127.0.0.1:12345", sources=dict.fromkeys(audio.PROBES, "async () => ({})"))
    return context, server


def test_measurement_retains_failed_probe_and_collects_all_remaining_checks():
    context, server = fake_measurement(fidelity_error=True)
    result = asyncio.run(audio.measure(context, server))
    assert not result["passed"] and set(result["probes"]) == set(audio.PROBES)
    assert result["probes"]["fidelity"]["observed"]["passed"] is False
    assert result["probes"]["fidelity"]["error_type"] == "ValueError"
    assert all(result["probes"][name]["passed"] for name in ("analyser", "worklet", "realtime"))
    assert context.pages[0].goto.await_count == 4
    context.unroute.assert_awaited_once()


def test_measurement_cannot_report_success_after_route_cleanup_failure():
    context, server = fake_measurement(unroute_error=OSError("Owned cleanup failure"))
    result = asyncio.run(audio.measure(context, server))
    assert not result["passed"] and result["cleanup_error_type"] == "OSError"
    assert all(row["passed"] for row in result["probes"].values())


def test_cancelled_measurement_removes_owned_route_without_running_later_probes():
    context, server = fake_measurement()
    context.pages[0].evaluate.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(audio.measure(context, server))
    context.pages[0].goto.assert_awaited_once()
    context.unroute.assert_awaited_once()


def test_stock_calibration_binds_actual_sources_without_glint_admission():
    raw = (audio.FIXTURES / "stock156-observations.json").read_bytes()
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    record = json.loads(raw)
    stock = json.loads((audio.ROOT / "native/drafts/upstream-156/stock-control-observations.json").read_bytes())
    assert record["passed"] and record["resources_closed"] and record["postguards_passed"]
    assert record["reference_version"] == stock["target_version"]
    assert record["reference_revision"] == stock["target_revision"]
    assert record["reference_core_sha256"] == stock["stock_core_sha256"]
    assert set(record["probe_coverage"]) == set(audio.PROBES)
    assert {name: row["cases"] for name, row in record["probe_coverage"].items()} == {
        "fidelity": 54, "analyser": 12, "worklet": 12, "realtime": 1}
    for name, digest in record["source_sha256"].items():
        source = (audio.ROOT / name).read_bytes()
        assert hashlib.sha256(source).hexdigest() == digest
        assert b"\r" not in source and not source.startswith(b"\xef\xbb\xbf")
    assert len(record["negative_javascript_controls"]["analyser"]["rejected"]) == 4
    assert len(record["negative_javascript_controls"]["worklet"]["rejected"]) == 5
    assert all(record[field] is False for field in ("glint_candidate_runtime_verified", "audio_v1_failure_fixed",
        "device_cohort_verified", "privacy_admitted", "production_admitted"))
def test_audio_math_readiness_draft_uses_noncolliding_fixed_backend_vectors():
    import hmac
    from scripts import native_build
    from scripts.verify_native_document_drafts import patch_paths

    path = native_build.ROOT / "native/drafts/audio-dsp-math-v2/audio_math_fixture_readiness.patch"
    selected = native_build.load_candidate("upstream-156")
    row = selected["manifest"]["patches"][-1]
    assert row["file"] == "0068-native-audio-math-fixture-readiness.patch"
    assert (selected["directory"] / "patches" / row["file"]).read_bytes() == path.read_bytes()
    patch = path.read_text(encoding="utf-8-sig")
    assert patch_paths(patch) == {"third_party/blink/renderer/modules/webaudio/offline_audio_context_test.cc"}
    assert "+constexpr uint8_t kGlintFloat32AudioSeed = 10;" in patch
    assert "+constexpr uint8_t kGlintNativeAudioSeed = 4;" in patch
    assert hmac.new(bytes([10]) * 32, b"glint.audio.math.backend.v1", hashlib.sha256).digest()[0] & 1 == 1
    assert hmac.new(bytes([4]) * 32, b"glint.audio.math.backend.v1", hashlib.sha256).digest()[0] & 1 == 0
    assert len({1, 2, 3, 10}) == len({1, 2, 3, 4}) == 4
    assert "GlintMathDuplicateSurfaceSeedRejectsBeforeNodeOrResolver" in patch
    assert "+  ASSERT_FALSE(holder->GetFrame().GetDocument()->GlintSurfacePolicyReady());" in patch
    assert "+      holder->GetFrame().GetDocument()->GlintSurfacePolicyReady() != ready) {" in patch


@pytest.mark.parametrize("count", [True, False, 0, -1, 17, "8", None])
def test_audio_profile_count_is_bounded_before_workspace_claim(tmp_path, monkeypatch, count):
    monkeypatch.setattr(audio.build, "workspace_lock", lambda *args: pytest.fail("Unexpected workspace claim"))
    with pytest.raises(ValueError, match="profile count"):
        audio.verify(tmp_path, tmp_path / "chrome.exe", tmp_path / "evidence",
                     candidate_name="upstream-156", modes=("baseline", "math"), profile_count=count)


@pytest.mark.parametrize("modes", [("baseline",), ("math",), ("legacy", "math")])
def test_audio_profile_matrix_requires_baseline_and_math(tmp_path, modes):
    with pytest.raises(ValueError, match="requires explicit baseline and math"):
        audio.verify(tmp_path, tmp_path / "chrome.exe", tmp_path / "evidence",
                     candidate_name="upstream-156", modes=modes, profile_count=8)


def profile_matrix_rows():
    return [{"index": index, "reference_selector": index, "cleanup_errors": [],
             "modes": {name: {"passed": True, "resources_closed": True,
                              "probes": {"fidelity": {"observed": valid_observation("fidelity")}}}
                       for name in ("baseline", "math", "math-restart")}} for index in (0, 1)]


def test_profile_summary_requires_complete_fixed_cohort_and_honest_selector_scope():
    result = audio.summarize_profiles(profile_matrix_rows(), 2, ("baseline", "math"))
    assert result["passed"] and result["reference_selectors_covered"]
    assert not result["internal_backend_observed"] and not result["device_cohort_verified"]
    assert all(row["restart_exact"] and row["unmodified_graphs_exact"] for row in result["comparisons"])


@pytest.mark.parametrize("mutation", ["one-selector", "restart", "native-dsp", "float-linear", "failed", "retained", "cleanup"])
def test_profile_matrix_never_hides_compatibility_or_lifecycle_failures(mutation):
    rows = profile_matrix_rows()
    if mutation == "one-selector":
        rows[1]["reference_selector"] = 0
    elif mutation in ("restart", "native-dsp", "float-linear"):
        row = rows[1 if mutation == "float-linear" else 0]
        modes = ("math",) if mutation == "restart" else ("math", "math-restart")
        for mode in modes:
            for value in row["modes"][mode]["probes"]["fidelity"]["observed"]["rows"]:
                if value["kind"] == "oscillator":
                    for channel in value["channels"]:
                        channel["sha256"] = "f" * 64
    elif mutation == "failed":
        rows[0]["modes"]["math"]["passed"] = False
    elif mutation == "retained":
        rows[0]["modes"]["math"]["resources_closed"] = False
    else:
        rows[0]["cleanup_errors"].append({"error": "Owned failure"})
    assert not audio.summarize_profiles(rows, 2, ("baseline", "math"))["passed"]


@pytest.mark.parametrize("mutation", ["missing-profile", "reorder", "selector-bool", "missing-restart"])
def test_profile_summary_rejects_missing_or_malformed_coverage(mutation):
    rows = profile_matrix_rows()
    if mutation == "missing-profile":
        rows.pop()
    elif mutation == "reorder":
        rows.reverse()
    elif mutation == "selector-bool":
        rows[0]["reference_selector"] = False
    else:
        rows[0]["modes"].pop("math-restart")
    with pytest.raises(ValueError):
        audio.summarize_profiles(rows, 2, ("baseline", "math"))


def test_audio_profile_selector_matches_two_stage_reference_without_returning_keys():
    import hmac
    from app.core.native.identity import NativePrivacyIdentity

    selectors = set()
    for value in range(16):
        identity = NativePrivacyIdentity(bytes([value]) * 32)
        message = b"Glint/profile-identity/v1\0" + (5).to_bytes(4, "big") + b"audio"
        derived = hmac.digest(identity.seed, message, hashlib.sha256)
        expected = hmac.digest(derived, b"glint.audio.math.backend.v1", hashlib.sha256)[0] & 1
        assert audio.profile_math_selector(identity) == expected
        selectors.add(expected)
    assert selectors == {0, 1}


@pytest.mark.parametrize("change_key", [False, True])
@pytest.mark.parametrize("custom_collector", [False, True])
def test_audio_profile_audit_precedes_capture_and_preserves_exact_key_on_restart(tmp_path, monkeypatch, change_key,
                                                                              custom_collector):
    from app.core.native import runtime as runtime_module, identity as identity_module

    first = identity_module.NativePrivacyIdentity(bytes(32))
    second = next(identity_module.NativePrivacyIdentity(bytes([value]) * 32) for value in range(1, 256)
                  if audio.profile_math_selector(identity_module.NativePrivacyIdentity(bytes([value]) * 32))
                  == audio.profile_math_selector(first))
    load = Mock(side_effect=[first, first, second if change_key else first])
    monkeypatch.setattr(identity_module, "load_or_create_identity", load)
    instances = []
    measured = []

    class Runtime:
        def __init__(self, profile, executable, configuration):
            self.configuration = configuration
            self.has_resources = False
            self.close = AsyncMock(side_effect=self.closed)
            instances.append(self)

        def closed(self):
            self.has_resources = False

        async def start(self, **kwargs):
            self.has_resources = True
            session = SimpleNamespace(send=AsyncMock(return_value={"revision": "@revision", "product": "Chrome/version"}),
                                      detach=AsyncMock())
            arguments = self.configuration.launch_arguments()
            if not any(value.startswith("--disable-features=") for value in arguments):
                arguments.append("--disable-features=Other,ThirdPartyStoragePartitioning")
            return SimpleNamespace(arguments=arguments, configuration=self.configuration,
                browser=SimpleNamespace(new_browser_cdp_session=AsyncMock(return_value=session)))

    async def capture(context, server):
        measured.append(context.configuration.audio_mode)
        if context.configuration.audio_mode == "math":
            assert load.call_count == measured.count("math") + 1
        return {"passed": True, "probes": {}}

    monkeypatch.setattr(runtime_module, "NativeRuntime", Runtime)
    monkeypatch.setattr(audio, "browser_arguments", AsyncMock(side_effect=lambda context: context.arguments))
    if custom_collector:
        monkeypatch.setattr(audio, "measure", AsyncMock(side_effect=AssertionError("Default collector was selected")))
    else:
        monkeypatch.setattr(audio, "measure", capture)
    report = {"modes": {}, "cleanup_errors": []}
    invocation = audio.measure_modes(tmp_path / "chrome.exe", tmp_path, None, ("baseline", "math"), report,
                                     "revision", "version", audit_backend=True,
                                     collector=capture if custom_collector else None)
    if change_key:
        with pytest.raises(ValueError, match="profile key changed"):
            asyncio.run(invocation)
        assert measured == ["baseline", "math"]
    else:
        asyncio.run(invocation)
        assert measured == ["baseline", "math", "math"]
        assert report["phase"] == "completed"
    assert report["reference_selector"] == audio.profile_math_selector(first)
    assert report["modes"]["math-restart"]["resources_closed"]
    assert all(not instance.has_resources and instance.close.await_count == 1 for instance in instances)


@pytest.mark.parametrize("both_selectors", [False, True])
def test_audio_matrix_executes_exact_fixed_profile_count_without_retry(tmp_path, monkeypatch, both_selectors):
    calls = []

    async def capture(executable, directory, server, modes, row, revision, version, *, audit_backend):
        assert audit_backend
        calls.append(directory.name)
        measured = profile_matrix_rows()[len(calls) % 2 if both_selectors else 0]
        row.update(reference_selector=measured["reference_selector"], modes=measured["modes"])

    monkeypatch.setattr(audio, "measure_modes", capture)
    report = {"profiles": []}
    asyncio.run(audio.measure_profiles(tmp_path / "chrome.exe", tmp_path, None, ("baseline", "math"),
                                      report, "revision", "version", 4))
    assert calls == ["profile-00", "profile-01", "profile-02", "profile-03"]
    assert len(report["profiles"]) == 4
    assert report["passed"] is both_selectors
    assert report["profile_summary"]["reference_selectors_covered"] is both_selectors
