async () => {
  const result = {schema: 1, scope: "Muted realtime compressor/analyser lifecycle only; not audio quality or worklet admission",
    passed: false, checks: {}, errors: []};
  let context;
  let oscillator;
  let started = false;
  const nodes = [];
  try {
    result.checks.trustedActivation = navigator.userActivation.isActive;
    context = new AudioContext();
    result.sampleRate = context.sampleRate;
    oscillator = context.createOscillator();
    oscillator.type = "triangle";
    oscillator.frequency.value = 997;
    const compressor = context.createDynamicsCompressor();
    const analyser = context.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0;
    const mute = context.createGain();
    mute.gain.value = 0;
    nodes.push(oscillator, compressor, analyser, mute);
    oscillator.connect(compressor).connect(analyser).connect(mute).connect(context.destination);
    oscillator.start();
    started = true;
    await context.resume();
    const deadline = performance.now() + 5000;
    while (context.currentTime < 4 * analyser.fftSize / context.sampleRate && performance.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
    result.checks.realtimeAdvanced = context.currentTime >= 4 * analyser.fftSize / context.sampleRate;
    await context.suspend();
    result.checks.suspended = context.state === "suspended";
    const time = new Float32Array(analyser.fftSize);
    const again = new Float32Array(analyser.fftSize);
    analyser.getFloatTimeDomainData(time);
    analyser.getFloatTimeDomainData(again);
    const bytes = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(bytes);
    const frequency = new Float32Array(analyser.frequencyBinCount);
    analyser.getFloatFrequencyData(frequency);
    result.checks.signalFiniteAndNonzero = time.every(Number.isFinite) && time.some((value) => value !== 0);
    result.checks.suspendedReadsExact = time.every((value, index) => Object.is(value, again[index]));
    result.checks.byteConversionExact = bytes.every((value, index) => value ===
      Math.max(0, Math.min(255, Math.floor(Math.fround(128 * (1 + time[index]))))));
    result.checks.frequencyValid = frequency.every((value) => Number.isFinite(value) || value === -Infinity);
    result.checks.compressorReductionFinite = Number.isFinite(compressor.reduction);
    result.checks.outputMuted = mute.gain.value === 0;
    result.checks.nativeSampleRateValid = Number.isFinite(context.sampleRate) && context.sampleRate > 0;
  } catch (error) {
    result.errors.push({phase: "measurement", name: error.name, message: error.message});
  } finally {
    if (started) {
      try { oscillator.stop(); } catch (error) { result.errors.push({phase: "stop", message: error.message}); }
    }
    for (const node of nodes) {
      try { node.disconnect(); } catch (error) { result.errors.push({phase: "disconnect", message: error.message}); }
    }
    if (context) {
      try {
        await context.close();
        result.checks.closed = context.state === "closed";
      } catch (error) {
        result.errors.push({phase: "close", message: error.message});
      }
    }
  }
  result.passed = Object.keys(result.checks).length === 11 && Object.values(result.checks).every(Boolean) && result.errors.length === 0;
  return result;
}
