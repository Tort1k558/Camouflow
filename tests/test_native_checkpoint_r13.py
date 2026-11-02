import hashlib
import json
from pathlib import Path

from scripts import native_build as build
from scripts.verify_native_checkpoint_units import load_plan


ROOT = Path(__file__).resolve().parents[1]


def test_checkpoint_r13_is_the_complete_r12_plus_one_pinned_test_packet():
    original = build.load_candidate('upstream-156-checkpoint-r12')
    corrected = build.load_candidate('upstream-156-checkpoint-r13')
    assert corrected['manifest']['patches'][:-1] == original['manifest']['patches']
    assert len(corrected['manifest']['patches']) == 144
    assert corrected['manifest']['source_files'] == original['manifest']['source_files']
    assert corrected['manifest']['dependencies'] == original['manifest']['dependencies']
    assert corrected['manifest']['build'] == original['manifest']['build']
    extension = corrected['manifest']['extension_batch']
    assert extension['base_manifest_sha256'] == original['manifest_sha256']
    assert extension['base_candidate'] == original['name'] and extension['added_patches'] == 1
    proof = ROOT / extension['packets'][0]['packet']
    assert hashlib.sha256(proof.read_bytes()).hexdigest() == extension['packets'][0]['packet_sha256']
    fixture = json.loads(proof.read_bytes())
    assert fixture['patch_sha256'] == corrected['manifest']['patches'][-1]['sha256']


def test_checkpoint_r13_source_preparation_does_not_claim_native_execution():
    candidate = build.load_candidate('upstream-156-checkpoint-r13')
    proof = json.loads((candidate['directory'] / 'preparation.json').read_bytes())
    assert proof['passed'] and proof['manifest_sha256'] == candidate['manifest_sha256']
    assert proof['forward_patches'] == proof['reverse_patches'] == 144
    assert proof['final_owned_files_matched'] == 454 and proof['upstream_files_restored'] == 319
    assert proof['test_sources_changed'] == 4 and proof['derived_native_case_plan_verified']
    assert proof['native_case_bodies_preserved'] == len(load_plan(candidate)['cases']) == 85
    assert not any(proof[k] for k in ('compiled', 'native_tests_executed', 'production_admitted',
                                     'canonical_sources_modified', 'production_sources_changed'))


def test_checkpoint_r13_host_upgrade_recovers_exact_measured_r12_source(host_sources_before_checkpoint_r13):
    directory = ROOT / 'native/drafts/environment'
    before = json.loads((directory / 'checkpoint-r12-host-source-upgrade.json').read_bytes())
    upgrade = json.loads((directory / 'checkpoint-r13-host-source-upgrade.json').read_bytes())
    assert len(upgrade['sources']) == 1
    row = upgrade['sources'][0]
    assert row['source'] == 'scripts/native_build.py'
    assert row['before_sha256'] == before['sources'][0]['after_sha256']
    assert hashlib.sha256(host_sources_before_checkpoint_r13[row['source']]).hexdigest() == row['before_sha256']
    assert not upgrade['native_runtime_verified'] and not upgrade['production_admitted']
