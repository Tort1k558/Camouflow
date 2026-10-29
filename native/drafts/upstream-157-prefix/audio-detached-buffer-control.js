async () => {
  const source = new AudioBuffer({numberOfChannels: 1, length: 128, sampleRate: 44100});
  const channel = source.getChannelData(0);
  const beforeFrames = channel.length;
  const original = channel.buffer;
  const transferred = structuredClone(original, {transfer: [original]});
  const afterFrames = source.getChannelData(0).length;
  return {
    beforeFrames,
    afterFrames,
    originalBytes: original.byteLength,
    transferredBytes: transferred.byteLength,
    sourceFrames: source.length,
    passed: beforeFrames === 128 && afterFrames === 0 && original.byteLength === 0 &&
      transferred.byteLength === 512 && source.length === 128
  };
}
