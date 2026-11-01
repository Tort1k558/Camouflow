import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.fixture
def native_args_before_serial_links(tmp_path):
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'serial-links-args-upgrade.json').read_bytes())
    base = tmp_path / 'before-serial-links'
    path = base / 'native/args.gn'
    path.parent.mkdir(parents=True)
    value = (root / 'native/args.gn').read_bytes()
    assert hashlib.sha256(value).hexdigest() == record['after_sha256']
    path.write_bytes(value)
    patch = directory / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', str(patch)],
                   cwd=base, check=True, capture_output=True, timeout=15)
    value = path.read_bytes()
    assert hashlib.sha256(value).hexdigest() == record['before_sha256']
    return value


@pytest.fixture
def host_sources_before_audio_pipeline(tmp_path):
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'audio-pipeline-version-host-source-upgrade.json').read_bytes())
    base = tmp_path / 'before-audio-pipeline-version'
    for row in record['sources']:
        path = base / row['source']
        path.parent.mkdir(parents=True, exist_ok=True)
        value = (root / row['source']).read_bytes()
        assert hashlib.sha256(value).hexdigest() == row['after_sha256']
        path.write_bytes(value)
    patch = directory / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', str(patch)],
                   cwd=base, check=True, capture_output=True, timeout=15)
    sources = {row['source']: (base / row['source']).read_bytes() for row in record['sources']}
    assert all(hashlib.sha256(sources[row['source']]).hexdigest() == row['before_sha256'] for row in record['sources'])
    return sources


@pytest.fixture
def host_sources_before_profile_surface(tmp_path, native_args_before_serial_links, host_sources_before_audio_pipeline):
    """Recover manager and GN bytes used by older browser measurements."""
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'profile-surface-host-source-upgrade.json').read_bytes())
    base = tmp_path / 'before-profile-surface-host'
    for row in record['sources']:
        target = base / row['source']
        target.parent.mkdir(parents=True, exist_ok=True)
        value = host_sources_before_audio_pipeline.get(row['source'], (root / row['source']).read_bytes())
        assert hashlib.sha256(value).hexdigest() == row['after_sha256']
        target.write_bytes(value)
    patch = directory / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', '--whitespace=error', str(patch)],
                   cwd=base, check=True, capture_output=True, timeout=15)
    sources = {'native/args.gn': native_args_before_serial_links}
    for row in record['sources']:
        path = base / row['source']
        if row['before_sha256'] is None:
            assert not path.exists()
        else:
            value = path.read_bytes()
            assert hashlib.sha256(value).hexdigest() == row['before_sha256']
            sources[row['source']] = value
    return {'sources': sources,
            'sha256': {name: hashlib.sha256(value).hexdigest() for name, value in sources.items()},
            'absent': {row['source'] for row in record['sources'] if row['before_sha256'] is None}}


@pytest.fixture
def host_sources_before_audio_r8(tmp_path):
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'audio-r8-host-source-upgrade.json').read_bytes())
    base = tmp_path / 'before-audio-r8'
    for row in record['sources']:
        target = base / row['source']
        target.parent.mkdir(parents=True, exist_ok=True)
        value = (root / row['source']).read_bytes()
        assert hashlib.sha256(value).hexdigest() == row['after_sha256']
        target.write_bytes(value)
    patch = directory / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', str(patch)],
                   cwd=base, check=True, capture_output=True, timeout=15)
    sources = {}
    for row in record['sources']:
        value = (base / row['source']).read_bytes()
        assert hashlib.sha256(value).hexdigest() == row['before_sha256']
        sources[row['source']] = value
    return sources


@pytest.fixture
def host_sources_before_webgpu_r7(tmp_path, host_sources_before_audio_r8):
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'webgpu-r7-host-source-upgrade.json').read_bytes())
    base = tmp_path / 'before-webgpu-r7'
    for row in record['sources']:
        target = base / row['source']
        target.parent.mkdir(parents=True, exist_ok=True)
        value = host_sources_before_audio_r8[row['source']]
        assert hashlib.sha256(value).hexdigest() == row['after_sha256']
        target.write_bytes(value)
    patch = directory / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', str(patch)],
                   cwd=base, check=True, capture_output=True, timeout=15)
    sources = {}
    for row in record['sources']:
        value = (base / row['source']).read_bytes()
        assert hashlib.sha256(value).hexdigest() == row['before_sha256']
        sources[row['source']] = value
    return sources


