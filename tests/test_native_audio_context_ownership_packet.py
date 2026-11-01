import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / 'native/drafts/audio-context-ownership'


def test_audio_context_packet_binds_r7_and_disjoint_cleanup_companion():
    from scripts import native_build

    record = json.loads((PACKET / 'packet.json').read_bytes())
    companion = ROOT / 'native/drafts/audio-masker-cleanup/packet.json'
    assert record['base_manifest_sha256'] == native_build.load_candidate('upstream-156-webgpu-r7')['manifest_sha256']
    assert record['patch_sha256'] == hashlib.sha256((PACKET / 'next.patch').read_bytes()).hexdigest()
    assert record['companion_packet_sha256'] == hashlib.sha256(companion.read_bytes()).hexdigest()
    assert not set(record['source_sha256']).intersection(json.loads(companion.read_bytes())['source_sha256'])
    assert record['selected'] is record['compiled_browser'] is record['browser_verified'] is False
    assert record['native_tests_executed'] is record['legacy_audio_repaired'] is record['production_admitted'] is False


def test_audio_context_patch_is_limited_to_context_and_native_tests():
    record = json.loads((PACKET / 'packet.json').read_bytes())
    patch = (PACKET / 'next.patch').read_text(encoding='utf-8-sig')
    paths = [line.split(' b/', 1)[1] for line in patch.splitlines() if line.startswith('diff --git ')]
    assert set(paths) == set(record['source_sha256']) and len(paths) == 3
    assert {Path(name).name for name in paths} == {
        'offline_audio_context.h', 'offline_audio_context.cc', 'offline_audio_context_test.cc'}
    assert record['native_tests_added'] == 4 and record['callback_variants'] == 3


def test_audio_context_packet_has_no_bom_or_corrupted_text():
    for name in ('packet.json', 'next.patch', 'README.md'):
        data = (PACKET / name).read_bytes()
        assert not data.startswith(b'\xef\xbb\xbf')
        assert '\ufffd' not in data.decode('utf-8')


def test_audio_context_combined_syntax_evidence_does_not_claim_runtime():
    record = json.loads((PACKET / 'observations.json').read_bytes())
    assert record['packet_sha256'] == hashlib.sha256((PACKET / 'packet.json').read_bytes()).hexdigest()
    assert record['passed'] and record['input_postguards_passed'] and record['reverse_restored']
    assert record['combined_files'] == 6 and len(record['targets']) == 4
    assert {Path(row['source']).name for row in record['targets']} == {
        'offline_audio_context.cc', 'offline_audio_context_test.cc',
        'offline_audio_candidate.cc', 'offline_audio_candidate_unittest.cc'}
    assert all(row['returncode'] == 0 for row in record['targets'])
    assert record['native_sources_modified'] is record['compiled_browser'] is False
    assert record['native_tests_executed'] is record['production_admitted'] is False
