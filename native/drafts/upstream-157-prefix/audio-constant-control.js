async value => {
  const context = new OfflineAudioContext(1, 256, 44100);
  const source = context.createConstantSource();
  source.offset.value = value;
  source.connect(context.destination);
  source.start(0);
  let eventBuffer = null;
  context.oncomplete = event => { eventBuffer = event.renderedBuffer; };
  const result = await context.startRendering();
  const values = result.getChannelData(0);
  const bits = new Uint32Array(values.buffer, values.byteOffset, values.length);
  const expected = new Uint32Array(new Float32Array([value]).buffer)[0];
  return {value, expectedBits: expected.toString(16).padStart(8, '0'),
    observedBits: [...new Set(bits)].map(value => value.toString(16).padStart(8, '0')),
    allExact: [...bits].every(value => value === expected),
    frames: values.length, sampleRate: result.sampleRate,
    channels: result.numberOfChannels, eventSameBuffer: eventBuffer === result,
    closed: context.state === 'closed'};
}
