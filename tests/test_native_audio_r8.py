import hashlib
import json
from pathlib import Path

import pytest

from scripts import native_build as build
from scripts import verify_native_privacy_units as units


ROOT = Path(__file__).resolve().parents[1]


def test_audio_r8_preserves_exact_r7_recipe_and_adds_two_chromium_packets():
    previous = build.load_candidate('upstream-156-webgpu-r7')
    candidate = build.load_candidate('upstream-156-audio-r8')
    manifest = candidate['manifest']
    assert manifest['patches'][:129] == previous['manifest']['patches']
    assert len(manifest['patches']) == 131
    for name in ('source_files', 'dependencies', 'build', 'target_revision', 'target_version'):
        assert manifest[name] == previous['manifest'][name]
    assert manifest['extension_batch']['base_manifest_sha256'] == previous['manifest_sha256']
    assert manifest['compiled'] is manifest['runtime_verified'] is manifest['production_admitted'] is False
    assert candidate['lock']['build_jobs'] == 4 and candidate['lock']['minimum_free_gib'] == 180
    for patch, packet in zip(manifest['patches'][129:], manifest['extension_batch']['packets'], strict=True):
        assert patch['directory'] == '.'
        prototype = ROOT / Path(packet['packet']).parent / 'next.patch'
        assert (candidate['directory'] / 'patches' / patch['file']).read_bytes() == prototype.read_bytes()
        assert hashlib.sha256((ROOT / packet['packet']).read_bytes()).hexdigest() == packet['packet_sha256']


def test_audio_r8_source_replay_does_not_claim_native_execution():
    candidate = build.load_candidate('upstream-156-audio-r8')
    record = json.loads((candidate['directory'] / 'preparation.json').read_bytes())
    assert record['passed'] and record['manifest_sha256'] == candidate['manifest_sha256']
    assert record['forward_patches'] == record['reverse_patches'] == 131
    assert record['final_owned_files_matched'] == 400 and record['upstream_files_restored'] == 270
    assert record['compiled'] is record['native_tests_executed'] is False
    assert record['canonical_sources_modified'] is record['production_admitted'] is False


def test_audio_r8_archived_host_sources_are_exactly_restorable(host_sources_before_audio_r8):
    for name, raw in host_sources_before_audio_r8.items():
        assert b'upstream-156-audio-r8' not in raw
        assert b'upstream-156-webgpu-r7' in raw


def test_audio_lifecycle_requires_exact_candidate_before_workspace_access(tmp_path):
    for candidate in (None, 'upstream-156-webgpu-r7'):
        with pytest.raises(ValueError, match='exact upstream-156-audio-r8'):
            units.verify(tmp_path, tmp_path / 'not-created.json', target='audio-lifecycle', candidate_name=candidate)
    assert not (tmp_path / 'not-created.json').exists()


def test_audio_lifecycle_exact_r8_reaches_resource_preflight(monkeypatch, tmp_path):
    class PreflightReached(Exception):
        pass

    def preflight(workspace, *, lock):
        assert workspace == tmp_path and lock['build_jobs'] == 4
        assert lock['minimum_free_gib'] == 180
        raise PreflightReached

    monkeypatch.setattr(units.sys, 'platform', 'win32')
    monkeypatch.setattr(build, 'preflight', preflight)
    with pytest.raises(PreflightReached):
        units.verify(tmp_path, tmp_path / 'not-created.json', target='audio-lifecycle',
                     candidate_name='upstream-156-audio-r8')


def test_audio_lifecycle_targets_linked_blink_and_exact_seven_cases():
    required = units.required_tests('audio-lifecycle')
    assert 'audio-lifecycle' in units.SUPPORTED_TARGETS
    assert units.unit_binary_target('audio-lifecycle') == 'blink_unittests'
    assert sum(map(len, required.values())) == 7
    assert 'GlintCopyBudgetRejectsBeforeAllocationOrRenderThread' in required['OfflineAudioContextTest']
    report = dict(tests=7, failures=0, disabled=0, testsuites=[
        dict(name=suite, testsuite=[dict(name=case, status='RUN', result='COMPLETED') for case in sorted(cases)])
        for suite, cases in required.items()])
    units.validate_results(report, target='audio-lifecycle')
    report['testsuites'][0]['testsuite'][0]['name'] = 'UnrelatedPassingTest'
    with pytest.raises(ValueError, match='names differ'):
        units.validate_results(report, target='audio-lifecycle')


def test_audio_lifecycle_registration_keeps_all_historical_target_prefixes(
        tmp_path, monkeypatch, host_sources_before_audio_r8):
    import runpy
    import sys

    path = tmp_path / 'before_audio_r8_units.py'
    path.write_bytes(host_sources_before_audio_r8['scripts/verify_native_privacy_units.py'])
    monkeypatch.setattr(sys, 'path', sys.path.copy())
    previous = runpy.run_path(str(path))
    assert units.SUPPORTED_TARGETS == (*previous['SUPPORTED_TARGETS'], 'audio-lifecycle')
    for target in previous['SUPPORTED_TARGETS']:
        assert units.required_tests(target) == previous['required_tests'](target)
        assert units.unit_binary_target(target) == previous['unit_binary_target'](target)


def test_audio_r8_full_host_record_preserves_failures_and_later_tooling_boundary():
    candidate = build.load_candidate('upstream-156-audio-r8')
    record = json.loads((candidate['directory'] / 'host-regression.json').read_bytes())
    assert record['passed'] and record['input_postguards_passed']
    assert record['counts'] == dict(passed=5581, failed=0, skipped=1)
    assert record['original_failed_run']['counts']['failed'] == 4
    assert record['interrupted_retry']['interrupted'] and not record['interrupted_retry']['passed']
    assert record['later_public_lifecycle_cli_included'] is False
    assert record['native_runtime_verified'] is record['production_admitted'] is False
