// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "canvas_partition_seed.h"

#include "third_party/blink/renderer/core/dom/document.h"
#include "third_party/blink/renderer/core/frame/local_dom_window.h"
#include "third_party/blink/renderer/core/workers/worker_global_scope.h"

namespace glint::candidate {
std::optional<std::array<uint8_t, 32>> CanvasPartitionSeed(
    blink::ExecutionContext* context) {
  if (auto* window = blink::DynamicTo<blink::LocalDOMWindow>(context)) {
    auto* document = window->document();
    return document ? document->GlintCanvasPartitionSeed() : std::nullopt;
  }
  if (auto* worker = blink::DynamicTo<blink::WorkerGlobalScope>(context)) {
    return worker->GlintCanvasPartitionSeed();
  }
  return std::nullopt;
}
}  // namespace glint::candidate
