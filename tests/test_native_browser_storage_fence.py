import hashlib
import json
from pathlib import Path
import re
import subprocess

from scripts.native_build import load_candidate


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/browser-storage-fence'


def packet():
    record = json.loads((DIRECTORY / 'source-observations.json').read_bytes())
    patch = DIRECTORY / record['patch']
    added = '\n'.join(line[1:] for line in patch.read_text(encoding='utf-8-sig').splitlines()
                      if line.startswith('+') and not line.startswith('+++'))
    return record, patch, added


def test_browser_fence_is_not_runtime_or_durability_admission():
    record, patch, _ = packet()
    candidate = load_candidate('upstream-156-image-r11')
    assert record['base_manifest_sha256'] == candidate['manifest_sha256']
    assert record['target_revision'] == candidate['manifest']['target_revision']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    assert len(record['sources']) == record['changed_files'] == 16
    assert len(candidate['manifest']['patches']) == 136
    assert record['producer_ipc_source_implemented']
    for key in ('selected', 'canonical_sources_modified', 'compiled_browser',
                'runtime_verified', 'native_cases_executed', 'privacy_admitted',
                'production_admitted', 'browser_coordinator_implemented',
                'network_producer_fence_implemented', 'profile_checkpoint_implemented',
                'full_candidate_composition_verified', 'gn_generation_verified'):
        assert record[key] is False


def test_seven_packet_replay_retains_r11_owned_inputs_and_new_files():
    record, _, _ = packet()
    assert record['composed_files'] == len(record['composed_sources']) == 50
    assert record['forward_reverse_passed'] and record['new_files_removed_on_reverse']
    assert len(record['composed_patch_chain']) == 6
    for row in record['composed_patch_chain']:
        assert hashlib.sha256((ROOT / row['path']).read_bytes()).hexdigest() == row['sha256']
    assert len(record['r11_owned_source_replay']) == 2
    assert record['r11_root_patches_replayed_for_owned_sources'] == 99
    new = {r['source'] for r in record['sources'] if r['before_sha256'] is None}
    assert record['new_files'] == len(new) == 2
    assert new == {'content/common/storage_checkpoint.mojom',
                   'third_party/blink/public/web/web_storage_checkpoint.h'}
    assert 'content/common/renderer.mojom' not in {r['source'] for r in record['sources']}


def test_browser_fence_uses_versioned_normal_endpoint_and_independent_deadline():
    record, _, added = packet()
    assert record['primary_renderer_schema_unchanged']
    assert record['normal_checkpoint_interface_version'] == 1
    assert record['finite_browser_deadline'] and record['wire_request_limit'] == 64
    assert 'mojo::Remote<mojom::StorageCheckpoint>' in added
    assert 'QueryVersion(' in added and 'base::OneShotTimer' in added
    assert 'RefCountedData<base::OnceCallback<void(bool)>>' in added
    assert 'storage_checkpoint_interface_generation_' in added
    assert 'instance_weak_factory_.GetWeakPtr()' in added
    assert 'ScopedClosureRunner' in added
    assert 'AllowedContext=sandbox.mojom.Context.kBrowser' in added
    assert 'MinVersion=1' in added
    assert record['no_javascript_surface'] and record['no_renderer_database_flush']


def test_prepared_tests_and_type_checks_are_not_executed_cases():
    record, _, added = packet()
    cases = re.findall(r'(?:TEST(?:_F)?|IN_PROC_BROWSER_TEST_F)\(\s*\w+,\s*(Checkpoint\w+)', added)
    assert cases == record['native_case_bodies_prepared']
    assert len(cases) == len(set(cases)) == 8
    assert len(record['browser_case_bodies_prepared']) == 4
    assert 'CheckpointHungRendererUsesBrowserDeadline' in cases
    assert 'CheckpointRendererExitRejectsInflightFence' in cases
    assert record['type_checked_translation_units'] == len(record['syntax_targets']) == 16
    assert all(r['returncode'] == 0 for r in record['syntax_targets'])
    assert record['gn_format_passed'] and record['active_core_unchanged']
    assert record['input_postguards_passed']
    assert not record['native_cases_executed']


def test_browser_patch_is_well_formed():
    _, patch, _ = packet()
    result = subprocess.run(['git', 'apply', '--numstat', str(patch)],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert len(result.stdout.splitlines()) == 16
