import copy
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts import native_incremental as incremental


ROOT = Path(__file__).resolve().parents[1]


def stage_identity(manifest='a' * 64, stage='hooks'):
    return dict(schema=1, stage=stage, platform='win32', chromium_revision='a' * 40,
        depot_tools_revision='b' * 40, candidate_manifest_sha256=manifest, deps_sha256='c' * 64,
        gclient_sha256='d' * 64, dependency_snapshots_sha256={
            'camouflow-git-revisions.json': 'e' * 64, 'camouflow-cipd-installed.json': 'f' * 64})


def test_actual_74_append_is_only_five_supported_cpp_files():
    before = json.loads((ROOT / 'native/drafts/upstream-156/checkpoints/001-073.json').read_bytes())
    after = json.loads((ROOT / 'native/drafts/upstream-156/checkpoints/001-074.json').read_bytes())
    delta = incremental.appended_patches(before, after)
    assert len(delta) == 1
    patch = ROOT / 'native/drafts/upstream-156/patches' / delta[0]['file']
    assert len(incremental.changed_paths([patch.read_text(encoding='utf-8')])) == 5


@pytest.mark.parametrize('fault', ['revision', 'prefix', 'no-append', 'settings'])
def test_non_equivalent_manifest_is_rejected(fault):
    before = {'target_revision': 'fixed', 'patches': [{'file': 'first'}], 'settings': {'sdk': 'fixed'}}
    after = copy.deepcopy(before)
    after['patches'].append({'file': 'next'})
    if fault == 'revision':
        after['target_revision'] = 'other'
    elif fault == 'prefix':
        after['patches'][0]['file'] = 'modified'
    elif fault == 'no-append':
        after = before
    else:
        after['settings']['sdk'] = 'other'
    with pytest.raises(ValueError):
        incremental.appended_patches(before, after)


@pytest.mark.parametrize('line', ['new file mode 100644', 'deleted file mode 100644', 'rename from x',
    'GIT binary patch', 'diff --git a/DEPS b/DEPS', 'diff --git a/build/args.gn b/build/args.gn',
    'diff --git a/../x.cc b/../x.cc', 'diff --git a/content/browser/renderer_host/a.cc b/content/browser/renderer_host/b.cc'])
def test_dependency_new_or_renamed_paths_are_rejected(line):
    with pytest.raises(ValueError):
        incremental.changed_paths([line])


def test_only_candidate_hash_may_differ_in_completed_stage_identity():
    before = stage_identity()
    after = {**before, 'candidate_manifest_sha256': 'b' * 64}
    assert incremental.dependencies_equivalent(before, after)
    assert not incremental.dependencies_equivalent(before, {**after, 'deps_sha256': 'e' * 64})
    with pytest.raises(ValueError):
        incremental.dependencies_equivalent({'candidate_manifest_sha256': 'a' * 64}, after)


@pytest.mark.parametrize('field,value', [('free_bytes', 63 * 1024**3), ('source_bytes', 17 * 1024**2),
    ('planned_steps', 257), ('valid_cache', False), ('matching_toolchain', False), ('matching_args', False),
    ('preserved_runtime_verified', False), ('planned_steps', True)])
def test_cached_budget_cannot_skip_any_admission_guard(field, value):
    values = dict(free_bytes=100 * 1024**3, source_bytes=1024, planned_steps=50, valid_cache=True,
                  matching_toolchain=True, matching_args=True, preserved_runtime_verified=True)
    values[field] = value
    with pytest.raises(ValueError):
        incremental.require_capacity(**values)


def test_capacity_alone_never_authorizes_execution_or_changes_full_build_reserve():
    result = incremental.require_capacity(free_bytes=100 * 1024**3, source_bytes=1024, planned_steps=50,
        valid_cache=True, matching_toolchain=True, matching_args=True, preserved_runtime_verified=True)
    assert result['execution_authorized'] is False
    assert incremental.build.LOCK['minimum_free_gib'] == 180


@pytest.mark.parametrize('text,expected', [('ninja: no work to do.\n5m44.79s Build Succeeded: 0 steps - 0.00/s\n', 0),
    ('compile a\ncompile b\n17.63s Build Succeeded: 2 steps - 0.45/s\n', 2)])
