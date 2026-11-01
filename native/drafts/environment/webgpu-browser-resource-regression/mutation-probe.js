async function probeWebGPU() {
  const cases = [];
  if (!navigator.gpu || !isSecureContext) throw new Error('Secure WebGPU unavailable');
  for (const format of ['rgba8unorm', 'bgra8unorm']) for (const route of ['render', 'copy', 'storage']) {
    if (format === 'bgra8unorm' && route === 'storage') continue;
    const adapter = await navigator.gpu.requestAdapter();
    if (!adapter) throw new Error('Default adapter unavailable');
    const device = await adapter.requestDevice();
    const buffers = [];
    const textures = [];
    const makeBuffer = (usage) => {
      const buffer = device.createBuffer({size: 4096, usage}); buffers.push(buffer); return buffer;
    };
    const makeTexture = () => {
      const texture = device.createTexture({size: [16,16], format, usage: GPUTextureUsage.RENDER_ATTACHMENT
        | GPUTextureUsage.COPY_SRC | GPUTextureUsage.COPY_DST | GPUTextureUsage.TEXTURE_BINDING
        | (route === 'storage' ? GPUTextureUsage.STORAGE_BINDING : 0)});
      textures.push(texture); return texture;
    };
    try {
      device.pushErrorScope('validation');
      const texture = makeTexture();
      const render = (encoder, destination, mutation) => {
        const module = device.createShaderModule({code: `
          @vertex fn v(@builtin(vertex_index) i:u32)->@builtin(position) vec4f {
            let p=array<vec2f,3>(vec2f(-1,-1),vec2f(3,-1),vec2f(-1,3)); return vec4f(p[i],0,1);
          }
          @fragment fn f(@builtin(position) p:vec4f)->@location(0) vec4f {
            if (u32(p.x)<8u) {return vec4f(${mutation ? '128,191,64' : '64,128,191'},255)/255.0;}
            return vec4f(${mutation ? '64,128,191' : '191,64,128'},255)/255.0;
          }`});
        const pipeline = device.createRenderPipeline({layout: 'auto', vertex: {module,entryPoint:'v'},
          fragment: {module,entryPoint:'f',targets:[{format}]}});
        const pass = encoder.beginRenderPass({colorAttachments:[{view:destination.createView(),
          loadOp:'clear',storeOp:'store',clearValue:[0,0,0,1]}]});
        pass.setPipeline(pipeline);pass.draw(3);pass.end();
      };
      const shaderModule = device.createShaderModule({code:`
        @group(0) @binding(0) var image:texture_2d<f32>;
        @group(0) @binding(1) var<storage,read_write> output:array<vec4u>;
        @compute @workgroup_size(4,4) fn main(@builtin(global_invocation_id) id:vec3u) {
          if(id.x>=16u||id.y>=16u){return;}
          output[id.y*16u+id.x]=vec4u(round(textureLoad(image,vec2i(id.xy),0)*255.0)) ^ vec4u(0xa1b2c3d4u);
        }`});
      const shaderPipeline = device.createComputePipeline({layout:'auto',compute:{module:shaderModule,entryPoint:'main'}});
      const encodeRead = encoder => {
        const direct = makeBuffer(GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ);
        const output = makeBuffer(GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC);
        const staging = makeBuffer(GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ);
        const group = device.createBindGroup({layout:shaderPipeline.getBindGroupLayout(0),entries:[
          {binding:0,resource:texture.createView()},{binding:1,resource:{buffer:output}}]});
        const pass = encoder.beginComputePass();
        pass.setPipeline(shaderPipeline);pass.setBindGroup(0,group);pass.dispatchWorkgroups(4,4);pass.end();
        encoder.copyTextureToBuffer({texture},{buffer:direct,bytesPerRow:256,rowsPerImage:16},[16,16]);
        encoder.copyBufferToBuffer(output,0,staging,0,4096);
        return {direct,staging};
      };
      const readDirect = async buffer => {
        await Promise.race([buffer.mapAsync(GPUMapMode.READ),device.lost.then(info=>{throw new Error('Device lost: '+info.message);})]);
        try {
          const mapped = new Uint8Array(buffer.getMappedRange());
          const rgba = new Uint8Array(1024);
          for(let y=0;y<16;y++)for(let x=0;x<16;x++) {
            const from=y*256+x*4, to=(y*16+x)*4;
            rgba.set(format==='bgra8unorm' ? [mapped[from+2],mapped[from+1],mapped[from],mapped[from+3]]
              : mapped.subarray(from,from+4),to);
          }
          for(let y=0;y<16;y++)for(let x=64;x<256;x++) if(mapped[y*256+x]!==0) throw new Error('Direct padding changed');
          return Array.from(rgba);
        } finally {buffer.unmap();}
      };
      const read = async capture => {
        const rgba = await readDirect(capture.direct);
        await Promise.race([capture.staging.mapAsync(GPUMapMode.READ),device.lost.then(info=>{throw new Error('Device lost: '+info.message);})]);
        let shader;
        try {
          shader = Array.from(new Uint32Array(capture.staging.getMappedRange()), word=>(word ^ 0xa1b2c3d4)>>>0);
          if(shader.some(value=>value>255)) throw new Error('Transformed shader value outside RGBA8');
        } finally {capture.staging.unmap();}
        return {rgba,shader};
      };
      const first = device.createCommandEncoder();
      render(first,texture,false);
      const beforeCapture = encodeRead(first);
      device.queue.submit([first.finish()]);
      const before = await read(beforeCapture);
      const second = device.createCommandEncoder();
      if(route==='render') render(second,texture,true);
      else if(route==='copy') {
        const temporary = makeTexture(); render(second,temporary,true);
        second.copyTextureToTexture({texture:temporary},{texture},[16,16]);
      } else {
        const module=device.createShaderModule({code:`
          @group(0) @binding(0) var image:texture_storage_2d<rgba8unorm,write>;
          @compute @workgroup_size(4,4) fn main(@builtin(global_invocation_id) id:vec3u) {
            if(id.x>=16u||id.y>=16u){return;}
            var color=vec4f(64,128,191,255)/255.0;
            if(id.x<8u){color=vec4f(128,191,64,255)/255.0;}
            textureStore(image,vec2i(id.xy),color);
          }`});
        const pipeline=device.createComputePipeline({layout:'auto',compute:{module,entryPoint:'main'}});
        const group=device.createBindGroup({layout:pipeline.getBindGroupLayout(0),entries:[{binding:0,resource:texture.createView()}]});
        const pass=second.beginComputePass();
        pass.setPipeline(pipeline);pass.setBindGroup(0,group);pass.dispatchWorkgroups(4,4);pass.end();
      }
      const afterCapture=encodeRead(second);
      device.queue.submit([second.finish()]);
      const after=await read(afterCapture);
      const retainedBefore=await readDirect(beforeCapture.direct);
      const error=await device.popErrorScope();
      if(error) throw new Error('Mutation commands rejected: '+error.message);
      cases.push({route,format,before,after,retainedBefore,commandValidationPassed:true});
    } finally {
      for(const buffer of buffers)buffer.destroy();
      for(const texture of textures)texture.destroy();
      device.destroy();
    }
  }
  return {measured:true,cases};
}
