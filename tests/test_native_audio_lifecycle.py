import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import verify_native_audio_lifecycle as lifecycle


def observation(mode):
    rows = []
    for rate in (44100, 48000):
        for frames in (128, 4096, 65536):
            for reenter in (False, True):
                rows.append(dict(kind='event-promise', rate=rate, frames=frames, reenter=reenter, passed=True,
                    checks=dict.fromkeys(('oneEvent', 'sameMutableBuffer', 'closed', 'format', 'sourceUnchanged', 'repeatRejected'), True)))
        for repetition in range(3):
            rows.append(dict(kind='detach-pending', rate=rate, repetition=repetition, passed=True,
                checks=dict.fromkeys(('noEventInObservationWindow', 'noFulfillmentInObservationWindow', 'frameRemoved'), True)))
            rows.append(dict(kind='detach-in-completion', rate=rate, repetition=repetition, passed=True,
                checks=dict.fromkeys(('oneEvent', 'frameRemoved', 'retainedMutation', 'fulfilledBufferAgreesIfDelivered'), True)))
        if mode == 'legacy':
            rows.append(dict(kind='budget-retry', rate=rate, passed=True,
                checks=dict.fromkeys(('allRejectBeforeRendering', 'contextStillSuspended'), True)))
    return dict(schema=1, mode=mode, passed=True, rows=rows)


@pytest.mark.parametrize('mode,cases,checks', [('baseline', 24, 114), ('legacy', 26, 118), ('math', 24, 114)])
def test_lifecycle_requires_complete_mode_specific_coverage(mode, cases, checks):
    assert lifecycle.validate_lifecycle(observation(mode), mode) == dict(
        cases=cases, checks=checks, pending_detach_window_ms=150)


@pytest.mark.parametrize('mode', lifecycle.MODES)
@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'failed', 'missing-check', 'false-check',
                                    'boolean-rate', 'boolean-schema', 'wrong-mode', 'boolean-frames',
                                    'integer-reenter', 'boolean-repetition', 'unhashable-kind', 'extra-field'])
def test_lifecycle_rejects_partial_failed_and_forged_results(mode, mutation):
    value = observation(mode)
    if mutation == 'missing':
        value['rows'].pop()
    elif mutation == 'duplicate':
        value['rows'][-1] = value['rows'][0]
    elif mutation == 'failed':
        value['rows'][0]['passed'] = False
    elif mutation == 'missing-check':
        value['rows'][0]['checks'].pop('closed')
    elif mutation == 'false-check':
        value['rows'][0]['checks']['closed'] = False
    elif mutation == 'boolean-rate':
        value['rows'][0]['rate'] = True
    elif mutation == 'boolean-schema':
        value['schema'] = True
    elif mutation == 'wrong-mode':
        value['mode'] = 'unrequested'
    elif mutation == 'boolean-frames':
        value['rows'][0]['frames'] = True
    elif mutation == 'integer-reenter':
        value['rows'][0]['reenter'] = 0
    elif mutation == 'boolean-repetition':
        next(row for row in value['rows'] if row['kind'] == 'detach-pending')['repetition'] = False
    elif mutation == 'unhashable-kind':
        value['rows'][0]['kind'] = []
    else:
        value['rows'][0]['unexpected'] = True
    with pytest.raises(ValueError):
        lifecycle.validate_lifecycle(value, mode)


@pytest.mark.parametrize('mode', ['unknown', None, True, []])
def test_lifecycle_rejects_unknown_requested_mode(mode):
    with pytest.raises(ValueError, match='Unknown lifecycle mode'):
        lifecycle.validate_lifecycle(observation('baseline'), mode)


@pytest.mark.parametrize('cleanup_fails', [False, True])
def test_collector_runs_explicit_fixture_and_preserves_cleanup_failure(cleanup_fails):
    calls = []

    class Page:
        async def goto(self, url, **kwargs):
            calls.append(url)

        async def evaluate(self, source, options):
            assert source == lifecycle.FIXTURE.read_text(encoding='utf-8')
            assert options == {'mode': 'math'}
            return observation('math')

    class Context:
        pages = [Page()]

        async def route(self, pattern, handler):
            assert pattern == '**/*'
            calls.append('route')

        async def unroute(self, pattern, handler):
            calls.append('unroute')
            if cleanup_fails:
                raise RuntimeError('owned cleanup failure')

    result = asyncio.run(lifecycle.collect(Context(), SimpleNamespace(origin='http://127.0.0.1:1234'), 'math'))
    assert result['passed'] is (not cleanup_fails)
    assert result['probes']['lifecycle']['coverage']['cases'] == 24
    assert calls == ['route', 'http://127.0.0.1:1234/audio', 'unroute']
    if cleanup_fails:
        assert result['cleanup_error_type'] == 'RuntimeError'


def test_lifecycle_rejects_non_windows_before_creating_artifacts(monkeypatch, tmp_path):
    monkeypatch.setattr(lifecycle.sys, 'platform', 'linux')
    with pytest.raises(ValueError, match='explicit Windows'):
        lifecycle.verify(tmp_path, tmp_path / 'chrome.exe', tmp_path / 'evidence',
                         candidate_name='upstream-156-audio-r8', driver_root=tmp_path)
    assert not (tmp_path / 'evidence').exists()


def test_fixture_keeps_budget_probe_legacy_only_and_names_bounded_detach_window():
    source = lifecycle.FIXTURE.read_text(encoding='utf-8')
    assert "if (mode === 'legacy')" in source and '8388609' in source
    assert 'not proof of all future scheduling or private-key erasure' in source
    assert 'sleep(150)' in source and 'clearTimeout(timer)' in source


def test_measured_r7_lifecycle_rows_revalidate_without_admitting_r8_or_legacy_audio():
    path = Path(__file__).resolve().parents[1] / 'native/drafts/audio-lifecycle-runtime/r7-observations.json'
    record = json.loads(path.read_bytes())
    assert record['passed'] and record['postguards_passed'] and record['cleanup_errors'] == []
    assert record['fixture_sha256'] == hashlib.sha256(lifecycle.FIXTURE.read_bytes()).hexdigest()
    assert set(record['modes']) == set(lifecycle.MODES)
    for mode, observed in record['modes'].items():
        assert observed['resources_closed']
        assert lifecycle.validate_lifecycle(observed['observed'], mode) == observed['coverage']
    assert sum(row['coverage']['cases'] for row in record['modes'].values()) == record['cases'] == 74
    assert sum(row['coverage']['checks'] for row in record['modes'].values()) == record['checks'] == 346
    for flag in ('public_cli_executed', 'r8_measured', 'native_seed_erasure_proven',
                 'legacy_audio_repaired', 'production_admitted'):
        assert record[flag] is False
