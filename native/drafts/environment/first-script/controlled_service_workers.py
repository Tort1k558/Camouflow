"""Owned service-controlled BFCache and explicit per-version worker restart checks."""
import asyncio
import json
import math
from urllib.parse import urlsplit

from scripts import verify_native_audio as audio
from scripts import verify_native_gpu_readback as gpu
from scripts.verify_native_audio_quality import strip_quality
import retained_worker_lifecycle as workers


READ = r'''async spec => {
  const controller = navigator.serviceWorker.controller;
  if (!controller || controller.scriptURL !== spec.url || controller.state !== 'activated')
    throw new Error('The owned document is not controlled by the expected active worker');
  const request = crypto.randomUUID();
  const worker = await new Promise((resolve, reject) => {
    const channel = new MessageChannel();
    let timer;
    const cleanup = () => {clearTimeout(timer); channel.port1.close(); channel.port2.close();};
    const fail = message => {cleanup(); reject(new Error(message));};
    channel.port1.onmessage = event => {
      const value = event.data;
      if (!value || value.request !== request) return;
      if (value.token !== spec.token || value.location !== spec.url || value.kind !== spec.kind || value.error) {
        fail(value.error || 'Controlled worker reply differs from the owned registration'); return;
      }
      cleanup(); resolve(value);
    };
    channel.port1.onmessageerror = () => fail('Invalid controlled worker message');
    timer = setTimeout(() => fail('Controlled worker response timed out'), 30000);
    channel.port1.start(); controller.postMessage({request, token: spec.token}, [channel.port2]);
  });
  return {controller: {scriptURL: controller.scriptURL, state: controller.state}, worker,
    document: {url: location.href, timeOrigin: performance.timeOrigin,
      persisted: window.glintHistoryProbe?.events.includes(true) === true}};
}'''


def server_type(original):
    class Handler(original):
        def do_GET(self):
            parsed = urlsplit(self.path)
            parts = parsed.path.split('/')
            if len(parts) == 5 and parts[1] == 'owned-retained' and parts[3] in {'classic', 'module'} and parts[4] == 'screen':
                if len(parts[2]) != 48 or any(value not in '0123456789abcdef' for value in parts[2]):
                    self.send_error(400)
                    return
                previous = self.path
                try:
                    self.path = '/screen?role=main'
                    return super().do_GET()
                finally:
                    self.path = previous
            return super().do_GET()

    return Handler


async def subscribe(session):
    state = dict(latest={}, events=[])

    def updated(event):
        for version in event['versions']:
            state['latest'][version['versionId']] = version
            state['events'].append(dict(version))

    session.on('ServiceWorker.workerVersionUpdated', updated)
    await session.send('ServiceWorker.enable')
    return state


async def evaluate(session, expression):
    result = await asyncio.wait_for(session.send('Runtime.evaluate', dict(expression=expression,
        returnByValue=True, awaitPromise=True, timeout=40000)), timeout=45)
    if 'exceptionDetails' in result or not isinstance(result.get('result', {}).get('value'), dict):
        raise ValueError('Controlled service worker evaluation failed: ' + str(result.get('exceptionDetails')))
    return result['result']['value']


def normalized(observed):
    gpu.validate_context('controlled-service', observed['gpu'], protected=True)
    clean = strip_quality({'controlled-service': observed['audio']})['controlled-service']
    available = audio.validate_context('controlled-service', clean)
    return dict(canvas=observed['canvas'], gpu=gpu.restart_state({'service': observed['gpu']})['service'],
                audio=clean), available


async def wait_until(predicate, description):
    try:
        async with asyncio.timeout(15):
            while not predicate():
                await asyncio.sleep(0.05)
    except TimeoutError as error:
        raise TimeoutError(description) from error


