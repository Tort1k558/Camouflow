import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-canonical-plane'


def preparation():
    return json.loads((ENV / 'webgpu-canonical-plane-preparation.json').read_bytes())


def test_canonical_plane_binds_eighteen_packet_chain_and_staged_extension():
    record = preparation()
    assert record['passed'] and record['exact_eighteen_packet_replay_and_reverse_verified']
    assert len(record['prerequisites']) == 17 and len(record['composed_sources']) == 84
    assert len(record['sources']) == 2 and len(record['source_extension']['sources']) == 7
    for row in [*record['prerequisites'], {'patch': record['patch'], 'sha256': record['patch_sha256']}]:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']
    extension = record['source_extension']
    assert extension['patch'] == record['patch'] and extension['patch_sha256'] == record['patch_sha256']
    assert extension['prerequisites'] == [record['prerequisites'][-1]]


def test_canonical_plane_binds_hardware_fixture_shaders_and_shared_runner():
    record = preparation()
    for directory, mapping in ((MODULE, record['sources_sha256']),
                               (MODULE.parent / 'webgpu-buffer-scatter', record['dependency_sources_sha256']),
                               (MODULE.parent, record['dependency_files_sha256'])):
        for name, value in mapping.items():
            assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == value
    for path, key in ((MODULE / 'check.py', 'checker_sha256'),
                      (MODULE.parent / 'webgpu-buffer-scatter/check.py', 'shared_checker_sha256'),
                      (MODULE.parent / 'webgpu-execution-inputs/check.py', 'source_gate_checker_sha256'),
                      (ENV / 'webgpu-execution-inputs-preparation.json', 'source_gate_record_sha256'),
                      (MODULE.parent / 'webgpu-edge-compute/edge_compute.hlsl', 'edge_shader_sha256')):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record[key]


def test_canonical_plane_actual_helpers_keep_snapshot_after_source_mutation():
    proof = preparation()['public_checker_observation']
    assert proof['passed'] and proof['postguards_passed'] and proof['hardware_execution_verified']
    assert proof['native_source_extension_verified']
    assert {row['sanitizer'] for row in proof['runs']} == {'none', 'address'}
    for row in proof['runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        value = row['result']
        assert value['passed'] and value['hardware_adapter']
        assert value['cases'] == 20 and value['assertions'] == 154849 and value['shared_quota_cases'] == 20
        for key in ('typed_texture_consumer_verified', 'canonical_plane_verified',
                    'source_mutation_isolated', 'dependent_retirement_verified'):
            assert value[key] is True
        assert value['browser_integrated'] is False


def test_canonical_plane_native_storage_layout_is_explicit_not_assumed_rgba():
    record = preparation()
    assert record['snapshot_storage'] == 'tight native RGBA8/BGRA8, explicit format'
    packet = (ENV / record['patch']).read_text(encoding='utf-8-sig')
    for text in ('canonical_pixel_format()', 'canonical_pixel_format_ = view_format',
                 'row * tight_pitch', 'footprint.Footprint.RowPitch', 'canonical_pixels.Reset()'):
        assert text in packet
    fixture = (MODULE / 'hardware-fixture.patch').read_text(encoding='utf-8-sig')
    assert 'Source and destination use the same native channel layout' in fixture
    assert 'projected->canonical_pixel_format() == view_format' in fixture


def test_canonical_plane_does_not_admit_unimplemented_registry_and_browser_paths():
    record = preparation()
    syntax = record['native_syntax']
    assert syntax['passed'] and syntax['postguards_passed'] and len(syntax['runs']) == 14
    assert all(row['returncode'] == 0 for row in syntax['runs'])
    for key in ('gn_rechecked', 'component_link_verified', 'actual_native_device_queue_executed',
                'actual_wire_server_roundtrip_executed', 'native_immutable_gpu_snapshot_registry_implemented',
                'native_binding_routing_installed', 'gpu_buffer_input_projection_integrated',
                'dxc_execution_verified', 'runtime_verified', 'canvas_gpu_shader_consistency_resolved',
                'selected', 'default_feature_enabled', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_canonical_plane_altered_inputs_are_refused_before_compilation():
    proof = preparation()['changed_input_refusal']
    assert proof['passed']
    assert {row['case'] for row in proof['cases']} == {
        'fixture', 'checker', 'shared-checker', 'mapping', 'parameters', 'packet', 'source-gate',
        'source-record', 'edge-shader', 'missing-extension', 'base-fixture', 'consumer-shader',
        'predecessor-packet',
    }
    assert all(row['passed'] and row['returncode'] == 2 and row['expected_error_observed']
               and row['refused_before_compilation'] for row in proof['cases'])
