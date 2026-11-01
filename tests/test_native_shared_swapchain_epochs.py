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


@pytest.mark.parametrize('index', range(3))
def test_swapchain_resource_supplement_reconstructs_measured_fixture(tmp_path, index):
    record = json.loads((PACKET / 'resource-supplement.json').read_bytes())
    row = record['variants'][index]
    source = PACKET.parent / 'webgpu-external-access-cache/wire-import-probe.cc'
    target = tmp_path / 'wire_probe.cc'
    target.write_bytes(source.read_bytes())
    command = ['git', '-c', 'core.autocrlf=false', 'apply']
    chain = [PRIOR / name for name in row['preceding_patches']]
    for patch in chain:
        subprocess.run([*command, str(patch)], cwd=tmp_path, check=True, capture_output=True, timeout=15)
    assert sha256(target) == row['before_sha256']
    patch = PACKET / row['patch']
    assert sha256(patch) == row['patch_sha256']
    subprocess.run([*command, str(patch)], cwd=tmp_path, check=True, capture_output=True, timeout=15)
    assert sha256(target) == row['after_sha256']
    text = target.read_text(encoding='utf-8-sig')
    assert 'canvasAccess.isSwapchain = true;' in text
    assert row['descriptors_marked_swapchain'] == ['initialProducerAccess', 'access', 'producerAccess', 'resumed']
    for name in row['descriptors_marked_swapchain']:
        assert f'{name}.nextInChain = &canvasAccess.chain;' in text
    if row['name'] == 'unowned-swapchain-wrapper-v1':
        assert 'Texture::CreateForSwapChain(' in text
        assert 'unowned->GetSharedResourceMemoryContents() == nullptr' in text
        assert text.count('Check(!unowned->GetGlintProjection(') == 2
    subprocess.run([*command, '--reverse', str(patch)], cwd=tmp_path, check=True, capture_output=True, timeout=15)
    assert sha256(target) == row['before_sha256']
    for patch in reversed(chain):
        subprocess.run([*command, '--reverse', str(patch)], cwd=tmp_path, check=True, capture_output=True, timeout=15)
    assert target.read_bytes() == source.read_bytes()


def test_swapchain_resource_supplement_keeps_failures_and_admission_separate():
    record = json.loads((PACKET / 'resource-supplement.json').read_bytes())
    original = json.loads((PACKET / 'observations.json').read_bytes())
    assert record['initial_observations_sha256'] == sha256(PACKET / 'observations.json')
    assert record['native_source_sha256'] == original['source_after_sha256']
    assert record['selected'] is record['browser_integrated'] is False
    assert record['privacy_admitted'] is record['production_admitted'] is False
    assert len(record['variants']) == 3
    for variant in record['variants']:
        assert variant['real_begin_access_descriptor'] is True
        assert len(variant['runs']) == 3
        for row in variant['runs']:
            measured = row['observed']
            assert row['passed'] and row['returncode'] == 0
            assert measured['actual_wire_client_server_executed'] and measured['native_d3d12_queue_executed']
            assert measured['producer_epoch_mutation'] and measured['old_cpu_snapshot_immutable']
            assert measured['capture_bytes_after_destroy'] == 0
            assert measured['capture_budget_limit_bytes'] == record['capture_budget_limit_bytes'] == 67108864
            assert measured['browser_integrated'] is False
            if variant['name'] != 'swapchain-producer-v1':
                assert measured['live_device_budget_drained'] and measured['device_usable_after_drain']
            if variant['name'] == 'unowned-swapchain-wrapper-v1':
                assert measured['unowned_wrapper_cache_excluded']
    negative = record['missing_invalidation_negative']
    patch = PACKET / negative['patch']
    assert sha256(patch) == negative['patch_sha256']
    assert negative['source_before_sha256'] == record['native_source_sha256']
    assert negative['only_two_clear_calls_removed'] is True
    removed = [line for line in patch.read_text(encoding='utf-8').splitlines()
               if line.startswith('-') and not line.startswith('---')]
    added = [line for line in patch.read_text(encoding='utf-8').splitlines()
             if line.startswith('+') and not line.startswith('+++')]
    assert removed == ['-    ClearGlintProjection();'] * 2 and not added
    assert len(negative['runs']) == 3
    for row in negative['runs']:
        assert row['returncode'] == 1 and 'SHARED_EPOCH_STALE_GPU index=' in row['stderr']
        assert 'E_OUTOFMEMORY' not in row['stderr']
    incomplete = record['inconclusive_original_large_oom_attempt']
    assert incomplete['passed'] is incomplete['exact_out_of_memory_cause_proven'] is False
    assert incomplete['device_loss_observed'] and 'is lost' in incomplete['stderr']
    assert record['remaining']


def test_swapchain_repository_form_changes_only_the_dawn_path_prefix():
    record = json.loads((PACKET / 'repository-form.json').read_bytes())
    original = PACKET / record['original_patch']
    owned = PACKET / record['repository_patch']
    assert record['repository'] == 'third_party/dawn' and record['browser_integrated'] is False
    assert sha256(original) == record['original_patch_sha256']
    assert sha256(owned) == record['repository_patch_sha256']
    assert owned.read_bytes() == original.read_bytes().replace(
        b'a/third_party/dawn/', b'a/').replace(b'b/third_party/dawn/', b'b/')
