import pytest


def _racy_native_index_fixture(tmp_path, external_index, optional_locks):
    import os
    import subprocess

    source = tmp_path / 'src'
    source.mkdir()
    env = {**os.environ, 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1',
           'GIT_OPTIONAL_LOCKS': optional_locks, 'GIT_TERMINAL_PROMPT': '0'}
    env.pop('GIT_INDEX_FILE', None)

    def git(*args):
        return subprocess.check_output(['git', *args], cwd=source, env=env)

    git('init', '--quiet')
    git('config', 'core.autocrlf', 'false')
    git('config', 'core.trustctime', 'false')
    target = source / 'value.txt'
    target.write_bytes(b'before\n')
    timestamp = 1_400_000_000_000_000_000
    os.utime(target, ns=(timestamp, timestamp))
    git('add', 'value.txt')
    git('-c', 'user.name=Glint fixture', '-c', 'user.email=fixture@example.invalid',
        'commit', '--quiet', '-m', 'owned baseline')
    index = source / '.git/index'
    os.utime(index, ns=(timestamp, timestamp))
    if external_index:
        selected = tmp_path / 'selected-index'
        selected.write_bytes(index.read_bytes())
        os.utime(selected, ns=(timestamp, timestamp))
        index = selected
        env['GIT_INDEX_FILE'] = str(index)
    target.write_bytes(b'after!\n')
    os.utime(target, ns=(timestamp, timestamp))
    assert target.read_bytes() != git('show', 'HEAD:value.txt')
    return source, env, index


@pytest.mark.parametrize('external_index', (False, True))
@pytest.mark.parametrize('optional_locks', ('0', '1'))
def test_native_source_index_copy_preserves_racy_stat_detection(tmp_path, external_index, optional_locks):
    from scripts import native_build as build

    source, env, index = _racy_native_index_fixture(tmp_path, external_index, optional_locks)
    original = index.read_bytes()
    timestamp = index.stat().st_mtime_ns
    assert build._source_patch_changes(source, env, index_dir=tmp_path) == {'value.txt'}
    assert index.read_bytes() == original and index.stat().st_mtime_ns == timestamp


@pytest.mark.parametrize('external_index', (False, True))
def test_native_source_index_rejects_metadata_only_concurrent_change(tmp_path, monkeypatch, external_index):
    import os

    from scripts import native_build as build

    source, env, index = _racy_native_index_fixture(tmp_path, external_index, '0')
    original = index.read_bytes()
    timestamp = index.stat().st_mtime_ns
    run = build.run

    def mutate(command, cwd, environment, **kwargs):
        result = run(command, cwd, environment, **kwargs)
        if command[:3] == ['git', 'diff', 'HEAD']:
            os.utime(index, ns=(timestamp, timestamp + 2_000_000_000))
        return result

    monkeypatch.setattr(build, 'run', mutate)
    with pytest.raises(ValueError, match='index changed concurrently'):
        build._source_patch_changes(source, env, index_dir=tmp_path)
    assert index.read_bytes() == original
