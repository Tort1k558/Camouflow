import sys
import json
import os
from pathlib import Path
import subprocess

import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Windows process/ACL integration')

from app.core.native import distribution
from app.core.native import windows_sandbox as sandbox


def acls(paths):
    script = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
@((ConvertFrom-Json $env:GLINT_TEST_ACL_PATHS) | ForEach-Object {
  $acl = Get-Acl -LiteralPath $_
  [pscustomobject]@{path=$_; sddl=$acl.Sddl; rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {
    [pscustomobject]@{sid=$_.IdentityReference.Value; mask=[long]$_.FileSystemRights; kind=$_.AccessControlType.ToString(); inherit=[int]$_.InheritanceFlags}
  })}
}) | ConvertTo-Json -Depth 6 -Compress
'''
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
        env=dict(os.environ, GLINT_TEST_ACL_PATHS=json.dumps([str(path) for path in paths])),
        capture_output=True, check=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    return {row['path']: row for row in json.loads(result.stdout.decode('utf-8-sig'))}


@pytest.fixture
def owned(tmp_path):
    stage = tmp_path / 'native-install-owned'
    payload = stage / 'payload'
    (payload / 'locales').mkdir(parents=True)
    executable = payload / 'chrome.exe'
    executable.write_bytes(b'owned synthetic package executable')
    (payload / 'locales/en-US.pak').write_bytes(b'owned synthetic locale')
    profile = tmp_path / 'private-profile'
    profile.mkdir()
    (profile / 'private.txt').write_bytes(b'owned synthetic secret fixture')
    return stage, payload, executable, profile


def test_exact_install_capabilities_get_rx_without_touching_private_profiles(owned):
    stage, payload, executable, profile = owned
    paths = [payload, executable, payload / 'locales', profile]
    before = acls(paths)
    original_bytes = executable.read_bytes()
    sandbox.configure_staged_sandbox_access(payload, stage)
    after = acls(paths)
    assert after[str(profile)]['sddl'] == before[str(profile)]['sddl']
    for path in paths[:-1]:
        for sid in sandbox.INSTALL_CAPABILITY_SIDS:
            rules = [rule for rule in after[str(path)]['rules'] if rule['sid'] == sid]
            assert rules and all(rule['kind'] == 'Allow' and rule['mask'] == 0x1200A9 for rule in rules)
        assert [rule for rule in after[str(path)]['rules'] if rule['sid'] not in sandbox.INSTALL_CAPABILITY_SIDS] == [
            rule for rule in before[str(path)]['rules'] if rule['sid'] not in sandbox.INSTALL_CAPABILITY_SIDS]
    assert all(rule['inherit'] == 3 for rule in after[str(payload)]['rules']
               if rule['sid'] in sandbox.INSTALL_CAPABILITY_SIDS)
    assert executable.read_bytes() == original_bytes
    sandbox.configure_staged_sandbox_access(payload, stage)
    assert acls(paths) == after


def test_hard_link_alias_rejects_before_any_permission_change(owned, tmp_path):
    stage, payload, executable, profile = owned
    outside = tmp_path / 'outside.txt'
    outside.write_bytes(b'owned alias target')
    os.link(outside, payload / 'alias.txt')
    before = acls([outside, profile])
    with pytest.raises(ValueError, match='link'):
        sandbox.configure_staged_sandbox_access(payload, stage)
    assert acls([outside, profile]) == before


@pytest.mark.parametrize('wrong', ['payload', 'stage'])
def test_only_the_installers_owned_payload_can_be_modified(owned, tmp_path, wrong):
    stage, payload, executable, profile = owned
    with pytest.raises(ValueError, match='owned'):
        sandbox.configure_staged_sandbox_access(profile if wrong == 'payload' else payload,
                                                tmp_path if wrong == 'stage' else stage)


def test_path_limit_fails_before_acl_command(owned, monkeypatch):
    stage, payload, _, _ = owned
    monkeypatch.setattr(sandbox, 'MAX_STAGE_PATHS', 2)
    with pytest.raises(ValueError, match='object limit'):
        sandbox.configure_staged_sandbox_access(payload, stage)


def test_acl_command_failure_is_explicit_not_silently_admitted(owned, monkeypatch):
    stage, payload, _, _ = owned

    def fail(command, **kwargs):
        raise subprocess.CalledProcessError(5, command)

    monkeypatch.setattr(sandbox.subprocess, 'run', fail)
    with pytest.raises(OSError, match='sandbox read/execute'):
        sandbox.configure_staged_sandbox_access(payload, stage)


def test_system_utility_does_not_use_a_path_selected_executable(monkeypatch):
    monkeypatch.setenv('PATH', '')
    executable = sandbox._system_icacls()
    assert executable.is_file() and executable.name == 'icacls.exe'
    assert executable.parent.name.casefold() in ('system32', 'syswow64')


def test_installer_calls_the_guard_on_its_stage_before_publishing(tmp_path, monkeypatch):
    import test_native_runtime as existing

    store = distribution.NativeBinaryStore(tmp_path / 'store')
    archive, digest = existing._native_release_archive(tmp_path)
    calls = []
    original = distribution.configure_staged_sandbox_access

    def observe(payload, stage):
        assert payload.parent == stage and stage.parent == store.root
        assert not (store.root / 'releases' / digest).exists()
        calls.append((payload, stage))
        original(payload, stage)

    monkeypatch.setattr(distribution, 'configure_staged_sandbox_access', observe)
    installed = store.install_archive(archive, digest)
    assert len(calls) == 1 and store.inspect(digest) == installed
    assert not list(store.root.glob('native-install-*'))


def test_failed_acl_setup_never_publishes_or_damages_the_existing_release(tmp_path, monkeypatch):
    import test_native_runtime as existing

    store = distribution.NativeBinaryStore(tmp_path / 'store')
    archive, digest = existing._native_release_archive(tmp_path)
    installed = store.install_archive(archive, digest)
    first_bytes = Path(installed['executable_path']).read_bytes()
    archive, second_digest = existing._native_release_archive(tmp_path, '0.2.0-dev')

    def fail(*args):
        raise OSError('controlled capability setup failure')

    monkeypatch.setattr(distribution, 'configure_staged_sandbox_access', fail)
    with pytest.raises(OSError, match='capability setup failure'):
        store.install_archive(archive, second_digest)
    assert not (store.root / 'releases' / second_digest).exists()
    assert Path(installed['executable_path']).read_bytes() == first_bytes
    assert store.inspect(digest) == installed
    assert not list(store.root.glob('native-install-*'))
