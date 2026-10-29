// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
// Owned OfflineAudioContext compatibility fixtures; not anti-bot admission.
async () => {
  const frames = 512;
  const kinds = ["silence", "identity", "half-gain", "impulse", "stereo", "constant-positive", "constant-negative", "oscillator", "compressor"];
  const rows = [];
  const bytes = (values) => new Uint8Array(values.buffer, values.byteOffset, values.byteLength);
  const equal = (left, right) => left.length === right.length && bytes(left).every((value, index) => value === bytes(right)[index]);
  const hash = async (values) => Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes(values))), (value) => value.toString(16).padStart(2, "0")).join("");

  for (const rate of [44100, 48000]) {
    for (const kind of kinds) {
      for (let repetition = 0; repetition < 3; repetition += 1) {
        const context = new OfflineAudioContext(2, frames, rate);
        const nodes = [];
        const input = context.createBuffer(2, frames, rate);
        const expected = [new Float32Array(frames), new Float32Array(frames)];
        for (let channel = 0; channel < 2; channel += 1) {
          const signal = input.getChannelData(channel);
          for (let index = 0; index < frames; index += 1) {
            const value = kind === "impulse" ? (index === 0 ? 0.5 : 0)
              : kind === "stereo" ? (channel === 0 ? 0.25 : -0.125)
              : ((index % 17) - 8) / 32;
            signal[index] = value;
            expected[channel][index] = kind === "half-gain" ? value / 2 : value;
          }
        }
        let eventBuffer;
        context.oncomplete = (event) => { eventBuffer = event.renderedBuffer; };
        try {
          if (kind === "constant-positive" || kind === "constant-negative") {
            const source = context.createConstantSource();
            source.offset.value = kind === "constant-positive" ? 0.25 : -0.25;
            source.connect(context.destination);
            source.start();
            nodes.push(source);
            expected.forEach((channel) => channel.fill(source.offset.value));
          } else if (kind === "oscillator") {
            const source = context.createOscillator();
            source.frequency.value = 997;
            source.type = "triangle";
            source.connect(context.destination);
            source.start();
            nodes.push(source);
          } else if (kind !== "silence") {
            const source = context.createBufferSource();
            source.buffer = input;
            nodes.push(source);
            if (kind === "half-gain") {
              const gain = context.createGain();
              gain.gain.value = 0.5;
              source.connect(gain).connect(context.destination);
              nodes.push(gain);
            } else if (kind === "compressor") {
              const compressor = context.createDynamicsCompressor();
              source.connect(compressor).connect(context.destination);
              nodes.push(compressor);
            } else {
              source.connect(context.destination);
            }
            source.start();
          }
          if (kind === "silence") expected.forEach((channel) => channel.fill(0));
          const rendered = await context.startRendering();
          const channels = [];
          for (let channel = 0; channel < 2; channel += 1) {
            const first = new Float32Array(rendered.getChannelData(channel));
            const second = new Float32Array(rendered.getChannelData(channel));
            const copied = new Float32Array(frames);
            rendered.copyFromChannel(copied, channel);
            const segmented = new Float32Array(frames);
            for (let offset = 0; offset < frames; offset += 37) {
              rendered.copyFromChannel(segmented.subarray(offset, Math.min(offset + 37, frames)), channel, offset);
            }
            const expectedExact = ["oscillator", "compressor"].includes(kind) ? null : equal(first, expected[channel]);
            const finite = first.every(Number.isFinite);
            channels.push({
              sha256: await hash(first),
              finite,
              expectedExact,
              repeatedExact: equal(first, second),
              copiedExact: equal(first, copied),
              segmentedExact: equal(first, segmented),
              nonzero: first.some((value) => value !== 0),
            });
          }
          const replacement = new Float32Array([0.125, -0.25, 0.5]);
          rendered.copyToChannel(replacement, 0, 23);
          const readBack = new Float32Array(replacement.length);
          rendered.copyFromChannel(readBack, 0, 23);
          const copyMutationExact = equal(replacement, readBack);
          const passed = context.state === "closed" && eventBuffer === rendered && copyMutationExact
            && channels.every((channel) => channel.finite && channel.expectedExact !== false
              && channel.repeatedExact && channel.copiedExact && channel.segmentedExact
              && (kind === "silence" || channel.nonzero));
          rows.push({ kind, rate, repetition, frames: rendered.length, sampleRate: rendered.sampleRate,
            channelCount: rendered.numberOfChannels, closed: context.state === "closed",
            eventSameBuffer: eventBuffer === rendered, copyMutationExact, channels, passed });
        } finally {
          nodes.forEach((node) => node.disconnect());
          context.oncomplete = null;
        }
      }
    }
  }
  const repeatStable = rows.every((row) => {
    const reference = rows.find((candidate) => candidate.kind === row.kind && candidate.rate === row.rate);
    return row.channels.every((channel, index) => channel.sha256 === reference.channels[index].sha256);
  });
  return { schema: 1, scope: "Owned OfflineAudioContext fidelity only", rows,
    repeatStable, passed: rows.length === kinds.length * 6 && rows.every((row) => row.passed) && repeatStable };
}
