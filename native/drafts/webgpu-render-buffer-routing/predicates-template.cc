#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <span>
#include <vector>

#define DAWN_CHECK(value) do { if (!(value)) std::abort(); } while (false)
template <typename T> using Span = std::span<T>;
using BlockDef = std::vector<std::byte>;
struct MemoryBlockAllocator {};

// Command storage and traversal are a model; the checkpoint below is extracted.
class CommandIterator {
  public:
    explicit CommandIterator(size_t count) {
        for (size_t i = 0; i < count; ++i) mBlocks.emplace_back((i + 1) * 8);
        Reset();
    }
    void Reset() {
        mCurrentBlockIndex = 0;
        mCurrentBlock = mBlocks.empty() ? Span<std::byte>(&sentinel, 1) : Span<std::byte>(mBlocks[0]);
    }
    bool Next() {
        if (mBlocks.empty()) return false;
        if (mCurrentBlock.empty()) {
            if (++mCurrentBlockIndex == mBlocks.size()) { Reset(); return false; }
            mCurrentBlock = mBlocks[mCurrentBlockIndex];
        }
        mCurrentBlock = mCurrentBlock.subspan(8);
        return true;
    }
    auto Cursor() const { return std::pair{mCurrentBlockIndex, mCurrentBlock.data()}; }
    size_t Remaining() const { return mCurrentBlock.size(); }
    /* GLINT_CURSOR */
  private:
    std::vector<BlockDef> mBlocks;
    size_t mCurrentBlockIndex = 0;
    Span<std::byte> mCurrentBlock;
    std::byte sentinel{};
    MemoryBlockAllocator* mPool = nullptr;
};

struct Owner { const void* value; const void* Get() const { return value; } };
struct Buffer { const void* handle; uint64_t size; };
struct Use {
    Buffer buffer;
    bool readable;
    bool writable;
    uint64_t offset;
    uint64_t size;
    bool rangeKnown;
};
struct GlintBoundScope { std::vector<Use> uses; std::vector<Owner> owners; bool textureInputs = false; };
struct RenderPredicates {
    /* GLINT_SCOPE */
};

int main() {
    size_t cursorCases = 0;
    for (size_t blocks = 0; blocks <= 4; ++blocks) {
        const size_t commands = blocks * (blocks + 1) / 2;
        for (size_t position = 0; position <= commands; ++position) {
            CommandIterator iterator(blocks);
            for (size_t i = 0; i < position; ++i) DAWN_CHECK(iterator.Next());
            const auto before = iterator.Cursor();
            const auto remaining = iterator.Remaining();
            auto all = iterator.ReadWithoutAdvancing([&](CommandIterator* outer) {
                outer->Reset();
                size_t count = 0;
                while (outer->Next()) {
                    const auto nestedCursor = outer->Cursor();
                    const auto nestedRemaining = outer->Remaining();
                    const bool rejected = outer->ReadWithoutAdvancing([](CommandIterator* inner) {
                        inner->Reset();
                        inner->Next();
                        return false;
                    });
                    DAWN_CHECK(!rejected && outer->Cursor() == nestedCursor &&
                               outer->Remaining() == nestedRemaining);
                    ++count;
                }
                return std::make_unique<size_t>(count);
            });
            DAWN_CHECK(*all == commands && iterator.Cursor() == before && iterator.Remaining() == remaining);
            ++cursorCases;
            iterator.ReadWithoutAdvancing([](CommandIterator* inner) { inner->Reset(); });
            DAWN_CHECK(iterator.Cursor() == before && iterator.Remaining() == remaining);
            ++cursorCases;
            const bool rejected = iterator.ReadWithoutAdvancing([](CommandIterator* inner) {
                inner->Next();
                return false;
            });
            DAWN_CHECK(!rejected && iterator.Cursor() == before && iterator.Remaining() == remaining);
            ++cursorCases;
            auto value = iterator.ReadWithoutAdvancing([](CommandIterator* inner) {
                inner->Reset();
                while (inner->Next()) {}
                return uint64_t{42};
            });
            DAWN_CHECK(value == 42 && iterator.Cursor() == before && iterator.Remaining() == remaining);
            ++cursorCases;
            iterator.ReadWithoutAdvancing([&](CommandIterator* outer) {
                outer->ReadWithoutAdvancing([](CommandIterator* inner) { while (inner->Next()) {} });
                DAWN_CHECK(outer->Cursor() == before && outer->Remaining() == remaining);
            });
            DAWN_CHECK(iterator.Cursor() == before && iterator.Remaining() == remaining);
            ++cursorCases;
        }
    }
    size_t scopeCases = 0;
    int first = 0, second = 0;
    for (uint64_t offset = 0; offset < 128; ++offset) {
        const GlintBoundScope expected{{{{&first, 4096}, true, false, offset, 32, true}}, {{&first}}, false};
        DAWN_CHECK(RenderPredicates::SameGlintRenderScope(expected, expected));
        ++scopeCases;
        for (size_t fault = 0; fault < 11; ++fault) {
            auto actual = expected;
            switch (fault) {
                case 0: actual.textureInputs = true; break;
                case 1: actual.uses.clear(); break;
                case 2: actual.owners.clear(); break;
                case 3: actual.owners[0].value = &second; break;
                case 4: actual.uses[0].buffer.handle = &second; break;
                case 5: actual.uses[0].buffer.size--; break;
                case 6: actual.uses[0].readable = false; break;
                case 7: actual.uses[0].writable = true; break;
                case 8: actual.uses[0].offset++; break;
                case 9: actual.uses[0].size--; break;
                case 10: actual.uses[0].rangeKnown = false; break;
            }
            DAWN_CHECK(!RenderPredicates::SameGlintRenderScope(expected, actual));
            ++scopeCases;
        }
    }
    // 25 cursor positions, five return/nesting paths each; 128 scopes, 12 paths.
    DAWN_CHECK(cursorCases == 125 && scopeCases == 1536);
    std::puts("{\"passed\":true,\"cursor_cases\":125,\"scope_cases\":1536,"
              "\"backend_mocked\":true,\"actual_native_device_queue_executed\":false}");
}
