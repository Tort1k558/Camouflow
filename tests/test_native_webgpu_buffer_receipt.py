import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-buffer-receipt'


def preparation():
    return json.loads((ENV / 'webgpu-buffer-receipt-preparation.json').read_bytes())


def test_buffer_receipt_binds_twenty_seven_packets_and_all_fixture_dependencies():
    record = preparation()
    assert record['passed'] and record['exact_twenty_seven_packet_replay_and_reverse_verified']
    assert len(record['prerequisites']) == 26 and len(record['composed_sources']) == 87
    assert len(record['sources']) == 4
    for row in [*record['prerequisites'], {'patch': record['patch'], 'sha256': record['patch_sha256']}]:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']
    for path, key in ((MODULE / 'check.py', 'checker_sha256'),
                      (MODULE / 'predicates-template.cc', 'template_sha256'),
                      (MODULE.parent / 'webgpu-private-backing/check.py', 'shared_checker_sha256')):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record[key]
    assert set(record['extracted_predicates_sha256']) == {'regression', 'getter'}
    assert set(record['dependency_sources_sha256']) == {
        'webgpu-input-plan/check.py', 'webgpu-input-plan/predicates-template.cc',
        'webgpu-shader-capture/controller_test.cc',
    }
    for relative, expected in record['dependency_sources_sha256'].items():
        assert hashlib.sha256((MODULE.parent / relative).read_bytes()).hexdigest() == expected


def test_buffer_receipt_is_private_exact_scope_and_issued_after_copyback():
    record = preparation()
    packet = (ENV / record['patch']).read_text(encoding='utf-8-sig')
    for text in ('friend class d3d12::CommandBuffer', 'GlintGpuInputReceipt(const GlintGpuInputReceipt&) = delete',
                 'committed_gpu_input_plan_', 'receipt->GetPlan() != committed',
                 'scope.buffers.size() != gpu_input_scope_.size()', 'expected.readable != actual.readable',
                 'expected.writable != actual.writable', 'expected.rangeKnown != actual.rangeKnown',
                 'mGlintComputeBindingsApplied', 'mGlintComputeCopiedBack', 'ValidateGpuInputReceipt'):
        assert text in packet
    command = packet[packet.index('+++ b/third_party/dawn/src/dawn/native/d3d12/CommandBufferD3D12.cpp'):]
    assert command.index('CopyBackGlintComputeBuffers(commandContext)') < command.index('new GlintGpuInputReceipt(')
    assert command.index('new GlintGpuInputReceipt(') < command.index('CaptureGlintComputeScope(commandContext, std::move(receipt))')
    assert '&& !projected_inputs' in packet
    assert 'ByteEligible(found->second' in packet


def test_buffer_receipt_cpu_checks_keep_native_issuer_and_gpu_boundary_explicit():
    proof = preparation()['public_checker_observation']
    assert proof['passed'] and proof['measurement_complete'] and proof['postguards_passed']
    assert proof['cpu_controller_executed'] and proof['backend_mocked']
    assert proof['actual_native_device_queue_executed'] is False
    assert {row['sanitizer'] for row in proof['runs']} == {'none', 'address'}
    for row in proof['runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result'] == {
            'passed': True, 'assertions': 15735, 'cases': 896, 'prior_plan_assertions': 12802,
            'legacy_assertions': 10154, 'backend_mocked': True, 'cpu_controller_executed': True,
            'exact_scope_receipt_checked': True, 'actual_native_device_queue_executed': False,
        }
    fixture = (MODULE / 'predicates-template.cc').read_text(encoding='utf-8-sig')
    assert 'static_assert(!std::is_abstract_v<LegacyObserver>)' in fixture
    assert 'static_assert(!std::is_constructible_v<GlintGpuInputReceipt' in fixture
    assert 'legacy_observer.legacy_calls == 1' in fixture


def test_buffer_routing_copyback_does_not_claim_combined_native_dispatch():
    record = json.loads((ENV / 'webgpu-buffer-routing-preparation.json').read_bytes())
    assert record['passed'] and record['exact_twenty_six_packet_replay_and_reverse_verified']
    assert len(record['prerequisites']) == 25
    assert hashlib.sha256((ENV / record['patch']).read_bytes()).hexdigest() == record['patch_sha256']
    assert record['exact_prepared_scope_retained'] and record['no_precapture_observer_write_callback']
    assert record['dynamic_uniform_shadow_roots_source_prepared']
    assert record['writable_copyback_source_prepared'] and record['indirect_projected_buffer_inputs_denied']
    for row in record['hardware_copyback']['runs']:
        assert row['compile_returncode'] == row['returncode'] == 0
        value = row['result']
        assert value['passed'] and value['cases'] == 24 and value['assertions'] == 21534
        assert value['hardware_copyback_verified'] and value['readonly_bytes_preserved']
        assert value['native_dawn_queue_executed'] is False
        assert value['binding_tracker_dispatch_executed'] is False


def test_buffer_receipt_keeps_unverified_runtime_and_release_gates_closed():
    record = preparation()
    assert all(record[key] for key in ('direct_compute_buffer_routing_source_prepared',
               'writable_range_copyback_source_prepared', 'private_command_buffer_receipt_constructor_prepared',
               'exact_scope_one_shot_controller_prepared', 'legacy_observer_source_compatibility_checked'))
    assert record['native_syntax']['passed'] and record['native_syntax']['postguards_passed']
    assert len(record['native_syntax']['runs']) == 15
    assert all(row['returncode'] == 0 for row in record['native_syntax']['runs'])
    for key in ('invalid_receipt_legacy_retry_permitted', 'receipt_issuer_command_recording_executed',
                'full_native_binding_tracker_dispatch_executed', 'actual_native_device_queue_executed',
                'actual_native_allocator_retirement_executed', 'actual_physical_padding_gpu_clear_executed',
                'actual_wire_server_roundtrip_executed', 'gn_rechecked', 'component_link_verified',
                'canvas_gpu_shader_consistency_resolved', 'selected', 'default_feature_enabled',
                'runtime_verified', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_buffer_receipt_changed_inputs_are_refused_before_compilation():
    proof = preparation()['changed_input_refusal']
    assert proof['passed']
    assert {row['case'] for row in proof['cases']} == {
        'packet', 'template', 'checker', 'shared-checker', 'getter-hash', 'controller-fixture-hash',
        'generated-fixture-hash', 'baseline-hash', 'legacy-checker', 'legacy-template',
        'legacy-controller', 'dependency-set',
    }
    assert all(row['passed'] and row['returncode'] in (1, 2) and row['expected_error_observed']
               and row['refused_before_compilation'] for row in proof['cases'])
