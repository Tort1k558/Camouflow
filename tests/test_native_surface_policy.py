import hashlib
import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from app.core.native.admission import NativePolicyAdmission
from app.core.native.configuration import NativeConfiguration
from app.core.native.privacy import NativePrivacyPolicy
from app.core.native.surface_driver import (
    ORIGINAL_DISABLED_FEATURES,
    PARTITIONED_DISABLED_FEATURES,
    surface_driver_arguments,
)


@pytest.mark.parametrize('mode', ['profile-identity', 'partitioned-privacy'])
def test_surface_policy_roundtrip_and_required_capability(mode):
    policy = NativePrivacyPolicy(surface_policy_version=1, fingerprint_derivation_mode=mode)
    assert NativePrivacyPolicy.from_dict(policy.to_dict()) == policy
    assert policy.required_capabilities() == ['surface-policy-v1']
    settings = NativeConfiguration(privacy_policy=policy).environment_settings()
    assert NativeConfiguration.from_settings(settings).privacy_policy == policy
    arguments = policy.prepared_arguments()
    assert '--glint-profile-surface-policy=1' in arguments
    assert '--camouflow-native-privacy-key-service=1' in arguments
    assert '--glint-fingerprint-derivation-mode=' + mode in arguments
    assert not any('bootstrap-test' in argument for argument in arguments)


def test_surface_defaults_do_not_change_legacy_serialization_or_arguments():
    policy = NativePrivacyPolicy()
    assert policy.prepared_arguments() == []
    assert policy.required_capabilities() == []
    assert policy.to_dict() == {
        'cpu_limit': 0, 'memory_limit': 0, 'fonts': [], 'restrict_webrtc': False,
        'conceal_automation': False, 'native_user_agent': False,
        'font_rasterization': 'native',
    }


@pytest.mark.parametrize('version', [True, False, '1', 1.0, None, -1, 2, [], {}])
def test_surface_policy_rejects_unknown_or_coerced_versions(version):
    with pytest.raises(ValueError, match='version'):
        NativePrivacyPolicy(surface_policy_version=version, fingerprint_derivation_mode='profile-identity').validate()


@pytest.mark.parametrize('mode', ['', 'auto', 'PROFILE-IDENTITY', 'profile-identity ', None, 1, True, []])
def test_surface_policy_requires_explicit_known_derivation(mode):
    with pytest.raises(ValueError, match='derivation'):
        NativePrivacyPolicy(surface_policy_version=1, fingerprint_derivation_mode=mode).validate()


def test_surface_mode_cannot_be_requested_without_a_policy_version():
    with pytest.raises(ValueError, match='version'):
        NativePrivacyPolicy(fingerprint_derivation_mode='profile-identity').validate()


@pytest.mark.parametrize('mode', ['profile-identity', 'partitioned-privacy'])
def test_surface_unknown_package_cannot_self_admit(mode):
    policy = NativePrivacyPolicy(surface_policy_version=1, fingerprint_derivation_mode=mode)
    admission = NativePolicyAdmission(Path('chrome.exe'), '0' * 64, policy,
                                      tuple(policy.required_capabilities()))
    with pytest.raises(ValueError, match='admission'):
        policy.require_verified_runtime(admission)
    with pytest.raises(ValueError, match='admission'):
        policy.require_verified_runtime()


def test_surface_driver_override_preserves_unrelated_disabled_features():
    before = ORIGINAL_DISABLED_FEATURES.partition('=')[2].split(',')
    after = PARTITIONED_DISABLED_FEATURES.partition('=')[2].split(',')
    assert before.count('ThirdPartyStoragePartitioning') == 1
    assert after == [feature for feature in before if feature != 'ThirdPartyStoragePartitioning']
    assert after


def test_surface_driver_rejects_unknown_bytes_and_missing_files(tmp_path):
    with pytest.raises(ValueError, match='missing'):
        surface_driver_arguments(tmp_path)
    (tmp_path / 'package/lib').mkdir(parents=True)
    (tmp_path / 'node.exe').write_bytes(b'not a reviewed Node binary')
    (tmp_path / 'package/lib/coreBundle.js').write_bytes(b'not a reviewed driver')
    with pytest.raises(ValueError, match='not reviewed'):
        surface_driver_arguments(tmp_path)


