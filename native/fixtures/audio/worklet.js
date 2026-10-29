async () => {
  const frames = 2048;
  const rows = [];
  const bytes = (value) => new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
  const equal = (left, right) => left.length === right.length && bytes(left).every((value, index) => value === bytes(right)[index]);
  for (const rate of [44100, 48000]) {
    for (const graph of ["identity", "half-gain", "compressor"]) {
      for (let repetition = 0; repetition < 2; repetition += 1) {
        const context = new OfflineAudioContext(1, frames, rate);
        const nodes = [];
        let worklet;
        let timer;
        try {
          await context.audioWorklet.addModule("/glint-audio-worklet.js");
          const input = context.createBuffer(1, frames, rate);
          const signal = input.getChannelData(0);
          for (let index = 0; index < frames; ++index) signal[index] = ((index % 17) - 8) / 32;
          const original = signal.slice();
          const source = context.createBufferSource();
          source.buffer = input;
          worklet = new AudioWorkletNode(context, "owned-audio-copy", {numberOfInputs: 1, numberOfOutputs: 1,
            outputChannelCount: [1], channelCount: 1, channelCountMode: "explicit", processorOptions: {frames}});
          nodes.push(source, worklet);
          if (graph === "identity") {
            source.connect(worklet);
          } else {
            const processor = graph === "half-gain" ? context.createGain() : context.createDynamicsCompressor();
            if (graph === "half-gain") processor.gain.value = 0.5;
            nodes.push(processor);
            source.connect(processor).connect(worklet);
          }
          worklet.connect(context.destination);
          const reconstructed = new Float32Array(frames);
          reconstructed.fill(NaN);
          const coverage = new Uint8Array(frames);
          const packets = [];
          const completed = new Promise((resolve, reject) => {
            timer = setTimeout(() => reject(new Error("Owned AudioWorklet completion timeout")), 10000);
            worklet.onprocessorerror = () => reject(new Error("Owned AudioWorklet processor error"));
            worklet.port.onmessage = ({data}) => {
              try {
                if (!Number.isInteger(data.offset) || data.offset < 0 || !(data.samples instanceof Float32Array)
                    || !data.samples.length || data.offset + data.samples.length > frames) {
                  throw new Error("Invalid owned worklet packet");
                }
                reconstructed.set(data.samples, data.offset);
                for (let index = data.offset; index < data.offset + data.samples.length; ++index) {
                  if (coverage[index]) throw new Error("Overlapping owned worklet packet");
                  coverage[index] = 1;
                }
                packets.push({offset: data.offset, length: data.samples.length, rate: data.rate, time: data.time});
                if (data.complete) resolve();
              } catch (error) { reject(error); }
            };
          });
          source.start();
          const [rendered] = await Promise.all([context.startRendering(), completed]);
          const output = rendered.getChannelData(0);
          const copied = new Float32Array(frames);
          rendered.copyFromChannel(copied, 0);
          const expected = graph === "compressor" ? null : Float32Array.from(original, (value) =>
            graph === "half-gain" ? value * 0.5 : value);
          const checks = {
            closed: context.state === "closed",
            formatPreserved: rendered.sampleRate === rate && rendered.length === frames && rendered.numberOfChannels === 1,
            allFramesCoveredExactlyOnce: coverage.every((value) => value === 1),
            workletSampleRateExact: packets.every((packet) => packet.rate === rate),
            workletTimelineCoherent: packets.every((packet) => Number.isFinite(packet.time) && Math.abs(packet.time - packet.offset / rate) < 1e-9),
            workletDataFinite: reconstructed.every(Number.isFinite),
            workletSignalNonzero: reconstructed.some((value) => value !== 0),
            workletMatchesRendered: equal(reconstructed, output),
            readApisAgree: equal(copied, output),
            linearGraphExact: expected === null || equal(expected, output),
            sourceBufferUnchanged: equal(original, input.getChannelData(0)),
          };
          rows.push({rate, graph, repetition, packetCount: packets.length, checks, passed: Object.values(checks).every(Boolean)});
        } finally {
          clearTimeout(timer);
          if (worklet) {
            worklet.port.onmessage = null;
            worklet.onprocessorerror = null;
            worklet.port.close();
          }
          for (const node of nodes) node.disconnect();
        }
      }
    }
  }
  return {schema: 1, scope: "Owned OfflineAudioContext AudioWorklet/pass-through consistency; not realtime worklet or audio quality admission",
    rows, passed: rows.length === 12 && rows.every((row) => row.passed)};
}
