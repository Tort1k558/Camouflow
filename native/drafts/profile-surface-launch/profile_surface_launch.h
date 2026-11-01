// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_PROFILE_SURFACE_LAUNCH_DRAFT_H_
#define GLINT_PROFILE_SURFACE_LAUNCH_DRAFT_H_

#include <optional>
#include <string_view>

namespace glint::candidate {

enum class ProfileSurfaceLaunchStatus { kAbsent, kValidated, kInvalid };

struct ProfileSurfaceLaunchInput {
  std::optional<std::string_view> policy_version;
  std::optional<std::string_view> key_service_version;
  std::string_view derivation_mode;
  bool diagnostic_bootstrap_present = false;
  bool third_party_storage_partitioning = false;
  bool audio_math = false;
  bool webgl_readback = false;
  bool readback_metadata = false;
  bool webgpu_transport = false;
};

// Validates launch intent only. BrowserContext key readiness, IPC partition
// authorization and reviewed-package admission remain mandatory later gates.
constexpr ProfileSurfaceLaunchStatus ValidateProfileSurfaceLaunch(
    const ProfileSurfaceLaunchInput& input) {
  if (!input.policy_version.has_value()) {
    return ProfileSurfaceLaunchStatus::kAbsent;
  }
  if (*input.policy_version != "1" || !input.key_service_version.has_value() ||
      *input.key_service_version != "1" || input.diagnostic_bootstrap_present ||
      !input.third_party_storage_partitioning || !input.audio_math ||
      !input.webgl_readback || !input.readback_metadata || !input.webgpu_transport ||
      (input.derivation_mode != "profile-identity" &&
       input.derivation_mode != "partitioned-privacy")) {
    return ProfileSurfaceLaunchStatus::kInvalid;
  }
  return ProfileSurfaceLaunchStatus::kValidated;
}

}  // namespace glint::candidate
#endif
