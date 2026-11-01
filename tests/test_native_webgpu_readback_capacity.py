import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/webgpu-readback-capacity'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def packet():
    return json.loads((DIRECTORY / 'packet.json').read_text(encoding='utf-8'))


def test_capacity_packet_binds_exact_r6_without_claiming_admission():
    record = packet()
    assert record['base_candidate'] == 'upstream-156-webgpu-r6'
    assert record['base_candidate_manifest_sha256'] == digest(ROOT / 'native/drafts/upstream-156-webgpu-r6/manifest.json')
    assert record['repository'] == '.'
    assert record['selected'] is False and record['browser_integrated'] is False
    assert record['per_buffer_region_limit'] == 16
    assert record['snapshot_slot_hard_limit'] == 4096
    assert record['default_buffer_budget'] == 256
    assert record['snapshot_data_budget_bytes'] == record['map_shadow_limit_bytes'] == 64 * 1024 * 1024


def test_capacity_packet_contains_only_six_owned_chromium_files():
    record = packet()
    patch = DIRECTORY / record['patch']
    assert digest(patch) == record['patch_sha256']
    assert digest(DIRECTORY / 'fixture.cc') == record['fixture_sha256']
    text = patch.read_text(encoding='utf-8')
    before = re.findall(r'^--- a/(.+)$', text, re.M)
    after = re.findall(r'^\+\+\+ b/(.+)$', text, re.M)
    assert before == after and len(after) == len(set(after)) == 6
    assert set(after) == set(record['source_files'])
    assert set(after).issubset(record['source_inputs_sha256'])
    assert 'std::min(limits.buffers,' in text
    for name, row in record['source_files'].items():
        assert row['before_sha256'] == record['source_inputs_sha256'][name]
        assert row['before_sha256'] != row['after_sha256']
        assert name.startswith('gpu/command_buffer/common/glint/') or name in {
            'gpu/command_buffer/service/glint_webgpu_readback_observer.h',
            'gpu/command_buffer/service/glint_webgpu_readback_observer.cc',
        }


def test_capacity_fixture_retains_exact_coverage_and_negative_controls():
    text = (DIRECTORY / 'fixture.cc').read_text(encoding='utf-8')
    for required in ('VerifyLedgerTests()', 'VerifyPublicationTests()', 'WebGpuCapturedByte',
                     'WebGpuCanonicalByte', 'BuildProtectedShadow', 'RecordBufferCopy',
                     'RecordUncertainWrite', 'kWebGpuReadbackRegionLimit != 16',
                     'snapshot_capacity() != 48', 'byte_limited.reserved_bytes()!=128',
                     'kWebGpuSnapshotSlotLimit+1', 'id<=24', 'std::move(retained)', '1080u'):
        assert required in text
    checker = (DIRECTORY / 'check.py').read_text(encoding='utf-8')
    assert "for mode in ('normal', 'address')" in checker
    assert 'require_idle_builder' in checker and '-vfsoverlay' in checker
    assert 'source.is_dir()' in checker and "path.drive.upper() != 'D:'" in checker
    assert 'Wno-unsafe' not in checker and 'unsafe-buffer-usage' not in checker


def test_capacity_observations_bind_public_checker_and_source_postimages():
    record = packet()
    measured = json.loads((DIRECTORY / 'observations.json').read_text(encoding='utf-8'))
    assert measured['passed'] and measured['postguards_passed']
    assert measured['checker_sha256'] == digest(DIRECTORY / 'check.py')
    assert measured['packet_sha256'] == digest(DIRECTORY / 'packet.json')
    assert measured['fixture_sha256'] == record['fixture_sha256']
    assert measured['canonical_sources_modified'] is False
    assert measured['browser_integrated'] is False and measured['production_admitted'] is False
    assert {row['sanitizer'] for row in measured['runs']} == {'normal', 'address'}
    assert all(row['compile_returncode'] == row['returncode'] == 0 for row in measured['runs'])
    assert len(measured['native_syntax']) == 3
    assert all(row['returncode'] == 0 for row in measured['native_syntax'])
    assert measured['prepared_source_after_sha256'] == {
        name: row['after_sha256'] for name, row in record['source_files'].items()
    }
