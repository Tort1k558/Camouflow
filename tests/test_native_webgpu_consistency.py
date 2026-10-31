import base64
import copy
import hashlib
import struct
import zlib

import pytest

from scripts import verify_native_webgpu_consistency as gate


def pixels():
    return bytes(channel for y in range(16) for x in range(16)
                 for channel in ((x * 17) % 256, (y * 29 + 31) % 256,
                                 (x * 43 + y * 11) % 256, 255))


def png_url(data):
    def chunk(name, value):
        return struct.pack('>I', len(value)) + name + value + struct.pack('>I', zlib.crc32(name + value))
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 16, 16, 8, 6, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(b''.join(b'\0' + data[row*64:(row+1)*64] for row in range(16))))
    png += chunk(b'IEND', b'')
    return 'data:image/png;base64,' + base64.b64encode(png).decode('ascii')


def row(mode, direct=None, shader=None, exported=None):
    direct = pixels() if direct is None else direct
    shader = pixels() if shader is None else shader
    exported = pixels() if exported is None else exported
    return {'mode': mode, 'context': 'document', 'value': {
        'measured': True, 'commandValidationPassed': True, 'exportStable': True, 'format': 'rgba8unorm',
        'rgbaBase64': base64.b64encode(direct).decode('ascii'), 'shaderRGBA': list(shader),
        'png': png_url(exported)}}


def changed():
    value = bytearray(pixels())
    value[0] = 1
    return bytes(value)


def test_raw_compatibility_does_not_pass_without_observed_protection():
    result = gate.validate_rows([row('baseline'), row('ready')])
    assert result['fixture_validation_passed'] and result['readback_consistent']
    assert result['surface_noise_observed'] is result['consistency_gate_passed'] is False
    assert result['privacy_admitted'] is result['production_admitted'] is False


def test_current_runtime_style_png_only_protection_fails_the_consistency_gate():
    result = gate.validate_rows([row('baseline'), row('ready', exported=changed())])
    assert result['surface_noise_observed'] and result['readback_consistent'] is False
    assert result['consistency_gate_passed'] is False
    assert result['rows'][1]['png_vs_shader'] == {'changed_channels': 1, 'maximum_delta': 1}


def test_copy_only_protection_cannot_hide_unprotected_shader_storage_readback():
    result = gate.validate_rows([row('baseline'), row('ready', direct=changed(), exported=changed())])
    assert result['rows'][1]['png_vs_direct']['changed_channels'] == 0
    assert result['rows'][1]['png_vs_shader']['changed_channels'] == 1
    assert result['consistency_gate_passed'] is False


def test_coherent_fixture_passes_only_scoped_gate_without_privacy_admission():
    result = gate.validate_rows([row('baseline'), row('ready', changed(), changed(), changed())])
    assert result['consistency_gate_passed'] and result['surface_noise_observed']
    assert result['privacy_admitted'] is result['production_admitted'] is False
    assert result['rows'][0]['shader_rgba_sha256'] == hashlib.sha256(pixels()).hexdigest()


@pytest.mark.parametrize('bad', [None, {}, [], ['baseline', 'ready'], [row('baseline')],
    [row('baseline'), row('baseline')], [row('baseline'), {'mode': []}],
    [row('baseline'), row('ready'), row('ready')]])
def test_missing_duplicate_or_malformed_phases_are_rejected(bad):
    with pytest.raises(ValueError):
        gate.validate_rows(bad)


@pytest.mark.parametrize(('name', 'bad'), [('measured', False), ('commandValidationPassed', False),
    ('exportStable', False), ('format', 'rgba16float'), ('rgbaBase64', None),
    ('rgbaBase64', 'not base64'), ('rgbaBase64', 'A' * 2049), ('shaderRGBA', [0] * 1023),
    ('shaderRGBA', [False] * 1024), ('shaderRGBA', [256] * 1024), ('png', None),
    ('png', 'data:image/png;base64,AA=='), ('png', 'data:image/png;base64,' + 'A' * 90000)],
    ids=['not-measured', 'command-error', 'unstable-export', 'wrong-format', 'missing-direct',
         'invalid-base64', 'oversized-direct', 'short-shader', 'boolean-shader', 'invalid-shader',
         'missing-png', 'invalid-png', 'oversized-png'])
def test_malformed_api_pixel_and_png_results_are_rejected(name, bad):
    rows = [row('baseline'), row('ready')]
    rows[1]['value'][name] = bad
    with pytest.raises(ValueError):
        gate.validate_rows(rows)


def test_png_dimensions_are_checked_before_qt_decoding():
    data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR' + struct.pack('>II', 65535, 65535) + b'\0' * 16
    with pytest.raises(ValueError, match='16x16'):
        gate.decode_png('data:image/png;base64,' + base64.b64encode(data).decode('ascii'))


@pytest.mark.parametrize(('offset', 'value'), [(3, 254), (0, 3)])
def test_alpha_changes_and_color_outside_policy_bound_are_rejected(offset, value):
    bad = bytearray(pixels())
    bad[offset] = value
    with pytest.raises(ValueError):
        gate.validate_rows([row('baseline'), row('ready', bytes(bad))])


def test_incorrect_baseline_cannot_be_excused_as_protection():
    with pytest.raises(ValueError, match='Unprotected fixture'):
        gate.validate_rows([row('baseline', changed()), row('ready', changed(), changed(), changed())])


def test_validator_does_not_modify_raw_observations():
    rows = [row('baseline'), row('ready', exported=changed())]
    before = copy.deepcopy(rows)
    gate.validate_rows(rows)
    assert rows == before
