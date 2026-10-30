"""Top-document readback continuity only, not full GPU/Audio lifecycle admission."""

from scripts import verify_native_gpu_readback as gpu
from scripts.verify_native_audio_quality import strip_quality


def normalized(observed):
    if not isinstance(observed, dict) or set(observed) != {'gpu', 'audio'}:
        raise ValueError('Both measured GPU and Audio observations are required')
    audio = strip_quality({'document': observed['audio']})['document']
    if audio.get('available') is not True or audio.get('completionMutationVisible') is not True:
        raise ValueError('Completed offline Audio is required')
    for phase in ('signal', 'repeat', 'silence'):
        row = audio[phase]
        if (row.get('finite') is not True or row.get('closed') is not True
                or row.get('hash') != row.get('copiedHash') or row.get('hash') != row.get('rightHash')):
            raise ValueError('Audio readback is incomplete or inconsistent')
    if audio['signal'] != audio['repeat'] or audio['signal'].get('signal') is not True or audio['silence'].get('silence') is not True:
        raise ValueError('Repeated signal or silence semantics disagree')
    graphics = observed['gpu']
    if (not isinstance(graphics, dict) or set(graphics) != {'webgl', 'webgpu'}
            or not isinstance(graphics['webgl'], dict) or set(graphics['webgl']) != {'webgl', 'webgl2'}):
        raise ValueError('Both WebGL APIs and explicit WebGPU metadata are required')
    webgpu = graphics['webgpu']
    if (not isinstance(webgpu, dict) or type(webgpu.get('available')) is not bool
            or (not webgpu['available'] and (not isinstance(webgpu.get('reason'), str) or not webgpu['reason']))
            or (webgpu['available'] and (not isinstance(webgpu.get('info'), dict)
                or not isinstance(webgpu.get('deviceInfo'), dict) or not isinstance(webgpu.get('features'), list)
                or not isinstance(webgpu.get('limits'), dict)))):
        raise ValueError('Explicit WebGPU capability metadata is missing')
    for api, value in graphics['webgl'].items():
        if not isinstance(value, dict) or value.get('available') is not True or not isinstance(value.get('scene'), dict):
            raise ValueError('WebGL readback unavailable: ' + api)
        scene = value['scene']
        fields = ('pixels', 'repeat', 'crop', 'pbo', 'packed')
        if any(name not in scene for name in (*fields, 'png')) or 'translatedShaderLength' not in value:
            raise ValueError('WebGL readback/export observations missing: ' + api)
        gpu.validate_shader_readback({name: scene[name] for name in fields}, api, expected_pixels=scene['pixels'])
        if gpu.decode_png(scene['png']) != scene['pixels']:
            raise ValueError('WebGL export differs from measured pixels')
    return {'audio': audio, 'gpu': gpu.restart_state({'document': graphics})['document']}


def validate_pair(before, after):
    if normalized(before) != normalized(after):
        raise ValueError('GPU/Audio readback changed across retained history restoration')
    return dict(passed=True, document_contexts=1, webgl_apis=2, audio_phases=3,
                webgpu_readback_verified=False, privacy_admitted=False, production_admitted=False)


def validate_runs(runs):
    if (not isinstance(runs, list) or len(runs) != 2
            or any(not isinstance(row, dict) for row in runs)
            or {row.get('mode') for row in runs} != {'manager-desktop', 'manager-mobile-web'}):
        raise ValueError('Both manager environments are required exactly once')
    results = []
    for row in runs:
        if (row.get('bfcache_restored') is not True
                or row.get('post_surfaces_screen_verified') is not True
                or row.get('history_navigation', {}).get('type') != 'BackForwardCacheRestore'):
            raise ValueError('Actual retained BFCache restoration is required')
        result = validate_pair(row.get('surfaces_before'), row.get('surfaces_after'))
        results.append({'mode': row['mode'], **result})
    return dict(passed=True, runs=results, privacy_admitted=False, production_admitted=False)
