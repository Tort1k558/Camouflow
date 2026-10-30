"""Owned finite binary16/alpha/crop fidelity, not broad HDR or privacy admission."""
import base64
import math
import struct


READ = r'''async () => {
 const encode = value => btoa(String.fromCharCode(...new Uint8Array(value.buffer, value.byteOffset, value.byteLength)));
 if (new Uint8Array(new Uint16Array([0x0102]).buffer)[0] !== 2) throw new Error('Owned fixture requires little-endian binary16');
 const rows = [];
 for (const kind of ['html', 'offscreen']) for (const colorSpace of ['srgb', 'display-p3']) {
  const row = {kind, colorSpace};
  const canvas = kind === 'html' ? document.createElement('canvas') : new OffscreenCanvas(16, 16);
  canvas.width = canvas.height = 16;
  try {
   const ctx = canvas.getContext('2d', {colorSpace, colorType:'float16', willReadFrequently:true});
   if (!ctx) throw new Error('Owned F16 context unavailable');
   row.attributes = ctx.getContextAttributes();
   const data = new Float16Array(16 * 16 * 4);
   const values = [-2, -1, -.125, -.001, 0, 2**-20, 2**-14, .00025177,
                   .25 + 2**-12, .5 + 2**-11, .75, .9995, 1, 1.125, 2, 4, 16, 64, 65504];
   for (let i=0; i<256; i++) {
    for (let c=0; c<3; c++) data[4*i+c] = values[(i*7+c*5)%values.length];
    data[4*i+3] = i < 64 ? 0 : i < 128 ? .5 : 1;
   }
   const inputBefore = encode(data);
   const image = new ImageData(data, 16, 16, {colorSpace, pixelFormat:'rgba-float16'});
   ctx.putImageData(image, 0, 0);
   const options = {colorSpace, pixelFormat:'rgba-float16'};
   const full = ctx.getImageData(0, 0, 16, 16, options);
   row.arrayType = full.data.constructor.name;
   row.readColorSpace = full.colorSpace; row.pixelFormat = full.pixelFormat;
   row.full = encode(full.data);
   row.repeat = encode(ctx.getImageData(0, 0, 16, 16, options).data);
   row.crop = encode(ctx.getImageData(3, 4, 9, 7, options).data);
   row.sourceBufferUnchanged = encode(data) === inputBefore;
   ctx.putImageData(image, 0, 0);
   row.afterReput = encode(ctx.getImageData(0, 0, 16, 16, options).data);
  } catch (error) { row.error = {name:error.name, message:error.message}; }
  finally { canvas.width = 0; }
  rows.push(row);
 }
 return rows;
}'''


CASES = {(kind, space) for kind in ('html', 'offscreen') for space in ('srgb', 'display-p3')}


def decode(value, expected):
    if type(value) is not str or len(value) > ((expected + 2) // 3) * 4:
        raise ValueError('Malformed or oversized owned binary16 data')
    raw = base64.b64decode(value, validate=True)
    if len(raw) != expected:
        raise ValueError('Owned binary16 byte count differs')
    return raw


def inspect_rows(rows):
    if type(rows) is not list or len(rows) != 4:
        raise ValueError('All four owned HDR contexts are required')
    seen, observed, errors = set(), {}, []
    for row in rows:
        if type(row) is not dict:
            raise ValueError('Malformed owned HDR context')
        key = row.get('kind'), row.get('colorSpace')
        if any(type(value) is not str for value in key) or key not in CASES or key in seen:
            raise ValueError('Unknown or duplicated owned HDR context')
        seen.add(key)
        if 'error' in row:
            errors.append({'kind': key[0], 'colorSpace': key[1], 'error': row['error']})
            continue
        attributes = row.get('attributes')
        if (type(attributes) is not dict or attributes.get('colorSpace') != key[1]
                or attributes.get('colorType') != 'float16' or row.get('arrayType') != 'Float16Array'
                or row.get('readColorSpace') != key[1] or row.get('pixelFormat') != 'rgba-float16'):
            raise ValueError('Owned HDR metadata differs from the requested context')
        raw = decode(row.get('full'), 2048)
        crop = b''.join(raw[(y*16+3)*8:(y*16+12)*8] for y in range(4, 11))
        if (decode(row.get('repeat'), 2048) != raw or decode(row.get('afterReput'), 2048) != raw
                or decode(row.get('crop'), 504) != crop or row.get('sourceBufferUnchanged') is not True):
            errors.append({'kind': key[0], 'colorSpace': key[1], 'error': 'Repeat/re-put/crop/input-buffer coherence differs'})
        bits = tuple(value[0] for value in struct.iter_unpack('<H', raw))
        numbers = tuple(value[0] for value in struct.iter_unpack('<e', raw))
        if any(not math.isfinite(value) for value in numbers):
            errors.append({'kind': key[0], 'colorSpace': key[1], 'error': 'Finite owned input produced nonfinite output'})
        observed[key] = bits, numbers
    return observed, errors


def compare_hdr(baseline, protected):
    reference, baseline_errors = inspect_rows(baseline)
    candidate, protected_errors = inspect_rows(protected)
    checks = []
    for key in sorted(CASES):
        if key not in reference or key not in candidate:
            continue
        before_bits, before = reference[key]
        after_bits, after = candidate[key]
        failures, changed = [], 0
        for index, (left, right) in enumerate(zip(before_bits, after_bits, strict=True)):
            alpha = before_bits[(index//4)*4+3]
            exponent = (left & 0x7c00) >> 10
            delta = left ^ right
            if index % 4 == 3 or alpha != 0x3c00 or exponent in (0, 31):
                valid = delta == 0
            else:
                valid = ((left & 0xfc00) == (right & 0xfc00)
                         and (delta == 0 or delta & (delta-1) == 0)
                         and abs(before[index] - after[index]) <= max(1/256, 2**(exponent-25)))
            if not valid:
                failures.append(index)
            changed += delta != 0
        checks.append({'kind': key[0], 'colorSpace': key[1], 'changed_channels': changed,
            'unexpected_changed_channels': failures,
            'baseline_negative_rgb_channels': sum(value < 0 for index, value in enumerate(before) if index%4 != 3),
            'baseline_hdr_rgb_channels': sum(value > 1 for index, value in enumerate(before) if index%4 != 3),
            'baseline_subnormal_channels': sum(0 < (bits & 0x7fff) < 0x400 for bits in before_bits),
            'opaque_pixels': sum(bits == 0x3c00 for bits in before_bits[3::4]),
            'nonopaque_pixels': sum(bits != 0x3c00 for bits in before_bits[3::4]),
            'passed': not failures and changed > 0})
    coverage = all(row['baseline_negative_rgb_channels'] > 0 and row['baseline_hdr_rgb_channels'] > 0
                   and row['baseline_subnormal_channels'] > 0 and row['opaque_pixels'] >= 32
                   and row['nonopaque_pixels'] >= 32 for row in checks)
    return {'baseline_signal_coverage_verified': coverage, 'passed': (coverage and not baseline_errors and not protected_errors and len(checks) == 4
                       and all(row['passed'] for row in checks)),
        'checks': checks, 'baseline_errors': baseline_errors, 'protected_errors': protected_errors,
        'privacy_admitted': False, 'production_admitted': False}
