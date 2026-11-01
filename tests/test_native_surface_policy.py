from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re

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


def test_surface_r5_windows_build_evidence_does_not_admit_runtime_features():
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
    assert record['gn_template_sha256'] == hashlib.sha256((root / 'native/args.gn').read_bytes()).hexdigest()
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
