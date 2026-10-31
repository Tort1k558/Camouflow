import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'


def test_actual_shader_gate_source_and_negative_result_are_bound():
    record = json.loads((ENV / 'webgpu-shader-dataflow76-observations.json').read_bytes())
    assert record['measurement_complete'] and record['postguards_passed']
    assert record['fixture_validation_passed'] and record['surface_noise_observed']
    assert record['passed'] is record['readback_consistent'] is record['consistency_gate_passed'] is False
    assert record['public_cli_integrated'] and record['public_cli_returncode'] == 1
    for path, key in ((record['source'], 'source_sha256'), (record['cli'], 'cli_sha256')):
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == record[key]
    assert record['owned_profiles_removed']
    assert record['native_webgpu_shader_readback_protected'] is False
    assert record['unselected_service_packet_runtime_verified'] is False
    assert record['privacy_admitted'] is record['production_admitted'] is False


def test_shader_probe_measures_gpu_texture_load_and_storage_not_a_png_echo():
    source = (ENV / 'first-script/webgpu_shader_dataflow.js').read_text(encoding='utf-8-sig')
    assert 'textureLoad(image' in source and 'var<storage, read_write>' in source
    assert 'encoder.copyTextureToBuffer' in source
    assert 'encoder.copyBufferToBuffer(storage' in source and 'staging.mapAsync' in source
    assert 'new Uint32Array(staging.getMappedRange())' in source
    record = json.loads((ENV / 'webgpu-shader-dataflow76-observations.json').read_bytes())
    assert len(record['rows']) == 2 and {row['mode'] for row in record['rows']} == {'baseline', 'ready'}
    baseline = next(row for row in record['rows'] if row['mode'] == 'baseline')
    ready = next(row for row in record['rows'] if row['mode'] == 'ready')
    assert all(value['changed_channels'] == 0 for value in baseline['deviation_from_reference'].values())
    assert ready['direct_vs_shader']['changed_channels'] == 0
    assert ready['png_vs_shader'] == ready['png_vs_direct']
    assert ready['png_vs_shader']['changed_channels'] > 0
    assert ready['png_vs_shader']['maximum_delta'] == 1
    assert baseline['shader_rgba_sha256'] == ready['shader_rgba_sha256']


def test_full_python_service_baseline_does_not_claim_native_execution():
    prepared = json.loads((ENV / 'webgpu-service-readback-preparation.json').read_bytes())
    record = prepared['full_python_baseline']
    assert record['passed'] and record['postguards_passed'] and record['git_head'].startswith('becb858')
    assert record['counts'] == {'tests': 5065, 'passed': 5064, 'skipped': 1, 'failures': 0, 'errors': 0}
    assert record['native_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
