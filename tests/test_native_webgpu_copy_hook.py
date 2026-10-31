"""Trusted native notifications are not registered observers or protected mappings."""
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/environment'


def preparation():
    return json.loads((DIRECTORY / 'webgpu-native-copy-hook-preparation.json').read_bytes())


def test_native_copy_packet_binds_checked_sources_without_changing_capture_budget_core(tmp_path):
    record = preparation()
    patch = DIRECTORY / record['patch']
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    assert len(record['sources']) == 16 and record['exact_patch_roundtrip_verified']
    assert record['replacement_for'] == 'webgpu-d3d12-budget-next.patch'
    assert record['apply_both_native_packets'] is False
    evidence = DIRECTORY / record['inherited_capture_budget_evidence']
    assert hashlib.sha256(evidence.read_bytes()).hexdigest() == record['inherited_capture_budget_evidence_sha256']
    assert record['capture_budget_core_unchanged']
    command = ['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error',
               '--include=third_party/dawn/src/dawn/native/d3d12/glint/*']
    subprocess.run(command + [str(patch)], cwd=tmp_path, check=True, capture_output=True, timeout=15)
    rows = [row for row in record['sources'] if '/glint/' in row['source']]
    assert len(rows) == 2 and all(row['before_sha256'] is None for row in rows)
    for row in rows:
        data = (tmp_path / row['source']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == row['staged_sha256']
        assert data == (ROOT / 'native/drafts/webgpu-d3d12-capture' / Path(row['source']).name).read_bytes()
    subprocess.run(command + ['--reverse', str(patch)], cwd=tmp_path, check=True,
                   capture_output=True, timeout=15)
    assert all(not (tmp_path / row['source']).exists() for row in rows)


def test_native_copy_and_write_notifications_do_not_claim_runtime_or_pixel_transform():
    record = preparation()
    assert len(record['syntax_checks']) == 9 and record['syntax_diagnostic_bytes'] == 0
    assert all(row['returncode'] == 0 for row in record['syntax_checks'])
    assert record['registered_backend'] == 'D3D12' and record['registration_once']
    assert record['observer_pointer_synchronized'] and record['trusted_native_copy_hook_prepared']
    assert record['snapshot_copy_recorded_before_roi_copy']
    assert record['successful_snapshot_notification_follows_roi_recording']
    assert record['uncertain_map_write_clears_provenance'] is False
    assert set(record['notification_paths']) == {
        'texture-to-buffer', 'buffer-to-buffer', 'queue-write-buffer', 'encoded-write-buffer',
        'clear-buffer', 'write-map-unmap', 'buffer-destroy'}
    for key in ('selected', 'default_observer_registered', 'gpu_service_observer_registered',
                'native_capture_hook_activated', 'observer_callbacks_runtime_verified',
                'native_map_shadow_installed', 'native_pixel_transform_installed',
                'shader_taint_propagation_installed', 'shared_memory_map_protected',
                'chromium_component_link_verified', 'runtime_verified',
                'privacy_admitted', 'production_admitted', 'canvas_gpu_export_mismatch_resolved'):
        assert record[key] is False


def test_native_observer_interface_stays_borrowed_and_does_not_require_api_library_destructors():
    record = preparation()
    text = (DIRECTORY / record['patch']).read_text(encoding='utf-8-sig')
    assert '+    virtual ~GlintReadbackSnapshot() = default;' in text
    assert '+    virtual ~GlintReadbackObserver() = default;' in text
    assert 'GlintReadbackSnapshot::~GlintReadbackSnapshot()' not in text
    assert '+enum class GlintBufferWriteKind { Uncertain, KnownBytes };' in text
    assert 'observer->OnBufferDestroyed(ToAPI(this));' in text
    assert 'GlintBufferWriteKind::Uncertain' in text
    assert 'GlintBufferWriteKind::KnownBytes' in text
    assert 'observer->OnTextureToBufferCopy(notification, nullptr);' in text
    assert 'observer->OnTextureToBufferCopy(notification, std::move(snapshot));' in text
    assert 'GetBackendType() != wgpu::BackendType::D3D12' in text


def test_full_gpu_budget_python_result_predates_native_copy_observer():
    record = json.loads((DIRECTORY / 'canonical-python76-d3d12-budget-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['git_head'].startswith('975bb87')
    assert record['counts'] == dict(tests=5048, passed=5047, skipped=1, failures=0, errors=0)
    assert record['native_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False


def test_native_observer_gn_checks_preserve_dawn_and_existing_builds_without_claiming_linkage():
    record = json.loads((DIRECTORY / 'webgpu-native-copy-gn-observations.json').read_bytes())
    source = preparation()
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['patch_sha256'] == source['patch_sha256'] and record['sources'] == source['sources']
    assert record['source_rollback_verified'] and record['original_git_indexes_unchanged']
    assert record['dawn_git_index_unchanged'] and record['original_build_outputs_unchanged']
    assert {row['mode'] for row in record['graphs']} == {'static', 'component'}
    for row in record['graphs']:
        assert row['targets'] > 30000 and row['build_files'] == 5063
        assert {check['name'] for check in row['checks']} == {
            row['mode'] + suffix for suffix in ('-gen', '-native-sources-check',
                                               '-native-api-static-check', '-native-api-shared-check')}
        for check in row['checks']:
            assert check['returncode'] == 0
            assert hashlib.sha256(check['stdout'].encode('utf-8')).hexdigest() == check['log_sha256']
    for key in ('selected', 'native_compilation_started', 'chromium_component_link_verified',
                'gpu_service_observer_registered', 'observer_callbacks_runtime_verified',
                'native_map_shadow_installed', 'native_pixel_transform_installed',
                'runtime_verified', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False
