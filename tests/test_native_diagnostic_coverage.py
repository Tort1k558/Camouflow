import asyncio
import copy

import pytest

from app.core.native.configuration import NativeConfiguration
from app.core.native.diagnostics import compare_observed, inspect_native_profile


def observed():
    values = dict(width=1366, height=768, dpr=1, language='en-US', timezone='UTC')
    return dict(document=values, worker=copy.deepcopy(values))


@pytest.mark.parametrize('value', [None, [], 'invalid', 1, True])
def test_non_object_observation_is_reported(value):
    assert compare_observed(NativeConfiguration(), value) == ['Native observation is not an object']


@pytest.mark.parametrize('value', [None, [], 'invalid', 1, True])
def test_non_object_document_is_reported(value):
    assert compare_observed(NativeConfiguration(), {'document': value}) == ['Document values could not be observed']


@pytest.mark.parametrize('value', [None, [], 'invalid', 1, True])
def test_non_object_worker_is_reported(value):
    current = observed()
    current['worker'] = value
    assert 'Worker values could not be observed' in compare_observed(NativeConfiguration(), current)


@pytest.mark.parametrize('missing', ['document', 'worker'])
def test_canvas_missing_from_one_context_is_not_a_pass(missing):
    current = observed()
    for scope in current.values():
        scope['canvas'] = dict(available=False, error='2D unavailable')
    del current[missing]['canvas']
    assert 'Canvas observations could not be compared' in compare_observed(NativeConfiguration(), current)


@pytest.mark.parametrize('available', [None, 0, 1, 'true', ''])
def test_identical_non_boolean_canvas_availability_is_rejected(available):
    current = observed()
    for scope in current.values():
        scope['canvas'] = dict(available=available)
    assert 'Canvas observations could not be compared' in compare_observed(NativeConfiguration(), current)


@pytest.mark.parametrize('missing', ['document', 'worker'])
@pytest.mark.parametrize('kind', ['webgl', 'webgl2'])
def test_webgl_missing_from_one_context_is_not_a_pass(missing, kind):
    current = observed()
    for scope in current.values():
        scope['graphics'] = {kind: dict(available=False, error='Native context unavailable')}
    del current[missing]['graphics'][kind]
    assert f'{kind} observations could not be compared' in compare_observed(NativeConfiguration(), current)


@pytest.mark.parametrize('value', [None, [], {'document': []}])
def test_profile_inspection_keeps_malformed_evidence_without_throwing(value):
    class Page:
        async def evaluate(self, expression):
            return value
    result = asyncio.run(inspect_native_profile(Page(), NativeConfiguration(), '156.0.8078.36'))
    assert result['observed'] == value
    assert result['mismatches']
    assert all(isinstance(issue, str) for issue in result['mismatches'])
    assert result['native_patch_capabilities'] == []


def test_profile_inspection_requires_every_emitted_surface_in_each_context():
    class Page:
        async def evaluate(self, expression):
            return observed()
    result = asyncio.run(inspect_native_profile(Page(), NativeConfiguration(), '156.0.8078.36'))
    for scope in ('Document', 'Worker'):
        for surface in ('canvas', 'graphics', 'webgpu'):
            assert f'{scope} {surface} observation is missing' in result['mismatches']
    assert 'Document identity is missing userAgent' in result['mismatches']


def test_direct_comparison_keeps_legacy_partial_observations_compatible():
    assert compare_observed(NativeConfiguration(), observed()) == []


def test_stalled_inspection_has_a_deadline_and_cancels_the_evaluation(monkeypatch):
    from app.core.native import diagnostics
    original_timeout = asyncio.timeout
    budgets, cancelled = [], []
    def short_deadline(delay):
        budgets.append(delay)
        return original_timeout(0.01)
    monkeypatch.setattr(diagnostics.asyncio, 'timeout', short_deadline)
    class Page:
        async def evaluate(self, expression):
            try:
                await asyncio.Future()
            finally:
                cancelled.append(True)
    with pytest.raises(TimeoutError, match='Native profile diagnostics timed out after 30 seconds'):
        asyncio.run(inspect_native_profile(Page(), NativeConfiguration(), '156.0.8078.36'))
    assert budgets == [30] and cancelled == [True]


def test_inspection_preserves_the_original_evaluation_timeout():
    failure = TimeoutError('underlying evaluation timeout')
    class Page:
        async def evaluate(self, expression):
            raise failure
    with pytest.raises(TimeoutError) as caught:
        asyncio.run(inspect_native_profile(Page(), NativeConfiguration(), '156.0.8078.36'))
    assert caught.value is failure


def test_caller_cancellation_is_not_converted_into_a_successful_diagnostic():
    async def check():
        entered = asyncio.Event()
        cancelled = []
        class Page:
            async def evaluate(self, expression):
                entered.set()
                try:
                    await asyncio.Future()
                finally:
                    cancelled.append(True)
        task = asyncio.create_task(inspect_native_profile(Page(), NativeConfiguration(), '156.0.8078.36'))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cancelled == [True]
    asyncio.run(check())


@pytest.mark.parametrize('scope', ['document', 'worker'])
@pytest.mark.parametrize('error', [None, 0, False, ['error'], {'message': 'error'}])
def test_malformed_client_hint_error_is_reported_not_concatenated(scope, error):
    current = observed()
    current[scope]['userAgentDataError'] = error
    issues = compare_observed(NativeConfiguration(), current)
    assert f'{scope.capitalize()} high-entropy client hints error observation is malformed' in issues
    assert all(isinstance(issue, str) for issue in issues)
