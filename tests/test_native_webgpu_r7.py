import hashlib
import json
from pathlib import Path

import pytest

from scripts import native_build as build

ROOT = Path(__file__).resolve().parents[1]


def test_r7_preserves_exact_r6_prefix_and_chromium_owned_append():
    before = build.load_candidate('upstream-156-webgpu-r6')
    candidate = build.load_candidate('upstream-156-webgpu-r7')
    manifest = candidate['manifest']
    assert manifest['patches'][:128] == before['manifest']['patches']
    assert len(manifest['patches']) == 129
    for key in ('source_files', 'dependencies', 'build', 'target_revision', 'target_version'):
        assert manifest[key] == before['manifest'][key]
    assert manifest['compiled'] is manifest['runtime_verified'] is manifest['production_admitted'] is False
    assert manifest['extension_batch']['base_manifest_sha256'] == before['manifest_sha256']
    assert candidate['lock']['build_jobs'] == 4 and candidate['lock']['minimum_free_gib'] == 180
    for patch, evidence in zip(manifest['patches'][128:], manifest['extension_batch']['packets'], strict=True):
        assert patch['directory'] == '.'
        path = candidate['directory'] / 'patches' / patch['file']
        prototype = ROOT / Path(evidence['packet']).parent / 'next.patch'
        assert path.read_bytes() == prototype.read_bytes()
        assert hashlib.sha256((ROOT / evidence['packet']).read_bytes()).hexdigest() == evidence['packet_sha256']
    receipts = build.expected_candidate_patches(manifest)
    assert len(receipts) == 129
    appended = [row for row in receipts if row['name'] == '0129-webgpu-readback-capacity.patch']
    assert len(appended) == 1 and appended[0].get('repository', '.') == '.'


def test_r7_source_replay_evidence_is_not_compilation_or_runtime_admission():
    candidate = build.load_candidate('upstream-156-webgpu-r7')
    record = json.loads((candidate['directory'] / 'preparation.json').read_bytes())
    assert record['passed'] and record['registered']
    assert record['manifest_sha256'] == candidate['manifest_sha256']
    assert record['forward_patches'] == record['reverse_patches'] == 129
    assert record['upstream_files_restored'] == 270 and record['final_owned_files_matched'] == 400
    assert record['compiled'] is record['source_transitioned'] is record['runtime_verified'] is False
    assert record['canonical_dependency_detector_verified'] is record['production_admitted'] is False


def test_r7_host_registration_restores_exact_r6_tooling(host_sources_before_webgpu_r7):
    previous = json.loads((ROOT / 'native/drafts/environment/webgpu-r6-host-source-upgrade.json').read_bytes())
    for row in previous['sources']:
        assert hashlib.sha256(host_sources_before_webgpu_r7[row['source']]).hexdigest() == row['after_sha256']


def test_r7_build_baseline_record_keeps_wider_admission_closed():
    candidate = build.load_candidate('upstream-156-webgpu-r7')
    record = json.loads((candidate['directory'] / 'windows-build-baseline.json').read_bytes())
    assert record['passed'] and record['candidate_manifest_sha256'] == candidate['manifest_sha256']
    assert record['build']['compiled'] and record['build']['compile_jobs'] == 4
    assert record['build']['link_pool_depth'] == record['resources']['max_observed_linkers'] == 1
    assert record['build']['reused_stages'] == ['sync', 'hooks', 'patch']
    assert record['native']['postguards_passed']
    assert sum(row['tests'] for row in record['native']['groups']) == record['native']['cases'] == 116
    assert all(row['native_cases_passed'] for row in record['native']['groups'])
    assert sum(row['checks'] for row in record['runtime']['groups']) == record['runtime']['cases'] == 160
    assert len(record['runtime']['groups']) == 8 and all(row['passed'] for row in record['runtime']['groups'])
    for name in ('complete_r7_diagnostics_passed', 'retained_buffer_repair_verified', 'legacy_audio_repaired',
                 'third_party_antibot_verified', 'privacy_admitted', 'production_admitted'):
        assert record[name] is False


def test_surface_launch_accepts_r7_before_requiring_a_real_workspace(monkeypatch, tmp_path):
    from scripts import verify_native_privacy_units as units

    class PreflightReached(Exception):
        pass

    def preflight(workspace, *, lock):
        assert workspace == tmp_path and lock['build_jobs'] == 4
        assert lock['chromium_revision'] == build.load_candidate('upstream-156-webgpu-r7')['lock']['chromium_revision']
        raise PreflightReached

    monkeypatch.setattr(units.sys, 'platform', 'win32')
    monkeypatch.setattr(build, 'preflight', preflight)
    with pytest.raises(PreflightReached):
        units.verify(tmp_path, tmp_path / 'not-executed.json', target='surface-launch',
                     candidate_name='upstream-156-webgpu-r7')


def test_r7_runtime_record_preserves_original_failures_and_audio_boundary():
    directory = build.load_candidate('upstream-156-webgpu-r7')['directory']
    record = json.loads((directory / 'runtime-observations.json').read_bytes())
    baseline = json.loads((directory / 'windows-build-baseline.json').read_bytes())
    assert record['runtime_core_sha256_measured'] == baseline['runtime']['runtime_core_sha256_measured']
    assert len(record['original_gates']) == record['total_named_gates'] == 16
    assert sum(row['passed'] for row in record['original_gates']) == record['original_passing_gates'] == 14
    assert {row['name'] for row in record['original_gates'] if not row['passed']} == {
        'normal-profile-webgpu', 'audio-compatibility'}
    assert record['corrected_normal_profile_webgpu']['passed']
    assert record['corrected_normal_profile_webgpu']['validators_unchanged']
    assert record['effective_passing_gates'] == 15
    assert record['retained_array']['result']['cases'] == 144
    assert record['retained_array']['result']['profile_isolation_proven'] is False
    assert record['retained_mutation']['result']['producer_mutation_visible']
    assert record['long_audio']['profile_summary']['reference_selectors_covered']
    metrics = record['audio_differences']
    assert metrics['original_report_passed'] is False and metrics['pass_criteria_unchanged']
    assert all(row['maximum_ulp_distance'] == 1 for row in metrics['groups'] if row['mode'] == 'legacy')
    assert record['complete_compatibility_passed'] is record['privacy_admitted'] is record['production_admitted'] is False