def test_siso_plan_requires_its_actual_success_summary(text, expected):
    assert incremental.siso_steps(text) == expected


@pytest.mark.parametrize('text', ['', '[1/2] CXX x', '[1/1] GEN x\n[1/2] CXX a\n[2/2] LINK b',
    '1s Build Succeeded: 0 steps - 0.00/s',
    'ninja: no work to do.\n1s Build Succeeded: 2 steps - 0.45/s',
    '1s Build Succeeded: 2 steps - 0.45/s\n1s Build Succeeded: 2 steps - 0.45/s'])
def test_missing_or_ambiguous_siso_plan_is_rejected(text):
    with pytest.raises(ValueError):
        incremental.siso_steps(text)


def test_dirty_frontier_includes_downstream_links_but_not_unrequested_targets():
    rows = [dict(output='object', rule='cxx', command='compile', inputs=['source']),
            dict(output='library', rule='link', inputs=['object'], extra_outputs=['import.lib']),
            dict(output='requested.exe', rule='link', inputs=['import.lib']),
            dict(output='requested', rule='phony', inputs=['requested.exe']),
            dict(output='other.exe', rule='link', inputs=['object'])]
    assert incremental.affected_steps(rows, ['requested'], 'compile', 1) == 3


@pytest.mark.parametrize('fault', ['missing-command', 'missing-target', 'duplicate-node', 'duplicate-alias', 'malformed'])
def test_incomplete_or_ambiguous_graph_is_rejected(fault):
    rows = [dict(output='object', rule='cxx', command='compile', inputs=['source']),
            dict(output='requested', rule='link', inputs=['object'])]
    if fault == 'duplicate-node':
        rows.append(rows[0])
    elif fault == 'duplicate-alias':
        rows[0]['extra_outputs'] = ['requested']
    elif fault == 'malformed':
        rows[0]['inputs'] = 'source'
    with pytest.raises(ValueError):
        incremental.affected_steps(rows, ['absent' if fault == 'missing-target' else 'requested'],
                                   'unbound' if fault == 'missing-command' else 'compile', 1)


@pytest.fixture
def cache(tmp_path, monkeypatch):
    repository = tmp_path / 'repo'
    (repository / 'native').mkdir(parents=True)
    args = (ROOT / 'native/args.gn').read_bytes()
    (repository / 'native/args.gn').write_bytes(args)
    output = tmp_path / 'cache'
    output.mkdir()
    for name in ('.ninja_log', '.siso_deps', '.siso_fs_state', 'build.ninja', 'chrome.exe'):
        (output / name).write_bytes(b'owned')
    (output / '.siso_config').write_text(json.dumps({'properties': {
        'gn_logs:use_siso': 'true', 'gn_args:use_remoteexec': 'false'}}), encoding='utf-8')
    (output / 'args.gn').write_bytes(args)
    monkeypatch.setattr(incremental, 'ROOT', repository)
    return output, {'args_sha256': hashlib.sha256(args).hexdigest()}, repository


def test_existing_cache_is_not_replaced_or_cleaned(cache):
    output, receipt, _ = cache
    assert incremental.eligible_cache(output, ['chrome'], receipt) == (output / 'args.gn').read_bytes()


def test_siso_dependency_cache_does_not_depend_on_ninja_timing_log(cache):
    output, receipt, _ = cache
    (output / '.ninja_log').unlink()
    assert incremental.eligible_cache(output, ['chrome'], receipt) == (output / 'args.gn').read_bytes()


