"""Owned worker GPU-object continuity and explicit service restart checks."""
import asyncio
import math
import controlled_service_workers as service
from urllib.parse import urlsplit

import retained_gpu_objects as gpu
import retained_worker_lifecycle as lifecycle


def worker_read(*, backend=gpu):
    if backend is not gpu:
        return backend.READ
    text = gpu.READ
    replacements = {
        "Object.hasOwn(window, key)": "Object.hasOwn(globalThis, key)",
        "Object.defineProperty(window, key": "Object.defineProperty(globalThis, key",
        "const canvas = document.createElement('canvas');\n      canvas.width = canvas.height = 16;":
            "const canvas = new OffscreenCanvas(16, 16);",
        "const state = window[key];": "const state = globalThis[key];",
        "const png = item.canvas.toDataURL('image/png');":
            "const blob = await item.canvas.convertToBlob({type: 'image/png'});\n"
            "    if (blob.type !== 'image/png') throw new Error(item.api + ' worker PNG type differs');\n"
            "    const bytes = new Uint8Array(await blob.arrayBuffer());\n"
            "    if (bytes.length < 24 || [137,80,78,71,13,10,26,10].some((value,index) => bytes[index] !== value)) throw new Error(item.api + ' worker PNG header malformed');\n"
            "    const header = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);\n"
            "    if (header.getUint32(16) !== 16 || header.getUint32(20) !== 16) throw new Error(item.api + ' worker PNG dimensions differ');\n"
            "    const png = 'data:image/png;base64,' + btoa(Array.from(bytes, value => String.fromCharCode(value)).join(''));",
    }
    for before, after in replacements.items():
        if text.count(before) != 1:
            raise ValueError('Document GPU fixture changed; worker adapter requires review')
        text = text.replace(before, after, 1)
    if 'window' in text or 'document.' in text:
        raise ValueError('Worker GPU probe retained a document-only dependency')
    return text


def validate_phase(phase, *, backend=gpu):
    if not isinstance(phase, dict) or set(phase) != {'rootTimeOrigin', 'persisted', 'workers'}:
        raise ValueError('Worker GPU phase lacks actual document lifecycle evidence')
    epoch = phase['rootTimeOrigin']
    if type(epoch) not in (float, int) or not math.isfinite(epoch) or epoch <= 0:
        raise ValueError('Worker GPU owning document epoch is invalid')
    if type(phase['persisted']) is not bool:
        raise ValueError('Worker GPU persisted state must be a native boolean')
    workers = phase['workers']
    if not isinstance(workers, dict) or set(workers) != lifecycle.WORKER_KINDS:
        raise ValueError('All six actual worker classes are required')
    instances, tokens, gpu_instances, ports = set(), set(), set(), set()
    for kind, record in workers.items():
        instance, token = lifecycle.validate_record(kind, record)
        backend.validate_record(record['observed'])
        if record['observed']['timeOrigin'] != record['timeOrigin']:
            raise ValueError('Worker GPU epoch differs from its own worker global')
        instances.add(instance)
        tokens.add(token)
        gpu_instances.add(record['observed']['id'])
        ports.add(urlsplit(record['location']).port)
    if len(instances) != 6 or len(tokens) != 1 or len(gpu_instances) != 6:
        raise ValueError('Worker GPU records duplicated globals or mixed owners')
    if len(ports) != 1 or None in ports:
        raise ValueError('Worker GPU records mixed fixture server registrations')


def validate_pair(before, after, *, backend=gpu):
    validate_phase(before, backend=backend)
    validate_phase(after, backend=backend)
    if (before['persisted'] is not False or after['persisted'] is not True
            or before['rootTimeOrigin'] != after['rootTimeOrigin']):
        raise ValueError('Worker GPU requires a genuinely restored owning document')
    return _compare_workers(before, after, backend=backend)


def validate_restart_pair(before, after, *, kind, backend=gpu):
    validate_phase(before, backend=backend)
    validate_phase(after, backend=backend)
    if (not isinstance(kind, str) or kind not in {'service-classic', 'service-module'}
            or before['persisted'] is not True or after['persisted'] is not True
            or before['rootTimeOrigin'] != after['rootTimeOrigin']):
        raise ValueError('GPU restart requires the same genuinely retained owner')
    result = _compare_workers(before, after, backend=backend)
    target = next(row for row in result['workers'] if row['kind'] == kind)
    if target['service_restarted'] is not True:
        raise ValueError('Requested service worker did not obtain a new GPU global')
    return result


