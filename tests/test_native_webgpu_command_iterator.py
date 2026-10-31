import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-command-iterator'


def observation():
    return json.loads((ENV / 'webgpu-command-iterator-observations.json').read_bytes())


def test_native_iterator_binds_real_sources_fixture_and_render_source_gate():
    record = observation()
    assert record['passed']
    assert record['source_chain_packets'] == 29 and record['source_chain_paths'] == 88
    for path, key in ((MODULE / 'check.py', 'checker_sha256'),
                      (MODULE / 'command_iterator_test.cc', 'fixture_sha256'),
                      (MODULE.parent / 'webgpu-render-buffer-routing/check.py', 'source_gate_checker_sha256'),
                      (ENV / 'webgpu-render-buffer-routing-preparation.json', 'source_gate_record_sha256')):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record[key]
    assert len(record['pinned_native_files']) == 90
    assert len(record['native_translation_units']) == 6
    assert all(path in record['pinned_native_files'] for path in record['native_translation_units'])
    assert 'third_party/dawn/src/dawn/native/CommandAllocator.cpp' in record['native_translation_units']
    assert 'third_party/dawn/src/dawn/common/MemoryBlockAllocator.cpp' in record['native_translation_units']
    fixture = (MODULE / 'command_iterator_test.cc').read_text(encoding='utf-8-sig')
    assert '#include "src/dawn/native/CommandAllocator.h"' in fixture
    assert 'class CommandIterator' not in fixture and '#define DAWN_CHECK' not in fixture


def test_native_iterator_pool_and_reference_counting_execute_in_both_modes():
    proof = observation()['public_checker_observation']
    assert proof['passed'] and proof['measurement_complete'] and proof['postguards_passed']
    assert {row['sanitizer'] for row in proof['runs']} == {'none', 'address'}
    for row in proof['runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        result = row['result']
        assert result['passed'] and result['position_cases'] == 182
        assert result['checks'] == 1064016 and result['destroyed'] == 9284
        assert result['bundle_like_cases'] == result['pool_reuse_cases'] == result['merged_block_cases'] == 1
        assert result['native_command_iterator_executed'] and result['native_memory_pool_executed']
        assert result['standalone_noop_raw_ptr'] and result['actual_native_device_queue_executed'] is False
        assert {case['case'] for case in row['ownership_refusals']} == {'destroy', 'move'}
        assert all(case['passed'] and case['native_restore_guard_observed']
                   and case['returncode'] not in (0, 98, 99) for case in row['ownership_refusals'])


def test_native_iterator_proof_does_not_claim_chromium_allocator_or_render_execution():
    record = observation()
    assert record['standalone_noop_raw_ptr']
    for proof in (record, record['public_checker_observation']):
        for key in ('chromium_miracle_ptr_executed', 'actual_native_device_queue_executed',
                    'actual_native_render_bundle_decoder_executed', 'runtime_verified',
                    'privacy_admitted', 'production_admitted'):
            assert proof[key] is False


def test_native_iterator_changed_inputs_are_refused_before_all_compilation():
    proof = observation()['changed_input_refusal']
    assert proof['passed']
    assert {row['case'] for row in proof['cases']} == {
        'fixture', 'checker', 'source-gate-checker', 'source-gate-record',
        'native-source-hash', 'native-header-hash', 'native-unit-unpinned', 'source-gate-packet',
    }
    assert all(row['passed'] and row['returncode'] in (1, 2) and row['expected_error_observed']
               and row['refused_before_native_compilation'] and row['refused_before_all_compilation']
               for row in proof['cases'])
