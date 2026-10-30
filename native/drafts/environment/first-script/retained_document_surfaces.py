"""Owned six-document recreated GPU/Audio reads; no worker or live-object claim."""
import json
import secrets

from scripts import verify_native_audio as audio
from scripts import verify_native_gpu_readback as gpu
from scripts.verify_native_audio_quality import strip_quality


INSTALL = r'''spec => {
  if (Object.hasOwn(window, 'glintRetainedSurfaceProbe')) throw new Error('Duplicate retained surface installation');
  const read = __OWNED_READ__;
  const state = {spec, events: [], active: null};
  Object.defineProperty(window, 'glintRetainedSurfaceProbe', {value: state});
  addEventListener('pageshow', event => state.events.push(event.persisted));
  if (spec.role === 'main') {
    state.sources = new Map();
    for (const [role, item] of Object.entries(spec.registry)) {
      let source = self;
      for (const index of item.path) source = source.frames[index];
      if (!source) throw new Error('Missing owned WindowProxy: ' + role);
      state.sources.set(role, source);
    }
    state.collect = async persisted => {
      if (state.active !== null) throw new Error('Overlapping retained surface collection');
      const request = crypto.randomUUID();
      return await new Promise((resolve, reject) => {
        const result = {};
        let timer;
        const finish = error => {
          clearTimeout(timer);
          state.active = null;
          if (error) reject(new Error(error)); else resolve(result);
        };
        state.active = {request, persisted, result, finish};
        timer = setTimeout(() => finish('Incomplete retained document surface coverage'), 30000);
        for (const [role, item] of Object.entries(spec.registry)) {
          state.sources.get(role).postMessage({kind: 'owned-glint-surface-request', token: spec.token,
            nonce: item.nonce, role, request}, item.origin);
        }
      });
    };
  }
  addEventListener('message', async event => {
    const value = event.data;
    if (!value || value.token !== spec.token) return;
    if (value.kind === 'owned-glint-surface-response' && spec.role === 'main') {
      const active = state.active;
      if (!active || value.request !== active.request) return;
      const expected = spec.registry[value.role];
      if (!expected || event.source !== state.sources.get(value.role) || event.origin !== expected.origin ||
          value.origin !== expected.origin || value.nonce !== expected.nonce || value.location !== expected.location) {
        active.finish('Retained response source/origin/nonce/document mismatch');
        return;
      }
      if (Object.hasOwn(active.result, value.role) || value.persisted !== active.persisted || value.error) {
        active.finish(value.error || 'Duplicate or wrong-lifecycle retained response');
        return;
      }
      active.result[value.role] = {nonce: value.nonce, origin: value.origin, location: value.location,
        persisted: value.persisted, timeOrigin: value.timeOrigin, observed: value.observed};
      if (Object.keys(active.result).length === Object.keys(spec.registry).length) active.finish(null);
      return;
    }
    if (value.kind !== 'owned-glint-surface-request' || event.source !== top ||
        event.origin !== spec.rootOrigin || value.role !== spec.role || value.nonce !== spec.nonce ||
        typeof value.request !== 'string' || !value.request) return;
    const response = {kind: 'owned-glint-surface-response', token: spec.token, request: value.request,
      role: spec.role, nonce: spec.nonce, origin: self.origin, location: location.href,
      timeOrigin: performance.timeOrigin, persisted: state.events.includes(true)};
    try { response.observed = await read(); }
    catch (error) { response.error = String(error); }
    top.postMessage(response, spec.rootOrigin);
  });
}'''


async def install(page, before, read):
    frames = {frame.name or 'main': frame for frame in page.frames}
    if set(frames) != set(before) or len(page.frames) != len(before) or len(before) != 6:
        raise ValueError('Six actual registered documents are required')
    registry = {}
    for role, frame in frames.items():
        path = []
        current = frame
        while current.parent_frame is not None:
            parent = current.parent_frame
            path.insert(0, parent.child_frames.index(current))
            current = parent
        row = before[role]
        if not row['origin'].startswith('http://'):
            raise ValueError('Only exact owned nonopaque HTTP fixture origins are allowed')
        registry[role] = dict(nonce=secrets.token_hex(24), path=path,
                              origin=row['origin'], location=row['location'])
    token = secrets.token_hex(24)
    expression = INSTALL.replace('__OWNED_READ__', '(' + read + ')')
    for role in ('main', *sorted(set(frames) - {'main'})):
        await frames[role].evaluate(expression, dict(token=token, role=role, nonce=registry[role]['nonce'],
            rootOrigin=before['main']['origin'], registry=registry if role == 'main' else None))
    return dict(token=token, registry=registry)


async def collect(session, registration, *, persisted):
    expression = ('(async spec => { const probe = window.glintRetainedSurfaceProbe; '
                  'if (!probe || probe.spec.token !== spec.token) throw new Error("Retained registration missing"); '
                  'return await probe.collect(spec.persisted); })(' +
                  json.dumps(dict(token=registration['token'], persisted=persisted)) + ')')
    response = await session.send('Runtime.evaluate', dict(expression=expression, awaitPromise=True,
        returnByValue=True, timeout=40000))
    if ('exceptionDetails' in response or not isinstance(response.get('result', {}).get('value'), dict)):
        raise ValueError('Retained document surface CDP evaluation failed: ' + str(response.get('exceptionDetails')))
    result = response['result']['value']
    if set(result) != set(registration['registry']):
        raise ValueError('Retained surface result has incomplete or extra document roles')
    for role, row in result.items():
        expected = registration['registry'][role]
        if (row['persisted'] is not persisted or row['nonce'] != expected['nonce']
                or row['origin'] != expected['origin'] or row['location'] != expected['location']):
            raise ValueError('Measured document identity/lifecycle differs: ' + role)
    return result


def validate_pair(before, after):
    roles = {'main', 'same', 'cross', 'nested-return', 'srcdoc', 'about-blank'}
    if set(before) != roles or set(after) != roles:
        raise ValueError('Six actual document surface observations are required')
    for role in sorted(roles):
        first, second = before[role], after[role]
        if (first['persisted'] is not False or second['persisted'] is not True
                or any(first[key] != second[key] for key in ('nonce', 'origin', 'location', 'timeOrigin'))):
            raise ValueError('Document was replaced or not genuinely restored: ' + role)
        previous = None
        for row in (first, second):
            observed = row['observed']
            stripped = strip_quality({role: observed['audio']})[role]
            if not audio.validate_context(role, stripped, previous):
                raise ValueError('Unavailable Audio does not count as document coverage: ' + role)
            gpu.validate_context(role, observed['gpu'], protected=True)
            previous = stripped
        if gpu.restart_state({role: first['observed']['gpu']}) != gpu.restart_state({role: second['observed']['gpu']}):
            raise ValueError('GPU observations changed after retained restoration: ' + role)
    return dict(passed=True, document_contexts=6, webgl_apis=2, audio_phases=3,
                retained_gpu_objects_verified=False, workers_verified=False,
                webgpu_readback_verified=False, privacy_admitted=False, production_admitted=False)