async def capture(context, domain_session, versions, run, probe, recapture, expected_screen):
    results = []
    for script_type in ('classic', 'module'):
        kind = 'service-' + script_type
        reference = run['worker_lifecycle_after']['workers'][kind]
        url, token = reference['location'], reference['token']
        parsed = urlsplit(url)
        if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or not parsed.port:
            raise ValueError('Service control must use the exact owned local fixture origin')
        origin = parsed.scheme + '://' + parsed.netloc
        client_url = origin + '/owned-retained/' + token + '/' + script_type + '/screen'
        page = await context.new_page()
        session = await context.new_cdp_session(page)
        result = dict(kind=kind, passed=False, client_url=client_url, service_script_url=url)
        results.append(result)
        primary = None
        try:
            await session.send('Page.enable')
            await page.goto(client_url, timeout=15000)
            before_screen = await probe['capture_page'](page)
            if probe['validate_page'](before_screen, expected_screen):
                raise ValueError('Controlled document screen disagrees with the profile')
            expression = '(' + READ + ')(' + json.dumps(dict(url=url, token=token, kind=kind)) + ')'
            initial = await evaluate(session, expression)
            history = dict(fixture_port=parsed.port)
            state = await probe['restore_history'](page, session, before_screen, history)
            if (history['history_navigation']['type'] != 'BackForwardCacheRestore'
                    or not probe['history_restored'](state)):
                raise ValueError('Service-controlled document did not genuinely enter BFCache')
            if probe['validate_page'](probe['restored_observations'](state), expected_screen):
                raise ValueError('Service-controlled BFCache screen is inconsistent')
            restored = await evaluate(session, expression)
            if (initial['document']['persisted'] is not False or restored['document']['persisted'] is not True
                    or initial['document']['timeOrigin'] != restored['document']['timeOrigin']
                    or initial['document']['url'] != restored['document']['url']):
                raise ValueError('Service-controlled owning document was replaced')
            matching = lambda: [value for value in versions['latest'].values()
                                if value['scriptURL'] == url and value['status'] == 'activated']
            await wait_until(lambda: len(matching()) == 1, 'Exact owned active service worker version')
            version = matching()[0]
            if version['runningStatus'] != 'running':
                raise ValueError('Controlled service worker is not confirmed running before stop')
            version_id = version['versionId']
            offset = len(versions['events'])
            await asyncio.wait_for(domain_session.send('ServiceWorker.stopWorker', {'versionId': version_id}), timeout=10)
            stopped = lambda: [value for value in versions['events'][offset:]
                               if value['versionId'] == version_id and value['scriptURL'] == url
                               and value['runningStatus'] == 'stopped']
            await wait_until(lambda: bool(stopped()), 'Explicit owned service worker stopped event')
            restarted = await evaluate(session, expression)
            if (restarted['worker']['instanceId'] == restored['worker']['instanceId']
                    or restarted['worker']['timeOrigin'] <= restored['worker']['timeOrigin']
                    or restarted['worker']['sequence'] != 1):
                raise ValueError('New worker execution after confirmed stop was not proven')
            if restarted['document'] != restored['document']:
                raise ValueError('Worker restart replaced or changed the restored client document')
            await wait_until(lambda: versions['latest'].get(version_id, {}).get('runningStatus') == 'running',
                             'Restarted owned service worker running event')
            reference_observed, _ = normalized(reference['observed'])
            for phase in (initial, restored, restarted):
                observed, audio_available = normalized(phase['worker']['observed'])
                if observed != reference_observed:
                    raise ValueError('Service controller policy/surfaces differ after BFCache or forced restart')
            after = await recapture(session, state)
            if probe['validate_page'](probe['restored_observations'](after), expected_screen):
                raise ValueError('Service worker restart changed a retained document screen')
            result.update(passed=True, service_controlled_document_verified=True,
                history_navigation=history['history_navigation'], initial=initial, restored=restored,
                version_before_stop=dict(version), stopped_event=stopped()[-1], restarted=restarted,
                version_after_restart=dict(versions['latest'][version_id]), initial_screen=before_screen,
                bfcache_state=state, post_restart_history=after,
                forced_restart_verified=True, policy_continuity_verified=True,
                all_six_document_screens_verified=True, audio_api_available=audio_available,
                audio_readback_verified=audio_available, privacy_admitted=False, production_admitted=False)
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                await session.detach()
            except Exception as error:
                if primary is None:
                    raise
                primary.add_note('Controlled service session cleanup failed: ' + str(error))
    return dict(passed=all(value['passed'] for value in results), results=results,
                scope='Owned classic/module service-controlled client BFCache and explicit per-version worker stop/restart; not retained GPU objects or WebGPU readback',
                privacy_admitted=False, production_admitted=False)


