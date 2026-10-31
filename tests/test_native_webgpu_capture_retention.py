import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'native/drafts/webgpu-capture-retention'


def observation():
    return json.loads((MODULE / 'observations.json').read_bytes())


def test_retention_records_bind_the_patch_fixture_and_component_project():
    record = observation()
    for name, expected in record['public_inputs_sha256'].items():
        assert hashlib.sha256((MODULE / name).read_bytes()).hexdigest() == expected
    assert record['source_chain_packets'] == 29
    assert record['source_chain_paths'] == 88
    assert record['patch_replay_reverse_passed']
    assert record['public_cmake_and_fixture_match_compiled_inputs']
    assert record['observer_before_sha256'] != record['observer_after_sha256']
    patch = (MODULE / 'next.patch').read_text(encoding='utf-8-sig')
    assert '-      found->byte_native.reset();' in patch
    assert '-    found->native.reset();' in patch
    assert 'limits_' not in patch


def test_retention_negative_control_and_repeated_native_observations():
    record = observation()
    failure = record['negative_control']
    assert failure['returncode'] != 0
    assert 'Glint GPU input metadata plan was denied' in failure['stderr']
    assert len(record['corrected_runs']) == 3
    for run in record['corrected_runs']:
        assert run['returncode'] == 0
        result = json.loads(run['stdout'])
        assert result['passed'] and result['native_dawn_queue_executed']
        assert result['glint_protected_inputs_tested']
        assert result['browser_integrated'] is False
        assert 'Protected native buffer shader matched CPU reference' in run['stderr']


def test_retention_fixture_uses_native_inputs_and_keeps_delivery_boundary_explicit():
    source = (MODULE / 'native_probe.cc').read_text(encoding='utf-8-sig')
    assert 'InstallGlintReadbackObserver' in source
    assert 'first.CopyTextureToBuffer' in source
    assert 'pass.DispatchWorkgroups' in source
    assert 'observer->PrepareReadMap' in source
    assert 'observer->PrepareGpuInputPlan' in source
    assert 'input.Destroy();' in source
    record = observation()
    for key in ('wire_executed', 'browser_integrated', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_wire_hardware_observation_binds_the_compiled_public_inputs():
    record = json.loads((MODULE / 'wire-observations.json').read_bytes())
    assert record['public_inputs_match_compiled_inputs']
    for name, expected in record['public_inputs_sha256'].items():
        assert hashlib.sha256((MODULE / name).read_bytes()).hexdigest() == expected
    source = (MODULE / 'wire_probe.cc').read_text(encoding='utf-8-sig')
    assert 'dawn::wire::WireClient' in source and 'dawn::wire::WireServer' in source
    assert 'CreateGlintWebGPUReadbackFilterFactory()' in source
    assert 'observer->PrepareReadMap' not in source
    assert '#include "native_probe.cc"' not in source


def test_wire_hardware_covers_cpu_first_dispatch_repeated_mapping_and_unrelated_bytes():
    record = json.loads((MODULE / 'wire-observations.json').read_bytes())
    assert len(record['corrected_runs']) == 3
    for row in record['corrected_runs']:
        assert row['returncode'] == 0 and row['stderr'] == ''
        result = json.loads(row['stdout'])
        assert result['passed'] and result['actual_wire_client_server_executed']
        assert result['native_d3d12_queue_executed']
        assert result['protected_channels'] == 100
        assert result['projected_compute_values'] == 64
        assert result['unrelated_values'] == 16 and result['repeated_map']
        assert result['observer_delivery_called_manually'] is False
        assert result['browser_integrated'] is False


def test_wire_missing_filter_control_observes_raw_pixels_not_an_arbitrary_crash():
    record = json.loads((MODULE / 'wire-observations.json').read_bytes())
    negative = record['without_filter_negative_control']
    assert negative['args'] == ['--without-filter'] and negative['returncode'] == 1
    assert 'WIRE_FILTER_MISMATCH' in negative['stderr']
    match = re.search(r'actual=(\d+) expected=(\d+) raw=(\d+)', negative['stderr'])
    assert match and match[1] == match[3] and match[1] != match[2]
    for key in ('chromium_miracle_ptr_executed', 'chromium_gpu_process_executed',
                'browser_integrated', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False
