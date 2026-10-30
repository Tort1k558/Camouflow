"""Owned classic/module dedicated/shared/service Offscreen format experiment."""
from urllib.parse import parse_qs, urlsplit


CASES = {f'{kind}-{script_type}' for kind in ('dedicated', 'shared', 'service')
         for script_type in ('classic', 'module')}


def worker_read(document_read):
    assert document_read.count("['html', 'offscreen']") == 1
    return document_read.replace("['html', 'offscreen']", "['offscreen']")


READ = r'''async () => {
 const result = {};
 for (const kind of ['dedicated', 'shared', 'service']) for (const scriptType of ['classic', 'module']) {
  let worker, registration, channel, timer;
  try {
   const id = crypto.randomUUID();
   const url = `/owned-formats-${kind}.js?type=${scriptType}&id=${id}`;
   result[`${kind}-${scriptType}`] = await new Promise((resolve, reject) => {
    timer = setTimeout(() => reject(new Error(`Owned ${kind}/${scriptType} format timeout`)), 20000);
    const finish = event => {
     if (event.data.workerError) reject(new Error(JSON.stringify(event.data.workerError)));
     else resolve(event.data);
    };
    const fail = event => { event.preventDefault(); reject(new Error(`Owned ${kind}/${scriptType} error`)); };
    if (kind === 'dedicated') {
     worker = new Worker(url, {type:scriptType});
     worker.onmessage = finish; worker.onerror = fail; worker.postMessage('collect');
    } else if (kind === 'shared') {
     worker = new SharedWorker(url, {type:scriptType, name:id});
     worker.onerror = fail; worker.port.onmessage = finish;
     worker.port.start(); worker.port.postMessage('collect');
    } else {
     navigator.serviceWorker.register(url, {type:scriptType, scope:`/owned-formats/${id}/`}).then(value => {
      registration = value;
      const active = value.installing || value.waiting || value.active;
      if (!active) { reject(new Error('Owned service worker has no active lifecycle')); return; }
      const send = () => {
       if (active.state === 'redundant') { reject(new Error('Owned service worker became redundant')); return; }
       if (active.state !== 'activated' || channel) return;
       channel = new MessageChannel(); channel.port1.onmessage = finish;
       channel.port1.start(); active.postMessage('collect', [channel.port2]);
      };
      active.addEventListener('statechange', send); send();
     }, reject);
    }
   });
  } finally {
   clearTimeout(timer);
   if (kind === 'dedicated') worker?.terminate();
   if (kind === 'shared') worker?.port.close();
   channel?.port1.close(); channel?.port2.close();
   if (registration && !(await registration.unregister())) throw new Error('Owned service worker cleanup failed');
  }
 }
 return result;
}'''


def server_type(surfaces, read):
    class Handler(surfaces.SurfaceFixtureHandler):
        def do_GET(self):
            parsed = urlsplit(self.path)
            kinds = {f'/owned-formats-{kind}.js': kind for kind in ('dedicated', 'shared', 'service')}
            if parsed.path not in kinds:
                return super().do_GET()
            kind = kinds[parsed.path]
            script_type = parse_qs(parsed.query).get('type')
            if script_type not in (['classic'], ['module']):
                self.send_error(400)
                return
            prefix = 'export {};\n' if script_type == ['module'] else ''
            prefix += 'const collect = (' + read + ');\n'
            prefix += 'const reply = async port => { try { port.postMessage(await collect()); } catch (error) { port.postMessage({workerError:{name:error.name,message:error.message}}); } };\n'
            body = {
                'dedicated': 'self.onmessage = () => reply(self);',
                'shared': 'self.onconnect = event => { const port = event.ports[0]; port.onmessage = () => reply(port); port.start(); };',
                'service': "self.addEventListener('install', event => event.waitUntil(self.skipWaiting())); self.addEventListener('activate', event => event.waitUntil(self.clients.claim())); self.addEventListener('message', event => event.waitUntil(reply(event.ports[0])));",
            }[kind]
            data = (prefix + body).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            if kind == 'service':
                self.send_header('Service-Worker-Allowed', '/')
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    class Server(surfaces.SurfaceFixtureServer):
        def __init__(self, address):
            super().__init__(address)
            self.RequestHandlerClass = Handler

    return Server


def matrix_read(document_read):
    return 'async () => ({document: await (' + document_read + ')(), workers: await (' + READ + ')()})'


def compare_worker_formats(baseline, protected, compare_document):
    for value in (baseline, protected):
        if (type(value) is not dict or set(value) != {'document', 'workers'}
                or type(value['workers']) is not dict or set(value['workers']) != CASES):
            raise ValueError('A document and all six classic/module worker classes are required')
    document = compare_document(baseline['document'], protected['document'])
    values, coherence = {}, []
    for name in sorted(CASES):
        paired = []
        for mode, value in (('baseline', baseline), ('protected', protected)):
            controls = [row for row in value['document']['rows'] if row['kind'] == 'html']
            worker = value['workers'][name]
            if (type(worker) is not dict or type(worker.get('rows')) is not list
                    or len(worker['rows']) != 16
                    or any(type(row) is not dict or row.get('kind') != 'offscreen' for row in worker['rows'])):
                raise ValueError('Each worker must supply exactly sixteen Offscreen cases')
            paired.append({'rows': controls + worker['rows']})
            document_rows = {tuple(row[field] for field in ('colorSpace', 'colorType', 'readColorSpace', 'pixelFormat')): row
                             for row in value['document']['rows'] if row['kind'] == 'offscreen'}
            for row in worker['rows']:
                key = tuple(row.get(field) for field in ('colorSpace', 'colorType', 'readColorSpace', 'pixelFormat'))
                reference = document_rows.get(key)
                if reference is None or row.get('observed') != reference.get('observed') or 'observed' not in row:
                    coherence.append({'worker': name, 'mode': mode, 'format': list(key)})
        values[name] = compare_document(*paired)
    result = {'cases': 16 * len(CASES), 'worker_results_with_document_html_controls': values,
              'document_comparison': document, 'document_worker_mismatches': coherence}
    for field in ('baseline_unavailable', 'compatibility_regressions', 'no_effect'):
        result[field] = [{**item, 'worker': name} for name, row in values.items()
                         for item in row[field] if item['kind'] == 'offscreen']
    result['baseline_supported'] = result['cases'] - len(result['baseline_unavailable'])
    result['protected_supported'] = result['baseline_supported'] - len(result['compatibility_regressions'])
    result['compatibility_passed'] = document['compatibility_passed'] and all(row['compatibility_passed'] for row in values.values())
    result['protection_effect_observed'] = (document['protection_effect_observed'] and not coherence
                                           and all(row['protection_effect_observed'] for row in values.values()))
    return result