def validate_runs(runs, restore_observations, validate_screen):
    workers.validate_runs(runs)
    results = []
    for run in runs:
        controlled = run.get('controlled_service_validation')
        if (not isinstance(controlled, dict) or controlled.get('passed') is not True
                or not isinstance(controlled.get('results'), list) or len(controlled['results']) != 2
                or {row.get('kind') for row in controlled['results']} != {'service-classic', 'service-module'}):
            raise ValueError('Both actual classic/module service-controlled client results are required')
        expected_screen = run['phases'][0]['observed']['main']['snapshot']['screen']
        for row in controlled['results']:
            reference = run['worker_lifecycle_after']['workers'][row['kind']]
            expected, available = normalized(reference['observed'])
            first, restored, restarted = row['initial'], row['restored'], row['restarted']
            location = urlsplit(reference['location'])
            script_type = row['kind'].split('-', 1)[1]
            client_url = (location.scheme + '://' + location.netloc + '/owned-retained/'
                          + reference['token'] + '/' + script_type + '/screen')
            if row.get('client_url') != client_url:
                raise ValueError('Controlled client differs from the owned service scope')
            if (row.get('passed') is not True or row.get('forced_restart_verified') is not True
                    or row.get('history_navigation', {}).get('type') != 'BackForwardCacheRestore'
                    or first['document']['persisted'] is not False):
                raise ValueError('Actual service-controlled BFCache and explicit restart are required')
            for phase in (first, restored, restarted):
                record = phase['worker']
                clock = phase['document']['timeOrigin']
                if (phase['document']['url'] != client_url or type(clock) not in (int, float)
                        or not math.isfinite(clock) or clock <= 0):
                    raise ValueError('Controlled client URL/time origin is invalid')
                workers.validate_record(row['kind'], record)
                if (phase['controller'] != {'scriptURL': reference['location'], 'state': 'activated'}
                        or record['token'] != reference['token'] or record['location'] != reference['location']):
                    raise ValueError('Controlled service worker registration differs from the owning profile')
                actual, phase_available = normalized(record['observed'])
                if actual != expected or phase_available != available:
                    raise ValueError('Controlled service policy differs before/after BFCache or restart')
            for phase in (restored, restarted):
                if (phase['document']['persisted'] is not True
                        or phase['document']['timeOrigin'] != first['document']['timeOrigin']
                        or phase['document']['url'] != first['document']['url']):
                    raise ValueError('Controlled client document was replaced')
            before, stop, after = row['version_before_stop'], row['stopped_event'], row['version_after_restart']
            if (before['runningStatus'] != 'running' or stop['runningStatus'] != 'stopped'
                    or after['runningStatus'] != 'running'
                    or any(not isinstance(value['versionId'], str) or not value['versionId']
                           for value in (before, stop, after))
                    or len({value['versionId'] for value in (before, stop, after)}) != 1
                    or any(value['scriptURL'] != reference['location'] or value['status'] != 'activated'
                           for value in (before, stop, after))):
                raise ValueError('Same owned version running/stopped/running events are required')
            if (restarted['worker']['instanceId'] == restored['worker']['instanceId']
                    or restarted['worker']['timeOrigin'] <= restored['worker']['timeOrigin']
                    or restarted['worker']['sequence'] != 1):
                raise ValueError('A new worker execution after explicit stop is required')
            if len({value['worker']['request'] for value in (first, restored, restarted)}) != 3:
                raise ValueError('Controlled worker replies reused a request identifier')
            if validate_screen(row['initial_screen'], expected_screen):
                raise ValueError('Initial service-controlled document screen differs')
            for history in (row['bfcache_state'], row['post_restart_history']):
                if validate_screen(restore_observations(history), expected_screen):
                    raise ValueError('Service-controlled retained document screens differ')
            results.append(dict(mode=run['mode'], kind=row['kind'], passed=True,
                service_controlled_document_verified=True, forced_restart_verified=True,
                worker_audio_api_available=available, worker_audio_readback_verified=available))
    return dict(passed=True, results=results, controlled_clients=4, forced_restarts=4,
                retained_gpu_objects_verified=False, webgpu_readback_verified=False,
                privacy_admitted=False, production_admitted=False)
