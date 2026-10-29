async spec => {
  const context = new OfflineAudioContext(2, spec.frames, spec.rate);
  const input = context.createBuffer(spec.channels, spec.frames, spec.rate);
  for (let channel = 0; channel < spec.channels; channel += 1) {
    const values = input.getChannelData(channel);
    let state = (spec.seed ^ Math.imul(channel, 0x9e3779b9)) >>> 0;
    for (let frame = 0; frame < values.length; frame += 1) {
      let value;
      switch (spec.signal) {
        case 'random':
          state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
          value = (state >>> 12) / 524288 - 1;
          break;
        case 'silence': value = 0; break;
        case 'constant': value = 1; break;
        case 'impulse': value = frame % 1024 === 0 ? 1 : 0; break;
        case 'triangle': {
          const phase = frame % 256;
          value = phase < 128 ? phase / 64 - 1 : 3 - phase / 64;
          break;
        }
        case 'burst':
          value = frame < Math.floor(spec.frames / 4) ? 1 :
            (frame >= Math.floor(spec.frames / 2) && frame < Math.floor(spec.frames * 5 / 8) ? -1 : 0);
          break;
        default: throw new Error('Unsupported matrix signal');
      }
      values[frame] = spec.amplitude * value;
    }
  }
  const source = context.createBufferSource();
  source.buffer = input;
  if (spec.graph === 'compressor') {
    const compressor = new DynamicsCompressorNode(context, {
      threshold: spec.threshold, knee: spec.knee, ratio: spec.ratio,
      attack: spec.attack, release: spec.release
    });
    source.connect(compressor);
    compressor.connect(context.destination);
  } else if (spec.graph === 'direct') source.connect(context.destination);
  else throw new Error('Unsupported matrix graph');
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
  return {id: spec.id, frames: output.length, sampleRate: output.sampleRate,
    channelCount: output.numberOfChannels, samplesBase64: channels,
    eventSameBuffer: eventBuffer === output, closed: context.state === 'closed'};
}
