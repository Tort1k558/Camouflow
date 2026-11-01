#include <cstdio>
#include <cstdlib>
#include <initializer_list>
#include <string_view>

#include "profile_surface_launch.h"

using glint::candidate::ProfileSurfaceLaunchInput;
using glint::candidate::ProfileSurfaceLaunchStatus;
using glint::candidate::ValidateProfileSurfaceLaunch;

int main() {
  size_t checks = 0;
  auto require = [&](ProfileSurfaceLaunchInput input,
                     ProfileSurfaceLaunchStatus expected) {
    if (ValidateProfileSurfaceLaunch(input) != expected) {
      std::fprintf(stderr, "PROFILE_LAUNCH_MISMATCH case=%zu\n", checks);
      std::exit(1);
    }
    ++checks;
  };
  require({}, ProfileSurfaceLaunchStatus::kAbsent);
  for (const auto mode : {"profile-identity", "partitioned-privacy"}) {
    const ProfileSurfaceLaunchInput valid{"1", "1", mode, false, true, true, true, true, true};
    require(valid, ProfileSurfaceLaunchStatus::kValidated);
    for (const auto version : {"", "0", "2", "01", " 1", "1 ", "1\n"}) {
      auto input = valid;
      input.policy_version = version;
      require(input, ProfileSurfaceLaunchStatus::kInvalid);
    }
    auto missing_key = valid;
    missing_key.key_service_version.reset();
    require(missing_key, ProfileSurfaceLaunchStatus::kInvalid);
    for (const auto key : {"", "0", "2", "01"}) {
      auto input = valid;
      input.key_service_version = key;
      require(input, ProfileSurfaceLaunchStatus::kInvalid);
    }
    for (const auto bad_mode : {"", "auto", "PROFILE-IDENTITY"}) {
      auto input = valid;
      input.derivation_mode = bad_mode;
      require(input, ProfileSurfaceLaunchStatus::kInvalid);
    }
    auto mixed = valid;
    mixed.diagnostic_bootstrap_present = true;
    require(mixed, ProfileSurfaceLaunchStatus::kInvalid);
    for (int missing = 0; missing != 5; ++missing) {
      auto input = valid;
      if (missing == 0) input.third_party_storage_partitioning = false;
      if (missing == 1) input.audio_math = false;
      if (missing == 2) input.webgl_readback = false;
      if (missing == 3) input.readback_metadata = false;
      if (missing == 4) input.webgpu_transport = false;
      require(input, ProfileSurfaceLaunchStatus::kInvalid);
    }
    auto absent = valid;
    absent.policy_version.reset();
    absent.key_service_version.reset();
    absent.diagnostic_bootstrap_present = true;
    require(absent, ProfileSurfaceLaunchStatus::kAbsent);
  }
  std::printf("{\"passed\":true,\"checks\":%zu,\"launch_contract_only\":true,"
              "\"browser_integrated\":false}\n", checks);
}
