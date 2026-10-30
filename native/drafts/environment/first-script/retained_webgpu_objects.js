async () => {
  const key = 'glintOwnedRetainedWebGpu';
  if (!Object.hasOwn(globalThis, key)) {
    if (!isSecureContext || !navigator.gpu) throw new Error('WebGPU unavailable; no retained-resource coverage');
    const adapter = await navigator.gpu.requestAdapter();
    if (!adapter) throw new Error('No default WebGPU adapter');
    const device = await adapter.requestDevice();
    const state = {id: crypto.randomUUID(), timeOrigin: performance.timeOrigin,
      read: 0, device, resources: [], unexpected: [], lost: false, closed: false};
    device.addEventListener('uncapturederror', event => state.unexpected.push(event.error.message));
    device.lost.then(() => {if (!state.closed) state.lost = true;});
    state.close = () => {state.closed = true; for (const value of state.resources) value.destroy(); device.destroy();};
    try {
      device.pushErrorScope('validation');
      const buffer = (size, usage) => {
        const value = device.createBuffer({size, usage}); state.resources.push(value); return value;
      };
      state.output = buffer(256, GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC);
      state.staging = buffer(256, GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ);
      state.pixels = buffer(768, GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ);
      state.shader = device.createShaderModule({code: `
        @group(0) @binding(0) var<storage, read_write> output: array<u32>;
        @compute @workgroup_size(8) fn main(@builtin(global_invocation_id) id: vec3<u32>) {
          output[id.x] = id.x * 17u + 31u;
        }`});
      state.pipeline = await device.createComputePipelineAsync({layout: 'auto', compute: {module: state.shader, entryPoint: 'main'}});
      state.bindings = device.createBindGroup({layout: state.pipeline.getBindGroupLayout(0), entries: [{binding: 0, resource: {buffer: state.output}}]});
      state.texture = device.createTexture({size: [7, 3], format: 'rgba8unorm',
        usage: GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.COPY_SRC});
      state.resources.push(state.texture);
      state.view = state.texture.createView();
      state.refs = [device, state.output, state.staging, state.pixels, state.shader,
        state.pipeline, state.bindings, state.texture, state.view];
      const error = await device.popErrorScope();
      if (error) throw new Error('Retained GPU initialization rejected: ' + error.message);
      Object.defineProperty(globalThis, key, {value: state});
    } catch (error) {state.close(); throw error;}
  }
  const state = globalThis[key];
  if (state.closed || state.lost || state.unexpected.length) throw new Error('Retained WebGPU resources lost or closed');
  const {device, output, staging, pixels, texture, view, shader, pipeline, bindings} = state;
  const sameReferences = state.refs.map((value, index) => value === [device, output, staging, pixels, shader, pipeline, bindings, texture, view][index]);
  device.pushErrorScope('validation');
  const encoder = device.createCommandEncoder();
  const compute = encoder.beginComputePass();
  compute.setPipeline(pipeline); compute.setBindGroup(0, bindings); compute.dispatchWorkgroups(8); compute.end();
  encoder.copyBufferToBuffer(output, 0, staging, 0, 256);
  const render = encoder.beginRenderPass({colorAttachments: [{view,
    clearValue: {r: 1, g: 0, b: 1, a: 1}, loadOp: 'clear', storeOp: 'store'}]});
  render.end();
  encoder.copyTextureToBuffer({texture}, {buffer: pixels, bytesPerRow: 256, rowsPerImage: 3}, [7, 3]);
  device.queue.submit([encoder.finish()]);
  await staging.mapAsync(GPUMapMode.READ);
  let computeMatched;
  const computeBuffer = staging.getMappedRange();
  try {computeMatched = new Uint32Array(computeBuffer).every((value, index) => value === index * 17 + 31);}
  finally {staging.unmap();}
  await pixels.mapAsync(GPUMapMode.READ);
  const pixelBuffer = pixels.getMappedRange();
  let textureMatched = true, paddingZero = true;
  try {
    const bytes = new Uint8Array(pixelBuffer);
    for (let row = 0; row < 3; row++) {
      for (let column = 0; column < 28; column++) textureMatched &&= bytes[row * 256 + column] === [255, 0, 255, 255][column % 4];
      for (let column = 28; column < 256; column++) paddingZero &&= bytes[row * 256 + column] === 0;
    }
  } finally {pixels.unmap();}
  const validation = await device.popErrorScope();
  if (validation || !computeMatched || !textureMatched || !paddingZero || state.lost || state.unexpected.length) throw new Error('Retained WebGPU readback failed');
  return {id: state.id, timeOrigin: state.timeOrigin, read: ++state.read,
    sameReferences, computeMatched, textureMatched, paddingZero,
    detached: computeBuffer.byteLength === 0 && pixelBuffer.byteLength === 0,
    deviceLost: state.lost, unexpected: [...state.unexpected]};
}
