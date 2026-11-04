import asyncio
import json
import os
from types import SimpleNamespace

import pytest

from scripts import verify_ai_workflows as gate
from scripts import verify_ai_provider as provider_gate


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


@pytest.mark.parametrize('engine', ['camoufox', 'cloakbrowser'])
def test_live_provider_preserves_existing_engine_arguments(engine):
    args = provider_gate.parse_args(['--engine', engine, '--settings-file', 'private.json', '--report', 'report.json'])
    assert args.engine == engine and args.repeats == 1
    assert args.native_executable is args.work_dir is None


@pytest.mark.parametrize('engine', ['camoufox', 'cloakbrowser'])
def test_live_provider_rejects_native_executable_for_other_engines(engine):
    with pytest.raises(SystemExit) as error:
        provider_gate.parse_args(['--engine', engine, '--settings-file', 'private.json', '--report', 'report.json',
                                 '--native-executable', 'not-used.exe'])
    assert error.value.code == 2


def test_live_native_provider_requires_explicit_runtime_and_workspace():
    with pytest.raises(SystemExit) as error:
        provider_gate.parse_args(['--engine', 'native', '--settings-file', 'private.json', '--report', 'report.json'])
    assert error.value.code == 2


def test_live_native_provider_parser_does_not_read_secrets_or_create_output(native_paths):
    executable, workspace = native_paths
    args = provider_gate.parse_args(['--engine', 'native', '--settings-file', 'private-does-not-exist.json',
        '--native-executable', str(executable), '--work-dir', str(workspace), '--report', str(workspace / 'report.json')])
    assert args.native_executable == executable and args.work_dir == workspace
    assert not workspace.exists()


@pytest.mark.parametrize('case', ['outside-report', 'relative-report', 'existing-workspace', 'missing-parent',
                                  'runtime-overlap', 'missing-workspace', 'relative-executable'])
def test_live_native_provider_rejects_unsafe_output_without_launch(native_paths, case):
    executable, workspace = native_paths
    arguments = ['--engine', 'native', '--settings-file', 'private.json',
                 '--native-executable', str(executable), '--work-dir', str(workspace),
                 '--report', str(workspace / 'report.json')]
    if case == 'outside-report':
        arguments[-1] = str(workspace.parent / 'outside.json')
    elif case == 'relative-report':
        arguments[-1] = 'report.json'
    elif case == 'existing-workspace':
        arguments[7] = str(executable.parent)
    elif case == 'missing-parent':
        arguments[7] = str(workspace / 'missing' / 'output')
    elif case == 'runtime-overlap':
        arguments[7] = str(executable.parent / 'nested')
    elif case == 'missing-workspace':
        arguments = arguments[:6] + arguments[8:]
    else:
        arguments[5] = 'chrome.exe'
    with pytest.raises(SystemExit) as error:
        provider_gate.parse_args(arguments)
    assert error.value.code == 2
    assert not workspace.exists()


def test_live_provider_forwards_one_explicit_runtime_to_capture_and_replay(monkeypatch, tmp_path):
    from app.core import browser_interface
    from app.services.ai_agent import llm, loop, templates, to_steps
    from app.services import scenario_engine
    from app.storage import db

    captured = []
    replayed = []
    closed = []
    class Browser:
        page = object()
        def __init__(self, name, **kwargs):
            captured.append(kwargs)
        async def start(self):
            pass
        async def close(self, **kwargs):
            closed.append('capture')
    class Executor:
        variables = {'catalog': json.dumps([
            {'Name': 'Notebook updated', 'Price': '17'}, {'Name': 'Desk lamp', 'Price': '34'},
            {'Name': 'Keyboard', 'Price': '59'}])}
        def __init__(self, account, *args, **kwargs):
            replayed.append(account)
        async def start(self):
            pass
        async def run(self):
            return True
        async def close(self, **kwargs):
            closed.append('replay')
    class Session:
        def __init__(self, *args, **kwargs):
            pass
        async def run(self):
            return dict(status='success', requests=1, prompt_tokens=10, completion_tokens=10,
                        duration_s=0.1, result='provider echoed synthetic-key-not-a-real-credential',
                        steps=[{'action': 'start'}], outputs={'catalog': [
                            {'Name': 'Notebook', 'Price': '12', 'Link': '/products/notebook'},
                            {'Name': 'Desk lamp', 'Price': '34', 'Link': '/products/lamp'},
                            {'Name': 'Keyboard', 'Price': '59', 'Link': '/products/keyboard'}]})
    server = SimpleNamespace(url='http://127.0.0.1/catalog', close=lambda: closed.append('server'))
    monkeypatch.setattr(db, 'init_db', lambda: None)
    monkeypatch.setattr(db, 'DATA_ROOT', tmp_path)
    for name, relative in [('SETTINGS_DIR', 'settings'), ('PROFILES_DIR', 'profiles'),
                           ('SCENARIOS_DIR', 'scenaries'), ('OUTPUTS_DIR', 'outputs'),
                           ('ACCOUNTS_FILE', 'settings/accounts.json'), ('SETTINGS_FILE', 'settings/settings.json')]:
        monkeypatch.setattr(db, name, tmp_path / relative)
    monkeypatch.setattr(browser_interface, 'BrowserInterface', Browser)
    monkeypatch.setattr(scenario_engine, 'ScenarioExecutor', Executor)
    monkeypatch.setattr(llm, 'LLMClient', lambda config: object())
    monkeypatch.setattr(loop, 'AgentSession', Session)
    monkeypatch.setattr(to_steps, 'compile_workflow', lambda *args: [{'action': 'start'}])
    monkeypatch.setattr(templates, 'DemoServer', lambda: server)
    original_html = templates.DEMO_HTML
    settings = {'headless': True, 'executable_path': 'D:/owned-runtime/chrome.exe'}
    result = asyncio.run(provider_gate.verify('native', SimpleNamespace(model='fixture', api_key='synthetic-key-not-a-real-credential'), tmp_path, 1, settings))
    assert result['passed'] and result['engine'] == 'native'
    assert captured[0]['browser_settings'] == settings
    assert replayed[0]['_browser_settings'] == settings
    assert captured[0]['browser_settings'] is not settings
    assert replayed[0]['_browser_settings'] is not settings
    assert closed == ['capture', 'replay', 'server'] and templates.DEMO_HTML == original_html
    transcript = (tmp_path / 'outputs/ai-runs/native-0/transcript.json').read_text(encoding='utf-8-sig')
    assert 'synthetic-key-not-a-real-credential' not in transcript
    assert '[redacted]' in transcript


