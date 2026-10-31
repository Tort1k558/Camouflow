"""Evidence boundaries for the unselected private WebGPU transport draft."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT = ROOT / 'native/drafts/environment'


def test_private_transport_sources_and_patch_are_bound():
    record = json.loads((ENVIRONMENT / 'webgpu-private-policy-transport-preparation.json').read_bytes())
    assert hashlib.sha256((ENVIRONMENT / record['patch']).read_bytes()).hexdigest() == record['patch_sha256']
    for relative, expected in record['public_source_sha256'].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
    assert record['exact_patch_roundtrip_verified'] and record['postguards_passed']
    assert len(record['staged_sha256']) == 24
    assert record['command_id'] == 263
    assert record['existing_command_ids_preserved'] == list(range(256, 263))
    assert record['baseline_generated_files_exact'] == 12
    assert record['command_size_bytes'] == 24 and record['policy_packet_bytes'] == 64
    assert record['seed_in_command_arguments'] is False
    for key in ('selected', 'browser_integrated', 'runtime_verified', 'native_queue_hooks_installed',
                'native_webgpu_readback_protection', 'canvas_gpu_export_mismatch_resolved',
                'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_codec_checks_and_translation_units_do_not_claim_browser_integration():
    record = json.loads((ENVIRONMENT / 'webgpu-private-policy-transport-preparation.json').read_bytes())
    assert len(record['codec_checks']) == 2
    assert {row['mode'] for row in record['codec_checks']} == {'none', 'address'}
    for row in record['codec_checks']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result'] == dict(passed=True, assertions=152, transport_installed=False)
    assert len(record['syntax_checks']) == 4
    assert all(row['returncode'] == 0 for row in record['syntax_checks'])
    for filename in ('glint_webgpu_device_policy.h', 'glint_webgpu_device_policy.cc', 'policy_test.cc'):
        source = ROOT / 'native/drafts/webgpu-private-policy' / filename
        assert hashlib.sha256(source.read_bytes()).hexdigest() == record['measured_codec_source_sha256'][filename]
    assert record['public_codec_checks'] == record['codec_checks']
    for filename, expected in record['public_codec_source_sha256'].items():
        source = ROOT / 'native/drafts/webgpu-private-policy' / filename
        assert hashlib.sha256(source.read_bytes()).hexdigest() == expected


def test_full_capture_python_regression_predates_private_transport():
    record = json.loads((ENVIRONMENT / 'canonical-python76-capture-lifecycle-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['git_head'].startswith('1255aa7')
    assert record['counts'] == dict(tests=4968, passed=4967, skipped=1, failures=0, errors=0)
    assert record['native_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
