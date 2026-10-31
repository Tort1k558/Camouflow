import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'native/drafts/webgpu-capture-retention'


def test_wire_draft_variants_replay_independently_without_claiming_runtime(tmp_path):
    record = json.loads((MODULE / 'wire-drafts.json').read_bytes())
    original = (MODULE / record['base_source']).read_bytes()
    assert hashlib.sha256(original).hexdigest() == record['base_source_sha256']
    assert record['patches_are_independent'] is True
    for key in ('hardware_tdr_tested', 'browser_integrated', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False
    assert {row['name'] for row in record['variants']} == {'uniform', 'device-lifetime', 'byte-budget'}
    for row in record['variants']:
        assert row['compiled'] is False and row['runtime_verified'] is False
        patch = MODULE / row['patch']
        assert hashlib.sha256(patch.read_bytes()).hexdigest() == row['patch_sha256']
        stage = tmp_path / row['name']
        stage.mkdir()
        source = stage / 'wire_probe.cc'
        source.write_bytes(original)
        for options in (['--check'], []):
            subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply',
                            '--whitespace=error-all', *options, str(patch)],
                           cwd=stage, check=True, capture_output=True, timeout=20)
        restored = source.read_bytes()
        assert hashlib.sha256(restored).hexdigest() == row['source_sha256']
        assert all(mode.encode() in restored for mode in row['modes'])
        if row['name'] == 'byte-budget':
            block = restored.split(b'    if (byteBudget) {\n        constexpr uint32_t side = 2048;', 1)[1]
            block = block.split(b'    constexpr uint32_t width = 8, height = 8, pitch = 256;', 1)[0]
            assert b'budget->used_bytes() == before + charge' in block
            assert b'retained.size() < 16' in block and b'requireBudgetDrained();' in block
            assert b'GetMapState() == wgpu::BufferMapState::Unmapped' in block
            for forbidden in (b'.ForceLoss(', b'.WriteTexture(', b'->Reserve(', b'OnTextureToBufferCopy('):
                assert forbidden not in block
        subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', str(patch)],
                       cwd=stage, check=True, capture_output=True, timeout=20)
        assert source.read_bytes() == original
    assert (MODULE / record['base_source']).read_bytes() == original


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


def test_wire_fail_closed_cases_deny_mapping_without_exposing_raw_pixels():
    record = json.loads((MODULE / 'wire-observations.json').read_bytes())
    assert set(record['fail_closed_cases']) == {
        '--unsupported-format', '--cancel-map', '--snapshot-quota',
    }
    for name, rows in record['fail_closed_cases'].items():
        assert len(rows) == 3
        for row in rows:
            assert row['args'] == [name] and row['returncode'] == 0 and row['stderr'] == ''
            result = json.loads(row['stdout'])
            assert result['passed'] and result['actual_wire_client_server_executed']
            assert result['denied_mapping'] and result['raw_pixels_exposed'] is False
            assert result['snapshot_slots_reused'] == (name == '--snapshot-quota')
            assert result['browser_integrated'] is False
    source = (MODULE / 'wire_probe.cc').read_text(encoding='utf-8-sig')
    assert 'wgpu::TextureFormat::RGBA8UnormSrgb' in source
    assert 'wgpu::MapAsyncStatus::Aborted' in source
    assert 'for (auto& buffer : quotaBuffers) buffer.Destroy();' in source
    assert 'Check(freshMapped);' in source


def test_wire_native_capture_accounting_drains_without_claiming_total_vram_coverage():
    record = json.loads((MODULE / 'wire-observations.json').read_bytes())
    assert record['tracked_capture_budget_accounting_executed']
    assert record['native_capture_byte_budget_exhaustion_tested'] is False
    assert record['total_gpu_memory_profiled'] is False
    rows = list(record['corrected_runs'])
    for cases in record['fail_closed_cases'].values():
        rows.extend(cases)
    assert len(rows) == 12
    for row in rows:
        result = json.loads(row['stdout'])
        assert result['capture_budget_limit_bytes'] == 64 * 1024**2
        assert 0 <= result['capture_bytes_after_first_map'] <= result['capture_budget_limit_bytes']
        assert result['capture_bytes_after_destroy'] == 0
    source = (MODULE / 'wire_probe.cc').read_text(encoding='utf-8-sig')
    assert 'GetGlintReadbackBudget()' in source and 'requireBudgetDrained();' in source
    project = (MODULE / 'CMakeLists.txt').read_text(encoding='utf-8-sig')
    assert 'TARGET_PROPERTY:dawn_native_objects,COMPILE_DEFINITIONS' in project


def test_wire_real_render_and_bundle_paths_bind_the_executed_fixture():
    record = json.loads((MODULE / 'wire-render-observations.json').read_bytes())
    assert record['passed'] and record['public_inputs_match_compiled_inputs']
    assert hashlib.sha256((MODULE / 'wire_probe.cc').read_bytes()).hexdigest() == record['fixture_sha256']
    assert hashlib.sha256((MODULE / 'CMakeLists.txt').read_bytes()).hexdigest() == record['cmake_sha256']
    assert record['actual_native_render_bundle_decoder_executed']
    assert record['sanitizer'] == 'none' and record['standalone_noop_raw_ptr']
    for key in ('chromium_gpu_process_executed', 'chromium_miracle_ptr_executed',
                'browser_integrated', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False
    modes = {'--render-direct', '--render-bundle', '--vertex-direct', '--vertex-bundle',
             '--index-direct', '--index-bundle', '--render-writable-direct', '--render-writable-bundle'}
    assert {row['args'][0] for row in record['runs']} == modes
    assert len(record['runs']) == 24
    for mode in modes:
        rows = [row for row in record['runs'] if row['args'] == [mode]]
        assert {row['attempt'] for row in rows} == {1, 2, 3}
        for row in rows:
            assert row['returncode'] == 0 and row['stderr'] == ''
            result = json.loads(row['stdout'])
            assert result['passed'] and result['actual_wire_client_server_executed']
            assert result['native_d3d12_queue_executed'] and result['render_pass_executed']
            assert result['render_bundle_executed'] == mode.endswith('bundle')
            assert result['vertex_buffer_executed'] == mode.startswith('--vertex')
            assert result['index_buffer_executed'] == mode.startswith('--index')
            assert result['render_writable_copyback_executed'] == ('writable' in mode)
            assert result['projected_compute_values'] == 64
            assert result['capture_bytes_after_destroy'] == 0
            assert result['observer_delivery_called_manually'] is False
            assert result['browser_integrated'] is False
