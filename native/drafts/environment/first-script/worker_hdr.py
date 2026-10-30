"""Bounded finite Float16 worker readback over existing document controls."""


def compare_worker_hdr(baseline, protected, compare_hdr, worker_classes):
    expected = set(worker_classes)
    if len(expected) != 6:
        raise ValueError('Exactly six worker classes are required')
    for value in (baseline, protected):
        if (type(value) is not dict or set(value) != {'document', 'workers'}
                or type(value['workers']) is not dict or set(value['workers']) != expected):
            raise ValueError('Document and every worker class are required')
    document = compare_hdr(baseline['document'], protected['document'])
    results, mismatches = {}, []
    for worker_class in sorted(expected):
        paired = []
        for mode, value in (('baseline', baseline), ('protected', protected)):
            controls = [row for row in value['document'] if row['kind'] == 'html']
            rows = value['workers'][worker_class]
            if (type(rows) is not list or len(rows) != 2
                    or any(type(row) is not dict or row.get('kind') != 'offscreen'
                           or type(row.get('colorSpace')) is not str
                           or row['colorSpace'] not in ('srgb', 'display-p3') for row in rows)):
                raise ValueError('Each worker requires two real Offscreen color-space cases')
            paired.append(controls + rows)
            reference = {row['colorSpace']: row for row in value['document'] if row['kind'] == 'offscreen'}
            for row in rows:
                previous = reference.get(row.get('colorSpace'))
                if (previous is None or row.get('full') is None
                        or any(row.get(field) != previous.get(field) for field in ('full', 'repeat', 'afterReput', 'crop'))):
                    mismatches.append({'profile': mode, 'worker': worker_class, 'colorSpace': row.get('colorSpace')})
        results[worker_class] = compare_hdr(*paired)
    return {'passed': document['passed'] and not mismatches and all(row['passed'] for row in results.values()),
        'worker_contexts_per_profile': 2 * len(expected), 'document_contexts_per_profile': 4,
        'document_comparison': document, 'worker_results_with_document_html_controls': results,
        'document_worker_mismatches': mismatches,
        'privacy_admitted': False, 'production_admitted': False}
