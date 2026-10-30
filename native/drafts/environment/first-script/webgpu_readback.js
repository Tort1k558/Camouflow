async function probeWebGPU() {
  const result = {secureContext: isSecureContext, exposed: !!navigator.gpu,
    measured: false, compatibilityPassed: false, privacyAdmitted: false};
  if (!navigator.gpu) return {...result, unavailable: 'API not exposed'};
  const adapter = await navigator.gpu.requestAdapter();
  if (!adapter) return {...result, unavailable: 'No default adapter'};
  const device = await adapter.requestDevice();
  const resources = [];
  const unexpected = [];
  let intentionalDestroy = false;
  device.addEventListener('uncapturederror', event => unexpected.push(event.error.message));
  device.lost.then(info => {if (!intentionalDestroy) unexpected.push('device lost: ' + info.reason);});
  const buffer = (size, usage) => {
    const value = device.createBuffer({size, usage}); resources.push(value); return value;
  };
  try {
    device.pushErrorScope('validation');
    const output = buffer(256, GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC);
    const staging = buffer(256, GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ);
    const shader = device.createShaderModule({code: `
      @group(0) @binding(0) var<storage, read_write> output: array<u32>;
      @compute @workgroup_size(8) fn main(@builtin(global_invocation_id) id: vec3<u32>) {
        output[id.x] = id.x * 17u + 31u;
      }`});
    const compilation = await shader.getCompilationInfo();
    if (compilation.messages.some(message => message.type === 'error')) throw new Error('WGSL compilation error');
    const pipeline = await device.createComputePipelineAsync({layout: 'auto', compute: {module: shader, entryPoint: 'main'}});
    const bindings = device.createBindGroup({layout: pipeline.getBindGroupLayout(0), entries: [{binding: 0, resource: {buffer: output}}]});
    const computeReads = [];
    for (let repeat = 0; repeat < 2; repeat++) {
      const encoder = device.createCommandEncoder();
      const pass = encoder.beginComputePass();
      pass.setPipeline(pipeline); pass.setBindGroup(0, bindings); pass.dispatchWorkgroups(8); pass.end();
      encoder.copyBufferToBuffer(output, 0, staging, 0, 256);
      device.queue.submit([encoder.finish()]);
      await staging.mapAsync(GPUMapMode.READ);
      const mapped = staging.getMappedRange();
      const values = Array.from(new Uint32Array(mapped));
      if (!values.every((value, index) => value === index * 17 + 31)) throw new Error('Compute readback mismatch');
      let rangeError = '';
      try { staging.getMappedRange(4, 4); } catch (error) { rangeError = error.name; }
      if (rangeError !== 'OperationError') throw new Error('Unaligned mapped range did not reject correctly');
      staging.unmap();
      if (mapped.byteLength !== 0 || staging.mapState !== 'unmapped') throw new Error('Unmap did not detach mapping');
      computeReads.push({words: values.length, referenceMatched: true, detached: true, rangeError});
    }
    const texture = device.createTexture({size: [7, 3], format: 'rgba8unorm', usage: GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.COPY_SRC});
    resources.push(texture);
    const pixels = buffer(768, GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ);
    const textureReads = [];
    for (let repeat = 0; repeat < 2; repeat++) {
      const encoder = device.createCommandEncoder();
      const pass = encoder.beginRenderPass({colorAttachments: [{view: texture.createView(),
        clearValue: {r: 1, g: 0, b: 1, a: 1}, loadOp: 'clear', storeOp: 'store'}]});
      pass.end();
      encoder.copyTextureToBuffer({texture}, {buffer: pixels, bytesPerRow: 256, rowsPerImage: 3}, [7, 3]);
      device.queue.submit([encoder.finish()]);
      await pixels.mapAsync(GPUMapMode.READ);
      const bytes = new Uint8Array(pixels.getMappedRange());
      let paddingZero = true;
      for (let row = 0; row < 3; row++) {
        for (let column = 0; column < 28; column++) {
          if (bytes[row * 256 + column] !== [255, 0, 255, 255][column % 4]) throw new Error('Texture pixel mismatch');
        }
        for (let column = 28; column < 256; column++) paddingZero &&= bytes[row * 256 + column] === 0;
      }
      pixels.unmap();
      if (!paddingZero) throw new Error('Fresh staging padding was modified');
      textureReads.push({width: 7, height: 3, rowPitch: 256, referenceMatched: true, paddingZero});
    }
    const validError = await device.popErrorScope();
    if (validError) throw new Error('Valid operations rejected: ' + validError.message);
    device.pushErrorScope('validation');
    let alignmentError = '';
    try { await staging.mapAsync(GPUMapMode.READ, 4, 4); } catch (error) { alignmentError = error.name; }
    const mapValidation = await device.popErrorScope();
    if (alignmentError !== 'OperationError' || !(mapValidation instanceof GPUValidationError)) throw new Error('Invalid map offset validation missing');
    device.pushErrorScope('validation');
    buffer(16, GPUBufferUsage.MAP_READ | GPUBufferUsage.STORAGE);
    const usageError = await device.popErrorScope();
    if (!(usageError instanceof GPUValidationError)) throw new Error('Invalid MAP_READ usage accepted');
    await device.queue.onSubmittedWorkDone();
    if (unexpected.length) throw new Error('Unexpected GPU error: ' + unexpected.join('; '));
    return {...result, measured: true, compatibilityPassed: true, computeReads, textureReads,
      validation: {alignmentError, mapValidation: true, usageValidation: true}, unexpected};
  } finally {
    for (const resource of resources) resource.destroy();
    intentionalDestroy = true;
    device.destroy();
  }
}
