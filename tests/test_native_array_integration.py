import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / 'native/drafts/webgpu-array-native-integration'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_array_native_packet_pins_base_and_ordered_prerequisite_sources(tmp_path):
    packet = json.loads((DRAFT / 'packet.json').read_bytes())
    assert packet['selected'] is packet['browser_integrated'] is False
    assert packet['repository'] == 'third_party/dawn'
    assert packet['base_candidate'] == 'upstream-156-webgpu-r5'
    assert digest(ROOT / 'native/drafts/upstream-156-webgpu-r5/manifest.json') == packet['base_candidate_manifest_sha256']
    assert digest(DRAFT / packet['patch']) == packet['patch_sha256']
    assert [Path(row['patch']).parent.name for row in packet['prerequisites']] == [
        'webgpu-subresource-capture', 'webgpu-subresource-projection', 'webgpu-array-projection']
    final = {}
    for row in packet['prerequisites']:
        assert digest(ROOT / row['patch']) == row['patch_sha256']
        assert digest(ROOT / row['observations']) == row['observations_sha256']
        source = json.loads((ROOT / row['observations']).read_bytes())['source_files']
        for name, hashes in source.items():
            if name in final:
                assert final[name] == hashes['before_sha256']
            final[name] = hashes['after_sha256']
    final.update({name: row['after_sha256'] for name, row in packet['source_files'].items()})
    record = json.loads((DRAFT / 'observations.json').read_bytes())
    assert len(final) == 10
    assert record['prepared_source_sha256'] == {'third_party/dawn/' + name: value for name, value in final.items()}
    result = subprocess.run(['git', 'apply', '--numstat', str(DRAFT / 'next.patch')],
                            cwd=tmp_path, check=True, capture_output=True, text=True)
    paths = {line.split('\t')[-1] for line in result.stdout.splitlines()}
    assert paths == set(packet['source_files']) and len(paths) == 6
    assert all(name.startswith('src/dawn/native/d3d12/') for name in paths)


def test_array_native_packet_records_six_syntax_units_not_linked_browser_execution():
    record = json.loads((DRAFT / 'observations.json').read_bytes())
    assert record['native_target_syntax_passed'] and record['packet_composition_passed']
    assert record['postguards_passed']
    assert record['selected'] is record['browser_integrated'] is record['runtime_verified'] is False
    assert record['privacy_admitted'] is record['production_admitted'] is False
    assert digest(DRAFT / 'packet.json') == record['packet_sha256']
    assert digest(DRAFT / 'check.py') == record['checker_sha256']
    assert len(record['runs']) == 6 and all(row['returncode'] == 0 for row in record['runs'])
    assert {Path(row['source']).name for row in record['runs']} == {
        'GlintTextureProjectionD3D12.cpp', 'GlintTextureReadbackD3D12.cpp', 'BindGroupD3D12.cpp',
        'CommandBufferD3D12.cpp', 'projected_texture.cc', 'texture_capture.cc'}
    assert len(record['remaining_gates']) == 4 and len(record['limitations']) == 3


def test_array_native_packet_carries_selection_and_keeps_copy_boundaries_explicit():
    patch = (DRAFT / 'next.patch').read_text(encoding='utf-8-sig')
    assert 'canonical_pixel_buffer(mMipLevel, mArrayLayer)' in patch
    assert 'canonical_pixel_buffer(mipLevel, arrayLayer)' in patch
    assert 'SingleMipAndLayer(mipLevel, arrayLayer, Aspect::Color)' in patch
    assert 'copy->source.mipLevel, baseLayer + layer' in patch
    assert 'row.destinationOffset += uint64_t{layer} * stride' in patch
    assert 'layerBytes > notification.destination.size - lastOffset' in patch
    assert 'row.notification, std::move(row.snapshot)' in patch
    assert 'full.MipLevels != original.MipLevels' in patch
    assert 'full.DepthOrArraySize != original.DepthOrArraySize' in patch
    assert 'srv.Texture2DArray.FirstArraySlice == layer' in patch
    assert 'srv.Texture2DArray.MostDetailedMip == mip' in patch
    assert 'ValidateGlintSampledTextureView(device, view)' in patch
    assert 'ValidateGlintSampledTextureView(mDevice, view)' in patch
