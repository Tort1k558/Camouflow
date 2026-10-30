import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

import pytest

from scripts import verify_native_combined_math as combined


@pytest.fixture
def compressor_capture():
    return {slot: struct.pack('<4f', .1, -.2, .3, -.4) for slot in combined.DOCUMENT_CONTEXTS}


def test_native_math_matches_baseline_and_restart_without_mutation(compressor_capture):
    before = copy.deepcopy(compressor_capture)
    result = combined.validate_compressor_effect(compressor_capture, baseline=compressor_capture,
                                                 previous=compressor_capture, selector=0)
    assert compressor_capture == before
    assert set(result) == combined.DOCUMENT_CONTEXTS
    assert all(row['matches_baseline'] and row['bytes'] == 16 and len(row['sha256']) == 64 for row in result.values())


def test_float_math_must_have_a_real_effect_but_not_a_different_value_for_every_profile(compressor_capture):
    changed = {slot: struct.pack('<4f', .10000001, -.2, .3, -.4) for slot in combined.DOCUMENT_CONTEXTS}
    result = combined.validate_compressor_effect(changed, baseline=compressor_capture, previous=changed, selector=1)
    assert all(not row['matches_baseline'] for row in result.values())
    assert len({row['sha256'] for row in result.values()}) == 1
    with pytest.raises(ValueError, match='contradicts'):
        combined.validate_compressor_effect(compressor_capture, baseline=compressor_capture, selector=1)


@pytest.mark.parametrize('kind', ['missing', 'nonbytes', 'empty', 'unaligned', 'oversized', 'different-context'])
def test_compressor_rejects_incomplete_or_incoherent_captures(compressor_capture, kind):
    values = dict(compressor_capture)
    key = next(iter(values))
    if kind == 'missing':
        values.pop(key)
    else:
        values[key] = {'nonbytes': [], 'empty': b'', 'unaligned': b'123', 'oversized': b'0' * (1024 * 1024 + 4),
                       'different-context': struct.pack('<4f', 0, 0, 0, 0)}[kind]
    with pytest.raises(ValueError):
        combined.validate_compressor_effect(values)


@pytest.mark.parametrize('selector', [False, True, -1, 2, '0'])
def test_compressor_rejects_invalid_selectors(compressor_capture, selector):
    with pytest.raises(ValueError, match='selector'):
        combined.validate_compressor_effect(compressor_capture, baseline=compressor_capture, selector=selector)


def test_compressor_requires_a_selector_when_a_baseline_is_provided(compressor_capture):
    with pytest.raises(ValueError, match='selector'):
        combined.validate_compressor_effect(compressor_capture, baseline=compressor_capture)
    changed = {slot: struct.pack('<4f', 0, 0, 0, 0) for slot in combined.DOCUMENT_CONTEXTS}
    with pytest.raises(ValueError, match='selector'):
        combined.validate_compressor_effect(changed, baseline=compressor_capture)


def test_compressor_rejects_restart_drift_and_mismatched_extent(compressor_capture):
    changed = {slot: struct.pack('<4f', 0, 0, 0, 0) for slot in combined.DOCUMENT_CONTEXTS}
    with pytest.raises(ValueError, match='restart'):
        combined.validate_compressor_effect(changed, previous=compressor_capture)
    longer = {slot: value * 2 for slot, value in compressor_capture.items()}
    with pytest.raises(ValueError, match='extent'):
        combined.validate_compressor_effect(longer, baseline=compressor_capture, selector=0)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), float('-inf')])
def test_compressor_rejects_nonfinite_float_samples(value):
    values = {slot: struct.pack('<f', value) for slot in combined.DOCUMENT_CONTEXTS}
    with pytest.raises(ValueError, match='non-finite'):
        combined.validate_compressor_effect(values)


def test_audio_completion_requires_all_probes_and_successful_route_cleanup():
    result = {'passed': True, 'probes': {name: {'passed': True} for name in ('fidelity', 'analyser', 'worklet', 'realtime')}}
    combined.validate_audio_completion(result)
    for broken in (
        {**result, 'passed': False}, {**result, 'cleanup_error': 'route removal failed'},
        {**result, 'cleanup_error_type': 'TargetClosedError'}, {**result, 'probes': {}},
        {**result, 'probes': {**result['probes'], 'worklet': {'passed': False}}},
    ):
        with pytest.raises(ValueError, match='cleanup'):
            combined.validate_audio_completion(broken)