def _compare_workers(before, after, *, backend=gpu):
    rows = []
    previous_workers = {row['instanceId'] for row in before['workers'].values()}
    previous_gpu = {row['observed']['id'] for row in before['workers'].values()}
    for kind in sorted(lifecycle.WORKER_KINDS):
        first, second = before['workers'][kind], after['workers'][kind]
        if any(first[key] != second[key] for key in ('kind', 'token', 'location')):
            raise ValueError('Worker GPU registration changed: ' + kind)
        if first['request'] == second['request']:
            raise ValueError('Worker GPU response reused an old request: ' + kind)
        a, b = first['observed'], second['observed']
        same_worker = first['instanceId'] == second['instanceId'] and first['timeOrigin'] == second['timeOrigin']
        same_gpu = a['id'] == b['id'] and a['timeOrigin'] == b['timeOrigin']
        if same_worker:
            if not same_gpu or second['sequence'] <= first['sequence'] or b['read'] <= a['read']:
                raise ValueError('A live worker recreated its GPU resources: ' + kind)
        else:
            if (not kind.startswith('service-') or same_gpu or second['instanceId'] in previous_workers
                    or b['id'] in previous_gpu
                    or second['timeOrigin'] <= first['timeOrigin'] or second['sequence'] != 1 or b['read'] != 1):
                raise ValueError('Worker restart is not an explicit new service global: ' + kind)
        if {key: value for key, value in a.items() if key not in {'id', 'timeOrigin', 'read'}} != {key: value for key, value in b.items() if key not in {'id', 'timeOrigin', 'read'}}:
            raise ValueError('Worker GPU readback/PNG changed: ' + kind)
        rows.append(dict(kind=kind, retained_gpu_objects=same_worker,
                         service_restarted=not same_worker, policy_observations_stable=True))
    return dict(passed=True, workers=rows, dedicated_shared_retained=True,
        service_retention_guaranteed=False, forced_service_restart_verified=False,
        worker_audio_verified=False, webgpu_readback_verified=(backend is not gpu),
        cross_profile_isolation_verified=False, privacy_admitted=False, production_admitted=False)


def validate_runs(runs, *, backend=gpu):
    backend.validate_runs(runs)
    forced_modes = ['retained_gpu_service_restart_cases' in row for row in runs]
    if any(forced_modes) and not all(forced_modes):
        raise ValueError('GPU service restart coverage differs between manager modes')
    results = []
    tokens = set()
    for row in runs:
        before, after = row.get('retained_gpu_workers_before'), row.get('retained_gpu_workers_after')
        validate_phase(before, backend=backend)
        validate_phase(after, backend=backend)
        if before['rootTimeOrigin'] != row['retained_documents_before']['main']['timeOrigin']:
            raise ValueError('GPU worker owner differs from the actual retained main document')
        value = validate_pair(before, after, backend=backend)
        if row.get('retained_gpu_worker_validation') != value or row.get('retained_gpu_worker_cleanup') != {'closed': True}:
            raise ValueError('GPU worker validation or owned registration cleanup failed')
        token = next(iter(before['workers'].values()))['token']
        if token in tokens:
            raise ValueError('GPU worker registrations reused another manager run')
        tokens.add(token)
        if 'retained_gpu_service_restart_cases' in row:
            forced = validate_forced_cases(row['retained_gpu_service_restart_cases'],
                row['retained_documents_before'], row.get('retained_gpu_documents_after_restart'), before['rootTimeOrigin'], backend=backend)
            if row.get('retained_gpu_service_restart_validation') != forced:
                raise ValueError('Stored GPU restart validation differs')
            value = dict(value, forced_restart_validation=forced)
        results.append(dict(mode=row['mode'], **value))
    return dict(passed=True, runs=results, service_retention_guaranteed=False,
        forced_service_restart_verified=all(forced_modes), forced_service_restarts=4 if all(forced_modes) else 0,
        worker_audio_verified=False,
        webgpu_readback_verified=(backend is not gpu), cross_profile_isolation_verified=False,
        privacy_admitted=False, production_admitted=False)


