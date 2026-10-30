"""Bounded Windows cached C++ rebuild; no sync, download or clean-build fallback."""

from pathlib import PurePosixPath
import re
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import native_build as build
from scripts import verify_native_privacy_batch as batch
from scripts import verify_native_privacy_units as units
from scripts.package_native_windows import read_record, validate_build_receipt


MINIMUM_FREE_GIB = 64
MAX_PATCHES = 4
MAX_FILES = 16
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_BUILD_STEPS = 256
PREFIXES = ('content/browser/renderer_host/', 'third_party/blink/renderer/')
DEVTOOLS_CAPTURE_FILES = frozenset({
    'content/browser/devtools/protocol/emulation_handler.cc',
    'content/browser/devtools/protocol/emulation_handler.h',
    'content/browser/devtools/protocol/page_handler.cc',
    'content/browser/devtools/protocol/page_handler.h',
    'content/browser/devtools/devtools_agent_host_impl_unittest.cc',
})


def appended_patches(before, after):
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ValueError('Both pinned manifests are required')
    baseline, selected = before.get('patches'), after.get('patches')
    if (not isinstance(baseline, list) or not baseline or not isinstance(selected, list)
            or selected[:len(baseline)] != baseline
            or not 1 <= len(selected) - len(baseline) <= MAX_PATCHES):
        raise ValueError('Only a bounded exact patch-prefix append is eligible')
    if {k: v for k, v in before.items() if k != 'patches'} != {k: v for k, v in after.items() if k != 'patches'}:
        raise ValueError('Revision, dependency or candidate settings changed')
    return selected[len(baseline):]


def changed_paths(contents):
    if not isinstance(contents, list) or not 1 <= len(contents) <= MAX_PATCHES:
        raise ValueError('A bounded set of textual patches is required')
    paths = set()
    forbidden = ('new file mode ', 'deleted file mode ', 'rename from ', 'rename to ',
                 'copy from ', 'copy to ', 'GIT binary patch', 'Binary files ', 'old mode ', 'new mode ')
    for text in contents:
        if not isinstance(text, str) or '\x00' in text:
            raise ValueError('Patch must be text')
        count = 0
        for line in text.splitlines():
            if line.startswith(forbidden):
                raise ValueError('No new, deleted, renamed, linked or binary paths')
            if line.startswith('diff --git '):
                match = re.fullmatch(r'diff --git a/([^\s]+) b/([^\s]+)', line)
                if not match or match[1] != match[2]:
                    raise ValueError('Only ordinary same-path source edits are eligible')
                path = PurePosixPath(match[1])
                if (path.is_absolute() or '..' in path.parts or '\\' in match[1]
                        or path.suffix not in ('.cc', '.h')
                        or not (match[1].startswith(PREFIXES) or match[1] in DEVTOOLS_CAPTURE_FILES)):
                    raise ValueError('Patch changes dependency/build inputs or unsupported source paths')
                count += 1
                paths.add(path.as_posix())
        if not count:
            raise ValueError('No source changes were found')
    if len(paths) > MAX_FILES:
        raise ValueError('Changed source set is too large for the cached mode')
    return sorted(paths)


def dependencies_equivalent(previous, current):
    keys = {'schema', 'stage', 'platform', 'chromium_revision', 'depot_tools_revision',
            'candidate_manifest_sha256', 'deps_sha256', 'gclient_sha256', 'dependency_snapshots_sha256'}
    for value in (previous, current):
        if (not isinstance(value, dict) or set(value) != keys or type(value['schema']) is not int
                or value['schema'] != 1 or value['stage'] not in ('sync', 'hooks') or value['platform'] != 'win32'):
            raise ValueError('Complete Windows dependency-stage identities are required')
        for key, width in (('chromium_revision', 40), ('depot_tools_revision', 40),
                           ('candidate_manifest_sha256', 64), ('deps_sha256', 64), ('gclient_sha256', 64)):
            if not isinstance(value[key], str) or re.fullmatch('[0-9a-f]{' + str(width) + '}', value[key]) is None:
                raise ValueError('Stage identity has malformed pinned digests')
        snapshots = value['dependency_snapshots_sha256']
        if (not isinstance(snapshots, dict) or set(snapshots) != {'camouflow-git-revisions.json', 'camouflow-cipd-installed.json'}
                or any(not isinstance(item, str) or re.fullmatch('[0-9a-f]{64}', item) is None for item in snapshots.values())):
            raise ValueError('Both measured dependency inventories are required')
    return all(previous[key] == current[key] for key in previous if key != 'candidate_manifest_sha256')