def test_collector_cli_help_does_not_import_playwright_or_create_profiles(tmp_path):
    result = subprocess.run([sys.executable, str(Path(combined.__file__)), '--help'],
                            capture_output=True, text=True, cwd=tmp_path, timeout=15)
    assert result.returncode == 0 and '--driver-stage' in result.stdout
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('count', ['0', '1', '17'])
def test_collector_rejects_invalid_cohort_before_touching_output(tmp_path, count):
    output = tmp_path / 'owned-output'
    result = subprocess.run([sys.executable, str(Path(combined.__file__)), '--executable', 'unknown/chrome.exe',
                            '--driver-stage', 'unknown-stage', '--work-dir', str(output),
                            '--candidate', 'upstream-156', '--profiles', count],
                            capture_output=True, text=True, cwd=tmp_path, timeout=15)
    assert result.returncode != 0 and '2..16' in result.stderr
    assert not output.exists()


@pytest.fixture
def measured_combination():
    path = combined.ROOT / 'native/drafts/environment/combined-math70-observations.json'
    return json.loads(path.read_bytes())


def test_combined_measurement_binds_the_runner_without_admitting_a_release(measured_combination):
    record = measured_combination
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    source = (combined.ROOT / record['public_runner']).read_text(encoding='utf-8-sig')
    assert hashlib.sha256(source.encode('utf-8')).hexdigest() == record['public_runner_normalized_utf8_lf_sha256']
    for name in ('selected', 'privacy_admitted', 'production_admitted', 'device_cohort_verified',
                 'concurrent_profiles_verified', 'mobile_web_verified', 'webgpu_readback_admitted'):
        assert record[name] is False
    assert record['protected_profile_count'] == 8 and len(record['checks']) == 18
    assert record['both_audio_math_selectors_observed'] and record['audio_reference_selectors_observed'] == [0, 1]
    assert set(record['audio_selector_profile_counts']) == {'0', '1'}
    assert sum(record['audio_selector_profile_counts'].values()) == 8


def test_combined_measurement_requires_every_phase_and_validation(measured_combination):
    names = ('baseline', *(f'profile-{index:02d}' for index in range(8)))
    rows = measured_combination['checks']
    assert {(row['profile'], row['phase']) for row in rows} == {(name, phase) for name in names for phase in ('initial', 'restart')}
    expected = {'canvas-paths-contexts-restart', 'audio-sample-digests', 'audio-api-contexts-restart',
        'gpu-readback-export-contexts-restart', 'audio-fidelity-restart', 'audio-long-compressor-effect-contexts-restart',
        'canvas-origin-clean-errors', 'audio-profile-identity-context-consistency',
        'canvas-audio-parser-and-initial-child', 'full-audio-collection-and-cleanup',
        *(f'audio-fidelity-{slot}' for slot in combined.DOCUMENT_CONTEXTS),
        *(f'full-audio-{name}' for name in ('fidelity', 'analyser', 'worklet', 'realtime'))}
    for row in rows:
        assert row['passed'] and row['identity_stable'] and row['resources_released']
        assert row['remaining_observed_processes'] == 0 and row['observed_processes'] > 2
        assert set(row['validations']) == expected and all(value is True for value in row['validations'].values())
        assert row['first_script_counts'] == {'requests': 1, 'executions': 1}
        assert row['parser_state'] == 'loading' and row['initial_child_url'] == 'about:blank'
        assert set(row['fidelity']['document_contexts']) == combined.DOCUMENT_CONTEXTS
        assert row['fidelity']['all_passed'] and row['fidelity']['cases_per_document'] == 54
        assert {name: probe['coverage']['cases'] for name, probe in row['audio_compatibility'].items()} == {
            'fidelity': 54, 'analyser': 12, 'worklet': 12, 'realtime': 1}
        assert all(probe['passed'] for probe in row['audio_compatibility'].values())


def test_combined_measurement_records_two_audio_classes_not_eight_identities(measured_combination):
    initial = {row['profile']: row for row in measured_combination['checks'] if row['phase'] == 'initial'}
    baseline_hash = initial['baseline']['compressor_effect']['document']['sha256']
    all_hashes = set()
    for name, row in initial.items():
        effects = row['compressor_effect']
        assert set(effects) == combined.DOCUMENT_CONTEXTS
        assert {value['bytes'] for value in effects.values()} == {65536}
        assert len({value['sha256'] for value in effects.values()}) == 1
        digest = effects['document']['sha256']
        all_hashes.add(digest)
        if name != 'baseline':
            assert (digest == baseline_hash) == (row['audio_reference_selector'] == 0)
            assert all(value['matches_baseline'] is (row['audio_reference_selector'] == 0) for value in effects.values())
        restart = next(value for value in measured_combination['checks'] if value['profile'] == name and value['phase'] == 'restart')
        assert restart['compressor_effect'] == effects
    assert len(all_hashes) == 2
    assert all(value['passed'] for value in measured_combination['aggregate']['validations'].values())
