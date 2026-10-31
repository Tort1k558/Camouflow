async function armOwnedGPURecovery() {
  if (globalThis.__glintOwnedGPURecovery) throw new Error('Recovery probe already armed');
  if (!navigator.gpu || !isSecureContext) throw new Error('Secure WebGPU unavailable');
  const adapter = await navigator.gpu.requestAdapter();
  if (!adapter) throw new Error('WebGPU adapter unavailable');
  const device = await adapter.requestDevice();
  let callbacks = 0;
  const lost = device.lost.then(info => {
    callbacks++;
    return {reason: info.reason, messageLength: info.message.length};
  });
  const input = device.createBuffer({size: 16, usage: GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST});
  const readback = device.createBuffer({size: 16, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ});
  const reference = [17, 29, 43, 71];
  try {
    device.pushErrorScope('validation');
    device.queue.writeBuffer(input, 0, new Uint32Array(reference));
    const encoder = device.createCommandEncoder();
    encoder.copyBufferToBuffer(input, 0, readback, 0, 16);
    device.queue.submit([encoder.finish()]);
    await readback.mapAsync(GPUMapMode.READ);
    const actual = Array.from(new Uint32Array(readback.getMappedRange()));
    readback.unmap();
    const error = await device.popErrorScope();
    if (error || !actual.every((value, index) => value === reference[index]) || callbacks !== 0) {
      throw new Error('Initial owned GPU copy or device validation failed');
    }
    globalThis.__glintOwnedGPURecovery = Object.freeze({
      async finish() {
        let timer;
        try {
          const info = await Promise.race([
            lost,
            new Promise((_, reject) => {timer = setTimeout(() => reject(new Error('GPU loss timeout')), 60000);})
          ]);
          if (callbacks !== 1 || info.reason !== 'unknown' || info.messageLength > 16384) {
            throw new Error('Unexpected owned GPU loss callback');
          }
          let rejection;
          try {await readback.mapAsync(GPUMapMode.READ, 0, 16);} catch (error) {rejection = error.name;}
          if (rejection !== 'AbortError' || readback.mapState !== 'unmapped') {
            throw new Error('Lost GPU buffer mapping did not abort cleanly: ' + rejection);
          }
          return {initialCopyMatched: true, deviceLostCallbacks: callbacks, reason: info.reason,
            oldMapRejectedWith: rejection, oldMapState: readback.mapState};
        } finally {clearTimeout(timer);}
      },
      close() {
        readback.destroy(); input.destroy(); device.destroy();
        delete globalThis.__glintOwnedGPURecovery;
      }
    });
    return {armed: true, initialCopyMatched: true, deviceLostCallbacks: callbacks};
  } catch (error) {
    readback.destroy(); input.destroy(); device.destroy();
    throw error;
  }
}
