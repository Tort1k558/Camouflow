async () => {
  const size = 8;
  const changed = (a, b) => a.reduce((count, byte, index) => count + (byte !== b[index]), 0);
  const digest = async bytes => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)),
    byte => byte.toString(16).padStart(2, '0')).join('');
  const workerSource = async () => {
    let gl;
    self.onmessage = async event => {
      if (event.data === 'close') {
        gl?.getExtension('WEBGL_lose_context')?.loseContext();
        return;
      }
      try {
        const {canvas, api, size, alpha} = event.data;
        gl = canvas.getContext(api, {alpha, antialias: false, depth: false,
          stencil: false, preserveDrawingBuffer: true});
        if (!gl) throw new Error('Owned worker GPU context unavailable');
        gl.disable(gl.DITHER);
        gl.enable(gl.SCISSOR_TEST);
        const expected = new Uint8Array(size * size * 4);
        for (let x = 0; x < size; x++) for (let y = 0; y < size; y++) {
          const rgba = [(x * 53 + y * 17 + 23) % 256, (x * 31 + y * 71 + 91) % 256,
            (x * 97 + y * 13 + 47) % 256, 255];
          gl.scissor(x, y, 1, 1);
          gl.clearColor(rgba[0] / 255, rgba[1] / 255, rgba[2] / 255, 1);
          gl.clear(gl.COLOR_BUFFER_BIT);
          expected.set(rgba, ((size - y - 1) * size + x) * 4);
        }
        gl.disable(gl.SCISSOR_TEST);
        const bottomUp = new Uint8Array(expected.length);
        gl.readPixels(0, 0, size, size, gl.RGBA, gl.UNSIGNED_BYTE, bottomUp);
        if (gl.getError() !== gl.NO_ERROR) throw new Error('Owned worker GPU read failed');
        const direct = new Uint8Array(expected.length);
        for (let y = 0; y < size; y++) {
          direct.set(bottomUp.subarray(y * size * 4, (y + 1) * size * 4), (size - y - 1) * size * 4);
        }
        const png = new Uint8Array(await (await canvas.convertToBlob({type: 'image/png'})).arrayBuffer());
        await new Promise((resolve, reject) => {
          const timeout = setTimeout(() => reject(new Error('Worker animation frame unavailable')), 15000);
          requestAnimationFrame(() => { clearTimeout(timeout); resolve(); });
        });
        self.postMessage({direct: Array.from(direct), expected: Array.from(expected), png: Array.from(png)});
      } catch (error) {
        self.postMessage({error: String(error)});
      }
    };
  };
  const rows = [];
  for (const api of ['webgl', 'webgl2']) for (const alpha of [false, true]) {
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = size;
    document.body.append(canvas);
    const url = URL.createObjectURL(new Blob(['('+workerSource.toString()+')()'], {type: 'text/javascript'}));
    const worker = new Worker(url);
    const bitmaps = [];
    try {
      const offscreen = canvas.transferControlToOffscreen();
      const source = await new Promise((resolve, reject) => {
        const timeout = setTimeout(() => reject(new Error('Owned worker result timed out')), 20000);
        worker.onerror = event => { clearTimeout(timeout); reject(new Error(event.message)); };
        worker.onmessage = event => {
          clearTimeout(timeout);
          event.data.error ? reject(new Error(event.data.error)) : resolve(event.data);
        };
        worker.postMessage({canvas: offscreen, api, size, alpha}, [offscreen]);
      });
      const direct = new Uint8Array(source.direct);
      const expected = new Uint8Array(source.expected);
      const read = (image, frequent = false) => {
        const copy = new OffscreenCanvas(size, size);
        const context = copy.getContext('2d', {alpha: false, willReadFrequently: frequent});
        if (!context) throw new Error('Owned native copy context unavailable');
        context.drawImage(image, 0, 0);
        return context.getImageData(0, 0, size, size).data;
      };
      // An alpha:false destination is opaque even before a frame arrives.
      // Require actual coloured source content, not only opaque target alpha.
      const deadline = performance.now() + 8000;
      let attempts = 0, ready = false, lastReadError = null;
      while (performance.now() < deadline && attempts++ < 120) {
        try {
          const pixels = read(canvas);
          ready = pixels.some((value, index) => index % 4 !== 3 && value !== 0);
          if (ready) break;
        } catch (error) {
          lastReadError = String(error);
          if (!['InvalidStateError', 'NotReadableError'].includes(error.name)) throw error;
        }
        await new Promise(requestAnimationFrame);
      }
      if (!ready) throw new Error('Transferred placeholder frame was not observed; last read error: ' + lastReadError);
      const copies = [];
      const collect = async (name, image) => {
        for (const frequent of [false, true]) {
          const pixels = read(image, frequent);
          copies.push({name, willReadFrequently: frequent,
            changedChannels: changed(pixels, direct), knownFillChangedChannels: changed(pixels, expected),
            sha256: await digest(pixels)});
        }
      };
      await collect('drawImage', canvas);
      const bitmap = await createImageBitmap(canvas);
      bitmaps.push(bitmap);
      await collect('imageBitmap', bitmap);
      const fromUrl = await createImageBitmap(await (await fetch(canvas.toDataURL())).blob());
      bitmaps.push(fromUrl);
      await collect('toDataURL', fromUrl);
      const blob = await new Promise((resolve, reject) => canvas.toBlob(
        value => value ? resolve(value) : reject(new Error('Placeholder toBlob returned null')), 'image/png'));
      const fromBlob = await createImageBitmap(blob);
      bitmaps.push(fromBlob);
      await collect('toBlob', fromBlob);
      const fromWorker = await createImageBitmap(new Blob([new Uint8Array(source.png)], {type: 'image/png'}));
      bitmaps.push(fromWorker);
      await collect('workerPNG', fromWorker);
      rows.push({api, alpha, readyAttempts: attempts, directSha256: await digest(direct),
        knownFillChangedChannels: changed(direct, expected), copies,
        passed: copies.every(copy => copy.changedChannels === 0)});
    } catch (error) {
      rows.push({api, alpha, error: String(error), passed: false});
    } finally {
      bitmaps.forEach(bitmap => bitmap.close());
      worker.postMessage('close');
      worker.terminate();
      URL.revokeObjectURL(url);
      canvas.remove();
    }
  }
  return {schema: 1, scope: 'Owned worker-backed HTML placeholder copies; no external detector',
    rows, passed: rows.length === 4 && rows.every(row => row.passed)};
}
