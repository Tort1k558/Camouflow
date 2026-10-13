// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "canvas_partition_seed.h"

#include "third_party/blink/renderer/core/dom/document.h"
#include "third_party/blink/renderer/core/frame/local_dom_window.h"
#include "third_party/blink/renderer/core/workers/worker_global_scope.h"

namespace glint::candidate {
namespace {
template <typename Scope>
SurfaceSeedResult SeedForScope(const Scope& scope, SurfaceSeedKind kind) {
  if (!scope.GlintSurfacePolicyReady()) {
    return base::unexpected(SurfaceSeedError::kInvalidPolicy);
  }
  switch (kind) {
    case SurfaceSeedKind::kCanvas:
      return scope.GlintCanvasPartitionSeed();
    case SurfaceSeedKind::kWebGL:
      return scope.GlintWebGLPartitionSeed();
    case SurfaceSeedKind::kWebGPU:
      return scope.GlintWebGPUPartitionSeed();
    case SurfaceSeedKind::kAudio:
      return scope.GlintAudioPartitionSeed();
  }
  return base::unexpected(SurfaceSeedError::kUnsupportedKind);
}
}  // namespace

SurfaceSeedResult SurfacePartitionSeed(blink::ExecutionContext* context,
                                      SurfaceSeedKind kind) {
  if (!context) {
    return base::unexpected(SurfaceSeedError::kUnavailableContext);
  }
  if (auto* window = blink::DynamicTo<blink::LocalDOMWindow>(context)) {
    auto* document = window->document();
    if (!document) {
      return base::unexpected(SurfaceSeedError::kUnavailableContext);
    }
    return SeedForScope(*document, kind);
  }
  if (auto* worker = blink::DynamicTo<blink::WorkerGlobalScope>(context)) {
    return SeedForScope(*worker, kind);
  }
  return base::unexpected(SurfaceSeedError::kUnavailableContext);
}

SurfaceSeedResult CanvasPartitionSeed(blink::ExecutionContext* context) {
  return SurfacePartitionSeed(context, SurfaceSeedKind::kCanvas);
}
}  // namespace glint::candidate
