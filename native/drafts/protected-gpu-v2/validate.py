"""Explicit Canvas-v2 GPU contract; legacy validators and evidence stay unchanged."""

import copy


def validate_textures(rows, *, protected):
    from scripts.verify_native_gpu import expected_texture_readback

    if type(protected) is not bool:
        raise ValueError('An explicit protection mode is required')
    expected = expected_texture_readback()
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError('All six ordered texture/mip/layer observations are required')
    changed = 0
    for row, reference in zip(rows, expected, strict=True):
        if (not isinstance(row, dict) or set(row) != set(reference)
                or any(type(row.get(key)) is not int for key in ('mip', 'layer'))
                or not isinstance(row.get('size'), list)
                or any(type(value) is not int for value in row['size'])
                or any(row[key] != reference[key] for key in ('mip', 'layer', 'size'))):
            raise ValueError('Texture identity, ordering or dimensions differ')
        for name in ('packed', 'repeat', 'sampled'):
            value = row.get(name)
            if (not isinstance(value, list) or len(value) != len(reference[name])
                    or any(type(byte) is not int or not 0 <= byte <= 255 for byte in value)):
                raise ValueError('Texture byte array is incomplete or malformed')
        if row['repeat'] != row['packed'] or row['sampled'] != row['packed']:
            raise ValueError('Repeated copy and shader sampling must agree exactly')
        width, height = reference['size']
        colour_indices = {256 * (y + 1) + x * 4 + channel
                          for y in range(height) for x in range(width) for channel in range(3)}
        for index, (actual, original) in enumerate(zip(row['packed'], reference['packed'], strict=True)):
            if protected and index in colour_indices:
                if actual >> 1 != original >> 1:
                    raise ValueError('Texture upper colour bits changed')
                changed += actual != original
            elif actual != original:
                raise ValueError('Texture alpha, untouched padding or unprotected bytes changed')
    if protected and not changed:
        raise ValueError('Selected protection left the entire nonuniform texture fixture raw')
    return dict(textures=len(rows), changed_colour_bytes=changed,
                repeat_exact=True, shader_sample_exact=True, padding_and_alpha_exact=True)


def normalize(observed, *, protected):
    from scripts.verify_native_gpu import CONTEXTS, expected_texture_readback

    if not isinstance(observed, dict) or set(observed) != CONTEXTS:
        raise ValueError('Every exact document and worker context is required')
    normalized = copy.deepcopy(observed)
    summaries = {}
    for context, value in observed.items():
        gpu = value.get('webgpu') if isinstance(value, dict) else None
        if not isinstance(gpu, dict) or gpu.get('available') is not True:
            raise ValueError('Real WebGPU availability is required in ' + context)
        summaries[context] = validate_textures(gpu.get('textures'), protected=protected)
        # Capability validation is reused only after validating every original
        # protected byte, padding location, repeat and shader observation above.
        normalized[context]['webgpu']['textures'] = expected_texture_readback()
    if protected:
        reference = observed['document']['webgpu']['textures']
        if any(value['webgpu']['textures'] != reference for value in observed.values()):
            raise ValueError('Profile-identity WebGPU textures disagree across contexts')
    return normalized, summaries


def validate(observed, *, pipeline_version, protected, baseline=None, previous=None):
    from scripts import verify_native_gpu_readback as readback

    if type(pipeline_version) is not int or pipeline_version != 2:
        raise ValueError('Only explicitly selected Canvas pipeline version 2 is supported')
    normalized, textures = normalize(observed, protected=protected)
    baseline_normalized = None
    if baseline is not None:
        baseline_source, _ = normalize(baseline, protected=False)
        baseline_normalized = readback.validate_readback(
            baseline_source, protected=False, derivation_mode='profile-identity')
    readback.validate_readback(normalized, protected=protected, baseline=baseline_normalized,
                               derivation_mode='profile-identity')
    if previous is not None:
        validate(previous, pipeline_version=pipeline_version, protected=protected, baseline=baseline)
        if readback.restart_state(observed) != readback.restart_state(previous):
            raise ValueError('Original GPU pixels, metadata or API results changed across restart')
    return dict(contract_version=2, pipeline_version=2, contexts=len(textures),
                textures=sum(row['textures'] for row in textures.values()),
                changed_colour_bytes=sum(row['changed_colour_bytes'] for row in textures.values()),
                original_observations_mutated=False, legacy_validator_replaced=False)


def validate_profile_isolation(baseline, first, second, *, pipeline_version):
    from scripts import verify_native_gpu_readback as readback

    validate(baseline, pipeline_version=pipeline_version, protected=False)
    validate(first, pipeline_version=pipeline_version, protected=True, baseline=baseline)
    validate(second, pipeline_version=pipeline_version, protected=True, baseline=baseline)
    normalized = [normalize(value, protected=protected)[0]
                  for value, protected in ((baseline, False), (first, True), (second, True))]
    readback.validate_profile_isolation(*normalized, derivation_mode='profile-identity')
    for context in baseline:
        values = [value[context]['webgpu']['textures'] for value in (baseline, first, second)]
        if values[0] == values[1] or values[0] == values[2] or values[1] == values[2]:
            raise ValueError('WebGPU texture identity did not isolate both profiles in ' + context)
    return dict(contract_version=2, isolated_profiles=2, contexts=len(baseline))
