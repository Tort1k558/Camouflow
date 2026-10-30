"""Strict manager screen and top-document Canvas continuity after BFCache."""


EXPECTED = {
    'manager-desktop': (1366, 768, 1, 'landscape-primary'),
    'manager-mobile-web': (390, 844, 3, 'portrait-primary'),
}
PHASES = ('initial', 'initial', 'focus-restore', 'focus-restore', 'focus-restore', 'history-return')


def validate_runs(runs, validate_page, compare_formats):
    if (not isinstance(runs, list) or len(runs) != 2
            or {row.get('mode') for row in runs if isinstance(row, dict)} != set(EXPECTED)):
        raise ValueError('Both manager environments are required exactly once')
    results = []
    for row in runs:
        phases = row.get('phases')
        if (not isinstance(phases, list) or any(not isinstance(value, dict) for value in phases)
                or tuple(value.get('phase') for value in phases) != PHASES):
            raise ValueError('All initial, focus and restored history phases are required')
        width, height, dpr, orientation = EXPECTED[row['mode']]
        initial = phases[0]['observed']['main']['snapshot']['screen']
        expected = {**initial, 'width': width, 'height': height, 'availWidth': width,
                    'availHeight': height, 'availLeft': 0, 'availTop': 0, 'dpr': dpr,
                    'orientation': {'type': orientation, 'angle': 0}}
        errors = []
        for phase in phases:
            errors.extend(validate_page(phase['observed'], expected))
            if phase.get('errors') != []:
                errors.append('Collector phase contains errors')
        for flag in ('passed', 'protected_arguments_verified', 'bfcache_restored',
                     'browser_connection_closed', 'runtime_resources_released', 'canvas_stable_across_bfcache'):
            if row.get(flag) is not True:
                errors.append(flag + ' is not verified')
        if row.get('history_navigation', {}).get('type') != 'BackForwardCacheRestore':
            errors.append('Actual BFCache navigation was not observed')
        if (type(row.get('observed_processes')) is not int or row['observed_processes'] <= 0
                or type(row.get('remaining_observed_processes')) is not int
                or row['remaining_observed_processes'] != 0):
            errors.append('Observed runtime processes were not proven released')
        before, after = row.get('canvas_before'), row.get('canvas_after')
        formats = compare_formats(before, after)
        if (before != after or not formats['compatibility_passed']
                or formats['baseline_supported'] != 32 or formats['protected_supported'] != 32):
            errors.append('Canvas readback is unavailable or changed across history restoration')
        results.append({'mode': row['mode'], 'passed': not errors, 'errors': errors,
                        'screen_phases': len(phases), 'canvas_cases': formats['cases']})
    return {'passed': all(row['passed'] for row in results), 'runs': results,
            'privacy_admitted': False, 'production_admitted': False}
