#include <algorithm>
#include <array>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <vector>

#include "gpu/command_buffer/service/glint_webgpu_readback_observer.h"

using namespace gpu::webgpu;
size_t assertions = 0;
void Check(bool value, int line) {
  ++assertions;
  if (!value) {
    std::fprintf(stderr, "seed assertion %d\n", line);
    std::exit(1);
  }
}
#define CHECK(x) Check((x), __LINE__)

int main() {
  std::array<uint8_t, 32> key{};
  for (size_t i = 0; i < key.size(); ++i) key[i] = static_cast<uint8_t>(i + 1);
  auto policy = std::make_shared<const GlintWebGPUDevicePolicy>(
      std::move(*GlintWebGPUDevicePolicy::Create(3, key)));
  std::array<uint8_t, 32> output{};
  auto denied = [&](GlintWebGPUReadbackObserver& observer) {
    output.fill(173);
    CHECK(!observer.CopyShaderProjectionSeed(output));
    CHECK(std::all_of(output.begin(), output.end(), [](uint8_t v) { return v == 0; }));
  };
  GlintWebGPUReadbackObserver healthy(policy, 7, {});
  CHECK(healthy.CopyShaderProjectionSeed(output));
  CHECK(output == key);
  output.fill(0);
  CHECK(healthy.CopyShaderProjectionSeed(output));
  CHECK(output == key);
  healthy.OnExecutionError();
  denied(healthy);
  healthy.OnExecutionError();
  denied(healthy);
  GlintWebGPUReadbackObserver missing(nullptr, 7, {});
  denied(missing);
  GlintWebGPUReadbackObserver invalid_epoch(policy, 0, {});
  denied(invalid_epoch);
  for (size_t invalid_limit = 0; invalid_limit < 3; ++invalid_limit) {
    GlintReadbackLimits limits;
    if (invalid_limit == 0) limits.buffers = 0;
    if (invalid_limit == 1) limits.snapshots = 0;
    if (invalid_limit == 2) limits.shadow = 0;
    GlintWebGPUReadbackObserver invalid(policy, 7, limits);
    denied(invalid);
  }
  std::array<uint8_t, 32> second_key{};
  second_key.fill(221);
  auto second_policy = std::make_shared<const GlintWebGPUDevicePolicy>(
      std::move(*GlintWebGPUDevicePolicy::Create(3, second_key)));
  GlintWebGPUReadbackObserver isolated(second_policy, 7, {});
  CHECK(isolated.CopyShaderProjectionSeed(output));
  CHECK(output == second_key);
  CHECK(output != key);
  // The native policy remains owned by the observer after the caller drops it.
  second_policy.reset();
  CHECK(isolated.CopyShaderProjectionSeed(output));
  CHECK(output == second_key);

  GlintWebGPUReadbackObserver concurrent(policy, 7, {});
  std::atomic<size_t> errors{0};
  std::atomic<size_t> samples{0};
  std::atomic<bool> start{false};
  std::vector<std::thread> readers;
  for (size_t reader = 0; reader < 4; ++reader) {
    readers.emplace_back([&] {
      while (!start.load(std::memory_order_acquire)) std::this_thread::yield();
      for (size_t sample = 0; sample < 2000; ++sample) {
        std::array<uint8_t, 32> local;
        local.fill(173);
        const bool valid = concurrent.CopyShaderProjectionSeed(local);
        if (valid ? local != key : !std::all_of(local.begin(), local.end(),
                    [](uint8_t v) { return v == 0; })) ++errors;
        ++samples;
      }
    });
  }
  start.store(true, std::memory_order_release);
  while (samples.load() < 100) std::this_thread::yield();
  concurrent.OnExecutionError();
  for (auto& reader : readers) reader.join();
  CHECK(samples == 8000);
  CHECK(errors == 0);
  denied(concurrent);
  CHECK(isolated.CopyShaderProjectionSeed(output));
  CHECK(output == second_key);
  std::printf("{\"passed\":true,\"assertions\":%zu,\"concurrent_samples\":8000,"
              "\"native_gpu_queue_executed\":false}\n", assertions);
}
