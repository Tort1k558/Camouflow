#include <crtdbg.h>
#include <windows.h>

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <string_view>
#include <vector>

#include "src/dawn/common/MemoryBlockAllocator.h"
#include "src/dawn/common/Ref.h"
#include "src/dawn/native/CommandAllocator.h"

using dawn::AcquireRef;
using dawn::MemoryBlockAllocator;
using dawn::Ref;
using dawn::native::CommandAllocator;
using dawn::native::CommandIterator;

namespace {
size_t destroyed = 0;
size_t checks = 0;
void Check(bool value) {
    ++checks;
    if (!value) {
        std::abort();
    }
}
class Tracked final : public dawn::RefCounted {
  public:
    explicit Tracked(uint64_t value) : id(value) {}
    ~Tracked() override { ++destroyed; }
    uint64_t id;
};
enum class Kind : uint32_t { Payload = 1, Bundle = 2 };
struct Payload {
    uint64_t id;
    size_t count;
    Ref<Tracked> owner;
};
struct Bundle {
    CommandIterator* commands;
};
struct View {
    Payload* command;
    dawn::ityp::span<size_t, const uint32_t> data;
    dawn::ityp::span<size_t, const Ref<Tracked>> refs;
};

void Append(CommandAllocator* allocator, uint64_t id) {
    auto* command = allocator->Allocate<Payload>(Kind::Payload);
    command->id = id;
    command->count = static_cast<size_t>(id % 5 + 1);
    command->owner = AcquireRef(new Tracked(id));
    auto data = allocator->AllocateData<uint32_t>(command->count);
    for (size_t i = 0; i < data.size(); ++i) {
        data[i] = static_cast<uint32_t>(id ^ i ^ 0xa55a);
    }
    auto refs = allocator->AllocateData<Ref<Tracked>>(command->count);
    for (auto& ref : refs) {
        ref = command->owner;
    }
}

std::unique_ptr<CommandIterator> Make(MemoryBlockAllocator* pool, size_t count) {
    CommandAllocator allocator(pool);
    for (size_t i = 0; i < count; ++i) {
        Append(&allocator, i);
    }
    return std::make_unique<CommandIterator>(std::move(allocator));
}

View ReadPayload(CommandIterator* iterator) {
    auto* command = iterator->NextCommand<Payload>();
    auto data = iterator->NextData<uint32_t>(command->count);
    auto refs = iterator->NextData<Ref<Tracked>>(command->count);
    Check(command->owner && command->owner->id == command->id);
    Check(command->owner->GetRefCountForTesting() == command->count + 1);
    for (size_t i = 0; i < command->count; ++i) {
        Check(data[i] == static_cast<uint32_t>(command->id ^ i ^ 0xa55a));
        Check(refs[i].Get() == command->owner.Get());
    }
    return {command, data, refs};
}

std::vector<View> ReadAll(CommandIterator* iterator) {
    std::vector<View> result;
    Kind kind;
    while (iterator->NextCommandId(&kind)) {
        Check(kind == Kind::Payload);
        result.push_back(ReadPayload(iterator));
    }
    return result;
}

void DestroyPayloads(CommandIterator* iterator) {
    iterator->Reset();
    Kind kind;
    while (iterator->NextCommandId(&kind)) {
        Check(kind == Kind::Payload);
        auto view = ReadPayload(iterator);
        for (const auto& ref : view.refs) {
            ref.~Ref();
        }
        view.command->~Payload();
    }
    iterator->MakeEmptyAsDataWasDestroyed();
}

void PositionCase(size_t blockSize, size_t count, size_t position) {
    MemoryBlockAllocator pool(blockSize, 2);
    const size_t beforeDestroyed = destroyed;
    auto iterator = Make(&pool, count);
    auto baseline =
        iterator->ReadWithoutAdvancing([](CommandIterator* reader) { return ReadAll(reader); });
    Check(baseline.size() == count && pool.GetRecycledBlockCountForTesting() == 0);
    Kind kind;
    for (size_t i = 0; i < position; ++i) {
        Check(iterator->NextCommandId(&kind) && kind == Kind::Payload);
        Check(ReadPayload(iterator.get()).command == baseline[i].command);
    }
    for (size_t repeat = 0; repeat < 3; ++repeat) {
        auto preview = iterator->ReadWithoutAdvancing([&](CommandIterator* outer) {
            outer->Reset();
            auto nested = outer->ReadWithoutAdvancing([](CommandIterator* inner) {
                auto all = ReadAll(inner);
                return std::make_unique<size_t>(all.size());
            });
            Check(*nested == count);
            auto all = ReadAll(outer);
            Check(all.size() == count);
            return all;
        });
        Check(preview.size() == baseline.size());
        for (size_t i = 0; i < count; ++i) {
            Check(preview[i].command == baseline[i].command);
            Check(preview[i].data.data() == baseline[i].data.data());
            Check(preview[i].refs.data() == baseline[i].refs.data());
        }
        const bool accepted = iterator->ReadWithoutAdvancing([](CommandIterator* inner) {
            Kind type;
            if (inner->NextCommandId(&type)) {
                ReadPayload(inner);
            }
            return false;
        });
        Check(!accepted);
        iterator->ReadWithoutAdvancing([](CommandIterator* inner) { inner->Reset(); });
        auto rest =
            iterator->ReadWithoutAdvancing([](CommandIterator* inner) { return ReadAll(inner); });
        Check(rest.size() == count - position);
        for (size_t i = 0; i < rest.size(); ++i) {
            Check(rest[i].command == baseline[position + i].command);
        }
        Check(destroyed == beforeDestroyed && pool.GetRecycledBlockCountForTesting() == 0);
    }
    auto rest = ReadAll(iterator.get());
    Check(rest.size() == count - position);
    // End-of-stream automatically resets the actual Dawn iterator.
    Check(ReadAll(iterator.get()).size() == count);
    DestroyPayloads(iterator.get());
    Check(destroyed == beforeDestroyed + count);
    if (count) {
        Check(pool.GetRecycledBlockCountForTesting() > 0);
    }
    pool.Tick();
    pool.Tick();
    pool.Tick();
    Check(pool.GetRecycledBlockCountForTesting() == 0);
}

void BundleCase() {
    MemoryBlockAllocator pool(128, 2);
    const auto before = destroyed;
    auto first = Make(&pool, 3);
    auto second = Make(&pool, 17);
    CommandAllocator allocator(&pool);
    allocator.Allocate<Bundle>(Kind::Bundle)->commands = first.get();
    allocator.Allocate<Bundle>(Kind::Bundle)->commands = second.get();
    CommandIterator root(std::move(allocator));
    auto visit = [](CommandIterator* reader) {
        size_t count = 0;
        Kind kind;
        while (reader->NextCommandId(&kind)) {
            Check(kind == Kind::Bundle);
            auto* bundle = reader->NextCommand<Bundle>();
            count += bundle->commands->ReadWithoutAdvancing([](CommandIterator* commands) {
                commands->Reset();
                return ReadAll(commands).size();
            });
        }
        return count;
    };
    Check(root.ReadWithoutAdvancing(visit) == 20);
    Check(root.ReadWithoutAdvancing(visit) == 20);
    Check(destroyed == before && visit(&root) == 20);
    root.Reset();
    Kind kind;
    while (root.NextCommandId(&kind)) {
        root.NextCommand<Bundle>()->~Bundle();
    }
    root.MakeEmptyAsDataWasDestroyed();
    DestroyPayloads(first.get());
    DestroyPayloads(second.get());
    Check(destroyed == before + 20);
}

void PoolReuseCase() {
    MemoryBlockAllocator pool(128, 2);
    const size_t before = destroyed;
    auto first = Make(&pool, 17);
    auto original =
        first->ReadWithoutAdvancing([](CommandIterator* reader) { return ReadAll(reader); });
    std::vector<uintptr_t> addresses;
    for (const auto& view : original) {
        addresses.push_back(reinterpret_cast<uintptr_t>(view.command));
    }
    DestroyPayloads(first.get());
    const size_t available = pool.GetRecycledBlockCountForTesting();
    Check(available > 0);
    auto second = Make(&pool, 17);
    Check(pool.GetRecycledBlockCountForTesting() < available);
    auto reused =
        second->ReadWithoutAdvancing([](CommandIterator* reader) { return ReadAll(reader); });
    size_t matching = 0;
    for (const auto& view : reused) {
        matching += std::find(addresses.begin(), addresses.end(),
                              reinterpret_cast<uintptr_t>(view.command)) != addresses.end();
    }
    Check(matching > 0);
    DestroyPayloads(second.get());
    Check(destroyed == before + 34 && pool.GetRecycledBlockCountForTesting() > 0);
    pool.TrimMemory();
    Check(pool.GetRecycledBlockCountForTesting() == 0);
}

void MergeCase() {
    MemoryBlockAllocator pool(128, 2);
    const size_t before = destroyed;
    std::vector<CommandAllocator> allocators;
    allocators.emplace_back(&pool);
    for (size_t i = 0; i < 3; ++i) {
        Append(&allocators.back(), i);
    }
    allocators.emplace_back(&pool);
    for (size_t i = 3; i < 10; ++i) {
        Append(&allocators.back(), i);
    }
    CommandIterator iterator;
    iterator.AcquireCommandBlocks(std::move(allocators));
    auto all =
        iterator.ReadWithoutAdvancing([](CommandIterator* reader) { return ReadAll(reader); });
    Check(all.size() == 10);
    for (size_t i = 0; i < all.size(); ++i) {
        Check(all[i].command->id == i);
    }
    Check(destroyed == before && pool.GetRecycledBlockCountForTesting() == 0);
    DestroyPayloads(&iterator);
    Check(destroyed == before + 10 && pool.GetRecycledBlockCountForTesting() > 0);
}
}  // namespace

