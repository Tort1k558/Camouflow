"""Validate exact owned pixel contracts without tolerances or admission claims."""

CONTEXTS = ('document-html', 'document-offscreen', 'same-origin-frame', 'worker-classic', 'worker-module')
COUNTS = ('sourceFillChangedChannels', 'immediateCopyChangedChannels',
          'disjointWriteChangedChannels', 'uniformFillChangedChannels')


def validate(observed):
    if (not isinstance(observed, dict) or type(observed.get('schema')) is not int
            or observed['schema'] != 1 or type(observed.get('passed')) is not bool):
        raise ValueError('Expected a versioned owned Canvas observation')
    rows = observed.get('rows')
    if (not isinstance(rows, list) or len(rows) != len(CONTEXTS)
            or any(not isinstance(row, dict) for row in rows)
            or [row.get('name') for row in rows] != list(CONTEXTS)):
        raise ValueError('Owned Canvas context coverage is incomplete or reordered')
    complete = True
    for row in rows:
        if type(row.get('passed')) is not bool:
            raise ValueError('Canvas context verdict must be explicit')
        if 'error' in row:
            if row['passed'] or not isinstance(row['error'], str) or not row['error']:
                raise ValueError('Invalid Canvas context failure')
            complete = False
            continue
        if type(row.get('pixels')) is not int or row['pixels'] != 64:
            raise ValueError('Owned Canvas geometry changed')
        if any(type(row.get(name)) is not int or not 0 <= row[name] <= 256 for name in COUNTS):
            raise ValueError('Invalid changed-channel counts')
        if row['passed'] != all(row[name] == 0 for name in COUNTS):
            raise ValueError('Canvas exact-match verdict contradicts its counts')
    passed = complete and all(row['passed'] for row in rows)
    if observed['passed'] != passed:
        raise ValueError('Canvas combined verdict contradicts its contexts')
    return dict(measurement_complete=complete, passed=passed, contexts=len(rows),
                exact_copy_contracts_only=True, privacy_admitted=False, production_admitted=False)