@pytest.fixture
def host_sources_before_webgpu_r6(tmp_path, host_sources_before_webgpu_r7):
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'webgpu-r6-host-source-upgrade.json').read_bytes())
    base = tmp_path / 'before-webgpu-r6'
    for row in record['sources']:
        target = base / row['source']
        target.parent.mkdir(parents=True, exist_ok=True)
        value = host_sources_before_webgpu_r7[row['source']]
        assert hashlib.sha256(value).hexdigest() == row['after_sha256']
        target.write_bytes(value)
    patch = directory / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', str(patch)],
                   cwd=base, check=True, capture_output=True, timeout=15)
    sources = {}
    for row in record['sources']:
        value = (base / row['source']).read_bytes()
        assert hashlib.sha256(value).hexdigest() == row['before_sha256']
        sources[row['source']] = value
    return sources


@pytest.fixture
def host_sources_before_webgpu_r5(tmp_path, host_sources_before_webgpu_r6):
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'webgpu-r5-host-source-upgrade.json').read_bytes())
    base = tmp_path / 'before-webgpu-r5'
    for row in record['sources']:
        target = base / row['source']
        target.parent.mkdir(parents=True, exist_ok=True)
        value = host_sources_before_webgpu_r6[row['source']]
        assert hashlib.sha256(value).hexdigest() == row['after_sha256']
        target.write_bytes(value)
    patch = directory / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', str(patch)],
                   cwd=base, check=True, capture_output=True, timeout=15)
    sources = {}
    for row in record['sources']:
        value = (base / row['source']).read_bytes()
        assert hashlib.sha256(value).hexdigest() == row['before_sha256']
        sources[row['source']] = value
    return sources


@pytest.fixture
def host_sources_before_webgpu_r4(tmp_path, host_sources_before_webgpu_r5):
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'webgpu-r4-host-source-upgrade.json').read_bytes())
    base = tmp_path / 'before-webgpu-r4'
    for row in record['sources']:
        target = base / row['source']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(host_sources_before_webgpu_r5.get(row['source'], (root / row['source']).read_bytes()))
        assert hashlib.sha256(target.read_bytes()).hexdigest() == row['after_sha256']
    patch = directory / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', str(patch)],
                   cwd=base, check=True, capture_output=True, timeout=15)
    sources = dict(host_sources_before_webgpu_r5)
    for row in record['sources']:
        value = (base / row['source']).read_bytes()
        assert hashlib.sha256(value).hexdigest() == row['before_sha256']
        sources[row['source']] = value
    return sources


@pytest.fixture
def host_sources_before_webgpu_r3(tmp_path, host_sources_before_webgpu_r4):
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'webgpu-r3-host-source-upgrade.json').read_bytes())
    base = tmp_path / 'before-webgpu-r3'
    for row in record['sources']:
        target = base / row['source']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(host_sources_before_webgpu_r4.get(row['source'], (root / row['source']).read_bytes()))
        assert hashlib.sha256(target.read_bytes()).hexdigest() == row['after_sha256']
    patch = directory / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', str(patch)],
                   cwd=base, check=True, capture_output=True, timeout=15)
    sources = dict(host_sources_before_webgpu_r4)
    for row in record['sources']:
        value = (base / row['source']).read_bytes()
        assert hashlib.sha256(value).hexdigest() == row['before_sha256']
        sources[row['source']] = value
    return sources


@pytest.fixture
def host_sources_before_webgpu_r2(tmp_path, host_sources_before_webgpu_r3, host_sources_before_profile_surface):
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'webgpu-r2-host-source-upgrade.json').read_bytes())
    base = tmp_path / 'before-webgpu-r2'
    for row in record['sources']:
        target = base / row['source']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(host_sources_before_webgpu_r3.get(row['source'], (root / row['source']).read_bytes()))
        assert hashlib.sha256(target.read_bytes()).hexdigest() == row['after_sha256']
    patch = directory / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', str(patch)],
                   cwd=base, check=True, capture_output=True, timeout=15)
    sources = {**host_sources_before_webgpu_r3,
               **{name: value for name, value in host_sources_before_profile_surface['sources'].items() if name.startswith('app/')}}
    for row in record['sources']:
        value = (base / row['source']).read_bytes()
        assert hashlib.sha256(value).hexdigest() == row['before_sha256']
        sources[row['source']] = value
    return sources


