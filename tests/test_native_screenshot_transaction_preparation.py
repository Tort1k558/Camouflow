import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'


def test_screenshot_transaction_is_replayed_but_not_admitted():
    record = json.loads((ENV / 'screenshot-transaction76-preparation.json').read_bytes())
    assert record['exact_replay_passed']
    assert record['canonical_source_unchanged'] and record['build_outputs_unchanged']
    for key in ('selected', 'runtime_verified', 'native_tests_executed',
                'privacy_admitted', 'production_admitted'):
        assert record[key] is False
    patch = ENV / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    sources = {row['source'] for row in record['sources']}
    assert sources == {
        'content/browser/devtools/protocol/emulation_handler.h',
        'content/browser/devtools/protocol/emulation_handler.cc',
        'content/browser/devtools/protocol/page_handler.h',
        'content/browser/devtools/protocol/page_handler.cc',
        'content/browser/devtools/devtools_agent_host_impl_unittest.cc',
    }
    text = patch.read_text(encoding='utf-8-sig')
    assert {line.split(' b/')[1] for line in text.splitlines()
            if line.startswith('diff --git ')} == sources
    assert text.count('+TEST_F(GlintScreenshotEmulationTest,') == record['native_test_cases_prepared'] == 12
    # A draft must not silently enter the selected Chromium patch series.
    manifest = (ROOT / 'native/drafts/upstream-156/manifest.json').read_text(encoding='utf-8-sig')
    assert record['patch'] not in manifest


def test_native_draft_syntax_covers_production_and_real_session_test_fixture():
    record = json.loads((ENV / 'screenshot-transaction76-preparation.json').read_bytes())
    checks = record['compiler_syntax_checks']
    assert len(checks) == 3
    assert {row['source'] for row in checks} == {
        'content/browser/devtools/protocol/emulation_handler.cc',
        'content/browser/devtools/protocol/page_handler.cc',
        'content/browser/devtools/devtools_agent_host_impl_unittest.cc',
    }
    empty_log = hashlib.sha256(b'').hexdigest()
    assert all(row['returncode'] == 0 and row['log_sha256'] == empty_log for row in checks)
    assert record['native_tests_executed'] is False


def test_full_worker_service_regression_has_separate_scope_from_native_draft():
    record = json.loads((ENV / 'canonical-python75-worker-service-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['git_head'] == '2953274c1cc96406676509bf392d128fa74fae35'
    assert record['counts'] == dict(tests=4802, passed=4801, skipped=1, failures=0, errors=0)
    assert 'before unselected native screenshot' in record['scope']
    for key in ('native_runtime_verified', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False
