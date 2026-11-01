"""Strict owned placeholder-frame copy validator; no runtime admission."""

import re


PATHS = ('drawImage', 'imageBitmap', 'toDataURL', 'toBlob', 'workerPNG')


def validate(observed):
    if (not isinstance(observed, dict) or type(observed.get('schema')) is not int
            or observed['schema'] != 1):
        raise ValueError('A versioned placeholder-frame observation is required')
    rows = observed.get('rows')
    if (not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows)
            or [row.get('api') for row in rows] != ['webgl', 'webgl2']):
        raise ValueError('Both ordered worker GPU variants must be measured')
    complete = True
    for row in rows:
        if type(row.get('passed')) is not bool:
            raise ValueError('Per-API verdict must be explicit')
        if 'error' in row:
            if not isinstance(row['error'], str) or not row['error'] or row['passed']:
                raise ValueError('Invalid failed observation')
            complete = False
            continue
        if (type(row.get('readyAttempts')) is not int or not 1 <= row['readyAttempts'] <= 120
                or type(row.get('knownFillChangedChannels')) is not int
                or not 1 <= row['knownFillChangedChannels'] <= 256
                or not isinstance(row.get('directSha256'), str)
                or not re.fullmatch('[0-9a-f]{64}', row['directSha256'])):
            raise ValueError('Real frame readiness and active protected GPU readback are required')
        copies = row.get('copies')
        expected = [(path, frequent) for path in PATHS for frequent in (False, True)]
        if (not isinstance(copies, list) or len(copies) != 10
                or any(not isinstance(copy, dict) for copy in copies)
                or [(copy.get('name'), copy.get('willReadFrequently')) for copy in copies] != expected):
            raise ValueError('Every ordered copy path/backing request is required')
        for copy in copies:
            if (type(copy.get('willReadFrequently')) is not bool
                    or any(type(copy.get(field)) is not int or not 0 <= copy[field] <= 256
                        for field in ('changedChannels', 'knownFillChangedChannels'))
                    or not isinstance(copy.get('sha256'), str)
                    or not re.fullmatch('[0-9a-f]{64}', copy['sha256'])):
                raise ValueError('Malformed copy count or digest')
            if (copy['changedChannels'] == 0) != (copy['sha256'] == row['directSha256']):
                raise ValueError('Copy verdict contradicts its digest')
            direct_known = row['knownFillChangedChannels']
            copy_known = copy['knownFillChangedChannels']
            if (abs(copy_known - direct_known) > copy['changedChannels']
                    or copy['changedChannels'] > copy_known + direct_known):
                raise ValueError('Copy counts contradict their common known-colour reference')
        if row['passed'] != all(copy['changedChannels'] == 0 for copy in copies):
            raise ValueError('API verdict contradicts exact copy equality')
    passed = complete and all(row['passed'] for row in rows)
    if type(observed.get('passed')) is not bool or observed['passed'] != passed:
        raise ValueError('Aggregate verdict contradicts measurements')
    return dict(measurement_complete=complete, passed=passed,
        protected_source_apis=sum('error' not in row for row in rows),
        copy_observations=sum(len(row.get('copies', [])) for row in rows),
        third_party_verdict_verified=False, production_admitted=False)
