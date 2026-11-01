async () => {
  const measure = (create) => {
    const size = 8;
    const source = create(size, size);
    const target = create(size, size);
    const sourceContext = source.getContext('2d', {willReadFrequently: true});
    const targetContext = target.getContext('2d', {willReadFrequently: true});
    if (!sourceContext || !targetContext) throw new Error('A native 2D context is unavailable');
    const expected = new Uint8ClampedArray(size * size * 4);
    const offset = (x, y) => (y * size + x) * 4;
    for (let x = 0; x < size; x += 1) {
      for (let y = 0; y < size; y += 1) {
        const rgba = [(x * 53 + y * 17 + 23) % 256, (x * 31 + y * 71 + 91) % 256,
          (x * 97 + y * 13 + 47) % 256, 255];
        sourceContext.fillStyle = `rgb(${rgba[0]}, ${rgba[1]}, ${rgba[2]})`;
        sourceContext.fillRect(x, y, 1, 1);
        expected.set(rgba, offset(x, y));
      }
    }
    const written = [];
    let sourceFillChangedChannels = 0;
    let immediateCopyChangedChannels = 0;
    let disjointWriteChangedChannels = 0;
    for (let x = 0; x < size; x += 1) {
      for (let y = 0; y < size; y += 1) {
        const read = Array.from(sourceContext.getImageData(x, y, 1, 1).data);
        sourceFillChangedChannels += read.filter((value, channel) => value !== expected[offset(x, y) + channel]).length;
        targetContext.fillStyle = `rgba(${read[0]}, ${read[1]}, ${read[2]}, ${read[3] / 255})`;
        targetContext.fillRect(x, y, 1, 1);
        const copied = Array.from(targetContext.getImageData(x, y, 1, 1).data);
        immediateCopyChangedChannels += copied.filter((value, channel) => value !== read[channel]).length;
        written.push({x, y, copied});
      }
    }
    for (const {x, y, copied} of written) {
      const final = targetContext.getImageData(x, y, 1, 1).data;
      disjointWriteChangedChannels += copied.filter((value, channel) => value !== final[channel]).length;
    }
    const uniform = create(size, size).getContext('2d', {willReadFrequently: true});
    if (!uniform) throw new Error('A uniform native 2D context is unavailable');
    uniform.fillStyle = 'rgb(37, 129, 211)';
    uniform.fillRect(0, 0, size, size);
    const uniformRead = uniform.getImageData(0, 0, size, size).data;
    const uniformFillChangedChannels = Array.from(uniformRead).filter(
      (value, index) => value !== [37, 129, 211, 255][index % 4]).length;
    return {pixels: size * size, sourceFillChangedChannels, immediateCopyChangedChannels,
      disjointWriteChangedChannels, uniformFillChangedChannels,
      passed: sourceFillChangedChannels === 0 && immediateCopyChangedChannels === 0 &&
        disjointWriteChangedChannels === 0 && uniformFillChangedChannels === 0};
  };
  const rows = [];
  const record = (name, operation) => {
    try { rows.push({name, ...operation()}); }
    catch (error) { rows.push({name, passed: false, error: String(error)}); }
  };
  const htmlCanvas = (document) => (width, height) => {
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    return canvas;
  };
  record('document-html', () => measure(htmlCanvas(document)));
  record('document-offscreen', () => measure((width, height) => new OffscreenCanvas(width, height)));
  const frame = document.createElement('iframe');
  let frameTimer;
  try {
    const loaded = new Promise((resolve, reject) => {
      frameTimer = setTimeout(() => reject(new Error('Owned frame load deadline')), 10000);
      frame.onload = () => { clearTimeout(frameTimer); resolve(); };
    });
    frame.srcdoc = '<!doctype html><title>Owned pixel-copy contract</title>';
    document.body.append(frame);
    await loaded;
    record('same-origin-frame', () => measure(htmlCanvas(frame.contentDocument)));
  } catch (error) { rows.push({name: 'same-origin-frame', passed: false, error: String(error)}); }
  finally { clearTimeout(frameTimer); frame.remove(); }
  for (const type of ['classic', 'module']) {
    let worker, timer;
    const url = URL.createObjectURL(new Blob([
      `const measure = ${measure.toString()}; onmessage = () => {try {postMessage(measure((w,h)=>new OffscreenCanvas(w,h)));}` +
      'catch(error){postMessage({passed:false,error:String(error)});}};'
    ], {type: 'application/javascript'}));
    try {
      const result = await new Promise((resolve, reject) => {
        timer = setTimeout(() => reject(new Error('Owned worker deadline')), 15000);
        worker = new Worker(url, {type});
        worker.onmessage = (event) => { clearTimeout(timer); resolve(event.data); };
        worker.onerror = () => { clearTimeout(timer); reject(new Error('Owned worker failed')); };
        worker.postMessage(null);
      });
      rows.push({name: 'worker-' + type, ...result});
    } catch (error) { rows.push({name: 'worker-' + type, passed: false, error: String(error)}); }
    finally { clearTimeout(timer); worker?.terminate(); URL.revokeObjectURL(url); }
  }
  return {schema: 1, scope: 'Owned opaque CSS fill/copy and disjoint-write contracts only',
    rows, passed: rows.length === 5 && rows.every((row) => row.passed)};
}
