import hashlib
import json
from pathlib import Path

import pytest

from scripts import native_build
from scripts.fetch_native_rebase_sources import source_plan


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / 'native/drafts/upstream-157-r8-port'


def read(name):
    return json.loads((PACKET / name).read_bytes())


def test_157_r8_prefix_keeps_complete_inventory_and_explicit_unregistered_boundary():
    prefix, full = read('manifest.json'), read('full-unported-manifest.json')
    assert len(prefix['patches']) == prefix['selected_patch_count'] == 75
    assert len(full['patches']) == full['selected_patch_count'] == 131
    assert prefix['patches'] == full['patches'][:75]
    assert prefix['source_files'] == full['source_files'] and len(full['source_files']) == 270
    assert prefix['source_application_complete'] is True
    assert full['source_application_complete'] is False
    for value in (prefix, full):
        assert value['complete_patch_count'] == 131 and value['verified_prefix_patches'] == 75
        assert value['next_port_required_patch'] == 76 and value['complete_forward_port'] is False
        assert value['compiled'] is value['runtime_verified'] is value['production_admitted'] is False
    assert 'upstream-157-r8-port' not in native_build.CANDIDATES
    with pytest.raises(ValueError):
        native_build.load_candidate('upstream-157-r8-port')


def test_157_r8_packet_reuses_prefix_and_all_unadapted_r8_payloads():
    full = read('full-unported-manifest.json')
    previous = json.loads((ROOT / 'native/drafts/upstream-157-prefix/full-inputs-manifest.json').read_bytes())
    base = native_build.load_candidate('upstream-156-audio-r8')
    assert full['patches'][:65] == previous['patches']
    assert full['base_manifest_sha256'] == base['manifest_sha256']
    for index, row in enumerate(full['patches']):
        path = ROOT / 'native/drafts' / row['file']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
        if index >= 65 and index != 66:
            original = base['manifest']['patches'][index]
            assert row == {**original, 'file': 'upstream-156-audio-r8/patches/' + original['file']}


def test_157_r8_math_port_changes_only_the_two_required_file_sections():
    original = ROOT / 'native/drafts/upstream-156-audio-r8/patches/0067-native-audio-math-context-candidate.patch'
    adapted = PACKET / 'patches' / original.name

    def sections(path):
        return {value.splitlines()[0].split(' b/', 1)[1]: value
                for value in path.read_text(encoding='utf-8-sig').split('diff --git ')[1:]}

    before, after = sections(original), sections(adapted)
    assert set(before) == set(after) and len(after) == 16
    assert {name for name in before if before[name] != after[name]} == {
        'third_party/blink/renderer/modules/webaudio/offline_audio_context.cc',
        'third_party/blink/renderer/modules/webaudio/offline_audio_context_test.cc'}
    text = adapted.read_text(encoding='utf-8-sig')
    budget_case = 'GlintCopyBudgetRejectsBeforeAllocationOrRenderThread'
    prefix_patch = ROOT / 'native/drafts' / read('manifest.json')['patches'][32]['file']
    assert budget_case in prefix_patch.read_text(encoding='utf-8-sig')
    assert not any(line.startswith('-') and budget_case in line for line in text.splitlines())
    assert 'queued finite/indefinite' in text
    assert 'glint_audio_policy_captured_' in text and 'GetGlintAudioMathPipeline()' in text


def test_157_r8_sparse_inputs_are_revision_bound_and_match_the_audited_target():
    manifest = read('full-unported-manifest.json')
    rows = source_plan(manifest)
    audit = read('upstream-audit.json')
    assert audit['candidate'] == 'upstream-156-audio-r8' and audit['status'] == 'behind-stable'
    assert manifest['target_version'] == audit['highest_observed_stable']['version']
    assert manifest['target_revision'] == audit['highest_observed_stable']['chromium_revision']
    assert len(rows) == 270 and len({row['path'] for row in rows}) == 270
    assert sum(row['bytes'] for row in rows) == 15317261
    assert manifest['dependencies']['v8']['revision'] == 'a4889e05285021952e2ca9648c805a4c989345ae'
    assert manifest['dependencies']['dawn']['revision'] == '3c24c91e70eaf701ae92ab8cc414669cc4c38892'


def test_157_r8_source_evidence_does_not_claim_a_full_forward_port_or_native_execution():
    record = read('source-observations.json')
    assert record['source_replay_passed'] and record['prefix_patches'] == 75 and record['inputs_unchanged']
    assert record['prefix_manifest_sha256'] == hashlib.sha256((PACKET / 'manifest.json').read_bytes()).hexdigest()
    assert record['full_unported_manifest_sha256'] == hashlib.sha256((PACKET / 'full-unported-manifest.json').read_bytes()).hexdigest()
    assert record['source_invariants'] == {
        'gpu_commands': {'preserved': 321, 'appended': 577}, 'grit_structure_preserved': True}
    assert record['source_discovery']['cached_inputs'] == 185
    assert record['source_discovery']['network_requests'] == 85
    assert record['math_packet']['unmodified_file_sections_preserved'] == 14
    assert record['math_packet']['exact_sixteen_postimages_preserved'] is True
    assert record['math_packet']['upstream_test_bodies_preserved'] is True
    assert len(record['math_packet']['source_only_tests_present']) == 12
    assert record['full_chain_attempt']['passed'] is False
    assert record['full_chain_attempt']['applied_patches'] == 75
    assert record['full_chain_attempt']['first_failed_patch'] == 76
    for name in ('full_chain_ported', 'compiled', 'native_tests_executed', 'runtime_verified',
                 'canonical_checkout_modified', 'selected_candidate_changed', 'production_admitted'):
        assert record[name] is False
