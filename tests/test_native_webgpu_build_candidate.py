import hashlib
import json
from pathlib import Path

import pytest

from scripts import native_build as build
from scripts.fetch_native_rebase_sources import source_plan

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/upstream-156-webgpu'


def test_full_webgpu_candidate_preserves_baseline_and_resource_limits():
    baseline = build.load_candidate('upstream-156')
    candidate = build.load_candidate('upstream-156-webgpu')
    manifest = candidate['manifest']
    assert candidate['name'] == 'upstream-156-webgpu'
    assert manifest['patches'][:76] == baseline['manifest']['patches']
    assert len(manifest['patches']) == 116
    assert len(manifest['source_files']) == 268
    assert len(source_plan(manifest)) == 268
    assert manifest['component_batch']['draft_packets'] == 30
    assert manifest['dependencies']['v8'] == baseline['manifest']['dependencies']['v8']
    assert manifest['dependencies']['dawn']['revision'] == '0a2c7df818e285d6db0f085135139cda04cee8bb'
    assert manifest['build'] == baseline['manifest']['build']
    assert candidate['lock']['minimum_free_gib'] == 180
    assert candidate['lock']['build_jobs'] == 4
    for key in ('compiled', 'runtime_verified', 'production_admitted'):
        assert manifest[key] is False


def test_full_candidate_proof_and_original_drafts_are_bound():
    manifest_path = DIRECTORY / 'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    proof = json.loads((DIRECTORY / 'preparation.json').read_bytes())
    assert proof['passed'] and proof['forward_patches'] == proof['reverse_patches'] == 116
    assert proof['upstream_files_restored'] == 268
    assert proof['composed_webgpu_paths_matched'] == 88
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == proof['manifest_sha256']
    generated = []
    for row in manifest['component_batch']['drafts']:
        assert hashlib.sha256((ROOT / row['source']).read_bytes()).hexdigest() == row['sha256']
        generated.extend(row['patches'])
    assert generated == [row['file'] for row in manifest['patches'][76:]]


def test_variant_reuses_only_the_exact_pinned_checkout_family(tmp_path):
    baseline = build.load_candidate('upstream-156')
    candidate = build.load_candidate('upstream-156-webgpu')
    build.candidate_workspace(tmp_path, baseline, claim=True)
    build.candidate_workspace(tmp_path, candidate)
    marker = tmp_path / 'glint-build-candidate.json'
    value = json.loads(marker.read_bytes())
    value['chromium_revision'] = '0' * 40
    marker.write_text(json.dumps(value), encoding='utf-8')
    with pytest.raises(ValueError, match='different revision'):
        build.candidate_workspace(tmp_path, candidate)


def test_variant_cannot_reuse_baseline_dependency_stage_receipts(tmp_path):
    chromium = tmp_path / 'chromium'
    (chromium / 'src').mkdir(parents=True)
    for name in ('src/DEPS', '.gclient', 'camouflow-git-revisions.json', 'camouflow-cipd-installed.json'):
        (chromium / name).write_text('pinned\n', encoding='utf-8')
    baseline = build.load_candidate('upstream-156')
    candidate = build.load_candidate('upstream-156-webgpu')
    build.record_stage(chromium, 'sync', baseline)
    before = build.stage_path(chromium, 'sync').read_bytes()
    with pytest.raises(ValueError, match='inputs changed'):
        build.require_stage(chromium, 'sync', candidate)
    assert build.stage_path(chromium, 'sync').read_bytes() == before


def test_variant_tooling_upgrade_preserves_historical_measured_sources(native_tooling_before_webgpu_candidate):
    source = native_tooling_before_webgpu_candidate['sources']['scripts/native_build.py']
    previous = json.loads((ROOT / 'native/drafts/environment/net-path-tooling-source-upgrade.json').read_bytes())
    assert hashlib.sha256(source).hexdigest() == previous['sources'][0]['after_sha256']
