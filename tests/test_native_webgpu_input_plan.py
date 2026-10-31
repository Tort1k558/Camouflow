import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-input-plan'


def preparation():
    return json.loads((ENV / 'webgpu-input-plan-preparation.json').read_bytes())


def test_gpu_input_plan_binds_twenty_one_packets_and_actual_cpu_fixture():
    record = preparation()
    assert record['passed'] and record['exact_twenty_one_packet_replay_and_reverse_verified']
    assert len(record['prerequisites']) == 20 and len(record['sources']) == 3
    assert len(record['composed_sources']) == 84
    for row in [*record['prerequisites'], {'patch': record['patch'], 'sha256': record['patch_sha256']}]:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']
    for path, key in ((MODULE / 'check.py', 'checker_sha256'),
                      (MODULE / 'predicates-template.cc', 'template_sha256'),
                      (MODULE.parent / 'webgpu-private-backing/check.py', 'shared_checker_sha256')):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record[key]


def test_gpu_input_plan_reuses_existing_legacy_controller_fixture_exactly():
    spec = importlib.util.spec_from_file_location('gpu_input_plan_check', MODULE / 'check.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    parts = checker.extract_contracts(ROOT)
    record = preparation()
    assert set(parts) == {'legacy'}
    fixture = (MODULE / 'predicates-template.cc').read_text(encoding='utf-8-sig')
    for name, source in parts.items():
        assert hashlib.sha256(source.encode()).hexdigest() == record['extracted_predicates_sha256'][name]
        marker = '/* GLINT_' + name.upper() + ' */'
        assert fixture.count(marker) == 1
        fixture = fixture.replace(marker, source)
    assert hashlib.sha256(fixture.encode()).hexdigest() == record['generated_fixture_sha256']


def test_gpu_input_plan_source_checks_identity_and_revision_without_readiness_override():
    record = preparation()
    assert record['gpu_input_metadata_plan_source_prepared']
    assert record['immutable_pointer_bound_commit_source_prepared']
    packet = (ENV / record['patch']).read_text(encoding='utf-8-sig')
    for text in ('active == plan', 'plan->sequence == sequence_', 'plan->deviceEpoch == epoch_',
                 'plan->policyGeneration == policy_->generation()', 'capture->native->GetGpuSnapshot()',
                 'gpu_input_plan_.reset()', 'region.snapshot.device_epoch != epoch_',
                 'region.snapshot.policy_generation != policy_->generation()',
                 'GlintGpuInputPlan> gpu_input_plan_', 'kWebGpuReadbackRegionLimit'):
        assert text in packet
    assert 'Attests unchanged metadata only' in packet
    assert record['plan_commit_proves_gpu_routing'] is False


def test_gpu_input_plan_cpu_controller_and_legacy_regression_are_not_native_execution():
    proof = preparation()['public_checker_observation']
    assert proof['passed'] and proof['measurement_complete'] and proof['postguards_passed']
    assert proof['cpu_controller_executed'] and proof['backend_mocked']
    assert {row['sanitizer'] for row in proof['runs']} == {'none', 'address'}
    for row in proof['runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        value = row['result']
        assert value['assertions'] == 12802 and value['iterations'] == 256
        assert value['legacy_assertions'] == 10154
        for key in ('passed', 'cpu_controller_executed', 'backend_mocked',
                    'stale_and_foreign_plan_rejected', 'plan_commit_does_not_admit_raw_inputs'):
            assert value[key] is True
        assert value['actual_native_device_queue_executed'] is False


def test_gpu_input_plan_keeps_unfinished_native_paths_closed():
    record = preparation()
    syntax = record['native_syntax']
    assert syntax['passed'] and syntax['postguards_passed'] and len(syntax['runs']) == 14
    assert all(row['returncode'] == 0 for row in syntax['runs'])
    for key in ('native_gpu_input_routing_implemented', 'plan_commit_proves_gpu_routing',
                'actual_copy_command_execution_verified', 'gn_rechecked', 'component_link_verified',
                'actual_native_device_queue_executed', 'actual_wire_server_roundtrip_executed',
                'native_binding_routing_installed', 'dxc_execution_verified', 'runtime_verified',
                'canvas_gpu_shader_consistency_resolved', 'selected', 'default_feature_enabled',
                'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_gpu_input_plan_changed_inputs_are_refused_before_compilation():
    proof = preparation()['changed_input_refusal']
    assert proof['passed']
    assert {row['case'] for row in proof['cases']} == {
        'packet', 'template', 'checker', 'shared-checker', 'predecessor-packet',
        'generated-fixture-hash', 'legacy-fixture',
    }
    assert all(row['passed'] and row['returncode'] in (1, 2)
               and row['expected_error_observed'] and row['refused_before_compilation']
               for row in proof['cases'])
