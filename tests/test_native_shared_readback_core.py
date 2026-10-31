"""Shared GPU source preparation must not claim browser integration."""
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/environment'


def preparation():
    return json.loads((DIRECTORY / 'shared-gpu-readback-core-preparation.json').read_bytes())


def test_shared_core_archive_preserves_the_existing_canvas_implementation(tmp_path):
    record = preparation()
    patch = DIRECTORY / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    shared = 'gpu/command_buffer/common/glint/'
    original = 'third_party/blink/renderer/core/html/canvas/glint/canvas_readback_candidate.cc'

    def apply(*options):
        subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error',
                        *options, str(patch)], cwd=tmp_path, check=True,
                       capture_output=True, timeout=15)

    apply('--include=' + shared + '*')
    rows = [row for row in record['sources'] if row['source'].startswith(shared)]
    assert len(rows) == 8 and all(row['before_sha256'] is None for row in rows)
    for row in rows:
        data = (tmp_path / row['source']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == row['after_sha256']
        assert b'third_party/blink/' not in data
        assert not data.startswith(bytes.fromhex('efbbbf')) and b'\r' not in data
    apply('--reverse', '--include=' + original)
    original_row = next(row for row in record['sources'] if row['source'] == original)
    data = (tmp_path / original).read_bytes()
    assert hashlib.sha256(data).hexdigest() == original_row['before_sha256']
    assert data == (tmp_path / (shared + 'canvas_readback_candidate.cc')).read_bytes()
    assert original_row['after_sha256'] is None
    apply('--include=' + original)
    apply('--reverse', '--include=' + shared + '*')
    assert not list(tmp_path.rglob('*.cc')) and not list(tmp_path.rglob('*.h'))


def test_shared_core_measurements_are_exact_but_not_gn_or_runtime_admission():
    record = preparation()
    assert record['algorithm_implementation_unchanged']
    assert record['sparse_patch_roundtrip_verified'] and record['postguards_passed']
    assert record['source_policy_classification_verified']
    assert len(record['sources']) == 13
    assert len(record['syntax_checks']) == 5
    assert all(row['returncode'] == row['diagnostic_bytes'] == 0 for row in record['syntax_checks'])
    checks = record['isolated_component_checks']
    assert {(row['name'], row['sanitizer']) for row in checks} == {
        (name, sanitizer) for name in ('layout', 'provenance', 'snapshot', 'callback', 'uncertain')
        for sanitizer in ('none', 'address')}
    assertions = dict(layout=525936, provenance=1232777, snapshot=748, callback=201, uncertain=191874)
    for row in checks:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result']['passed'] and row['result']['browser_integrated'] is False
        assert row['result']['assertions'] == assertions[row['name']]
    for key in ('selected', 'browser_integrated', 'runtime_verified', 'native_queue_hooks_installed',
                'native_webgpu_readback_protection', 'canvas_gpu_export_mismatch_resolved',
                'privacy_admitted', 'production_admitted', 'gn_generated', 'linked'):
        assert record[key] is False
    assert record['candidate_net_path_support_required']
    assert len(record['measured_test_sources_sha256']) == 5
    for source, expected in record['measured_test_sources_sha256'].items():
        assert hashlib.sha256((ROOT / source).read_bytes()).hexdigest() == expected


def test_shared_core_is_unselected_and_keeps_one_existing_gn_owner():
    record = preparation()
    patch = (DIRECTORY / record['patch']).read_text(encoding='utf-8-sig')
    assert '+    "glint/canvas_readback_candidate.cc",' in patch
    assert '-  "canvas/glint/canvas_readback_candidate.cc",' in patch
    assert '+    "//gpu/command_buffer/common",' in patch
    assert '+    "//third_party/boringssl",' in patch
    checkpoint = ROOT / 'native/drafts/upstream-156/checkpoints/001-076.json'
    assert 'shared-gpu-readback-core' not in checkpoint.read_text(encoding='utf-8-sig')


def test_full_dawn_tooling_baseline_does_not_admit_this_later_shared_core():
    record = json.loads((DIRECTORY / 'canonical-python76-dawn-tooling-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['git_head'].startswith('9539fc2')
    assert record['counts'] == dict(tests=5015, passed=5014, skipped=1, failures=0, errors=0)
    assert record['native_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
