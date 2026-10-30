import base64
import copy
import hashlib
import json
from pathlib import Path
import runpy
import struct

import pytest


ROOT = Path(__file__).resolve().parents[1]
HELPERS = runpy.run_path(str(ROOT / 'native/drafts/environment/first-script/canvas_hdr.py'))


@pytest.fixture
def observations():
    record = json.loads((ROOT / 'native/drafts/environment/canvas-hdr72-observations.json').read_bytes())
    return tuple(copy.deepcopy(row['observed']) for row in record['runs'])


def compare(*values):
    return HELPERS['compare_hdr'](*values)


def replace_pixels(row, data):
    value = base64.b64encode(data).decode()
    row['full'] = row['repeat'] = row['afterReput'] = value
    row['crop'] = base64.b64encode(b''.join(data[(y*16+3)*8:(y*16+12)*8] for y in range(4, 11))).decode()


def test_measured_finite_hdr_alpha_crop_and_repeat_controls(observations):
    before = copy.deepcopy(observations)
    result = compare(*observations)
    assert result['passed'] and result['baseline_signal_coverage_verified'] and observations == before
    assert len(result['checks']) == 4
    assert all(row['changed_channels'] > 0 and not row['unexpected_changed_channels'] for row in result['checks'])
    assert result['privacy_admitted'] is result['production_admitted'] is False


@pytest.mark.parametrize('fault', ['alpha', 'sign', 'multiple-mantissa-bits', 'nonopaque-color', 'excessive-delta'])
def test_invalid_changes_cannot_pass_as_bounded_privacy_transform(observations, fault):
    baseline, protected = observations
    before = list(struct.unpack('<1024H', base64.b64decode(baseline[0]['full'])))
    after = list(struct.unpack('<1024H', base64.b64decode(protected[0]['full'])))
    if fault == 'alpha':
        after[515] = before[515] ^ 1
    elif fault == 'sign':
        after[512] = before[512] ^ 0x8000
    elif fault == 'multiple-mantissa-bits':
        after[512] = before[512] ^ 3
    elif fault == 'nonopaque-color':
        after[256] = before[256] ^ 1
    else:
        index = next(i for i in range(512, 1024) if i%4 != 3 and 14 <= ((before[i]&0x7c00)>>10) <= 16)
        after[index] = before[index] ^ 0x200
    replace_pixels(protected[0], struct.pack('<1024H', *after))
    result = compare(baseline, protected)
    assert not result['passed']
    assert result['checks'][1]['unexpected_changed_channels']


@pytest.mark.parametrize('fault', ['crop', 'repeat', 'reput', 'source'])
def test_readback_coherence_is_required(observations, fault):
    baseline, protected = observations
    row = protected[0]
    if fault == 'source':
        row['sourceBufferUnchanged'] = False
    else:
        field = {'crop': 'crop', 'repeat': 'repeat', 'reput': 'afterReput'}[fault]
        data = bytearray(base64.b64decode(row[field])); data[0] ^= 1
        row[field] = base64.b64encode(data).decode()
    result = compare(baseline, protected)
    assert not result['passed'] and result['protected_errors']


def test_zero_or_unorm_only_fixture_cannot_claim_hdr_coverage(observations):
    baseline, protected = observations
    for rows in (baseline, protected):
        for row in rows:
            replace_pixels(row, bytes(2048))
    result = compare(baseline, protected)
    assert not result['passed'] and not result['baseline_signal_coverage_verified']


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'wrong-format'])
def test_incomplete_or_wrong_contexts_are_rejected(observations, fault):
    baseline, protected = observations
    if fault == 'missing':
        protected.pop()
    elif fault == 'duplicate':
        protected[0] = copy.deepcopy(protected[1])
    else:
        protected[0]['pixelFormat'] = 'rgba-unorm8'
    with pytest.raises(ValueError):
        compare(baseline, protected)


def test_public_finite_hdr_probe_binds_preserved_72_without_broad_admission():
    record = json.loads((ROOT / 'native/drafts/environment/canvas-hdr72-observations.json').read_bytes())
    build = json.loads((ROOT / 'native/drafts/upstream-156/build72-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['runtime_core_sha256_measured'] == build['runtime_core_sha256_measured']
    assert record['receipt_sha256'] == build['build_receipt_sha256']
    assert record['candidate_manifest_sha256'] == build['candidate_manifest_sha256']
    assert record['current_checkout_manifest_used_for_runtime'] is False
    assert compare(*(row['observed'] for row in record['runs'])) == record['comparison']
    assert all(row['resources_released'] for row in record['runs'])
    assert record['privacy_admitted'] is record['production_admitted'] is False
    for name, expected in record['public_sources'].items():
        assert hashlib.sha256((ROOT / name).read_text(encoding='utf-8-sig').encode()).hexdigest() == expected


def test_unsuitable_isolated_pixel_oracle_is_retained_not_labelled_a_native_regression():
    record = json.loads((ROOT / 'native/drafts/environment/canvas-hdr72-initial-oracle-observations.json').read_bytes())
    assert record['passed'] is False and record['measurement_complete']
    assert record['native_browser_source_modified'] is record['native_policies_modified'] is False
    assert record['probe_fixture_changed'] is True
    result = compare(*(row['observed'] for row in record['runs']))
    assert not result['passed'] and not result['baseline_errors'] and not result['protected_errors']
    assert all(row['changed_channels'] == 0 and not row['unexpected_changed_channels'] for row in result['checks'])
    counts = []
    for row in record['runs'][0]['observed']:
        bits = tuple(value[0] for value in struct.iter_unpack('<H', base64.b64decode(row['full'], validate=True)))
        count = 0
        for y in range(16):
            for x in range(16):
                offset = (y*16+x)*4
                if bits[offset+3] == 0x3c00:
                    neighbours = ([offset+4] if x < 15 else []) + ([offset+64] if y < 15 else [])
                    count += sum(bits[index+3] == 0x3c00 for index in neighbours)
        counts.append({'kind': row['kind'], 'colorSpace': row['colorSpace'], 'adjacent_opaque_pairs': count})
    assert counts == record['opaque_neighbour_counts'] and all(row['adjacent_opaque_pairs'] == 0 for row in counts)
