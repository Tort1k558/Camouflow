import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / 'native/drafts/canvas-owned-raster'


def load_packet():
    record = json.loads((PACKET / 'source-observations.json').read_bytes())
    patch = PACKET / 'canvas-owned-raster.patch'
    assert record['patch_sha256'] == hashlib.sha256(patch.read_bytes()).hexdigest()
    return record, patch.read_text(encoding='utf-8-sig')


def test_owned_raster_extension_binds_both_parent_packets_and_exact_overlay():
    record, patch = load_packet()
    for name, digest in record['parent_packets_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    frame = json.loads((ROOT / 'native/drafts/canvas-frame-provenance/source-observations.json').read_bytes())
    assert record['base_manifest_sha256'] == frame['base_manifest_sha256']
    assert record['composed_forward_reverse_passed']
    assert record['overlay_source_files'] == len(record['source_files']) == 12
    changed = {name for name, row in record['source_files'].items() if row['before'] != row['after']}
    assert len(changed) == record['changed_files'] == 5
    assert set(re.findall(r'^diff --git a/(\S+) b/\S+$', patch, re.M)) == changed
    for name, binding in record['canonical_source_bindings'].items():
        if binding['kind'] == 'bound-frame-composition':
            assert binding['parent_after_sha256'] == frame['source_files'][name]['after']
            assert record['source_files'][name]['before'] == binding['parent_after_sha256']
        else:
            assert binding['kind'] == 'verified-r9-owned-composition'
            assert binding['canonical_sha256'] == record['source_files'][name]['before']


def test_owned_raster_cpp_checks_do_not_become_native_or_runtime_results():
    record, patch = load_packet()
    assert record['type_checked_translation_units'] == len(record['syntax_targets']) == 8
    assert len({row['source'] for row in record['syntax_targets']}) == 8
    assert all(row['returncode'] == 0 for row in record['syntax_targets'])
    cases = re.findall(r'TEST\(GlintOwnedCanvasCopyTest,\s*(\w+)\)', patch)
    assert cases == record['native_new_cases'] and len(cases) == record['prepared_native_tests'] == 10
    assert record['composed_native_cases']['GlintOwnedCanvasCopyTest'] == cases
    assert sum(map(len, record['composed_native_cases'].values())) == record['composed_prepared_native_tests'] == 21
    for field in ('selected', 'active_checkout_modified', 'compiled_browser', 'native_tests_executed',
                  'runtime_verified', 'original_r9_failure_repaired', 'privacy_admitted', 'production_admitted'):
        assert record[field] is False
    assert record['earlier_preparation_failure_preserved']


def test_owned_raster_keeps_budget_and_pixel_transform_without_second_full_copy():
    record, patch = load_packet()
    added = '\n'.join(line[1:] for line in patch.splitlines() if line.startswith('+') and not line.startswith('+++'))
    assert record['private_pixel_buffer_budget_bytes'] == 64*1024*1024
    assert record['full_size_private_rasters'] == 1 and record['pixel_transform_algorithm_changed'] is False
    assert record['owned_budget_does_not_bound_skia_gpu_internal_staging']
    assert 'if (bytes > memory_limit_bytes)' in added
    assert 'memory_limit_bytes / 2' not in added
    assert 'auto copy = TransformOwnedCanvasCopy(' in added
    assert 'CreateProtectedCanvasCopy(raster.pixmap()' not in added
    assert 'TransformEdgeCoherentCanvasF16(' in added
    assert 'TransformEdgeCoherentCanvas(' in added
    assert not any(name.startswith('gpu/command_buffer/') for name in record['source_files'])


def test_owned_raster_guards_shared_immutable_subset_padded_and_wrong_format_data():
    _, patch = load_packet()
    for condition in ('!pixels->unique()', 'owned.isImmutable()',
                      'pixels->pixels() != owned.getPixels()',
                      'pixels->width() != owned.width()', 'pixels->height() != owned.height()',
                      'pixels->rowBytes() != owned.rowBytes()',
                      'owned.colorType() != kRGBA_8888_SkColorType',
                      'owned.alphaType() != kUnpremul_SkAlphaType'):
        assert condition in patch
    assert 'owned.notifyPixelsChanged();' in patch and 'owned.setImmutable();' in patch
    assert 'result->SetOriginClean(source->OriginClean());' in patch
    assert 'ProtectGPUCanvasImageSource(source, seed, 63)' in patch
    assert 'ProtectGPUCanvasImageSource(source, seed, 64)' in patch


def test_large_image_fixture_is_prepared_not_a_claim_of_measured_4k_support():
    record, patch = load_packet()
    assert 'Full4096RasterFitsUnchanged64MiBImageBudget' in record['native_new_cases']
    assert '4096, 4096, kRGBA_8888_SkColorType' in patch
    assert 'constexpr size_t kBudget = 64U * 1024U * 1024U;' in patch
    assert 'CreateProtectedCanvasImage(source, seed, kBudget - 1)' in patch
    assert 'CreateProtectedCanvasImage(source, seed, kBudget)' in patch
    assert record['native_tests_executed'] is record['runtime_verified'] is False


def test_complete_recipe_replay_is_not_registered_or_built_runtime_evidence():
    record = json.loads((PACKET / 'full-composition-observations.json').read_bytes())
    assert record['passed'] and record['prepared_candidate'] == 'upstream-156-image-r10'
    assert record['forward_patches'] == record['reverse_patches'] == 135
    assert record['final_owned_files_matched'] == 406 and record['upstream_files_restored'] == 273
    assert re.fullmatch('[0-9a-f]{64}', record['manifest_sha256'])
    for field in ('canonical_sources_modified', 'registered', 'compiled', 'native_tests_executed',
                  'runtime_verified', 'privacy_admitted', 'production_admitted'):
        assert record[field] is False
