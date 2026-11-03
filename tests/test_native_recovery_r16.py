import hashlib
import json
from pathlib import Path

from scripts import native_build as build
from scripts.verify_native_checkpoint_units import load_plan

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/upstream-156-recovery-r16'


def read(name):
    return json.loads((DIRECTORY / name).read_bytes())


def test_recovery_recipe_preserves_r15_and_resource_limits():
    baseline = build.load_candidate('upstream-156-document-r15')
    candidate = build.load_candidate('upstream-156-recovery-r16')
    manifest = candidate['manifest']
    assert manifest['patches'][:154] == baseline['manifest']['patches']
    assert len(manifest['patches']) == 161
    assert manifest['build'] == baseline['manifest']['build']
    assert manifest['dependencies'] == baseline['manifest']['dependencies']
    assert candidate['lock']['minimum_free_gib'] == 180
    assert candidate['lock']['build_jobs'] == 4
    batch = manifest['extension_batch']
    assert batch['base_manifest_sha256'] == baseline['manifest_sha256']
    assert batch['base_candidate'] == baseline['name']
    assert batch['added_patches'] == len(batch['packets']) == 7
    for row in manifest['patches']:
        patch = DIRECTORY / 'patches' / row['file']
        assert hashlib.sha256(patch.read_bytes()).hexdigest() == row['sha256']
    for packet in batch['packets']:
        path = ROOT / packet['packet']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == packet['packet_sha256']
        record = json.loads(path.read_bytes())
        assert record['passed'] and packet['patches'] == [record['patch']]
        patch = DIRECTORY / 'patches' / record['patch']
        assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['normalized_patch_sha256']


def test_recovery_plan_preserves_all_previous_cases_and_adds_chrome_binary():
    plan = load_plan(build.load_candidate('upstream-156-recovery-r16'))
    baseline = load_plan(build.load_candidate('upstream-156-document-r15'))
    assert plan['cases'][:175] == baseline['cases']
    assert len(plan['cases']) == plan['native_case_bodies_prepared'] == 225
    assert len(plan['binaries']) == 7 and 'browser_tests' in plan['binaries']
    chrome = [row for row in plan['cases'] if row['binary'] == 'browser_tests']
    assert len(chrome) == 8
    assert all(row['source'] == 'chrome/browser/net/profile_network_context_service_browsertest.cc'
               for row in chrome)
    assert not any(plan[key] for key in ('built', 'executed', 'parameter_instances_discovered',
                                        'production_admitted'))


def test_cxx_evidence_does_not_claim_linking_native_execution_or_runtime():
    proof = read('preparation.json')
    assert proof['passed'] and proof['forward_patches'] == proof['reverse_patches'] == 161
    assert proof['final_owned_files_matched'] == 481 and proof['upstream_files_restored'] == 338
    assert proof['manifest_sha256'] == hashlib.sha256((DIRECTORY / 'manifest.json').read_bytes()).hexdigest()
    cxx_path = DIRECTORY / 'cxx-observations.json'
    assert proof['cxx_observations_sha256'] == hashlib.sha256(cxx_path.read_bytes()).hexdigest()
    cxx = read('cxx-observations.json')
    assert cxx['terminal'] and cxx['passed'] and cxx['cpp_typechecked']
    assert cxx['input_postguards_passed'] and not cxx['style_checks_disabled']
    assert len(cxx['targets']) == proof['cxx_translation_units'] == 13
    assert all(row['returncode'] == 0 for row in cxx['targets'])
    assert cxx['negative_style_control']['returncode'] == 1
    assert cxx['negative_style_control']['expected_style_failure_confirmed']
    assert not any(cxx[key] for key in ('new_graph_generated', 'browser_compiled',
        'source_modified', 'native_executed', 'runtime_verified', 'production_admitted'))
    assert not any(proof[key] for key in ('compiled', 'native_executed',
                                        'runtime_verified', 'production_admitted'))


def test_reverse_archive_preserves_pre_r16_host_bytes(host_sources_before_recovery_r16):
    directory = ROOT / 'native/drafts/environment'
    record = json.loads((directory / 'recovery-r16-host-source-upgrade.json').read_bytes())
    previous = json.loads((directory / 'document-r15-host-source-upgrade.json').read_bytes())
    assert len(record['sources']) == 2
    for row in record['sources']:
        assert hashlib.sha256(host_sources_before_recovery_r16[row['source']]).hexdigest() == row['before_sha256']
    native = next(row for row in record['sources'] if row['source'] == 'scripts/native_build.py')
    assert native['before_sha256'] == previous['sources'][0]['after_sha256']
