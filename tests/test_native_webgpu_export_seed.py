"""A coherent seed-selection draft is not installed WebGPU readback protection."""
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/environment'


def preparation():
    return json.loads((DIRECTORY / 'webgpu-export-seed-preparation.json').read_bytes())


def test_export_seed_packet_binds_both_prerequisites_instead_of_overwriting_gn_edits():
    record = preparation()
    patch = DIRECTORY / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    assert len(record['sources']) == 7 and record['sparse_roundtrip_verified']
    assert {row['patch'] for row in record['prerequisites']} == {
        'shared-gpu-readback-core-next.patch', 'webgpu-renderer-policy-transport-next.patch'}
    for row in record['prerequisites']:
        assert hashlib.sha256((DIRECTORY / row['patch']).read_bytes()).hexdigest() == row['sha256']
    shared = json.loads((DIRECTORY / 'shared-gpu-readback-core-preparation.json').read_bytes())
    transport = json.loads((DIRECTORY / 'webgpu-renderer-policy-transport-preparation.json').read_bytes())
    name = 'gpu/command_buffer/common/BUILD.gn'
    assert record['overlapping_prerequisite_paths_merged'] == [name]
    merged = next(row['before_sha256'] for row in record['sources'] if row['source'] == name)
    assert merged != next(row['after_sha256'] for row in shared['sources'] if row['source'] == name)
    assert merged != next(row['staged_sha256'] for row in transport['sources'] if row['source'] == name)


def test_common_feature_declaration_and_definition_round_trip_exactly(tmp_path):
    record = preparation()
    patch = DIRECTORY / record['patch']
    include = '--include=gpu/command_buffer/common/glint/webgpu_readback_features.*'
    command = ['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error', include]
    subprocess.run(command + [str(patch)], cwd=tmp_path, check=True, capture_output=True, timeout=15)
    rows = [row for row in record['sources'] if '/webgpu_readback_features.' in row['source']]
    assert len(rows) == 2 and all(row['before_sha256'] is None for row in rows)
    for row in rows:
        path = tmp_path / row['source']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['after_sha256']
        assert not path.read_bytes().startswith(bytes.fromhex('efbbbf')) and b'\r' not in path.read_bytes()
    text = (tmp_path / rows[0]['source']).read_text(encoding='utf-8')
    assert 'FEATURE_DISABLED_BY_DEFAULT' in text
    subprocess.run(command + ['--reverse', str(patch)], cwd=tmp_path, check=True,
                   capture_output=True, timeout=15)
    assert all(not (tmp_path / row['source']).exists() for row in rows)


def test_syntax_checked_export_selection_keeps_missing_seed_and_runtime_boundaries_explicit():
    record = preparation()
    assert record['passed'] and record['syntax_verified'] and record['syntax_diagnostic_bytes'] == 0
    assert len(record['syntax_checks']) == 4
    assert all(row['returncode'] == 0 for row in record['syntax_checks'])
    assert record['feature'] == 'GlintWebGPUPolicyTransportCandidate'
    assert record['feature_declared_in_gpu_common'] and not record['feature_default_enabled']
    assert record['missing_required_seed_allows_raw_export'] is False
    assert record['global_blink_feature_header_changed'] is False
    patch = (DIRECTORY / record['patch']).read_text(encoding='utf-8-sig')
    assert '+enum class CanvasExportSurface { kCanvas, kWebGL, kWebGPU };' in patch
    assert '+      return base::unexpected(SurfaceSeedError::kUnsupportedKind);' in patch
    assert '+        kind = SurfaceSeedKind::kWebGPU;' in patch
    assert patch.count('+        glint::candidate::CanvasExportSurfaceForContext(RenderingContext()));') == 2
    assert 'CanvasExportSurfaceForContext(context_.Get())' in patch
    for key in ('selected', 'feature_default_enabled', 'gn_verified', 'browser_integrated', 'runtime_verified',
                'native_queue_hooks_installed', 'native_webgpu_readback_protection',
                'canvas_gpu_export_mismatch_resolved', 'chromium_component_link_verified',
                'document_worker_runtime_verified', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_coupled_gn_graphs_cover_all_three_packets_without_native_or_runtime_admission():
    record = json.loads((DIRECTORY / 'webgpu-export-coupled-gn-observations.json').read_bytes())
    seed = preparation()
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['source_rollback_verified'] and record['original_build_outputs_unchanged']
    assert record['original_git_indexes_unchanged']
    audit = record['additional_checkout_verification']
    assert audit['passed'] and audit['postguards_passed'] and audit['patches'] == 76
    assert audit['cached_index_matches_head'] and audit['traced_index_writes_private_only']
    assert audit['retained_prior_negative']['source_chain_validation_returned'] == 76
    assert 'Origin not established' in audit['retained_prior_negative']['cause']
    assert record['prerequisites'] == [*seed['prerequisites'], dict(patch=seed['patch'], sha256=seed['patch_sha256'])]
    for row in record['prerequisites']:
        assert hashlib.sha256((DIRECTORY / row['patch']).read_bytes()).hexdigest() == row['sha256']
    assert len(record['composed_source_sha256']) == seed['combined_source_paths'] == 37
    assert record['composed_patch_sha256'] == seed['combined_patch_sha256']
    for row in seed['sources']:
        assert next(value['after_sha256'] for value in record['composed_source_sha256']
                    if value['source'] == row['source']) == row['after_sha256']
    assert {row['mode'] for row in record['graphs']} == {'static', 'component'}
    for row in record['graphs']:
        assert row['targets'] > 30000 and row['build_files'] == 5063
        assert {check['name'] for check in row['checks']} == {
            row['mode'] + suffix for suffix in ('-gen', '-common-check', '-blink-check', '-modules-check', '-service-check')}
        for check in row['checks']:
            assert check['returncode'] == 0
            assert hashlib.sha256(check['stdout'].encode('utf-8')).hexdigest() == check['log_sha256']
            assert ('Done. Made' if check['name'].endswith('-gen') else 'Header dependency check OK') in check['stdout']
    for key in ('selected', 'native_compilation_started', 'chromium_component_link_verified',
                'native_queue_hooks_installed', 'runtime_verified', 'canvas_gpu_export_mismatch_resolved',
                'privacy_admitted', 'production_admitted'):
        assert record[key] is False
