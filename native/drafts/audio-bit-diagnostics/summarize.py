import argparse
import hashlib
import json
import math
from pathlib import Path


def validate_difference(value):
    if not isinstance(value, dict):
        raise ValueError('Missing Audio sample difference')
    names = ('samples', 'changedSamples', 'finitePairs', 'nonFinitePairs', 'signedZeroDifferences')
    if any(type(value.get(name)) is not int or value[name] < 0 for name in names):
        raise ValueError('Invalid Audio difference counts')
    count = value['samples']
    if (value['finitePairs'] + value['nonFinitePairs'] != count
            or value['changedSamples'] > count
            or value['signedZeroDifferences'] > min(value['changedSamples'], value['finitePairs'])):
        raise ValueError('Inconsistent Audio difference counts')
    ulp, absolute = value.get('maximumUlpDistance'), value.get('maximumAbsoluteDifference')
    if value['finitePairs']:
        if (type(ulp) is not int or not 0 <= ulp <= 0xffffffff
                or type(absolute) not in (int, float) or not math.isfinite(absolute) or absolute < 0):
            raise ValueError('Invalid finite Audio difference maxima')
        if not value['changedSamples'] and (ulp != 0 or absolute != 0):
            raise ValueError('Unchanged Audio data has nonzero difference')
    elif ulp is not None or absolute is not None:
        raise ValueError('Nonfinite-only Audio data must not have finite maxima')
    return value


def summarize(report):
    cohorts = report.get('profiles') or [report]
    if not isinstance(cohorts, list) or not cohorts:
        raise ValueError('Missing Audio profiles')
    groups = []
    for profile_index, profile in enumerate(cohorts):
        for mode, measurement in profile.get('modes', {}).items():
            for probe, observation in measurement.get('probes', {}).items():
                rows = observation.get('observed', {}).get('rows', [])
                samples = changed = nonfinite = zero = 0
                maximum_ulp = maximum_absolute = None
                comparisons = failed_rows = compared_rows = 0
                for row in rows:
                    differences = ([row['difference']] if 'difference' in row else [])
                    differences += [channel['difference'] for channel in row.get('channels', [])
                                    if channel.get('difference') is not None]
                    if not differences:
                        continue
                    compared_rows += 1
                    failed_rows += row.get('passed') is not True
                    for difference in differences:
                        value = validate_difference(difference)
                        comparisons += 1
                        samples += value['samples']
                        changed += value['changedSamples']
                        nonfinite += value['nonFinitePairs']
                        zero += value['signedZeroDifferences']
                        if value['finitePairs']:
                            maximum_ulp = max(maximum_ulp or 0, value['maximumUlpDistance'])
                            maximum_absolute = max(maximum_absolute or 0, value['maximumAbsoluteDifference'])
                if comparisons:
                    groups.append(dict(profile_index=profile_index, mode=mode, probe=probe,
                                       comparisons=comparisons, compared_samples=samples,
                                       changed_samples=changed, nonfinite_pairs=nonfinite,
                                       signed_zero_differences=zero, maximum_ulp_distance=maximum_ulp,
                                       maximum_absolute_difference=maximum_absolute,
                                       observed_rows=len(rows), compared_rows=compared_rows,
                                       rows_without_sample_reference=len(rows) - compared_rows,
                                       original_failed_rows=failed_rows,
                                       original_probe_passed=observation.get('passed') is True))
    if not groups:
        raise ValueError('No metric-bearing Audio observations; do not infer zero differences')
    return dict(schema=1, scope='Descriptive sample differences only; original exact-match gates unchanged',
                original_report_passed=report.get('passed') is True,
                original_postguards_passed=report.get('postguards_passed') is True,
                production_admitted=False, groups=groups)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('report', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    raw = args.report.read_bytes()
    result = summarize(json.loads(raw))
    result['report_sha256'] = hashlib.sha256(raw).hexdigest()
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write(json.dumps(result, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
