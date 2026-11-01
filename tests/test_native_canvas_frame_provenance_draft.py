from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import runpy

import pytest


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / 'native/drafts/canvas-frame-provenance'
VALIDATE = runpy.run_path(str(PACKET / 'validate.py'))['validate']


def load_record(name):
    return json.loads((PACKET / name).read_bytes())


def test_frame_extension_binds_parent_and_exact_changed_overlay_files():
    record = load_record('source-observations.json')
    parent_path = ROOT / record['parent_packet']
    parent = json.loads((parent_path.parent / 'source-observations.json').read_bytes())
    assert record['parent_patch_sha256'] == hashlib.sha256(parent_path.read_bytes()).hexdigest()
    assert record['base_manifest_sha256'] == parent['base_manifest_sha256']
    patch_path = PACKET / 'canvas-frame-provenance.patch'
    assert record['patch_sha256'] == hashlib.sha256(patch_path.read_bytes()).hexdigest()
    patch = patch_path.read_text(encoding='utf-8-sig')
    changed = {name for name, row in record['source_files'].items() if row['before'] != row['after']}
    assert len(changed) == record['changed_files'] == 6
    assert set(re.findall(r'^diff --git a/(\S+) b/\S+$', patch, re.M)) == changed
    assert record['overlay_source_files'] == len(record['source_files']) == 8
    for name, binding in record['canonical_source_bindings'].items():
        if binding['kind'] == 'bound-parent-packet':
            assert binding['parent_after_sha256'] == parent['source_files'][name]['after']
            assert record['source_files'][name]['before'] == binding['parent_after_sha256']
            assert binding['sha256'] == parent['source_files'][name]['before']
        else:
            assert binding['kind'] == 'untouched-pinned-upstream-blob'
            assert re.fullmatch('[0-9a-f]{40}', binding['git_blob_oid'])
            assert binding['sha256'] == record['source_files'][name]['before']


def test_frame_type_checks_are_not_executed_native_cases_or_runtime_repair():
    record = load_record('source-observations.json')
    patch = (PACKET / 'canvas-frame-provenance.patch').read_text(encoding='utf-8-sig')
    assert record['composed_forward_reverse_passed']
    assert record['type_checked_translation_units'] == len(record['syntax_targets']) == 6
    assert all(row['returncode'] == 0 for row in record['syntax_targets'])
    cases = re.findall(r'TEST\(GlintCanvasFrameSourceTest,\s*(\w+)\)', patch)
    assert cases == record['native_new_cases'] and len(cases) == record['prepared_native_tests'] == 4
    assert record['composed_prepared_native_tests'] == 11
    for name in ('source_seeds_transported', 'compositor_pixels_modified', 'selected',
                 'active_checkout_modified', 'compiled_browser', 'native_tests_executed',
                 'runtime_verified', 'original_r9_failure_repaired', 'privacy_admitted', 'production_admitted'):
        assert record[name] is False


def test_frame_source_commitment_is_immutable_domain_bound_and_reuses_blink_crypto():
    patch = (PACKET / 'canvas-frame-provenance.patch').read_text(encoding='utf-8-sig')
    assert 'const GlintCanvasFrameSource glint_source_;' in patch
    assert 'GlintCanvasFrameSource glint_source = {}' in patch
    assert 'blink::Digestor digestor(blink::kHashAlgorithmSha256)' in patch
    assert 'Glint.CanvasFrame.WebGL.v1' in patch and 'Glint.CanvasFrame.WebGPU.v1' in patch
    assert 'MatchesCanvasFrameCommitment(source, *seed.value())' in patch
    assert 'CanvasFrameImageSourcePartitionSeed(owner, frame->GlintImageSource())' in patch
    assert 'CaptureCanvasFrameImageSource(' in patch
    assert patch.count('glint_frame->Bitmap()') == 3
    assert 'return base::unexpected(SurfaceSeedError::kInvalidPolicy);' in patch


def test_r9_placeholder_reproduction_keeps_all_twenty_measurements_and_failure():
    record = load_record('r9-observations.json')
    assert record['probe_sha256'] == hashlib.sha256((PACKET / 'probe.js').read_bytes()).hexdigest()
    assert record['published_validator_sha256'] == hashlib.sha256((PACKET / 'validate.py').read_bytes()).hexdigest()
    result = VALIDATE(record['observations'])
    assert result['measurement_complete'] and result['passed'] is False
    assert result['protected_source_apis'] == 2 and result['copy_observations'] == 20
    copies = [copy for row in record['observations']['rows'] for copy in row['copies']]
    assert sum(copy['changedChannels'] != 0 for copy in copies) == record['mismatching_copies'] == 16
    assert all((copy['changedChannels'] == 0) == (copy['name'] == 'workerPNG') for copy in copies)
    assert record['source_core_driver_asset_postguards_passed']
    assert record['runtime_resources_closed'] and record['fixture_thread_closed']
    assert record['measurement_complete'] and record['passed'] is False
    for field in ('source_provenance_patch_applied', 'source_provenance_repair_verified',
                  'external_sites_tested', 'third_party_antibot_verified', 'privacy_admitted', 'production_admitted'):
        assert record[field] is False


def exact_synthetic_observation():
    observed = deepcopy(load_record('r9-observations.json')['observations'])
    for row in observed['rows']:
        row['passed'] = True
        for copy in row['copies']:
            copy['changedChannels'] = 0
            copy['sha256'] = row['directSha256']
            copy['knownFillChangedChannels'] = row['knownFillChangedChannels']
    observed['passed'] = True
    return observed


def test_frame_validator_has_no_single_channel_tolerance():
    observed = exact_synthetic_observation()
    assert VALIDATE(observed)['passed']
    observed['rows'][0]['copies'][0].update(changedChannels=1, sha256='0'*64)
    observed['rows'][0]['passed'] = observed['passed'] = False
    assert VALIDATE(observed)['measurement_complete']
    assert VALIDATE(observed)['passed'] is False


@pytest.mark.parametrize('mutation', [
    'boolean-count', 'missing-route', 'bad-row', 'bad-copy', 'bad-digest', 'bad-copy-digest',
])
def test_frame_validator_rejects_malformed_or_incomplete_success(mutation):
    observed = exact_synthetic_observation()
    if mutation == 'boolean-count':
        observed['rows'][0]['copies'][0]['changedChannels'] = False
    elif mutation == 'missing-route':
        observed['rows'][0]['copies'].pop()
    elif mutation == 'bad-row':
        observed['rows'][0] = None
    elif mutation == 'bad-copy':
        observed['rows'][0]['copies'][0] = None
    elif mutation == 'bad-digest':
        observed['rows'][0]['directSha256'] = 123
    else:
        observed['rows'][0]['copies'][0]['sha256'] = 123
    with pytest.raises(ValueError):
        VALIDATE(observed)


def test_frame_validator_does_not_promote_timeout_to_a_measured_pass():
    observed = exact_synthetic_observation()
    observed['rows'][0] = dict(api='webgl', error='Owned worker result timed out', passed=False)
    observed['passed'] = False
    result = VALIDATE(observed)
    assert result['measurement_complete'] is result['passed'] is False
    assert result['protected_source_apis'] == 1 and result['copy_observations'] == 10


def test_frame_validator_rejects_contradictory_known_colour_counts():
    observed = exact_synthetic_observation()
    observed['rows'][0]['copies'][0]['knownFillChangedChannels'] = 0
    with pytest.raises(ValueError, match='common known-colour reference'):
        VALIDATE(observed)
