import ast
import hashlib
import json
from pathlib import Path

import pytest

from scripts import native_build as build
from scripts.fetch_native_rebase_sources import source_plan

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/upstream-156-webgpu'


def test_full_webgpu_candidate_preserves_baseline_and_resource_limits():
    baseline = build.load_candidate('upstream-156')
    candidate = build.load_candidate('upstream-156-webgpu')
    manifest = candidate['manifest']
    assert candidate['name'] == 'upstream-156-webgpu'
    assert manifest['patches'][:76] == baseline['manifest']['patches']
    assert len(manifest['patches']) == 116
    assert len(manifest['source_files']) == 268
    assert len(source_plan(manifest)) == 268
    assert manifest['component_batch']['draft_packets'] == 30
    assert manifest['dependencies']['v8'] == baseline['manifest']['dependencies']['v8']
    assert manifest['dependencies']['dawn']['revision'] == '0a2c7df818e285d6db0f085135139cda04cee8bb'
    assert manifest['build'] == baseline['manifest']['build']
    assert candidate['lock']['minimum_free_gib'] == 180
    assert candidate['lock']['build_jobs'] == 4
    for key in ('compiled', 'runtime_verified', 'production_admitted'):
        assert manifest[key] is False


def test_full_candidate_proof_and_original_drafts_are_bound():
    manifest_path = DIRECTORY / 'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    proof = json.loads((DIRECTORY / 'preparation.json').read_bytes())
    assert proof['passed'] and proof['forward_patches'] == proof['reverse_patches'] == 116
    assert proof['upstream_files_restored'] == 268
    assert proof['composed_webgpu_paths_matched'] == 88
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == proof['manifest_sha256']
    generated = []
    for row in manifest['component_batch']['drafts']:
        assert hashlib.sha256((ROOT / row['source']).read_bytes()).hexdigest() == row['sha256']
        generated.extend(row['patches'])
    assert generated == [row['file'] for row in manifest['patches'][76:]]


def test_variant_reuses_only_the_exact_pinned_checkout_family(tmp_path):
    baseline = build.load_candidate('upstream-156')
    candidate = build.load_candidate('upstream-156-webgpu')
    build.candidate_workspace(tmp_path, baseline, claim=True)
    build.candidate_workspace(tmp_path, candidate)
    marker = tmp_path / 'glint-build-candidate.json'
    value = json.loads(marker.read_bytes())
    value['chromium_revision'] = '0' * 40
    marker.write_text(json.dumps(value), encoding='utf-8')
    with pytest.raises(ValueError, match='different revision'):
        build.candidate_workspace(tmp_path, candidate)


def test_variant_cannot_reuse_baseline_dependency_stage_receipts(tmp_path):
    chromium = tmp_path / 'chromium'
    (chromium / 'src').mkdir(parents=True)
    for name in ('src/DEPS', '.gclient', 'camouflow-git-revisions.json', 'camouflow-cipd-installed.json'):
        (chromium / name).write_text('pinned\n', encoding='utf-8')
    baseline = build.load_candidate('upstream-156')
    candidate = build.load_candidate('upstream-156-webgpu')
    build.record_stage(chromium, 'sync', baseline)
    before = build.stage_path(chromium, 'sync').read_bytes()
    with pytest.raises(ValueError, match='inputs changed'):
        build.require_stage(chromium, 'sync', candidate)
    assert build.stage_path(chromium, 'sync').read_bytes() == before


def test_variant_tooling_upgrade_preserves_historical_measured_sources(native_tooling_before_webgpu_candidate):
    source = native_tooling_before_webgpu_candidate['sources']['scripts/native_build.py']
    previous = json.loads((ROOT / 'native/drafts/environment/net-path-tooling-source-upgrade.json').read_bytes())
    assert hashlib.sha256(source).hexdigest() == previous['sources'][0]['after_sha256']


DIAGNOSTICS = ('gpu', 'gpu_readback', 'surfaces', 'worker_startup', 'font_rendering',
               'suite', 'privacy_batch', 'privacy_units', 'audio_compatibility',
               'combined_math', 'webgpu_consistency')
CANDIDATE_TOOLS = tuple(f'scripts/verify_native_{name}.py' for name in DIAGNOSTICS) + (
    'scripts/stage_native_windows.py', 'scripts/package_native_windows.py',
    'scripts/native_windows_toolchain.py', 'scripts/audit_native_upstream.py')


@pytest.mark.parametrize('relative', CANDIDATE_TOOLS)
def test_diagnostic_cli_uses_the_explicit_candidate_registry(relative):
    source = (ROOT / relative).read_text(encoding='utf-8-sig')
    tree = ast.parse(source)
    imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
               and node.module == 'scripts.native_build'
               and any(alias.name == 'CANDIDATES' for alias in node.names)]
    arguments = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute) and node.func.attr == 'add_argument'
                 and node.args and isinstance(node.args[0], ast.Constant)
                 and node.args[0].value == '--candidate']
    assert len(imports) == len(arguments) == 1
    choices = next(item.value for item in arguments[0].keywords if item.arg == 'choices')
    assert isinstance(choices, ast.Name) and choices.id == 'CANDIDATES'