@pytest.fixture
def native_build_before_index_mtime_fix(tmp_path, host_sources_before_webgpu_r2):
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'native-build-racy-index-source-upgrade.json').read_bytes())
    base = tmp_path / 'before-index-mtime-fix'
    target = base / record['source']
    target.parent.mkdir(parents=True)
    target.write_bytes(host_sources_before_webgpu_r2[record['source']])
    assert hashlib.sha256(target.read_bytes()).hexdigest() == record['after_sha256']
    patch = directory / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', str(patch)],
                   cwd=base, check=True, capture_output=True, timeout=15)
    before = target.read_bytes()
    assert hashlib.sha256(before).hexdigest() == record['before_sha256']
    return {**record, 'before_bytes': before}


@pytest.fixture
def diagnostic_sources_before_candidate(tmp_path, native_build_before_index_mtime_fix, host_sources_before_webgpu_r2, host_sources_before_profile_surface):
    """Recover measured diagnostic sources without updating historical evidence."""
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'webgpu-diagnostics-source-upgrade.json').read_bytes())
    base = tmp_path / 'before-webgpu-diagnostics'
    for row in record['sources']:
        target = base / row['source']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(native_build_before_index_mtime_fix['before_bytes']
                           if row['source'] == native_build_before_index_mtime_fix['source']
                           else host_sources_before_webgpu_r2.get(row['source'], (root / row['source']).read_bytes()))
        assert hashlib.sha256(target.read_bytes()).hexdigest() == row['after_sha256']
    patch = directory / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', '--whitespace=error', str(patch)],
                   cwd=base, check=True, capture_output=True, timeout=15)
    sources = dict(host_sources_before_profile_surface['sources'])
    for row in record['sources']:
        data = (base / row['source']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == row['before_normalized_sha256']
        if row['before_newline'] == 'CRLF':
            data = data.replace(b'\n', b'\r\n')
        assert hashlib.sha256(data).hexdigest() == row['before_sha256']
        sources[row['source']] = data
    return sources


def diagnostic_source_text(root, relative, sources):
    data = sources[relative] if relative in sources else (root / relative).read_bytes()
    return data.decode('utf-8-sig').replace('\r\n', '\n')


def diagnostic_source_snapshot(sources, inherited=None):
    result = {'sources': {name: data.decode('utf-8-sig').replace('\r\n', '\n') for name, data in sources.items()},
              'sha256': {name: hashlib.sha256(data).hexdigest() for name, data in sources.items()}}
    if inherited is not None:
        for key in result:
            result[key].update(inherited[key])
    return result


@pytest.fixture
def native_d3d12_sources_before_budget(tmp_path):
    """Keep the capture-only measurements bound to their exact pre-budget sources."""
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'webgpu-d3d12-budget-preparation.json').read_bytes())
    legacy = json.loads((directory / 'webgpu-d3d12-capture-preparation.json').read_bytes())
    base = tmp_path / 'before-d3d12-budget'
    for relative, expected in record['public_source_sha256'].items():
        target = base / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((root / relative).read_text(encoding='utf-8-sig'), encoding='utf-8', newline='\n')
        assert hashlib.sha256(target.read_bytes()).hexdigest() == expected
    upgrade = record['source_upgrade']
    patch = directory / upgrade['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == upgrade['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', '--whitespace=error', str(patch)],
                   cwd=base, check=True, capture_output=True, timeout=15)
    result = {}
    for relative, expected in legacy['public_source_sha256'].items():
        data = (base / relative).read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected
        result[relative] = data
    return result


@pytest.fixture
def native_tooling_before_webgpu_candidate(tmp_path, diagnostic_sources_before_candidate):
    """Recover the exact build tooling measured before the explicit GPU variant."""
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'webgpu-candidate-tooling-source-upgrade.json').read_bytes())
    base = tmp_path / 'before-webgpu-candidate-tooling'
    for row in record['sources']:
        target = base / row['source']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(diagnostic_source_text(root, row['source'], diagnostic_sources_before_candidate),
                          encoding='utf-8', newline='\n')
        assert hashlib.sha256(target.read_bytes()).hexdigest() == row['after_sha256']
    patch = directory / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', '--whitespace=error', str(patch)],
                   cwd=base, check=True, capture_output=True, timeout=15)
    sources = {}
    for row in record['sources']:
        data = (base / row['source']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == row['before_sha256']
        sources[row['source']] = data
    return {'sources': sources}


@pytest.fixture
def native_tooling_before_net_paths(tmp_path, native_tooling_before_webgpu_candidate):
    """Recover the exact pre-net-path source for older measured tooling."""
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'net-path-tooling-source-upgrade.json').read_bytes())
    base = tmp_path / 'before-net-path-tooling'
    for row in record['sources']:
        path = base / row['source']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(native_tooling_before_webgpu_candidate['sources'][row['source']])
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['after_sha256']
    patch = directory / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', '--whitespace=error', str(patch)],
                   cwd=base, check=True, capture_output=True, timeout=15)
    result = {'sources': {}, 'sha256': {}}
    for row in record['sources']:
        data = (base / row['source']).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        assert digest == row['before_sha256']
        result['sources'][row['source']] = data
        result['sha256'][row['source']] = digest
    return result


