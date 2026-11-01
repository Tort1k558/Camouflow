import hashlib
import json
from pathlib import Path
import re

from scripts.native_build import load_candidate

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / 'native/drafts/canvas-opaque-sources'


def test_opaque_source_patch_is_an_unselected_r10_extension_with_exact_preimages():
    record = json.loads((PACKET / 'source-observations.json').read_bytes())
    patch = PACKET / 'canvas-opaque-sources.patch'
    candidate = load_candidate('upstream-156-image-r10')
    parent = json.loads((ROOT / 'native/drafts/canvas-owned-raster/source-observations.json').read_bytes())
    assert record['base_manifest_sha256'] == candidate['manifest_sha256']
    assert record['patch_sha256'] == hashlib.sha256(patch.read_bytes()).hexdigest()
    assert record['changed_files'] == len(record['source_files']) == 2
    for name, row in record['source_files'].items():
        assert row['before'] == parent['source_files'][name]['after']
        assert row['before'] != row['after']
    assert record['forward_reverse_passed']
    assert record['type_checked_translation_units'] == len(record['syntax_targets']) == 3
    assert all(row['returncode'] == 0 for row in record['syntax_targets'])
    for name in ('selected', 'active_checkout_modified', 'compiled_browser', 'native_tests_executed',
                 'runtime_verified', 'privacy_admitted', 'production_admitted'):
        assert record[name] is False


def test_new_native_cases_keep_ownership_budget_and_pixel_algorithm_contracts():
    record = json.loads((PACKET / 'source-observations.json').read_bytes())
    patch = (PACKET / 'canvas-opaque-sources.patch').read_text(encoding='utf-8-sig')
    assert re.findall(r'TEST\(GlintOpaqueCanvasImageSourceTest,\s*(\w+)\)', patch) == record['native_new_cases']
    assert record['prepared_native_tests'] == len(record['native_new_cases']) == 5
    production = patch.split('diff --git a/third_party/blink/renderer/modules/')[0]
    added = [line[1:] for line in production.splitlines() if line.startswith('+') and not line.startswith('+++')]
    assert added == ['       type != kRGB_888x_SkColorType &&']
    assert record['private_pixel_buffer_budget_bytes'] == 64*1024*1024
    assert record['pixel_transform_algorithm_changed'] is False
    assert record['owned_raster_normalization_requirement_retained']
    assert 'TransformOwnedCanvasCopy(std::move(owned), seed, true)' in patch
    assert 'CanvasCopyError::kUnsupportedFormat' in patch
    assert 'ProtectGPUCanvasImageSource(source, seed, 63)' in patch
    assert 'ProtectGPUCanvasImageSource(source, seed, 64)' in patch


def test_diagnostics_preserve_failed_opaque_paths_without_discarding_successful_copies():
    record = json.loads((PACKET / 'runtime-observations.json').read_bytes())
    assert record['passed'] is record['opaque_source_repair_verified'] is False
    assert record['direct_copy_attempts'] == 32 and record['direct_copies_exact'] == 28
    copies = [copy for row in record['direct_rows'] for copy in row['copies']]
    assert sum(copy['passed'] for copy in copies) == 28
    failed = [copy for copy in copies if not copy['passed']]
    assert len(failed) == record['direct_creation_failures'] == 4
    assert all(copy['name'] == 'transferToImageBitmap' and copy['creationFailed'] for copy in failed)
    assert all(row['passed'] == row['alpha'] for row in record['frame_rows'])
    assert record['alpha_enabled_frame_copies_exact'] == 20
    assert record['opaque_frame_variants_unreadable'] == 2
    assert record['source_core_driver_asset_postguards_passed'] and record['owned_resources_closed']
    assert record['original_failures_preserved'] and not record['production_admitted']
    for name, digest in record['probe_sha256'].items():
        assert hashlib.sha256((PACKET / name).read_bytes()).hexdigest() == digest
