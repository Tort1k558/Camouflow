import copy
import hashlib
import json
from pathlib import Path
import runpy

import pytest

from scripts import native_build
from scripts.verify_native_gpu import expected_texture_readback
from test_native_gpu import profile_identity_readback_observation, readback_observation

PACKET = Path(__file__).resolve().parents[1] / 'native/drafts/protected-gpu-v2'
CONTRACT = runpy.run_path(str(PACKET / 'validate.py'))


def protected_observation():
    observed = profile_identity_readback_observation()
    for context in observed.values():
        for field in ('packed', 'repeat', 'sampled'):
            context['webgpu']['textures'][0][field][256] ^= 1
    return observed


def test_matched_raw_baseline_and_exact_restart_preserve_original_inputs():
    baseline = readback_observation()
    observed = protected_observation()
    before = copy.deepcopy(observed)
    result = CONTRACT['validate'](observed, pipeline_version=2, protected=True,
                                  baseline=baseline, previous=copy.deepcopy(observed))
    assert result['contexts'] == 8 and result['textures'] == 48
    assert observed == before
    assert not result['original_observations_mutated'] and not result['legacy_validator_replaced']


@pytest.mark.parametrize('field,index,value', [
    ('packed', 0, 164), ('packed', 259, 254), ('packed', 256, 4),
    ('packed', 256, True), ('packed', 256, -1), ('packed', 256, 256),
    ('repeat', 256, 2), ('sampled', 256, 2),
])
def test_protected_texture_corruption_cannot_be_normalized_away(field, index, value):
    rows = protected_observation()['document']['webgpu']['textures']
    rows[0][field][index] = value
    with pytest.raises(ValueError):
        CONTRACT['validate_textures'](rows, protected=True)


def test_raw_protected_fixture_and_incomplete_rows_cannot_pass():
    raw = expected_texture_readback()
    assert CONTRACT['validate_textures'](raw, protected=False)['changed_colour_bytes'] == 0
    with pytest.raises(ValueError):
        CONTRACT['validate_textures'](raw, protected=True)
    with pytest.raises(ValueError):
        CONTRACT['validate_textures'](raw[:-1], protected=False)


@pytest.mark.parametrize('version', [None, True, 1, '2'])
def test_pipeline_selection_cannot_downgrade_validation(version):
    with pytest.raises(ValueError, match='pipeline version 2'):
        CONTRACT['validate'](protected_observation(), pipeline_version=version, protected=True)


def test_reusing_a_profile_cannot_pass_isolation():
    observed = protected_observation()
    with pytest.raises(ValueError):
        CONTRACT['validate_profile_isolation'](readback_observation(), observed, copy.deepcopy(observed),
                                                pipeline_version=2)


def test_observations_bind_the_measured_contract_without_admitting_r10():
    record = json.loads((PACKET / 'observations.json').read_bytes())
    candidate = native_build.load_candidate('upstream-156-image-r10')
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['candidate_manifest_sha256'] == candidate['manifest_sha256']
    assert record['validator_sha256'] == hashlib.sha256((PACKET / 'validate.py').read_bytes()).hexdigest()
    assert record['context_observations'] == 40 and record['texture_observations'] == 240
    assert record['isolated_profiles'] == record['restart_pairs'] == 2
    assert len(record['phases']) == 5 and all(row['passed'] for row in record['phases'])
    assert not record['full_browser_admitted'] and not record['production_admitted']
