import hashlib
import json
from pathlib import Path

from scripts import native_build as build

ROOT = Path(__file__).resolve().parents[1]


def test_serial_links_preserve_four_job_compilation_budget():
    lines = (ROOT / 'native/args.gn').read_text(encoding='utf-8-sig').splitlines()
    assert lines.count('concurrent_links = 1') == 1
    assert build.LOCK['build_jobs'] == 4
    candidate = build.load_candidate('upstream-156-webgpu-r7')
    assert candidate['lock']['build_jobs'] == 4 and candidate['lock']['minimum_free_gib'] == 180


def test_serial_link_upgrade_restores_exact_previously_measured_args(native_args_before_serial_links):
    directory = ROOT / 'native/drafts/environment'
    record = json.loads((directory / 'serial-links-args-upgrade.json').read_bytes())
    assert record['before_sha256'] == hashlib.sha256(native_args_before_serial_links).hexdigest()
    assert record['after_sha256'] == hashlib.sha256((ROOT / 'native/args.gn').read_bytes()).hexdigest()
    assert b'concurrent_links' not in native_args_before_serial_links
    assert record['compiled'] is record['runtime_verified'] is record['production_admitted'] is False


def test_link_memory_failure_is_distinct_from_compilation_and_runtime():
    path = ROOT / 'native/drafts/upstream-156-webgpu-r7/windows-build-attempt1.json'
    record = json.loads(path.read_bytes())
    assert record['sync_passed'] and record['hooks_passed'] and record['patch_passed']
    assert record['changed_translation_units_compiled'] == 4
    assert record['failure_kind'] == 'linker-out-of-memory'
    assert record['failed_target'] == 'v8_context_snapshot_generator.exe'
    assert record['minimum_available_commit_bytes'] < 128 * 1024**2
    assert record['compiled'] is record['runtime_verified'] is record['production_admitted'] is False


def test_historical_fixture_chain_preserves_pre_link_args(host_sources_before_profile_surface,
                                                         native70_historical_source_hashes,
                                                         historical_surface_source_sha256,
                                                         native_args_before_serial_links):
    name = 'native/args.gn'
    expected = hashlib.sha256(native_args_before_serial_links).hexdigest()
    assert host_sources_before_profile_surface['sources'][name] == native_args_before_serial_links
    assert native70_historical_source_hashes[name] == expected
    assert historical_surface_source_sha256(name) == expected
