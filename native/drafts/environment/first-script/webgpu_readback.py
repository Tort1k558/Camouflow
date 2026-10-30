"""Owned WebGPU compatibility probe; no native privacy or lifecycle admission."""
import json
from pathlib import Path


SOURCE = Path(__file__).with_suffix('.js')
CONTEXTS = {'document', *(kind + '-' + worker + '-worker'
    for kind in ('classic', 'module') for worker in ('dedicated', 'shared', 'service'))}

WORKER_READ = r'''async ({kind, scriptType, url}) => {
  const read = port => new Promise((resolve, reject) => {
    const timer = setTimeout(() => {port.close?.(); reject(new Error('Worker read timeout'));}, 60000);
    port.onmessage = event => {
      clearTimeout(timer); port.close?.();
      if (event.data.error) reject(new Error(event.data.error)); else resolve(event.data.value);
    };
    port.onmessageerror = () => {
      clearTimeout(timer); port.close?.(); reject(new Error('Worker message decoding failed'));
    };
    port.start?.();
  });
  if (kind === 'dedicated') {
    const worker = new Worker(url, {type: scriptType});
    try {
      const result = read(worker);
      worker.postMessage('read');
      return await result;
    } finally {worker.terminate();}
  }
  if (kind === 'shared') {
    const worker = new SharedWorker(url, {type: scriptType, name: 'owned-webgpu-' + scriptType});
    try {
      const result = read(worker.port);
      worker.port.postMessage('read');
      return await result;
    } finally {worker.port.close();}
  }
  if (kind !== 'service') throw new Error('Unsupported worker kind');
  const registration = await navigator.serviceWorker.register(url, {scope: '/', type: scriptType});
  try {
    const worker = registration.installing || registration.waiting || registration.active;
    if (!worker) throw new Error('Owned service worker missing');
    if (worker.state !== 'activated') await new Promise((resolve, reject) => {
      const finish = error => {
        clearTimeout(timer); worker.removeEventListener('statechange', changed);
        if (error) reject(error); else resolve();
      };
      const changed = () => {
        if (worker.state === 'activated') finish();
        if (worker.state === 'redundant') finish(new Error('Owned service became redundant'));
      };
      const timer = setTimeout(() => finish(new Error('Service activation timeout')), 30000);
      worker.addEventListener('statechange', changed);
      changed();
    });
    const channel = new MessageChannel();
    try {
      const result = read(channel.port1);
      worker.postMessage('read', [channel.port2]);
      return await result;
    } finally {channel.port1.close(); channel.port2.close();}
  } finally {
    if (!await registration.unregister()) throw new Error('Owned service unregister failed');
  }
}'''


def worker_source(source, kind):
    reply = r'''async port => {
      try {port.postMessage({value: await probeWebGPU()});}
      catch(error) {port.postMessage({error: error.name + ': ' + error.message});}
    }'''
    if kind == 'dedicated':
        handler = f'self.onmessage = () => ({reply})(self);'
    elif kind == 'shared':
        handler = f'''self.onconnect = event => {{const port = event.ports[0];
          port.onmessage = async () => {{try {{await ({reply})(port);}}
            finally {{port.close(); self.close();}}}}; port.start();}};'''
    elif kind == 'service':
        handler = f'''self.addEventListener('message', event => {{
          event.waitUntil((async () => {{try {{await ({reply})(event.ports[0]);}}
            finally {{event.ports[0].close();}}}})());}});'''
    else:
        raise ValueError('Unsupported WebGPU worker kind')
    return source + '\n' + handler


def validate_observation(value):
    expected = dict(secureContext=True, exposed=True, measured=True,
        compatibilityPassed=True, privacyAdmitted=False,
        computeReads=[dict(words=64, referenceMatched=True, detached=True, rangeError='OperationError')] * 2,
        textureReads=[dict(width=7, height=3, rowPitch=256, referenceMatched=True, paddingZero=True)] * 2,
        validation=dict(alignmentError='OperationError', mapValidation=True, usageValidation=True), unexpected=[])
    if not isinstance(value, dict) or json.dumps(value, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise ValueError('WebGPU compute/texture/mapping compatibility is incomplete or failed')


def validate_rows(rows):
    if not isinstance(rows, list) or len(rows) != 14:
        raise ValueError('Fourteen WebGPU observations required')
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'mode', 'context', 'value'}
                or not isinstance(row['mode'], str) or not isinstance(row['context'], str)):
            raise ValueError('Malformed WebGPU observation')
        key = row['mode'], row['context']
        if key in seen or key[0] not in {'baseline', 'ready'} or key[1] not in CONTEXTS:
            raise ValueError('Duplicate or unexpected WebGPU context')
        seen.add(key)
        validate_observation(row['value'])
    return dict(passed=True, observations=14, contexts_per_mode=7,
        native_webgpu_readback_protection=False, retained_objects_verified=False,
        cross_profile_isolation_verified=False, privacy_admitted=False, production_admitted=False)
