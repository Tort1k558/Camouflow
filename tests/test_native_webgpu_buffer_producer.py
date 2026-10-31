import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-buffer-producer'


def preparation():
    return json.loads((ENV / 'webgpu-buffer-producer-preparation.json').read_bytes())


def test_native_buffer_producer_binds_twenty_five_packets_and_extracted_contracts():
    record = preparation()
    assert record['passed'] and record['exact_twenty_five_packet_replay_and_reverse_verified']
    assert len(record['prerequisites']) == 24 and len(record['composed_sources']) == 87
    assert len(record['sources']) == 2
    for row in [*record['prerequisites'], {'patch': record['patch'], 'sha256': record['patch_sha256']}]:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']
    for path, key in ((MODULE / 'check.py', 'checker_sha256'),
                      (MODULE / 'predicates-template.cc', 'template_sha256'),
                      (MODULE.parent / 'webgpu-private-backing/check.py', 'shared_checker_sha256')):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record[key]
    assert set(record['extracted_predicates_sha256']) == {'types', 'helpers', 'resolve', 'producer'}


def test_native_buffer_producer_keeps_scope_ownership_and_failure_invalidation_explicit():
    record = preparation()
    packet = (ENV / record['patch']).read_text(encoding='utf-8-sig')
    for text in ('GlintNativeBufferOwner', 'Ref<Buffer> mBuffer', 'GlintInputPlanTransaction',
                 'mObserver->OnExecutionError()', 'GlintRangeCovered', 'owners.begin()',
                 'ResolveSnapshot(region.snapshot)', 'EnsureGlintAllocationInitialized(context)',
                 'TrackUsageAndTransitionNow(context, wgpu::BufferUsage::CopySrc)',
                 'ReferenceUntilUnused(projected->retirement_handle())',
                 'AddGlintReadbackSubmission(projected->submission_marker())'):
        assert text in packet
    assert packet.index('CommitGpuInputPlan(batch->plan)') < packet.index('item.buffer->EnsureGlintAllocationInitialized')
    assert packet.index('found->regions.size() == 16') < packet.index('ProjectedBuffer::Record(')
    assert all(not row['source'].endswith('/CommandBufferD3D12.cpp') for row in record['sources'])


def test_native_buffer_producer_cpu_fault_matrix_does_not_claim_native_gpu_execution():
    proof = preparation()['public_checker_observation']
    assert proof['passed'] and proof['measurement_complete'] and proof['postguards_passed']
    assert proof['backend_mocked'] and proof['actual_native_device_queue_executed'] is False
    assert {row['sanitizer'] for row in proof['runs']} == {'none', 'address'}
    for row in proof['runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result'] == {
            'passed': True, 'cases': 1216, 'assertions': 24288,
            'native_producer_control_flow_executed': True, 'backend_mocked': True,
            'actual_native_device_queue_executed': False,
        }


def test_native_buffer_pipeline_measures_both_compilers_without_dawn_queue_admission():
    record = json.loads((ENV / 'webgpu-buffer-pipeline-preparation.json').read_bytes())
    assert record['passed'] and record['exact_twenty_four_packet_replay_reverse_verified']
    assert record['embedded_scatter_matches_shared_source']
    assert len(record['prerequisites']) == 23 and len(record['composed_sources']) == 87
    assert hashlib.sha256((ENV / record['patch']).read_bytes()).hexdigest() == record['patch_sha256']
    cache = record['reports']['compiler_cache']['runs']
    assert {row['mode'] for row in cache} == {'none', 'address'}
    assert all(row['result']['assertions'] == 53 and row['result']['dxc_execution']
               and row['result']['native_dawn_device'] is False for row in cache)
    dispatch = record['reports']['dispatch']['runs']
    assert {(row['mode'], row['selected_compiler']) for row in dispatch} == {
        ('none', 'fxc'), ('none', 'dxc'), ('address', 'fxc'), ('address', 'dxc'),
    }
    for row in dispatch:
        assert row['returncode'] == 0
        value = row['result']
        assert value['passed'] and value['cases'] == 58 and value['changed_channels'] == 21501
        assert value['rejected_parameters'] == 696 and value['protected_source_unchanged']
        assert value['native_binding_routing_installed'] is False and value['browser_integrated'] is False


def test_native_buffer_producer_keeps_unconnected_runtime_gates_closed():
    record = preparation()
    assert all(record[key] for key in ('native_shadow_producer_source_prepared',
               'one_shadow_per_logical_buffer_source_prepared', 'writable_range_union_source_prepared',
               'native_allocation_owner_lease_source_prepared'))
    assert record['native_syntax']['passed'] and record['native_syntax']['postguards_passed']
    assert len(record['native_syntax']['runs']) == 15
    assert all(row['returncode'] == 0 for row in record['native_syntax']['runs'])
    for key in ('native_shadow_producer_connected', 'native_binding_routing_installed',
                'writable_copyback_implemented', 'actual_physical_padding_gpu_clear_executed',
                'actual_native_device_queue_executed', 'actual_wire_server_roundtrip_executed',
                'gn_rechecked', 'component_link_verified', 'runtime_verified',
                'canvas_gpu_shader_consistency_resolved', 'selected', 'default_feature_enabled',
                'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_native_buffer_producer_changed_inputs_are_refused_before_compilation():
    proof = preparation()['changed_input_refusal']
    assert proof['passed']
    assert {row['case'] for row in proof['cases']} == {
        'packet', 'template', 'checker', 'shared-checker', 'owner-helper-hash',
        'producer-hash', 'generated-fixture-hash', 'baseline-hash',
    }
    assert all(row['passed'] and row['returncode'] in (1, 2) and row['expected_error_observed']
               and row['refused_before_compilation'] for row in proof['cases'])