def require_capacity(*, free_bytes, source_bytes, planned_steps, valid_cache, matching_toolchain,
                     matching_args, preserved_runtime_verified):
    values = (free_bytes, source_bytes, planned_steps)
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError('Capacity measurements must be non-negative integers')
    if any(value is not True for value in (valid_cache, matching_toolchain, matching_args, preserved_runtime_verified)):
        raise ValueError('Cached mode requires all existing-cache, toolchain, args and rollback guards')
    if free_bytes < MINIMUM_FREE_GIB * 1024**3:
        raise ValueError('Cached rebuild reserve is insufficient')
    if source_bytes > MAX_SOURCE_BYTES or planned_steps > MAX_BUILD_STEPS:
        raise ValueError('Work exceeds the bounded cached mode; full build remains required')
    return {'mode': 'bounded-cached', 'reserve_gib': MINIMUM_FREE_GIB,
            'planned_steps': planned_steps, 'execution_authorized': False}


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def siso_steps(output: str) -> int:
    summaries = re.findall(r'^[ \t]*\d+(?:\.\d+)?(?:ms|s|m[\d.]+s|h[\dm.s]+) Build Succeeded: (\d+) steps - [\d.]+/s\s*$',
                           output, re.MULTILINE)
    if len(summaries) != 1 or 'Build Failed' in output:
        raise ValueError('Siso plan did not provide one successful work summary')
    total = int(summaries[0])
    if ('ninja: no work to do.' in output) != (total == 0):
        raise ValueError('Siso no-work marker and work summary disagree')
    return total


def affected_steps(records, targets, planned_output: str, frontier: int) -> int:
    """Count conservative downstream commands; Siso -n prints only the dirty frontier."""
    nodes, aliases, seeds = {}, {}, set()
    commands = set(planned_output.splitlines())
    for row in records:
        name, rule = row.get('output'), row.get('rule')
        if not isinstance(name, str) or not name or not isinstance(rule, str) or name in nodes:
            raise ValueError('Malformed or duplicate Siso graph node')
        inputs = []
        for key in ('inputs', 'implicit_inputs', 'order_only_inputs', 'extra_outputs'):
            values = row.get(key, [])
            if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values):
                raise ValueError('Malformed Siso graph edges')
            if key != 'extra_outputs':
                inputs.extend(values)
        strong = row.get('inputs', []) + row.get('implicit_inputs', [])
        nodes[name] = (rule, inputs, strong)
        for alias in row.get('extra_outputs', []):
            if alias in aliases or alias == name:
                raise ValueError('Duplicate Siso output alias')
            aliases[alias] = name
        command = row.get('command')
        if command is not None and not isinstance(command, str):
            raise ValueError('Malformed Siso graph command')
        if command in commands:
            seeds.add(name)
    if set(nodes).intersection(aliases):
        raise ValueError('Ambiguous Siso output alias')
    canonical = lambda name: aliases.get(name, name)
    pending = [canonical(name) for name in targets]
    if any(name not in nodes for name in pending):
        raise ValueError('Requested target missing from Siso graph')
    needed = set()
    while pending:
        name = pending.pop()
        if name in needed or name not in nodes:
            continue
        needed.add(name)
        pending.extend(canonical(value) for value in nodes[name][1])
    if len(seeds) != frontier or not seeds.issubset(needed):
        raise ValueError('Every dry-run command must bind to one requested graph edge')
    consumers = {}
    for name in needed:
        for value in nodes[name][2]:
            consumers.setdefault(canonical(value), set()).add(name)
    affected, pending = set(), list(seeds)
    while pending:
        name = pending.pop()
        if name in affected:
            continue
        affected.add(name)
        pending.extend(consumers.get(name, ()))
    return sum(nodes[name][0] != 'phony' for name in affected)


