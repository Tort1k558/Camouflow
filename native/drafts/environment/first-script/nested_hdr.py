"""Nested worker finite Float16/alpha/crop fidelity; not broad HDR or GPU/Audio admission."""
from pathlib import Path
import runpy


COMMON = runpy.run_path(str(Path(__file__).with_name('nested_formats.py')))
CASES = COMMON['CASES']
worker_read = COMMON['worker_read']
matrix_read = COMMON['matrix_read']
server_type = COMMON['server_type']


def compare_nested_hdr(baseline, protected, compare_hdr, worker_classes):
    if set(worker_classes) != CASES:
        raise ValueError('Exactly four nested classic/module paths are required')
    for value in (baseline, protected):
        if (not isinstance(value, dict) or set(value) != {'document', 'workers'}
                or not isinstance(value['workers'], dict) or set(value['workers']) != CASES):
            raise ValueError('Document and all nested worker paths are required')
    document = compare_hdr(baseline['document'], protected['document'])
    comparisons, mismatches = {}, []
    for mode, value in (('baseline', baseline), ('protected', protected)):
        reference = {row['colorSpace']: row for row in value['document'] if row['kind'] == 'offscreen'}
        for name, pair in value['workers'].items():
            if not isinstance(pair, dict) or set(pair) != {'initial', 'recreated'}:
                raise ValueError('Both nested worker instances are required')
            if pair['initial'] != pair['recreated']:
                mismatches.append((mode, name, 'recreated'))
            for phase, rows in pair.items():
                if (not isinstance(rows, list) or len(rows) != 2
                        or any(not isinstance(row, dict) or row.get('kind') != 'offscreen'
                               or row.get('colorSpace') not in ('srgb', 'display-p3') for row in rows)):
                    raise ValueError('Every nested worker requires two real Offscreen HDR cases')
                for row in rows:
                    prior = reference[row['colorSpace']]
                    if any(row.get(field) != prior.get(field) for field in ('full', 'repeat', 'afterReput', 'crop')):
                        mismatches.append((mode, name, phase, row['colorSpace']))
    for name in CASES:
        for phase in ('initial', 'recreated'):
            paired = []
            for value in (baseline, protected):
                controls = [row for row in value['document'] if row['kind'] == 'html']
                paired.append(controls + value['workers'][name][phase])
            comparisons[name + '/' + phase] = compare_hdr(*paired)
    return dict(passed=document['passed'] and not mismatches and all(row['passed'] for row in comparisons.values()),
        worker_cases_per_profile=8, worker_paths_per_profile=4, recreation_samples_per_path=2,
        document_contexts_per_profile=4, document_worker_mismatches=mismatches,
        document_comparison=document, comparisons=comparisons, privacy_admitted=False, production_admitted=False)
