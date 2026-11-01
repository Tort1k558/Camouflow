"""Validate rendering observations without admitting a replacement Canvas policy."""

import math
import re


CONTEXTS = ('document-html', 'document-offscreen', 'same-origin-frame',
            'worker-classic', 'worker-module')


def validate(observed):
    if (not isinstance(observed, dict) or type(observed.get('schema')) is not int
            or observed['schema'] != 1 or type(observed.get('passed')) is not bool):
        raise ValueError('Expected a versioned native rendering observation')
    rows = observed.get('rows')
    if (not isinstance(rows, list) or len(rows) != len(CONTEXTS)
            or any(not isinstance(row, dict) for row in rows)
            or [row.get('name') for row in rows] != list(CONTEXTS)):
        raise ValueError('Native rendering context coverage is incomplete or reordered')
    complete = True
    for row in rows:
        if type(row.get('passed')) is not bool:
            raise ValueError('Rendering context verdict must be explicit')
        if 'error' in row:
            if row['passed'] or not isinstance(row['error'], str) or not row['error']:
                raise ValueError('Invalid rendering context failure')
            complete = False
            continue
        count = row.get('plainChangedChannels')
        if type(count) is not int or not 0 <= count <= 256:
            raise ValueError('Invalid plain-colour changed-channel count')
        images = row.get('images')
        if (not isinstance(images, list) or len(images) != 2
                or any(not isinstance(image, dict) for image in images)
                or any(type(image.get('alpha')) is not bool for image in images)
                or [image['alpha'] for image in images] != [True, False]):
            raise ValueError('Expected both ordered alpha modes')
        for image in images:
            digest, metrics = image.get('sha256'), image.get('metrics')
            if (not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest)
                    or type(image.get('repeatExact')) is not bool):
                raise ValueError('Invalid rendering digest or repetition verdict')
            if (not isinstance(metrics, list) or len(metrics) != 5
                    or any(type(value) not in (int, float) for value in metrics)):
                raise ValueError('Invalid text metric vector')
            try:
                finite = all(math.isfinite(value) for value in metrics)
            except OverflowError:
                finite = False
            if not finite:
                raise ValueError('Text metrics must be finite')
        passed = count == 0 and all(image['repeatExact'] for image in images)
        if row['passed'] != passed:
            raise ValueError('Rendering context verdict contradicts observations')
    passed = complete and all(row['passed'] for row in rows)
    if observed['passed'] != passed:
        raise ValueError('Rendering combined verdict contradicts its contexts')
    return dict(measurement_complete=complete, passed=passed, contexts=len(rows),
                privacy_admitted=False, production_admitted=False)