@pytest.fixture
def native_tooling_before_dawn(tmp_path, native_tooling_before_net_paths, diagnostic_sources_before_candidate):
    """Recover exact tooling/test bytes used by historical runtime records."""
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'dawn-tooling-source-upgrade.json').read_bytes())
    base = tmp_path / 'before-dawn-tooling'
    for row in record['sources']:
        target = base / row['source']
        target.parent.mkdir(parents=True, exist_ok=True)
        if row['source'] in native_tooling_before_net_paths['sources']:
            target.write_bytes(native_tooling_before_net_paths['sources'][row['source']])
        else:
            target.write_text(diagnostic_source_text(root, row['source'], diagnostic_sources_before_candidate),
                              encoding='utf-8', newline='\n')
        assert hashlib.sha256(target.read_bytes()).hexdigest() == row['after_sha256']
    patch = directory / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', '--whitespace=error', str(patch)],
                   cwd=base, check=True, capture_output=True, timeout=15)
    result = {'sources': {}, 'sha256': {}}
    for row in record['sources']:
        value = (base / row['source']).read_bytes()
        digest = hashlib.sha256(value).hexdigest()
        assert digest == row['before_sha256'], row['source']
        result['sources'][row['source']] = value
        result['sha256'][row['source']] = digest
    return result


@pytest.fixture
def native_components_before_capture_lifecycle(tmp_path):
    """Recover exact measured synchronous component sources from the upgrade delta."""
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'webgpu-capture-lifecycle-preparation.json').read_bytes())
    base = tmp_path / 'before-native-capture-lifecycle'
    for row in record['sources']:
        target = base / row['source']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((root / row['source']).read_text(encoding='utf-8-sig'), encoding='utf-8', newline='\n')
    patch = directory / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', '--whitespace=error', str(patch)],
                   cwd=base, check=True, capture_output=True, timeout=15)
    result = {'sources': {}, 'sha256': {}}
    for row in record['sources']:
        target = base / row['source']
        if row['before_sha256'] is None:
            assert not target.exists()
        else:
            value = hashlib.sha256(target.read_bytes()).hexdigest()
            assert value == row['before_sha256'], row['source']
            result['sources'][row['source']] = target.read_bytes()
            result['sha256'][row['source']] = value
    return result


@pytest.fixture
def native_units_before_screenshot(tmp_path, monkeypatch, diagnostic_sources_before_candidate):
    root = Path(__file__).resolve().parents[1]
    relative = 'scripts/verify_native_privacy_units.py'
    directory = tmp_path / 'before-screenshot'
    path = directory / relative
    path.parent.mkdir(parents=True)
    path.write_text(diagnostic_source_text(root, relative, diagnostic_sources_before_candidate), encoding='utf-8', newline='\n')
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', '--whitespace=error',
                    str(root / 'native/drafts/environment/screenshot76-unit-gate.patch')],
                   cwd=directory, check=True, capture_output=True)
    record = json.loads((root / 'native/drafts/environment/screenshot76-selection-observations.json').read_bytes())
    expected = next(row['before_sha256'] for row in record['reversible_gate_archives'] if row['source'] == relative)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    monkeypatch.setattr(sys, 'path', sys.path.copy())
    namespace = {'__file__': str(root / relative), '__name__': '_native_units_before_screenshot'}
    exec(compile(path.read_text(encoding='utf-8'), str(path), 'exec'), namespace)
    return {'path': path, 'namespace': namespace, 'source_sha256': expected}


