"""Private real-Git cases for complete-chain final-tree identity."""
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest

from scripts import native_build as build


def patch(path, before, after):
    mode = 'new file mode 100644\n' if before is None else 'deleted file mode 100644\n' if after is None else ''
    return 'diff --git a/' + path + ' b/' + path + '\n' + mode + ''.join(difflib.unified_diff(
        before.splitlines(True) if before is not None else [],
        after.splitlines(True) if after is not None else [],
        fromfile='a/' + path if before is not None else '/dev/null',
        tofile='b/' + path if after is not None else '/dev/null'))


@pytest.mark.parametrize('failure', [None, 'foreign', 'resurrected', 'wrong-bytes', 'partial', 'clean', 'missing-patch'])
@pytest.mark.parametrize('net_zero', [False, True])
def test_complete_chain_accounts_for_add_modify_delete_without_touching_real_index(tmp_path, failure, net_zero):
    root, patches = tmp_path / 'src', tmp_path / 'patches'
    root.mkdir()
    patches.mkdir()
    env = {**os.environ, 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull}

    def git(*args):
        return subprocess.run(['git', '-c', 'core.autocrlf=false', *args], cwd=root,
            env=env, capture_output=True, text=True, check=True).stdout

    git('init')
    (root / 'keep.cc').write_text('original\n', encoding='utf-8', newline='\n')
    git('add', '.')
    git('-c', 'user.name=Local check', '-c', 'user.email=check@example.invalid', 'commit', '-m', 'baseline')
    pieces = [patch('transient.cc', None, 'first\n') + (patch('keep.cc', 'original\n', 'intermediate\n') if net_zero else ''),
              patch('transient.cc', 'first\n', 'second\n') + ('' if net_zero else patch('keep.cc', 'original\n', 'final\n')),
              patch('transient.cc', 'second\n', None) + (patch('keep.cc', 'intermediate\n', 'original\n') if net_zero else '')]
    names = tuple(f'{index:04}.patch' for index in range(1, 4))
    for name, value in zip(names, pieces):
        (patches / name).write_text(value, encoding='utf-8', newline='\n')
        if failure not in ('clean', 'partial'):
            git('apply', str(patches / name))
    if failure == 'partial':
        git('apply', str(patches / names[0]))
    elif failure == 'foreign':
        (root / 'foreign.cc').write_text('foreign\n', encoding='utf-8')
    elif failure == 'resurrected':
        (root / 'transient.cc').write_text('second\n', encoding='utf-8')
    elif failure == 'wrong-bytes':
        (root / 'keep.cc').write_text('wrong\n', encoding='utf-8')
    elif failure == 'missing-patch':
        (patches / names[1]).unlink()
    status = git('status', '--porcelain')
    index = (root / '.git/index').read_bytes()
    files = {path.name: path.read_bytes() for path in root.glob('*.cc')}
    try:
        if failure and not (failure == 'clean' and net_zero):
            with pytest.raises((ValueError, OSError, subprocess.SubprocessError)):
                build._source_patches(root, env, names, patch_directory=patches, complete_chain=True)
        else:
            rows = build._source_patches(root, env, names, patch_directory=patches, complete_chain=True)
            assert rows == [dict(name=name, sha256=hashlib.sha256((patches / name).read_bytes()).hexdigest())
                            for name in names]
            if net_zero:
                assert build._source_patches(root, env, names, patch_directory=patches) == []
            else:
                with pytest.raises(ValueError, match='Unrecognized'):
                    build._source_patches(root, env, names, patch_directory=patches)
    finally:
        assert (root / '.git/index').read_bytes() == index
        assert git('status', '--porcelain') == status
        assert {path.name: path.read_bytes() for path in root.glob('*.cc')} == files


def test_empty_complete_chain_requires_a_clean_checkout(tmp_path):
    env = {**os.environ, 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull}
    def git(*args):
        subprocess.run(['git', *args], cwd=tmp_path, env=env, check=True, capture_output=True)
    git('init')
    git('-c', 'user.name=Local check', '-c', 'user.email=check@example.invalid', 'commit', '--allow-empty', '-m', 'baseline')
    assert build._source_patches(tmp_path, env, (), complete_chain=True) == []
    (tmp_path / 'foreign.cc').write_text('foreign\n', encoding='utf-8')
    with pytest.raises(ValueError, match='Unrecognized'):
        build._source_patches(tmp_path, env, (), complete_chain=True)


def test_net_path_tooling_reconstructs_prior_sources_without_rewriting_runtime_evidence(
        native_tooling_before_net_paths, tmp_path):
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'net-path-tooling-source-upgrade.json').read_bytes())
    assert record['exact_roundtrip_verified'] and record['source_history_roundtrip_verified']
    assert record['real_git_cases_passed'] == 15 and record['selected_chain_patches_verified'] == 76
    assert record['actual_checkout_postguards_passed'] and record['live_indexes_preserved']
    assert record['runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
    manifest = root / 'native/drafts/upstream-156/checkpoints/001-076.json'
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == record['selected_manifest_sha256']
    for row in record['sources']:
        target = tmp_path / row['source']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(native_tooling_before_net_paths['sources'][row['source']])
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error',
                    str(directory / record['patch'])], cwd=tmp_path, check=True,
                   capture_output=True, timeout=15)
    for row in record['sources']:
        assert (tmp_path / row['source']).read_bytes() == (root / row['source']).read_bytes()
