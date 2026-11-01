from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from app.core.native.admission import NativePolicyAdmission
from app.core.native.configuration import NativeConfiguration
from app.core.native.privacy import NativePrivacyPolicy


@pytest.mark.parametrize('mode', ['profile-identity', 'partitioned-privacy'])
def test_explicit_audio_math_version_roundtrips_without_changing_algorithm_arguments(mode):
    previous = NativePrivacyPolicy(surface_policy_version=1, fingerprint_derivation_mode=mode)
    policy = replace(previous, audio_pipeline_version=2)
    assert policy.to_dict() == {**previous.to_dict(), 'audio_pipeline_version': 2}
    assert NativePrivacyPolicy.from_dict(policy.to_dict()) == policy
    assert NativeConfiguration.from_settings(NativeConfiguration(privacy_policy=policy).environment_settings()).privacy_policy == policy
    assert policy.prepared_arguments() == previous.prepared_arguments()
    assert policy.required_capabilities() == ['surface-policy-v1', 'audio-math-v2']
    assert 'audio_pipeline_version' not in previous.to_dict()
    assert 'audio_pipeline_version' not in NativePrivacyPolicy().to_dict()


@pytest.mark.parametrize('version', [True, False, 2.0, '2', 1, 3, -1, None, [], {}])
def test_audio_pipeline_version_rejects_unknown_or_coerced_values(version):
    with pytest.raises(ValueError, match='Audio pipeline version'):
        NativePrivacyPolicy(surface_policy_version=1, fingerprint_derivation_mode='profile-identity',
                            audio_pipeline_version=version).validate()


def test_explicit_audio_pipeline_requires_surface_identity_and_cannot_self_admit():
    with pytest.raises(ValueError, match='explicit surface policy'):
        NativePrivacyPolicy(audio_pipeline_version=2).validate()
    policy = NativePrivacyPolicy(surface_policy_version=1, fingerprint_derivation_mode='profile-identity',
                                 audio_pipeline_version=2)
    admission = NativePolicyAdmission(Path('chrome.exe'), '0' * 64, policy, tuple(policy.required_capabilities()))
    with pytest.raises(ValueError, match='admission'):
        policy.require_verified_runtime(admission)
    with pytest.raises(ValueError, match='admission'):
        policy.require_verified_runtime()


def test_audio_version_archive_recovers_exact_preexisting_surface_host_bytes(host_sources_before_audio_pipeline):
    root = Path(__file__).resolve().parents[1]
    previous = json.loads((root / 'native/drafts/environment/profile-surface-host-source-upgrade.json').read_bytes())
    expected = {row['source']: row['after_sha256'] for row in previous['sources']}
    assert len(host_sources_before_audio_pipeline) == 2
    for name, source in host_sources_before_audio_pipeline.items():
        assert hashlib.sha256(source).hexdigest() == expected[name]


def test_audio_pin_cannot_borrow_surface_only_admission(monkeypatch):
    from app.core.native import admission as gate

    policy = NativePrivacyPolicy(surface_policy_version=1, fingerprint_derivation_mode='profile-identity',
                                 audio_pipeline_version=2)
    checksum = '1' * 64
    monkeypatch.setattr(gate, '_REVIEWED_PACKAGES', {
        checksum: {'platform': gate.sys.platform, 'capabilities': ('surface-policy-v1',)},
    })
    admission = gate.NativePolicyAdmission(Path('chrome.exe'), checksum, policy, tuple(policy.required_capabilities()))
    with pytest.raises(ValueError, match='admission'):
        admission.require_policy(policy)


def test_loading_existing_surface_settings_does_not_silently_pin_audio_version(monkeypatch):
    from app.ui.bridge import browser_settings

    previous = NativePrivacyPolicy(surface_policy_version=1, fingerprint_derivation_mode='profile-identity').to_dict()
    monkeypatch.setattr(browser_settings, 'db_get_browser_engine', lambda: 'native')
    monkeypatch.setattr(browser_settings, 'db_get_camoufox_defaults', dict)
    monkeypatch.setattr(browser_settings, 'db_get_cloakbrowser_defaults', dict)
    monkeypatch.setattr(browser_settings, 'db_get_native_defaults', lambda: {'privacy_policy': previous.copy()})
    bridge = browser_settings.BrowserSettingsBridge()
    assert bridge.nativeSurfacePolicyMode == 'profile-identity'
    assert bridge._native['privacy_policy'] == previous
    bridge.setNativeSurfacePolicyMode('profile-identity')
    assert bridge._native['privacy_policy']['audio_pipeline_version'] == 2
    bridge.setNativeSurfacePolicyMode('')
    assert 'audio_pipeline_version' not in bridge._native['privacy_policy']
