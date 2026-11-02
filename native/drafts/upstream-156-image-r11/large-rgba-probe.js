async () => {
  const size = 4096, bytes = size*size*4;
  const hash = async data => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',data)),
    byte=>byte.toString(16).padStart(2,'0')).join('');
  const result = {schema:1,width:size,height:size,byteLength:bytes,api:'webgl2',alpha:false,
    copies:[],passed:false};
  let gl;
  try {
    const source = new OffscreenCanvas(size,size);
    gl = source.getContext('webgl2',{alpha:false,antialias:false,preserveDrawingBuffer:true});
    if (!gl) throw new Error('Large opaque WebGL2 context unavailable');
    if (gl.getParameter(gl.MAX_TEXTURE_SIZE) < size) throw new Error('Required texture size unavailable');
    gl.disable(gl.DITHER);
    gl.clearColor(17/255,34/255,51/255,1);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.enable(gl.SCISSOR_TEST);
    for (let x=0;x<8;x++) for (let y=0;y<8;y++) {
      const rgb = [(x*53+y*17+23)%256,(x*31+y*71+91)%256,(x*97+y*13+47)%256];
      gl.scissor(x,y,1,1);
      gl.clearColor(rgb[0]/255,rgb[1]/255,rgb[2]/255,1);
      gl.clear(gl.COLOR_BUFFER_BIT);
    }
    gl.disable(gl.SCISSOR_TEST);
    let direct = new Uint8Array(bytes);
    gl.readPixels(0,0,size,size,gl.RGBA,gl.UNSIGNED_BYTE,direct);
    if (gl.getError() !== gl.NO_ERROR) throw new Error('Large direct read failed');
    const row = new Uint8Array(size*4);
    for (let y=0;y<size/2;y++) {
      const top=y*size*4,bottom=(size-y-1)*size*4;
      row.set(direct.subarray(top,top+row.length));
      direct.copyWithin(top,bottom,bottom+row.length);
      direct.set(row,bottom);
    }
    result.opaqueAlphaPixels = 0;
    for (let offset=3;offset<bytes;offset+=4) result.opaqueAlphaPixels += direct[offset] === 255;
    result.fixtureChangedChannels = 0;
    for (let x=0;x<8;x++) for (let y=0;y<8;y++) {
      const rgba = [(x*53+y*17+23)%256,(x*31+y*71+91)%256,(x*97+y*13+47)%256,255];
      const offset=((size-y-1)*size+x)*4;
      for (let c=0;c<4;c++) result.fixtureChangedChannels += direct[offset+c] !== rgba[c];
    }
    result.directSha256 = await hash(direct);
    direct = null;
    const paths = [
      ['drawImage',async()=>source],
      ['png',async()=>createImageBitmap(await source.convertToBlob({type:'image/png'}),{colorSpaceConversion:'none'})],
      ['transferToImageBitmap',async()=>source.transferToImageBitmap()]
    ];
    for (const [name,create] of paths) {
      let image;
      try {
        image = await create();
        for (const willReadFrequently of [false,true]) {
          const copy = {name,willReadFrequently,passed:false};
          result.copies.push(copy);
          const target = new OffscreenCanvas(size,size);
          try {
            const context = target.getContext('2d',{alpha:false,willReadFrequently});
            if (!context) throw new Error('Large destination context unavailable');
            context.drawImage(image,0,0);
            const pixels = context.getImageData(0,0,size,size).data;
            copy.sha256 = await hash(pixels);
            copy.passed = copy.sha256 === result.directSha256;
          } catch (error) {
            copy.error = String(error);
          } finally {
            target.width = target.height = 1;
          }
        }
      } catch (error) {
        for (const willReadFrequently of [false,true])
          result.copies.push({name,willReadFrequently,passed:false,error:String(error)});
      } finally {
        if (image instanceof ImageBitmap) image.close();
      }
    }
    const cleared = new Uint8Array(4);
    gl.readPixels(0,0,1,1,gl.RGBA,gl.UNSIGNED_BYTE,cleared);
    result.afterTransfer = {pixel:Array.from(cleared),error:gl.getError(),lost:gl.isContextLost()};
    result.passed = result.opaqueAlphaPixels === size*size && result.fixtureChangedChannels > 0 &&
      result.copies.length === 6 && result.copies.every(copy=>copy.passed) &&
      result.afterTransfer.error === 0 && !result.afterTransfer.lost &&
      result.afterTransfer.pixel.every((byte,index)=>byte === (index===3?255:0));
  } catch (error) {
    result.error = String(error);
  } finally {
    gl?.getExtension('WEBGL_lose_context')?.loseContext();
  }
  return result;
}
