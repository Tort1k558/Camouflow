import asyncio
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest


DIRECTORY = Path(__file__).resolve().parents[1] / 'native/drafts/upstream-156-image-r11'


def test_published_recovery_binds_exact_runtime_and_does_not_admit_other_crashes():
    root = DIRECTORY.parents[2]
    record = json.loads((DIRECTORY / 'gpu-recovery-observations.json').read_bytes())
    native = json.loads((DIRECTORY / 'native-all-observations.json').read_bytes())
    for key in ('candidate_manifest_sha256', 'runtime_core_sha256_measured', 'receipt_sha256'):
        assert record[key] == native[key]
    assert record['collector_sha256'] == hashlib.sha256((DIRECTORY / 'measure_gpu_recovery.py').read_bytes()).hexdigest()
    for name, digest in record['source_sha256'].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['owned_resources_closed'] and record['fixture_thread_closed']
    assert not any(record[key] for key in ('privacy_admitted', 'production_admitted',
        'physical_gpu_reset_tested', 'full_recovery_admitted', 'persistent_worker_gpu_objects_verified'))
    assert record['phase_count'] == record['actual_gpu_crash_commands'] == len(record['phases']) == 3
    assert [row['name'] for row in record['phases']] == ['baseline', 'native', 'gamma-1400-contrast-300']
    contexts = textures = protected_contexts = protected_textures = 0
    for row in record['phases']:
        assert row['passed'] and row['resources_closed'] and row['effective_arguments_verified']
        assert row['crash_command_completed'] and row['browser_identity_unchanged']
        assert row['existing_documents_preserved'] == 5 and row['page_crashes'] == 0
        assert row['before_state_sha256'] == row['after_state_sha256']
        assert row['loss'] == dict(initialCopyMatched=True, deviceLostCallbacks=1, reason='unknown',
                                   oldMapRejectedWith='AbortError', oldMapState='unmapped')
        for value in (row['before_validation'], row['after_validation']):
            assert value['contract_version'] == value['pipeline_version'] == 2
            assert value['contexts'] == 8 and value['textures'] == 48
            contexts += value['contexts']
            textures += value['textures']
            if row['protected']:
                protected_contexts += value['contexts']
                protected_textures += value['textures']
    assert contexts == record['observed_context_executions'] == 48
    assert textures == record['observed_texture_executions'] == 288
    assert protected_contexts == record['protected_context_executions'] == 32
    assert protected_textures == record['protected_texture_executions'] == 192


@pytest.mark.parametrize('mode', ['success', 'lost-frame', 'loss-mismatch', 'pixel-mismatch',
                                 'session-cleanup-failure', 'retained-runtime', 'baseline-failure'])
