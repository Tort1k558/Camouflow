registerProcessor("owned-audio-copy", class extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.expectedFrames = options.processorOptions.frames;
  }
  process(inputs, outputs) {
    const output = outputs[0][0];
    const input = inputs[0][0];
    if (input) output.set(input); else output.fill(0);
    const copy = output.slice();
    this.port.postMessage({offset: currentFrame, time: currentTime, rate: sampleRate,
      samples: copy, complete: currentFrame + copy.length >= this.expectedFrames}, [copy.buffer]);
    return true;
  }
});
