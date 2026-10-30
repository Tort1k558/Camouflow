"""Owned classic/module dedicated/shared/service policy continuity around document BFCache; service workers may restart."""
import json
import math
import secrets
from urllib.parse import parse_qs, urlsplit

from scripts import verify_native_audio as audio
from scripts import verify_native_gpu_readback as gpu
from scripts.verify_native_audio_quality import strip_quality


INSTALL = r'''async spec => {
  if (Object.hasOwn(window, 'glintRetainedWorkers')) throw new Error('Retained workers already installed');
  const state = {token: spec.token, records: new Map(), events: []};
  Object.defineProperty(window, 'glintRetainedWorkers', {value: state});
  addEventListener('pageshow', event => state.events.push(event.persisted));
  state.collect = async () => {
    const result = {};
    for (const [kind, item] of state.records) {
      const request = crypto.randomUUID();
      result[kind] = await new Promise((resolve, reject) => {
        const channel = item.class === 'service' ? new MessageChannel() : null;
        const port = channel ? channel.port1 : item.class === 'shared' ? item.worker.port : item.worker;
        let timer;
        const cleanup = () => {
          clearTimeout(timer); port.onmessage = null; port.onmessageerror = null;
          if (item.class !== 'service') item.worker.onerror = null;
          channel?.port1.close(); channel?.port2.close();
        };
        const fail = message => {cleanup(); reject(new Error(kind + ': ' + message));};
        port.onmessage = event => {
          const data = event.data;
          if (!data || data.request !== request) return;
          if (data.token !== state.token || data.kind !== kind || data.location !== item.url || data.error) {
            fail(data.error || 'Worker identity/response differs'); return;
          }
          cleanup(); resolve(data);
        };
        port.onmessageerror = () => fail('Worker message deserialization failed');
        if (item.class !== 'service') item.worker.onerror = event => fail(event.message || 'Worker execution failed');
        timer = setTimeout(() => fail('Retained worker timed out'), 30000);
        const message = {token: state.token, request};
        if (item.class === 'service') {
          channel.port1.start();
          if (!item.registration.active) {fail('No active registered service worker'); return;}
          item.registration.active.postMessage(message, [channel.port2]);
        } else {if (item.class === 'shared') port.start(); port.postMessage(message);}
      });
    }
    return {rootTimeOrigin: performance.timeOrigin, persisted: state.events.includes(true), workers: result};
  };
  state.close = async () => {
    for (const item of state.records.values()) {
      if (item.class === 'dedicated') item.worker.terminate();
      else if (item.class === 'shared') item.worker.port.close();
      else if (!(await item.registration.unregister())) throw new Error('Owned service worker unregister failed');
    }
    state.records.clear();
    return {closed: true};
  };
  for (const kind of ['dedicated', 'shared', 'service']) for (const type of ['classic', 'module']) {
    const url = new URL('/owned-retained-' + kind + '.js', location.href);
    url.searchParams.set('type', type); url.searchParams.set('token', spec.token);
    const entry = {class: kind, url: url.href};
    if (kind === 'dedicated') entry.worker = new Worker(url.href, {type});
    else if (kind === 'shared') entry.worker = new SharedWorker(url.href, {type, name: spec.token + '-' + type});
    else {
      entry.registration = await navigator.serviceWorker.register(url.href, {type, scope: '/owned-retained/' + spec.token + '/' + type + '/'});
      const worker = entry.registration.installing || entry.registration.waiting || entry.registration.active;
      if (!worker) throw new Error('Service worker registration has no worker');
      await new Promise((resolve, reject) => {
        let timer;
        const changed = () => {
          if (worker.state === 'activated' || worker.state === 'redundant') {
            clearTimeout(timer); worker.removeEventListener('statechange', changed);
            if (worker.state === 'activated') resolve(); else reject(new Error('Service worker became redundant'));
          }
        };
        timer = setTimeout(() => {worker.removeEventListener('statechange', changed); reject(new Error('Service worker activation timed out'));}, 30000);
        worker.addEventListener('statechange', changed); changed();
      });
    }
    state.records.set(kind + '-' + type, entry);
  }
}'''

