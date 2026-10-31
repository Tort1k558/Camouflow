#include "glint_webgpu_device_policy.h"

#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <type_traits>
#include <utility>
#include <vector>

using namespace gpu::webgpu;
size_t assertions = 0;
void Check(bool condition, int line) {
  ++assertions;
  if (!condition) {
    std::fprintf(stderr, "Policy assertion failed at line %d\n", line);
    std::exit(1);
  }
}
#define CHECK(value) Check((value), __LINE__)

int main() {
  static_assert(!std::is_copy_constructible_v<GlintWebGPUDevicePolicy>);
  static_assert(!std::is_copy_constructible_v<GlintWebGPUPolicyPacket>);
  std::array<uint8_t, 32> seed{};
  for (size_t index = 0; index < seed.size(); ++index) seed[index] = static_cast<uint8_t>(index * 5 + 7);
  CHECK(!GlintWebGPUDevicePolicy::Create(0, seed));
  CHECK(!GlintWebGPUDevicePolicy::Create(1, std::array<uint8_t, 32>{}));
  for (uint64_t generation : {uint64_t{1}, uint64_t{0x1020304050607080}, std::numeric_limits<uint64_t>::max()}) {
    auto original = GlintWebGPUDevicePolicy::Create(generation, seed);
    CHECK(original.has_value());
    auto encoded = original->Encode();
    CHECK(encoded.has_value() && encoded->bytes().size() == 64);
    auto decoded = GlintWebGPUDevicePolicy::Decode(encoded->bytes());
    CHECK(decoded.has_value() && decoded->Matches(*original));
    CHECK(decoded->generation() == generation);
    CHECK(std::equal(seed.begin(), seed.end(), decoded->seed().begin()));
    for (size_t byte = 0; byte < 8; ++byte) {
      CHECK(encoded->bytes()[8 + byte] == static_cast<uint8_t>(generation >> (byte * 8)));
    }
    auto policy = std::move(*decoded);
    CHECK(decoded->generation() == 0 && !decoded->Encode());
    CHECK(std::all_of(decoded->seed().begin(), decoded->seed().end(), [](uint8_t byte) { return byte == 0; }));
    CHECK(policy.Matches(*original));
    auto packet = std::move(*encoded);
    CHECK(std::all_of(encoded->bytes().begin(), encoded->bytes().end(), [](uint8_t byte) { return byte == 0; }));
    CHECK(GlintWebGPUDevicePolicy::Decode(packet.bytes())->Matches(policy));
  }
  auto original = GlintWebGPUDevicePolicy::Create(1, seed);
  auto packet = original->Encode();
  std::vector<uint8_t> bytes(packet->bytes().begin(), packet->bytes().end());
  for (size_t length = 0; length < bytes.size(); ++length) {
    CHECK(!GlintWebGPUDevicePolicy::Decode(std::span<const uint8_t>(bytes).first(length)));
  }
  auto oversized = bytes;
  oversized.push_back(0);
  CHECK(!GlintWebGPUDevicePolicy::Decode(oversized));
  for (size_t byte = 0; byte < 8; ++byte) {
    auto malformed = bytes;
    malformed[byte] ^= 0x80;
    CHECK(!GlintWebGPUDevicePolicy::Decode(malformed));
  }
  for (size_t byte = 48; byte < 64; ++byte) {
    auto malformed = bytes;
    malformed[byte] = 1;
    CHECK(!GlintWebGPUDevicePolicy::Decode(malformed));
  }
  auto zero_generation = bytes;
  std::fill(zero_generation.begin() + 8, zero_generation.begin() + 16, 0);
  CHECK(!GlintWebGPUDevicePolicy::Decode(zero_generation));
  auto zero_seed = bytes;
  std::fill(zero_seed.begin() + 16, zero_seed.begin() + 48, 0);
  CHECK(!GlintWebGPUDevicePolicy::Decode(zero_seed));
  auto different = bytes;
  different[16] ^= 1;
  CHECK(!GlintWebGPUDevicePolicy::Decode(different)->Matches(*original));
  auto assignment = GlintWebGPUDevicePolicy::Create(2, seed);
  *assignment = std::move(*original);
  CHECK(assignment->generation() == 1 && original->generation() == 0);
  CHECK(!original->Encode());
  auto old_packet = assignment->Encode();
  auto moved_packet = assignment->Encode();
  *old_packet = std::move(*moved_packet);
  CHECK(!GlintWebGPUDevicePolicy::Decode(moved_packet->bytes()));
  CHECK(GlintWebGPUDevicePolicy::Decode(old_packet->bytes())->Matches(*assignment));
  std::printf("{\"passed\":true,\"assertions\":%zu,\"transport_installed\":false}\n", assertions);
}
