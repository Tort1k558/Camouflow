import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / 'native/drafts/scoped-patch-index'


def test_scoped_index_packet_binds_exact_public_inputs(host_sources_before_desktop_build_paths):
    packet = json.loads((PACKET / 'packet.json').read_bytes())
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    assert sha(PACKET / 'next.patch') == packet['patch_sha256']
    assert sha(PACKET / 'check.py') == packet['checker_sha256']
    assert sha(ROOT / 'native/drafts/upstream-156-webgpu-r7/manifest.json') == packet['base_candidate_manifest_sha256']
    for name, digest in packet['test_inputs_sha256'].items():
        source = (host_sources_before_desktop_build_paths[name] if name in host_sources_before_desktop_build_paths
                  else (ROOT / name).read_bytes())
        assert hashlib.sha256(source).hexdigest() == digest, name


def test_scoped_index_packet_preserves_archived_builder_base_and_scope():
    packet = json.loads((PACKET / 'packet.json').read_bytes())
    archive = json.loads((ROOT / 'native/drafts/environment/webgpu-r7-host-source-upgrade.json').read_bytes())
    before = next(row for row in archive['sources'] if row['source'] == packet['source'])
    assert packet['before_sha256'] == before['after_sha256']
    assert packet['selected'] is packet['compiled'] is packet['production_admitted'] is False
    headers = [line for line in (PACKET / 'next.patch').read_text(encoding='utf-8-sig').splitlines()
               if line.startswith('diff --git ')]
    assert headers == ['diff --git a/scripts/native_build.py b/scripts/native_build.py']


def test_scoped_index_observations_do_not_claim_native_admission():
    record = json.loads((PACKET / 'observations.json').read_bytes())
    assert record['passed'] and record['host']['input_postguards_passed']
    assert record['host']['counts'] == {'passed': 1171, 'failed': 0, 'skipped': 1}
    assert record['packet_sha256'] == hashlib.sha256((PACKET / 'packet.json').read_bytes()).hexdigest()
    assert record['public_recipe_sha256'] == hashlib.sha256((PACKET / 'recipe-observations.json').read_bytes()).hexdigest()
    assert record['selected'] is record['canonical_builder_modified'] is record['compiled'] is False
    assert record['runtime_verified'] is record['production_admitted'] is False
    recipe = json.loads((PACKET / 'recipe-observations.json').read_bytes())
    assert recipe['passed'] and recipe['patches'] == 129
    assert recipe['final_owned_files_matched'] == 400 and recipe['upstream_files_restored'] == 270
    assert recipe['real_indices_unchanged'] and recipe['unrelated_files_preserved'] == 192