def regular(path: Path) -> Path:
    if not path.is_absolute() or path != path.resolve() or not path.is_file() or path.is_symlink():
        raise ValueError('Expected a canonical regular file: ' + str(path))
    return path


def eligible_cache(output: Path, targets: list[str], receipt: dict) -> bytes:
    for name in ('.siso_deps', '.siso_fs_state', '.siso_config', 'build.ninja'):
        if not regular(output / name).stat().st_size:
            raise ValueError('The initialized Siso cache is incomplete')
    properties = read_record(output / '.siso_config').get('properties', {})
    if ((output / '.ninja_deps').exists() or properties.get('gn_logs:use_siso') != 'true'
            or properties.get('gn_args:use_remoteexec') != 'false'):
        raise ValueError('The bounded mode requires the existing local-only Siso cache')
    args = regular(output / 'args.gn').read_bytes()
    text = args.decode('utf-8-sig').replace('\r\n', '\n')
    if (digest(output / 'args.gn') != receipt.get('args_sha256')
            or text != (ROOT / 'native/args.gn').read_text(encoding='utf-8-sig')):
        raise ValueError('Cached build and selected GN arguments differ')
    for key in ('symbol_level', 'blink_symbol_level', 'v8_symbol_level'):
        if re.search(r'^' + key + r'\s*=\s*0\s*$', text, re.MULTILINE) is None:
            raise ValueError('The bounded mode requires the existing symbol-free cache')
    for key in ('is_debug', 'is_component_build'):
        if re.search(r'^' + key + r'\s*=\s*false\s*$', text, re.MULTILINE) is None:
            raise ValueError('Debug/component caches require the normal full-build policy')
    if sum(regular(output / (name + '.exe')).stat().st_size for name in targets) > 4 * 1024**3:
        raise ValueError('Cached binary set exceeds the bounded resource profile')
    return args


def verify_preserved(runtime: Path, receipt_raw: bytes, core: dict) -> dict:
    record = read_record(runtime.parent / 'report.json')
    if (record.get('passed') is not True or record.get('postguards_passed') is not True
            or record.get('runtime_core_sha256_measured') != core
            or regular(runtime / 'camouflow-build.json').read_bytes() != receipt_raw):
        raise ValueError('Rollback runtime is not the exact independently preserved baseline')
    assets = record.get('measured_assets_sha256')
    if not isinstance(assets, dict) or not 3 <= len(assets) <= 4096:
        raise ValueError('Rollback runtime asset inventory is incomplete')
    if (set(core) != {'chrome.exe', 'chrome.dll', 'chrome_elf.dll'}
            or not {'camouflow-build.json', 'args.gn'}.issubset(assets)
            or any(assets.get(name) != expected for name, expected in core.items())):
        raise ValueError('Rollback inventory must bind every code file, receipt and GN arguments')
    for relative, expected in assets.items():
        if (not isinstance(relative, str) or not relative or not isinstance(expected, str)
                or re.fullmatch('[0-9a-f]{64}', expected) is None):
            raise ValueError('Malformed rollback asset inventory')
        name = PurePosixPath(relative)
        if name.is_absolute() or '..' in name.parts or '\\' in relative:
            raise ValueError('Unsafe rollback asset path')
        path = runtime / relative
        if not path.is_relative_to(runtime) or ':' in relative or digest(regular(path)) != expected:
            raise ValueError('Rollback runtime asset changed: ' + relative)
    return assets


