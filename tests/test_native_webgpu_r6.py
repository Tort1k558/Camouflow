import hashlib
import json
from pathlib import Path

import pytest

from scripts import native_build as build

ROOT = Path(__file__).resolve().parents[1]


def test_r6_preserves_exact_r5_prefix_and_dawn_owned_append():
    before = build.load_candidate('upstream-156-webgpu-r5')
    candidate = build.load_candidate('upstream-156-webgpu-r6')
    manifest = candidate['manifest']
    assert manifest['patches'][:124] == before['manifest']['patches']
    assert len(manifest['patches']) == 128
    for key in ('source_files', 'dependencies', 'build', 'target_revision', 'target_version'):
        assert manifest[key] == before['manifest'][key]
    assert manifest['compiled'] is manifest['runtime_verified'] is manifest['production_admitted'] is False
    assert manifest['extension_batch']['base_manifest_sha256'] == before['manifest_sha256']
    assert candidate['lock']['build_jobs'] == 4 and candidate['lock']['minimum_free_gib'] == 180
    for patch, evidence in zip(manifest['patches'][124:], manifest['extension_batch']['packets'], strict=True):
        assert patch['directory'] == 'third_party/dawn'
        path = candidate['directory'] / 'patches' / patch['file']
        prototype = ROOT / Path(evidence['packet']).parent / 'next.patch'
        assert path.read_bytes() == prototype.read_bytes()
        assert hashlib.sha256((ROOT / evidence['packet']).read_bytes()).hexdigest() == evidence['packet_sha256']
    receipts = build.expected_candidate_patches(manifest)
    assert len(receipts) == 128
    assert all(row['repository'] == 'third_party/dawn' for row in receipts if row['name'].startswith(('0125-', '0126-', '0127-', '0128-')))


def test_r6_source_replay_evidence_is_not_compilation_or_runtime_admission():
    candidate = build.load_candidate('upstream-156-webgpu-r6')
    record = json.loads((candidate['directory'] / 'preparation.json').read_bytes())
    assert record['passed'] and record['registered']
    assert record['manifest_sha256'] == candidate['manifest_sha256']
    assert record['forward_patches'] == record['reverse_patches'] == 128
    assert record['upstream_files_restored'] == 270 and record['final_owned_files_matched'] == 400
    assert record['compiled'] is record['source_transitioned'] is record['runtime_verified'] is False
    assert record['canonical_dependency_detector_verified'] is record['production_admitted'] is False


def test_r6_host_registration_restores_exact_r5_tooling(host_sources_before_webgpu_r6):
    previous = json.loads((ROOT / 'native/drafts/environment/webgpu-r5-host-source-upgrade.json').read_bytes())
    for row in previous['sources']:
        assert hashlib.sha256(host_sources_before_webgpu_r6[row['source']]).hexdigest() == row['after_sha256']


def test_surface_launch_accepts_r6_before_requiring_a_real_workspace(monkeypatch, tmp_path):
    from scripts import verify_native_privacy_units as units

    class PreflightReached(Exception):
        pass

    def preflight(workspace, *, lock):
        assert workspace == tmp_path and lock['build_jobs'] == 4
        assert lock['chromium_revision'] == build.load_candidate('upstream-156-webgpu-r6')['lock']['chromium_revision']
        raise PreflightReached

    monkeypatch.setattr(units.sys, 'platform', 'win32')
    monkeypatch.setattr(build, 'preflight', preflight)
    with pytest.raises(PreflightReached):
        units.verify(tmp_path, tmp_path / 'not-executed.json', target='surface-launch',
                     candidate_name='upstream-156-webgpu-r6')