async def force_service_restarts(session, versions, token, before, *, backend=gpu):
    cases = []
    validate_phase(before, backend=backend)
    if before['persisted'] is not True:
        raise ValueError('GPU service restart requires the restored owner')
    if not isinstance(token, str) or any(row['token'] != token for row in before['workers'].values()):
        raise ValueError('GPU service restart token differs from the owned registrations')
    for kind in ('service-classic', 'service-module'):
        reference = before['workers'][kind]
        lifecycle.validate_record(kind, reference)
        url = reference['location']
        matching = lambda: [value for value in versions['latest'].values()
                            if value.get('scriptURL') == url and value.get('status') == 'activated']
        await service.wait_until(lambda: len(matching()) == 1 and matching()[0].get('runningStatus') == 'running',
                                 'Exact owned running GPU service version')
        version = dict(matching()[0])
        if version.get('runningStatus') != 'running':
            raise ValueError('Owned GPU service was not running before stop')
        version_id = version['versionId']
        offset = len(versions['events'])
        await asyncio.wait_for(session.send('ServiceWorker.stopWorker', {'versionId': version_id}), timeout=10)
        stopped = lambda: [(index, value) for index, value in enumerate(versions['events'][offset:], offset)
                           if value.get('versionId') == version_id and value.get('scriptURL') == url
                           and value.get('runningStatus') == 'stopped']
        await service.wait_until(lambda: bool(stopped()), 'Explicit owned GPU service stopped event')
        stop_index, stop_event = stopped()[0]
        after = await lifecycle.collect(session, token, persisted=True)
        comparison = validate_restart_pair(before, after, kind=kind, backend=backend)
        running = lambda: [(index, value) for index, value in enumerate(versions['events'][stop_index + 1:], stop_index + 1)
                           if value.get('versionId') == version_id and value.get('scriptURL') == url
                           and value.get('runningStatus') == 'running']
        await service.wait_until(lambda: bool(running()), 'Restarted owned GPU service running event')
        run_index, run_event = running()[0]
        cases.append(dict(kind=kind, passed=True, before=before, after=after, comparison=comparison,
            version_events=[version, dict(stop_event), dict(run_event)],
            request_event_offset=offset, stopped_event_index=stop_index, restarted_event_index=run_index))
        before = after
    return cases


def validate_forced_cases(cases, document_before, document_after, owner_epoch, *, backend=gpu):
    if (not isinstance(cases, list) or len(cases) != 2
            or any(not isinstance(case, dict) or not isinstance(case.get('kind'), str) for case in cases)
            or {case.get('kind') for case in cases} != {'service-classic', 'service-module'}):
        raise ValueError('Both owned GPU service restart cases are required')
    backend.validate_pair(document_before, document_after)
    if type(owner_epoch) not in (int, float) or owner_epoch != document_before['main']['timeOrigin']:
        raise ValueError('GPU restart owner differs from the retained main document')
    result = []
    for case in cases:
        kind = case['kind']
        before, after = case.get('before'), case.get('after')
        comparison = validate_restart_pair(before, after, kind=kind, backend=backend)
        if case.get('passed') is not True or case.get('comparison') != comparison:
            raise ValueError('GPU restart comparison differs from the raw phases')
        if before['rootTimeOrigin'] != owner_epoch:
            raise ValueError('GPU restart replaced the owning document')
        events = case.get('version_events')
        if (not isinstance(events, list) or len(events) != 3
                or any(not isinstance(event, dict) for event in events)):
            raise ValueError('GPU service lifecycle events missing')
        url = before['workers'][kind]['location']
        if ([event.get('runningStatus') for event in events] != ['running', 'stopped', 'running']
                or any(event.get('scriptURL') != url or event.get('status') != 'activated' for event in events)
                or any(not isinstance(event.get('versionId'), str) or not event['versionId'] for event in events)
                or any(not isinstance(event.get('registrationId'), str) or not event['registrationId'] for event in events)
                or len({event['versionId'] for event in events}) != 1
                or len({event['registrationId'] for event in events}) != 1):
            raise ValueError('GPU service events do not bind the exact owned version')
        offset, stop, restart = (case.get(key) for key in
            ('request_event_offset', 'stopped_event_index', 'restarted_event_index'))
        if any(type(value) is not int for value in (offset, stop, restart)) or not 0 <= offset <= stop < restart:
            raise ValueError('GPU service events preceded the explicit stop request')
        previous, current = before['workers'][kind], after['workers'][kind]
        result.append(dict(kind=kind, passed=True, version_state_chain=['running', 'stopped', 'running'],
            new_worker_instance=previous['instanceId'] != current['instanceId'],
            new_gpu_instances=previous['observed']['id'] != current['observed']['id'],
            worker_sequence=current['sequence'], gpu_read_sequence=current['observed']['read'],
            policy_observations_stable=True, owning_document_unchanged=True))
    return dict(passed=True, cases=result, forced_service_restart_verified=True,
        post_restart_document_gpu_verified=True, service_retention_guaranteed=False,
        privacy_admitted=False, production_admitted=False)