def baseline_chain(source: Path, candidate: dict, env: dict) -> None:
    manifest = candidate['manifest']
    for directory, revision in (('.', manifest['target_revision']), ('v8', manifest['dependencies']['v8']['revision'])):
        repository = source / directory
        if build.run(['git', 'rev-parse', 'HEAD'], repository, env, capture=True) != revision:
            raise ValueError('Cached Chromium/V8 revision changed')
        names = tuple(row['file'] for row in manifest['patches'] if row.get('directory', '.') == directory)
        measured = build._source_patches(repository, env, names, index_dir=source.parent,
                                         patch_directory=candidate['directory'] / 'patches')
        if [row['name'] for row in measured] != list(names):
            raise ValueError('The complete baseline source chain is not applied')


def write_report(path: Path, record: dict) -> None:
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')
    temporary.replace(path)


def restore_sources(source: Path, records: dict) -> list[str]:
    errors = []
    for name, row in records.items():
        path = source / name
        try:
            if digest(regular(path)) not in {row['before_sha256'], row['owned_after_sha256']}:
                raise ValueError('Refusing to overwrite a foreign source modification')
            if digest(regular(Path(row['backup']))) != row['before_sha256']:
                raise ValueError('Source backup changed; refusing to overwrite the checkout')
            shutil.copy2(row['backup'], path)
            if digest(path) != row['before_sha256']:
                raise ValueError('Restored bytes differ')
        except (OSError, ValueError) as error:
            errors.append(name + ': ' + str(error))
    return errors


COMPILE = """import sys
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from scripts import native_build as build
candidate = build.load_candidate('upstream-156')
if candidate['manifest_sha256'] != sys.argv[4]:
    raise ValueError('Selected compile inputs changed')
workspace = Path(sys.argv[2])
env = build.environment(workspace, git_ssl_backend=sys.argv[5])
if build.run(['git', 'rev-parse', 'HEAD'], workspace / 'depot_tools', env, capture=True) != candidate['lock']['depot_tools_revision']:
    raise ValueError('Pinned cached depot_tools changed before compilation')
build._execute_locked('build', Path(sys.argv[2]), int(sys.argv[3]), candidate, candidate['lock'],
                      git_ssl_backend=sys.argv[5], local_toolchain=True)
"""


