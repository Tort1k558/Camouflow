import hashlib
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply_patch(directory, patch, *, reverse=False):
    command = ['git', '-c', 'core.autocrlf=false', 'apply']
    if reverse:
        command.append('--reverse')
    subprocess.run([*command, str(patch)], cwd=directory, check=True,
                   capture_output=True, timeout=15)


@pytest.mark.parametrize('kind', ['contexts', 'mutation', 'large'])
def test_resource_collectors_apply_independently_and_restore_exact_source(tmp_path, kind):
    packet = ENV / 'webgpu-browser-resource-regression'
    record = json.loads((packet / 'observations.json').read_bytes())['variants'][kind]
    source = ROOT / 'scripts/verify_native_webgpu_consistency.py'
    assert sha256(source) == record['base_collector_sha256']
    assert sha256(packet / f'{kind}-collector.patch') == record['patch_sha256']
    assert sha256(packet / f'{kind}-probe.js') == record['fixture_sha256']
    target = tmp_path / source.relative_to(ROOT)
    target.parent.mkdir(parents=True)
    target.write_bytes(source.read_bytes())
    patch = packet / f'{kind}-collector.patch'
    apply_patch(tmp_path, patch)
    assert sha256(target) == record['portable_collector_sha256']
    compile(target.read_text(encoding='utf-8-sig'), str(target), 'exec')
    apply_patch(tmp_path, patch, reverse=True)
    assert target.read_bytes() == source.read_bytes()


def test_portable_execution_keeps_expected_resource_failure_separate_from_reproducibility():
    packet = ENV / 'webgpu-browser-resource-regression'
    record = json.loads((packet / 'portable-execution-observations.json').read_bytes())
    assert record['reproducibility_check_passed']
    assert not record['all_browser_gates_passed']
    assert sha256(packet / 'observations.json') == record['preparation_observations_sha256']
    variants = {row['kind']: row for row in record['variants']}
    assert variants['contexts']['context_observations'] == 12
    assert variants['mutation']['mutation_cases'] == 10
    assert variants['large']['expected_native_oom_reproduced']
    assert not variants['large']['original_browser_gate_passed']
    assert all(row['independent_source_postguard_passed'] and row['independent_runtime_postguard_passed']
               for row in variants.values())
    assert record['privacy_admitted'] is record['production_admitted'] is False


def test_realtime_worklet_extension_restores_all_canonical_files(tmp_path):
    packet = ENV / 'audio-realtime-worklet'
    record = json.loads((packet / 'observations.json').read_bytes())
    patch = packet / 'fixture-extension.patch'
    assert sha256(patch) == record['patch_sha256']
    for name, pins in record['portable_source_pins'].items():
        source, target = ROOT / name, tmp_path / name
        assert sha256(source) == pins['before_sha256']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    apply_patch(tmp_path, patch)
    for name, pins in record['portable_source_pins'].items():
        assert sha256(tmp_path / name) == pins['after_sha256']
    apply_patch(tmp_path, patch, reverse=True)
    for name in record['portable_source_pins']:
        assert (tmp_path / name).read_bytes() == (ROOT / name).read_bytes()
    assert record['privacy_admitted'] is record['production_admitted'] is False


def test_imported_resource_draft_has_exact_fixture_and_no_browser_admission(tmp_path):
    packet = ROOT / 'native/drafts/webgpu-external-access-cache'
    record = json.loads((packet / 'observations.json').read_bytes())
    assert sha256(packet / 'next.patch') == record['patch_sha256']
    assert sha256(packet / 'wire-import-probe.cc') == record['fixture_sha256']
    assert sha256(packet / 'wire-import-fixture.patch') == record['fixture_patch_sha256']
    target = tmp_path / 'wire_probe.cc'
    target.write_bytes((packet / 'wire-import-probe.cc').read_bytes())
    apply_patch(tmp_path, packet / 'wire-import-fixture.patch', reverse=True)
    assert sha256(target) == record['fixture_base_sha256']
    apply_patch(tmp_path, packet / 'wire-import-fixture.patch')
    assert target.read_bytes() == (packet / 'wire-import-probe.cc').read_bytes()
    assert record['compiled_standalone'] and record['internal_control_runs'] == 54
    assert len(record['imported_runs']) == 3
    for row in record['imported_runs']:
        assert row['passed'] and row['imported_d3d12_resource']
        assert row['access_epoch_cache_detached'] and row['actual_wire_client_server_executed']
        assert row['projected_compute_values'] == 64
        assert row['capture_bytes_after_destroy'] == 0
        assert not row['browser_integrated']
    for key in ('selected', 'chromium_runtime_verified', 'producer_mutation_verified',
                'large_import_verified', 'epoch_negative_control_verified',
                'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_r3_runtime_evidence_does_not_promote_failed_audio_or_canvas():
    record = json.loads((ENV / 'webgpu-r3-runtime-observations.json').read_bytes())
    assert record['compiled'] and record['patches'] == 120
    assert not record['all_browser_gates_passed']
    main = {row['name']: row for row in record['main_gates']}
    assert all(row['terminal'] for row in main.values())
    assert main['runtime-suite']['passed'] and main['worker-startup']['passed']
    assert not main['audio-compatibility']['passed']
    extra = {row['name']: row for row in record['additional_reports']}
    assert extra['large_internal']['passed']
    assert not extra['large_canvas']['passed']
    assert not extra['large_canvas_no_export']['passed']
    assert record['privacy_admitted'] is record['production_admitted'] is False
