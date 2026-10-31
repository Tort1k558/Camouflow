#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <span>
#include <utility>
#include "gpu/command_buffer/service/glint_webgpu_readback_observer.h"

size_t assertions = 0;
void Check(bool valid, int line) {
  ++assertions;
  if (!valid) { std::fprintf(stderr, "queue assertion %d\n", line); std::exit(1); }
}
#define CHECK(x) Check((x), __LINE__)
#define DAWN_ASSERT(x) CHECK(x)
#define DAWN_LOCAL_VAR(x) x
#define DAWN_APPEND_ERROR_BACKTRACE(x) static_cast<void>(x)
#define TRACE_EVENT(...) static_cast<void>(0)
#define DAWN_TRACE_CATEGORY(x) x
namespace probe {
using Observer = gpu::webgpu::GlintWebGPUReadbackObserver;
using Policy = gpu::webgpu::GlintWebGPUDevicePolicy;
using MapStatus = dawn::native::GlintReadbackMapStatus;
using Identity = dawn::native::GlintBufferIdentity;
using ExecutionSerial = uint64_t;
template <typename T> using Span = std::span<T>;
template <typename T> T* ToBackend(T* value) { return value; }
struct Error { int code; };
class MaybeError {
 public:
  MaybeError() = default;
  MaybeError(std::unique_ptr<Error> error) : error_(std::move(error)) {}
  bool IsError() const { return error_ != nullptr; }
  std::unique_ptr<Error> AcquireError() { return std::move(error_); }
 private:
  std::unique_ptr<Error> error_;
};
MaybeError Failure(int code) { return {std::make_unique<Error>(Error{code})}; }
struct DeviceBase {
  explicit DeviceBase(bool enabled) : enabled(enabled) {
    std::array<uint8_t, 32> key{};
    key.fill(23);
    const auto policy = std::make_shared<const Policy>(std::move(*Policy::Create(1, key)));
    controller = std::make_shared<Observer>(policy, 7, gpu::webgpu::GlintReadbackLimits{});
    const std::array uses{dawn::native::GlintShaderBufferUse{buffer, false, true, 0, 4096, true}};
    controller->OnShaderScope({uses, true, true});
    CHECK(controller->ClassifyReadMap(buffer, 0, 4096) == MapStatus::Denied);
  }
  bool IsLockedByCurrentThreadIfNeeded() const { return true; }
  std::shared_ptr<dawn::native::GlintReadbackObserver> GetGlintReadbackObserver() {
    ++lookups;
    return enabled ? controller : nullptr;
  }
  Identity buffer{reinterpret_cast<WGPUBuffer>(1), 4096};
  std::shared_ptr<Observer> controller;
  bool enabled;
  int lookups = 0;
};
using Device = DeviceBase;
struct CommandRecordingContext {};
class Queue;
struct CommandBufferBase {
  Queue* owner;
  int index;
  MaybeError RecordCommands(CommandRecordingContext*);
};
struct CommandQueue { void* Get() const { return nullptr; } };
struct Pending {
  Queue* owner;
  bool needsSubmit = true;
  bool NeedsSubmit() const { return needsSubmit; }
  MaybeError ExecuteCommandList(Device*, void*);
};
class Queue {
 public:
  Queue(bool enabled, int failure) : device(enabled), failure(failure), mPendingCommands{this} {}
  DeviceBase* GetDevice() { return &device; }
  CommandRecordingContext* GetPendingCommandContext() { return &context; }
  ExecutionSerial GetPendingCommandSerial() const { return 7; }
  void RecycleLastCommandListAfter(ExecutionSerial serial) { CHECK(serial == 7); ++retireCalls; }
  MaybeError NextSerial() { ++serialCalls; return failure == 4 ? Failure(4) : MaybeError{}; }
  MaybeError RecycleUnusedCommandLists() {
    ++recycleCalls; return failure == 5 ? Failure(5) : MaybeError{};
  }
  MaybeError OpenPendingCommands() { ++openCalls; return failure == 6 ? Failure(6) : MaybeError{}; }
  MaybeError SubmitImpl(Span<CommandBufferBase* const> commands);
  MaybeError SubmitPendingCommandsImpl();
  Device device;
  int failure;
  CommandRecordingContext context;
  Pending mPendingCommands;
  CommandQueue mCommandQueue;
  int recordCalls = 0, executeCalls = 0, serialCalls = 0, recycleCalls = 0,
      openCalls = 0, retireCalls = 0;
};
MaybeError CommandBufferBase::RecordCommands(CommandRecordingContext* context) {
  CHECK(context == &owner->context);
  ++owner->recordCalls;
  if (owner->device.enabled) {
    owner->device.controller->OnBufferWrite(owner->device.buffer, 0, 4096,
                                           dawn::native::GlintBufferWriteKind::KnownBytes);
    CHECK(owner->device.controller->ClassifyReadMap(owner->device.buffer, 0, 4096) ==
          MapStatus::Unrelated);
  }
  return owner->failure == index + 1 ? Failure(index + 1) : MaybeError{};
}
MaybeError Pending::ExecuteCommandList(Device* device, void* queue) {
  CHECK(device == &owner->device && queue == nullptr);
  ++owner->executeCalls;
  return owner->failure == 3 ? Failure(3) : MaybeError{};
}

#define DAWN_TRY_WITH_CLEANUP(EXPR, BODY)                                       \
    {                                                                           \
        auto DAWN_LOCAL_VAR(Result) = EXPR;                                     \
        if (DAWN_LOCAL_VAR(Result).IsError()) [[unlikely]] {                    \
            auto DAWN_LOCAL_VAR(Error) = DAWN_LOCAL_VAR(Result).AcquireError(); \
            {BODY} /* comment to force the formatter to insert a newline */     \
            DAWN_APPEND_ERROR_BACKTRACE(DAWN_LOCAL_VAR(Error));                 \
            return {std::move(DAWN_LOCAL_VAR(Error))};                          \
        }                                                                       \
    }                                                                           \
    for (;;)                                                                    \
    break
void NotifyGlintExecutionError(DeviceBase* device) {
    if (auto observer = device->GetGlintReadbackObserver()) {
        observer->OnExecutionError();
    }
}

MaybeError Queue::SubmitImpl(Span<CommandBufferBase* const> commands) {
    CommandRecordingContext* commandContext = GetPendingCommandContext();
    [[maybe_unused]] ExecutionSerial pendingSerial = GetPendingCommandSerial();

    {
        TRACE_EVENT(DAWN_TRACE_CATEGORY("recording"), "CommandBufferD3D12::RecordCommands",
                    "serial", uint64_t{pendingSerial});
        for (CommandBufferBase* commandBuffer : commands) {
            DAWN_TRY_WITH_CLEANUP(ToBackend(commandBuffer)->RecordCommands(commandContext),
                                  { NotifyGlintExecutionError(GetDevice()); });
        }
    }

    return SubmitPendingCommandsImpl();
}

MaybeError Queue::SubmitPendingCommandsImpl() {
    Device* device = ToBackend(GetDevice());
    DAWN_ASSERT(device->IsLockedByCurrentThreadIfNeeded());

    if (!mPendingCommands.NeedsSubmit()) {
        return {};
    }

    DAWN_TRY_WITH_CLEANUP(mPendingCommands.ExecuteCommandList(device, mCommandQueue.Get()),
                          { NotifyGlintExecutionError(device); });
    RecycleLastCommandListAfter(GetPendingCommandSerial());

    // Immediately reopen the command recording context so it is always available.
    DAWN_TRY_WITH_CLEANUP(NextSerial(),
                          { NotifyGlintExecutionError(device); });
    DAWN_TRY_WITH_CLEANUP(RecycleUnusedCommandLists(),
                          { NotifyGlintExecutionError(device); });
    DAWN_TRY_WITH_CLEANUP(OpenPendingCommands(), { NotifyGlintExecutionError(device); });
    return {};
}
}  // namespace probe
int main() {
  using namespace probe;
  for (bool enabled : {false, true}) {
    for (int failure = 0; failure <= 6; ++failure) {
      Queue queue(enabled, failure);
      CommandBufferBase first{&queue, 0}, second{&queue, 1};
      const std::array<CommandBufferBase*, 2> commands{&first, &second};
      auto result = queue.SubmitImpl(commands);
      CHECK(result.IsError() == (failure != 0));
      if (result.IsError()) CHECK(result.AcquireError()->code == failure);
      CHECK(queue.device.lookups == (failure != 0 ? 1 : 0));
      CHECK(queue.recordCalls == (failure == 1 ? 1 : 2));
      CHECK(queue.executeCalls == (failure == 1 || failure == 2 ? 0 : 1));
      CHECK(queue.serialCalls == (failure >= 1 && failure <= 3 ? 0 : 1));
      CHECK(queue.retireCalls == (failure >= 1 && failure <= 3 ? 0 : 1));
      CHECK(queue.recycleCalls == (failure >= 1 && failure <= 4 ? 0 : 1));
      CHECK(queue.openCalls == (failure >= 1 && failure <= 5 ? 0 : 1));
      if (enabled) {
        CHECK(queue.device.controller->IsHealthy() == (failure == 0));
        CHECK(queue.device.controller->ClassifyReadMap(queue.device.buffer, 0, 4096) ==
              (failure == 0 ? MapStatus::Unrelated : MapStatus::Denied));
        if (failure != 0) {
          queue.device.controller->OnBufferWrite(queue.device.buffer, 0, 4096,
                                                dawn::native::GlintBufferWriteKind::KnownBytes);
          CHECK(!queue.device.controller->IsHealthy());
          CHECK(queue.device.controller->ClassifyReadMap(queue.device.buffer, 0, 4096) ==
                MapStatus::Denied);
        }
      }
    }
    for (int failure : {0, 3, 4, 5, 6}) {
      // Pending work may originate from writeBuffer without a command buffer.
      Queue pending(enabled, failure);
      if (enabled) {
        pending.device.controller->OnBufferWrite(pending.device.buffer, 0, 4096,
                                                 dawn::native::GlintBufferWriteKind::KnownBytes);
        CHECK(pending.device.controller->ClassifyReadMap(pending.device.buffer, 0, 4096) ==
              MapStatus::Unrelated);
      }
      auto result = pending.SubmitPendingCommandsImpl();
      CHECK(result.IsError() == (failure != 0));
      if (result.IsError()) CHECK(result.AcquireError()->code == failure);
      CHECK(pending.recordCalls == 0 && pending.executeCalls == 1);
      CHECK(pending.device.lookups == (failure == 0 ? 0 : 1));
      CHECK(pending.serialCalls == (failure == 3 ? 0 : 1));
      CHECK(pending.retireCalls == (failure == 3 ? 0 : 1));
      CHECK(pending.recycleCalls == (failure == 3 || failure == 4 ? 0 : 1));
      CHECK(pending.openCalls == (failure >= 3 && failure <= 5 ? 0 : 1));
      if (enabled) {
        CHECK(pending.device.controller->IsHealthy() == (failure == 0));
        CHECK(pending.device.controller->ClassifyReadMap(pending.device.buffer, 0, 4096) ==
              (failure == 0 ? MapStatus::Unrelated : MapStatus::Denied));
      }
    }
    Queue idle(enabled, 3);
    idle.mPendingCommands.needsSubmit = false;
    CHECK(!idle.SubmitPendingCommandsImpl().IsError());
    CHECK(idle.device.lookups == 0 && idle.executeCalls == 0 && idle.recordCalls == 0);
    CHECK(idle.device.controller->IsHealthy());
  }
  std::printf("{\"passed\":true,\"assertions\":%zu,\"scenarios\":26,"
              "\"source_extracted_queue_control_flow_only\":true,"
              "\"backend_mocked\":true,\"native_gpu_queue_executed\":false}\n", assertions);
}