def execute(action: str, workspace: Path, report_dir: Path, preserved_runtime: Path,
            base_checkpoint: str, *, jobs: int = 4, git_ssl_backend: str = 'schannel') -> dict:
    if action not in ('plan', 'rebuild', 'resume') or sys.platform != 'win32':
        raise ValueError('Explicit Windows plan/rebuild/resume is required')
    if type(jobs) is not int or not 1 <= jobs <= 4 or not re.fullmatch(r'001-\d{3}', base_checkpoint):
        raise ValueError('Select an exact checkpoint and 1..4 jobs')
    source = workspace / 'chromium/src'
    for path in (workspace, report_dir, preserved_runtime):
        if not path.is_absolute() or path != path.resolve() or path.drive.upper() != 'D:':
            raise ValueError('Use canonical unlinked paths on D:')
    if (not workspace.is_dir() or not preserved_runtime.is_dir() or report_dir.is_relative_to(ROOT)
            or report_dir.is_relative_to(source) or report_dir.is_relative_to(preserved_runtime)
            or preserved_runtime.is_relative_to(source) or preserved_runtime.is_relative_to(report_dir)
            or not report_dir.parent.is_dir() or (report_dir.exists() != (action == 'resume'))):
        raise ValueError('Use a fresh external report, or its explicit interrupted resume; rollback must be independent')
    candidate = build.load_candidate('upstream-156')
    checkpoint = regular(candidate['directory'] / 'checkpoints' / (base_checkpoint + '.json'))
    baseline = {**candidate, 'manifest': read_record(checkpoint), 'manifest_sha256': digest(checkpoint)}
    delta = appended_patches(baseline['manifest'], candidate['manifest'])
    patch_files = [regular(candidate['directory'] / 'patches' / row['file']) for row in delta]
    names = changed_paths([path.read_text(encoding='utf-8-sig') for path in patch_files])
    resource = build.preflight(workspace, lock={**candidate['lock'], 'minimum_free_gib': MINIMUM_FREE_GIB})
    build.candidate_workspace(workspace, candidate)
    output = source / 'out/CamouFlowNative'
    targets = sorted({'chrome', *(units.unit_binary_target(target) for target in units.SUPPORTED_TARGETS)})
    with build.workspace_lock(workspace):
        units.require_idle_builder(workspace)
        env = units.verification_environment(workspace, None, git_ssl_backend, True)
        env['NINJA_STATUS'] = '[%f/%t] '
        env_toolchain = env['GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256']
        if build.run(['git', 'rev-parse', 'HEAD'], workspace / 'depot_tools', env, capture=True) != candidate['lock']['depot_tools_revision']:
            raise ValueError('The pinned existing depot_tools cache is required')
        path = report_dir / 'report.json'
        if action == 'resume':
            report = read_record(path)
            if (report.get('kind') != 'bounded-native-rebuild' or report.get('measurement_complete')
                    or not report.get('compilation_started') or report.get('build_completed')
                    or report.get('candidate_manifest_sha256') != candidate['manifest_sha256']
                    or report.get('workspace') != str(workspace) or report.get('preserved_runtime') != str(preserved_runtime)
                    or report.get('base_manifest_sha256') != baseline['manifest_sha256']):
                raise ValueError('Only the same interrupted compilation can be resumed')
            receipt_raw = regular(report_dir / 'baseline-build.json').read_bytes()
        else:
            receipt_raw = regular(output / 'camouflow-build.json').read_bytes()
            report = dict(schema=1, kind='bounded-native-rebuild', action=action, passed=False,
                measurement_complete=False, compilation_started=False, build_completed=False,
                workspace=str(workspace), preserved_runtime=str(preserved_runtime), jobs=jobs,
                base_manifest_sha256=baseline['manifest_sha256'], candidate_manifest_sha256=candidate['manifest_sha256'],
                full_build_reserve_gib=candidate['lock']['minimum_free_gib'], cached_reserve_gib=MINIMUM_FREE_GIB,
                resource_preflight=resource, source_before={}, stage_before={}, build_attempts=0,
                sync_rerun=False, hooks_rerun=False, objects_cleaned=False,
                browser_runtime_verified=False, privacy_admitted=False, production_admitted=False)
        receipt = json.loads(receipt_raw)
        validate_build_receipt(receipt, baseline['lock'], candidate=baseline)
        if receipt.get('local_windows_toolchain_sha256') != env_toolchain:
            raise ValueError('Cached receipt and actual local SDK/MSVC differ')
        core = receipt['runtime_core_sha256_measured']
        assets = verify_preserved(preserved_runtime, receipt_raw, core)
        args = eligible_cache(output, targets, receipt)
        total_bytes = sum(regular(source / name).stat().st_size for name in names)
        require_capacity(free_bytes=shutil.disk_usage(workspace).free, source_bytes=total_bytes, planned_steps=0,
                         valid_cache=True, matching_toolchain=True, matching_args=True, preserved_runtime_verified=True)
        frozen = {item: digest(regular(item)) for item in batch.source_inputs(candidate) | {checkpoint, Path(__file__).resolve()}}

        def check_inputs():
            if (any(digest(item) != expected for item, expected in frozen.items())
                    or (output / 'args.gn').read_bytes() != args
                    or build.local_windows_toolchain(workspace)['GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256'] != env_toolchain):
                raise ValueError('Source, GN or local toolchain changed during the bounded rebuild')

        def plan(label):
            command = build.depot_command('autoninja', workspace) + ['-C', 'out/CamouFlowNative', '-n', *targets]
            result = subprocess.run(command, cwd=source, env=env, capture_output=True, text=True, check=True)
            (report_dir / (label + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
            steps = siso_steps(result.stdout + '\n' + result.stderr)
            if steps:
                graph = report_dir / (label + '.graph.jsonl')
                with graph.open('xb') as stream, (report_dir / (label + '.graph.stderr')).open('xb') as errors:
                    subprocess.run([str(regular(source / 'third_party/siso/cipd/siso.exe')), 'query', 'graph',
                                    '-C', 'out/CamouFlowNative'], cwd=source, env=env,
                                   stdout=stream, stderr=errors, check=True)
                if graph.stat().st_size > 2 * 1024**3:
                    raise ValueError('Siso graph exceeds the cached resource profile')
                with graph.open(encoding='utf-8') as stream:
                    affected = affected_steps((json.loads(line) for line in stream), targets,
                                              result.stdout, steps)
                report.setdefault('graph_plans', {})[label] = dict(frontier_steps=steps,
                    conservative_affected_steps=affected, graph_sha256=digest(graph))
                steps = max(steps, affected)
            require_capacity(free_bytes=shutil.disk_usage(workspace).free, source_bytes=total_bytes, planned_steps=steps,
                             valid_cache=True, matching_toolchain=True, matching_args=True, preserved_runtime_verified=True)
            return steps

        if action == 'resume':
            if report.get('inputs_sha256') != {str(item): value for item, value in frozen.items()}:
                raise ValueError('Interrupted rebuild inputs changed; refusing an implicit restart')
            build.candidate_source_patches(source, env, candidate)
            for stage in ('sync', 'hooks'):
                build.require_stage(workspace / 'chromium', stage, candidate)
        else:
            if build.measure_runtime_core(output / 'chrome.exe') != core:
                raise ValueError('The initialized output is not the preserved baseline code')
            baseline_chain(source, baseline, env)
            for stage in ('sync', 'hooks'):
                build.require_stage(workspace / 'chromium', stage, baseline)
                if not dependencies_equivalent(build.stage_identity(workspace / 'chromium', stage, baseline),
                                              build.stage_identity(workspace / 'chromium', stage, candidate)):
                    raise ValueError('Dependency stage needs a real sync/hooks execution')
            report_dir.mkdir(exist_ok=False)
            (report_dir / 'baseline-build.json').write_bytes(receipt_raw)
            report.update(inputs_sha256={str(item): value for item, value in frozen.items()},
                          baseline_core=core, preserved_assets=len(assets), source_bytes=total_bytes,
                          local_windows_toolchain_sha256=env_toolchain)
        write_report(path, report)
        try:
            if action != 'resume':
                report['baseline_planned_steps'] = plan('baseline-plan')
                if report['baseline_planned_steps'] != 0:
                    raise ValueError('Baseline cache has unrelated pending work; full build policy required')
                if action == 'plan':
                    check_inputs()
                    report.update(passed=True, measurement_complete=True, phase='eligible-baseline-no-source-change')
                    write_report(path, report)
                    return report
                for name in names:
                    file = regular(source / name)
                    backup = report_dir / 'source-before' / name
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file, backup)
                    report['source_before'][name] = dict(backup=str(backup), before_sha256=digest(file), owned_after_sha256=digest(file))
                for stage in ('sync', 'hooks'):
                    file = build.stage_path(workspace / 'chromium', stage)
                    value = file.read_bytes()
                    backup = report_dir / ('baseline-' + stage + '.json')
                    backup.write_bytes(value)
                    report['stage_before'][stage] = dict(backup=str(backup), before_sha256=digest(file),
                                                        owned_after_sha256=digest(file))
                write_report(path, report)
                for patch in patch_files:
                    build.run(['git', 'apply', '--check', '--whitespace=error', str(patch)], source, env)
                    build.run(['git', 'apply', '--whitespace=error', str(patch)], source, env)
                    for name in names:
                        report['source_before'][name]['owned_after_sha256'] = digest(regular(source / name))
                    write_report(path, report)
                build.candidate_source_patches(source, env, candidate)
                for stage in ('sync', 'hooks'):
                    build.require_stage(workspace / 'chromium', stage, baseline)
                    build.record_stage(workspace / 'chromium', stage, candidate)
                    report['stage_before'][stage]['owned_after_sha256'] = digest(build.stage_path(workspace / 'chromium', stage))
                    write_report(path, report)
                report['dependency_stages_reused'] = True
                build.check_patch_dependencies(source, env)
                build.run(build.depot_command('gn', workspace) + ['gen', 'out/CamouFlowNative'], source, env)
            attempt = report['build_attempts'] + 1
            report['append_planned_steps'] = plan('append-plan-' + str(attempt))
            check_inputs()
            report.update(compilation_started=True, phase='build', build_attempts=attempt)
            write_report(path, report)
            with (report_dir / ('build-' + str(attempt) + '.log')).open('xb') as log:
                subprocess.run([sys.executable, '-c', COMPILE, str(ROOT), str(workspace), str(jobs),
                                candidate['manifest_sha256'], git_ssl_backend], cwd=ROOT,
                               stdout=log, stderr=subprocess.STDOUT, check=True)
            check_inputs()
            report.update(build_completed=True, phase='native-batch', runtime_core_sha256_measured=build.measure_runtime_core(output / 'chrome.exe'),
                          build_receipt_sha256=digest(output / 'camouflow-build.json'))
            write_report(path, report)
            native_dir = report_dir / ('native-batch-' + str(attempt))
            native_dir.mkdir(exist_ok=False)
            native = batch._verify_locked(workspace, native_dir, tuple(units.SUPPORTED_TARGETS), candidate=candidate,
                jobs=jobs, vs_installation=None, git_ssl_backend=git_ssl_backend, local_toolchain=True, timeout_seconds=300)
            check_inputs()
            report.update(passed=native['passed'] and native['postguards_passed'], measurement_complete=True,
                          native_tests=sum(row.get('tests', 0) for row in native['targets']), phase='complete')
        except Exception as error:
            report.update(passed=False, error_type=type(error).__name__, error=str(error))
            if isinstance(error, subprocess.CalledProcessError):
                report['measurement_complete'] = True
            if not report['compilation_started']:
                report['rollback_errors'] = restore_sources(source, report['source_before'])
                for stage, row in report['stage_before'].items():
                    file = build.stage_path(workspace / 'chromium', stage)
                    report['rollback_errors'].extend(restore_sources(file.parent, {file.name: row}))
                report['measurement_complete'] = True
            write_report(path, report)
            raise
        write_report(path, report)
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'rebuild', 'resume'))
    parser.add_argument('--candidate', choices=('upstream-156',), required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--base-checkpoint', required=True)
    parser.add_argument('--preserved-runtime', type=Path, required=True)
    parser.add_argument('--report-dir', type=Path, required=True)
    parser.add_argument('--jobs', type=int, choices=range(1, 5), default=4)
    parser.add_argument('--git-ssl-backend', choices=('openssl', 'schannel'), default='schannel')
    args = parser.parse_args()
    try:
        report = execute(args.action, args.workspace, args.report_dir, args.preserved_runtime,
                         args.base_checkpoint, jobs=args.jobs, git_ssl_backend=args.git_ssl_backend)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('Bounded native rebuild failed: ' + str(error), file=sys.stderr)
        return 1
    print(json.dumps({key: report.get(key) for key in ('passed', 'phase', 'build_completed', 'native_tests')}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
