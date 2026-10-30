import hashlib
import json
from pathlib import Path

import pytest

from scripts import native_build as build
from scripts import native_incremental as incremental
from scripts import verify_native_privacy_units as units


ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'


def test_selected_76_is_an_exact_75_prefix_append_with_unchanged_settings():
    candidate = build.load_candidate('upstream-156')
    record = json.loads((ENV / 'screenshot76-selection-observations.json').read_bytes())
    before = (candidate['directory'] / 'checkpoints/001-075.json').read_bytes()
    after = (candidate['directory'] / 'checkpoints/001-076.json').read_bytes()
    assert hashlib.sha256(before).hexdigest() == record['base_manifest_sha256']
    assert hashlib.sha256(after).hexdigest() == record['selected_manifest_sha256']
    assert after == (candidate['directory'] / 'manifest.json').read_bytes()
    delta = incremental.appended_patches(json.loads(before), json.loads(after))
    assert delta == [dict(file=record['patch'], sha256=record['patch_sha256'])]
    patch = candidate['directory'] / 'patches' / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    assert set(incremental.changed_paths([patch.read_text(encoding='utf-8')])) == incremental.DEVTOOLS_CAPTURE_FILES
    assert record['selected'] and record['exact_replay_passed']
    assert record['compiled_into_browser'] is record['native_tests_executed'] is record['runtime_verified'] is False


def test_capture_gate_adds_all_twelve_cases_without_replacing_existing_494(native_units_before_screenshot):
    historical = native_units_before_screenshot['namespace']
    assert units.SUPPORTED_TARGETS == (*historical['SUPPORTED_TARGETS'], 'screenshot-transaction')
    assert len(units.SUPPORTED_TARGETS) == 24
    for target in historical['SUPPORTED_TARGETS']:
        assert units.required_tests(target) == historical['required_tests'](target)
    assert sum(len(names) for target in units.SUPPORTED_TARGETS
               for names in units.required_tests(target).values()) == 506
    required = units.required_tests('screenshot-transaction')
    assert len(required['GlintScreenshotEmulationTest']) == 12
    assert units.unit_binary_target('screenshot-transaction') == 'content_unittests'
    record = json.loads((ENV / 'screenshot76-selection-observations.json').read_bytes())
    patch = (ROOT / 'native/drafts/upstream-156/patches' / record['patch']).read_text(encoding='utf-8')
    for name in required['GlintScreenshotEmulationTest']:
        assert '+TEST_F(GlintScreenshotEmulationTest, ' + name + ')' in patch


def test_capture_gate_rejects_missing_source_chain_and_implicit_candidate(tmp_path):
    with pytest.raises(ValueError, match='exact context'):
        units.require_target_sources(tmp_path, [], 'screenshot-transaction')
    with pytest.raises(ValueError, match='explicit upstream-156'):
        units.verify(tmp_path, tmp_path / 'report.json', target='screenshot-transaction')


@pytest.mark.parametrize('path', [
    'content/browser/devtools/devtools_session.cc',
    'content/browser/devtools/protocol/network_handler.cc',
    'content/browser/devtools/protocol/other.h',
    'content/browser/devtools/devtools_agent_host_impl.cc',
    'content/browser/devtools/protocol/../emulation_handler.cc',
])
def test_cached_capture_allowlist_does_not_allow_neighboring_devtools_files(path):
    with pytest.raises(ValueError, match='unsupported source'):
        incremental.changed_paths([f'diff --git a/{path} b/{path}\n'])


def test_capture_allowlist_does_not_relax_resources_or_build_inputs():
    assert incremental.MAX_BUILD_STEPS == 256 and incremental.MAX_FILES == 16
    assert incremental.MAX_SOURCE_BYTES == 16 * 1024**2
    assert incremental.MINIMUM_FREE_GIB == 64
    assert build.LOCK['minimum_free_gib'] == 180
