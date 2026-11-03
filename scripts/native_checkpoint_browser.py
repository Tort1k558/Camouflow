"""Run discovered ordinary browser tests with isolated, complete PRE chains."""
import re
import subprocess
import time
from pathlib import Path

from scripts.native_checkpoint_crash import checksum
from scripts.native_checkpoint_recovery import _run_recovery_process as run_tests

from scripts.package_native_windows import read_record
from scripts.verify_native_checkpoint_units import validate_results


def browser_case_groups(required: dict) -> list[tuple[str, tuple[str, ...]]]:
    if not isinstance(required, dict) or not required:
        raise ValueError('Browser execution requires a nonempty discovered selection')
    grouped = []
    name_pattern = re.compile(r'[A-Za-z0-9_/]+')
    for suite, selected in required.items():
        if (not isinstance(suite, str) or not name_pattern.fullmatch(suite)
                or 'PRE_' in suite or not isinstance(selected, (set, frozenset, list, tuple))
                or not selected):
            raise ValueError('Invalid discovered browser suite/cases')
        families = {}
        observed = set()
        for case in selected:
            if (not isinstance(case, str) or not name_pattern.fullmatch(case)
                    or case in observed or ('PRE_' in case and not case.startswith('PRE_'))):
                raise ValueError('Invalid or duplicate discovered browser case')
            observed.add(case)
            leaf, depth = case, 0
            while leaf.startswith('PRE_'):
                leaf, depth = leaf[4:], depth + 1
            if not leaf or 'PRE_' in leaf:
                raise ValueError('Invalid PRE_ chain name')
            families.setdefault(leaf, {})[depth] = case
        for leaf, phases in families.items():
            deepest = max(phases)
            if set(phases) != set(range(deepest + 1)):
                raise ValueError('PRE_ chain is orphaned or missing a declared phase: ' + suite + '.' + leaf)
            grouped.append((suite, tuple(phases[level] for level in range(deepest, -1, -1))))
    return sorted(grouped, key=lambda item: (item[0], item[1][-1]))


def run_browser_cases(executable: Path, required: dict, *, source: Path, env: dict,
                      report_dir: Path, timeout: int) -> list[dict]:
    groups = browser_case_groups(required)
    deadline = time.monotonic() + timeout
    runs = []
    for group_index, (suite, phases) in enumerate(groups):
        profile = None
        identity = None
        if len(phases) > 1:
            if report_dir != report_dir.resolve() or not report_dir.is_dir():
                raise ValueError('Paired browser profiles require a canonical report directory')
            profile = report_dir / (executable.stem + '-chain-' + str(group_index).zfill(3) + '-profile')
            if profile.resolve() != profile or profile.parent != report_dir or profile.exists():
                raise ValueError('Paired browser profile must be fresh and owned by this report')
            profile.mkdir(exist_ok=False)
            stat = profile.stat()
            identity = (stat.st_dev, stat.st_ino)
        previous_failed = False
        for phase_index, case in enumerate(phases):
            selected = suite + '.' + case
            prefix = executable.stem + '-' + str(len(runs)).zfill(3)
            results = report_dir / (prefix + '-tests.json')
            row = {'case': selected, 'passed': False}
            if profile:
                row.update(profile_directory=profile.name, phase_index=phase_index,
                           phase_count=len(phases))
            runs.append(row)
            if previous_failed:
                row.update(error='Earlier PRE_ phase failed; dependent phase was not executed',
                           not_executed=True)
                continue
            try:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError('Browser test binary execution budget exhausted')
                command = [str(executable), '--gtest_filter=' + selected,
                           '--single-process-tests', '--gtest_output=json:' + str(results)]
                if profile:
                    stat = profile.stat()
                    if profile.resolve() != profile or (stat.st_dev, stat.st_ino) != identity:
                        raise ValueError('Paired browser profile identity changed')
                    command.append('--user-data-dir=' + str(profile))
                run_tests(command, source=source, env=env,
                          log=report_dir / (prefix + '.log'), timeout=remaining)
                validate_results(read_record(results), {suite: {case}})
                if profile:
                    stat = profile.stat()
                    if (profile.resolve() != profile or (stat.st_dev, stat.st_ino) != identity
                            or not any(profile.iterdir())):
                        raise ValueError('Browser did not retain the requested owned profile')
                    row['profile_identity_verified'] = True
                row.update(passed=True, results_file=results.name,
                           results_sha256=checksum(results))
            except (ValueError, OSError, subprocess.SubprocessError) as error:
                row['error'] = str(error)
                previous_failed = True
    return runs
