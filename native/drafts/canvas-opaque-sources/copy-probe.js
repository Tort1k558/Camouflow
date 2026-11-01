async () => {
  const size = 8;
  const digest = async data => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', data)),
    value => value.toString(16).padStart(2, '0')).join('');
  const changed = (a,b) => a.reduce((n,value,index) => n + (value !== b[index]), 0);
  const rows = [];
  for (const api of ['webgl','webgl2']) for (const alpha of [false,true]) {
    const row = {api,alpha,copies:[],passed:false};
    rows.push(row);
    let gl;
    try {
      const source = new OffscreenCanvas(size,size);
      gl = source.getContext(api,{alpha,antialias:false,depth:false,stencil:false,preserveDrawingBuffer:true});
      if (!gl) throw new Error('GPU context unavailable');
      row.attributes = gl.getContextAttributes();
      row.drawingBufferColorSpace = gl.drawingBufferColorSpace;
      gl.disable(gl.DITHER);
      gl.enable(gl.SCISSOR_TEST);
      const expected = new Uint8Array(size*size*4);
      for (let x=0;x<size;x++) for (let y=0;y<size;y++) {
        const rgba = [(x*53+y*17+23)%256,(x*31+y*71+91)%256,(x*97+y*13+47)%256,255];
        gl.scissor(x,y,1,1);
        gl.clearColor(rgba[0]/255,rgba[1]/255,rgba[2]/255,1);
        gl.clear(gl.COLOR_BUFFER_BIT);
        expected.set(rgba,((size-y-1)*size+x)*4);
      }
      gl.disable(gl.SCISSOR_TEST);
      const raw = new Uint8Array(expected.length);
      gl.readPixels(0,0,size,size,gl.RGBA,gl.UNSIGNED_BYTE,raw);
      if (gl.getError() !== gl.NO_ERROR) throw new Error('Direct GPU read failed');
      const direct = new Uint8Array(raw.length);
      for (let y=0;y<size;y++) direct.set(raw.subarray(y*size*4,(y+1)*size*4),(size-y-1)*size*4);
      row.directSha256 = await digest(direct);
      row.knownFillChangedChannels = changed(direct,expected);
      const paths = [
        ['drawImage',async()=>source],
        ['png',async()=>createImageBitmap(await source.convertToBlob({type:'image/png'}),{colorSpaceConversion:'none'})],
        ['createImageBitmap',async()=>createImageBitmap(source,{colorSpaceConversion:'none'})],
        ['transferToImageBitmap',async()=>source.transferToImageBitmap()]
      ];
      for (const [name,create] of paths) {
        let image;
        try {
          image = await create();
          for (const willReadFrequently of [false,true]) {
            const result = {name,willReadFrequently,passed:false};
            row.copies.push(result);
            try {
              const canvas = new OffscreenCanvas(size,size);
              const context = canvas.getContext('2d',{alpha:false,willReadFrequently});
              if (!context) throw new Error('2D copy context unavailable');
              context.drawImage(image,0,0);
              const pixels = context.getImageData(0,0,size,size).data;
              result.changedChannels = changed(pixels,direct);
              result.knownFillChangedChannels = changed(pixels,expected);
              result.sha256 = await digest(pixels);
              result.passed = result.changedChannels === 0;
            } catch (error) {
              result.error = String(error);
            }
          }
        } catch (error) {
          for (const willReadFrequently of [false,true]) {
            row.copies.push({name,willReadFrequently,passed:false,error:String(error),creationFailed:true});
          }
        } finally {
          if (image instanceof ImageBitmap) image.close();
        }
      }
      row.passed = row.copies.length === 8 && row.copies.every(copy=>copy.passed);
    } catch (error) {
      row.error = String(error);
    } finally {
      gl?.getExtension('WEBGL_lose_context')?.loseContext();
    }
  }
  return {schema:1,rows,passed:rows.length===4 && rows.every(row=>row.passed)};
}
