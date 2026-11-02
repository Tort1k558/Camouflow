import hashlib
import json
from pathlib import Path

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
