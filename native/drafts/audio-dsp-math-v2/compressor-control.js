async () => {
  const context = new OfflineAudioContext(2, 8192, 44100);
  const input = context.createBuffer(1, 8192, 44100);
  const values = input.getChannelData(0);
  let state = 123456789;
  for (let frame = 0; frame < values.length; frame += 1) {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    values[frame] = (state >>> 12) / 524288 - 1;
  }
  const source = context.createBufferSource();
  source.buffer = input;
  const compressor = new DynamicsCompressorNode(context, {
    threshold: -24, knee: 30, ratio: 12, attack: 0.003, release: 0.25
  });
  source.connect(compressor);
  compressor.connect(context.destination);
  source.start(0);
  let eventBuffer = null;
  context.oncomplete = event => { eventBuffer = event.renderedBuffer; };
  const output = await context.startRendering();
  const channels = [];
  for (let channel = 0; channel < output.numberOfChannels; channel += 1) {
    const samples = output.getChannelData(channel);
    const bytes = new Uint8Array(samples.buffer, samples.byteOffset, samples.byteLength);
    let binary = '';
    for (let offset = 0; offset < bytes.length; offset += 8192) {
      binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
    }
    channels.push(btoa(binary));
  }
  return {frames: output.length, sampleRate: output.sampleRate,
    channelCount: output.numberOfChannels, samplesBase64: channels,
    eventSameBuffer: eventBuffer === output, closed: context.state === 'closed'};
}
