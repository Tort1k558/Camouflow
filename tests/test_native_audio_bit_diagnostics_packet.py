from pathlib import Path
import json
import runpy

import pytest


PACKET = Path(__file__).resolve().parents[1] / 'native/drafts/audio-bit-diagnostics'


def test_audio_difference_summary_keeps_original_failures_and_missing_reference_coverage():
    summarize = runpy.run_path(str(PACKET / 'summarize.py'))['summarize']
    difference = dict(samples=2, changedSamples=1, finitePairs=2, nonFinitePairs=0,
                      signedZeroDifferences=0, maximumUlpDistance=1, maximumAbsoluteDifference=2**-26)
    measured = dict(passed=False, observed={'rows': [
        {'passed': False, 'channels': [{'difference': difference}]},
        {'passed': True, 'channels': [{'difference': None}]},
    ]})
    result = summarize(dict(passed=False, postguards_passed=True,
                            modes={'legacy': {'probes': {'fidelity': measured}}}))
    group = result['groups'][0]
    assert result['original_report_passed'] is result['production_admitted'] is False
    assert group['original_probe_passed'] is False
    assert group['original_failed_rows'] == 1
    assert group['maximum_ulp_distance'] == 1
    assert group['compared_samples'] == 2 and group['changed_samples'] == 1
    assert group['observed_rows'] == 2 and group['rows_without_sample_reference'] == 1


@pytest.mark.parametrize('report', [{}, {'modes': {'baseline': {'probes': {}}}}])
def test_audio_difference_summary_rejects_absent_metrics(report):
    summarize = runpy.run_path(str(PACKET / 'summarize.py'))['summarize']
    with pytest.raises(ValueError, match='No metric-bearing'):
        summarize(report)


@pytest.mark.parametrize('field,value', [('changedSamples', 3), ('samples', True),
                                        ('maximumUlpDistance', 0.5), ('maximumAbsoluteDifference', float('nan'))])
def test_audio_difference_summary_rejects_invalid_metrics(field, value):
    validate = runpy.run_path(str(PACKET / 'summarize.py'))['validate_difference']
    difference = dict(samples=2, changedSamples=1, finitePairs=2, nonFinitePairs=0,
                      signedZeroDifferences=0, maximumUlpDistance=1, maximumAbsoluteDifference=2**-26)
    with pytest.raises(ValueError):
        validate({**difference, field: value})


def test_r8_measured_differences_preserve_failed_compatibility_and_missing_selector():
    record = json.loads((PACKET / 'r8-observations.json').read_bytes())
    assert record['measurement_complete'] and record['postguards_passed'] and record['resources_closed']
    assert record['original_runner_failed'] and record['raw_report_rewritten'] is False
    assert record['browser_rerun_for_normalization'] is False
    assert record['profiles'] == 2 and record['reference_selectors'] == [1, 1]
    assert record['math_restart_exact'] and record['unmodified_math_graphs_exact']
    assert record['all_other_compared_samples_unchanged']
    assert [(row['profile_index'], row['probe'], row['changed_samples'])
            for row in record['legacy_differences']] == [
        (0, 'fidelity', 13536), (0, 'analyser', 1198), (0, 'worklet', 9140),
        (1, 'fidelity', 11208), (1, 'analyser', 1296), (1, 'worklet', 10006)]
    assert all(row['maximum_ulp_distance'] == 1 and row['original_failed_rows'] > 0
               for row in record['legacy_differences'])
    for name in ('compatibility_passed', 'reference_selectors_covered', 'both_math_backends_verified',
                 'internal_backend_observed', 'legacy_audio_repaired', 'privacy_admitted', 'production_admitted'):
        assert record[name] is False