def test_recovery_faults_never_admit_a_partial_or_unclean_run(monkeypatch, mode):
    from scripts import verify_native_canvas as canvas
    from scripts import verify_native_gpu_readback
    from scripts import verify_native_worker_startup as startup

    collector = runpy.run_path(str(DIRECTORY / 'measure_gpu_recovery.py'))
    closed = []
    requested = []

    class Session:
        async def send(self, command):
            return {'product': 'owned-test'} if command == 'Browser.getVersion' else {}

        async def detach(self):
            if mode == 'session-cleanup-failure':
                raise OSError('Injected session cleanup failure')

    class Frame:
        marker = None

        async def evaluate(self, expression, value=None):
            if expression.startswith('value =>'):
                self.marker = value
                return
            return self.marker

    class Page(Frame):
        def __init__(self):
            self.frames = (self, *(Frame() for _ in range(4)))

        def on(self, *args):
            pass

        def is_closed(self):
            return False

        async def evaluate(self, expression, value=None):
            if 'armOwnedGPURecovery' in expression:
                return dict(armed=True, initialCopyMatched=True, deviceLostCallbacks=0)
            if '__glintOwnedGPURecovery.finish' in expression:
                if mode == 'lost-frame':
                    self.frames = self.frames[:-1]
                return dict(initialCopyMatched=True, deviceLostCallbacks=2 if mode == 'loss-mismatch' else 1,
                            reason='unknown', oldMapRejectedWith='AbortError', oldMapState='unmapped')
            if '__glintOwnedGPURecovery.close' in expression:
                return
            return await super().evaluate(expression, value)

    class Browser:
        async def new_browser_cdp_session(self):
            return Session()

    class Runtime:
        has_resources = False

        def __init__(self, name):
            self.name = name

        async def start(self, **kwargs):
            self.has_resources = True
            return SimpleNamespace(pages=[Page()], browser=Browser())

        async def close(self):
            closed.append(self.name)
            self.has_resources = mode == 'retained-runtime'

    @dataclass
    class Configuration:
        rendering_preset: str = 'native'
        bootstrap_policy: str = 'surfaces'
        disabled_features_argument: str = 'owned-disabled'
        ignored_driver_argument: str = 'owned-ignored'

        def launch_arguments(self):
            return ['owned-argument']

    def baseline_configuration(**kwargs):
        return Configuration(**kwargs)

    def make(name, config):
        requested.append(name)
        return Runtime(name)

    async def arguments(context):
        return ['owned-argument']

    async def observe(*args, **kwargs):
        if mode == 'baseline-failure':
            raise ValueError('Injected baseline failure')
        return {'pixels': 'stable'}

    async def after(*args, **kwargs):
        return {'pixels': 'changed' if mode == 'pixel-mismatch' else 'stable'}

    def validate(value, **kwargs):
        assert kwargs['pipeline_version'] == 2
        if kwargs.get('previous') is not None and kwargs['previous'] != value:
            raise ValueError('Injected protected pixel mismatch')
        if kwargs['protected']:
            assert kwargs['baseline'] == {'pixels': 'stable'}
        return {'contexts': 8, 'textures': 48}

    collector['measure'].__globals__['existing_contexts'] = after
    collector['validation']['validate'] = validate
    monkeypatch.setattr(canvas, 'observe', observe)
    monkeypatch.setattr(startup, 'browser_arguments', arguments)
    monkeypatch.setattr(startup, 'StartupConfiguration', baseline_configuration)
    result = asyncio.run(collector['measure'](make, Configuration()))
    assert result['passed'] == (mode == 'success')
    assert result['fixture_thread_closed']
    assert len(closed) == len(requested)
    if mode == 'retained-runtime':
        assert len(requested) == 1 and not result['resources_closed']
    else:
        assert result['resources_closed']
    if mode == 'baseline-failure':
        assert len(requested) == 1
        assert all(not phase['passed'] for phase in result['phases'])
    if mode == 'success':
        assert result['measurement_complete'] and len(result['phases']) == 3
        assert all(phase['existing_documents_preserved'] == 5 for phase in result['phases'])


def test_existing_contexts_require_the_original_frames_and_all_worker_results(monkeypatch):
    from scripts import verify_native_canvas as canvas

    collector = runpy.run_path(str(DIRECTORY / 'measure_gpu_recovery.py'))
    calls = []
    async def read(frame, script, name, **kwargs):
        calls.append(name)
        return {name: {}} if name != 'new-workers-after-recovery' else dict(dedicated={}, shared={}, service={})
    class Element:
        async def content_frame(self):
            return object()
    class Page:
        missing = False
        def locator(self, selector):
            async def element():
                return None if self.missing else Element()
            return SimpleNamespace(element_handle=element)
    monkeypatch.setattr(canvas, 'read_owned_context', read)
    page = Page()
    observed = asyncio.run(collector['existing_contexts'](page, 'owned-read'))
    assert len(observed) == 8 and len(calls) == 6
    page.missing = True
    with pytest.raises(ValueError, match='lost an existing frame'):
        asyncio.run(collector['existing_contexts'](page, 'owned-read'))
