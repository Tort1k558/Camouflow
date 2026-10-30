"""Owned main-document PNG/capture coherence probe, not privacy admission."""

import base64
import hashlib


READ = r'''async () => {
  const rows = [];
  const encode = bytes => btoa(String.fromCharCode(...bytes));
  for (const kind of ['html', 'offscreen']) {
    for (const colorSpace of ['srgb', 'display-p3']) {
      for (const colorType of ['unorm8', 'float16']) {
        const row = {kind, colorSpace, colorType};
        const canvas = kind === 'html' ? document.createElement('canvas') : new OffscreenCanvas(16, 16);
        canvas.width = canvas.height = 16;
        try {
          const ctx = canvas.getContext('2d', {colorSpace, colorType, willReadFrequently: true});
          if (!ctx) throw new Error('Owned Canvas context unavailable');
          row.attributes = ctx.getContextAttributes();
          const gradient = ctx.createLinearGradient(0, 0, 16, 16);
          gradient.addColorStop(0, '#234567'); gradient.addColorStop(1, '#cda987');
          ctx.fillStyle = gradient; ctx.fillRect(0, 0, 16, 16);
          ctx.fillStyle = '#db613f'; ctx.fillRect(2, 3, 5, 7);
          ctx.fillStyle = '#efe397'; ctx.font = '8px sans-serif'; ctx.fillText('Glint', 0, 12);
          const pixels = () => ctx.getImageData(0, 0, 16, 16, {colorSpace, pixelFormat: 'rgba-unorm8'});
          const before = pixels();
          row.before = encode(before.data);
          row.readColorSpace = before.colorSpace;
          row.readPixelFormat = before.pixelFormat;
          row.exports = {};
          if (kind === 'html') row.exports.dataURL = canvas.toDataURL('image/png').split(',')[1];
          const pending = kind === 'html' ? new Promise((resolve, reject) => canvas.toBlob(
            blob => blob ? resolve(blob) : reject(new Error('Owned PNG export returned null')), 'image/png'))
            : canvas.convertToBlob({type: 'image/png'});
          ctx.fillStyle = '#000000'; ctx.fillRect(0, 0, 16, 16);
          row.after = encode(pixels().data);
          const blob = await pending;
          if (blob.type !== 'image/png' || blob.size > 1024 * 1024) throw new Error('Unexpected owned PNG export');
          row.exports.asyncSnapshot = encode(new Uint8Array(await blob.arrayBuffer()));
        } catch (error) {
          row.error = {name: error.name, message: error.message};
        } finally { canvas.width = 0; }
        rows.push(row);
      }
    }
  }
  return rows;
}'''

CASES = {(kind, space, storage) for kind in ('html', 'offscreen')
         for space in ('srgb', 'display-p3') for storage in ('unorm8', 'float16')}


def bounded_base64(value, maximum):
    if type(value) is not str or len(value) > ((maximum + 2) // 3) * 4:
        raise ValueError('Owned image payload is malformed or oversized')
    data = base64.b64decode(value, validate=True)
    if len(data) > maximum:
        raise ValueError('Owned image payload is oversized')
    return data


def decode_png(encoded):
    from PyQt6.QtGui import QImage

    data = bounded_base64(encoded, 1024 * 1024)
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('Owned image is not PNG')
    # Bound dimensions before invoking the existing application image decoder.
    if data[12:16] != b'IHDR' or data[16:24] != b'\x00\x00\x00\x10' * 2:
        raise ValueError('Unexpected owned PNG dimensions')
    image = QImage.fromData(data, 'PNG')
    if image.isNull() or (image.width(), image.height()) != (16, 16):
        raise ValueError('Owned PNG decoding failed')
    space = image.colorSpace()
    profile = {'valid': space.isValid(), 'description': space.description(),
               'primaries': space.primaries().name, 'transfer': space.transferFunction().name}
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    raw = rgba.constBits().asstring(rgba.sizeInBytes())
    if rgba.bytesPerLine() != 64 or len(raw) != 1024:
        raise ValueError('Unexpected owned decoded layout')
    return raw, profile


def validate_exports(observed):
    if type(observed) is not list or len(observed) != len(CASES):
        raise ValueError('Owned Canvas export matrix is incomplete')
    seen = set()
    rows = []
    for row in observed:
        if type(row) is not dict:
            raise ValueError('Malformed owned Canvas row')
        case = tuple(row.get(key) for key in ('kind', 'colorSpace', 'colorType'))
        if any(type(value) is not str for value in case) or case not in CASES or case in seen:
            raise ValueError('Owned Canvas export matrix has a duplicate or unknown case')
        seen.add(case)
        summary = {key: row.get(key) for key in ('kind', 'colorSpace', 'colorType', 'attributes', 'error')}
        summary['exports'] = {}
        summary['passed'] = False
        if 'error' not in row:
            attributes = row.get('attributes')
            exports = row.get('exports')
            carriers = {'dataURL', 'asyncSnapshot'} if case[0] == 'html' else {'asyncSnapshot'}
            if (type(attributes) is not dict or type(exports) is not dict or set(exports) != carriers
                    or attributes.get('colorSpace') != case[1] or attributes.get('colorType') != case[2]
                    or row.get('readColorSpace') != case[1] or row.get('readPixelFormat') != 'rgba-unorm8'):
                raise ValueError('Owned Canvas metadata or export carriers differ from the requested case')
            before = bounded_base64(row.get('before'), 1024)
            after = bounded_base64(row.get('after'), 1024)
            if len(before) != 1024 or len(after) != 1024:
                raise ValueError('Owned Canvas pixel count differs')
            summary['mutation_changed_source'] = before != after
            for name, encoded in exports.items():
                pixels, profile = decode_png(encoded)
                different = sum(left != right for left, right in zip(before, pixels, strict=True))
                expected_primaries = 'DciP3D65' if case[1] == 'display-p3' else 'SRgb'
                tagged_correctly = (profile['valid'] and profile['primaries'] == expected_primaries
                                    and profile['transfer'] == 'SRgb')
                color_matches = tagged_correctly or (case[1] == 'srgb' and not profile['valid'])
                summary['exports'][name] = {'matches_pre_mutation_pixels': different == 0,
                    'different_bytes': different, 'decoded_color_space': profile,
                    'color_space_matches_request': color_matches,
                    'sha256': hashlib.sha256(pixels).hexdigest()}
            summary['passed'] = (summary['mutation_changed_source']
                                 and all(value['matches_pre_mutation_pixels'] and value['color_space_matches_request']
                                         for value in summary['exports'].values()))
        rows.append(summary)
    return {'passed': all(row['passed'] for row in rows), 'rows': rows,
            'scope': __doc__, 'privacy_admitted': False, 'production_admitted': False}
