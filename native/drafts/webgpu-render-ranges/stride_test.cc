#include <initializer_list>
#include <cstdint>
#include <cstdio>
#include <limits>
struct Pipeline {
  bool vertex = false, instance = false;
  bool UsesVertexIndex() const { return vertex; }
  bool UsesInstanceIndex() const { return instance; }
};
int main() {
  Pipeline pipeline;
  const Pipeline* lastPipeline = &pipeline;
    auto indirectStride = [&](bool indexed) -> uint64_t {
        const uint64_t arguments = indexed ? 5 : 4;
        const uint64_t rootConstants =
            lastPipeline->UsesVertexIndex() || lastPipeline->UsesInstanceIndex() ? 2 : 0;
        return (arguments + rootConstants) * sizeof(uint32_t);
    };
  size_t assertions = 0;
  for (bool indexed : {false, true}) {
    for (bool vertex : {false, true}) {
      for (bool instance : {false, true}) {
        pipeline.vertex = vertex;
        pipeline.instance = instance;
        const uint64_t expected = (indexed ? 20u : 16u) + ((vertex || instance) ? 8u : 0u);
        if (indirectStride(indexed) != expected) return 1;
        ++assertions;
        for (uint32_t count : {0u, 1u, std::numeric_limits<uint32_t>::max()}) {
          const uint64_t bytes = static_cast<uint64_t>(count) * indirectStride(indexed);
          if (bytes != static_cast<uint64_t>(count) * expected) return 2;
          ++assertions;
        }
      }
    }
  }
  std::printf("{\"passed\":true,\"assertions\":%zu,\"source_extracted_stride_only\":true}\n", assertions);
}
