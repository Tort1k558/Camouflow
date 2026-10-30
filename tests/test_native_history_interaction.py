import asyncio
import base64
import copy
import hashlib
import json
from pathlib import Path
import runpy
import struct

import pytest


COLLECTOR = Path(__file__).resolve().parents[1] / 'native/drafts/environment/first-script/history_interaction.py'


@pytest.fixture
def history_interaction():
    return runpy.run_path(str(COLLECTOR))


class HistorySession:
    def __init__(self, mutation=None):
        self.calls = []
        self.before = {'sample': {'screen': {'dpr': 3}, 'viewport': {'width': 390, 'height': 844}},
                       'rect': {'x': 16, 'y': 24, 'width': 72, 'height': 28}, 'clicks': []}
        self.after = {'sample': copy.deepcopy(self.before['sample']),
                      'clicks': [{'trusted': True, 'x': 52, 'y': 38, 'inside': True}]}
        self.size = (1170, 2532)
        self.mutation = mutation
        if mutation == 'numeric-trusted':
            self.after['clicks'][0]['trusted'] = 1
        elif mutation == 'untrusted':
            self.after['clicks'][0]['trusted'] = False
        elif mutation == 'missing-click':
            self.after['clicks'] = []
        elif mutation == 'extra-click':
            self.after['clicks'] *= 2
        elif mutation == 'changed-screen':
            self.after['sample']['screen']['dpr'] = 1
        elif mutation == 'wrong-screenshot-size':
            self.size = (390, 844)
        elif mutation == 'invalid-geometry':
            self.before['rect']['width'] = float('nan')
        elif mutation == 'boolean-geometry':
            self.before['rect']['x'] = True
        elif mutation == 'invalid-dpr':
            self.before['sample']['screen']['dpr'] = float('inf')
        elif mutation == 'boolean-dpr':
            self.before['sample']['screen']['dpr'] = True
        elif mutation == 'boolean-viewport':
            self.before['sample']['viewport']['width'] = True
        elif mutation == 'outside-viewport':
            self.before['rect']['x'] = 400

    async def send(self, method, parameters):
        self.calls.append((method, parameters))
        if method == 'Runtime.evaluate':
            value = self.before if len(self.calls) == 1 else self.after
            return {'result': {'value': copy.deepcopy(value)}}
        if method == 'Input.dispatchMouseEvent':
            return {}
        assert method == 'Page.captureScreenshot'
        png = b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR' + struct.pack('>II', *self.size)
        if self.mutation == 'invalid-png':
            png = b'not a PNG'
        return {'data': base64.b64encode(png).decode('ascii')}


def test_restored_main_interaction_uses_cdp_and_exact_trusted_input(history_interaction, tmp_path):
    session = HistorySession()
    result = asyncio.run(history_interaction['capture'](session, tmp_path))
    assert result['passed'] and result['trusted_input_passed'] and result['screen_stable_across_input']
    assert result['screenshot_size'] == result['expected_screenshot_size'] == [1170, 2532]
    assert all(result[name] is False for name in ('all_frame_input_verified', 'privacy_admitted', 'production_admitted'))
    assert [method for method, _ in session.calls] == ['Runtime.evaluate', 'Input.dispatchMouseEvent',
        'Input.dispatchMouseEvent', 'Runtime.evaluate', 'Page.captureScreenshot']
    assert (tmp_path / 'history-return-main-cdp.png').is_file()


@pytest.mark.parametrize('mutation', ['numeric-trusted', 'untrusted', 'missing-click', 'extra-click',
                                     'changed-screen', 'wrong-screenshot-size'])
def test_restored_main_interaction_rejects_false_success(history_interaction, tmp_path, mutation):
    assert asyncio.run(history_interaction['capture'](HistorySession(mutation), tmp_path))['passed'] is False


@pytest.mark.parametrize('mutation', ['invalid-geometry', 'boolean-geometry', 'invalid-dpr', 'boolean-dpr',
                                     'boolean-viewport', 'outside-viewport', 'invalid-png'])
def test_restored_main_interaction_rejects_invalid_input(history_interaction, tmp_path, mutation):
    with pytest.raises(ValueError):
        asyncio.run(history_interaction['capture'](HistorySession(mutation), tmp_path))


@pytest.mark.parametrize('response', [{'exceptionDetails': {'text': 'failure'}}, {'result': {'type': 'undefined'}}])
def test_restored_main_evaluation_requires_actual_value(history_interaction, response):
    class Session:
        async def send(self, *_):
            return response
    with pytest.raises(ValueError, match='evaluation failed'):
        asyncio.run(history_interaction['evaluate'](Session(), 'owned sample'))


def test_actual_restored_main_result_keeps_full_lifecycle_failure():
    root = Path(__file__).resolve().parents[1]
    record = json.loads((root / 'native/drafts/environment/history-interaction70-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['bfcache_restored'] and record['persisted_document_count'] == 6
    assert record['trusted_input_passed'] and record['screen_stable_across_input']
    assert record['screenshot_size'] == record['expected_screenshot_size'] == [1170, 2532]
    assert all(record[name] is False for name in ('overall_lifecycle_passed', 'all_frame_input_verified',
                                                'privacy_admitted', 'production_admitted'))
    assert record['retained_incomplete_attempt']['measurement_complete'] is False
    assert record['retained_incomplete_attempt']['timeout_ms'] == 10000
    assert all(hashlib.sha256((root / path).read_bytes()).hexdigest() == value
               for path, value in record['source_sha256'].items())
    assert hashlib.sha256(COLLECTOR.read_bytes()).hexdigest() == record['collector_source_sha256']