@pytest.mark.parametrize('fault', ['missing-deps', 'args-changed', 'debug', 'symbols', 'mixed-cache', 'remote'])
def test_incomplete_or_changed_cache_requires_full_policy(cache, fault):
    output, receipt, repository = cache
    if fault == 'missing-deps':
        (output / '.siso_deps').unlink()
    elif fault == 'mixed-cache':
        (output / '.ninja_deps').write_bytes(b'foreign')
    elif fault == 'remote':
        (output / '.siso_config').write_text(json.dumps({'properties': {
            'gn_logs:use_siso': 'true', 'gn_args:use_remoteexec': 'true'}}), encoding='utf-8')
    elif fault == 'args-changed':
        (output / 'args.gn').write_bytes(b'other')
    else:
        text = (output / 'args.gn').read_text(encoding='utf-8-sig')
        text = text.replace('is_debug = false', 'is_debug = true') if fault == 'debug' else text.replace('symbol_level = 0', 'symbol_level = 2')
        (output / 'args.gn').write_text(text, encoding='utf-8', newline='\n')
        (repository / 'native/args.gn').write_text(text, encoding='utf-8', newline='\n')
        receipt['args_sha256'] = incremental.digest(output / 'args.gn')
    with pytest.raises(ValueError):
        incremental.eligible_cache(output, ['chrome'], receipt)


@pytest.mark.parametrize('fault', ['none', 'foreign-source', 'corrupt-backup'])
def test_rollback_restores_only_owned_bytes_and_valid_backup(tmp_path, fault):
    source = tmp_path / 'source'
    source.mkdir()
    target = source / 'owned.cc'
    target.write_bytes(b'owned-change')
    backup = tmp_path / 'before.cc'
    backup.write_bytes(b'before')
    rows = {'owned.cc': dict(backup=str(backup), before_sha256=incremental.digest(backup),
                            owned_after_sha256=incremental.digest(target))}
    if fault == 'foreign-source':
        target.write_bytes(b'foreign')
    elif fault == 'corrupt-backup':
        backup.write_bytes(b'corrupt')
    errors = incremental.restore_sources(source, rows)
    if fault == 'none':
        assert not errors and target.read_bytes() == b'before'
    else:
        assert errors and target.read_bytes() == (b'foreign' if fault == 'foreign-source' else b'owned-change')


def test_record_rollback_preserves_exact_bom_and_crlf_bytes(tmp_path):
    original = b'\xef\xbb\xbf{\r\n  "stage": "hooks"\r\n}\r\n'
    backup = tmp_path / 'backup.json'
    backup.write_bytes(original)
    target = tmp_path / 'hooks.json'
    target.write_bytes(b'{"stage": "updated"}\n')
    row = dict(backup=str(backup), before_sha256=incremental.digest(backup),
               owned_after_sha256=incremental.digest(target))
    assert incremental.restore_sources(tmp_path, {'hooks.json': row}) == []
    assert target.read_bytes() == original


@pytest.mark.parametrize('fault', ['none', 'tamper', 'escape', 'malformed', 'omitted-code', 'omitted-receipt'])
def test_preserved_runtime_inventory_is_measured(tmp_path, fault):
    runtime = tmp_path / 'preserved/runtime'
    runtime.mkdir(parents=True)
    receipt = b'{"baseline": true}'
    (runtime / 'camouflow-build.json').write_bytes(receipt)
    for name in ('chrome.exe', 'chrome.dll', 'chrome_elf.dll', 'args.gn'):
        (runtime / name).write_bytes(b'baseline')
    core = {name: incremental.digest(runtime / name) for name in ('chrome.exe', 'chrome.dll', 'chrome_elf.dll')}
    assets = {item.name: incremental.digest(item) for item in runtime.iterdir()}
    if fault == 'escape':
        assets['../outside'] = 'a' * 64
    elif fault == 'malformed':
        assets['chrome.exe'] = None
    elif fault == 'omitted-code':
        del assets['chrome.dll']
    elif fault == 'omitted-receipt':
        del assets['camouflow-build.json']
    record = dict(passed=True, postguards_passed=True, runtime_core_sha256_measured=core,
                  measured_assets_sha256=assets)
    incremental.write_report(runtime.parent / 'report.json', record)
    if fault == 'tamper':
        (runtime / 'chrome.exe').write_bytes(b'changed')
    if fault == 'none':
        assert incremental.verify_preserved(runtime, receipt, core) == assets
    else:
        with pytest.raises(ValueError):
            incremental.verify_preserved(runtime, receipt, core)


