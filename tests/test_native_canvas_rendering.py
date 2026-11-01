import copy
import hashlib
import json
from pathlib import Path
import runpy
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / 'native/drafts/canvas-native-rendering'
TOOL = runpy.run_path(str(PACKET / 'validate.py'))
EXPANDED = runpy.run_path(str(PACKET / 'validate_expanded.py'))


def observation():
    return dict(schema=1, passed=True, rows=[dict(name=name, passed=True,
        plainChangedChannels=0, images=[dict(alpha=alpha, sha256='a' * 64,
            repeatExact=True, metrics=[12.5, -1, 12, 13, 0]) for alpha in (True, False)])
        for name in TOOL['CONTEXTS']])


def test_rendering_validator_preserves_input_and_does_not_admit_privacy():
    value = observation()
    before = copy.deepcopy(value)
    result = TOOL['validate'](value)
    assert value == before and result['passed'] and result['measurement_complete']
    assert result['privacy_admitted'] is result['production_admitted'] is False


@pytest.mark.parametrize('value', [True, -1, 257, 1.0, None])
def test_rendering_rejects_malformed_colour_counts(value):
    measured = observation()
    measured['rows'][0]['plainChangedChannels'] = value
    with pytest.raises(ValueError, match='changed-channel'):
        TOOL['validate'](measured)


@pytest.mark.parametrize('value', [True, None, float('nan'), float('inf'), '12'])
def test_rendering_rejects_invalid_metrics(value):
    measured = observation()
    measured['rows'][0]['images'][0]['metrics'][0] = value
    with pytest.raises(ValueError, match='metric'):
        TOOL['validate'](measured)


def test_rendering_worker_failure_is_incomplete():
    measured = observation()
    measured['rows'][-1] = dict(name='worker-module', passed=False, error='Owned deadline')
    measured['passed'] = False
    result = TOOL['validate'](measured)
    assert result['passed'] is result['measurement_complete'] is False


@pytest.mark.parametrize('kind', ['colour', 'repeat'])
def test_rendering_difference_is_not_hidden_by_success_verdict(kind):
    measured = observation()
    row = measured['rows'][0]
    if kind == 'colour':
        row['plainChangedChannels'] = 1
    else:
        row['images'][0]['repeatExact'] = False
    with pytest.raises(ValueError, match='contradicts'):
        TOOL['validate'](measured)
    row['passed'] = measured['passed'] = False
    result = TOOL['validate'](measured)
    assert result['measurement_complete'] and result['passed'] is False


@pytest.mark.parametrize('kind', ['context', 'alpha', 'digest', 'metrics'])
def test_rendering_rejects_missing_or_malformed_coverage(kind):
    measured = observation()
    image = measured['rows'][0]['images'][0]
    if kind == 'context':
        measured['rows'].reverse()
    elif kind == 'alpha':
        image['alpha'] = 1
    elif kind == 'digest':
        image['sha256'] = 'x' * 64
    else:
        image['metrics'].pop()
    with pytest.raises(ValueError):
        TOOL['validate'](measured)


def test_rendering_public_patch_reconstructs_the_measured_probe(tmp_path):
    relative = Path('native/drafts/canvas-roundtrip/probe.js')
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    target.write_bytes((ROOT / relative).read_bytes())
    record = json.loads((PACKET / 'observations.json').read_bytes())
    assert hashlib.sha256(target.read_bytes()).hexdigest() == record['base_probe_sha256']
    result = subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', str(PACKET / 'probe-extension.patch')],
                            cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert hashlib.sha256(target.read_bytes()).hexdigest() == record['probe_sha256']


def test_rendering_record_binds_restart_and_keeps_unverified_work_explicit():
    record = json.loads((PACKET / 'observations.json').read_bytes())
    for field, name in (('publication_validator_sha256', 'validate.py'),
                        ('probe_extension_sha256', 'probe-extension.patch')):
        assert record[field] == hashlib.sha256((PACKET / name).read_bytes()).hexdigest()
    assert record['measurement_complete'] and record['source_core_driver_asset_postguards_passed']
    assert record['fixture_thread_closed'] and record['publication_validator_rechecked_all_phases']
    phases = record['phases']
    assert len(phases) == 14 and record['image_observations'] == 140
    first = {phase['profile_name']: phase for phase in phases if not phase['restart']}
    restarts = [phase for phase in phases if phase['restart']]
    assert len(first) == len(restarts) == record['restart_pairs_exact'] == 7
    for phase in phases:
        assert TOOL['validate'](phase['observed'])['passed'] and phase['resources_closed']
        assert phase['readback_masking_enabled'] is False
        assert all(row['images'] == phase['observed']['rows'][0]['images'] for row in phase['observed']['rows'])
    assert all(phase['observed'] == first[phase['profile_name']]['observed'] for phase in restarts)
    pairs = {tuple(image['sha256'] for image in phase['observed']['rows'][0]['images']) for phase in first.values()}
    assert len(pairs) == record['distinct_initial_image_pairs'] == 6
    assert record['attempts'][0]['measurement_complete'] is False
    for name in ('default_backing_verified', 'multicolour_contract_verified',
                 'export_contracts_verified', 'seed_bound_rendering_identity',
                 'real_device_cohorts_verified', 'canvas_policy_repaired',
                 'third_party_verdict_validated', 'manager_admission_changed',
                 'privacy_admitted', 'production_admitted'):
        assert record[name] is False