def server_type(base, read):
    class Handler(base):
        def do_GET(self):
            parsed = urlsplit(self.path)
            kinds = {f'/owned-retained-{kind}.js': kind for kind in ('dedicated', 'shared', 'service')}
            if parsed.path not in kinds:
                return super().do_GET()
            query = parse_qs(parsed.query)
            if query.get('type') not in (['classic'], ['module']) or len(query.get('token', [])) != 1:
                self.send_error(400)
                return
            script_type = query['type'][0]
            worker_kind = kinds[parsed.path]
            body = ('export {};\n' if script_type == 'module' else '') + 'const read = (' + read + ');\n'
            body += r'''
const options = new URL(location.href).searchParams;
const token = options.get('token');
const kind = '__KIND__-' + options.get('type');
const instanceId = crypto.randomUUID();
let sequence = 0;
const reply = async (event, port) => {
  const data = event.data;
  if (!data || data.token !== token || typeof data.request !== 'string') return;
  const response = {request: data.request, token, kind, location: location.href,
    instanceId, timeOrigin: performance.timeOrigin, sequence: ++sequence};
  try { response.observed = await read(); }
  catch (error) { response.error = String(error); }
  port.postMessage(response);
};'''
            body = body.replace('__KIND__', worker_kind)
            body += {'dedicated': 'self.onmessage = event => reply(event, self);',
                'shared': 'self.onconnect = event => {const port = event.ports[0]; port.onmessage = value => reply(value, port); port.start();};',
                'service': "self.addEventListener('install', event => event.waitUntil(self.skipWaiting())); self.addEventListener('activate', event => event.waitUntil(Promise.resolve())); self.addEventListener('message', event => event.waitUntil(reply(event, event.ports[0])));"}[worker_kind]
            encoded = body.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript')
            self.send_header('Content-Length', str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return Handler


async def install(page):
    token = secrets.token_hex(24)
    await page.evaluate(INSTALL, dict(token=token))
    return token


async def collect(session, token, *, persisted):
    expression = '(async token => {const state = window.glintRetainedWorkers; if (!state || state.token !== token) throw new Error("Retained worker owner missing"); return await state.collect();})(' + json.dumps(token) + ')'
    result = await session.send('Runtime.evaluate', dict(expression=expression, awaitPromise=True, returnByValue=True, timeout=70000))
    value = result.get('result', {}).get('value')
    if result.get('exceptionDetails') or not isinstance(value, dict) or value.get('persisted') is not persisted:
        raise ValueError('Retained worker collection failed: ' + str(result.get('exceptionDetails')))
    return value


WORKER_KINDS = frozenset(kind + "-" + script_type for kind in ("dedicated", "shared", "service")
                         for script_type in ("classic", "module"))


def validate_record(kind, record):
    if kind not in WORKER_KINDS:
        raise ValueError('Unknown worker class')
    if not isinstance(record, dict) or set(record) != {
            'request', 'token', 'kind', 'location', 'instanceId', 'timeOrigin', 'sequence', 'observed'}:
        raise ValueError('Worker response evidence is incomplete')
    if any(not isinstance(record[key], str) or not record[key]
           for key in ('request', 'token', 'kind', 'location', 'instanceId')):
        raise ValueError('Worker identity fields must be explicit strings')
    if record['kind'] != kind or type(record['sequence']) is not int or record['sequence'] <= 0:
        raise ValueError('Worker class/sequence differs from its registered slot')
    clock = record['timeOrigin']
    if type(clock) not in (int, float) or not math.isfinite(clock) or clock <= 0:
        raise ValueError('Worker time origin is invalid')
    parsed = urlsplit(record['location'])
    query = parse_qs(parsed.query)
    worker_class, script_type = kind.split('-', 1)
    if (parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost'}
            or parsed.path != '/owned-retained-' + worker_class + '.js'
            or set(query) != {'token', 'type'} or query['type'] != [script_type]
            or query['token'] != [record['token']]):
        raise ValueError('Worker script URL differs from the owned registration')
    return record['instanceId'], record['token']


def validate_pair(before, after, *, canvas_document, document_gpu):
    kinds = WORKER_KINDS
    for phase in (before, after):
        if not isinstance(phase, dict) or set(phase) != {'rootTimeOrigin', 'persisted', 'workers'}:
            raise ValueError('Malformed owning document lifecycle evidence')
        clock = phase['rootTimeOrigin']
        if type(clock) not in (int, float) or not math.isfinite(clock) or clock <= 0:
            raise ValueError('Owning document time origin is invalid')
        if not isinstance(phase['workers'], dict) or set(phase['workers']) != kinds:
            raise ValueError('All six actual worker classes are required')
        instances, tokens = set(), set()
        for kind, record in phase['workers'].items():
            instance, token = validate_record(kind, record)
            instances.add(instance)
            tokens.add(token)
        if len(instances) != len(kinds) or len(tokens) != 1:
            raise ValueError('Worker instances were duplicated or joined to another owner')
    if before['persisted'] is not False or after['persisted'] is not True or before['rootTimeOrigin'] != after['rootTimeOrigin']:
        raise ValueError('Retained workers require the same genuinely restored owning document')
    if set(before['workers']) != kinds or set(after['workers']) != kinds:
        raise ValueError('All six actual classic/module worker observations are required')
    fields = ('colorSpace', 'colorType', 'readColorSpace', 'pixelFormat')
    expected = {tuple(row[key] for key in fields): row['observed']
                for row in canvas_document['rows'] if row['kind'] == 'offscreen'}
    if len(expected) != 16:
        raise ValueError('Sixteen independently validated document Offscreen cases are required')
    results = []
    for kind in sorted(kinds):
        first, second = before['workers'][kind], after['workers'][kind]
        same_instance = first['instanceId'] == second['instanceId'] and first['timeOrigin'] == second['timeOrigin']
        if any(first[key] != second[key] for key in ('token', 'location', 'kind')):
            raise ValueError('Worker registration identity changed: ' + kind)
        if not kind.startswith('service-') and not same_instance:
            raise ValueError('A retained dedicated/shared worker was replaced: ' + kind)
        if first['sequence'] != 1 or second['sequence'] != (2 if same_instance else 1):
            raise ValueError('Worker message sequence does not match measured lifetime: ' + kind)
        previous_audio = None
        for row in (first, second):
            observed = row['observed']
            formats = observed['canvas']
            if not isinstance(formats, dict) or len(formats['rows']) != 16:
                raise ValueError('Actual worker Offscreen coverage is incomplete')
            seen = set()
            for case in formats['rows']:
                key = tuple(case[field] for field in fields)
                if case['kind'] != 'offscreen' or key in seen or key not in expected or case.get('observed') != expected[key]:
                    raise ValueError('Worker Canvas differs from real document Offscreen output')
                seen.add(key)
            gpu.validate_context(kind, observed['gpu'], protected=True)
            for api in ('webgl', 'webgl2'):
                if observed['gpu']['webgl'][api]['scene']['pixels'] != document_gpu['webgl'][api]['scene']['pixels']:
                    raise ValueError('Worker GPU profile identity differs from document')
            stripped = strip_quality({kind: observed['audio']})[kind]
            available = audio.validate_context(kind, stripped, previous_audio)
            previous_audio = stripped
        if gpu.restart_state({kind: first['observed']['gpu']}) != gpu.restart_state({kind: second['observed']['gpu']}):
            raise ValueError('GPU output changed in the same retained dedicated worker')
        results.append(dict(kind=kind, same_worker_instance=same_instance, canvas_cases=16, webgl_apis=2,
                            audio_api_available=available, audio_readback_verified=available))
    return dict(passed=True, workers=results, worker_classes=6, shared_service_policy_continuity_verified=True, service_worker_controlled_document_verified=False,
                retained_gpu_objects_verified=False, webgpu_readback_verified=False,
                privacy_admitted=False, production_admitted=False)


def validate_runs(runs):
    if (not isinstance(runs, list) or len(runs) != 2 or any(not isinstance(row, dict) for row in runs)
            or {row.get('mode') for row in runs} != {'manager-desktop', 'manager-mobile-web'}):
        raise ValueError('Both manager environments are required exactly once')
    results = []
    for row in runs:
        if (row.get('bfcache_restored') is not True
                or row.get('history_navigation', {}).get('type') != 'BackForwardCacheRestore'
                or row.get('worker_lifecycle_cleanup') != {'closed': True}
                or row.get('post_surfaces_screen_verified') is not True
                or row.get('runtime_resources_released') is not True
                or row.get('browser_connection_closed') is not True
                or row.get('remaining_observed_processes') != 0):
            raise ValueError('Actual BFCache, worker cleanup, screen and resource release are required')
        result = validate_pair(row['worker_lifecycle_before'], row['worker_lifecycle_after'],
            canvas_document=row['canvas_before'], document_gpu=row['surfaces_before']['gpu'])
        if result != row.get('worker_lifecycle_validation'):
            raise ValueError('Worker validation summary differs from measured observations')
        results.append({'mode': row['mode'], **result})
    return dict(passed=True, runs=results, privacy_admitted=False, production_admitted=False)