@pytest.fixture
def native_units_before_orientation(tmp_path, monkeypatch, diagnostic_sources_before_candidate):
    """Reconstruct the measured 001-070 verifier, without rewriting old evidence."""
    root = Path(__file__).resolve().parents[1]
    directory = root / "native/drafts/environment"
    record = json.loads((directory / "screen-orientation71-gate-preparation.json").read_bytes())
    path = tmp_path / record["base_source"]
    path.parent.mkdir(parents=True)
    path.write_text(diagnostic_source_text(root, record["base_source"], diagnostic_sources_before_candidate), encoding="utf-8", newline="\n")
    subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--reverse", "--whitespace=error",
                    str(directory / "screenshot76-unit-gate.patch")], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--reverse", "--whitespace=error",
                    str(directory / "live-screen74-unit-gate.patch")], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--reverse", "--whitespace=error",
                    str(directory / record["patch"])], cwd=tmp_path, check=True, capture_output=True)
    value = hashlib.sha256(path.read_bytes()).hexdigest()
    assert value == record["base_source_sha256"]
    monkeypatch.setattr(sys, "path", sys.path.copy())
    namespace = {"__file__": str(root / record["base_source"]), "__name__": "_native_units_before_orientation"}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
    return {"path": path, "source_sha256": value, "namespace": namespace}


@pytest.fixture
def release_tools_before_72_sha256(tmp_path, native_tooling_before_dawn):
    root = Path(__file__).resolve().parents[1]
    relative = Path("tests/test_release_tools.py")
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_bytes(native_tooling_before_dawn["sources"][relative.as_posix()])
    subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--reverse", "--whitespace=error",
                    str(root / "native/drafts/environment/screenshot76-test-contract.patch")],
                   cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--reverse", "--whitespace=error",
                    str(root / "native/drafts/environment/screen75-test-contract.patch")],
                   cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--reverse", "--whitespace=error",
                    str(root / "native/drafts/environment/linked72-test-contract.patch")],
                   cwd=tmp_path, check=True, capture_output=True)
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def qml_before_delivery_diagnostics_sha256(tmp_path):
    root = Path(__file__).resolve().parents[1]
    relative = Path('tests/test_qml_python_editor.py')
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    target.write_text((root / relative).read_text(encoding='utf-8-sig'), encoding='utf-8', newline='\n')
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', '--whitespace=error',
                    str(root / 'native/drafts/environment/qml-profile-delivery-diagnostics.patch')],
                   cwd=tmp_path, check=True, capture_output=True)
    return hashlib.sha256(target.read_bytes()).hexdigest()


@pytest.fixture
def native70_historical_source_hashes(native_units_before_orientation, recorder_before_document_open_sha256,
                                     storage_before_read_lock_sha256, surface_sources_before_retained,
                                     native_tooling_before_dawn, diagnostic_sources_before_candidate,
                                     historical_source_newlines, host_sources_before_profile_surface):
    root = Path(__file__).resolve().parents[1]
    return {
        **{name: row['measured_sha256'] for name, row in historical_source_newlines.items()},
        **{name: hashlib.sha256(data).hexdigest() for name, data in diagnostic_sources_before_candidate.items()},
        "native/drafts/upstream-156/manifest.json": hashlib.sha256(
            (root / "native/drafts/upstream-156/checkpoints/001-070.json").read_bytes()).hexdigest(),
        **host_sources_before_profile_surface['sha256'],
        **surface_sources_before_retained['sha256'],
        **native_tooling_before_dawn['sha256'],
        "scripts/verify_native_privacy_units.py": native_units_before_orientation["source_sha256"],
        "app/services/scenario_recorder.py": recorder_before_document_open_sha256,
        "app/storage/db.py": storage_before_read_lock_sha256,
    }


@pytest.fixture
def storage_before_read_lock_sha256(tmp_path):
    """Reconstruct the measured storage source without modifying historical evidence."""
    root = Path(__file__).resolve().parents[1]
    relative = Path('app/storage/db.py')
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text((root / relative).read_text(encoding='utf-8-sig'), encoding='utf-8', newline='\n')
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', '--whitespace=error',
                    str(root / 'native/drafts/environment/storage-read-lock74.patch')],
                   cwd=tmp_path, check=True, capture_output=True)
    record = json.loads((root / 'native/drafts/environment/storage-read-lock74-observations.json').read_bytes())
    value = hashlib.sha256(target.read_bytes()).hexdigest()
    assert value == record['before']['source_sha256']
    return value


