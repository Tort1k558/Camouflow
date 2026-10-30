"""Owned original-resource continuity validator, not full GPU admission."""
import math
import re
from urllib.parse import urlsplit


READ = r'''async () => {
  const key = 'glintOwnedRetainedGpuObjects';
  if (!Object.hasOwn(window, key)) {
    const state = {id: crypto.randomUUID(), timeOrigin: performance.timeOrigin, reads: 0, records: []};
    Object.defineProperty(window, key, {value: state});
    for (const api of ['webgl', 'webgl2']) {
      const canvas = document.createElement('canvas');
      canvas.width = canvas.height = 16;
      const gl = canvas.getContext(api, {alpha: true, antialias: false, preserveDrawingBuffer: true});
      if (!gl) throw new Error(api + ' unavailable; no retained-object coverage');
      const record = {api, canvas, gl, lost: 0, restored: 0};
      canvas.addEventListener('webglcontextlost', event => {event.preventDefault(); record.lost++;});
      canvas.addEventListener('webglcontextrestored', () => record.restored++);
      const shader = (type, source) => {
        const value = gl.createShader(type);
        if (!value) throw new Error(api + ' shader allocation failed');
        gl.shaderSource(value, source); gl.compileShader(value);
        if (!gl.getShaderParameter(value, gl.COMPILE_STATUS)) throw new Error(api + ' shader compile failed');
        return value;
      };
      const modern = api === 'webgl2';
      record.vertexShader = shader(gl.VERTEX_SHADER, modern
        ? '#version 300 es\nin vec2 position;out vec2 uv;void main(){uv=(position+1.0)*0.5;gl_Position=vec4(position,0.0,1.0);}'
        : 'attribute vec2 position;varying vec2 uv;void main(){uv=(position+1.0)*0.5;gl_Position=vec4(position,0.0,1.0);}');
      record.fragmentShader = shader(gl.FRAGMENT_SHADER, modern
        ? '#version 300 es\nprecision highp float;in vec2 uv;uniform sampler2D source;out vec4 outputColor;void main(){outputColor=texture(source,uv);}'
        : 'precision highp float;varying vec2 uv;uniform sampler2D source;void main(){gl_FragColor=texture2D(source,uv);}');
      record.program = gl.createProgram();
      if (!record.program) throw new Error(api + ' program allocation failed');
      gl.attachShader(record.program, record.vertexShader); gl.attachShader(record.program, record.fragmentShader);
      gl.linkProgram(record.program);
      if (!gl.getProgramParameter(record.program, gl.LINK_STATUS)) throw new Error(api + ' program link failed');
      record.buffer = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, record.buffer);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,-1,1,1,1]), gl.STATIC_DRAW);
      record.attribute = gl.getAttribLocation(record.program, 'position');
      record.uniform = gl.getUniformLocation(record.program, 'source');
      if (record.attribute < 0 || record.uniform === null) throw new Error(api + ' shader bindings missing');
      record.expected = new Uint8Array(16 * 16 * 4);
      for (let pixel = 0; pixel < 256; pixel++) {
        record.expected.set([(pixel * 17) % 256, (pixel * 29 + 31) % 256, (pixel * 43 + 11) % 256, 255], pixel * 4);
      }
      const texture = data => {
        const value = gl.createTexture();
        if (!value) throw new Error(api + ' texture allocation failed');
        gl.bindTexture(gl.TEXTURE_2D, value);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 16, 16, 0, gl.RGBA, gl.UNSIGNED_BYTE, data);
        return value;
      };
      record.source = texture(record.expected);
      record.destination = texture(null);
      record.framebuffer = gl.createFramebuffer();
      gl.bindFramebuffer(gl.FRAMEBUFFER, record.framebuffer);
      gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, record.destination, 0);
      if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) throw new Error(api + ' incomplete framebuffer');
      if (gl.getError() !== gl.NO_ERROR) throw new Error(api + ' initial GL error');
      state.records.push(record);
    }
  }
  const state = window[key];
  const hash = async bytes => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)))
    .map(value => value.toString(16).padStart(2, '0')).join('');
  const result = {id: state.id, timeOrigin: state.timeOrigin, read: ++state.reads, apis: []};
  for (const item of state.records) {
    const {gl} = item;
    const valid = {
      context: !gl.isContextLost(), program: gl.isProgram(item.program),
      vertexShader: gl.isShader(item.vertexShader), fragmentShader: gl.isShader(item.fragmentShader),
      buffer: gl.isBuffer(item.buffer), sourceTexture: gl.isTexture(item.source),
      destinationTexture: gl.isTexture(item.destination), framebuffer: gl.isFramebuffer(item.framebuffer)
    };
    if (Object.values(valid).some(value => value !== true) || item.lost || item.restored) {
      throw new Error(item.api + ' original GPU resources lost or replaced');
    }
    gl.useProgram(item.program); gl.bindBuffer(gl.ARRAY_BUFFER, item.buffer);
    gl.vertexAttribPointer(item.attribute, 2, gl.FLOAT, false, 0, 0); gl.enableVertexAttribArray(item.attribute);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, item.source); gl.uniform1i(item.uniform, 0);
    gl.viewport(0, 0, 16, 16); gl.disable(gl.BLEND); gl.disable(gl.DITHER); gl.pixelStorei(gl.PACK_ALIGNMENT, 1);
    const reads = [];
    for (const framebuffer of [item.framebuffer, null]) {
      gl.bindFramebuffer(gl.FRAMEBUFFER, framebuffer); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      const first = new Uint8Array(1024), second = new Uint8Array(1024);
      gl.readPixels(0, 0, 16, 16, gl.RGBA, gl.UNSIGNED_BYTE, first);
      gl.readPixels(0, 0, 16, 16, gl.RGBA, gl.UNSIGNED_BYTE, second);
      if (gl.getError() !== gl.NO_ERROR) throw new Error(item.api + ' retained draw/read error');
      if (first.some((value, index) => value !== second[index])) throw new Error(item.api + ' repeated read differs');
      const maximumDelta = first.reduce((maximum, value, index) => Math.max(maximum, Math.abs(value - item.expected[index])), 0);
      if (maximumDelta > 2) throw new Error(item.api + ' texture draw differs from known reference');
      reads.push({target: framebuffer === null ? 'default' : 'framebuffer',
        hash: await hash(first), repeat: await hash(second), maximumDelta, bytes: first.length});
    }
    const png = item.canvas.toDataURL('image/png');
    if (!png.startsWith('data:image/png;base64,')) throw new Error(item.api + ' PNG export failed');
    result.apis.push({api: item.api, resources: valid, contextLostEvents: item.lost,
      contextRestoredEvents: item.restored, reads, pngHash: await hash(new TextEncoder().encode(png))});
  }
  return result;
}
'''
ROLES = {'main', 'same', 'cross', 'nested-return', 'srcdoc', 'about-blank'}
RESOURCES = {'context', 'program', 'vertexShader', 'fragmentShader', 'buffer',
             'sourceTexture', 'destinationTexture', 'framebuffer'}


