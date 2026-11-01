async function probeWebGPU() {
  if (!navigator.gpu || !isSecureContext) throw new Error('Secure WebGPU unavailable');
  const results = [];
  for (const size of [1921, 2048]) for (const format of ['rgba8unorm', 'bgra8unorm']) {
    const adapter = await navigator.gpu.requestAdapter();
    if (!adapter) throw new Error('Default adapter unavailable');
    const device = await adapter.requestDevice();
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = size;
    const context = canvas.getContext('webgpu');
    if (!context) throw new Error('WebGPU canvas unavailable');
    const pitch = Math.ceil(size * 4 / 256) * 256;
    const cut = Math.floor(size / 2);
    const points = [0, 1, cut, size - 1].flatMap(y => [0, cut - 1, cut, size - 1].map(x => [x, y]));
    const buffers = [];
    const buffer = (bytes, usage) => {
      const result = device.createBuffer({size: bytes, usage}); buffers.push(result); return result;
    };
    try {
      device.pushErrorScope('validation');
      const direct = buffer(pitch * size, GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ);
      const storage = buffer(256, GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC);
      const staging = buffer(256, GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ);
      context.configure({device, format, alphaMode: 'opaque', usage:
        GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.COPY_SRC | GPUTextureUsage.TEXTURE_BINDING});
      const module = device.createShaderModule({code: `
        @vertex fn vertex(@builtin(vertex_index) id: u32) -> @builtin(position) vec4f {
          let p = array<vec2f, 3>(vec2f(-1,-1),vec2f(3,-1),vec2f(-1,3));
          return vec4f(p[id],0,1);
        }
        @fragment fn fragment(@builtin(position) p: vec4f) -> @location(0) vec4f {
          if (u32(p.x) < ${cut}u) { return vec4f(64,128,191,255) / 255.0; }
          return vec4f(191,64,128,255) / 255.0;
        }`});
      const render = device.createRenderPipeline({layout: 'auto', vertex: {module, entryPoint: 'vertex'},
        fragment: {module, entryPoint: 'fragment', targets: [{format}]}});
      const computeModule = device.createShaderModule({code: `
        @group(0) @binding(0) var image: texture_2d<f32>;
        @group(0) @binding(1) var<storage, read_write> output: array<vec4u>;
        @compute @workgroup_size(16) fn main(@builtin(global_invocation_id) id: vec3u) {
          if (id.x >= 16u) { return; }
          let points = array<vec2i,16>(${points.map(([x,y]) => `vec2i(${x},${y})`).join(',')});
          output[id.x] = vec4u(round(textureLoad(image,points[id.x],0) * 255.0)) ^ vec4u(0xa1b2c3d4u);
        }`});
      const compute = device.createComputePipeline({layout: 'auto', compute: {module: computeModule, entryPoint: 'main'}});
      const texture = context.getCurrentTexture();
      const group = device.createBindGroup({layout: compute.getBindGroupLayout(0), entries: [
        {binding: 0, resource: texture.createView()}, {binding: 1, resource: {buffer: storage}}]});
      const encoder = device.createCommandEncoder();
      const draw = encoder.beginRenderPass({colorAttachments: [{view: texture.createView(),
        loadOp: 'clear', storeOp: 'store', clearValue: [0,0,0,1]}]});
      draw.setPipeline(render); draw.draw(3); draw.end();
      encoder.copyTextureToBuffer({texture}, {buffer: direct, bytesPerRow: pitch, rowsPerImage: size}, [size,size]);
      const sample = encoder.beginComputePass();
      sample.setPipeline(compute); sample.setBindGroup(0, group); sample.dispatchWorkgroups(1); sample.end();
      encoder.copyBufferToBuffer(storage,0,staging,0,256);
      device.queue.submit([encoder.finish()]);
      // Export before yielding so this is the same canvas frame as the command buffer.
      const png = canvas.toDataURL('image/png');
      const repeat = canvas.toDataURL('image/png');
      if (png.length > 3 * 1024 * 1024) throw new Error('PNG fixture payload too large');
      const lost = device.lost.then(info => {throw new Error('GPU device lost: ' + info.reason + ': ' + info.message);});
      const completed = Promise.all([direct.mapAsync(GPUMapMode.READ),staging.mapAsync(GPUMapMode.READ)]);
      await Promise.race([completed,lost]);
      const mapped = new Uint8Array(direct.getMappedRange());
      const rgba = new Uint8Array(size * size * 4);
      let paddingZero = true;
      for (let y = 0; y < size; y++) {
        rgba.set(mapped.subarray(y * pitch,y * pitch + size * 4),y * size * 4);
        for (let i = y * pitch + size * 4; i < (y + 1) * pitch; i++) paddingZero &&= mapped[i] === 0;
      }
      if (format === 'bgra8unorm') for (let i = 0; i < rgba.length; i += 4) {
        const first = rgba[i]; rgba[i] = rgba[i+2]; rgba[i+2] = first;
      }
      const words = new Uint32Array(staging.getMappedRange());
      const shaderRGBA = Array.from(words, word => (word ^ 0xa1b2c3d4) >>> 0);
      if (shaderRGBA.some(word => word > 255)) throw new Error('Shader transform outside RGBA8');
      const directSamples = points.flatMap(([x,y]) => Array.from(rgba.subarray((y * size + x) * 4,(y * size + x) * 4 + 4)));
      const digest = await crypto.subtle.digest('SHA-256',rgba);
      direct.unmap(); staging.unmap();
      const validation = await device.popErrorScope();
      if (validation) throw new Error('GPU validation rejected fixture: ' + validation.message);
      results.push({size, format, pitch, points, measured: true, paddingZero,
        commandValidationPassed: true, exportStable: png === repeat, png, shaderRGBA, directSamples,
        directSHA256: Array.from(new Uint8Array(digest), x => x.toString(16).padStart(2,'0')).join('')});
    } finally {
      for (const item of buffers) item.destroy();
      context.unconfigure(); device.destroy();
    }
  }
  return {measured: true, cases: results};
}
