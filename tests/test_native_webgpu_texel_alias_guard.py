import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-texel-alias-guard'


def preparation():
    return json.loads((ENV / 'webgpu-texel-alias-guard-preparation.json').read_bytes())


def test_texel_guard_binds_twenty_eight_packets_and_native_predicates():
    record = preparation()
    assert record['passed'] and record['exact_twenty_eight_packet_replay_and_reverse_verified']
    assert len(record['prerequisites']) == 27 and len(record['composed_sources']) == 87
    assert len(record['sources']) == 1
    for row in [*record['prerequisites'], {'patch': record['patch'], 'sha256': record['patch_sha256']}]:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']
    for path, key in ((MODULE / 'check.py', 'checker_sha256'),
                      (MODULE / 'predicates-template.cc', 'template_sha256'),
                      (MODULE.parent / 'webgpu-private-backing/check.py', 'shared_checker_sha256')):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record[key]
    assert set(record['extracted_predicates_sha256']) == {'lookup', 'guard'}


def test_texel_guard_checks_projected_aliases_before_shader_binding_and_receipt():
    record = preparation()
    packet = (ENV / record['patch']).read_text(encoding='utf-8-sig')
    for text in ('ValidateGlintProjectedTexelBindings(group, wgpu::ShaderStage::Compute)',
                 'ValidateGlintProjectedTexelBindings(group, stages)',
                 'layout->GetTexelBufferIndices()', 'visibility & stages',
                 'view ? view->GetBuffer() : nullptr', '!buffer || FindGlintProjectedBuffer(buffer)',
                 'group->GetDevice() != mDevice'):
        assert text in packet
    assert 'GlintGpuInputReceipt' not in packet
    assert 'ByteEligible' not in packet


def test_texel_guard_extracted_predicate_matrix_is_not_native_gpu_execution():
    proof = preparation()['public_checker_observation']
    assert proof['passed'] and proof['measurement_complete'] and proof['postguards_passed']
    assert proof['backend_mocked'] and proof['actual_native_device_queue_executed'] is False
    assert {row['sanitizer'] for row in proof['runs']} == {'none', 'address'}
    for row in proof['runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result'] == {
            'passed': True, 'cases': 3840, 'assertions': 11584,
            'projected_texel_alias_denied': True, 'unprojected_texel_binding_preserved': True,
            'backend_mocked': True, 'actual_native_device_queue_executed': False,
        }


def test_texel_guard_preserves_unprojected_bindings_without_claiming_typed_projection():
    record = preparation()
    boundary = record['upstream_texel_backend_boundary']
    assert boundary['d3d12_texel_descriptors_supported'] is False
    assert boundary['selected_runtime_leak_demonstrated'] is False
    assert boundary['guard_is_defensive_for_unsupported_family'] is True
    assert 'DAWN_UNREACHABLE' in boundary['unsupported_descriptor_branch']
    assert record['projected_texel_alias_guard_source_prepared']
    assert record['unprojected_texel_bindings_preserved']
    assert record['native_syntax']['passed'] and record['native_syntax']['postguards_passed']
    assert len(record['native_syntax']['runs']) == 15
    assert all(row['returncode'] == 0 for row in record['native_syntax']['runs'])
    for key in ('typed_texel_projection_implemented', 'actual_native_binding_tracker_dispatch_executed',
                'actual_native_device_queue_executed', 'actual_wire_server_roundtrip_executed',
                'gn_rechecked', 'component_link_verified', 'runtime_verified',
                'canvas_gpu_shader_consistency_resolved', 'selected', 'default_feature_enabled',
                'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_texel_guard_changed_inputs_are_refused_before_compilation():
    proof = preparation()['changed_input_refusal']
    assert proof['passed']
    assert {row['case'] for row in proof['cases']} == {
        'packet', 'template', 'checker', 'shared-checker', 'lookup-hash', 'guard-hash',
        'generated-fixture-hash', 'baseline-hash',
    }
    assert all(row['passed'] and row['returncode'] in (1, 2) and row['expected_error_observed']
               and row['refused_before_compilation'] for row in proof['cases'])
