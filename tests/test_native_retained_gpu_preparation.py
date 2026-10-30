import ast
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'


@pytest.fixture
def retained_gpu_stage(tmp_path):
    record = json.loads((ENV / 'retained-gpu-objects76-preparation.json').read_bytes())
    patch = ENV / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    for row in record['sources']:
        if row['before_sha256'] is not None:
            original = (ROOT / row['source']).read_bytes()
            assert hashlib.sha256(original).hexdigest() == row['before_sha256']
            target = tmp_path / row['source']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original)
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error', str(patch)],
                   cwd=tmp_path, check=True, capture_output=True, timeout=30)
    for row in record['sources']:
        target = tmp_path / row['source']
        assert hashlib.sha256(target.read_bytes()).hexdigest() == row['staged_sha256']
        ast.parse(target.read_text(encoding='utf-8-sig'))
    return tmp_path / 'native/drafts/environment/first-script'


def test_retained_gpu_package_is_synthetic_only_and_does_not_admit_runtime():
    record = json.loads((ENV / 'retained-gpu-objects76-preparation.json').read_bytes())
    assert record['exact_replay_passed'] and record['default_probe'] == 'canvas'
    for key in ('selected', 'runtime_verified', 'native_tests_executed', 'browser_executed',
                'existing_modes_replaced', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False
    validation = record['synthetic_validator']
    assert validation['passed'] and validation['cases'] == 36
    assert validation['document_pair_cases'] == 22 and validation['aggregate_cases'] == 14
    assert len(validation['rejected_faults']) == len(set(validation['rejected_faults'])) == 34
    helper = next(row for row in record['sources'] if row['before_sha256'] is None)
    assert helper['staged_sha256'] == validation['validator_sha256']


def test_prepared_mode_keeps_default_and_existing_probe_choices(retained_gpu_stage):
    source = (retained_gpu_stage / 'protected_history_runtime.py').read_text(encoding='utf-8-sig')
    calls = [node for node in ast.walk(ast.parse(source))
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and node.func.attr == 'add_argument' and node.args
             and isinstance(node.args[0], ast.Constant) and node.args[0].value == '--probe']
    assert len(calls) == 1
    keywords = {item.arg: ast.literal_eval(item.value) for item in calls[0].keywords}
    assert keywords['default'] == 'canvas'
    assert keywords['choices'] == ('canvas', 'combined', 'retained-documents', 'retained-workers', 'retained-gpu-objects')
    helper = runpy.run_path(str(retained_gpu_stage / 'retained_gpu_objects.py'))
    assert 'gl.isProgram(item.program)' in helper['READ']
    assert 'gl.isTexture(item.source)' in helper['READ']
    assert 'original GPU resources lost or replaced' in helper['READ']
    assert 'surface_validator = None' in source
    assert "retained_objects.validate_runs(report['runs'])" in source


def test_prepared_mode_does_not_allow_service_restart_flag(retained_gpu_stage, tmp_path):
    output = tmp_path / 'must-not-exist'
    result = subprocess.run([sys.executable, str(retained_gpu_stage / 'protected_history_runtime.py'),
        '--executable', str(tmp_path / 'chrome.exe'), '--work-dir', str(output),
        '--driver-stage', str(tmp_path / 'driver'), '--probe', 'retained-gpu-objects',
        '--verify-service-lifecycle'], capture_output=True, text=True, timeout=30)
    assert result.returncode == 2
    assert '--verify-service-lifecycle requires --probe retained-workers' in result.stderr
    assert not output.exists()


def test_prepared_validator_rejects_unavailable_or_fabricated_coverage(retained_gpu_stage):
    helper = runpy.run_path(str(retained_gpu_stage / 'retained_gpu_objects.py'))
    for observed in (None, {}, {'main': {}}, {'webgl': {'available': False}}):
        with pytest.raises(ValueError):
            helper['validate_record'](observed)
    for runs in ([], [{'mode': 'manager-desktop'}],
                 [{'mode': 'manager-desktop'}, {'mode': 'manager-mobile-web'}]):
        with pytest.raises(ValueError):
            helper['validate_runs'](runs)
