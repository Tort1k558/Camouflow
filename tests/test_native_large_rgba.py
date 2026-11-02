import asyncio
import copy
import hashlib
import json
from pathlib import Path
import runpy

import pytest

from app.core.native import process_monitor


COLLECTOR = Path(__file__).resolve().parents[1] / 'native/drafts/upstream-156-image-r11/measure_large_rgba.py'


def test_published_timeline_keeps_navigation_gaps_and_original_failure():
    directory = COLLECTOR.parent
    record = json.loads((directory / 'large-image-resource-timeline.json').read_bytes())
    native = json.loads((directory / 'native-all-observations.json').read_bytes())
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    assert record['candidate_manifest_sha256'] == native['candidate_manifest_sha256']
    assert record['runtime_core_sha256_measured'] == native['runtime_core_sha256_measured']
    assert record['receipt_sha256'] == native['receipt_sha256']
    assert record['original_failure_preserved']
    assert record['original_resource_record_sha256'] == sha(directory / 'large-image-resources.json')
    assert record['collector_sha256'] == sha(COLLECTOR)
    assert record['validator_sha256'] == sha(directory / 'validate_large_rgba.py')
    assert record['probe_sha256'] == sha(directory / 'large-rgba-probe.js')
    assert not any(record[key] for key in ('passed', 'full_resource_gate_passed', 'privacy_admitted', 'production_admitted'))
    assert len(record['runs']) == 2
    validate = runpy.run_path(str(directory / 'validate_large_rgba.py'))['validate']
    for row in record['runs']:
        assert row['graphics_passed'] and row['graphics_measurement_complete']
        assert validate(row['observations'])['passed']
        assert row['owned_resources_closed'] and row['postguards_passed']
        assert not row['passed'] and not row['resource_measurement_complete'] and not row['full_resource_gate_passed']
        events = row['phase_events']
        assert [event['phase'] for event in events] == ['navigation', 'measurement', 'after']
        assert 0 == events[0]['offset_ns'] < events[1]['offset_ns'] < events[2]['offset_ns']
        assert len(row['sampling_errors']) == 1
        error = row['sampling_errors'][0]
        assert error['phase'] == 'navigation'
        assert 0 <= error['started_offset_ns'] <= error['finished_offset_ns'] < events[1]['offset_ns']
        assert row['maximum_sampled_private_commit_bytes'] == max(sample['private_commit_sum_bytes'] for sample in row['samples'])
        assert row['maximum_sampled_summed_working_set_bytes'] == max(sample['working_set_sum_bytes'] for sample in row['samples'])
        assert all(0 <= sample['started_offset_ns'] <= sample['finished_offset_ns'] for sample in row['samples'])
    assert record['runs'][1]['measured_contract_sha256'] == record['collector_sha256']


def observation():
    digest = 'a' * 64
    return dict(schema=1, width=4096, height=4096, byteLength=67108864,
                opaqueAlphaPixels=16777216, api='webgl2', alpha=False, fixtureChangedChannels=1,
                directSha256=digest, passed=True, afterTransfer=dict(pixel=[0, 0, 0, 255], error=0, lost=False),
                copies=[dict(name=name, willReadFrequently=frequent, passed=True, sha256=digest)
                        for name in ('drawImage', 'png', 'transferToImageBitmap') for frequent in (False, True)])


@pytest.mark.parametrize('mode', ['success', 'initial-gap', 'measurement-gap', 'invalid-observation',
                                 'binding-failure', 'monitor-close-failure', 'runtime-close-failure'])
def test_large_rgba_collector_preserves_gaps_and_closes_owned_resources(monkeypatch, mode):
    collector = runpy.run_path(str(COLLECTOR))
    closed = []
    calls = []
    expected = observation()

    class Page:
        async def goto(self, *args, **kwargs):
            pass

        async def evaluate(self, script):
            assert script == collector['PROBE'].read_text(encoding='utf-8')
            await asyncio.sleep(0.3)
            return {} if mode == 'invalid-observation' else copy.deepcopy(expected)

    class Context:
        async def new_page(self):
            return Page()

    class Runtime:
        has_resources = False

        async def start(self, **kwargs):
            self.has_resources = True
            return Context()

        async def close(self):
            closed.append('runtime')
            if mode == 'runtime-close-failure':
                raise OSError('Injected retained runtime')
            self.has_resources = False

    class Monitor:
        def sample(self):
            calls.append(len(calls) + 1)
            if ((mode == 'initial-gap' and len(calls) == 1)
                    or (mode == 'measurement-gap' and len(calls) == 2)):
                raise ValueError('Injected topology transition')
            return dict(private_commit_sum_bytes=123, working_set_sum_bytes=456)

        async def close(self):
            closed.append('monitor')
            if mode == 'monitor-close-failure':
                raise OSError('Injected listener cleanup failure')

    async def bind(context):
        if mode == 'binding-failure':
            raise OSError('Injected binding failure')
        return Monitor()

    monkeypatch.setattr(process_monitor.BrowserProcessMonitor, 'bind', bind)
    run = collector['measure'](lambda *args: Runtime(), object())
    if mode == 'runtime-close-failure':
        with pytest.raises(ValueError, match='resources remain live'):
            asyncio.run(run)
        assert closed == ['monitor', 'runtime']
        return
    result = asyncio.run(run)
    assert 'runtime' in closed and result['resources_closed']
    assert result['passed'] == (mode == 'success')
    for row in result['samples'] + result['sampling_errors']:
        assert 0 < row['started_ns'] <= row['finished_ns'] <= result['sampling_finished_ns']
        assert row['phase'] in ('before', 'navigation', 'measurement', 'after')
    if mode in ('initial-gap', 'measurement-gap'):
        assert len(result['sampling_errors']) == 1 and not result['resource_measurement_complete']
        error = result['sampling_errors'][0]
        assert error['phase'] == ('before' if mode == 'initial-gap' else 'measurement')
        assert error['type'] == 'ValueError' and error['error'] == 'Injected topology transition'
        assert 'private_commit_sum_bytes' not in error
    if mode == 'measurement-gap':
        assert result['measurement_complete'] and result['observations'] == expected
        assert len(result['samples']) >= 3
    if mode == 'initial-gap':
        assert not result['measurement_complete'] and 'observations' not in result
        assert calls == [1, 2]
    if mode == 'invalid-observation':
        assert result['observations'] == {} and result['error_type'] == 'ValueError'
    if mode == 'monitor-close-failure':
        assert closed == ['monitor', 'runtime'] and result['cleanup_errors']


def test_large_rgba_factory_failure_does_not_start_a_fixture(monkeypatch):
    from scripts import verify_native_runtime

    collector = runpy.run_path(str(COLLECTOR))
    def make(*args):
        raise ValueError('Invalid runtime configuration')
    def server(*args):
        pytest.fail('Fixture must not start before the runtime is constructed')
    monkeypatch.setattr(verify_native_runtime, 'FixtureServer', server)
    with pytest.raises(ValueError, match='Invalid runtime configuration'):
        asyncio.run(collector['measure'](make, object()))
