import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from app.core.native.privacy import NativePrivacyPolicy


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / 'native/drafts/canvas-rendering-v2'
PRESETS = {
    'native': ('native', 'native'),
    'aliased': ('aliased', 'native'),
    'grayscale': ('grayscale', 'native'),
    'cleartype-rgb': ('cleartype-rgb', 'native'),
    'cleartype-bgr': ('cleartype-bgr', 'native'),
    'gamma-1400-contrast-300': ('native', 'gamma-1400-contrast-300'),
    'gamma-2200-contrast-500': ('native', 'gamma-2200-contrast-500'),
}


@pytest.fixture
def upgraded_policy(tmp_path, monkeypatch):
    relative = Path('app/core/native/privacy.py')
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    target.write_bytes((ROOT / relative).read_bytes())
    proof = json.loads((PACKET / 'host-observations.json').read_bytes())
    assert hashlib.sha256(target.read_bytes()).hexdigest() == proof['base_sha256']
    result = subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply',
        str(PACKET / 'host-policy.patch')], cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert hashlib.sha256(target.read_bytes()).hexdigest() == proof['after_sha256']
    name = 'app.core.native._canvas_rendering_v2_test'
    spec = importlib.util.spec_from_file_location(name, target)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module.NativePrivacyPolicy


@pytest.mark.parametrize('preset', list(PRESETS))
def test_v2_draft_roundtrips_explicit_version_and_exact_rendering_switches(upgraded_policy, preset):
    rasterization, tuning = PRESETS[preset]
    policy = upgraded_policy(canvas_pipeline_version=2, canvas_rendering_preset=preset,
        surface_policy_version=1, fingerprint_derivation_mode='profile-identity',
        font_rasterization=rasterization, text_tuning=tuning)
    assert upgraded_policy.from_dict(policy.to_dict()) == policy
    assert 'canvas-rendering-v2' in policy.required_capabilities()
    arguments = policy.prepared_arguments()
    assert '--glint-canvas-pipeline-version=2' in arguments
    assert '--glint-canvas-rendering-preset=' + preset in arguments
    existing = NativePrivacyPolicy(font_rasterization=rasterization, text_tuning=tuning)
    assert all(arg in arguments for arg in existing.prepared_arguments())
    with pytest.raises(ValueError, match='verified runtime admission'):
        policy.require_verified_runtime()


@pytest.mark.parametrize('preset', list(PRESETS))
def test_v2_draft_keeps_legacy_serialization_and_switches_unchanged(upgraded_policy, preset):
    rasterization, tuning = PRESETS[preset]
    original = NativePrivacyPolicy(font_rasterization=rasterization, text_tuning=tuning)
    upgraded = upgraded_policy.from_dict(original.to_dict())
    assert upgraded.to_dict() == original.to_dict()
    assert upgraded.prepared_arguments() == original.prepared_arguments()
    assert upgraded.required_capabilities() == original.required_capabilities()
    assert upgraded.canvas_pipeline_version == 0 and upgraded.canvas_rendering_preset == ''


@pytest.mark.parametrize('fields', [
    {'canvas_pipeline_version': True}, {'canvas_pipeline_version': 1},
    {'canvas_pipeline_version': 3}, {'canvas_pipeline_version': '2'},
    {'canvas_rendering_preset': 'native'},
    {'canvas_pipeline_version': 2, 'canvas_rendering_preset': None},
    {'canvas_pipeline_version': 2, 'canvas_rendering_preset': 'unknown',
     'surface_policy_version': 1, 'fingerprint_derivation_mode': 'profile-identity'},
    {'canvas_pipeline_version': 2, 'canvas_rendering_preset': 'native'},
    {'canvas_pipeline_version': 2, 'canvas_rendering_preset': 'native',
     'surface_policy_version': 1, 'fingerprint_derivation_mode': 'partitioned-privacy'},
    {'canvas_pipeline_version': 2, 'canvas_rendering_preset': 'grayscale',
     'surface_policy_version': 1, 'fingerprint_derivation_mode': 'profile-identity'},
], ids=['boolean', 'legacy-number', 'future-version', 'string-version', 'orphan-preset',
        'nonstring-preset', 'unknown-preset', 'missing-bootstrap', 'partitioned-mode', 'mismatched-raster'])
def test_v2_draft_rejects_invalid_intent_without_fallback(upgraded_policy, fields):
    with pytest.raises(ValueError):
        upgraded_policy.from_dict(fields)


def test_v2_draft_capability_is_not_admitted_by_existing_packages():
    from app.core.native.admission import _REVIEWED_PACKAGES

    assert all('canvas-rendering-v2' not in row['capabilities'] for row in _REVIEWED_PACKAGES.values())
    with pytest.raises(ValueError, match='Unknown or invalid'):
        NativePrivacyPolicy.from_dict(dict(canvas_pipeline_version=2, canvas_rendering_preset='native'))


def test_v2_draft_source_record_does_not_promote_replay_to_runtime_admission():
    record = json.loads((PACKET / 'source-observations.json').read_bytes())
    assert record['patch_sha256'] == hashlib.sha256((PACKET / 'canvas-rendering-v2.patch').read_bytes()).hexdigest()
    base = ROOT / 'native/drafts/upstream-156-audio-r8/manifest.json'
    assert record['base_manifest_sha256'] == hashlib.sha256(base.read_bytes()).hexdigest()
    assert record['source_forward_and_reverse_passed'] and record['added_headers_and_tests_removed_on_reverse']
    assert record['source_files_count'] == len(record['source_files']) == 11
    assert record['prepared_native_tests'] == 6
    assert len([item for item in record['source_files'].values() if item['before'] is None]) == 3
    for name in ('selected', 'active_checkout_modified', 'host_runtime_modified', 'compiled_browser',
                 'native_tests_executed', 'linked_canvas_v2_runtime_verified',
                 'seed_selected_preset_implemented', 'privacy_admitted', 'production_admitted'):
        assert record[name] is False


def test_v2_draft_host_record_binds_patch_and_preserves_admission():
    record = json.loads((PACKET / 'host-observations.json').read_bytes())
    assert record['patch_sha256'] == hashlib.sha256((PACKET / 'host-policy.patch').read_bytes()).hexdigest()
    assert record['capability'] == 'canvas-rendering-v2'
    assert record['selected'] is record['admission_changed'] is record['production_admitted'] is False


def test_v2_draft_syntax_evidence_covers_the_published_overlay_without_link_claims():
    record = json.loads((PACKET / 'source-observations.json').read_bytes())
    assert record['syntax_passed'] and record['cpp_translation_units_typechecked'] == 6
    assert len(record['syntax_checks']) == 2
    assert [len(check['targets']) for check in record['syntax_checks']] == [5, 1]
    for check in record['syntax_checks']:
        assert check['input_postguards_passed'] and check['active_core_unchanged']
        assert all(target['returncode'] == 0 for target in check['targets'])
        assert all(digest == record['source_files'][name]['after']
                   for name, digest in check['overlay_source_sha256'].items())
    assert record['compiled_browser'] is record['native_tests_executed'] is False