@pytest.fixture
def live_main_args(monkeypatch, tmp_path):
    settings = tmp_path / 'private.json'
    settings.write_text(json.dumps({'ai_base_url': 'https://example.invalid/v1',
                                   'ai_api_key': 'synthetic-key-not-a-real-credential', 'ai_model': 'fixture'}), encoding='utf-8')
    workspace = tmp_path / 'owned-workspace'
    runtime = tmp_path / 'runtime'
    runtime.mkdir()
    executable = runtime / 'chrome.exe'
    executable.write_bytes(b'not executed')
    args = SimpleNamespace(engine='native', settings_file=settings, native_executable=executable,
                           work_dir=workspace, report=workspace / 'report.json', repeats=1)
    monkeypatch.setattr(provider_gate, 'parse_args', lambda: args)
    monkeypatch.setenv('CAMOUFLOW_DATA_DIR', str(tmp_path / 'before-main'))
    return args


def test_live_provider_refuses_busy_native_runtime_before_browser_or_provider(monkeypatch, live_main_args):
    from scripts import verify_native_privacy_units as native_guard
    def busy(scope):
        assert scope == live_main_args.native_executable.parent
        raise ValueError('synthetic-private-error-must-not-leak')
    async def unexpected(*args):
        pytest.fail('Browser/provider must not start while the build is active')
    monkeypatch.setattr(native_guard, 'require_idle_builder', busy)
    monkeypatch.setattr(provider_gate, 'verify', unexpected)
    assert provider_gate.main() == 1
    report = json.loads(live_main_args.report.read_text(encoding='utf-8-sig'))
    assert report['passed'] is False
    assert report['failed_phase'] == 'native-preflight'
    assert 'synthetic-private-error' not in live_main_args.report.read_text(encoding='utf-8-sig')
    assert sorted(path.name for path in live_main_args.work_dir.iterdir()) == ['report.json']


@pytest.mark.parametrize('changed', [False, True])
def test_live_provider_binds_result_to_unchanged_native_code(monkeypatch, live_main_args, changed):
    from scripts import verify_native_privacy_units as native_guard, verify_native_runtime as runtime_guard
    cores = iter([{'chrome.exe': 'a' * 64}, {'chrome.exe': ('b' if changed else 'a') * 64}])
    monkeypatch.setattr(native_guard, 'require_idle_builder', lambda scope: None)
    monkeypatch.setattr(runtime_guard, 'measure_runtime_core', lambda path: next(cores))
    async def verify(engine, config, root, repeats, settings):
        assert engine == 'native' and root == live_main_args.work_dir
        assert settings == {'headless': True, 'executable_path': str(live_main_args.native_executable)}
        return {'passed': True}
    monkeypatch.setattr(provider_gate, 'verify', verify)
    assert provider_gate.main() == int(changed)
    report = json.loads(live_main_args.report.read_text(encoding='utf-8-sig'))
    assert report['passed'] is (not changed) and report['runtime_core_unchanged'] is (not changed)
    assert report['privacy_admitted'] is False


def test_live_provider_preserves_report_created_during_the_run(monkeypatch, live_main_args):
    from scripts import verify_native_privacy_units as native_guard, verify_native_runtime as runtime_guard
    monkeypatch.setattr(native_guard, 'require_idle_builder', lambda scope: None)
    monkeypatch.setattr(runtime_guard, 'measure_runtime_core', lambda path: {'chrome.exe': 'a' * 64})
    async def verify(*args):
        live_main_args.report.write_text('owned existing artifact', encoding='utf-8')
        return {'passed': True}
    monkeypatch.setattr(provider_gate, 'verify', verify)
    with pytest.raises(FileExistsError):
        provider_gate.main()
    assert live_main_args.report.read_text(encoding='utf-8-sig') == 'owned existing artifact'
