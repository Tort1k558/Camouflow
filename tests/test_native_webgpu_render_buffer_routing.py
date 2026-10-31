import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-render-buffer-routing'


def preparation():
    return json.loads((ENV / 'webgpu-render-buffer-routing-preparation.json').read_bytes())


def test_render_buffer_routing_binds_full_chain_and_extracted_predicates():
    record = preparation()
    assert record['passed'] and record['exact_twenty_nine_packet_replay_and_reverse_verified']
    assert len(record['prerequisites']) == 28 and len(record['composed_sources']) == 88
    assert len(record['sources']) == 2
    for row in [*record['prerequisites'], {'patch': record['patch'], 'sha256': record['patch_sha256']}]:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']
    for path, key in ((MODULE / 'check.py', 'checker_sha256'),
                      (MODULE / 'predicates-template.cc', 'template_sha256'),
                      (MODULE.parent / 'webgpu-private-backing/check.py', 'shared_checker_sha256')):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record[key]
    assert set(record['extracted_predicates_sha256']) == {'cursor', 'scope'}


def test_render_buffer_routing_has_preview_address_copyback_and_receipt_hooks():
    packet = (ENV / preparation()['patch']).read_text(encoding='utf-8-sig')
    for value in ('ReadWithoutAdvancing', 'RestoreCursor', 'previewBindings', 'collectOnly',
                  'PrepareGlintRenderBuffers', 'ResolveGlintVertexIndexAddress', 'applyIndexView',
                  'mGlintRenderPreparedScope', 'SameGlintRenderScope', 'CopyBackGlintBuffers',
                  'GlintGpuInputReceipt', 'new GlintGpuInputReceipt', 'GetGlintGpuInputPlanForCapture'):
        assert value in packet
    for value in ('draw->vertexCount == 0 || draw->instanceCount == 0',
                  'draw->indexCount == 0 || draw->instanceCount == 0',
                  'device->GetGlintReadbackObserver() && draw->maxDrawCount == 0'):
        assert value in packet
    assert 'ByteEligible' not in packet


def test_render_buffer_routing_predicate_proof_is_not_native_execution():
    proof = preparation()['public_checker_observation']
    assert proof['passed'] and proof['measurement_complete'] and proof['postguards_passed']
    assert proof['backend_mocked'] and proof['actual_native_device_queue_executed'] is False
    assert {row['sanitizer'] for row in proof['runs']} == {'none', 'address'}
    for row in proof['runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result'] == {
            'passed': True, 'cursor_cases': 125, 'scope_cases': 1536,
            'backend_mocked': True, 'actual_native_device_queue_executed': False,
        }


def test_render_buffer_routing_retains_unverified_runtime_gates():
    record = preparation()
    for key in ('render_bundle_buffer_routing_source_prepared',
                'vertex_index_shadow_addresses_source_prepared',
                'passwide_writable_copyback_source_prepared',
                'exact_replayed_scope_receipt_source_prepared'):
        assert record[key] is True
    assert record['native_syntax']['passed'] and record['native_syntax']['postguards_passed']
    assert len(record['native_syntax']['runs']) == 16
    assert all(row['returncode'] == 0 for row in record['native_syntax']['runs'])
    for key in ('indirect_projected_buffer_inputs_admitted', 'typed_texel_projection_implemented',
                'actual_native_binding_tracker_dispatch_executed', 'actual_native_device_queue_executed',
                'actual_wire_server_roundtrip_executed', 'gn_rechecked', 'component_link_verified',
                'runtime_verified', 'canvas_gpu_shader_consistency_resolved', 'selected',
                'default_feature_enabled', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_render_buffer_routing_changed_inputs_refused_before_compilation():
    proof = preparation()['changed_input_refusal']
    assert proof['passed']
    assert {row['case'] for row in proof['cases']} == {
        'packet', 'template', 'checker', 'shared-checker', 'cursor-hash', 'scope-hash',
        'generated-fixture-hash', 'baseline-hash',
    }
    assert all(row['passed'] and row['returncode'] in (1, 2) and row['expected_error_observed']
               and row['refused_before_compilation'] for row in proof['cases'])