def validate_record(row):
    if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id']:
        raise ValueError('Retained GPU instance marker missing')
    if (type(row.get('timeOrigin')) not in (int, float) or not math.isfinite(row['timeOrigin'])
            or row['timeOrigin'] <= 0 or type(row.get('read')) is not int or row['read'] <= 0):
        raise ValueError('Retained GPU epoch/read sequence malformed')
    if (not isinstance(row.get('apis'), list) or len(row['apis']) != 2
            or any(not isinstance(item, dict) for item in row['apis'])):
        raise ValueError('Both real WebGL API contexts are required')
    if [item.get('api') for item in row['apis']] != ['webgl', 'webgl2']:
        raise ValueError('Retained GPU APIs missing, duplicated or reordered')
    for item in row['apis']:
        resources = item.get('resources')
        if not isinstance(resources, dict) or set(resources) != RESOURCES or not all(value is True for value in resources.values()):
            raise ValueError('Original retained GPU resource is invalid')
        for key in ('contextLostEvents', 'contextRestoredEvents'):
            if type(item.get(key)) is not int or item[key] != 0:
                raise ValueError('Context loss/restoration is not original-object retention')
        reads = item.get('reads')
        if (not isinstance(reads, list) or len(reads) != 2
                or any(not isinstance(entry, dict) for entry in reads)
                or [entry.get('target') for entry in reads] != ['framebuffer', 'default']):
            raise ValueError('Both retained framebuffer and default read paths are required')
        for entry in reads:
            if (type(entry.get('bytes')) is not int or entry['bytes'] != 1024
                    or type(entry.get('maximumDelta')) is not int or not 0 <= entry['maximumDelta'] <= 2
                    or not isinstance(entry.get('hash'), str) or re.fullmatch('[0-9a-f]{64}', entry['hash']) is None
                    or entry.get('repeat') != entry['hash']):
                raise ValueError('Retained read bounds/reference/repeat check failed')
        if not isinstance(item.get('pngHash'), str) or re.fullmatch('[0-9a-f]{64}', item['pngHash']) is None:
            raise ValueError('Retained canvas PNG observation missing')


