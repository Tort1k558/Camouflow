// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
// Controlled-page API calibration, not fingerprint/automation admission.
async () => {
  const attemptNode = (context) => {
    try {
      const node = context.createDynamicsCompressor();
      const created = node.constructor.name === "DynamicsCompressorNode";
      node.disconnect();
      return { created, error: null };
    } catch (error) {
      return { created: false, error: error.name };
    }
  };
  const live = new AudioContext();
  const frame = document.createElement("iframe");
  try {
    await live.close();
    const closedRealtime = { state: live.state, node: attemptNode(live) };
    const loaded = new Promise((resolve, reject) => {
      frame.onload = resolve;
      frame.onerror = () => reject(new Error("Controlled iframe failed"));
    });
    frame.srcdoc = "<!doctype html><title>Audio lifecycle control</title>";
    document.body.append(frame);
    await loaded;
    const detached = new frame.contentWindow.OfflineAudioContext(1, 128, 44100);
    frame.remove();
    await new Promise((resolve) => setTimeout(resolve, 0));
    return {
      closedRealtime,
      detachedOffline: { state: detached.state, node: attemptNode(detached) },
      frameRemoved: !frame.isConnected,
    };
  } finally {
    frame.remove();
    if (live.state !== "closed") await live.close();
  }
}
