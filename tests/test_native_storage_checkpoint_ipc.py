import hashlib
import json
from pathlib import Path
import re
import subprocess

from scripts.native_build import load_candidate


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/storage-checkpoint-ipc'


def test_checkpoint_extension_composes_the_exact_prerequisite_without_admission():
    record = json.loads((DIRECTORY / 'source-observations.json').read_bytes())
    base = json.loads((ROOT / 'native/drafts/storage-commit-barrier/source-observations.json').read_bytes())
    assert hashlib.sha256((DIRECTORY / record['patch']).read_bytes()).hexdigest() == record['patch_sha256']
    assert hashlib.sha256((ROOT / record['prerequisite_packet']).read_bytes()).hexdigest() == record['prerequisite_patch_sha256']
    assert record['prerequisite_sources'] == base['sources']
    candidate = load_candidate('upstream-156-image-r11')
    assert record['base_manifest_sha256'] == candidate['manifest_sha256']
    assert record['target_revision'] == candidate['manifest']['target_revision']
    assert record['changed_files'] == len(record['sources']) == 7
    assert record['composed_files_matched'] == record['upstream_files_restored'] == 10
    assert record['forward_reverse_passed']
    assert not any(record[key] for key in ('full_candidate_composition_verified', 'native_tests_executed',
        'selected', 'canonical_sources_modified', 'compiled_browser', 'runtime_verified',
        'profile_checkpoint_implemented', 'privacy_admitted', 'production_admitted'))
    assert len(candidate['manifest']['patches']) == 136


def test_privileged_versioned_method_does_not_replace_legacy_flush_or_renderer_ipc():
    record = json.loads((DIRECTORY / 'source-observations.json').read_bytes())
    patch = (DIRECTORY / record['patch']).read_text(encoding='utf-8-sig')
    added = '\n'.join(line[1:] for line in patch.splitlines() if line.startswith('+') and not line.startswith('+++'))
    assert re.search(r'\[MinVersion=1\]\s+FlushForCheckpoint\(\) => \(bool success\);', added)
    assert record['interface_version'] == record['new_method_min_version'] == 1
    assert len(record['legacy_method_min_versions']) == 8 and set(record['legacy_method_min_versions'].values()) == {0}
    assert record['legacy_schema_prefix_preserved'] and record['legacy_flush_body_preserved']
    assert not any(row['source'].startswith('third_party/blink/public/mojom') for row in record['sources'])
    assert 'owner->checkpoint_generation_ == generation' in added
    assert 'AdvanceCheckpointGeneration();' in added
    assert 'holder->storage_area()->FencePendingWrites(fenced)' in added
    assert 'database_->CommitPendingMaps' in added and 'base::BarrierCallback<DbStatus>' in added


def test_native_cases_and_generated_units_remain_prepared_not_runtime_results():
    record = json.loads((DIRECTORY / 'source-observations.json').read_bytes())
    patch = (DIRECTORY / record['patch']).read_text(encoding='utf-8-sig')
    added = '\n'.join(line[1:] for line in patch.splitlines() if line.startswith('+') and not line.startswith('+++'))
    cases = {suite: re.findall(r'TEST_P\('+suite+r',\s*(Checkpoint\w+)\)', added)
             for suite in ('StorageAreaImplTest', 'LocalStorageImplTest')}
    assert cases == record['native_new_cases']
    assert sum(map(len, cases.values())) == record['prepared_new_native_case_bodies'] == 12
    assert record['prepared_native_case_bodies_including_prerequisite'] == 21
    assert record['type_checked_translation_units'] == len(record['syntax_targets']) == 8
    assert sum(row['generated'] for row in record['syntax_targets']) == 2
    assert all(row['returncode'] == 0 for row in record['syntax_targets'])
    assert record['bindings_generated'] and record['generated_bindings_sha256']
    assert record['input_postguards_passed'] and record['active_core_unchanged']
    assert 'first_area->Put' in added and 'second_area->Put' in added
    assert 'control.QueryVersion' in added and 'EXPECT_EQ(version.Get(), 1u)' in added


def test_extension_patch_has_only_the_declared_seven_sources(tmp_path):
    record = json.loads((DIRECTORY / 'source-observations.json').read_bytes())
    result = subprocess.run(['git', 'apply', '--numstat', str(DIRECTORY / record['patch'])], cwd=tmp_path,
        capture_output=True, text=True, check=True, timeout=15)
    assert {line.split('\t', 2)[2] for line in result.stdout.splitlines()} == {row['source'] for row in record['sources']}
    assert not list(tmp_path.iterdir())
