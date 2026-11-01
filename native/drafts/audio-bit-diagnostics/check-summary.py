import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--report', type=Path, required=True)
args = parser.parse_args()
base = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('audio_summary', base / 'summarize.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
metric = dict(samples=4, changedSamples=2, finitePairs=4, nonFinitePairs=0,
              signedZeroDifferences=0, maximumUlpDistance=1, maximumAbsoluteDifference=2**-26)
row = dict(channels=[{'difference': metric}, {'difference': None}], passed=False)
probe = dict(passed=False, observed={'rows': [row, {'channels': [{'difference': None}], 'passed': True}]})
report = dict(passed=False, postguards_passed=True, modes={'legacy': {'probes': {'fidelity': probe}}})
original = copy.deepcopy(report)
result = module.summarize(report)
assert report == original
assert result['original_report_passed'] is False and result['original_postguards_passed'] is True
assert result['groups'][0]['maximum_ulp_distance'] == 1
assert result['groups'][0]['changed_samples'] == 2
assert result['groups'][0]['original_failed_rows'] == 1
assert result['groups'][0]['original_probe_passed'] is False
assert result['groups'][0]['observed_rows'] == 2
assert result['groups'][0]['compared_rows'] == 1
assert result['groups'][0]['rows_without_sample_reference'] == 1
assert module.summarize({'profiles': [report, report]})['groups'][1]['profile_index'] == 1
checks = 3
for field, value in [('samples', True), ('changedSamples', 5), ('finitePairs', 3),
                     ('signedZeroDifferences', 3), ('maximumUlpDistance', 1.5),
                     ('maximumAbsoluteDifference', float('nan'))]:
    invalid = {**metric, field: value}
    try:
        module.validate_difference(invalid)
    except ValueError:
        checks += 1
    else:
        raise AssertionError('Invalid metric accepted: ' + field)
for invalid in [{}, {'modes': {'baseline': {'probes': {}}}}]:
    try:
        module.summarize(invalid)
    except ValueError:
        checks += 1
    else:
        raise AssertionError('Absent metrics treated as zero')
module.validate_difference(dict(samples=1, changedSamples=1, finitePairs=0, nonFinitePairs=1,
                                signedZeroDifferences=0, maximumUlpDistance=None, maximumAbsoluteDifference=None))
checks += 1
record = dict(schema=1, passed=True, checks=checks, browser_executed=False,
              source_sha256=hashlib.sha256((base / 'summarize.py').read_bytes()).hexdigest(),
              checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
with args.report.open('x', encoding='utf-8', newline='\n') as output:
    output.write(json.dumps(record, indent=2) + '\n')
print(json.dumps(record))