int main(int argc, char** argv) {
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX);
    _set_abort_behavior(0, _WRITE_ABORT_MSG | _CALL_REPORTFAULT);
    if (argc == 2) {
        MemoryBlockAllocator pool(128);
        auto iterator = Make(&pool, 1);
        std::unique_ptr<CommandIterator> stolen;
        iterator->ReadWithoutAdvancing([&](CommandIterator* reader) {
            if (std::string_view(argv[1]) == "destroy") {
                DestroyPayloads(reader);
            } else if (std::string_view(argv[1]) == "move") {
                stolen = std::make_unique<CommandIterator>(std::move(*reader));
            } else {
                std::exit(98);
            }
            return false;
        });
        return 99;
    }
    size_t cases = 0;
    for (size_t blockSize : {size_t{128}, size_t{512}}) {
        for (size_t count : {size_t{0}, size_t{1}, size_t{3}, size_t{17}, size_t{65}}) {
            for (size_t position = 0; position <= count; ++position) {
                PositionCase(blockSize, count, position);
                ++cases;
            }
        }
    }
    BundleCase();
    PoolReuseCase();
    MergeCase();
    std::printf(
        "{\"passed\":true,\"position_cases\":%zu,\"checks\":%zu,\"destroyed\":%zu,"
                "\"bundle_like_cases\":1,\"pool_reuse_cases\":1,\"merged_block_cases\":1,"
                "\"native_command_iterator_executed\":true,\"native_memory_pool_executed\":true,"
        "\"standalone_noop_raw_ptr\":true,\"actual_native_device_queue_executed\":false}\n",
        cases, checks, destroyed);
}
