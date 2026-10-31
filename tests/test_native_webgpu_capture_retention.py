import hashlib
import json
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
