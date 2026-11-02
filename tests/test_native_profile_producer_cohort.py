import hashlib
import json
from pathlib import Path
import re
import subprocess

from scripts.native_build import load_candidate


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/profile-producer-cohort'


def packet():
    record = json.loads((DIRECTORY / 'source-observations.json').read_bytes())
    patch = DIRECTORY / record['patch']
    added = '\n'.join(line[1:] for line in patch.read_text(encoding='utf-8-sig').splitlines()
                      if line.startswith('+') and not line.startswith('+++'))
    return record, patch, added


def test_profile_cohort_is_unselected_source_not_a_checkpoint_capability():
    record, patch, _ = packet()
    candidate = load_candidate('upstream-156-checkpoint-r12')
    assert record['base_manifest_sha256'] == candidate['manifest_sha256']
    assert record['target_revision'] == candidate['manifest']['target_revision']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    assert record['cohort_source_implemented']
    assert len(candidate['manifest']['patches']) == 143
    for key in ('selected', 'registered', 'type_checked', 'gn_generation_verified',
                'compiled_browser', 'native_tests_executed', 'runtime_verified',
                'canonical_sources_modified', 'privacy_admitted', 'production_admitted',
                'profile_checkpoint_implemented', 'network_producer_fence_implemented',
                'backend_coordination_implemented', 'manager_checkpoint_implemented',
                'full_candidate_composition_verified'):
        assert record[key] is False


def test_profile_cohort_has_two_reconstructed_gn_inputs_and_three_new_files():
    record, _, _ = packet()
    assert record['changed_files'] == len(record['sources']) == 5
    assert record['new_files'] == sum(r['before_sha256'] is None for r in record['sources']) == 3
    assert record['isolated_forward_reverse_passed'] and record['r12_owned_inputs_reconstructed']
    assert record['r12_root_patches_replayed_for_owned_inputs'] == 106
    assert {r['source'] for r in record['sources'] if r['before_sha256']} == {
        'content/browser/BUILD.gn', 'content/test/BUILD.gn'}
    assert len(record['gn_files_parsed']) == 2
    assert all(r['parsed'] for r in record['gn_files_parsed'])


def test_profile_cohort_declares_weak_scope_value_partitions_and_bounded_lifecycle():
    _, patch, _ = packet()
    production = [block for block in patch.read_text(encoding='utf-8-sig').split('diff --git ')[1:]
                  if block.split(' b/', 1)[0].endswith(
                      ('/profile_producer_fence.cc', '/profile_producer_fence.h'))]
    assert len(production) == 2
    added = '\n'.join(line[1:] for block in production for line in block.splitlines()
                      if line.startswith('+') and not line.startswith('+++'))
    assert 'base::WeakPtr<content::BrowserContext> context_' in added
    assert 'std::set<content::StoragePartitionConfig> partitions_' in added
    assert 'kMaxRenderers = 512' in added and 'kMaxPartitions = 128' in added
    assert 'context_->ForEachLoadedStoragePartition(' in added
    assert 'context_->ShutdownStarted()' in added
    assert 'context_->IsOffTheRecord()' in added
    assert 'RenderProcessHostDestroyed(' in added and 'OnRenderProcessHostCreated(' in added
    assert 'topology_changed_ || renderers != renderers_' in added
    assert 'partitions != partitions_' in added
    assert 'base::BindPostTaskToCurrentDefault' in added
    assert 'Status::kCancelled' in added and 'timer_.Start(' in added
    assert 'GetDefaultStoragePartition(' not in added and 'CommitPendingMaps(' not in added


def test_profile_cohort_prepared_mock_cases_are_not_real_ipc_results():
    record, _, added = packet()
    cases = re.findall(r'TEST_F\(ProfileProducerFenceTest,\s*(\w+)', added)
    assert cases == record['native_case_bodies_prepared']
    assert len(cases) == len(set(cases)) == record['native_bodies_prepared'] == 20
    assert {'WaitsForAllCapturedRenderers', 'DoesNotContactOtherBrowserContext',
            'CancelQueuedSuccessCannotBecomeAcknowledged', 'ContextDestructionRejectsQueuedSuccess',
            'NewReadyRendererInvalidatesQueuedEmptyScope', 'UnansweredProducerUsesBrowserDeadline',
            'RendererExitRejectsLateProducerAcknowledgment',
            'NewPartitionInvalidatesPostedEmptySuccess',
            'RendererLimitRejectsBeforeAnyProducerRequest'} <= set(cases)
    assert 'public content::MockRenderProcessHost' in added
    assert not record['type_checked'] and not record['native_tests_executed']


def test_profile_cohort_patch_parses_without_modifying_active_source():
    _, patch, _ = packet()
    result = subprocess.run(['git', 'apply', '--numstat', str(patch)],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert len(result.stdout.splitlines()) == 5