def expanded_observation():
    measured = observation()
    for row in measured['rows']:
        images = row.pop('images')
        names = (['toDataURL', 'toBlob'] if row['name'] in ('document-html', 'same-origin-frame')
                 else ['convertToBlob'])
        for image in images:
            image['exports'] = [dict(name=name, changedChannels=0, sha256=image['sha256']) for name in names]
        row['variants'] = [dict(willReadFrequently=backing, images=copy.deepcopy(images),
            multicolourChangedChannels=0, plainChangedChannels=0, passed=True) for backing in (False, True)]
        del row['plainChangedChannels']
    return measured


def test_expanded_rendering_validator_preserves_the_observation():
    measured = expanded_observation()
    before = copy.deepcopy(measured)
    result = EXPANDED['validate'](measured)
    assert result['measurement_complete'] and result['passed'] and measured == before
    assert result['privacy_admitted'] is result['production_admitted'] is False


@pytest.mark.parametrize('kind', ['backing', 'export-name', 'missing-export', 'count', 'digest', 'hash-conflict'])
def test_expanded_rendering_rejects_malformed_exports_or_backing(kind):
    measured = expanded_observation()
    variant = measured['rows'][0]['variants'][0]
    export = variant['images'][0]['exports'][0]
    if kind == 'backing':
        variant['willReadFrequently'] = 0
    elif kind == 'export-name':
        export['name'] = 'convertToBlob'
    elif kind == 'missing-export':
        variant['images'][0]['exports'].pop()
    elif kind == 'count':
        export['changedChannels'] = True
    elif kind == 'digest':
        export['sha256'] = 'q' * 64
    else:
        export['sha256'] = 'b' * 64
    with pytest.raises(ValueError):
        EXPANDED['validate'](measured)


@pytest.mark.parametrize('kind', ['export', 'multicolour'])
def test_expanded_rendering_keeps_real_contract_differences_failed(kind):
    measured = expanded_observation()
    row = measured['rows'][0]
    variant = row['variants'][0]
    if kind == 'export':
        variant['images'][0]['exports'][0].update(changedChannels=1, sha256='b' * 64)
    else:
        variant['multicolourChangedChannels'] = 1
    with pytest.raises(ValueError, match='contradicts'):
        EXPANDED['validate'](measured)
    variant['passed'] = row['passed'] = measured['passed'] = False
    result = EXPANDED['validate'](measured)
    assert result['measurement_complete'] and result['passed'] is False


def test_expanded_rendering_worker_failure_is_incomplete():
    measured = expanded_observation()
    measured['rows'][-1] = dict(name='worker-module', passed=False, error='Owned deadline')
    measured['passed'] = False
    result = EXPANDED['validate'](measured)
    assert result['measurement_complete'] is result['passed'] is False


def test_expanded_rendering_patch_and_restart_evidence(tmp_path):
    record = json.loads((PACKET / 'expanded-observations.json').read_bytes())
    relative = Path('native/drafts/canvas-roundtrip/probe.js')
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    target.write_bytes((ROOT / relative).read_bytes())
    for field, name in (('publication_validator_sha256', 'validate_expanded.py'),
                        ('text_validator_sha256', 'validate.py'),
                        ('probe_extension_sha256', 'expanded-probe-extension.patch')):
        assert record[field] == hashlib.sha256((PACKET / name).read_bytes()).hexdigest()
    result = subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply',
        str(PACKET / 'expanded-probe-extension.patch')], cwd=tmp_path,
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert hashlib.sha256(target.read_bytes()).hexdigest() == record['probe_sha256']
    assert record['measurement_complete'] and record['source_core_driver_asset_postguards_passed']
    assert record['fixture_thread_closed'] and record['publication_validator_rechecked_all_phases']
    assert record['image_observations'] == 280 and record['png_exports'] == 392
    phases = record['phases']
    assert len(phases) == 14 and all(p['resources_closed'] and p['passed'] for p in phases)
    first = {p['profile_name']: p for p in phases if not p['restart']}
    restarts = [p for p in phases if p['restart']]
    assert len(first) == len(restarts) == record['restart_pairs_exact'] == 7
    assert all(p['observed_sha256'] == first[p['profile_name']]['observed_sha256'] for p in restarts)
    for preset in record['presets']:
        observed = preset['observed']
        assert EXPANDED['validate'](observed)['passed']
        digest = hashlib.sha256(json.dumps(observed, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        assert digest == first[preset['name']]['observed_sha256']
    for field in ('readback_masking_enabled', 'hardware_gpu_backing_verified', 'float16_or_p3_verified',
                  'seed_bound_rendering_identity', 'real_device_cohorts_verified', 'canvas_policy_repaired',
                  'third_party_verdict_validated', 'manager_admission_changed', 'privacy_admitted', 'production_admitted'):
        assert record[field] is False
