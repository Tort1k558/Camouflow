"""Unselected launch contract; no application settings or browser switches installed."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProfileSurfaceLaunchInput:
    policy_version: str | None = None
    key_service_version: str | None = None
    derivation_mode: str = ''
    diagnostic_bootstrap_present: bool = False
    third_party_storage_partitioning: bool = False
    audio_math: bool = False
    webgl_readback: bool = False
    readback_metadata: bool = False
    webgpu_transport: bool = False


def validate_profile_surface_launch(value: ProfileSurfaceLaunchInput) -> str:
    if not isinstance(value, ProfileSurfaceLaunchInput):
        raise TypeError('Expected a typed profile surface launch input')
    if value.policy_version is None:
        return 'absent'
    if (type(value.policy_version) is not str or value.policy_version != '1'
            or type(value.key_service_version) is not str or value.key_service_version != '1'
            or type(value.derivation_mode) is not str
            or value.derivation_mode not in {'profile-identity', 'partitioned-privacy'}
            or type(value.diagnostic_bootstrap_present) is not bool or value.diagnostic_bootstrap_present
            or any(type(flag) is not bool or not flag for flag in (
                value.third_party_storage_partitioning, value.audio_math, value.webgl_readback,
                value.readback_metadata, value.webgpu_transport))):
        return 'invalid'
    return 'validated'