def test_surface_bridge_switch_is_atomic_and_preserves_other_controls(monkeypatch):
    from app.ui.bridge import browser_settings

    monkeypatch.setattr(browser_settings, 'db_get_browser_engine', lambda: 'native')
    monkeypatch.setattr(browser_settings, 'db_get_camoufox_defaults', dict)
    monkeypatch.setattr(browser_settings, 'db_get_cloakbrowser_defaults', dict)
    monkeypatch.setattr(browser_settings, 'db_get_native_defaults',
                        lambda: {'privacy_policy': {'cpu_limit': 4, 'restrict_webrtc': True}})
    bridge = browser_settings.BrowserSettingsBridge()
    changes, messages = [], []
    bridge.changed.connect(lambda: changes.append(True))
    bridge.message.connect(messages.append)
    for mode in ('profile-identity', 'partitioned-privacy', ''):
        bridge.setNativeSurfacePolicyMode(mode)
        policy = NativePrivacyPolicy.from_dict(bridge._native['privacy_policy'])
        assert bridge.nativeSurfacePolicyMode == mode
        assert policy.surface_policy_version == (1 if mode else 0)
        assert policy.audio_pipeline_version == (2 if mode else 0)
        assert policy.cpu_limit == 4 and policy.restrict_webrtc
    assert len(changes) == 3
    before = bridge._native.copy()
    bridge.setNativeSurfacePolicyMode('auto')
    assert bridge._native == before and len(changes) == 3 and len(messages) == 1
    bridge._engine = 'camoufox'
    bridge.setNativeSurfacePolicyMode('profile-identity')
    assert bridge._native == before and len(changes) == 3


@pytest.mark.parametrize('mode', ['profile-identity', 'partitioned-privacy'])
def test_surface_policy_retains_legacy_controls_when_replaced(mode):
    policy = NativePrivacyPolicy(cpu_limit=4, native_user_agent=True)
    upgraded = replace(policy, surface_policy_version=1, fingerprint_derivation_mode=mode)
    assert set(upgraded.required_capabilities()) == {'surface-policy-v1', 'hardware', 'identity'}
    assert set(policy.prepared_arguments()).issubset(upgraded.prepared_arguments())
    assert replace(upgraded, surface_policy_version=0, fingerprint_derivation_mode='') == policy


def test_surface_r5_candidate_preserves_r4_prefix_and_repository_ownership():
    from scripts import native_build as build

    before = build.load_candidate('upstream-156-webgpu-r4')
    candidate = build.load_candidate('upstream-156-webgpu-r5')
    manifest = candidate['manifest']
    assert manifest['patches'][:122] == before['manifest']['patches']
    assert len(manifest['patches']) == 124
    assert manifest['target_revision'] == before['manifest']['target_revision']
    assert manifest['dependencies'] == before['manifest']['dependencies']
    assert manifest['build'] == before['manifest']['build']
    assert manifest['compiled'] is manifest['runtime_verified'] is manifest['production_admitted'] is False
    receipt = build.expected_candidate_patches(manifest)
    dawn = next(row for row in receipt if row['name'].startswith('0124-'))
    assert dawn['repository'] == 'third_party/dawn'
    root = Path(__file__).resolve().parents[1]
    assert (candidate['directory'] / 'patches' / dawn['name']).read_bytes() == (
        root / 'native/drafts/webgpu-shared-swapchain-epoch/dawn-owned.patch').read_bytes()


