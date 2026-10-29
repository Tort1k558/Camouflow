async () => {
  const size = 4096;
  const canvas = new OffscreenCanvas(16, 16);
  const gl = canvas.getContext('webgl2', {antialias: false});
  if (!gl) throw new Error('WebGL2 is required; no software/size fallback');
  if (gl.getParameter(gl.MAX_RENDERBUFFER_SIZE) < size) throw new Error('4096 renderbuffer is unavailable');
  const framebuffer = gl.createFramebuffer();
  const renderbuffer = gl.createRenderbuffer();
  const pack = gl.createBuffer();
  if (!framebuffer || !renderbuffer || !pack) throw new Error('Owned GL allocation failed');
  const check = label => {
    const error = gl.getError();
    if (error !== gl.NO_ERROR) throw new Error(label + ': GL error ' + error);
  };
  const digest = async bytes => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)))
    .map(value => value.toString(16).padStart(2, '0')).join('');
  const state = () => ({viewport: Array.from(gl.getParameter(gl.VIEWPORT)),
    framebuffer: gl.getParameter(gl.FRAMEBUFFER_BINDING) === framebuffer,
    renderbuffer: gl.getParameter(gl.RENDERBUFFER_BINDING) === renderbuffer,
    packBound: gl.getParameter(gl.PIXEL_PACK_BUFFER_BINDING) !== null,
    alignment: gl.getParameter(gl.PACK_ALIGNMENT), rowLength: gl.getParameter(gl.PACK_ROW_LENGTH),
    skipRows: gl.getParameter(gl.PACK_SKIP_ROWS), skipPixels: gl.getParameter(gl.PACK_SKIP_PIXELS)});
  try {
    gl.bindFramebuffer(gl.FRAMEBUFFER, framebuffer);
    gl.bindRenderbuffer(gl.RENDERBUFFER, renderbuffer);
    gl.renderbufferStorage(gl.RENDERBUFFER, gl.RGBA8, size, size);
    gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.RENDERBUFFER, renderbuffer);
    if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) throw new Error('Framebuffer incomplete');
    gl.viewport(0, 0, 2, 2); // Intentionally not the attachment extent.
    gl.enable(gl.SCISSOR_TEST);
    const colors = [[87, 113, 149], [101, 143, 179], [53, 97, 137], [127, 167, 197]];
    for (let index = 0; index < 4; index += 1) {
      gl.scissor((index % 2) * 2048, Math.floor(index / 2) * 2048, 2048, 2048);
      gl.clearColor(...colors[index].map(value => value / 255), 1);
      gl.clear(gl.COLOR_BUFFER_BIT);
    }
    gl.disable(gl.SCISSOR_TEST);
    gl.pixelStorei(gl.PACK_ALIGNMENT, 4);
    check('setup');
    const before = state();
    const cpu = new Uint8Array(size * size * 4);
    const cpuStart = performance.now();
    gl.readPixels(0, 0, size, size, gl.RGBA, gl.UNSIGNED_BYTE, cpu);
    const cpuMilliseconds = performance.now() - cpuStart;
    check('full CPU');
    const cpuHash = await digest(cpu);
    const cropFromFull = new Uint8Array(64);
    for (let row = 0; row < 4; row += 1) {
      const offset = ((2046 + row) * size + 2046) * 4;
      cropFromFull.set(cpu.subarray(offset, offset + 16), row * 16);
    }
    const crops = [];
    for (let repeat = 0; repeat < 3; repeat += 1) {
      const crop = new Uint8Array(64);
      const start = performance.now();
      gl.readPixels(2046, 2046, 4, 4, gl.RGBA, gl.UNSIGNED_BYTE, crop);
      const milliseconds = performance.now() - start;
      check('CPU crop');
      crops.push({pixels: Array.from(crop), milliseconds});
    }
    const clipped = new Uint8Array(64).fill(165);
    gl.readPixels(-size, -size, 4, 4, gl.RGBA, gl.UNSIGNED_BYTE, clipped);
    check('outside-only crop');
    const cpuRepeat = new Uint8Array(cpu.length);
    gl.readPixels(0, 0, size, size, gl.RGBA, gl.UNSIGNED_BYTE, cpuRepeat);
    check('CPU repeat');
    const cpuRepeatHash = await digest(cpuRepeat);
    gl.bindBuffer(gl.PIXEL_PACK_BUFFER, pack);
    gl.bufferData(gl.PIXEL_PACK_BUFFER, cpu.length, gl.STREAM_READ);
    check('PBO allocation');
    const pbo = new Uint8Array(cpu.length);
    const pboStart = performance.now();
    gl.readPixels(0, 0, size, size, gl.RGBA, gl.UNSIGNED_BYTE, 0);
    gl.getBufferSubData(gl.PIXEL_PACK_BUFFER, 0, pbo);
    const pboMilliseconds = performance.now() - pboStart;
    check('PBO full read and publication');
    const pboHash = await digest(pbo);
    gl.bindBuffer(gl.PIXEL_PACK_BUFFER, null);
    const after = state();
    return {size, byteLength: cpu.length, cpuHash, cpuRepeatHash, pboHash,
      cropFromFull: Array.from(cropFromFull), crops, clipped: Array.from(clipped),
      cpuMilliseconds, pboMilliseconds, before, after};
  } finally {
    gl.bindBuffer(gl.PIXEL_PACK_BUFFER, null);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.bindRenderbuffer(gl.RENDERBUFFER, null);
    gl.deleteBuffer(pack); gl.deleteRenderbuffer(renderbuffer); gl.deleteFramebuffer(framebuffer);
    gl.getExtension('WEBGL_lose_context')?.loseContext();
  }
}
