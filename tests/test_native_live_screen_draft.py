import hashlib
import json
from pathlib import Path

from scripts import native_build as build


ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'


def test_linked_screen_draft_binds_five_paths_and_four_successful_syntax_checks():
    record = json.loads((ENV / 'live-screen-linked-next-observations.json').read_bytes())
    patch = ENV / record['patch_file']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    assert record['passed'] and record['measurement_complete'] and record['source_unchanged']
    assert len(record['base_source_sha256']) == len(record['prepared_source_sha256']) == 5
    assert len(record['checks']) == len(record['inherited_blink_checks']) == 2
    assert all(row['returncode'] == 0 for row in record['checks'] + record['inherited_blink_checks'])
    text = patch.read_text(encoding='utf-8-sig')
    assert {line.split(' b/', 1)[1] for line in text.splitlines() if line.startswith('diff --git ')} == set(record['base_source_sha256'])


def test_draft_covers_dispatch_invalidation_and_live_emulator_without_weakening_old_tests():
    record = json.loads((ENV / 'live-screen-linked-next-observations.json').read_bytes())
    text = (ENV / record['patch_file']).read_text(encoding='utf-8-sig')
    assert '+         old_visual_properties->glint_logical_screen_infos !=' in text
    assert '+             new_visual_properties.glint_logical_screen_infos ||' in text
    assert '+  glint_logical_screen_infos_.reset();' in text
    assert '+  if (device_emulator_)\n+    return GetScreenInfos();' in text
    assert '+  using RenderWidgetHostImpl::StoredVisualPropertiesNeedsUpdate;' in text
    assert len(record['prepared_cases']) == len(set(record['prepared_cases'])) == 6
    for case in record['prepared_cases']:
        suite, name = case.split('.')
        assert f'TEST_F({suite}, {name})' in text
    assert not any(line.startswith(('-  EXPECT_', '-  ASSERT_', '-TEST_F')) for line in text.splitlines())


def test_preflight_does_not_select_or_admit_the_unbuilt_six_case_package():
    record = json.loads((ENV / 'live-screen-linked-next-observations.json').read_bytes())
    candidate = build.load_candidate('upstream-156')
    checkpoint = (candidate['directory'] / 'checkpoints/001-073.json').read_bytes()
    assert hashlib.sha256(checkpoint).hexdigest() == record['base_manifest_sha256']
    assert len(json.loads(checkpoint)['patches']) == 73
    assert not any(row['file'] == record['proposed_registered_name'] for row in json.loads(checkpoint)['patches'])
    assert all(record[key] is False for key in ('selected', 'native_tests_executed', 'compiled_into_browser',
                                               'privacy_admitted', 'production_admitted'))


def test_full_python_after_protected_history_is_not_native_case_execution():
    record = json.loads((ENV / 'canonical-python73-protected-history-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['git_head'] == 'f59e5788e33afea2a5bc428ecaff9f816b82fe30'
    assert record['counts'] == dict(tests=4569, failures=0, errors=0, skipped=1, passed=4568)
    assert not record['changed_tracked_files'] and record['before_status'] == record['after_status']
    assert record['native_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
