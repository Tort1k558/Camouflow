import hashlib
import json
import subprocess
from pathlib import Path

import pytest

PACKET = Path(__file__).resolve().parents[1] / 'native/drafts/webgpu-shared-swapchain-epoch'
PRIOR = PACKET.parent / 'webgpu-shared-read-epoch'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize('index', range(6))
def test_swapchain_descriptor_fixtures_reconstruct_and_reverse_exact_sources(tmp_path, index):
    record = json.loads((PACKET / 'observations.json').read_bytes())
    row = record['variants'][index]
    source = PACKET.parent / 'webgpu-external-access-cache/wire-import-probe.cc'
    original = json.loads((PRIOR / 'observations.json').read_bytes())
    assert sha256(source) == original['fixture_base_sha256']
    target = tmp_path / 'wire_probe.cc'
    target.write_bytes(source.read_bytes())
    name = row['name']
    chain = [PRIOR / ('two-readers-fixture.patch' if name == 'two-reader-wire-v1'
                      else 'single-reader-fixture.patch')]
    if name.startswith('shared-wire-large-'):
        dimensions = name.removeprefix('shared-wire-large-').removesuffix('-v1')
        chain.append(PRIOR / ('large-' + dimensions + '-fixture.patch'))
    command = ['git', '-c', 'core.autocrlf=false', 'apply']
    for patch in chain:
        subprocess.run([*command, str(patch)], cwd=tmp_path, check=True, capture_output=True, timeout=15)
    assert sha256(target) == row['before_sha256']
    patch = PACKET / row['patch']
    assert sha256(patch) == row['patch_sha256']
    subprocess.run([*command, str(patch)], cwd=tmp_path, check=True, capture_output=True, timeout=15)
    assert sha256(target) == row['after_sha256']
    text = target.read_text(encoding='utf-8-sig')
    assert 'WGPUSType_SharedTextureMemoryD3DSwapchainBeginState' in text
    assert 'canvasAccess.isSwapchain = true;' in text
    assert 'access.nextInChain = &canvasAccess.chain;' in text
    assert 'resumed.nextInChain = &canvasAccess.chain;' in text
    subprocess.run([*command, '--reverse', str(patch)], cwd=tmp_path, check=True, capture_output=True, timeout=15)
    assert sha256(target) == row['before_sha256']
    for patch in reversed(chain):
        subprocess.run([*command, '--reverse', str(patch)], cwd=tmp_path, check=True, capture_output=True, timeout=15)
    assert target.read_bytes() == source.read_bytes()


def test_swapchain_native_measurements_do_not_claim_a_repaired_browser():
    record = json.loads((PACKET / 'observations.json').read_bytes())
    assert record['compiled_standalone'] and record['actual_begin_access_swapchain_descriptor']
    assert record['selected'] is record['browser_integrated'] is False
    assert record['privacy_admitted'] is record['production_admitted'] is False
    assert record['manual_backend_flag_toggle'] is False
    assert record['internal_controls'] == 54 and record['imported_resource_runs'] == 18
    assert record['capture_budget_limit_bytes'] == 67108864
    negative = record['original_library_negative']
    assert negative['expected_failure'] and negative['passed'] and negative['returncode'] == 1
    assert 'SHARED_EPOCH_CACHE_MISSING' in negative['stderr']
    assert len(record['variants']) == 6
    for variant in record['variants']:
        assert len(variant['runs']) == 3
        for row in variant['runs']:
            observed = row['observed']
            assert row['passed'] and row['returncode'] == 0
            assert observed['actual_wire_client_server_executed'] and observed['native_d3d12_queue_executed']
            assert observed['imported_d3d12_resource'] and observed['access_epoch_cache_detached']
            assert observed['capture_bytes_after_first_map'] <= observed['capture_budget_limit_bytes'] == 67108864
            assert observed['capture_bytes_after_destroy'] == 0 and observed['browser_integrated'] is False
            assert row['mode'] == ('--sampled-bgra' if variant['name'].endswith('bgra-v1') else '--sampled-rgba')
            assert observed['sampled_bgra_executed'] is (row['mode'] == '--sampled-bgra')
    assert record['full_composition']['forward_patches'] == record['full_composition']['reverse_patches'] == 124
    assert record['full_composition']['browser_compiled'] is False
    assert record['required_next']


def test_swapchain_native_patch_is_bound_to_the_measured_r4_source():
    record = json.loads((PACKET / 'observations.json').read_bytes())
    previous = json.loads((PRIOR / 'observations.json').read_bytes())
    assert record['source_before_sha256'] == previous['source_after_sha256']
    patch = PACKET / 'next.patch'
    assert sha256(patch) == record['patch_sha256']
    text = patch.read_text(encoding='utf-8-sig')
    assert '+    if (!HasAccess()) return false;' in text
    assert '+        return !mIsExternalSwapChainTexture;' in text
    assert 'return contents && contents->HasAccess();' in text
    assert 'CaptureMemoryBudget' not in text and '67108864' not in text
