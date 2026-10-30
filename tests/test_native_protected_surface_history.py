import copy
import asyncio
import hashlib
from pathlib import Path
import runpy
import struct
from types import SimpleNamespace
from unittest.mock import AsyncMock

from PyQt6.QtCore import QBuffer, QIODevice
from PyQt6.QtGui import QImage
import pytest

from test_native_audio import observation as audio_observation
from test_native_gpu import observation as gpu_observation


ROOT = Path(__file__).resolve().parents[1]
PROBE = runpy.run_path(str(ROOT / 'native/drafts/environment/first-script/protected_surface_history.py'))
RUNTIME = runpy.run_path(str(ROOT / 'native/drafts/environment/first-script/protected_history_runtime.py'))


@pytest.fixture
def observed():
    audio = audio_observation()['document']
    for phase in ('signal', 'repeat', 'silence'):
        bits = [0 if phase == 'silence' else 0x3e800000] * 4096
        digest = hashlib.sha256(struct.pack('<4096I', *bits)).hexdigest()
        audio[phase].update(hash=digest, copiedHash=digest, rightHash=digest,
                            sampleBits=bits, renderMilliseconds=2)
    graphics = gpu_observation()['document']
    for value in graphics['webgl'].values():
        pixels = value['scene']['pixels']
        raw = bytes(byte for row in range(3, -1, -1) for byte in pixels[row * 16:(row + 1) * 16])
        image = QImage(raw, 4, 4, 16, QImage.Format.Format_RGBA8888)
        buffer = QBuffer()
        assert buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        assert image.save(buffer, 'PNG')
        value['scene']['png'] = list(bytes(buffer.data()))
    return {'gpu': graphics, 'audio': audio}


def test_same_measured_surfaces_have_bounded_continuity_without_modifying_input(observed):
    before = copy.deepcopy(observed)
    result = PROBE['validate_pair'](observed, copy.deepcopy(observed))
    assert result['passed'] and observed == before
    assert result['document_contexts'] == 1 and result['webgl_apis'] == 2
    assert result['audio_phases'] == 3
    assert not result['webgpu_readback_verified'] and not result['privacy_admitted']


def test_render_duration_and_shader_debug_length_are_not_surface_identity(observed):
    after = copy.deepcopy(observed)
    for phase in ('signal', 'repeat', 'silence'):
        after['audio'][phase]['renderMilliseconds'] = 100
    for value in after['gpu']['webgl'].values():
        value['translatedShaderLength'] += 10
    assert PROBE['validate_pair'](observed, after)['passed']


@pytest.mark.parametrize('fault', ['missing', 'unavailable-audio', 'not-finite', 'not-closed', 'sample-tamper',
    'silence', 'unavailable-gpu', 'missing-webgl2', 'crop', 'export', 'metadata'])
def test_bad_or_changed_readback_cannot_pass_by_matching_itself(observed, fault):
    after = copy.deepcopy(observed)
    if fault == 'missing':
        del after['audio']
    elif fault == 'unavailable-audio':
        after['audio']['available'] = False
    elif fault == 'not-finite':
        after['audio']['signal']['finite'] = False
    elif fault == 'not-closed':
        after['audio']['signal']['closed'] = False
    elif fault == 'sample-tamper':
        after['audio']['signal']['sampleBits'][0] ^= 1
    elif fault == 'silence':
        after['audio']['silence']['silence'] = False
    elif fault == 'unavailable-gpu':
        after['gpu']['webgl']['webgl']['available'] = False
    elif fault == 'missing-webgl2':
        del after['gpu']['webgl']['webgl2']
    elif fault == 'crop':
        after['gpu']['webgl']['webgl2']['scene']['crop'][0] ^= 1
    elif fault == 'export':
        after['gpu']['webgl']['webgl']['scene']['png'][0] ^= 1
    else:
        after['gpu']['webgl']['webgl']['vendor'] = 'Changed vendor'
    with pytest.raises((ValueError, TypeError)):
        PROBE['validate_pair'](observed, after)


def test_both_real_bfcache_modes_are_required(observed):
    runs = [dict(mode=mode, bfcache_restored=True, post_surfaces_screen_verified=True,
                 history_navigation={'type': 'BackForwardCacheRestore'},
                 surfaces_before=copy.deepcopy(observed), surfaces_after=copy.deepcopy(observed))
            for mode in ('manager-desktop', 'manager-mobile-web')]
    assert PROBE['validate_runs'](runs)['passed']
    runs[0]['history_navigation']['type'] = 'Navigation'
    with pytest.raises(ValueError, match='Actual retained BFCache'):
        PROBE['validate_runs'](runs)


def test_screen_must_be_revalidated_after_surface_reads(observed):
    runs = [dict(mode=mode, bfcache_restored=True, post_surfaces_screen_verified=False,
                 history_navigation={'type': 'BackForwardCacheRestore'},
                 surfaces_before=observed, surfaces_after=observed)
            for mode in ('manager-desktop', 'manager-mobile-web')]
    with pytest.raises(ValueError, match='Actual retained BFCache'):
        PROBE['validate_runs'](runs)


@pytest.mark.parametrize('webgpu', [None, {'available': True}, {'available': False, 'reason': ''}])
def test_missing_webgpu_metadata_is_not_an_explicit_capability_observation(observed, webgpu):
    observed['gpu']['webgpu'] = webgpu
    with pytest.raises(ValueError, match='WebGPU capability'):
        PROBE['validate_pair'](observed, copy.deepcopy(observed))


def test_restored_read_uses_cdp_without_playwright_frame_operations():
    value = {'gpu': {}, 'audio': {}}
    session = SimpleNamespace(send=AsyncMock(return_value={'result': {'value': value}}))
    assert asyncio.run(RUNTIME['read_restored_surfaces'](session, 'async () => ({})')) == value
    session.send.assert_awaited_once_with('Runtime.evaluate', {
        'expression': '(async () => ({}))()', 'awaitPromise': True,
        'returnByValue': True, 'timeout': 30000})


@pytest.mark.parametrize('response', [None, {}, {'result': {'value': None}},
    {'exceptionDetails': {}, 'result': {'value': {}}}])
def test_restored_protocol_error_or_missing_value_has_no_fallback(response):
    session = SimpleNamespace(send=AsyncMock(return_value=response))
    with pytest.raises(ValueError, match='Restored GPU/Audio'):
        asyncio.run(RUNTIME['read_restored_surfaces'](session, 'async () => ({})'))
