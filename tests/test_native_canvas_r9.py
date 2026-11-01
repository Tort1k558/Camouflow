import hashlib
import json
from pathlib import Path
import re

import pytest

from scripts import native_build as build
from scripts import verify_native_privacy_units as units


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = 'upstream-156-canvas-r9'


def test_canvas_r9_extends_exact_r8_recipe_and_retains_resource_limits():
    candidate = build.load_candidate(CANDIDATE)
    previous = build.load_candidate('upstream-156-audio-r8')
    manifest = candidate['manifest']
    assert len(manifest['patches']) == 132
    assert manifest['patches'][:131] == previous['manifest']['patches']
    for field in ('source_files', 'dependencies', 'build', 'target_revision', 'target_version'):
        assert manifest[field] == previous['manifest'][field]
    assert manifest['extension_batch']['base_manifest_sha256'] == previous['manifest_sha256']
    packet = manifest['extension_batch']['packets'][0]
    assert packet['packet_sha256'] == hashlib.sha256((ROOT / packet['packet']).read_bytes()).hexdigest()
    added = manifest['patches'][-1]
    assert added['file'] == '0132-canvas-rendering-v2.patch' and added['directory'] == '.'
    assert (candidate['directory'] / 'patches' / added['file']).read_bytes() == (
        ROOT / 'native/drafts/canvas-rendering-v2/canvas-rendering-v2.patch').read_bytes()
    assert candidate['lock']['build_jobs'] == 4 and candidate['lock']['minimum_free_gib'] == 180
    assert manifest['compiled'] is manifest['runtime_verified'] is manifest['production_admitted'] is False


def test_canvas_r9_source_replay_is_not_a_browser_or_native_test_result():
    candidate = build.load_candidate(CANDIDATE)
    record = json.loads((candidate['directory'] / 'preparation.json').read_bytes())
    assert record['passed'] and record['manifest_sha256'] == candidate['manifest_sha256']
    assert record['forward_patches'] == record['reverse_patches'] == 132
    assert record['final_owned_files_matched'] == 403 and record['upstream_files_restored'] == 270
    assert record['canonical_sources_modified'] is record['compiled'] is False
    assert record['native_tests_executed'] is record['production_admitted'] is False


def test_canvas_r9_unit_registration_matches_all_six_actual_native_test_names():
    candidate = build.load_candidate(CANDIDATE)
    patch = (candidate['directory'] / 'patches/0132-canvas-rendering-v2.patch').read_text(encoding='utf-8-sig')
    cases = set(re.findall(r'TEST\(GlintCanvasRenderingPolicyTest,\s*(\w+)\)', patch))
    assert len(cases) == 6
    assert units.required_tests('canvas-rendering') == {'GlintCanvasRenderingPolicyTest': cases}
    assert units.unit_binary_target('canvas-rendering') == 'blink_common_unittests'


def test_canvas_r9_preserves_all_r8_unit_groups_and_their_exact_archived_source(native_units_before_canvas_r9):
    previous = native_units_before_canvas_r9
    assert units.SUPPORTED_TARGETS == (*previous['SUPPORTED_TARGETS'], 'canvas-rendering')
    assert len(previous['SUPPORTED_TARGETS']) == 26
    for target in previous['SUPPORTED_TARGETS']:
        assert units.required_tests(target) == previous['required_tests'](target)
        assert units.unit_binary_target(target) == previous['unit_binary_target'](target)


@pytest.mark.parametrize('candidate', [None, 'upstream-156', 'upstream-156-audio-r8'])
def test_canvas_units_reject_the_wrong_candidate_before_workspace_access(tmp_path, candidate):
    with pytest.raises(ValueError, match='exact upstream-156-canvas-r9'):
        units.verify(tmp_path / 'absent', tmp_path / 'not-created.json', target='canvas-rendering',
                     candidate_name=candidate)
    assert not (tmp_path / 'absent').exists() and not (tmp_path / 'not-created.json').exists()


@pytest.mark.parametrize('target', ['canvas-rendering', 'audio-lifecycle', 'surface-launch'])
def test_canvas_r9_uses_the_unchanged_resource_preflight(monkeypatch, tmp_path, target):
    class ReachedPreflight(Exception):
        pass

    def preflight(workspace, *, lock):
        assert workspace == tmp_path and lock['build_jobs'] == 4 and lock['minimum_free_gib'] == 180
        raise ReachedPreflight

    monkeypatch.setattr(units.sys, 'platform', 'win32')
    monkeypatch.setattr(build, 'preflight', preflight)
    with pytest.raises(ReachedPreflight):
        units.verify(tmp_path, tmp_path / 'not-created.json', target=target, candidate_name=CANDIDATE)
    assert not (tmp_path / 'not-created.json').exists()


def test_canvas_r9_requires_the_actual_canvas_and_bootstrap_patches(tmp_path):
    required = {'0015-native-browser-context-key-ownership.patch', '0016-native-private-key-readiness.patch',
                '0123-profile-surface-launch.patch', '0132-canvas-rendering-v2.patch'}
    assert units.require_target_sources(tmp_path, [{'name': name} for name in required], 'canvas-rendering') is None
    for missing in required:
        with pytest.raises(ValueError, match='exact context ownership'):
            units.require_target_sources(tmp_path, [{'name': name} for name in required - {missing}], 'canvas-rendering')


def test_canvas_r9_host_archive_binds_both_registration_sources(host_sources_before_canvas_r9):
    packet = ROOT / 'native/drafts/environment/canvas-r9-host-source-upgrade.json'
    record = json.loads(packet.read_bytes())
    assert set(host_sources_before_canvas_r9) == {row['source'] for row in record['sources']}
    for row in record['sources']:
        assert hashlib.sha256((ROOT / row['source']).read_bytes()).hexdigest() == row['after_sha256']
        assert hashlib.sha256(host_sources_before_canvas_r9[row['source']]).hexdigest() == row['before_sha256']
        assert b'upstream-156-canvas-r9' not in host_sources_before_canvas_r9[row['source']]
