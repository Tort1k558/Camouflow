import hashlib
import json
from pathlib import Path

from scripts import native_build


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / 'native/drafts/scoped-patch-index-r8'
PREVIOUS = ROOT / 'native/drafts/scoped-patch-index'


def test_scoped_index_r8_keeps_measured_implementation_and_checker_unchanged():
    record = json.loads((PACKET / 'packet.json').read_bytes())
    for name, field in (('next.patch', 'patch_sha256'), ('check.py', 'checker_sha256')):
        assert (PACKET / name).read_bytes() == (PREVIOUS / name).read_bytes()
        assert hashlib.sha256((PACKET / name).read_bytes()).hexdigest() == record[field]
    assert record['predecessor_packet_sha256'] == hashlib.sha256((PREVIOUS / 'packet.json').read_bytes()).hexdigest()


def test_scoped_index_r8_pins_archived_r8_builder_not_a_new_runtime_claim(host_sources_before_desktop_build_paths):
    record = json.loads((PACKET / 'packet.json').read_bytes())
    archive = json.loads((ROOT / 'native/drafts/environment/audio-r8-host-source-upgrade.json').read_bytes())
    builder = next(row for row in archive['sources'] if row['source'] == 'scripts/native_build.py')
    assert record['source'] == builder['source']
    assert record['before_sha256'] == builder['after_sha256']
    assert record['base_candidate_manifest_sha256'] == native_build.load_candidate('upstream-156-audio-r8')['manifest_sha256']
    for name, digest in record['test_inputs_sha256'].items():
        source = (host_sources_before_desktop_build_paths[name] if name in host_sources_before_desktop_build_paths
                  else (ROOT / name).read_bytes())
        assert hashlib.sha256(source).hexdigest() == digest, name
    assert record['selected'] is record['compiled'] is record['runtime_verified'] is record['production_admitted'] is False


def test_scoped_index_r8_preparation_proves_only_detached_patch_roundtrip():
    record = json.loads((PACKET / 'preparation.json').read_bytes())
    packet = json.loads((PACKET / 'packet.json').read_bytes())
    assert record['prepared'] and record['patch_apply_reverse_restored'] and record['predecessor_patch_identical']
    assert record['packet_sha256'] == hashlib.sha256((PACKET / 'packet.json').read_bytes()).hexdigest()
    assert record['before_sha256'] == packet['before_sha256'] and record['after_sha256'] == packet['after_sha256']
    assert record['canonical_builder_modified'] is record['native_source_modified'] is record['checker_executed'] is False
