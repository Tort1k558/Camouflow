import hashlib
import json
from pathlib import Path

from scripts import native_build as build
from scripts.verify_native_checkpoint_units import load_plan


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/upstream-156-document-r15'


def read(name):
    return json.loads((DIRECTORY / name).read_bytes())


def test_document_r15_preserves_r14_recipe_and_limits():
    baseline = build.load_candidate('upstream-156-producer-r14')
    candidate = build.load_candidate('upstream-156-document-r15')
    manifest = candidate['manifest']
    assert manifest['patches'][:152] == baseline['manifest']['patches']
    assert len(manifest['patches']) == 154
    assert manifest['build'] == baseline['manifest']['build']
    assert manifest['dependencies'] == baseline['manifest']['dependencies']
    assert candidate['lock']['minimum_free_gib'] == 180
    assert candidate['lock']['build_jobs'] == 4
    batch = manifest['extension_batch']
    assert batch['base_candidate'] == baseline['name']
    assert batch['base_manifest_sha256'] == baseline['manifest_sha256']
    assert batch['added_patches'] == len(batch['packets']) == 2
    for row in manifest['patches']:
        assert hashlib.sha256((DIRECTORY / 'patches' / row['file']).read_bytes()).hexdigest() == row['sha256']
    for packet in batch['packets']:
        assert hashlib.sha256((ROOT / packet['packet']).read_bytes()).hexdigest() == packet['packet_sha256']


def test_document_r15_plan_preserves_every_r14_body_and_adds_twelve():
    candidate = build.load_candidate('upstream-156-document-r15')
    plan = load_plan(candidate)
    original = load_plan(build.load_candidate('upstream-156-producer-r14'))
    assert plan['cases'][:163] == original['cases']
    assert len(plan['cases']) == plan['native_case_bodies_prepared'] == 175
    added = plan['cases'][163:]
    assert sum(row['binary'] == 'content_browsertests' for row in added) == 4
    assert sum(row['binary'] == 'content_unittests' for row in added) == 8
    assert not any(plan[key] for key in ('built', 'executed', 'parameter_instances_discovered', 'production_admitted'))


def test_document_r15_proof_does_not_promote_one_cxx_check_to_full_admission():
    proof = read('preparation.json')
    assert proof['passed'] and proof['forward_patches'] == proof['reverse_patches'] == 154
    assert proof['final_owned_files_matched'] == 471
    assert proof['upstream_files_restored'] == 332
    assert proof['manifest_sha256'] == hashlib.sha256((DIRECTORY / 'manifest.json').read_bytes()).hexdigest()
    assert proof['isolated_cookie_translation_unit_compiled']
    assert not any(proof[key] for key in ('compiled', 'cpp_typechecked', 'native_executed',
        'native_tests_executed', 'runtime_verified', 'whole_profile_checkpoint', 'production_admitted'))


def test_document_cookie_scopes_keep_legacy_default_and_fail_closed():
    patch = (DIRECTORY / 'patches/0153-native-profile-document-producers.patch').read_text(encoding='utf-8-sig')
    assert 'ProducerScope producers = ProducerScope::kLocalStorage' in patch
    assert 'host->FenceDocumentCookiesForCheckpoint(deadline_, reply())' in patch
    assert 'host->FenceLocalStorageForCheckpoint(deadline_, reply())' in patch
    assert 'CombinedCookieFailureRejectsLocalSuccess' in patch
    assert 'CombinedLocalFailureRejectsCookieSuccess' in patch
    assert 'CombinedSharesOriginalDeadline' in patch
    assert 'LegacyDefaultNeverContactsCookies' in patch
    assert 'CombinedDroppedCookieReplyFailsClosed' in patch


def test_main_thread_fix_adds_only_the_missing_definition_include():
    patch = (DIRECTORY / 'patches/0154-native-cookie-main-thread-include.patch').read_text(encoding='utf-8-sig')
    added = [line for line in patch.splitlines() if line.startswith('+') and not line.startswith('+++')]
    removed = [line for line in patch.splitlines() if line.startswith('-') and not line.startswith('---')]
    assert added == ['+#include "third_party/blink/renderer/platform/scheduler/public/main_thread.h"']
    assert removed == []
    proof = json.loads((ROOT / 'native/drafts/cookie-main-thread-include/source-observations.json').read_bytes())
    assert proof['passed'] and proof['returncode'] == 0 and proof['source_postguard_passed']
    assert not proof['canonical_source_modified'] and not proof['browser_runtime_verified']


def test_document_r15_reverse_host_archive_preserves_historical_source(host_sources_before_document_r15):
    directory = ROOT / 'native/drafts/environment'
    current = json.loads((directory / 'document-r15-host-source-upgrade.json').read_bytes())
    prior = json.loads((directory / 'checkpoint-r14-host-source-upgrade.json').read_bytes())
    assert len(current['sources']) == 1
    row = current['sources'][0]
    assert row['before_sha256'] == prior['sources'][0]['after_sha256']
    assert hashlib.sha256(host_sources_before_document_r15[row['source']]).hexdigest() == row['before_sha256']
