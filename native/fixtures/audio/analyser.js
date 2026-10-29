async () => {
  const rows = [];
  const bytes = (value) => new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
  const equal = (left, right) => left.length === right.length && bytes(left).every((value, index) => value === bytes(right)[index]);
  const frames = 2048;
  for (const rate of [44100, 48000]) {
    for (const graph of ["identity", "half-gain", "compressor"]) {
      for (let repetition = 0; repetition < 2; repetition += 1) {
        const context = new OfflineAudioContext(1, frames, rate);
        const input = context.createBuffer(1, frames, rate);
        const signal = input.getChannelData(0);
        for (let index = 0; index < frames; index += 1) signal[index] = ((index % 17) - 8) / 32;
        const source = context.createBufferSource();
        source.buffer = input;
        const analyser = context.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0;
        const nodes = [source, analyser];
        try {
          if (graph === "identity") {
            source.connect(analyser);
          } else {
            const processor = graph === "half-gain" ? context.createGain() : context.createDynamicsCompressor();
            if (graph === "half-gain") processor.gain.value = 0.5;
            nodes.push(processor);
            source.connect(processor).connect(analyser);
          }
          analyser.connect(context.destination);
          source.start();
          const rendered = await context.startRendering();
          const time = new Float32Array(analyser.fftSize);
          const repeated = new Float32Array(analyser.fftSize);
          time.fill(NaN);
          analyser.getFloatTimeDomainData(time);
          analyser.getFloatTimeDomainData(repeated);
          const raw = rendered.getChannelData(0);
          const tail = raw.slice(frames - analyser.fftSize);
          const small = new Float32Array(analyser.fftSize / 2);
          analyser.getFloatTimeDomainData(small);
          const large = new Float32Array(analyser.fftSize + 17);
          large.fill(42.25);
          analyser.getFloatTimeDomainData(large);
          const byteTime = new Uint8Array(analyser.fftSize);
          analyser.getByteTimeDomainData(byteTime);
          const expectedBytes = Uint8Array.from(time, (value) =>
            Math.max(0, Math.min(255, Math.floor(Math.fround(128 * (1 + value))))));
          const frequency = new Float32Array(analyser.frequencyBinCount);
          const frequencyAgain = new Float32Array(analyser.frequencyBinCount);
          analyser.getFloatFrequencyData(frequency);
          analyser.getFloatFrequencyData(frequencyAgain);
          const byteFrequency = new Uint8Array(analyser.frequencyBinCount);
          const byteFrequencyAgain = new Uint8Array(analyser.frequencyBinCount);
          analyser.getByteFrequencyData(byteFrequency);
          analyser.getByteFrequencyData(byteFrequencyAgain);
          let fftError;
          try { analyser.fftSize = 31; } catch (error) { fftError = error.name; }
          const beforeMutation = time.slice();
          raw[frames - analyser.fftSize] = 0.75;
          const afterMutation = new Float32Array(analyser.fftSize);
          analyser.getFloatTimeDomainData(afterMutation);
          const checks = {
            closed: context.state === "closed",
            formatPreserved: rendered.length === frames && rendered.numberOfChannels === 1 && rendered.sampleRate === rate,
            timeFinite: time.every(Number.isFinite),
            timeRepeatedExact: equal(time, repeated),
            timeMatchesRenderedTail: equal(time, tail),
            shortArrayPrefixExact: equal(small, time.subarray(0, small.length)),
            longArrayPrefixExact: equal(large.subarray(0, time.length), time),
            longArrayTailUntouched: large.subarray(time.length).every((value) => value === 42.25),
            byteTimeConversionExact: equal(byteTime, expectedBytes),
            frequencyValid: frequency.every((value) => Number.isFinite(value) || value === -Infinity),
            frequencyRepeatedExact: equal(frequency, frequencyAgain),
            byteFrequencyRepeatedExact: equal(byteFrequency, byteFrequencyAgain),
            invalidFftRejected: fftError === "IndexSizeError" && analyser.fftSize === 256,
            outputMutationDoesNotChangeAnalyser: equal(beforeMutation, afterMutation),
          };
          rows.push({rate, graph, repetition, checks, passed: Object.values(checks).every(Boolean)});
        } finally {
          for (const node of nodes) node.disconnect();
        }
      }
    }
  }
  return {schema: 1, scope: "Owned OfflineAudioContext analyser/result compatibility; no realtime or worklet admission",
    rows, passed: rows.length === 12 && rows.every((row) => row.passed)};
}
