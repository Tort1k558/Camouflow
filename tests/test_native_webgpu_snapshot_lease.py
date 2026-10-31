import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-snapshot-lease'


def preparation():
    return json.loads((ENV / 'webgpu-snapshot-lease-preparation.json').read_bytes())


def test_snapshot_lease_binds_twenty_packet_sources_and_shared_runner():
    record = preparation()
    assert record['passed'] and record['exact_twenty_packet_replay_and_reverse_verified']
    assert len(record['prerequisites']) == 19 and len(record['sources']) == 4
    assert len(record['composed_sources']) == 84
    for row in [*record['prerequisites'], {'patch': record['patch'], 'sha256': record['patch_sha256']}]:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']
    for path, key in ((MODULE / 'check.py', 'checker_sha256'),
                      (MODULE / 'predicates-template.cc', 'template_sha256'),
                      (MODULE.parent / 'webgpu-private-backing/check.py', 'shared_checker_sha256')):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record[key]


def test_snapshot_lease_source_uses_private_payload_and_non_recyclable_logical_identity():
    record = preparation()
    for key in ('gpu_snapshot_lease_export_source_prepared', 'private_payload_source_prepared',
                'logical_device_identity_source_prepared'):
        assert record[key]
    packet = (ENV / record['patch']).read_text(encoding='utf-8-sig')
    for text in ('friend class d3d12::GlintTextureProjector', 'snapshot->mNative->mIdentity != mIdentity',
                 'std::make_shared<const GlintProjectionIdentity>()', 'GetGpuSnapshot() const',
                 'GlintReadbackSnapshot() = default', 'Invalid Glint GPU pixel snapshot metadata.'):
        assert text in packet
    assert 'dynamic_cast' not in packet and 'reinterpret_cast' not in packet


def test_snapshot_lease_synthetic_owner_and_reused_address_evidence_stays_explicit():
    proof = preparation()['public_checker_observation']
    assert proof['passed'] and proof['measurement_complete'] and proof['postguards_passed']
    assert proof['backend_mocked'] and proof['actual_native_device_queue_executed'] is False
    assert {row['sanitizer'] for row in proof['runs']} == {'none', 'address'}
    for row in proof['runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        value = row['result']
        assert value['assertions'] == 34817 and value['iterations'] == 512
        for key in ('passed', 'backend_mocked', 'source_extracted_gpu_lease_only',
                    'logical_owner_identity_verified', 'reused_device_address_rejected'):
            assert value[key] is True
        assert value['actual_native_device_queue_executed'] is False


def test_snapshot_lease_does_not_admit_unimplemented_plan_or_native_runtime():
    record = preparation()
    syntax = record['native_syntax']
    assert syntax['passed'] and syntax['postguards_passed'] and len(syntax['runs']) == 14
    assert all(row['returncode'] == 0 for row in syntax['runs'])
    for key in ('native_gpu_input_plan_implemented', 'actual_copy_command_execution_verified',
                'gn_rechecked', 'component_link_verified', 'actual_native_device_queue_executed',
                'actual_wire_server_roundtrip_executed', 'native_binding_routing_installed',
                'dxc_execution_verified', 'runtime_verified', 'canvas_gpu_shader_consistency_resolved',
                'selected', 'default_feature_enabled', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_snapshot_lease_extractor_rejects_missing_native_contracts(tmp_path):
    spec = importlib.util.spec_from_file_location('snapshot_lease_check', MODULE / 'check.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    native = tmp_path / 'third_party/dawn'
    for name in ('include/dawn/native/DawnNative.h', 'src/dawn/native/d3d12/GlintTextureProjectionD3D12.h',
                 'src/dawn/native/d3d12/GlintTextureProjectionD3D12.cpp',
                 'src/dawn/native/d3d12/GlintTextureReadbackD3D12.cpp'):
        path = native / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('', encoding='utf-8')
    with pytest.raises(ValueError, match='substring not found'):
        checker.extract_contracts(tmp_path)


def test_snapshot_lease_changed_inputs_are_refused_before_compilation():
    refusal = preparation()['changed_input_refusal']
    assert refusal['passed']
    assert {row['case'] for row in refusal['cases']} == {
        'packet', 'template', 'checker', 'shared-checker', 'extraction-hash', 'generated-fixture-hash',
    }
    assert all(row['passed'] and row['returncode'] in (1, 2)
               and row['expected_error_observed'] and row['refused_before_compilation']
               for row in refusal['cases'])
