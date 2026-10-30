import hashlib
import json
from pathlib import Path

from scripts import native_build as build
from scripts import verify_native_privacy_units as units


ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
CANDIDATE = ROOT / 'native/drafts/upstream-156'


def test_fixture_append_keeps_exact_74_prefix_and_all_non_patch_settings():
    candidate = build.load_candidate('upstream-156')
    before = json.loads((CANDIDATE / 'checkpoints/001-074.json').read_bytes())
    selected = (CANDIDATE / 'checkpoints/001-075.json').read_bytes()
    assert selected == (CANDIDATE / 'manifest.json').read_bytes()
    assert candidate['manifest']['patches'][:-1] == before['patches']
    assert len(candidate['manifest']['patches']) == 75
    assert {key: value for key, value in candidate['manifest'].items() if key != 'patches'} == {
        key: value for key, value in before.items() if key != 'patches'}


def test_fixture_correction_retains_assertions_and_only_initializes_real_test_view_data():
    record = json.loads((ENV / 'screen75-selection-observations.json').read_bytes())
    patch = (CANDIDATE / 'patches' / record['patch']).read_bytes()
    text = patch.decode('utf-8')
    assert hashlib.sha256(patch).hexdigest() == record['patch_sha256']
    assert 'diff --git a/content/browser/renderer_host/render_widget_host_unittest.cc ' in text
    assert text.count('diff --git ') == 1
    assert text.count('+  old->screen_infos = view_->GetScreenInfos();') == 3
    assert text.count('+  ASSERT_FALSE(old->screen_infos.screen_infos.empty());') == 3
    assert not any(line.startswith('-') and not line.startswith('--- ') for line in text.splitlines())
    assert record['prepared']['passed'] and record['prepared']['source_unchanged']
    assert record['assertions_removed'] == 0 and record['browser_code_changed'] is False
    assert all(record[key] is False for key in ('compiled_into_browser', 'native_tests_executed',
        'runtime_verified', 'privacy_admitted', 'production_admitted'))


def test_all_494_cases_remain_required_including_all_three_dispatch_cases():
    assert len(units.SUPPORTED_TARGETS) == 23
    assert sum(len(names) for target in units.SUPPORTED_TARGETS for names in units.required_tests(target).values()) == 494
    assert units.required_tests('screen-dispatch') == {'RenderWidgetHostTest': {
        'GlintLogicalScreenAdditionRequiresVisualUpdate',
        'GlintLogicalScreenOnlyChangesRequireVisualUpdate',
        'GlintLogicalScreenClearRequiresVisualUpdate'}}


def test_native_74_crash_is_retained_without_fabricated_results_for_unexecuted_cases():
    record = json.loads((CANDIDATE / 'native-batch74-observations.json').read_bytes())
    assert not record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['tests_passed'] == 491 and record['native_cases_required'] == 494
    assert record['native_cases_crashed'] == 1 and record['native_cases_not_executed'] == 2
    assert len(record['targets']) == 23
    failed = [row for row in record['targets'] if not row['native_cases_passed']]
    assert len(failed) == 1 and failed[0]['target'] == 'screen-dispatch'
    assert 'tests' not in failed[0] and 'result_sha256' not in failed[0]
    assert not record['browser_runtime_verified'] and not record['privacy_admitted']