def validate_pair(before, after):
    if not isinstance(before, dict) or not isinstance(after, dict) or set(before) != ROLES or set(after) != ROLES:
        raise ValueError('Six actual document roles are required')
    instance_ids = set()
    ports = set()
    for role in sorted(ROLES):
        first, second = before[role], after[role]
        if not isinstance(first, dict) or not isinstance(second, dict):
            raise ValueError('Malformed retained document record')
        if (not isinstance(first.get('nonce'), str) or re.fullmatch('[0-9a-f]{48}', first['nonce']) is None
                or not isinstance(first.get('origin'), str)
                or not isinstance(first.get('location'), str) or not first['location']):
            raise ValueError('Retained document registration fields missing')
        origin = urlsplit(first['origin'])
        if origin.scheme != 'http' or origin.hostname not in {'127.0.0.1', 'localhost'} or origin.port is None:
            raise ValueError('Retained prototype requires the owned loopback fixture')
        ports.add(origin.port)
        if (first.get('persisted') is not False or second.get('persisted') is not True
                or any(first.get(key) != second.get(key) for key in ('nonce', 'origin', 'location', 'timeOrigin'))):
            raise ValueError('Retained GPU document identity/lifecycle differs: ' + role)
        a, b = first.get('observed'), second.get('observed')
        validate_record(a)
        validate_record(b)
        if (a['id'] != b['id'] or a['timeOrigin'] != b['timeOrigin'] or b['read'] <= a['read']
                or a['apis'] != b['apis'] or a['id'] in instance_ids
                or a['timeOrigin'] != first['timeOrigin']):
            raise ValueError('GPU resources/readback were replaced or changed: ' + role)
        instance_ids.add(a['id'])
    if len(ports) != 1:
        raise ValueError('Retained documents came from different fixture servers')
    return dict(passed=True, document_contexts=6, webgl_apis=2,
        retained_gpu_objects_verified=True, known_reference_maximum_delta=2,
        webgpu_readback_verified=False, workers_verified=False,
        privacy_admitted=False, production_admitted=False)


def validate_runs(runs):
    if (not isinstance(runs, list) or len(runs) != 2
            or any(not isinstance(row, dict) or not isinstance(row.get('mode'), str) for row in runs)
            or {row.get('mode') for row in runs} != {'manager-desktop', 'manager-mobile-web'}):
        raise ValueError('Two actual manager-mode runs are required')
    results = []
    instances = set()
    for row in runs:
        for key in ('passed', 'bfcache_restored', 'protected_arguments_verified',
                    'post_surfaces_screen_verified', 'runtime_resources_released', 'browser_connection_closed'):
            if row.get(key) is not True:
                raise ValueError('Retained GPU lifecycle/resources failed: ' + key)
        navigation = row.get('history_navigation')
        if (not isinstance(navigation, dict) or navigation.get('type') != 'BackForwardCacheRestore'
                or type(row.get('observed_processes')) is not int or row['observed_processes'] <= 1
                or type(row.get('remaining_observed_processes')) is not int or row['remaining_observed_processes'] != 0):
            raise ValueError('Retained GPU browser restoration/process evidence missing')
        value = validate_pair(row.get('retained_documents_before'), row.get('retained_documents_after'))
        if row.get('retained_gpu_object_validation') != value:
            raise ValueError('Stored retained GPU validation differs from actual observations')
        current = {item['observed']['id'] for item in row['retained_documents_before'].values()}
        if instances.intersection(current):
            raise ValueError('Manager runs reused the same document/resource instances')
        instances.update(current)
        results.append(dict(mode=row['mode'], **value))
    return dict(passed=True, runs=results, retained_gpu_objects_verified=True,
                webgpu_readback_verified=False, workers_verified=False,
                cross_profile_isolation_verified=False, privacy_admitted=False, production_admitted=False)
