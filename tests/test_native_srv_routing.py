import hashlib
import json
from pathlib import Path

from scripts import native_build as build

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / 'native/drafts/webgpu-srv-routing'


def observation():
    return json.loads((PACKET / 'observations.json').read_bytes())


def test_srv_packet_binds_actual_sources_and_keeps_scope_separate():
    record = observation()
    for name, digest in record['public_inputs_sha256'].items():
        assert hashlib.sha256((PACKET / name).read_bytes()).hexdigest() == digest
    assert record['compiled'] and record['input_postguards_passed']
    assert len(record['engine_sources']) == 2
    for key in ('browser_runtime_verified', 'physical_tdr_tested', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_actual_corrected_matrix_includes_sampled_formats_and_indirect_boundaries():
    record = observation()
    assert record['standalone_case_matrix_passed']
    rows = record['corrected_cases']
    assert len(rows) == 54 and all(row['passed'] for row in rows)
    assert {row['attempt'] for row in rows} == {1, 2, 3}
    for mode in ('--sampled-rgba', '--sampled-bgra', '--indirect-readonly', '--indirect-zero', '--indirect-offset'):
        selected = [row for row in rows if row['mode'] == mode]
        assert len(selected) == 3
        for row in selected:
            value = row['observation']
            assert row['returncode'] == 0 and value['actual_wire_client_server_executed']
            assert value['capture_bytes_after_destroy'] == 0
            assert value['projected_compute_values'] == (0 if mode == '--indirect-zero' else 64)
            assert value['browser_integrated'] is False
            if mode.startswith('--sampled-'):
                assert value['sampled_texture_executed']
                assert value['sampled_bgra_executed'] == (mode == '--sampled-bgra')
            else:
                assert value['indirect_dispatch_executed']
                assert value['zero_work_output_unchanged'] == (mode == '--indirect-zero')
                assert value['indirect_offset_bytes'] == (16 if mode == '--indirect-offset' else 0)


def test_before_after_controls_observe_the_exact_native_rejection():
    record = observation()
    assert record['controlled_before_after_passed']
    rows = record['controlled_cases']
    assert len(rows) == 12 and all(row['passed'] for row in rows)
    for row in rows:
        before = row['variant'] == 'control-link'
        assert row['returncode'] == int(before)
        assert row['device_lost_observed'] == row['exact_descriptor_error_observed'] == before


def test_revision_two_preserves_the_entire_measured_candidate_prefix():
    before = build.load_candidate('upstream-156-webgpu')
    after = build.load_candidate('upstream-156-webgpu-r2')
    original = before['manifest']
    manifest = after['manifest']
    assert manifest['patches'][:116] == original['patches']
    assert len(manifest['patches']) == 118
    for key in ('source_files', 'dependencies', 'build', 'target_revision', 'target_version', 'component_batch'):
        assert manifest[key] == original[key]
    assert manifest['extension_batch']['base_manifest_sha256'] == before['manifest_sha256']
    assert manifest['extension_batch']['packet_sha256'] == hashlib.sha256((PACKET / 'observations.json').read_bytes()).hexdigest()
    assert after['lock']['minimum_free_gib'] == 180 and after['lock']['build_jobs'] == 4
    for key in ('compiled', 'runtime_verified', 'production_admitted'):
        assert manifest[key] is False
    rows = build.expected_candidate_patches(manifest)
    assert len(rows) == 118
    assert all(row['directory'] == 'third_party/dawn' for row in manifest['patches'][116:])


def test_revision_two_reuses_only_the_same_pinned_checkout_family(tmp_path):
    before = build.load_candidate('upstream-156-webgpu')
    after = build.load_candidate('upstream-156-webgpu-r2')
    build.candidate_workspace(tmp_path, before, claim=True)
    marker = tmp_path / 'glint-build-candidate.json'
    original = marker.read_bytes()
    build.candidate_workspace(tmp_path, after)
    assert marker.read_bytes() == original
    assert after['manifest_sha256'] != before['manifest_sha256']


def test_revision_two_source_replay_is_not_runtime_admission():
    candidate = build.load_candidate('upstream-156-webgpu-r2')
    proof = json.loads((candidate['directory'] / 'preparation.json').read_bytes())
    assert proof['passed'] and proof['manifest_sha256'] == candidate['manifest_sha256']
    assert proof['forward_patches'] == proof['reverse_patches'] == 118
    assert proof['upstream_files_restored'] == 268
    assert proof['standalone_engine_sources_matched'] == 2
    for key in ('compiled', 'runtime_verified', 'privacy_admitted', 'production_admitted'):
        assert proof[key] is False


def test_descriptor_patch_keeps_exact_shape_and_source_ownership_checks():
    patch = (PACKET / 'srv-routing.patch').read_text(encoding='utf-8-sig')
    for expression in ('srv.Texture2DArray.ArraySize == 1', 'srv.Texture2DArray.FirstArraySlice == 0',
                       'srv.Texture2DArray.PlaneSlice == 0', 'srv.Texture2DArray.MipLevels == 1',
                       'view->GetLayerCount() != 1', 'view->GetDimension() != wgpu::TextureViewDimension::e2D',
                       '(!exact2D && !exactArray)'):
        assert expression in patch
    assert 'CreateShaderResourceView' not in patch
