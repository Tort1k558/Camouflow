import hashlib
import json
from pathlib import Path
import re
import subprocess

from scripts.native_build import load_candidate


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/cookie-checkpoint-ipc'


def packet():
    record = json.loads((DIRECTORY / 'source-observations.json').read_bytes())
    patch = DIRECTORY / record['patch']
    text = patch.read_text(encoding='utf-8-sig')
    added = '\n'.join(line[1:] for line in text.splitlines()
                      if line.startswith('+') and not line.startswith('+++'))
    return record, patch, added


def test_cookie_ipc_packet_preserves_the_selected_r11_candidate():
    record, patch, _ = packet()
    candidate = load_candidate('upstream-156-image-r11')
    assert record['base_manifest_sha256'] == candidate['manifest_sha256']
    assert record['target_revision'] == candidate['manifest']['target_revision']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    assert record['changed_files'] == len(record['sources']) == 15
    names = {row['source'] for row in record['sources']}
    assert len(names) == 15
    assert not names & {row['path'] for row in candidate['manifest']['source_files']}
    assert len(candidate['manifest']['patches']) == 136
    assert not any(record[key] for key in ('selected', 'canonical_sources_modified',
        'compiled_browser', 'runtime_verified', 'profile_checkpoint_implemented',
        'privacy_admitted', 'production_admitted', 'native_cases_executed',
        'full_candidate_composition_verified'))


def test_cookie_ipc_composition_binds_shared_sqlite_header_and_all_prerequisites():
    record, _, _ = packet()
    assert record['four_packet_composed_files'] == 27
    assert record['forward_reverse_passed']
    assert len(record['upstream_composed_sources']) == 27
    for row in record['prerequisite_patches']:
        path = ROOT / row['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
    assert len(record['prerequisite_patches']) == 3
    backing = json.loads((ROOT / 'native/drafts/cookie-checkpoint/source-observations.json').read_bytes())
    name = 'net/extras/sqlite/sqlite_persistent_cookie_store.h'
    base = next(row for row in backing['sources'] if row['source'] == name)
    extension = next(row for row in record['sources'] if row['source'] == name)
    upstream = next(row for row in record['upstream_composed_sources'] if row['source'] == name)
    assert extension['before_sha256'] == base['after_sha256']
    assert upstream['before_sha256'] == base['before_sha256']
    assert upstream['after_sha256'] == extension['after_sha256']


def test_cookie_ipc_is_versioned_browser_only_without_legacy_flush_substitution():
    record, _, added = packet()
    assert record['legacy_schema_prefix_preserved'] and record['legacy_flush_bodies_preserved']
    assert record['interface_version'] == record['new_method_min_version'] == 1
    assert record['browser_only_method']
    versions = record['legacy_method_min_versions']
    assert len(versions) == 17 and set(versions.values()) == {0}
    assert versions['FlushCookieStore'] == 0
    assert '[MinVersion=1, AllowedContext=sandbox.mojom.Context.kBrowser]' in added
    assert 'FlushCookieStoreForCheckpoint() => (bool success);' in added
    assert 'store_->Flush(std::move(callback));' not in added
    assert 'cookie_store_->FlushStore(std::move(callback));' not in added
    assert 'CookieMonster::PersistentCookieStore::FlushForCheckpoint' in added
    assert 'CookieStore::FlushStoreForCheckpoint' in added
    assert 'base::BindPostTaskToCurrentDefault(std::move(callback)).Run(false);' in added


def test_cookie_ipc_guards_received_write_queue_and_each_owner_boundary():
    _, _, added = packet()
    assert 'DoCookieCallback(base::BindOnce(' in added
    assert 'base::ScopedClosureRunner abandoned' in added
    assert 'abandoned.RunAndReset();' in added and 'abandoned.Release().Reset();' in added
    assert 'base::SplitOnceCallback' in added
    assert 'base::WeakPtr<CookieMonster>' in added and 'base::WeakPtr<CookieManager>' in added
    assert 'mojo::WrapCallbackWithDefaultInvokeIfNotRun' in added
    assert 'std::memory_order_acquire' in added and 'std::memory_order_release' in added
    assert 'checkpoint_closed_' in added
    assert 'TestCookieManager::FlushCookieStoreForCheckpoint' in added


def test_cookie_ipc_native_cases_are_prepared_not_executed():
    record, _, added = packet()
    cases = re.findall(r'TEST_F\((CookieMonsterTest|SessionCleanupCookieStoreTest|CookieManagerTest),\s*(Checkpoint\w+)\)', added)
    assert [{'fixture': fixture, 'name': name} for fixture, name in cases] == record['native_cases_prepared']
    assert len(cases) == len(set(cases)) == 15
    assert sum(fixture == 'CookieMonsterTest' for fixture, _ in cases) == 8
    assert sum(fixture == 'SessionCleanupCookieStoreTest' for fixture, _ in cases) == 2
    assert sum(fixture == 'CookieManagerTest' for fixture, _ in cases) == 5
    names = {name for _, name in cases}
    assert {'CheckpointDrainsPreviouslyReceivedHostWrite',
            'CheckpointUnsupportedStoreDoesNotUseLegacyFlush',
            'CheckpointPersistentOwnerLossRejectsLateSuccess',
            'CheckpointWrapperLossRejectsLateSuccess'} <= names
    assert 'store->TakeCallbackAt(0).Run(' in added
    assert 'store->saw_add_at_checkpoint' in added
    assert not record['native_cases_executed']


def test_cookie_ipc_real_bindings_and_fourteen_type_checks_do_not_admit_runtime():
    record, _, _ = packet()
    assert record['bindings_generated']
    assert len(record['bindings_sha256']) >= 6
    assert all(len(value) == 64 for value in record['bindings_sha256'].values())
    assert record['type_checked_translation_units'] == len(record['syntax_targets']) == 14
    assert sum(row['generated'] for row in record['syntax_targets']) == 2
    assert all(row['returncode'] == 0 for row in record['syntax_targets'])
    assert record['input_postguards_passed'] and record['active_core_unchanged']
    assert not record['profile_checkpoint_implemented'] and not record['runtime_verified']
    assert len(record['remaining']) == 5


def test_cookie_ipc_patch_parses_as_fifteen_sources_without_writing_files(tmp_path):
    record, patch, _ = packet()
    result = subprocess.run(['git', 'apply', '--numstat', str(patch)], cwd=tmp_path,
                            capture_output=True, text=True, check=True, timeout=15)
    assert {line.split('\t', 2)[2] for line in result.stdout.splitlines()} == {
        row['source'] for row in record['sources']}
    assert not list(tmp_path.iterdir())
