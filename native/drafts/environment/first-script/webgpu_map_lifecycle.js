async function probeWebGPU() {
  if (!isSecureContext || !navigator.gpu) throw new Error('Secure WebGPU unavailable');
  const adapter = await navigator.gpu.requestAdapter();
  if (!adapter) throw new Error('Default WebGPU adapter unavailable');
  const device = await adapter.requestDevice();
  const buffers = [], textures = [];
  try {
    const encoder = device.createCommandEncoder();
    for (const color of [[1, 0, 0, 1], [0, 0, 1, 1]]) {
      const texture = device.createTexture({size: [7, 3], format: 'rgba8unorm',
        usage: GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.COPY_SRC});
      const buffer = device.createBuffer({size: 768, usage: GPUBufferUsage.MAP_READ | GPUBufferUsage.COPY_DST});
      textures.push(texture); buffers.push(buffer);
      const pass = encoder.beginRenderPass({colorAttachments: [{view: texture.createView(),
        clearValue: color, loadOp: 'clear', storeOp: 'store'}]});
      pass.end();
      encoder.copyTextureToBuffer({texture}, {buffer, bytesPerRow: 256, rowsPerImage: 3}, [7, 3]);
    }
    device.queue.submit([encoder.finish()]);
    const reads = [];
    for (const index of [1, 0]) {
      const buffer = buffers[index];
      await buffer.mapAsync(GPUMapMode.READ);
      const mapped = buffer.getMappedRange();
      const bytes = new Uint8Array(mapped);
      const expected = index === 0 ? [255, 0, 0, 255] : [0, 0, 255, 255];
      for (let row = 0; row < 3; row++) for (let column = 0; column < 28; column++) {
        if (bytes[row * 256 + column] !== expected[column % 4]) throw new Error('Reversed read returned wrong source pixels');
      }
      buffer.unmap();
      if (mapped.byteLength !== 0) throw new Error('Unmap did not detach returned data');
      reads.push({source: index + 1, referenceMatched: true, detached: true});
    }
    const pending = buffers[0].mapAsync(GPUMapMode.READ).then(() => 'resolved', error => error.name);
    buffers[0].unmap();
    const cancellation = await pending;
    if (cancellation !== 'AbortError' || buffers[0].mapState !== 'unmapped') throw new Error('Cancelled map has wrong lifecycle');
    const dead = device.createBuffer({size: 16, usage: GPUBufferUsage.MAP_READ | GPUBufferUsage.COPY_DST});
    buffers.push(dead);
    device.destroy();
    const lost = await device.lost;
    const afterDestroy = await dead.mapAsync(GPUMapMode.READ).then(() => 'resolved', error => error.name);
    return {measured: true, compatibilityPassed: lost.reason === 'destroyed' && afterDestroy === 'AbortError' && dead.mapState === 'unmapped', mapStateAfterDestroy: dead.mapState, copyOrder: [1, 2], readOrder: [2, 1],
      reads, cancellation, afterDestroy, deviceLossReason: lost.reason};
  } finally {
    for (const buffer of buffers) buffer.destroy();
    for (const texture of textures) texture.destroy();
    device.destroy();
  }
}