@pytest.fixture
def execution(tmp_path, monkeypatch):
    assert tmp_path.drive.upper() == 'D:'
    workspace = tmp_path / 'workspace'
    source = workspace / 'chromium/src'
    output = source / 'out/CamouFlowNative'
    output.mkdir(parents=True)
    preserved = tmp_path / 'preserved/runtime'
    preserved.mkdir(parents=True)
    report = tmp_path / 'report'
    candidate = incremental.build.load_candidate('upstream-156')
    checkpoint = candidate['directory'] / 'checkpoints/001-073.json'
    baseline_hash = incremental.digest(checkpoint)
    receipt = dict(local_windows_toolchain_sha256='sdk', runtime_core_sha256_measured={'core': 'old'})
    (output / 'camouflow-build.json').write_text(json.dumps(receipt), encoding='utf-8')
    (output / 'args.gn').write_bytes(b'args')
    name = 'third_party/blink/renderer/core/example.cc'
    file = source / name
    file.parent.mkdir(parents=True)
    file.write_bytes(b'before')
    stages = {}
    for stage in ('sync', 'hooks'):
        stages[stage] = workspace / (stage + '.json')
        stages[stage].write_text('before', encoding='utf-8')
    build = incremental.build
    monkeypatch.setattr(incremental, 'changed_paths', lambda _: [name])
    monkeypatch.setattr(build, 'preflight', lambda *a, **k: {'passed': True})
    monkeypatch.setattr(build, 'candidate_workspace', lambda *a: None)
    monkeypatch.setattr(build, 'workspace_lock', lambda *a: nullcontext())
    monkeypatch.setattr(incremental.units, 'require_idle_builder', lambda *a: None)
    monkeypatch.setattr(incremental.units, 'verification_environment', lambda *a: {'GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256': 'sdk'})
    monkeypatch.setattr(build, 'local_windows_toolchain', lambda *a: {'GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256': 'sdk'})
    monkeypatch.setattr(incremental, 'validate_build_receipt', lambda *a, **k: None)
    monkeypatch.setattr(incremental, 'verify_preserved', lambda *a: {'asset': 'hash'})
    monkeypatch.setattr(incremental, 'eligible_cache', lambda *a: b'args')
    monkeypatch.setattr(incremental, 'require_capacity', lambda **k: {})
    monkeypatch.setattr(incremental.batch, 'source_inputs', lambda *a: {checkpoint})
    monkeypatch.setattr(incremental, 'baseline_chain', lambda *a: None)
    monkeypatch.setattr(build, 'measure_runtime_core', lambda *a: {'core': 'old'})
    monkeypatch.setattr(build, 'require_stage', lambda *a: None)
    monkeypatch.setattr(build, 'stage_identity', lambda _, stage, selected: stage_identity(selected['manifest_sha256'], stage))
    monkeypatch.setattr(build, 'stage_path', lambda _, stage: stages[stage])
    monkeypatch.setattr(build, 'record_stage', lambda _, stage, selected: stages[stage].write_text('owned', encoding='utf-8'))
    monkeypatch.setattr(build, 'candidate_source_patches', lambda *a: None)
    monkeypatch.setattr(build, 'check_patch_dependencies', lambda *a: None)
    monkeypatch.setattr(build, 'depot_command', lambda *a: ['cached-tool'])
    def run(command, *args, **kwargs):
        if command[:3] == ['git', 'rev-parse', 'HEAD']:
            return candidate['lock']['depot_tools_revision']
        if command[:2] == ['git', 'apply'] and '--check' not in command:
            file.write_bytes(b'owned')
        return ''
    monkeypatch.setattr(build, 'run', run)
    state = SimpleNamespace(plan_calls=0, failure=None)
    def subprocess_run(command, **kwargs):
        if '-n' in command:
            state.plan_calls += 1
            return SimpleNamespace(stdout='ninja: no work to do.\n1s Build Succeeded: 0 steps - 0.00/s\n', stderr='')
        if state.failure is not None:
            raise state.failure
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(incremental.subprocess, 'run', subprocess_run)
    monkeypatch.setattr(incremental.batch, '_verify_locked', lambda *a, **k:
        dict(passed=True, postguards_passed=True, targets=[{'tests': 494}]))
    return SimpleNamespace(workspace=workspace, report=report, preserved=preserved,
                           file=file, stages=stages, state=state, baseline_hash=baseline_hash)


