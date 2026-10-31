import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'


def preparation():
    return json.loads((ENV / 'webgpu-ranged-provenance-preparation.json').read_bytes())


def test_ranged_provenance_packet_binds_measured_source_and_prerequisites():
    record = preparation()
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['exact_patch_roundtrip_verified'] and len(record['sources']) == 4
    assert hashlib.sha256((ENV / record['patch']).read_bytes()).hexdigest() == record['patch_sha256']
    assert len(record['prerequisites']) == 7
    for row in record['prerequisites']:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']
    source = ROOT / 'native/drafts/webgpu-ranged-provenance/ranged_test.cc'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record['test_sha256']


def test_ranged_provenance_new_cpu_oracle_and_controller_checks_passed_with_asan():
    record = preparation()
    assert record['region_limit'] == 16
    assert {row['sanitizer'] for row in record['cpu_runs']} == {'none', 'address'}
    for row in record['cpu_runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result'] == {
            'passed': True, 'assertions': 4900091, 'oracle_operations': 4000,
            'shader_transformation_implemented': False,
        }


def test_ranged_provenance_preserves_all_five_isolated_component_suites():
    runs = preparation()['isolated_component_runs']
    expected = {'layout': 525936, 'provenance': 1232777, 'snapshot': 748,
                'callback': 201, 'uncertain': 191874}
    assert len(runs) == 10
    assert {(row['name'], row['sanitizer']) for row in runs} == {
        (name, sanitizer) for name in expected for sanitizer in ('none', 'address')
    }
    for row in runs:
        assert row['result']['passed']
        assert row['result']['assertions'] == expected[row['name']]
        assert len(row['dll_sha256']) == len(row['executable_sha256']) == 64


def test_ranged_provenance_syntax_evidence_does_not_grant_runtime_admission():
    record = preparation()
    assert len(record['syntax_checks']) == 3 and record['syntax_diagnostic_bytes'] == 0
    assert all(row['returncode'] == 0 for row in record['syntax_checks'])
    assert record['shader_scope_still_whole_buffer'] is True
    for key in ('default_feature_enabled', 'selected', 'gn_rechecked',
                'chromium_component_link_verified', 'native_shader_callbacks_executed',
                'exact_binding_ranges_implemented', 'shader_transformation_implemented',
                'canvas_gpu_shader_consistency_resolved', 'runtime_verified',
                'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_ranged_provenance_baseline_is_full_python_not_native_proof():
    record = preparation()['full_python_baseline']
    assert record['git_head'] == 'cca22d8' and record['postguards_passed']
    assert record['counts'] == {
        'tests': 5103, 'passed': 5102, 'skipped': 1, 'failures': 0, 'errors': 0,
    }