@pytest.fixture
def nested_runtime_before_selector_sha256(tmp_path):
    root = Path(__file__).resolve().parents[1]
    relative = Path('native/drafts/environment/first-script/nested_formats_runtime.py')
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text((root / relative).read_text(encoding='utf-8-sig'), encoding='utf-8', newline='\n')
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', '--whitespace=error',
                    str(root / 'native/drafts/environment/nested-probe-selector74.patch')],
                   cwd=tmp_path, check=True, capture_output=True)
    return hashlib.sha256(target.read_bytes()).hexdigest()


@pytest.fixture
def protected_runtime_before_surfaces_sha256(tmp_path, surface_sources_before_retained):
    root = Path(__file__).resolve().parents[1]
    relative = Path('native/drafts/environment/first-script/protected_history_runtime.py')
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(surface_sources_before_retained['sources'][relative.as_posix()], encoding='utf-8', newline='\n')
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', '--whitespace=error',
                    str(root / 'native/drafts/environment/protected-surface-history74.patch')],
                   cwd=tmp_path, check=True, capture_output=True)
    record = json.loads((root / 'native/drafts/environment/protected-surface-history74-preparation-observations.json').read_bytes())
    normalized = target.read_bytes()
    assert hashlib.sha256(normalized).hexdigest() == record['before']['normalized_utf8_lf_sha256']
    assert record['before']['newline'] == 'CRLF'
    measured = hashlib.sha256(normalized.replace(b'\n', b'\r\n')).hexdigest()
    assert measured == record['before']['source_sha256']
    return measured


@pytest.fixture
def recorder_before_document_open_sha256(tmp_path):
    """Reconstruct the measured historical source, without rewriting old evidence."""
    root = Path(__file__).resolve().parents[1]
    relative = Path("app/services/scenario_recorder.py")
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    target.write_text((root / relative).read_text(encoding="utf-8-sig"), encoding="utf-8", newline="\n")
    subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--reverse", "--whitespace=error",
                    str(root / "native/drafts/environment/recorder-document-open.patch")],
                   cwd=tmp_path, check=True, capture_output=True)
    record = json.loads((root / "native/drafts/environment/recorder-document-open70-observations.json").read_bytes())
    result = hashlib.sha256(target.read_bytes()).hexdigest()
    assert result == record["source_before"]["normalized_utf8_lf_sha256"] == "b41dc9a12865a0eecf73749b1f69adc70e587f87c14a93973eeff18f60872c8e"
    assert record["source_before"]["raw_sha256"] == "cf37b1e51facc4cf807e0588c2da4869756cbcd170754a3071df261a1817574c"
    return record["source_before"]["raw_sha256"]


@pytest.fixture
def stage_before_python_overlay_sources(tmp_path):
    """Reconstruct the source-bound JS-only build inputs without rewriting evidence."""
    root = Path(__file__).resolve().parents[1]
    names = ("camouflow.spec", "scripts/native_driver_stage.py")
    for name in names:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((root / name).read_text(encoding="utf-8-sig"), encoding="utf-8", newline="\n")
    subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--reverse", "--whitespace=error",
                    str(root / "native/drafts/environment/driver-stage-python-integration.patch")],
                   cwd=tmp_path, check=True, capture_output=True)
    return {name: (tmp_path / name).read_text(encoding="utf-8") for name in names}


@pytest.fixture
def surface_sources_before_retained(tmp_path, worker_sources_before_integration, diagnostic_sources_before_candidate):
    """Reconstruct exact pre-extraction sources; never rewrite historical observations."""
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'retained-document-surfaces-preparation.json').read_bytes())
    base = tmp_path / 'before-retained-document-surfaces'
    for row in record['sources']:
        target = base / row['source']
        target.parent.mkdir(parents=True, exist_ok=True)
        source = (worker_sources_before_integration['sources'][row['source']]
                  if row['source'] in worker_sources_before_integration['sources']
                  else diagnostic_source_text(root, row['source'], diagnostic_sources_before_candidate))
        target.write_text(source,
                          encoding='utf-8', newline='\n')
    patch = directory / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', '--whitespace=error', str(patch)],
                   cwd=base, check=True, capture_output=True, timeout=30)
    result = diagnostic_source_snapshot(diagnostic_sources_before_candidate, worker_sources_before_integration)
    for row in record['sources']:
        target = base / row['source']
        if row['before_sha256'] is None:
            assert not target.exists()
            continue
        normalized = target.read_bytes()
        assert hashlib.sha256(normalized).hexdigest() == row['before_normalized_utf8_lf_sha256']
        assert row['before_newline'] in {'LF', 'CRLF'}
        original = normalized if row['before_newline'] == 'LF' else normalized.replace(b'\n', b'\r\n')
        value = hashlib.sha256(original).hexdigest()
        assert value == row['before_sha256'], row['source']
        result['sha256'][row['source']] = value
        result['sources'][row['source']] = target.read_text(encoding='utf-8')
    return result