def test_diagnostic_upgrade_recovers_all_previously_measured_sources(diagnostic_sources_before_candidate):
    assert set(diagnostic_sources_before_candidate) == set(CANDIDATE_TOOLS) | {'scripts/native_build.py'}
    for name, value in diagnostic_sources_before_candidate.items():
        assert value != (ROOT / name).read_bytes()
        ast.parse(value.decode('utf-8-sig'))


@pytest.mark.parametrize('name', build.CANDIDATES)
def test_readback_inputs_bind_the_selected_manifest_and_every_patch(name):
    from scripts.verify_native_gpu_readback import probe_inputs

    candidate = build.load_candidate(name)
    measured = probe_inputs(candidate_name=name)
    directory = candidate['directory'].relative_to(ROOT).as_posix()
    assert measured[directory + '/manifest.json'] == candidate['manifest_sha256']
    for row in candidate['manifest']['patches']:
        assert measured[directory + '/patches/' + row['file']] == row['sha256']


@pytest.mark.parametrize('failure', ('baseline-receipt', 'missing-dawn', 'wrong-dawn-revision', 'duplicate-dawn'))
def test_full_candidate_diagnostics_cannot_accept_incomplete_build_receipts(failure):
    from scripts.package_native_windows import validate_build_receipt

    candidate = build.load_candidate('upstream-156-webgpu')
    receipt = {'schema': 1, 'platform': 'win32', 'binary': 'chrome.exe',
               **{key: candidate['lock'][key] for key in
                  ('native_version', 'chromium_revision', 'depot_tools_revision')},
               'candidate_manifest_sha256': candidate['manifest_sha256'],
               'patches': build.expected_candidate_patches(candidate['manifest'])}
    validate_build_receipt(receipt, candidate['lock'], candidate=candidate)
    dawn = next(row for row in receipt['patches'] if row.get('repository') == 'third_party/dawn')
    if failure == 'baseline-receipt':
        baseline = build.load_candidate('upstream-156')
        receipt.update(candidate_manifest_sha256=baseline['manifest_sha256'],
                       patches=build.expected_candidate_patches(baseline['manifest']))
    elif failure == 'missing-dawn':
        receipt['patches'].remove(dawn)
    elif failure == 'wrong-dawn-revision':
        dawn['revision'] = 'f' * 40
    else:
        receipt['patches'].append(dawn.copy())
    with pytest.raises(ValueError):
        validate_build_receipt(receipt, candidate['lock'], candidate=candidate)


@pytest.mark.parametrize('target', ('screenshot-transaction', 'audio-math', 'screen-orientation',
                                   'screen-widget', 'screen-metrics', 'screen-live-main'))
def test_full_candidate_units_reach_resource_checks_without_bypassing_them(tmp_path, monkeypatch, target):
    from scripts import verify_native_privacy_units as units

    class ResourceGateReached(Exception):
        pass

    def preflight(*args, **kwargs):
        assert kwargs['lock'] == build.load_candidate('upstream-156-webgpu')['lock']
        raise ResourceGateReached

    monkeypatch.setattr(units.sys, 'platform', 'win32')
    monkeypatch.setattr(units.build, 'preflight', preflight)
    with pytest.raises(ResourceGateReached):
        units.verify(tmp_path, tmp_path / 'report.json', target=target,
                     candidate_name='upstream-156-webgpu')


@pytest.mark.parametrize('candidate', build.CANDIDATES)
@pytest.mark.parametrize('mode', ('baseline', 'ready'))
@pytest.mark.parametrize('existing', (False, True))
def test_webgpu_transport_is_enabled_only_for_the_explicit_protected_variant(candidate, mode, existing):
    from scripts.verify_native_webgpu_consistency import (
        TRANSPORT_FEATURE,
        transport_arguments,
    )

    arguments = ['--owned-switch', '--disable-features=OtherDisabled']
    if existing:
        arguments.append('--enable-features=OtherEnabled')
    before = arguments.copy()
    actual = transport_arguments(arguments, candidate_name=candidate, mode=mode)
    assert arguments == before
    enabled = [feature for value in actual if value.startswith('--enable-features=')
               for feature in value.partition('=')[2].split(',')]
    assert enabled.count(TRANSPORT_FEATURE) == int(candidate == 'upstream-156-webgpu' and mode == 'ready')
    assert '--owned-switch' in actual and '--disable-features=OtherDisabled' in actual
    if existing:
        assert 'OtherEnabled' in enabled


@pytest.mark.parametrize('arguments', (
    ['--enable-features=A', '--enable-features=B'], ['--enable-features='],
    ['--disable-features=A', '--disable-features=B'],
    ['--enable-features=A,,B'], ['--enable-features=GlintWebGPUPolicyTransportCandidate'],
    ['--enable-features=GlintWebGPUPolicyTransportCandidate<Trial'],
    ['--disable-features=GlintWebGPUPolicyTransportCandidate'], [None], 'not-a-list'))
def test_webgpu_transport_rejects_ambiguous_or_foreign_fixture_overrides(arguments):
    from scripts.verify_native_webgpu_consistency import transport_arguments

    with pytest.raises(ValueError):
        transport_arguments(arguments, candidate_name='upstream-156-webgpu', mode='ready')
