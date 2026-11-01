from pathlib import Path
import hashlib
import json
import runpy

import pytest


TOOL = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'native/drafts/resources/build_actions.py'))


@pytest.mark.parametrize('image,arguments,expected', [
    ('lld-link.exe', ['/lib', '/OUT:foo.lib'], 'archive'),
    ('C:\\llvm\\LLD-LINK.EXE', ['/LIB', '/OUT:foo.lib'], 'archive'),
    ('lld-link.exe', ['/libpath:x', '/OUT:foo.exe'], 'link'),
    ('lld-link.exe', ['@response.rsp'], 'link-unclassified'),
    ('lld-link.exe', None, 'unavailable'),
    ('clang-cl.exe', ['/c', 'file.cc'], 'compiler-driver'),
    ('clang-cl.exe', ['-cc1', 'file.cc'], 'compiler-frontend'),
    ('clang-cl.exe', ['-cc1as'], 'compiler-frontend'),
    ('clang-cl.exe', ['@response.rsp'], 'compiler-unclassified'),
    ('python.exe', ['build.py'], 'other'),
])
def test_build_action_classification_does_not_equate_process_names_with_link_actions(image, arguments, expected):
    assert TOOL['classify_process'](image, arguments) == expected


@pytest.mark.parametrize('arguments', [(), [1], ['bad\0argument'], ['x' * 32769]])
def test_build_action_arguments_are_bounded_and_explicit(arguments):
    with pytest.raises(ValueError, match='bounded'):
        TOOL['classify_process']('lld-link.exe', arguments)


def test_ninja_rule_inspection_keeps_archive_and_runtime_boundaries(tmp_path):
    (tmp_path / 'build.ninja').write_text('pool link_pool\n  depth = 1\nbuild foo: phony\n', encoding='utf-8')
    (tmp_path / 'toolchain.ninja').write_text(
        'rule link\n  pool = link_pool\nrule solink\n  pool = link_pool\nrule alink\n'
        '  command = lld-link.exe /lib\nbuild x: alink\n' + 'x' * 3_000_000, encoding='utf-8')
    result = TOOL['inspect'](tmp_path)
    assert result['configured_executable_and_dll_link_pool_depth_one']
    assert result['archive_pool'] is None
    assert result['toolchain_configuration']['captured_bytes'] > 3_000_000
    assert result['toolchain_configuration']['maximum_line_buffer_bytes'] == 65536
    assert result['toolchain_configuration']['whole_file_hashed']
    for name in ('runtime_scheduling_verified', 'historical_two_linker_cause_confirmed',
                 'raw_lld_process_count_is_heavy_link_count', 'build_modified', 'production_admitted'):
        assert result[name] is False


@pytest.mark.parametrize('content', ['pool p\n  depth = 0\n', 'pool p\npool p\n',
                                     'rule link\n  pool = $variable\n'], ids=['zero-depth', 'duplicate-pool', 'variable-pool'])
def test_ninja_configuration_rejects_ambiguous_pool_configuration(tmp_path, content):
    path = tmp_path / 'toolchain.ninja'
    path.write_text(content, encoding='utf-8')
    with pytest.raises(ValueError):
        TOOL['read_configuration'](path)


def test_ninja_configuration_rejects_files_over_bound(tmp_path, monkeypatch):
    monkeypatch.setitem(TOOL['read_configuration'].__globals__, 'MAX_FILE_BYTES', 128)
    path = tmp_path / 'toolchain.ninja'
    path.write_bytes(b'x' * 129)
    with pytest.raises(ValueError, match='bound'):
        TOOL['read_configuration'](path)


def test_ninja_configuration_reads_definitions_after_interleaved_edges(tmp_path):
    path = tmp_path / 'toolchain.ninja'
    path.write_text('rule link\n  pool = links\nbuild x: link\nrule solink\n  pool = links\n'
                    'pool links\n  depth = 1\n', encoding='utf-8')
    result = TOOL['read_configuration'](path)
    assert result['rules'] == {'link': 'links', 'solink': 'links'}
    assert result['pools'] == {'links': 1}


def test_ninja_configuration_does_not_split_utf8_at_its_line_buffer_boundary(tmp_path):
    path = tmp_path / 'toolchain.ninja'
    path.write_text('build long:' + '\u044f' * 40000 + '\nrule link\n  pool = links\n', encoding='utf-8')
    assert TOOL['read_configuration'](path)['rules'] == {'link': 'links'}


def test_r8_build_rule_evidence_is_configuration_not_historical_action_attribution():
    packet = Path(__file__).resolve().parents[1] / 'native/drafts/resources'
    record = json.loads((packet / 'r8-build-rule-observations.json').read_bytes())
    assert record['tool_sha256'] == hashlib.sha256((packet / 'build_actions.py').read_bytes()).hexdigest()
    assert record['configured_executable_and_dll_link_pool_depth_one']
    assert set(record['executable_and_dll_pools'].values()) == {'build_toolchain_link_pool'}
    assert record['archive_pool'] is None and record['archive_rule_uses_lld_link_lib']
    assert record['historical_observer_counts'] == dict(lld_link_processes=2, clang_cl_processes=5,
                                                       command_lines_captured=False)
    assert record['root_configuration']['whole_file_hashed'] and record['toolchain_configuration']['whole_file_hashed']
    for name in ('runtime_scheduling_verified', 'historical_two_linker_cause_confirmed',
                 'raw_lld_process_count_is_heavy_link_count', 'build_modified', 'production_admitted'):
        assert record[name] is False
