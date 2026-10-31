import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-shadow-texture'


def observations():
    return json.loads((ENV / 'webgpu-shadow-texture-observations.json').read_bytes())


def test_shadow_texture_sources_and_reused_budget_extension_are_bound():
    record = observations()
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    for name, expected in record['sources_sha256'].items():
        assert hashlib.sha256((MODULE / name).read_bytes()).hexdigest() == expected
    for name, expected in record['capture_base_sha256'].items():
        source = MODULE.parent / 'webgpu-d3d12-capture' / name
        assert hashlib.sha256(source.read_bytes()).hexdigest() == expected
    patch = MODULE / 'capture-budget-shadow-friends.patch'
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['budget_patch_sha256']
    assert record['budget_patch_roundtrip_verified']
    kernel = MODULE.parent / 'webgpu-edge-compute/edge_compute.hlsl'
    assert hashlib.sha256(kernel.read_bytes()).hexdigest() == record['edge_shader_sha256']


def test_shadow_texture_hardware_dataflow_preserves_original_and_matches_cpu():
    record = observations()
    assert record['gpu_only_projection_to_typed_texture_verified'] and record['original_texture_unchanged']
    assert {row['sanitizer'] for row in record['hardware_runs']} == {'none', 'address'}
    for row in record['hardware_runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result'] == {
            'passed': True, 'hardware_adapter': True, 'cases': 8, 'assertions': 19206,
            'shared_quota_cases': 8, 'typed_texture_consumer_verified': True,
            'original_unchanged': True, 'browser_integrated': False,
        }


def test_shadow_texture_lifetime_and_quota_evidence_is_scoped():
    record = observations()
    assert record['shared_capture_budget_used']
    assert record['cpu_owner_cancel_before_submit_cases'] == 4
    assert record['withheld_marker_after_completion_cases'] == 4
    assert record['descriptor_fixed_charge_bytes'] == 65536
    assert record['charge_is_total_driver_vram_measurement'] is False
    assert record['same_physical_device_validation']
    assert record['logical_dawn_device_ownership_validated'] is False


def test_shadow_texture_target_syntax_does_not_prove_native_linking():
    record = observations()
    assert record['native_target_syntax_verified']
    assert len(record['native_syntax_checks']) == 2
    assert all(row['returncode'] == 0 for row in record['native_syntax_checks'])
    for name in ('projected_texture.h', 'projected_texture.cc'):
        assert record['native_syntax_sources_sha256'][name] == record['sources_sha256'][name]
    assert record['native_component_link_verified'] is False


def test_shadow_texture_public_check_does_not_grant_browser_admission():
    record = observations()
    public = record['public_checker_observation']
    assert public['passed'] and public['postguards_passed'] and public['hardware_execution_verified']
    assert len(public['runs']) == 2
    assert all(row['result']['assertions'] == 19206 for row in public['runs'])
    for key in ('native_shader_input_routing_installed', 'browser_integrated',
                'native_state_tracker_restoration_verified', 'raster_consumer_verified',
                'actual_device_loss_injected', 'unsupported_formats_supported',
                'canvas_gpu_shader_consistency_resolved', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_shadow_texture_python_baseline_is_not_browser_routing_evidence():
    record = observations()['full_python_baseline']
    assert record['passed'] and record['postguards_passed'] and record['git_head'].startswith('04a22bd')
    assert record['counts'] == {
        'tests': 5132, 'passed': 5131, 'skipped': 1, 'failures': 0, 'errors': 0,
    }
