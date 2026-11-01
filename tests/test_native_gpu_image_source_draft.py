import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / 'native/drafts/canvas-gpu-image-sources'


def load_packet():
    patch = PACKET / 'canvas-gpu-image-sources.patch'
    record = json.loads((PACKET / 'source-observations.json').read_bytes())
    assert record['patch_sha256'] == hashlib.sha256(patch.read_bytes()).hexdigest()
    return record, patch.read_text(encoding='utf-8-sig')


def test_gpu_image_source_draft_binds_exact_r9_and_untouched_upstream_input():
    record, patch = load_packet()
    base = ROOT / 'native/drafts/upstream-156-canvas-r9/manifest.json'
    manifest = json.loads(base.read_bytes())
    assert record['candidate_base'] == 'upstream-156-canvas-r9'
    assert record['base_manifest_sha256'] == hashlib.sha256(base.read_bytes()).hexdigest()
    assert record['source_forward_and_reverse_passed']
    assert record['source_files_count'] == len(record['source_files']) == 6
    assert set(re.findall(r'^diff --git a/(\S+) b/\S+$', patch, re.M)) == set(record['source_files'])
    assert set(record['base_source_bindings']) == set(record['source_files'])
    upstream = []
    for name, binding in record['base_source_bindings'].items():
        assert binding['sha256'] == record['source_files'][name]['before']
        if binding['kind'] == 'untouched-pinned-upstream-blob':
            upstream.append(name)
            assert binding['revision'] == manifest['target_revision']
            assert re.fullmatch('[0-9a-f]{40}', binding['git_blob_oid'])
        else:
            assert binding['kind'] == 'verified-r9-owned-composition'
    assert upstream == ['third_party/blink/renderer/modules/webgpu/gpu_canvas_context.cc']


def test_gpu_image_source_type_checks_do_not_admit_native_or_runtime_results():
    record, _ = load_packet()
    accepted = [target for check in record['syntax_checks'] for target in check['accepted_targets']]
    assert record['syntax_type_checked_translation_units'] == len(accepted) == 5
    assert len({target['source'] for target in accepted}) == 5
    assert all(target['returncode'] == 0 for target in accepted)
    assert record['prepared_native_tests'] == 7
    assert record['earlier_failures_preserved'] and len(record['earlier_attempts']) == 2
    for field in ('selected', 'active_checkout_modified', 'compiled_browser', 'native_tests_executed',
                  'runtime_verified', 'original_r9_failure_repaired', 'privacy_admitted', 'production_admitted'):
        assert record[field] is False
    assert len(record['known_gaps']) == 3


def test_gpu_image_source_prepared_cases_are_present_in_the_actual_native_patch():
    record, patch = load_packet()
    cases = re.findall(r'TEST\(GlintGPUCanvasImageSourceTest,\s*(\w+)\)', patch)
    assert len(cases) == len(set(cases)) == 7
    assert cases == record['prepared_native_cases']
    assert 'std::array<uint8_t, 64> pixels{};' in patch
    assert 'SkImages::RasterFromPixmapCopy(SkPixmap(info, pixels.data(), 16))' in patch
    assert 'bytes[start]' not in patch


def test_gpu_image_source_resolution_stays_explicit_v2_and_source_owned():
    _, patch = load_packet()
    assert 'rendering->pipeline != CanvasPipeline::kRenderingV2' in patch
    assert 'CanvasExportPartitionSeed(\n+      owner, CanvasExportSurfaceForContext(source_context))' in patch
    assert 'GetExecutionContext(), RenderingContext()' in patch
    assert 'GetTopExecutionContext(), RenderingContext()' in patch
    assert patch.count('GetExecutionContext(), this)') == 2
    assert 'return base::unexpected(SurfaceSeedError::kInvalidPolicy);' in patch


def test_gpu_image_source_preserves_origin_and_propagates_protected_copy_failure():
    _, patch = load_packet()
    assert 'const bool origin_clean = source->OriginClean();' in patch
    assert 'result.value()->SetOriginClean(origin_clean);' in patch
    assert 'std::move(source), *partition_seed, memory_limit_bytes)' in patch
    assert 'return base::unexpected(result.error());' in patch
    assert patch.count('if (!glint_source_seed.value())') == 2
    assert 'Glint GPU image source copy failed.' in patch
    assert 'Glint GPU image source policy is unavailable.' in patch
