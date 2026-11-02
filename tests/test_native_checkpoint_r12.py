import hashlib
import json
from pathlib import Path
import re

from scripts import native_build as build


ROOT = Path(__file__).resolve().parents[1]


def test_checkpoint_candidate_retains_complete_r11_prefix_and_limits():
    candidate = build.load_candidate('upstream-156-checkpoint-r12')
    base = build.load_candidate('upstream-156-image-r11')
    manifest = candidate['manifest']
    assert manifest['patches'][:136] == base['manifest']['patches']
    assert len(manifest['patches']) == 143
    for field in ('dependencies', 'build', 'target_revision', 'target_version'):
        assert manifest[field] == base['manifest'][field]
    assert candidate['lock']['minimum_free_gib'] == 180
    assert candidate['lock']['build_jobs'] == 4
    assert not any(manifest[k] for k in ('compiled', 'runtime_verified', 'production_admitted'))


def test_checkpoint_manifest_binds_source_packets_and_upstream_inputs():
    candidate = build.load_candidate('upstream-156-checkpoint-r12')
    manifest = candidate['manifest']
    base = build.load_candidate('upstream-156-image-r11')
    assert manifest['extension_batch']['base_manifest_sha256'] == base['manifest_sha256']
    assert manifest['source_files'][:273] == base['manifest']['source_files']
    assert len(manifest['source_files']) == 319
    assert len({row['path'] for row in manifest['source_files']}) == 319
    packets = manifest['extension_batch']['packets']
    assert len(packets) == manifest['extension_batch']['added_patches'] == 7
    for packet in packets:
        path = ROOT / packet['packet']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == packet['packet_sha256']
        record = json.loads(path.read_bytes())
        assert len(packet['patches']) == 1
        registered = candidate['directory'] / 'patches' / packet['patches'][0]
        assert registered.read_bytes() == (path.parent / record['patch']).read_bytes()


def test_checkpoint_complete_replay_is_not_compilation_or_execution():
    candidate = build.load_candidate('upstream-156-checkpoint-r12')
    proof = json.loads((candidate['directory'] / 'preparation.json').read_bytes())
    assert proof['passed'] and proof['manifest_sha256'] == candidate['manifest_sha256']
    assert proof['forward_patches'] == proof['reverse_patches'] == 143
    assert proof['final_owned_files_matched'] == 454
    assert proof['upstream_files_restored'] == 319
    for key in ('compiled', 'native_tests_executed', 'canonical_sources_modified', 'production_admitted'):
        assert proof[key] is False


def test_checkpoint_host_measurement_binds_the_measured_commit_only():
    candidate = build.load_candidate('upstream-156-checkpoint-r12')
    record = json.loads((candidate['directory'] / 'host-observations.json').read_bytes())
    assert record['passed'] and record['input_postguards_passed'] and record['full_suite_executed']
    assert record['candidate_manifest_sha256'] == candidate['manifest_sha256']
    assert record['measured_commit'] == '369d39f6a1db91abe4210180b42a1032d58d61b4'
    assert record['counts'] == {'passed': 6037, 'failed': 0, 'skipped': 1}
    assert not any(record[k] for k in ('native_tests_executed', 'compiled_browser',
                                      'runtime_verified', 'privacy_admitted', 'production_admitted'))


def test_checkpoint_native_plan_accounts_for_every_added_test_body():
    candidate = build.load_candidate('upstream-156-checkpoint-r12')
    plan = json.loads((candidate['directory'] / 'native-case-plan.json').read_bytes())
    assert plan['candidate_manifest_sha256'] == candidate['manifest_sha256']
    expected = []
    for patch in candidate['manifest']['patches'][136:]:
        text = (candidate['directory'] / 'patches' / patch['file']).read_text(encoding='utf-8-sig')
        added = '\n'.join(line[1:] for line in text.splitlines()
                          if line.startswith('+') and not line.startswith('+++'))
        expected.extend((patch['file'], kind, fixture, case)
                        for kind, fixture, case in re.findall(
                            r'\b(TEST(?:_F|_P)?|IN_PROC_BROWSER_TEST_F)\(\s*(\w+),\s*(\w+)', added))
    assert expected == [(r['patch'], r['kind'], r['fixture'], r['case']) for r in plan['cases']]
    assert len(expected) == plan['native_case_bodies_prepared'] == 85
    assert plan['binaries'] == ['blink_unittests', 'components_unittests', 'content_browsertests',
                                 'content_unittests', 'net_unittests', 'services_unittests']
    assert not any(plan[k] for k in ('parameter_instances_discovered', 'built', 'executed',
                                    'production_admitted'))


def test_checkpoint_source_transition_does_not_claim_a_built_browser():
    candidate = build.load_candidate('upstream-156-checkpoint-r12')
    record = json.loads((candidate['directory'] / 'source-transition-observations.json').read_bytes())
    assert record['source_transition_passed'] and record['full_source_backup_verified']
    assert record['candidate_manifest_sha256'] == candidate['manifest_sha256']
    assert record['canonical_source_patch_count'] == 143
    assert record['owned_sources_matched'] == 454 and record['changed_sources'] == 50
    assert record['preserved_r11_runtime_assets'] == 269
    assert [r['action'] for r in record['stages']] == ['sync', 'hooks', 'patch']
    assert all(r['terminal'] and r['returncode'] == 0 for r in record['stages'])
    assert not any(record[k] for k in ('compiled_browser', 'native_tests_executed',
                                      'runtime_verified', 'privacy_admitted', 'production_admitted'))


def test_checkpoint_windows_build_is_not_native_or_runtime_admission():
    candidate = build.load_candidate('upstream-156-checkpoint-r12')
    record = json.loads((candidate['directory'] / 'windows-build.json').read_bytes())
    assert record['passed'] and record['compiled_browser'] and record['source_and_receipt_postguards_passed']
    assert record['candidate_manifest_sha256'] == candidate['manifest_sha256']
    assert record['chromium_revision'] == candidate['manifest']['target_revision']
    assert record['chromium_version'] == candidate['manifest']['target_version']
    assert record['build_jobs'] == 4 and record['patch_count'] == 143
    assert record['ninja_steps'] == 2508 and record['ninja_elapsed'] == '1h25m28.03s'
    assert record['official_build_stage_seconds'] == record['stages'][-1]['duration_seconds'] == 5574.557
    assert [r['action'] for r in record['stages']] == ['sync', 'hooks', 'patch', 'build']
    assert all(r['returncode'] == 0 for r in record['stages'])
    assert set(record['runtime_core_sha256_measured']) == {'chrome.exe', 'chrome.dll', 'chrome_elf.dll'}
    assert all(re.fullmatch('[0-9a-f]{64}', value) for value in record['runtime_core_sha256_measured'].values())
    assert not any(record[k] for k in ('native_tests_executed', 'runtime_verified',
                                      'privacy_admitted', 'production_admitted'))
