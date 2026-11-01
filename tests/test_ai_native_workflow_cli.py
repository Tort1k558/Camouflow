import os

import pytest

from scripts import verify_ai_workflows as gate


@pytest.mark.parametrize('engine', ['camoufox', 'cloakbrowser'])
def test_ai_workflow_preserves_existing_engine_arguments(engine):
    args = gate.parse_args([engine])
    assert args.engine == engine
    assert args.native_executable is args.work_dir is None
    assert gate.parse_args([]).engine == 'camoufox'


@pytest.mark.parametrize('engine', ['camoufox', 'cloakbrowser'])
def test_non_native_workflow_rejects_native_executable(engine):
    with pytest.raises(SystemExit) as error:
        gate.parse_args([engine, '--native-executable', 'not-used.exe'])
    assert error.value.code == 2


def test_native_workflow_requires_explicit_executable_and_workspace():
    with pytest.raises(SystemExit) as error:
        gate.parse_args(['native'])
    assert error.value.code == 2


@pytest.fixture
def native_paths(tmp_path):
    if os.name != 'nt' or tmp_path.drive.upper() != 'D:':
        pytest.skip('Native filesystem argument controls require a disposable Windows D: directory')
    runtime = tmp_path / 'runtime'
    runtime.mkdir()
    executable = runtime / 'chrome.exe'
    executable.write_bytes(b'not launched by CLI parser tests')
    return executable, tmp_path / 'workspace'


def test_native_workflow_parsing_does_not_create_profiles_or_launch_a_browser(native_paths):
    executable, workspace = native_paths
    args = gate.parse_args(['native', '--native-executable', str(executable), '--work-dir', str(workspace)])
    assert args.native_executable == executable and args.work_dir == workspace
    assert not workspace.exists()


@pytest.mark.parametrize('case', ['missing-workspace', 'relative-executable', 'existing-workspace',
                                  'relative-workspace', 'runtime-overlap', 'non-d-workspace', 'missing-parent'])
def test_native_workflow_rejects_unsafe_paths_without_creating_output(native_paths, case):
    executable, workspace = native_paths
    arguments = ['native', '--native-executable', str(executable), '--work-dir', str(workspace)]
    if case == 'missing-workspace':
        arguments = arguments[:-2]
    elif case == 'relative-executable':
        arguments[2] = 'chrome.exe'
    elif case == 'existing-workspace':
        arguments[-1] = str(executable.parent)
    elif case == 'relative-workspace':
        arguments[-1] = 'relative-workspace'
    elif case == 'runtime-overlap':
        arguments[-1] = str(executable.parent / 'nested')
    elif case == 'non-d-workspace':
        arguments[-1] = 'C:/ai-workflow-must-not-be-created'
    else:
        arguments[-1] = str(workspace / 'missing-parent' / 'output')
    with pytest.raises(SystemExit) as error:
        gate.parse_args(arguments)
    assert error.value.code == 2
    assert not workspace.exists()
