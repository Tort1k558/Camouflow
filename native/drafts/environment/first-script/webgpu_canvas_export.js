async function probeWebGPU() {
  if (!navigator.gpu || !isSecureContext) throw new Error('Secure WebGPU API unavailable');
  const adapter = await navigator.gpu.requestAdapter();
  if (!adapter) throw new Error('Default WebGPU adapter unavailable');
  const device = await adapter.requestDevice();
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 16;
  const context = canvas.getContext('webgpu');
  if (!context) throw new Error('WebGPU canvas unavailable');
  const format = navigator.gpu.getPreferredCanvasFormat();
  if (!['rgba8unorm', 'bgra8unorm'].includes(format)) throw new Error('Unsupported measured canvas format');
  context.configure({device, format, alphaMode: 'opaque', usage: GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.COPY_SRC});
  const buffer = device.createBuffer({size: 4096, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ});
  try {
    device.pushErrorScope('validation');
    const module = device.createShaderModule({code: `
      @vertex fn vertex(@builtin(vertex_index) index: u32) -> @builtin(position) vec4f {
        let points = array<vec2f, 3>(vec2f(-1.0, -1.0), vec2f(3.0, -1.0), vec2f(-1.0, 3.0));
        return vec4f(points[index], 0.0, 1.0);
      }
      @fragment fn fragment(@builtin(position) position: vec4f) -> @location(0) vec4f {
        let x = u32(position.x); let y = u32(position.y);
        return vec4f(f32((x * 17u) % 256u), f32((y * 29u + 31u) % 256u), f32((x * 43u + y * 11u) % 256u), 255.0) / 255.0;
      }`});
    const pipeline = device.createRenderPipeline({layout: 'auto', vertex: {module, entryPoint: 'vertex'},
      fragment: {module, entryPoint: 'fragment', targets: [{format}]}, primitive: {topology: 'triangle-list'}});
    const texture = context.getCurrentTexture();
    const encoder = device.createCommandEncoder();
    const pass = encoder.beginRenderPass({colorAttachments: [{view: texture.createView(), loadOp: 'clear', storeOp: 'store', clearValue: [0, 0, 0, 1]}]});
    pass.setPipeline(pipeline); pass.draw(3); pass.end();
    encoder.copyTextureToBuffer({texture}, {buffer, bytesPerRow: 256, rowsPerImage: 16}, [16, 16]);
    device.queue.submit([encoder.finish()]);
    const png = canvas.toDataURL('image/png');
    const repeat = canvas.toDataURL('image/png');
    await buffer.mapAsync(GPUMapMode.READ);
    const bytes = new Uint8Array(buffer.getMappedRange());
    const rgba = new Uint8Array(16 * 16 * 4);
    let referenceMatched = true;
    for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) {
      const offset = y * 256 + x * 4;
      const pixel = format === 'bgra8unorm' ? [bytes[offset + 2], bytes[offset + 1], bytes[offset], bytes[offset + 3]] : Array.from(bytes.slice(offset, offset + 4));
      const expected = [(x * 17) % 256, (y * 29 + 31) % 256, (x * 43 + y * 11) % 256, 255];
      referenceMatched &&= pixel.every((value, index) => value === expected[index]);
      rgba.set(pixel, (y * 16 + x) * 4);
    }
    buffer.unmap();
    const error = await device.popErrorScope();
    if (error) throw new Error('Canvas commands rejected: ' + error.message);
    return {measured: true, compatibilityPassed: referenceMatched && png === repeat,
      referenceMatched, exportStable: png === repeat, format, png,
      rgbaBase64: btoa(Array.from(rgba, value => String.fromCharCode(value)).join(''))};
  } finally {buffer.destroy(); context.unconfigure(); device.destroy();}
}
