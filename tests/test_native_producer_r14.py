import hashlib
import json
from pathlib import Path

import pytest

from scripts import native_build as build
from scripts.verify_native_checkpoint_units import CASE_PATTERN


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/upstream-156-producer-r14'


def read(name):
    return json.loads((DIRECTORY / name).read_bytes())


def test_producer_r14_preserves_the_complete_r13_recipe_and_resource_limits():
    manifest = read('manifest.json')
    original = build.load_candidate('upstream-156-checkpoint-r13')
    assert manifest['patches'][:144] == original['manifest']['patches']
    assert len(manifest['patches']) == 152
    assert manifest['build'] == original['manifest']['build']
    assert manifest['dependencies'] == original['manifest']['dependencies']
    extension = manifest['extension_batch']
    assert extension['base_manifest_sha256'] == original['manifest_sha256']
    assert extension['base_candidate'] == original['name']
    assert extension['added_patches'] == len(extension['packets']) == 8
    for row in manifest['patches']:
        assert hashlib.sha256((DIRECTORY / 'patches' / row['file']).read_bytes()).hexdigest() == row['sha256']
    for row in extension['packets']:
        assert hashlib.sha256((ROOT / row['packet']).read_bytes()).hexdigest() == row['packet_sha256']


def test_producer_r14_source_proof_does_not_claim_native_or_runtime_admission():
    proof = read('preparation.json')
    assert proof['passed'] and proof['forward_patches'] == proof['reverse_patches'] == 152
    assert proof['final_owned_files_matched'] == 471
    assert proof['upstream_files_restored'] == len(read('manifest.json')['source_files']) == 332
    assert proof['native_case_bodies_prepared'] == 163
    assert proof['baseline_native_bodies_preserved'] == 85 and proof['added_case_bodies'] == 78
    assert proof['manifest_sha256'] == hashlib.sha256((DIRECTORY / 'manifest.json').read_bytes()).hexdigest()
    for name in ('registered', 'canonical_sources_modified', 'cpp_type_checked', 'compiled',
                 'native_tests_executed', 'runtime_verified', 'whole_profile_checkpoint', 'production_admitted'):
        assert proof[name] is False


def test_producer_r14_plan_accounts_for_every_added_body_without_parameter_guesses():
    manifest, plan = read('manifest.json'), read('native-case-plan.json')
    expected = []
    for patch in manifest['patches'][136:]:
        source, added = None, {}
        for line in (DIRECTORY / 'patches' / patch['file']).read_text(encoding='utf-8-sig').splitlines():
            if line.startswith('diff --git a/'):
                source = line.split(' b/', 1)[1]
            elif source and line.startswith('+') and not line.startswith('+++'):
                added.setdefault(source, []).append(line[1:])
        for source, lines in added.items():
            for kind, fixture, case in CASE_PATTERN.findall('\n'.join(lines)):
                expected.append((source, fixture, case, kind, patch['file']))
    assert [(r['source'], r['fixture'], r['case'], r['kind'], r['patch']) for r in plan['cases']] == expected
    assert len(expected) == len(set(expected)) == plan['native_case_bodies_prepared'] == 163
    assert not any(plan[k] for k in ('parameter_instances_discovered', 'built', 'executed', 'production_admitted'))


def test_producer_r14_remains_unregistered_until_its_complete_native_gate_exists():
    assert 'upstream-156-producer-r14' not in build.CANDIDATES
    with pytest.raises(ValueError, match='Unknown Native build candidate'):
        build.load_candidate('upstream-156-producer-r14')


def test_cookie_cohort_binding_proof_preserves_browser_only_versioned_wire():
    proof = json.loads((ROOT / 'native/drafts/renderer-cookie-cohort/binding-observations.json').read_bytes())
    assert proof['passed'] and proof['input_postguards_passed']
    assert proof['existing_method_wire_shape_unchanged'] and proof['import_metadata_checked']
    assert proof['primary_input_count'] == 143 and len(proof['generated_artifacts']) == 13
    method = proof['added_method']
    assert method['ordinal'] == 1 and method['min_version'] == 2
    assert method['attributes']['AllowedContext']['field'] == 'kBrowser'
    assert method['parameters'][0]['spec'] == 'x:mojo_base.mojom.TimeTicks'
    assert method['response_parameters'][0]['spec'] == 'b'
    assert not any(proof[k] for k in ('native_executed', 'cpp_type_checked', 'gn_graph_verified', 'production_admitted'))


def test_sql_gc_fixture_packet_keeps_negative_assertions_and_dangling_detection():
    directory = ROOT / 'native/drafts/checkpoint-sql-gc-fixtures'
    proof = json.loads((directory / 'source-observations.json').read_bytes())
    assert proof['native_case_declarations_unchanged']
    assert proof['original_error_and_false_assertions_preserved']
    assert not proof['dangling_checks_disabled'] and not proof['production_behavior_changed']
    assert not proof['compiled'] and not proof['native_tests_executed']
    patch = (directory / 'checkpoint-sql-gc-fixtures.patch').read_text(encoding='utf-8-sig')
    assert 'CREATE UNIQUE INDEX checkpoint_guard ON cookies(value)' in patch
    assert 'DROP INDEX checkpoint_guard' in patch
    assert 'CollectAllGarbageForTesting' in patch
    assert 'local_storage_namespace_.Clear()' in patch
