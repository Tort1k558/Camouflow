"""Bounded text-rasterization observations; not fingerprint or font-identity proof."""

from __future__ import annotations

import math
import re

FONTS = ("20px Arial", "20px Times New Roman", "20px monospace")
METRICS = ("width", "actualBoundingBoxLeft", "actualBoundingBoxRight",
           "actualBoundingBoxAscent", "actualBoundingBoxDescent",
           "fontBoundingBoxAscent", "fontBoundingBoxDescent")
HASHES = ("pixels", "repeat", "pngPixels", "bitmapPixels", "png", "pngRepeat")

READ = """async () => {
  const digest = async bytes => Array.from(new Uint8Array(
    await crypto.subtle.digest('SHA-256', bytes)), value => value.toString(16).padStart(2, '0')).join('');
  const rows = [];
  for (const font of ['20px Arial', '20px Times New Roman', '20px monospace']) {
    for (const opaque of [true, false]) {
      const canvas = new OffscreenCanvas(192, 64);
      const copy = new OffscreenCanvas(192, 64);
      let pngBitmap, directBitmap;
      try {
        const context = canvas.getContext('2d', {colorSpace: 'srgb', willReadFrequently: true});
        const destination = copy.getContext('2d', {colorSpace: 'srgb', willReadFrequently: true});
        if (!context || !destination) throw new Error('Text rasterization context unavailable');
        if (opaque) { context.fillStyle = '#ffffff'; context.fillRect(0, 0, 192, 64); }
        context.font = font;
        context.fillStyle = '#172a19';
        const text = 'Glint: AaMm 0123';
        context.fillText(text, 8, 40);
        const measured = context.measureText(text);
        const metrics = Object.fromEntries(['width', 'actualBoundingBoxLeft', 'actualBoundingBoxRight',
          'actualBoundingBoxAscent', 'actualBoundingBoxDescent', 'fontBoundingBoxAscent',
          'fontBoundingBoxDescent'].map(name => [name, measured[name]]));
        const pixels = context.getImageData(0, 0, 192, 64).data;
        const repeat = context.getImageData(0, 0, 192, 64).data;
        const png = await canvas.convertToBlob({type: 'image/png'});
        const pngRepeat = await canvas.convertToBlob({type: 'image/png'});
        pngBitmap = await createImageBitmap(png);
        destination.drawImage(pngBitmap, 0, 0);
        const pngPixels = destination.getImageData(0, 0, 192, 64).data;
        destination.clearRect(0, 0, 192, 64);
        directBitmap = await createImageBitmap(canvas);
        destination.drawImage(directBitmap, 0, 0);
        const bitmapPixels = destination.getImageData(0, 0, 192, 64).data;
        let inkPixels = 0;
        for (let i = 0; i < pixels.length; i += 4) {
          if (opaque ? pixels[i] !== 255 || pixels[i + 1] !== 255 || pixels[i + 2] !== 255
                     : pixels[i + 3] !== 0) inkPixels++;
        }
        rows.push({font, opaque, metrics, inkPixels, mime: png.type, pngBytes: png.size,
          hashes: {pixels: await digest(pixels), repeat: await digest(repeat),
            pngPixels: await digest(pngPixels), bitmapPixels: await digest(bitmapPixels),
            png: await digest(await png.arrayBuffer()), pngRepeat: await digest(await pngRepeat.arrayBuffer())}});
      } finally {
        pngBitmap?.close(); directBitmap?.close(); canvas.width = 0; copy.width = 0;
      }
    }
  }
  return {rows};
}"""


def validate_measurement(measured: dict) -> None:
    if (not isinstance(measured, dict) or set(measured) != {"rows"}
            or not isinstance(measured["rows"], list) or len(measured["rows"]) != 6):
        raise ValueError("Text rendering requires all six observations")
    expected = [(font, opaque) for font in FONTS for opaque in (True, False)]
    for row, (font, opaque) in zip(measured["rows"], expected, strict=True):
        if (not isinstance(row, dict)
                or set(row) != {"font", "opaque", "metrics", "inkPixels", "mime", "pngBytes", "hashes"}
                or row["font"] != font or row["opaque"] is not opaque
                or row["mime"] != "image/png" or type(row["pngBytes"]) is not int
                or not 0 < row["pngBytes"] <= 1024 * 1024
                or type(row["inkPixels"]) is not int or not 0 < row["inkPixels"] <= 192 * 64):
            raise ValueError("Text rendering observation is incomplete or blank")
        metrics = row["metrics"]
        if (not isinstance(metrics, dict) or set(metrics) != set(METRICS)
                or any(type(value) not in (int, float) or not math.isfinite(value)
                       or not -1024 <= value <= 1024 for value in metrics.values())
                or metrics["width"] <= 0):
            raise ValueError("Text metrics are invalid")
        hashes = row["hashes"]
        if (not isinstance(hashes, dict) or set(hashes) != set(HASHES)
                or any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
                       for value in hashes.values())):
            raise ValueError("Text pixel/export hashes are invalid")


def consistency_observations(measured: dict) -> list[dict]:
    """Retain differences; transparent premultiplication needs a measured control."""
    validate_measurement(measured)
    differences = []
    for row in measured["rows"]:
        for reference, operation in (("pixels", "repeat"), ("pixels", "pngPixels"),
                                     ("pixels", "bitmapPixels"), ("png", "pngRepeat")):
            if row["hashes"][reference] != row["hashes"][operation]:
                differences.append({"font": row["font"], "opaque": row["opaque"],
                                    "reference": reference, "operation": operation})
    return differences


def compare_control(control: dict, candidate: dict) -> list[dict]:
    """Report changes, not whether a changed rendering is realistic or desirable."""
    validate_measurement(control)
    validate_measurement(candidate)
    differences = []
    for before, after in zip(control["rows"], candidate["rows"], strict=True):
        fields = [key for key in ("metrics", "inkPixels", "hashes") if before[key] != after[key]]
        if fields:
            differences.append({"font": after["font"], "opaque": after["opaque"], "fields": fields})
    return differences
