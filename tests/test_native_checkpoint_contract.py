import copy
import hashlib
from pathlib import Path

import pytest

from scripts import native_checkpoint_contract as contract


@pytest.fixture
def prepared(tmp_path):
    # Protocol validation only: this synthetic C++ source is never compiled.
    source = tmp_path / 'source'
    fixture = source / contract.BROWSER_TEST_SOURCE
    fixture.parent.mkdir(parents=True)
    names = [contract.CRASH_PRE_CASE, contract.CRASH_POST_CASE, 'OrdinaryCase']
    fixture.write_text('\n'.join(
        'IN_PROC_BROWSER_TEST_F(' + contract.CRASH_SUITE + ', ' + name + ') {}'
        for name in names), encoding='utf-8')
    cases = [dict(binary='browser_tests', source=contract.BROWSER_TEST_SOURCE,
        kind='IN_PROC_BROWSER_TEST_F', fixture=contract.CRASH_SUITE, case=name) for name in names]
    plan = dict(cases=cases, binaries=['browser_tests'], native_case_bodies_prepared=len(cases),
        browser_execution=dict(schema=1, mode='source-bound-acknowledged-crash-v1',
            binary='browser_tests', source=contract.BROWSER_TEST_SOURCE,
            source_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
            expected_termination_case=contract.CRASH_SUITE + '.' + contract.CRASH_PRE_CASE,
            recovery_case=contract.CRASH_SUITE + '.' + contract.CRASH_POST_CASE,
            ordinary_pre_chains_require_fresh_shared_profiles=True,
            maximum_crash_phase_seconds=300, forced_phase_is_gtest_pass=False))
    return source, fixture, plan


def test_fixture_bytes_match_the_explicit_protocol_plan(prepared):
    source, fixture, plan = prepared
    result = contract.validate_browser_contract(source, plan)
    assert result == {str(fixture): hashlib.sha256(fixture.read_bytes()).hexdigest()}
    assert result[str(fixture)] == plan['browser_execution']['source_sha256']


@pytest.mark.parametrize('key,value', [
    ('schema', True), ('schema', 2), ('mode', 'ordinary-pre'), ('binary', 'net_unittests'),
    ('source', '../foreign.cc'), ('source_sha256', '0' * 63),
    ('source_sha256', 'F' * 64), ('expected_termination_case', 'Foreign.PRE_Crash'),
    ('recovery_case', 'Foreign.Recovery'), ('ordinary_pre_chains_require_fresh_shared_profiles', False),
    ('maximum_crash_phase_seconds', True), ('maximum_crash_phase_seconds', 301),
    ('forced_phase_is_gtest_pass', True), ('forced_phase_is_gtest_pass', 0),
])
def test_contract_fields_are_exact_not_truthy_or_guessed(prepared, key, value):
    source, _, plan = prepared
    plan['browser_execution'][key] = value
    with pytest.raises(ValueError, match='contract'):
        contract.validate_browser_contract(source, plan)


@pytest.mark.parametrize('mutation', ['missing', 'unknown', 'absent'])
def test_contract_is_explicit_and_versioned(prepared, mutation):
    source, _, plan = prepared
    if mutation == 'missing':
        del plan['browser_execution']['source_sha256']
    elif mutation == 'unknown':
        plan['browser_execution']['unknown_field'] = True
    else:
        del plan['browser_execution']
    with pytest.raises(ValueError):
        contract.validate_browser_contract(source, plan)


def test_modified_source_rejects_even_when_case_names_still_match(prepared):
    source, fixture, plan = prepared
    fixture.write_bytes(fixture.read_bytes() + b'\n// modified\n')
    with pytest.raises(ValueError, match='hash'):
        contract.validate_browser_contract(source, plan)


def test_duplicate_source_body_rejects_even_after_hash_is_updated(prepared):
    source, fixture, plan = prepared
    fixture.write_bytes(fixture.read_bytes() +
        b'\nIN_PROC_BROWSER_TEST_F(GlintCookiePrefixBrowserTest, CrashAfterAcknowledgedPrefix) {}\n')
    plan['browser_execution']['source_sha256'] = hashlib.sha256(fixture.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='duplicated'):
        contract.validate_browser_contract(source, plan)


@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'order', 'kind', 'binary'])
def test_declared_fixture_must_match_every_actual_body_in_source_order(prepared, mutation):
    source, _, plan = prepared
    rows = [row for row in plan['cases'] if row['source'] == contract.BROWSER_TEST_SOURCE]
    if mutation == 'missing':
        plan['cases'].remove(rows[0])
    elif mutation == 'duplicate':
        plan['cases'].append(copy.deepcopy(rows[0]))
    elif mutation == 'order':
        first, second = [plan['cases'].index(row) for row in rows[:2]]
        plan['cases'][first], plan['cases'][second] = plan['cases'][second], plan['cases'][first]
    elif mutation == 'kind':
        rows[0]['kind'] = 'TEST_F'
    else:
        rows[0]['binary'] = 'net_unittests'
    plan['native_case_bodies_prepared'] = len(plan['cases'])
    with pytest.raises(ValueError):
        contract.validate_browser_contract(source, plan)


def test_oversized_fixture_rejects_before_parsing(prepared):
    source, fixture, plan = prepared
    fixture.write_bytes(b' ' * (contract.MAX_FIXTURE_BYTES + 1))
    with pytest.raises(ValueError, match='bounded'):
        contract.validate_browser_contract(source, plan)


def test_relative_source_root_is_never_resolved_as_a_fallback(prepared):
    _, _, plan = prepared
    with pytest.raises(ValueError, match='canonical'):
        contract.validate_browser_contract(Path('relative-source'), plan)


@pytest.mark.parametrize('value', [True, 299, '300'])
def test_native_case_count_must_be_an_exact_integer(prepared, value):
    source, _, plan = prepared
    plan['native_case_bodies_prepared'] = value
    with pytest.raises(ValueError, match='case plan'):
        contract.validate_browser_contract(source, plan)
