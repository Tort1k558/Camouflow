import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-private-backing'


def preparation():
    return json.loads((ENV / 'webgpu-private-backing-preparation.json').read_bytes())


def test_private_backing_packet_binds_full_chain_and_checker():
    record = preparation()
    assert record['passed'] and record['exact_fourteen_packet_replay_and_reverse_verified']
    assert len(record['prerequisites']) == 13
    assert len(record['sources']) == 3 and len(record['composed_sources']) == 78
    for row in [*record['prerequisites'], {'patch': record['patch'], 'sha256': record['patch_sha256']}]:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']
    for name, key in [('check.py', 'checker_sha256'), ('predicates-template.cc', 'template_sha256')]:
        assert hashlib.sha256((MODULE / name).read_bytes()).hexdigest() == record[key]


def test_private_backing_reuses_one_native_predicate_at_all_entry_points():
    record = preparation()
    packet = (ENV / record['patch']).read_text(encoding='utf-8-sig')
    for text in ('!mHostMappedHeap', '!GetSharedResourceMemoryContents()',
                 'AllocationMethod::kExternal', '!ToBackend(buffer)->HasPrivateGlintReadbackBacking()',
                 '!ToBackend(indirectBuffer)->HasPrivateGlintReadbackBacking()',
                 '!source->HasPrivateGlintReadbackBacking()'):
        assert text in packet
    assert record['private_backing_source_prepared'] and record['native_syntax_verified']
    assert set(record['extracted_predicates_sha256']) == {'getter', 'binding', 'indirect', 'capture'}


def test_private_backing_predicates_are_not_actual_import_or_runtime_evidence():
    record = preparation()
    for key in ('gn_rechecked', 'component_link_verified', 'all_native_buffer_write_paths_audited',
                'actual_shared_or_host_mapped_import_executed', 'actual_native_device_queue_executed',
                'runtime_verified', 'selected', 'default_feature_enabled', 'privacy_admitted',
                'production_admitted'):
        assert record[key] is False
    runs = record['proofs']['native_syntax']['runs']
    assert len(runs) == 10 and all(row['returncode'] == 0 for row in runs)
    for row in record['proofs']['predicates']['runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        result = row['result']
        assert result['passed'] and result['assertions'] == 216 and result['origin_combinations'] == 16
        assert result['source_extracted_predicates_only'] is True
        assert result['actual_shared_or_host_mapped_import_executed'] is False


def test_private_backing_public_checker_passed_both_modes():
    observation = preparation()['public_checker_observation']
    assert observation['passed'] and observation['measurement_complete'] and observation['postguards_passed']
    assert observation['backend_mocked'] and observation['source_extracted_predicates_only']
    assert {row['sanitizer'] for row in observation['runs']} == {'none', 'address'}
    assert all(row['result']['assertions'] == 216 for row in observation['runs'])
    assert not observation['actual_shared_or_host_mapped_import_executed']
    assert not observation['actual_native_device_queue_executed']


def test_private_backing_extractor_rejects_missing_native_predicates(tmp_path):
    spec = importlib.util.spec_from_file_location('backing_checker', MODULE / 'check.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    native = tmp_path / 'third_party/dawn/src/dawn/native/d3d12'
    native.mkdir(parents=True)
    (native / 'BufferD3D12.h').write_text('', encoding='utf-8')
    with pytest.raises(ValueError, match='substring not found'):
        checker.extract_predicates(tmp_path)


def test_private_backing_changed_inputs_fail_before_compilation():
    observation = preparation()['changed_input_refusal']
    assert observation['passed']
    assert {row['case'] for row in observation['cases']} == {
        'packet', 'template', 'extraction-hash', 'generated-fixture-hash',
    }
    for row in observation['cases']:
        assert row['passed'] and row['returncode'] in (1, 2)
        assert row['expected_error_observed'] and row['refused_before_compilation']
