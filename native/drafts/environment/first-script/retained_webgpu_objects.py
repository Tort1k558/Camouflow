"""Original owned WebGPU resources across real document BFCache; no native protection."""
import math
from pathlib import Path
import re
from urllib.parse import urlsplit

READ = Path(__file__).with_suffix('.js').read_text(encoding='utf-8-sig')


def validate_record(value):
    if (not isinstance(value, dict) or not isinstance(value.get('id'), str)
            or re.fullmatch('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value['id']) is None
            or type(value.get('timeOrigin')) not in (int, float) or not math.isfinite(value['timeOrigin'])
            or value['timeOrigin'] <= 0 or type(value.get('read')) is not int or value['read'] <= 0
            or not isinstance(value.get('sameReferences'), list) or len(value['sameReferences']) != 9
            or any(item is not True for item in value['sameReferences'])
            or any(value.get(key) is not True for key in ('computeMatched', 'textureMatched', 'paddingZero', 'detached'))
            or value.get('deviceLost') is not False or value.get('unexpected') != []):
        raise ValueError('Retained WebGPU resource/readback observation invalid')


def validate_pair(before, after):
    roles = {'main', 'same', 'cross', 'about-blank', 'srcdoc', 'nested-return'}
    if not isinstance(before, dict) or not isinstance(after, dict) or set(before) != roles or set(after) != roles:
        raise ValueError('Six exact document roles required')
    instances, ports = set(), set()
    for role in roles:
        a, b = before[role], after[role]
        if (not isinstance(a, dict) or not isinstance(b, dict)
                or set(a) != {'nonce', 'origin', 'location', 'persisted', 'timeOrigin', 'observed'}
                or set(b) != set(a)
                or a.get('persisted') is not False or b.get('persisted') is not True
                or any(a.get(key) != b.get(key) for key in ('nonce', 'origin', 'location', 'timeOrigin'))):
            raise ValueError('Retained WebGPU document lifecycle changed')
        if not isinstance(a.get('nonce'), str) or re.fullmatch('[0-9a-f]{48}', a['nonce']) is None:
            raise ValueError('Missing owned document nonce')
        if not isinstance(a.get('origin'), str) or not isinstance(a.get('location'), str) or not a['location']:
            raise ValueError('Owned document origin/location missing')
        origin = urlsplit(a['origin'])
        if origin.scheme != 'http' or origin.hostname not in {'127.0.0.1', 'localhost'} or origin.port is None:
            raise ValueError('Only owned loopback documents allowed')
        ports.add(origin.port)
        x, y = a.get('observed'), b.get('observed')
        validate_record(x)
        validate_record(y)
        if x['id'] != y['id'] or y['read'] <= x['read'] or x['id'] in instances or x['timeOrigin'] != a['timeOrigin'] or y['timeOrigin'] != b['timeOrigin']:
            raise ValueError('Retained WebGPU objects replaced or stale')
        instances.add(x['id'])
    if len(ports) != 1:
        raise ValueError('Document registrations mixed fixture servers')
    return dict(passed=True, document_contexts=6, original_webgpu_objects_verified=True,
        native_webgpu_readback_protection=False, workers_verified=False,
        privacy_admitted=False, production_admitted=False)


def validate_runs(runs):
    if (not isinstance(runs, list) or len(runs) != 2
            or any(not isinstance(row, dict) or not isinstance(row.get('mode'), str) for row in runs)
            or {row['mode'] for row in runs} != {'manager-desktop', 'manager-mobile-web'}):
        raise ValueError('Two actual manager mode runs required')
    instances = set()
    for row in runs:
        if any(row.get(key) is not True for key in ('passed', 'bfcache_restored', 'protected_arguments_verified',
                'post_surfaces_screen_verified', 'runtime_resources_released', 'browser_connection_closed')):
            raise ValueError('WebGPU runtime/lifecycle cleanup failed')
        if (not isinstance(row.get('history_navigation'), dict)
                or row['history_navigation'].get('type') != 'BackForwardCacheRestore'
                or type(row.get('observed_processes')) is not int or row['observed_processes'] <= 1
                or type(row.get('remaining_observed_processes')) is not int or row['remaining_observed_processes'] != 0):
            raise ValueError('Real BFCache restoration and owned process cleanup required')
        result = validate_pair(row.get('retained_documents_before'), row.get('retained_documents_after'))
        if row.get('retained_gpu_object_validation') != result:
            raise ValueError('Stored WebGPU validation differs from actual observations')
        current = {value['observed']['id'] for value in row['retained_documents_before'].values()}
        if instances.intersection(current):
            raise ValueError('Manager modes reused WebGPU resource instances')
        instances.update(current)
    return dict(passed=True, original_webgpu_objects_verified=True,
        native_webgpu_readback_protection=False, workers_verified=False,
        privacy_admitted=False, production_admitted=False)
