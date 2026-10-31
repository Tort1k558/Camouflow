#include "gpu/command_buffer/service/glint_webgpu_readback_observer.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <vector>
#include "gpu/command_buffer/common/glint/canvas_readback_candidate.h"

using namespace dawn::native;
using namespace gpu::webgpu;
size_t assertions = 0;
void Check(bool valid, int line) {
  ++assertions;
  if (!valid) { std::fprintf(stderr, "controller assertion %d\n", line); std::exit(1); }
}
#define CHECK(x) Check((x), __LINE__)

struct Ticket {
  GlintReadbackStatus status = GlintReadbackStatus::Ready;
  size_t destroyed = 0;
};
class Snapshot final : public GlintReadbackSnapshot {
 public:
  Snapshot(Ticket& ticket, std::vector<uint8_t> bytes) : ticket_(ticket), bytes_(std::move(bytes)) {}
  ~Snapshot() override { ++ticket_.destroyed; }
  GlintReadbackStatus Read(std::span<const uint8_t>* pixels) const override {
    if (ticket_.status == GlintReadbackStatus::Ready) *pixels = bytes_;
    return ticket_.status;
  }
  uint32_t GetWidth() const override { return 16; }
  uint32_t GetHeight() const override { return 16; }
  uint32_t GetRowPitch() const override { return 256; }
  GlintReadbackFormat GetFormat() const override { return GlintReadbackFormat::Rgba8Unorm; }
 private:
  Ticket& ticket_;
  std::vector<uint8_t> bytes_;
};
GlintBufferIdentity Buffer(size_t id, uint64_t size = 4096) {
  return {reinterpret_cast<WGPUBuffer>(id), size};
}
GlintTextureToBufferCopy Copy(GlintBufferIdentity buffer) {
  GlintTextureToBufferCopy copy{};
  copy.destination = buffer;
  copy.destinationRowPitch = 256;
  copy.width = copy.height = 16;
  copy.format = GlintReadbackFormat::Rgba8Unorm;
  return copy;
}
std::shared_ptr<const GlintWebGPUDevicePolicy> Policy(uint8_t first = 1) {
  std::array<uint8_t, 32> seed{};
  for (size_t i = 0; i < seed.size(); ++i) seed[i] = static_cast<uint8_t>(first + i);
  return std::make_shared<const GlintWebGPUDevicePolicy>(std::move(*GlintWebGPUDevicePolicy::Create(1, seed)));
}
int main() {
  std::vector<uint8_t> packed(1024);
  for (size_t y = 0; y < 16; ++y) for (size_t x = 0; x < 16; ++x) {
    size_t p = (y * 16 + x) * 4;
    packed[p] = static_cast<uint8_t>(x * 17);
    packed[p + 1] = static_cast<uint8_t>(y * 29 + 31);
    packed[p + 2] = static_cast<uint8_t>(x * 43 + y * 11);
    packed[p + 3] = 255;
  }
  std::vector<uint8_t> raw(4096, 0xa5);
  for (size_t y = 0; y < 16; ++y) std::copy_n(packed.begin() + y * 64, 64, raw.begin() + y * 256);
  auto expected = raw;
  std::array<uint8_t, 32> seed{};
  for (size_t i = 0; i < seed.size(); ++i) seed[i] = static_cast<uint8_t>(i + 1);
  CHECK(glint::candidate::TransformEdgeCoherentCanvas(packed, 16, 16, seed));
  for (size_t y = 0; y < 16; ++y) std::copy_n(packed.begin() + y * 64, 64, expected.begin() + y * 256);
  CHECK(raw != expected);
  const auto policy = Policy();
  const auto buffer = Buffer(1), destination = Buffer(2);
  {
    Ticket ticket;
    GlintWebGPUReadbackObserver observer(policy, 7, {});
    CHECK(observer.IsHealthy());
    CHECK(observer.ClassifyReadMap(buffer, 0, raw.size()) == GlintReadbackMapStatus::Unrelated);
    observer.OnTextureToBufferCopy(Copy(buffer), std::make_unique<Snapshot>(ticket, raw));
    CHECK(observer.ClassifyReadMap(buffer, 0, raw.size()) == GlintReadbackMapStatus::Protected);
    auto first = observer.PrepareReadMap(buffer, 0, raw);
    CHECK(first.status == GlintReadbackMapStatus::Protected && first.size == raw.size());
    CHECK(std::equal(expected.begin(), expected.end(), first.bytes.get()));
    CHECK(ticket.destroyed == 1);
    auto second = observer.PrepareReadMap(buffer, 0, raw);
    CHECK(second.status == GlintReadbackMapStatus::Protected);
    CHECK(std::equal(expected.begin(), expected.end(), second.bytes.get()));
    CHECK(first.bytes.get() != second.bytes.get());
    auto partial = observer.PrepareReadMap(buffer, 512, std::span<const uint8_t>(raw).subspan(512, 64));
    CHECK(partial.status == GlintReadbackMapStatus::Protected && partial.size == 64);
    CHECK(std::equal(expected.begin() + 512, expected.begin() + 576, partial.bytes.get()));
    observer.OnBufferToBufferCopy(buffer, 0, destination, 0, raw.size());
    observer.OnBufferDestroyed(buffer.handle);
    auto copied = observer.PrepareReadMap(destination, 0, raw);
    CHECK(copied.status == GlintReadbackMapStatus::Protected);
    CHECK(std::equal(expected.begin(), expected.end(), copied.bytes.get()));
    observer.OnBufferWrite(destination, 0, raw.size(), GlintBufferWriteKind::KnownBytes);
    CHECK(observer.ClassifyReadMap(destination, 0, raw.size()) == GlintReadbackMapStatus::Unrelated);
    CHECK(std::equal(expected.begin(), expected.end(), first.bytes.get()));
  }
  {
    Ticket ticket{GlintReadbackStatus::Pending};
    GlintWebGPUReadbackObserver observer(policy, 7, {});
    observer.OnTextureToBufferCopy(Copy(buffer), std::make_unique<Snapshot>(ticket, raw));
    CHECK(observer.PrepareReadMap(buffer, 0, raw).status == GlintReadbackMapStatus::Denied);
    CHECK(ticket.destroyed == 0);
    ticket.status = GlintReadbackStatus::Ready;
    CHECK(observer.PrepareReadMap(buffer, 0, raw).status == GlintReadbackMapStatus::Protected);
    CHECK(ticket.destroyed == 1);
  }
  for (auto status : {GlintReadbackStatus::Failed, GlintReadbackStatus::Ready}) {
    Ticket ticket{status};
    GlintWebGPUReadbackObserver observer(policy, 7, {});
    auto bytes = raw;
    if (status == GlintReadbackStatus::Ready) bytes.resize(1);
    observer.OnTextureToBufferCopy(Copy(buffer), std::make_unique<Snapshot>(ticket, bytes));
    CHECK(observer.PrepareReadMap(buffer, 0, raw).status == GlintReadbackMapStatus::Denied);
    CHECK(ticket.destroyed == 1);
    ticket.status = GlintReadbackStatus::Ready;
    CHECK(observer.PrepareReadMap(buffer, 0, raw).status == GlintReadbackMapStatus::Denied);
  }
  {
    GlintWebGPUReadbackObserver observer(policy, 7, {});
    observer.OnTextureToBufferCopy(Copy(buffer), nullptr);
    CHECK(observer.ClassifyReadMap(buffer, 0, raw.size()) == GlintReadbackMapStatus::Denied);
    observer.OnBufferToBufferCopy(buffer, 0, destination, 0, raw.size());
    CHECK(observer.ClassifyReadMap(destination, 0, raw.size()) == GlintReadbackMapStatus::Denied);
  }
  for (auto kind : {GlintBufferWriteKind::KnownBytes, GlintBufferWriteKind::Uncertain}) {
    Ticket ticket;
    GlintWebGPUReadbackObserver observer(policy, 7, {});
    observer.OnTextureToBufferCopy(Copy(buffer), std::make_unique<Snapshot>(ticket, raw));
    observer.OnBufferWrite(buffer, 0, raw.size(), kind);
    CHECK(observer.ClassifyReadMap(buffer, 0, raw.size()) == (kind == GlintBufferWriteKind::KnownBytes ?
          GlintReadbackMapStatus::Unrelated : GlintReadbackMapStatus::Denied));
    CHECK(ticket.destroyed == 1);
  }
  {
    Ticket ticket;
    GlintWebGPUReadbackObserver observer(policy, 7, {});
    observer.OnTextureToBufferCopy(Copy(buffer), std::make_unique<Snapshot>(ticket, raw));
    auto changed = raw;
    changed[0] ^= 1;
    CHECK(observer.PrepareReadMap(buffer, 0, changed).status == GlintReadbackMapStatus::Denied);
    CHECK(observer.PrepareReadMap(buffer, 0, raw).status == GlintReadbackMapStatus::Denied);
  }
  {
    GlintWebGPUReadbackObserver observer(policy, 7, {1, 65536, 65536});
    CHECK(observer.ClassifyReadMap(buffer, 0, 4) == GlintReadbackMapStatus::Unrelated);
    CHECK(observer.ClassifyReadMap(destination, 0, 4) == GlintReadbackMapStatus::Denied);
    CHECK(!observer.IsHealthy());
    CHECK(observer.ClassifyReadMap(buffer, 0, 4) == GlintReadbackMapStatus::Denied);
  }
  {
    GlintWebGPUReadbackObserver observer(policy, 7, {});
    CHECK(observer.ClassifyReadMap(buffer, 4096, 1) == GlintReadbackMapStatus::Denied);
    CHECK(observer.ClassifyReadMap(Buffer(1, 8192), 0, 1) == GlintReadbackMapStatus::Denied);
    CHECK(!observer.IsHealthy());
  }
  for (auto limits : {GlintReadbackLimits{256, 16, 65536}, GlintReadbackLimits{256, 65536, 16}}) {
    Ticket ticket;
    GlintWebGPUReadbackObserver observer(policy, 7, limits);
    observer.OnTextureToBufferCopy(Copy(buffer), std::make_unique<Snapshot>(ticket, raw));
    CHECK(observer.PrepareReadMap(buffer, 0, raw).status == GlintReadbackMapStatus::Denied);
  }
  {
    std::vector<uint8_t> first_bytes;
    for (uint8_t value : {uint8_t{1}, uint8_t{2}}) {
      Ticket ticket;
      GlintWebGPUReadbackObserver observer(Policy(value), 7, {});
      observer.OnTextureToBufferCopy(Copy(buffer), std::make_unique<Snapshot>(ticket, raw));
      auto shadow = observer.PrepareReadMap(buffer, 0, raw);
      CHECK(shadow.status == GlintReadbackMapStatus::Protected);
      if (first_bytes.empty()) first_bytes.assign(shadow.bytes.get(), shadow.bytes.get() + shadow.size);
      else CHECK(!std::equal(first_bytes.begin(), first_bytes.end(), shadow.bytes.get()));
    }
  }
  {
    std::array<Ticket, 32> tickets;
    GlintWebGPUReadbackObserver observer(policy, 7, {256, 2048, 65536});
    for (size_t i = 0; i < tickets.size(); ++i) {
      observer.OnTextureToBufferCopy(Copy(buffer), std::make_unique<Snapshot>(tickets[i], raw));
      CHECK(observer.PrepareReadMap(buffer, 0, raw).status == GlintReadbackMapStatus::Protected);
      observer.OnBufferDestroyed(buffer.handle);
      CHECK(tickets[i].destroyed == 1);
    }
  }
  {
    Ticket ticket;
    GlintWebGPUReadbackObserver observer(policy, 7, {});
    observer.OnTextureToBufferCopy(Copy(buffer), std::make_unique<Snapshot>(ticket, raw));
    std::atomic<size_t> successes{0};
    std::array<std::thread, 4> threads;
    for (auto& thread : threads) thread = std::thread([&] {
      for (size_t i = 0; i < 100; ++i) {
        auto shadow = observer.PrepareReadMap(buffer, 0, raw);
        if (shadow.status == GlintReadbackMapStatus::Protected && shadow.size == raw.size() &&
            std::equal(expected.begin(), expected.end(), shadow.bytes.get())) ++successes;
      }
    });
    for (auto& thread : threads) thread.join();
    CHECK(successes == 400);
    CHECK(ticket.destroyed == 1);
  }
  std::printf("{\"passed\":true,\"assertions\":%zu,\"concurrent_maps\":400}\n", assertions);
}