def test_surface_r5_windows_build_evidence_does_not_admit_runtime_features(native_args_before_serial_links):
    from scripts import native_build as build

    root = Path(__file__).resolve().parents[1]
    candidate = build.load_candidate('upstream-156-webgpu-r5')
    record = json.loads((candidate['directory'] / 'windows-build-observations.json').read_bytes())
    previous = json.loads((root / 'native/drafts/environment/webgpu-r4-runtime-observations.json').read_bytes())
    assert record['compiled'] is True
    assert record['runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
    assert record['candidate_manifest_sha256'] == candidate['manifest_sha256']
    assert record['chromium_revision'] == candidate['manifest']['target_revision']
    assert record['chromium_version'] == candidate['manifest']['target_version']
    assert record['jobs'] == candidate['lock']['build_jobs'] == 4 and record['patches'] == 124
    core = record['runtime_core_sha256_measured']
    assert set(core) == {'chrome.exe', 'chrome.dll', 'chrome_elf.dll'}
    assert all(re.fullmatch('[0-9a-f]{64}', value) for value in core.values())
    assert core['chrome.exe'] == previous['runtime_core']['chrome.exe']
    assert core['chrome.dll'] != previous['runtime_core']['chrome.dll']
    assert record['gn_template_sha256'] == hashlib.sha256(native_args_before_serial_links).hexdigest()
    assert record['siso_executed_steps'] == 62
    assert 0 < record['siso_duration_seconds'] < record['build_stage_duration_seconds']
    assert len(record['changed_source_sha256']) == 14
    swapchain = json.loads((root / 'native/drafts/webgpu-shared-swapchain-epoch/observations.json').read_bytes())
    assert record['changed_source_sha256']['third_party/dawn/src/dawn/native/d3d12/TextureD3D12.cpp'] == swapchain['source_after_sha256']
    assert record['manual_build_output_timestamp_restoration'] is False


def test_surface_r5_native_execution_preserves_exact_case_coverage_without_browser_admission():
    from scripts import native_build as build
    from scripts import verify_native_privacy_units as units

    candidate = build.load_candidate('upstream-156-webgpu-r5')
    record = json.loads((candidate['directory'] / 'native-unit-observations.json').read_bytes())
    assert record['passed'] and record['native_tests_executed'] and record['source_postguards_passed']
    assert record['browser_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
    assert record['candidate_manifest_sha256'] == candidate['manifest_sha256']
    assert record['build_invocations'] == 1 and record['jobs'] == 4
    assert [(row['target'], row['tests']) for row in record['targets']] == [
        ('surface-launch', 41), ('identity-transport', 20), ('worker-surfaces', 55)]
    names = set()
    binaries = set()
    for row in record['targets']:
        path = candidate['directory'] / row['result']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['portable_result_sha256']
        assert b'\r' not in path.read_bytes()
        result = json.loads(path.read_bytes())
        assert row['passed'] and result['errors'] == 0
        units.validate_results(result, target=row['target'])
        names.update((suite['name'], case['name']) for suite in result['testsuites'] for case in suite['testsuite'])
        binaries.add(row['test_binary_sha256'])
    assert len(names) == record['case_executions'] == record['distinct_suite_case_pairs'] == 116
    assert len(binaries) == 1


def test_surface_launch_unit_target_requires_exact_new_and_existing_test_names():
    from scripts import verify_native_privacy_units as units

    root = Path(__file__).resolve().parents[1]
    patch = (root / 'native/drafts/profile-surface-launch/next.patch').read_text(encoding='utf-8-sig')
    required = units.required_tests('surface-launch')
    assert 'surface-launch' in units.SUPPORTED_TARGETS
    assert units.unit_binary_target('surface-launch') == 'content_unittests'
    assert required['NativeSurfaceLaunchTest'] == set(re.findall(r'\+TEST\(NativeSurfaceLaunchTest, (\w+)\)', patch))
    assert len(required['NativeSurfaceLaunchTest']) == 4
    assert required['NativePrivacyBrowserContextTest'] == units.required_tests('identity-contexts')['NativePrivacyBrowserContextTest']
    report = {'tests': sum(map(len, required.values())), 'failures': 0, 'disabled': 0,
              'testsuites': [{'name': suite, 'testsuite': [
                  {'name': case, 'status': 'RUN', 'result': 'COMPLETED'} for case in sorted(cases)
              ]} for suite, cases in required.items()]}
    assert report['tests'] == 41
    units.validate_results(report, target='surface-launch')
    for mutation in ('missing', 'duplicate', 'failed', 'disabled', 'extra'):
        invalid = json.loads(json.dumps(report))
        cases = invalid['testsuites'][-1]['testsuite']
        if mutation == 'missing':
            cases.pop()
        elif mutation == 'duplicate':
            cases[-1] = dict(cases[0])
        elif mutation == 'failed':
            cases[0]['failures'] = [{'failure': 'deliberate'}]
        elif mutation == 'disabled':
            cases[0]['status'] = 'NOTRUN'
        else:
            cases.append({'name': 'Unexpected', 'status': 'RUN', 'result': 'COMPLETED'})
        with pytest.raises(ValueError, match='Native privacy'):
            units.validate_results(invalid, target='surface-launch')


@pytest.mark.parametrize('candidate', [None, 'upstream-156', 'upstream-156-webgpu-r4'])
def test_surface_launch_units_reject_a_candidate_without_the_launch_patch(tmp_path, candidate):
    from scripts import verify_native_privacy_units as units

    with pytest.raises(ValueError, match='exact upstream-156-webgpu-r5'):
        units.verify(tmp_path, tmp_path / 'report.json', target='surface-launch', candidate_name=candidate)


def test_r5_browser_evidence_keeps_failures_separate_from_controlled_rechecks():
    from scripts import native_build as build

    candidate = build.load_candidate('upstream-156-webgpu-r5')
    record = json.loads((candidate['directory'] / 'browser-observations.json').read_bytes())
    compiled = json.loads((candidate['directory'] / 'windows-build-observations.json').read_bytes())
    assert record['candidate_manifest_sha256'] == candidate['manifest_sha256']
    assert record['runtime_assets_sha256'] == compiled['runtime_core_sha256_measured']
    assert record['browser_executed'] and not record['all_browser_gates_passed']
    assert record['privacy_admitted'] is record['production_admitted'] is False
    gates = record['original_batch']['gates']
    assert len(gates) == 11 and sum(row['passed'] for row in gates) == 8
    assert {row['name'] for row in gates if not row['passed']} == {
        'normal-profile-surfaces', 'audio-compatibility', 'audio-math-long-buffer'}
    assert all(row['runtime_postguard_passed'] and not row['remaining_owned_processes'] for row in gates)
    assert len(record['large_canvas_webgpu']['cases']) == 8
    assert all(row['full_png_direct_equal'] and row['shader_edge_samples_equal'] and row['padding_zero']
               for row in record['large_canvas_webgpu']['cases'])
    assert all(row['passed'] and row['source_postguard_passed'] and row['immutable_runtime_passed']
               for row in record['gpu_crash_recovery']['gates'])
    maps = record['array_mip_map_counterfactual']['runs']
    assert {row['candidate'] for row in maps} == {'r4', 'r5'}
    assert len({row['javascript_sha256'] for row in maps}) == 1
    for row in maps:
        assert row['baseline_contexts_passed'] == 8 and len(row['map_failures']) == 16
        assert len({error['context'] for error in row['map_failures']}) == 8
        assert {error['phase'] for error in row['map_failures']} == {'protected-initial', 'protected-restart'}
        assert all(error['error'].startswith('MAP_TEXTURE mip=0 layer=0 sampled=false:')
                   for error in row['map_failures'])
    audio = record['audio']
    assert not audio['long_buffer_first_attempt']['passed']
    recheck = audio['long_buffer_preselected_recheck']
    assert recheck['passed'] and recheck['selection_before_measurement']
    assert recheck['profile_summary']['reference_selectors_covered']
    assert all(row['restart_exact'] and row['unmodified_graphs_exact']
               for row in recheck['profile_summary']['comparisons'])
    assert all(not row['modes']['legacy'] for row in audio['legacy_modes'])
    screenshots = record['driver_screenshots']
    assert not screenshots['first_attempt']['passed'] and not screenshots['root_driver_modified']
    assert screenshots['explicit_automation_recheck']['passed']
    assert all(row['exact_rgba_pixels'] and row['resources_released']
               for row in screenshots['explicit_automation_recheck']['checks'])


def test_subresource_capture_draft_roundtrips_exact_r5_source_without_admission(tmp_path):
    import subprocess

    root = Path(__file__).resolve().parents[1]
    draft = root / 'native/drafts/webgpu-subresource-capture'
    record = json.loads((draft / 'observations.json').read_bytes())
    assert record['hardware_capture_passed'] and record['postguards_passed']
    assert record['selected'] is record['browser_integrated'] is record['production_admitted'] is False
    assert hashlib.sha256((draft / 'next.patch').read_bytes()).hexdigest() == record['patch_sha256']
    assert hashlib.sha256((draft / 'capture_test.cc').read_bytes()).hexdigest() == record['fixture_sha256']
    assert hashlib.sha256((draft / 'check.py').read_bytes()).hexdigest() == record['runner_sha256']
    for path, hashes in record['source_files'].items():
        after = (draft / Path(path).name).read_bytes()
        assert hashlib.sha256(after).hexdigest() == hashes['after_sha256']
        assert record['report_source_sha256'][Path(path).name] == hashes['after_sha256']
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(after)
    patch = str(draft / 'next.patch')
    for reverse, expected in ((True, 'before_sha256'), (False, 'after_sha256')):
        subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', *(['--reverse'] if reverse else []), patch],
                       cwd=tmp_path, check=True, capture_output=True)
        for path, hashes in record['source_files'].items():
            assert hashlib.sha256((tmp_path / path).read_bytes()).hexdigest() == hashes[expected]
    assert {row['sanitizer'] for row in record['runs']} == {'none', 'address'}
    for row in record['runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result']['hardware_adapter'] and row['result']['passed']
        assert row['result']['cases'] == row['result']['budget_cases'] == 32
        assert row['result']['assertions'] == 97072 and not row['result']['browser_integrated']


def test_selected_gpu_subresource_projection_preserves_source_and_hardware_scope(tmp_path):
    import subprocess

    root = Path(__file__).resolve().parents[1]
    draft = root / 'native/drafts/webgpu-subresource-projection'
    record = json.loads((draft / 'observations.json').read_bytes())
    assert record['hardware_projection_passed'] and record['postguards_passed']
    assert record['selected'] is record['browser_integrated'] is record['privacy_admitted'] is False
    assert not record['production_admitted'] and len(record['unresolved']) == 4
    for name, expected in record['source_sha256'].items():
        assert hashlib.sha256((draft / name).read_bytes()).hexdigest() == expected
    capture = root / 'native/drafts/webgpu-subresource-capture/observations.json'
    assert hashlib.sha256(capture.read_bytes()).hexdigest() == record['capture_observations_sha256']
    assert hashlib.sha256((draft / 'next.patch').read_bytes()).hexdigest() == record['patch_sha256']
    for path, hashes in record['source_files'].items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((draft / Path(path).name).read_bytes())
        assert hashlib.sha256(target.read_bytes()).hexdigest() == hashes['after_sha256']
    for reverse, key in ((True, 'before_sha256'), (False, 'after_sha256')):
        subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', *(['--reverse'] if reverse else []),
                        str(draft / 'next.patch')], cwd=tmp_path, check=True, capture_output=True)
        assert all(hashlib.sha256((tmp_path / path).read_bytes()).hexdigest() == row[key]
                   for path, row in record['source_files'].items())
    assert {row['sanitizer'] for row in record['runs']} == {'none', 'address'}
    for row in record['runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        measured = row['result']
        assert measured['passed'] and measured['hardware_adapter'] and measured['cases'] == 32
        assert measured['shared_quota_cases'] == 32 and measured['assertions'] == 99158
        assert measured['typed_texture_consumer_verified'] and measured['original_unchanged']
        assert not measured['browser_integrated']
    shader = (draft / 'edge_projection.hlsl').read_text(encoding='utf-8-sig')
    assert 'Texture2D<float4> InputTexture' in shader and 'InputTexture.Load(' in shader
    runner = (draft / 'check.py').read_text(encoding='utf-8-sig')
    assert 'REPO = ROOT.parents[2]' in runner and "'/I' + str(staging)" in runner


def test_r5_host_regression_record_does_not_promote_browser_or_foreign_edits():
    root = Path(__file__).resolve().parents[1]
    record = json.loads((root / 'native/drafts/upstream-156-webgpu-r5/host-regression-observations.json').read_bytes())
    assert record['passed'] and record['input_postguards_passed'] and record['current_inputs_reverified']
    assert record['counts'] == {'passed': 5481, 'failed': 0, 'skipped': 1}
    assert record['browser_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
    assert record['git_commit_after_run'] == '45a24a194fb996ceb4c00e02ded51b01c2d1e1d7'
    assert record['foreign_dirty_file']['path'] == 'docs/HUB.md'
    assert record['foreign_dirty_file']['included_in_commit'] is False
