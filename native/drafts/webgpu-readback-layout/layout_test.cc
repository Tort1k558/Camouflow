#include "webgpu_readback_layout.h"

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <vector>

using namespace glint::candidate;
size_t assertions = 0;
void Check(bool condition, int line) {
  ++assertions;
  if (!condition) {
    std::fprintf(stderr, "Layout assertion failed at line %d\n", line);
    std::exit(1);
  }
}
#define CHECK(value) Check((value), __LINE__)

int main() {
  CHECK(!WebGpuPackedPixelBytes({}));
  constexpr auto rgba = WebGpuPixelFormat::kRgba8Unorm;
  constexpr auto bgra = WebGpuPixelFormat::kBgra8Unorm;
  for (uint32_t iteration = 0; iteration < 1024; ++iteration) {
    const uint32_t width = iteration % 7 + 1;
    const uint32_t height = iteration % 5 + 1;
    const uint64_t offset = (iteration % 8) * 4;
    const uint32_t pitch = height == 1 && iteration % 2 == 0 ? 0 : 256;
    const auto format = iteration % 2 == 0 ? rgba : bgra;
    const WebGpuReadbackLayout layout{offset, pitch, width, height, format};
    const size_t source_size = static_cast<size_t>(offset) + (height - 1) * pitch + width * 4 + 13;
    std::vector<uint8_t> mapped(source_size, 0xa5);
    std::vector<uint8_t> canonical(static_cast<size_t>(width) * height * 4);
    for (size_t i = 0; i < canonical.size(); ++i) {
      canonical[i] = static_cast<uint8_t>((i * 43 + iteration * 17) % 256);
    }
    CHECK(WebGpuPackedPixelBytes(layout) == canonical.size());
    CHECK(StoreWebGpuRgba8(canonical, layout, 0, mapped));
    const auto original = mapped;
    std::vector<uint8_t> extracted(canonical.size(), 0xff);
    CHECK(ExtractWebGpuRgba8(mapped, 0, layout, extracted));
    CHECK(extracted == canonical);
    CHECK(mapped == original);
    for (size_t byte = 0; byte < mapped.size(); ++byte) {
      bool pixel = false;
      if (byte >= offset) {
        const size_t relative = byte - static_cast<size_t>(offset);
        pixel = pitch == 0 ? relative < width * 4
                          : relative / pitch < height && relative % pitch < width * 4;
      }
      if (!pixel) {
        CHECK(mapped[byte] == 0xa5);
      }
    }
    auto partial = std::span<const uint8_t>(mapped).subspan(static_cast<size_t>(offset));
    CHECK(ExtractWebGpuRgba8(partial, offset, layout, extracted));
    CHECK(extracted == canonical);
  }
  const WebGpuReadbackLayout valid{8, 256, 3, 2, rgba};
  std::vector<uint8_t> mapped(284, 0x71), canonical(24, 0x42);
  for (const WebGpuReadbackLayout invalid : {
           WebGpuReadbackLayout{8, 0, 3, 2, rgba},
           WebGpuReadbackLayout{9, 256, 3, 2, rgba},
           WebGpuReadbackLayout{8, 255, 3, 2, rgba},
           WebGpuReadbackLayout{8, 256, 65, 2, rgba},
           WebGpuReadbackLayout{8, 256, 0, 2, rgba},
           WebGpuReadbackLayout{8, 256, 3, 0, rgba},
           WebGpuReadbackLayout{8, 256, 3, 2, static_cast<WebGpuPixelFormat>(255)},
           WebGpuReadbackLayout{std::numeric_limits<uint64_t>::max() - 3, 256, 3, 2, rgba}}) {
    const auto before = mapped;
    const auto target_before = canonical;
    CHECK(!ExtractWebGpuRgba8(mapped, 0, invalid, canonical));
    CHECK(canonical == target_before);
    CHECK(!StoreWebGpuRgba8(canonical, invalid, 0, mapped));
    CHECK(mapped == before);
  }
  CHECK(!WebGpuPackedPixelBytes({0, 256, 0xffffffffu, 0xffffffffu, rgba}));
  CHECK(!ExtractWebGpuRgba8(mapped, 12, valid, canonical));
  CHECK(!ExtractWebGpuRgba8(std::span<const uint8_t>(mapped).first(275), 0, valid, canonical));
  CHECK(ExtractWebGpuRgba8(std::span<const uint8_t>(mapped).first(276), 0, valid, canonical));
  CHECK(!ExtractWebGpuRgba8(mapped, 0, valid, std::span<uint8_t>(canonical).first(23)));
  CHECK(!StoreWebGpuRgba8(std::span<const uint8_t>(canonical).first(23), valid, 0, mapped));
  const WebGpuReadbackLayout one{0, 0, 6, 1, rgba};
  const auto before = mapped;
  CHECK(!ExtractWebGpuRgba8(mapped, 0, one, std::span<uint8_t>(mapped).first(24)));
  CHECK(!StoreWebGpuRgba8(std::span<const uint8_t>(mapped).first(24), one, 0, mapped));
  CHECK(mapped == before);
  CHECK(!ExtractWebGpuRgba8(std::span<const uint8_t>(mapped).subspan(16), 16, valid, canonical));
  CHECK(!ExtractWebGpuRgba8(mapped, std::numeric_limits<uint64_t>::max() - 7,
      {std::numeric_limits<uint64_t>::max() - 7, 0, 1, 1, rgba}, std::span<uint8_t>(canonical).first(4)));
  std::printf("{\"passed\":true,\"property_iterations\":1024,\"assertions\":%zu,\"browser_integrated\":false}\n", assertions);
}
