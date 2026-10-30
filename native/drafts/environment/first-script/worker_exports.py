"""Worker PNG capture coherence over the existing independently decoded export probe."""


def validate_worker_exports(baseline, protected, validate_exports, worker_classes):
    expected = set(worker_classes)
    if len(expected) != 6:
        raise ValueError('Exactly six classic/module worker classes are required')
    profiles, mismatches, effects = {}, [], []
    for name, observed in (('baseline', baseline), ('protected', protected)):
        if (type(observed) is not dict or set(observed) != {'document', 'workers'}
                or type(observed['workers']) is not dict or set(observed['workers']) != expected):
            raise ValueError('The document and every classic/module worker class are required')
        document = validate_exports(observed['document'])
        controls = [row for row in observed['document'] if row['kind'] == 'html']
        document_rows = {(row['colorSpace'], row['colorType']): row
                         for row in document['rows'] if row['kind'] == 'offscreen'}
        workers = {}
        for worker_class in sorted(expected):
            rows = observed['workers'][worker_class]
            if (type(rows) is not list or len(rows) != 4
                    or any(type(row) is not dict or row.get('kind') != 'offscreen' for row in rows)):
                raise ValueError('Each worker must provide four real Offscreen export cases')
            validation = validate_exports(controls + rows)
            workers[worker_class] = {**validation,
                'rows': [row for row in validation['rows'] if row['kind'] == 'offscreen']}
            for row in workers[worker_class]['rows']:
                key = row['colorSpace'], row['colorType']
                reference = document_rows.get(key)
                digest = row['exports'].get('asyncSnapshot', {}).get('sha256')
                reference_digest = (reference or {}).get('exports', {}).get('asyncSnapshot', {}).get('sha256')
                if digest is None or digest != reference_digest:
                    mismatches.append({'profile': name, 'worker': worker_class,
                        'colorSpace': key[0], 'colorType': key[1]})
        profiles[name] = {'document': document, 'workers': workers}
    for worker_class in sorted(expected):
        before = {(row['colorSpace'], row['colorType']): row
                  for row in profiles['baseline']['workers'][worker_class]['rows']}
        for row in profiles['protected']['workers'][worker_class]['rows']:
            key = row['colorSpace'], row['colorType']
            reference = before[key]['exports'].get('asyncSnapshot', {}).get('sha256')
            actual = row['exports'].get('asyncSnapshot', {}).get('sha256')
            effects.append({'worker': worker_class, 'colorSpace': key[0], 'colorType': key[1],
                            'changed_from_baseline': reference is not None and actual is not None and reference != actual})
    return {'passed': (all(value['document']['passed'] and all(row['passed'] for row in value['workers'].values())
                            for value in profiles.values())
                       and not mismatches and all(row['changed_from_baseline'] for row in effects)),
        'worker_cases_per_profile': 4 * len(expected), 'worker_carriers_per_profile': 4 * len(expected),
        'document_cases_per_profile': 8, 'document_carriers_per_profile': 12,
        'profiles': profiles, 'document_worker_mismatches': mismatches, 'effect': effects,
        'privacy_admitted': False, 'production_admitted': False}
