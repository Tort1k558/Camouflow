import base64
import copy
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys

from PyQt6.QtCore import QBuffer, QIODevice
from PyQt6.QtGui import QColorSpace, QImage
import pytest


def test_export_runtime_help_has_no_profile_or_browser_side_effects(tmp_path):
    root = Path(__file__).resolve().parents[1]
    runner = root / 'native/drafts/environment/first-script/canvas_export_runtime.py'
    result = subprocess.run([sys.executable, str(runner), '--help'], cwd=tmp_path,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0 and '--cohort-directory' in result.stdout
    assert list(tmp_path.iterdir()) == []


@pytest.fixture
def export_probe():
    root = Path(__file__).resolve().parents[1]
    return runpy.run_path(str(root / 'native/drafts/environment/first-script/canvas_export.py'))


@pytest.fixture
def export_rows(export_probe):
    before = bytes([71, 91, 111, 255]) * 256
    after = bytes([0, 0, 0, 255]) * 256
    pngs = {}
    for name, profile in [('srgb', QColorSpace.NamedColorSpace.SRgb), ('display-p3', QColorSpace.NamedColorSpace.DisplayP3)]:
        image = QImage(before, 16, 16, 64, QImage.Format.Format_RGBA8888).copy()
        image.setColorSpace(QColorSpace(profile))
        buffer = QBuffer()
        assert buffer.open(QIODevice.OpenModeFlag.WriteOnly) and image.save(buffer, 'PNG')
        pngs[name] = base64.b64encode(bytes(buffer.data())).decode()
        buffer.close()
    rows = []
    for kind, space, storage in sorted(export_probe['CASES']):
        carriers = ['dataURL', 'asyncSnapshot'] if kind == 'html' else ['asyncSnapshot']
        rows.append({'kind': kind, 'colorSpace': space, 'colorType': storage,
                     'attributes': {'colorSpace': space, 'colorType': storage},
                     'readColorSpace': space, 'readPixelFormat': 'rgba-unorm8',
                     'before': base64.b64encode(before).decode(), 'after': base64.b64encode(after).decode(),
                     'exports': {carrier: pngs[space] for carrier in carriers}})
    return rows


def test_export_validation_preserves_input_and_uses_an_independent_decoder(export_probe, export_rows):
    original = copy.deepcopy(export_rows)
    result = export_probe['validate_exports'](export_rows)
    assert result['passed'] and len(result['rows']) == 8 and export_rows == original
    assert sum(len(row['exports']) for row in result['rows']) == 12
    assert result['privacy_admitted'] is result['production_admitted'] is False


@pytest.mark.parametrize('kind', ['missing', 'duplicate', 'unknown', 'malformed'])
def test_export_matrix_cannot_skip_cases(export_probe, export_rows, kind):
    if kind == 'missing':
        export_rows.pop()
    elif kind == 'duplicate':
        export_rows[0] = copy.deepcopy(export_rows[1])
    elif kind == 'unknown':
        export_rows[0]['kind'] = 'worker'
    else:
        export_rows[0]['kind'] = []
    with pytest.raises(ValueError):
        export_probe['validate_exports'](export_rows)


@pytest.mark.parametrize('kind', ['no-mutation', 'wrong-pixels', 'wrong-profile', 'api-error'])
def test_pixel_profile_snapshot_and_api_failures_are_not_passes(export_probe, export_rows, kind):
    row = next(row for row in export_rows if row['colorSpace'] == 'display-p3')
    if kind == 'no-mutation':
        row['after'] = row['before']
    elif kind == 'wrong-pixels':
        row['before'] = row['after']
    elif kind == 'wrong-profile':
        source = next(item for item in export_rows if item['kind'] == row['kind'] and item['colorSpace'] == 'srgb')
        row['exports'] = copy.deepcopy(source['exports'])
    else:
        row['error'] = {'name': 'NotReadableError', 'message': 'owned rejection'}
    assert not export_probe['validate_exports'](export_rows)['passed']


@pytest.mark.parametrize('kind', ['missing-carrier', 'wrong-storage', 'short-pixels', 'oversized-png'])
def test_malformed_export_payloads_reject(export_probe, export_rows, kind):
    row = export_rows[0]
    if kind == 'missing-carrier':
        row['exports'].pop('asyncSnapshot')
    elif kind == 'wrong-storage':
        row['attributes']['colorType'] = 'unknown'
    elif kind == 'short-pixels':
        row['before'] = base64.b64encode(b'short').decode()
    else:
        row['exports']['asyncSnapshot'] = 'A' * (2 * 1024 * 1024)
    with pytest.raises(ValueError):
        export_probe['validate_exports'](export_rows)


def test_actual_export_baseline_is_unprotected_and_binds_the_public_probe():
    root = Path(__file__).resolve().parents[1]
    record = json.loads((root / 'native/drafts/environment/canvas-export-baseline70-observations.json').read_bytes())
    assert record['passed'] and record['core_unchanged'] and record['measurement_complete']
    assert record['protected_policy_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
    assert len(record['rows']) == 8 and sum(len(row['exports']) for row in record['rows']) == 12
    assert all(row['passed'] and row['mutation_changed_source'] for row in record['rows'])
    for row in record['rows']:
        for value in row['exports'].values():
            assert value['different_bytes'] == 0 and value['color_space_matches_request']
    normalized = (root / record['public_probe']).read_text(encoding='utf-8-sig').encode()
    assert hashlib.sha256(normalized).hexdigest() == record['public_probe_normalized_utf8_lf_sha256']


def test_actual_protected_72_exports_match_pre_mutation_pixels_and_color_metadata(export_probe):
    root = Path(__file__).resolve().parents[1]
    record = json.loads((root / 'native/drafts/environment/canvas-export72-observations.json').read_bytes())
    build = json.loads((root / 'native/drafts/upstream-156/build72-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['runtime_core_sha256_measured'] == build['runtime_core_sha256_measured']
    assert record['receipt_sha256'] == build['build_receipt_sha256']
    assert record['candidate_manifest_sha256'] == build['candidate_manifest_sha256']
    assert record['privacy_admitted'] is record['production_admitted'] is False
    assert [row['profile'] for row in record['runs']] == ['baseline', 'protected']
    for row in record['runs']:
        assert row['resources_released']
        assert export_probe['validate_exports'](row['observed']) == row['validation']
        assert row['validation']['passed'] and len(row['validation']['rows']) == 8
        assert sum(len(value['exports']) for value in row['validation']['rows']) == 12
    assert len(record['effect']) == 8 and all(row['changed_from_baseline'] for row in record['effect'])
    for name in ('public_runner', 'public_probe'):
        normalized = (root / record[name]).read_text(encoding='utf-8-sig').encode()
        assert hashlib.sha256(normalized).hexdigest() == record[name + '_normalized_utf8_lf_sha256']