@pytest.fixture
def historical_source_newlines():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'native/drafts/environment/historical-source-newlines.json').read_bytes())
    assert manifest['schema'] == 1
    result = {}
    for record in manifest['sources']:
        name = record['source']
        assert name not in result and name in manifest['lf_checkout_sources']
        source = (root / name).read_text(encoding='utf-8-sig').encode('utf-8')
        assert hashlib.sha256(source).hexdigest() == record['canonical_lf_sha256'], name
        lines = source.splitlines(keepends=True)
        alternate = set(record['alternate_eol_lines'])
        assert len(lines) == record['line_count'] and len(alternate) == len(record['alternate_eol_lines'])
        assert alternate and min(alternate) > 0 and max(alternate) <= len(lines)
        assert record['default_eol'] in {'LF', 'CRLF'}
        assert all(lines[index - 1].endswith(b'\n') for index in alternate)
        measured = b''.join(
            line[:-1] + b'\r\n' if line.endswith(b'\n') and
            ((record['default_eol'] == 'CRLF') != (index in alternate)) else line
            for index, line in enumerate(lines, 1))
        assert hashlib.sha256(measured).hexdigest() == record['measured_sha256'], name
        result[name] = {**record, 'measured_bytes': measured}
    return result


@pytest.fixture
def historical_surface_source_sha256(surface_sources_before_retained, native_tooling_before_dawn,
                                    diagnostic_sources_before_candidate, historical_source_newlines,
                                    host_sources_before_profile_surface):
    """Hash reconstructed Audio/GPU and tooling sources used by older runtime records."""
    root = Path(__file__).resolve().parents[1]
    names = {'scripts/verify_native_audio.py', 'scripts/verify_native_gpu.py',
             'scripts/verify_native_gpu_readback.py'}

    def source_sha256(relative, *, normalized=False):
        name = Path(relative).as_posix()
        if name in native_tooling_before_dawn['sources']:
            value = native_tooling_before_dawn['sources'][name]
            if normalized:
                value = value.decode('utf-8-sig').encode('utf-8')
            return hashlib.sha256(value).hexdigest()
        if name in names:
            if normalized:
                source = surface_sources_before_retained['sources'][name].encode('utf-8')
                return hashlib.sha256(source).hexdigest()
            return surface_sources_before_retained['sha256'][name]
        if name in diagnostic_sources_before_candidate:
            value = diagnostic_sources_before_candidate[name]
            if normalized:
                value = value.decode('utf-8-sig').replace('\r\n', '\n').encode('utf-8')
            return hashlib.sha256(value).hexdigest()
        if name in historical_source_newlines:
            return historical_source_newlines[name]['canonical_lf_sha256' if normalized else 'measured_sha256']
        if name in host_sources_before_profile_surface['sources']:
            value = host_sources_before_profile_surface['sources'][name]
            if normalized:
                value = value.decode('utf-8-sig').replace('\r\n', '\n').encode('utf-8')
            return hashlib.sha256(value).hexdigest()
        path = root / name
        source = path.read_text(encoding='utf-8-sig').encode('utf-8') if normalized else path.read_bytes()
        return hashlib.sha256(source).hexdigest()

    return source_sha256


@pytest.fixture
def sources_before_webgpu(tmp_path, diagnostic_sources_before_candidate):
    """Reverse the exact WebGPU packet before checking historical GPU evidence."""
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'retained-webgpu-integration-preparation.json').read_bytes())
    base = tmp_path / 'before-retained-webgpu'
    for row in record['sources']:
        target = base / row['source']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(diagnostic_source_text(root, row['source'], diagnostic_sources_before_candidate), encoding='utf-8', newline='\n')
    patch = directory / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', '--whitespace=error', str(patch)],
                   cwd=base, check=True, capture_output=True, timeout=30)
    result = diagnostic_source_snapshot(diagnostic_sources_before_candidate)
    for row in record['sources']:
        target = base / row['source']
        if row['before_sha256'] is None:
            assert not target.exists()
        else:
            value = hashlib.sha256(target.read_bytes()).hexdigest()
            assert value == row['before_sha256'], row['source']
            result['sha256'][row['source']] = value
            result['sources'][row['source']] = target.read_text(encoding='utf-8')
    return result


