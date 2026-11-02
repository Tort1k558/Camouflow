import hashlib
import json
from pathlib import Path
import re
import subprocess

from scripts.native_build import load_candidate


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/cookie-producer-endpoint'


def packet():
    record = json.loads((DIRECTORY / 'source-observations.json').read_bytes())
    patch = DIRECTORY / record['patch']
    text = patch.read_text(encoding='utf-8-sig')
    added = '\n'.join(line[1:] for line in text.splitlines()
                      if line.startswith('+') and not line.startswith('+++'))
    return record, patch, added


def test_cookie_endpoint_is_source_preparation_not_binding_or_runtime_admission():
    record, patch, _ = packet()
    candidate = load_candidate('upstream-156-checkpoint-r12')
    assert record['base_manifest_sha256'] == candidate['manifest_sha256']
    assert record['target_revision'] == candidate['manifest']['target_revision']
    assert record['patch_sha256'] == hashlib.sha256(patch.read_bytes()).hexdigest()
    for key in ('selected', 'registered', 'type_checked', 'compiled', 'native_executed',
                'renderer_cohort_integrated', 'worker_integrated', 'whole_profile_checkpoint',
                'canonical_sources_modified', 'production_admitted', 'runtime_verified',
                'full_candidate_composition_verified', 'generated_bindings_cpp_type_checked',
                'all_implementers_verified', 'http_producers_fenced'):
        assert record[key] is False
    assert record['mojo_grammar_parsed']
    assert record['generated_bindings_verified']
    assert record['mojo_endpoint_source_prepared']
    assert record['document_drain_source_prepared']


def test_cookie_endpoint_composition_and_overlapping_inputs_are_pinned():
    record, _, _ = packet()
    assert record['isolated_four_packet_composition_passed']
    assert record['composed_final_files'] == 19
    assert record['composed_original_files_restored'] == 16
    assert record['composed_new_files_removed_on_reverse'] == 3
    directories = ('profile-producer-cohort', 'local-storage-checkpoint-owner',
                   'restricted-cookie-producer-drain', 'cookie-producer-endpoint')
    assert len(record['composed_packets']) == len(directories)
    for row, directory in zip(record['composed_packets'], directories):
        artifact = ROOT / 'native/drafts' / directory / row['patch']
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == row['sha256']
    predecessor = json.loads((ROOT / 'native/drafts/restricted-cookie-producer-drain/'
                              'source-observations.json').read_bytes())
    previous = {row['source']: row['after_sha256'] for row in predecessor['sources']}
    overlapping = [row for row in record['sources'] if row['source'] in previous]
    assert len(overlapping) == 2
    assert all(row['before_sha256'] == previous[row['source']] for row in overlapping)


def test_cookie_endpoint_declares_version_identity_and_independent_timeout_state():
    _, _, added = packet()
    assert '[MinVersion=1]' in added
    assert 'DrainCookieWritesForCheckpoint() => (bool success)' in added
    assert 'wrapper_->remote().QueryVersion(std::move(callback))' in added
    assert 'backend_.QueryVersion(' in added
    assert 'version < 1 || generation != checkpoint_generation_' in added
    assert 'checkpoint_wire_requests_ >= 64' in added
    assert 'deadline > now + base::Seconds(30)' in added
    assert 'epoch == checkpoint_epoch_' in added
    assert 'checkpoint_history_lost_' in added
    assert 'WrapWeakPersistent(this)' in added
    assert 'std::make_shared<CheckpointReply>' in added
    assert 'RequestRestrictedCookieManagerIfNeeded();' not in added
    assert 'GetInterface(' not in added
    assert 'document_->IsActive()' in added


def test_cookie_endpoint_fixture_declarations_and_file_scope_are_explicit():
    record, patch, added = packet()
    declared = re.findall(r'TEST_[FP]\((\w+),\s*(\w+)', added)
    cases = [(row['suite'], row['case']) for row in record['fixture_case_bodies']]
    assert sorted(declared) == sorted(cases)
    assert len(cases) == len(set(cases)) == record['fixture_bodies_prepared'] == 8
    result = subprocess.run(['git', 'apply', '--numstat', str(patch)], cwd=ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    paths = {line.split('\t', 2)[2] for line in result.stdout.splitlines()}
    assert paths == {row['source'] for row in record['sources']}
    assert len(paths) == 10


def test_cookie_endpoint_generated_bindings_preserve_existing_wire_methods():
    record, _, _ = packet()
    observed = json.loads((DIRECTORY / record['binding_observations']).read_bytes())
    assert observed['passed'] and observed['input_postguards_passed']
    assert observed['patch_sha256'] == record['patch_sha256']
    assert observed['import_metadata_checked']
    assert observed['existing_six_method_wire_shapes_unchanged']
    assert observed['transitive_import_modules'] == 16
    assert len(observed['primary_input_hashes']) == 32
    assert len(observed['generated_artifacts']) == 18
    assert [row['name'] for row in observed['commands']] == ['parse', 'cpp', 'blink', 'shared']
    assert all(row['returncode'] == 0 for row in observed['commands'])
    method = observed['added_method']
    assert method['name'] == 'DrainCookieWritesForCheckpoint'
    assert method['ordinal'] == 6 and method['min_version'] == 1
    assert method['parameters'] == []
    assert [p['spec'] for p in method['response_parameters']] == ['b']
    for key in ('cpp_type_checked', 'native_executed', 'gn_graph_verified',
                'canonical_sources_modified'):
        assert observed[key] is False
