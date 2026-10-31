#include <algorithm>
#include <array>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <thread>
#include <vector>

#include "gpu/command_buffer/service/glint_webgpu_readback_observer.h"
#include "gpu/command_buffer/service/glint_webgpu_wire_filter.h"

namespace {
std::map<WGPUDevice, std::shared_ptr<dawn::native::GlintReadbackObserver>>
    devices;
std::atomic<size_t> queries{0};
size_t assertions = 0;
void Check(bool valid, int line) {
  ++assertions;
  if (!valid) {
    std::fprintf(stderr, "bridge assertion %d\n", line);
    std::exit(1);
  }
}
#define CHECK(value) Check((value), __LINE__)
}  // namespace

// Explicit synthetic boundary: this does not exercise native device
// lookup/locking.
namespace dawn::native {
std::shared_ptr<GlintReadbackObserver> GetGlintReadbackObserver(
    WGPUDevice device) {
  ++queries;
  auto found = devices.find(device);
  return found == devices.end() ? nullptr : found->second;
}
}  // namespace dawn::native

using namespace dawn::native;
using namespace dawn::wire;
using namespace gpu::webgpu;

class Snapshot final : public GlintReadbackSnapshot {
 public:
  explicit Snapshot(std::vector<uint8_t> bytes) : bytes_(std::move(bytes)) {}
  GlintReadbackStatus Read(std::span<const uint8_t>* pixels) const override {
    *pixels = bytes_;
    return GlintReadbackStatus::Ready;
  }
  uint32_t GetWidth() const override { return 16; }
  uint32_t GetHeight() const override { return 16; }
  uint32_t GetRowPitch() const override { return 256; }
  GlintReadbackFormat GetFormat() const override {
    return GlintReadbackFormat::Rgba8Unorm;
  }

 private:
  std::vector<uint8_t> bytes_;
};
std::shared_ptr<GlintWebGPUReadbackObserver> Observer(uint8_t key,
                                                      uint64_t epoch = 7) {
  std::array<uint8_t, 32> seed{};
  for (size_t i = 0; i < seed.size(); ++i) {
    seed[i] = static_cast<uint8_t>(key + i);
  }
  auto policy = std::make_shared<const GlintWebGPUDevicePolicy>(
      std::move(*GlintWebGPUDevicePolicy::Create(1, seed)));
  return std::make_shared<GlintWebGPUReadbackObserver>(policy, epoch,
                                                       GlintReadbackLimits{});
}
int main() {
  const auto device = reinterpret_cast<WGPUDevice>(1);
  const auto buffer = reinterpret_cast<WGPUBuffer>(1);
  auto factory = CreateGlintWebGPUReadbackFilterFactory();
  CHECK(factory != nullptr);
  CHECK(factory->ForDevice(device) == nullptr);
  CHECK(queries == 1);
  std::vector<uint8_t> raw(4096, 0xa5);
  for (size_t y = 0; y < 16; ++y) {
    for (size_t x = 0; x < 16; ++x) {
      const size_t offset = y * 256 + x * 4;
      raw[offset] = static_cast<uint8_t>(x * 17);
      raw[offset + 1] = static_cast<uint8_t>(y * 29 + 31);
      raw[offset + 2] = static_cast<uint8_t>(x * 43 + y * 11);
      raw[offset + 3] = 255;
    }
  }
  const auto original = raw;
  std::vector<uint8_t> previous;
  for (uint8_t key : {uint8_t{1}, uint8_t{2}}) {
    auto observer = Observer(key);
    devices[device] = observer;
    auto filter = factory->ForDevice(device);
    CHECK(filter != nullptr);
    CHECK(filter->Classify(buffer, raw.size(), 0, raw.size()) ==
          BufferReadbackDisposition::Passthrough);
    GlintTextureToBufferCopy copy{};
    copy.destination = {buffer, raw.size()};
    copy.destinationRowPitch = 256;
    copy.width = copy.height = 16;
    copy.format = GlintReadbackFormat::Rgba8Unorm;
    observer->OnTextureToBufferCopy(copy, std::make_unique<Snapshot>(raw));
    CHECK(filter->Classify(buffer, raw.size(), 0, raw.size()) ==
          BufferReadbackDisposition::Protected);
    auto mapped = filter->Prepare(buffer, raw.size(), 0,
                                  std::as_bytes(std::span<const uint8_t>(raw)));
    CHECK(mapped.disposition == BufferReadbackDisposition::Protected &&
          mapped.size == raw.size());
    CHECK(!std::equal(raw.begin(), raw.end(), mapped.bytes.get()));
    CHECK(raw == original);
    if (!previous.empty()) {
      CHECK(!std::equal(previous.begin(), previous.end(), mapped.bytes.get()));
    }
    previous.assign(mapped.bytes.get(), mapped.bytes.get() + mapped.size);
    auto repeat = filter->Prepare(buffer, raw.size(), 0,
                                  std::as_bytes(std::span<const uint8_t>(raw)));
    CHECK(std::equal(previous.begin(), previous.end(), repeat.bytes.get()));
    auto partial = filter->Prepare(
        buffer, raw.size(), 512,
        std::as_bytes(std::span<const uint8_t>(raw).subspan(512, 64)));
    CHECK(partial.disposition == BufferReadbackDisposition::Protected &&
          partial.size == 64);
    CHECK(std::equal(previous.begin() + 512, previous.begin() + 576,
                     partial.bytes.get()));
    std::weak_ptr<GlintWebGPUReadbackObserver> weak = observer;
    devices.erase(device);
    observer.reset();
    CHECK(!weak.expired());
    CHECK(factory->ForDevice(device) == nullptr);
    std::atomic<size_t> successes{0};
    std::array<std::thread, 4> threads;
    for (auto& thread : threads) {
      thread = std::thread([&] {
        for (size_t i = 0; i < 100; ++i) {
          auto result =
              filter->Prepare(buffer, raw.size(), 0,
                              std::as_bytes(std::span<const uint8_t>(raw)));
          if (result.disposition == BufferReadbackDisposition::Protected &&
              result.size == previous.size() &&
              std::equal(previous.begin(), previous.end(),
                         result.bytes.get())) {
            ++successes;
          }
        }
      });
    }
    for (auto& thread : threads) {
      thread.join();
    }
    CHECK(successes == 400);
    filter.reset();
    CHECK(weak.expired());
    CHECK(std::equal(previous.begin(), previous.end(), mapped.bytes.get()));
  }
  devices[device] = Observer(1, 0);
  auto denied = factory->ForDevice(device);
  CHECK(denied != nullptr);
  CHECK(denied->Classify(buffer, raw.size(), 0, raw.size()) ==
        BufferReadbackDisposition::Denied);
  CHECK(denied
            ->Prepare(buffer, raw.size(), 0,
                      std::as_bytes(std::span<const uint8_t>(raw)))
            .disposition == BufferReadbackDisposition::Denied);
  CHECK(queries == 6);
  devices.clear();
  std::printf(
      "{\"passed\":true,\"assertions\":%zu,\"concurrent_maps\":800,\"native_"
      "lookup_mocked\":true}\n",
      assertions);
}