@pytest.fixture
def sources_before_gpu_workers(tmp_path, sources_before_webgpu, diagnostic_sources_before_candidate):
    """Reconstruct the measured document-only GPU CLI before worker expansion."""
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'retained-gpu-workers-integration-preparation.json').read_bytes())
    base = tmp_path / 'before-retained-gpu-workers'
    for row in record['sources']:
        target = base / row['source']
        target.parent.mkdir(parents=True, exist_ok=True)
        text = sources_before_webgpu['sources'].get(row['source'])
        if text is None:
            text = diagnostic_source_text(root, row['source'], diagnostic_sources_before_candidate)
        target.write_text(text, encoding='utf-8', newline='\n')
    patch = directory / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', '--whitespace=error', str(patch)],
                   cwd=base, check=True, capture_output=True, timeout=30)
    result = diagnostic_source_snapshot(diagnostic_sources_before_candidate, sources_before_webgpu)
    for row in record['sources']:
        target = base / row['source']
        if row['before_sha256'] is None:
            assert not target.exists()
        else:
            value = hashlib.sha256(target.read_bytes()).hexdigest()
            assert value == row['before_sha256'], row['source']
            result['sha256'][row['source']] = value
            result['sources'][row['source']] = target.read_text(encoding='utf-8')
    return result


@pytest.fixture
def sources_before_retained_gpu(tmp_path, sources_before_gpu_workers, diagnostic_sources_before_candidate):
    """Reverse the GPU opt-in before verifying earlier measured source bindings."""
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'retained-gpu-objects-integration-preparation.json').read_bytes())
    base = tmp_path / 'before-retained-gpu-integration'
    for row in record['sources']:
        target = base / row['source']
        target.parent.mkdir(parents=True, exist_ok=True)
        source = (sources_before_gpu_workers['sources'][row['source']]
                  if row['source'] in sources_before_gpu_workers['sources']
                  else diagnostic_source_text(root, row['source'], diagnostic_sources_before_candidate))
        target.write_text(source, encoding='utf-8', newline='\n')
    patch = directory / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', '--whitespace=error', str(patch)],
                   cwd=base, check=True, capture_output=True, timeout=30)
    result = diagnostic_source_snapshot(diagnostic_sources_before_candidate, sources_before_gpu_workers)
    for row in record['sources']:
        target = base / row['source']
        if row['before_sha256'] is None:
            assert not target.exists()
        else:
            value = hashlib.sha256(target.read_bytes()).hexdigest()
            assert value == row['before_sha256'], row['source']
            result['sha256'][row['source']] = value
            result['sources'][row['source']] = target.read_text(encoding='utf-8')
    return result


@pytest.fixture
def worker_sources_before_integration(tmp_path, sources_before_retained_gpu, diagnostic_sources_before_candidate):
    """Reverse the exact worker integration before reconstructing earlier layers."""
    root = Path(__file__).resolve().parents[1]
    directory = root / 'native/drafts/environment'
    record = json.loads((directory / 'retained-worker-lifecycle-preparation.json').read_bytes())
    base = tmp_path / 'before-worker-integration'
    for row in record['sources']:
        target = base / row['source']
        target.parent.mkdir(parents=True, exist_ok=True)
        source = (sources_before_retained_gpu['sources'][row['source']]
                  if row['source'] in sources_before_retained_gpu['sources']
                  else diagnostic_source_text(root, row['source'], diagnostic_sources_before_candidate))
        target.write_text(source, encoding='utf-8', newline='\n')
    patch = directory / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', '--whitespace=error', str(patch)],
                   cwd=base, check=True, capture_output=True, timeout=30)
    result = diagnostic_source_snapshot(diagnostic_sources_before_candidate, sources_before_retained_gpu)
    for row in record['sources']:
        target = base / row['source']
        if row['before_sha256'] is None:
            assert not target.exists()
        else:
            value = hashlib.sha256(target.read_bytes()).hexdigest()
            assert value == row['before_sha256'], row['source']
            result['sha256'][row['source']] = value
            result['sources'][row['source']] = target.read_text(encoding='utf-8')
    return result