def invoke(execution, action):
    return incremental.execute(action, execution.workspace, execution.report, execution.preserved, '001-073')


def test_plan_never_changes_sources_or_dependency_stages(execution):
    result = invoke(execution, 'plan')
    assert result['passed'] and not result['compilation_started']
    assert execution.file.read_bytes() == b'before'
    assert all(path.read_text() == 'before' for path in execution.stages.values())


def test_precompile_failure_restores_owned_sources_and_stages(execution, monkeypatch):
    def fail(*args):
        raise ValueError('dependency verification failed')
    monkeypatch.setattr(incremental.build, 'check_patch_dependencies', fail)
    with pytest.raises(ValueError, match='dependency verification failed'):
        invoke(execution, 'rebuild')
    result = json.loads((execution.report / 'report.json').read_bytes())
    assert result['measurement_complete'] and not result['compilation_started'] and not result['rollback_errors']
    assert execution.file.read_bytes() == b'before'
    assert all(path.read_text() == 'before' for path in execution.stages.values())


def test_interrupted_build_resumes_same_transaction(execution):
    execution.state.failure = OSError('controller interrupted')
    with pytest.raises(OSError, match='controller interrupted'):
        invoke(execution, 'rebuild')
    result = json.loads((execution.report / 'report.json').read_bytes())
    assert result['compilation_started'] and not result['measurement_complete']
    assert execution.file.read_bytes() == b'owned'
    execution.state.failure = None
    result = invoke(execution, 'resume')
    assert result['passed'] and result['build_attempts'] == 2 and result['native_tests'] == 494


def test_terminal_compiler_failure_is_not_an_interruption(execution):
    execution.state.failure = subprocess.CalledProcessError(1, ['compiler'])
    with pytest.raises(subprocess.CalledProcessError):
        invoke(execution, 'rebuild')
    result = json.loads((execution.report / 'report.json').read_bytes())
    assert result['measurement_complete'] and not result['passed']
    with pytest.raises(ValueError, match='same interrupted compilation'):
        invoke(execution, 'resume')


def test_foreign_dependency_record_is_retained_on_rollback(execution, monkeypatch):
    def fail(*args):
        execution.stages['sync'].write_bytes(b'foreign-stage')
        raise ValueError('dependency verification failed')
    monkeypatch.setattr(incremental.build, 'check_patch_dependencies', fail)
    with pytest.raises(ValueError, match='dependency verification failed'):
        invoke(execution, 'rebuild')
    result = json.loads((execution.report / 'report.json').read_bytes())
    assert execution.stages['sync'].read_bytes() == b'foreign-stage'
    assert result['rollback_errors'] and execution.file.read_bytes() == b'before'


def test_native_verification_exception_does_not_restart_completed_compilation(execution, monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError('native postguard failed')
    monkeypatch.setattr(incremental.batch, '_verify_locked', fail)
    with pytest.raises(ValueError, match='native postguard failed'):
        invoke(execution, 'rebuild')
    result = json.loads((execution.report / 'report.json').read_bytes())
    assert result['build_completed'] and not result['passed']
    with pytest.raises(ValueError, match='same interrupted compilation'):
        invoke(execution, 'resume')


def test_precompile_rollback_retains_exact_dependency_record_bytes(execution, monkeypatch):
    original = b'\xef\xbb\xbf{\r\n  "stage": "baseline"\r\n}\r\n'
    for path in execution.stages.values():
        path.write_bytes(original)
    def fail(*args):
        raise ValueError('dependency verification failed')
    monkeypatch.setattr(incremental.build, 'check_patch_dependencies', fail)
    with pytest.raises(ValueError, match='dependency verification failed'):
        invoke(execution, 'rebuild')
    result = json.loads((execution.report / 'report.json').read_bytes())
    assert not result['rollback_errors']
    assert all(path.read_bytes() == original for path in execution.stages.values())
