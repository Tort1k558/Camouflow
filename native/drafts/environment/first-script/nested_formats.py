"""Nested dedicated-worker Canvas matrices; explicit recreation, not worker GPU/Audio admission."""
from urllib.parse import parse_qs, urlsplit


CASES = {f'{parent}-{child}' for parent in ('classic', 'module') for child in ('classic', 'module')}


def worker_read(read):
    if read.count("['html', 'offscreen']") != 1:
        raise ValueError('Expected the exact Canvas matrix')
    return read.replace("['html', 'offscreen']", "['offscreen']")


READ = r'''async () => {
 const results = {};
 for (const parent of ['classic', 'module']) for (const child of ['classic', 'module']) {
  const samples = [];
  for (let iteration = 0; iteration < 2; iteration++) {
   let worker, timer;
   try {
    const id = crypto.randomUUID();
    samples.push(await new Promise((resolve, reject) => {
     timer = setTimeout(() => reject(new Error('Nested parent timeout')), 20000);
     worker = new Worker(`/owned-nested-parent.js?parent=${parent}&child=${child}&id=${id}`, {type:parent});
     worker.onmessage = event => event.data.workerError ? reject(new Error(JSON.stringify(event.data.workerError))) : resolve(event.data);
     worker.onerror = event => { event.preventDefault(); reject(new Error('Nested parent error')); };
     worker.postMessage('collect');
    }));
   } finally { clearTimeout(timer); worker?.terminate(); }
  }
  results[`${parent}-${child}`] = {initial:samples[0], recreated:samples[1]};
 }
 return results;
}'''


def matrix_read(document_read):
    return 'async () => ({document:await (' + document_read + ')(),workers:await (' + READ + ')()})'


def server_type(surfaces, read):
    class Handler(surfaces.SurfaceFixtureHandler):
        def do_GET(self):
            request = urlsplit(self.path)
            query = parse_qs(request.query)
            if request.path not in ('/owned-nested-parent.js', '/owned-nested-leaf.js'):
                return super().do_GET()
            parent, child = query.get('parent'), query.get('child')
            if parent not in (['classic'], ['module']) or child not in (['classic'], ['module']):
                self.send_error(400)
                return
            script_type = parent[0] if request.path.endswith('parent.js') else child[0]
            prefix = 'export {};\n' if script_type == 'module' else ''
            if request.path.endswith('leaf.js'):
                body = ('const collect=(' + read + '); self.onmessage=async()=>{try{'
                        'self.postMessage(await collect());}catch(e){self.postMessage({workerError:{name:e.name,message:e.message}});}};')
            else:
                body = r'''self.onmessage = async () => {
 let worker, timer, response;
 try {
  const url = new URL(self.location.href);
  const child = url.searchParams.get('child');
  response = await new Promise((resolve, reject) => {
   timer = setTimeout(() => reject(new Error('Nested child timeout')), 10000);
   worker = new Worker('/owned-nested-leaf.js' + url.search, {type:child});
   worker.onmessage = event => resolve(event.data);
   worker.onerror = event => { event.preventDefault(); reject(new Error('Nested child error')); };
   worker.postMessage('collect');
  });
 } catch (e) { response={workerError:{name:e.name,message:e.message}}; }
 finally { clearTimeout(timer); worker?.terminate(); }
 self.postMessage(response);
};'''
            data = (prefix + body).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)
    class Server(surfaces.SurfaceFixtureServer):
        def __init__(self, address):
            super().__init__(address)
            self.RequestHandlerClass = Handler
    return Server


def compare_nested_formats(baseline, protected, compare_formats, worker_classes):
    if set(worker_classes) != CASES:
        raise ValueError('Exactly four classic/module parent-child paths are required')
    for value in (baseline, protected):
        if not isinstance(value, dict) or set(value) != {'document', 'workers'} or not isinstance(value['workers'], dict):
            raise ValueError('Document and nested-worker observations are required')
    document = compare_formats(baseline['document'], protected['document'])
    comparisons, mismatches = {}, []
    for mode, value in (('baseline', baseline), ('protected', protected)):
        if set(value['workers']) != set(worker_classes):
            raise ValueError('All four nested parent/child type combinations are required')
        reference = [row for row in value['document']['rows'] if row['kind'] == 'offscreen']
        for name, pair in value['workers'].items():
            if not isinstance(pair, dict) or set(pair) != {'initial', 'recreated'}:
                raise ValueError('Both nested worker instances are required exactly once')
            if pair['initial'] != pair['recreated']:
                mismatches.append((mode, name, 'recreated'))
            for phase, rows in pair.items():
                if (not isinstance(rows, dict) or not isinstance(rows.get('rows'), list)
                        or len(rows['rows']) != 16):
                    raise ValueError('Every nested worker requires sixteen real Offscreen cases')
                if rows['rows'] != reference:
                    mismatches.append((mode, name, phase))
    for name in worker_classes:
        for phase in ('initial', 'recreated'):
            paired = []
            for value in (baseline, protected):
                rows = [row for row in value['document']['rows'] if row['kind'] == 'html']
                paired.append({'rows': rows + value['workers'][name][phase]['rows']})
            comparisons[name + '/' + phase] = compare_formats(*paired)
    passed = (document['compatibility_passed'] and document['protection_effect_observed']
              and not mismatches and all(row['compatibility_passed'] and row['protection_effect_observed']
                                         for row in comparisons.values()))
    return dict(passed=passed, worker_cases_per_profile=64, worker_paths_per_profile=4, recreation_samples_per_path=2, document_worker_mismatches=mismatches,
                comparisons=comparisons, privacy_admitted=False, production_admitted=False)
