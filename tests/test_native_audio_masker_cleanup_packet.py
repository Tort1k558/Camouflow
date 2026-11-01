import hashlib
import json
from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / 'native/drafts/audio-masker-cleanup'


def test_audio_cleanup_packet_binds_inputs_without_selecting_a_browser_recipe():
    record = json.loads((PACKET / 'packet.json').read_bytes())
    from scripts import native_build

    assert record['base_manifest_sha256'] == native_build.load_candidate('upstream-156-webgpu-r7')['manifest_sha256']
    for name, digest in record['artifacts_sha256'].items():
        assert hashlib.sha256((PACKET / name).read_bytes()).hexdigest() == digest
    assert record['selected'] is record['compiled'] is record['browser_verified'] is False
    assert record['legacy_audio_repaired'] is record['production_admitted'] is False


def test_audio_cleanup_patch_is_limited_to_masker_and_its_native_tests():
    record = json.loads((PACKET / 'packet.json').read_bytes())
    paths = [line.split(' b/', 1)[1] for line in (PACKET / 'next.patch').read_text(encoding='utf-8-sig').splitlines()
             if line.startswith('diff --git ')]
    assert set(paths) == set(record['source_sha256']) and len(paths) == 3
    assert {Path(name).name for name in paths} == {
        'offline_audio_candidate.h', 'offline_audio_candidate.cc', 'offline_audio_candidate_unittest.cc'}


def test_audio_cleanup_reference_matches_real_crypto_baseline_not_a_new_algorithm():
    observed = json.loads((PACKET / 'observations.json').read_bytes())
    reference = runpy.run_path(str(PACKET / 'check.py'))['reference_outputs']()
    assert len(reference) == observed['real_crypto_cases_per_run'] * 4 == 12327 * 4
    assert hashlib.sha256(reference).hexdigest() == observed['reference_outputs_sha256']
    assert set(observed['output_sha256'].values()) == {observed['reference_outputs_sha256']}


def test_audio_cleanup_observations_keep_fault_controls_and_admission_separate():
    observed = json.loads((PACKET / 'observations.json').read_bytes())
    assert observed['packet_sha256'] == hashlib.sha256((PACKET / 'packet.json').read_bytes()).hexdigest()
    assert observed['passed'] and observed['input_postguards_passed'] and observed['reverse_restored']
    assert observed['independent_python_hmac_match'] and observed['native_gtest_syntax_passed']
    assert observed['selected'] is observed['compiled_browser'] is observed['native_gtest_executed'] is False
    assert observed['legacy_audio_repaired'] is observed['production_admitted'] is False
    assert len(observed['runs']) == 6
    for row in observed['runs']:
        result = row['observed']
        if row['mode'] == 'fault':
            assert result['injected_hmac_failures'] == 4 and result['failed_calls_not_cached']
            assert result['digest_cleanses'] == (4 if row['label'] == 'after' else 0)
        else:
            assert result['storage_cleansed'] is (row['label'] == 'after')
            assert result['caller_seed_unchanged'] and result['copy_move_stable']
