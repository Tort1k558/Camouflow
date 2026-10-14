"""Observe owned float16/HDR pixel operations; PNG is not a lossless HDR control."""

from __future__ import annotations

import math
import re

WIDTH = 4
HEIGHT = 2
CASES = tuple((colour, alpha) for colour in ("srgb", "display-p3") for alpha in ("opaque", "partial"))
PALETTE = ((0, 0.25, 2), (4, 1, 0.5), (-0.25, 0.5, 1.5), (1, 0, 3))


def input_values(alpha: str) -> list[float]:
    if alpha not in {"opaque", "partial"}:
        raise ValueError("Unknown HDR alpha fixture")
    return [value for pixel in range(WIDTH * HEIGHT)
            for value in (*PALETTE[pixel % 4], 1 if alpha == "opaque" else (0, 0.25, 0.5, 1)[pixel % 4])]


READ = """async () => {
  const rows = [];
  const hash = async bytes => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)),
    value => value.toString(16).padStart(2, '0')).join('');
  for (const colorSpace of ['srgb', 'display-p3']) {
    for (const alpha of ['opaque', 'partial']) {
      const canvas = new OffscreenCanvas(4, 2);
      const decoded = new OffscreenCanvas(4, 2);
      let bitmap;
      try {
        const context = canvas.getContext('2d', {colorSpace, colorType: 'float16', willReadFrequently: true});
        if (!context) throw new Error('Owned HDR Canvas unavailable');
        const attributes = context.getContextAttributes();
        const palette = [[0, 0.25, 2], [4, 1, 0.5], [-0.25, 0.5, 1.5], [1, 0, 3]];
        const data = new Float16Array(32);
        for (let i = 0; i < 8; i++) {
          data.set(palette[i % 4], i * 4);
          data[i * 4 + 3] = alpha === 'opaque' ? 1 : [0, 0.25, 0.5, 1][i % 4];
        }
        const image = new ImageData(data, 4, 2, {colorSpace, pixelFormat: 'rgba-float16'});
        context.putImageData(image, 0, 0);
        const row = {colorSpace, alpha, contextColorSpace: attributes.colorSpace,
          contextColorType: attributes.colorType, input: Array.from(data)};
        for (const operation of ['read', 'repeat']) {
          try {
            const result = context.getImageData(0, 0, 4, 2, {colorSpace, pixelFormat: 'rgba-float16'});
            row[operation] = {status: 'ok', colorSpace: result.colorSpace, pixelFormat: result.pixelFormat,
              dataType: result.data.constructor.name, values: Array.from(result.data)};
          } catch (error) {
            row[operation] = {status: 'error', name: error instanceof DOMException ? error.name : 'non-DOM-exception'};
          }
        }
        try {
          const png = await canvas.convertToBlob({type: 'image/png'});
          bitmap = await createImageBitmap(png);
          const destination = decoded.getContext('2d', {colorSpace: 'srgb', willReadFrequently: true});
          if (!destination) throw new Error('Owned PNG decode Canvas unavailable');
          destination.drawImage(bitmap, 0, 0);
          const pixels = destination.getImageData(0, 0, 4, 2).data;
          row.png = {status: 'ok', mime: png.type, bytes: png.size, width: bitmap.width, height: bitmap.height,
            rgba8Sha256: await hash(pixels), pngSha256: await hash(await png.arrayBuffer())};
        } catch (error) {
          row.png = {status: 'error', name: error instanceof DOMException ? error.name : 'non-DOM-exception'};
        }
        rows.push(row);
      } finally {bitmap?.close(); canvas.width = 0; decoded.width = 0;}
    }
  }
  return {rows};
}"""


def validate_measurement(measured: dict) -> None:
    if (not isinstance(measured, dict) or set(measured) != {"rows"}
            or not isinstance(measured["rows"], list) or len(measured["rows"]) != len(CASES)):
        raise ValueError("HDR requires all four colour/alpha fixtures")
    for row, (colour, alpha) in zip(measured["rows"], CASES, strict=True):
        if (not isinstance(row, dict) or set(row) != {"colorSpace", "alpha", "contextColorSpace", "contextColorType", "input", "read", "repeat", "png"}
                or row["colorSpace"] != colour or row["alpha"] != alpha
                or row["contextColorSpace"] != colour or row["contextColorType"] != "float16"
                or not isinstance(row["input"], list) or row["input"] != input_values(alpha)
                or any(type(value) not in (int, float) for value in row["input"])):
            raise ValueError("HDR input or context was not observed as requested")
        for operation in ("read", "repeat", "png"):
            result = row[operation]
            if not isinstance(result, dict):
                raise ValueError("HDR operation observation is missing")
            if result.get("status") == "error":
                if set(result) != {"status", "name"} or not isinstance(result["name"], str) or not result["name"]:
                    raise ValueError("HDR operation error is malformed")
            elif result.get("status") == "ok" and operation in {"read", "repeat"}:
                if (set(result) != {"status", "colorSpace", "pixelFormat", "dataType", "values"}
                        or result["colorSpace"] != colour or result["pixelFormat"] != "rgba-float16"
                        or result["dataType"] != "Float16Array" or not isinstance(result["values"], list)
                        or len(result["values"]) != WIDTH * HEIGHT * 4
                        or any(type(value) not in (int, float) or not math.isfinite(value)
                               or not -65504 <= value <= 65504 for value in result["values"])
                        or any(not 0 <= result["values"][index] <= 1 for index in range(3, 32, 4))):
                    raise ValueError("HDR float16 pixels are malformed")
            elif result.get("status") == "ok" and operation == "png":
                if (set(result) != {"status", "mime", "bytes", "width", "height", "rgba8Sha256", "pngSha256"}
                        or result["mime"] != "image/png" or type(result["bytes"]) is not int
                        or not 0 < result["bytes"] <= 1024 * 1024
                        or type(result["width"]) is not int or result["width"] != WIDTH
                        or type(result["height"]) is not int or result["height"] != HEIGHT
                        or any(not isinstance(result[key], str) or not re.fullmatch(r"[0-9a-f]{64}", result[key])
                               for key in ("rgba8Sha256", "pngSha256"))):
                    raise ValueError("HDR PNG conversion observation is malformed")
            else:
                raise ValueError("HDR operation was not observed")


def observations(measured: dict) -> list[dict]:
    validate_measurement(measured)
    result = []
    for row in measured["rows"]:
        item = {"colorSpace": row["colorSpace"], "alpha": row["alpha"],
                "repeat_matches": row["read"] == row["repeat"], "read_status": row["read"]["status"]}
        if row["read"]["status"] == "ok":
            values = row["read"]["values"]
            item.update(changed_channels=sum(first != second for first, second in zip(row["input"], values, strict=True)),
                        rgb_below_zero=sum(value < 0 for index, value in enumerate(values) if index % 4 != 3),
                        rgb_above_one=sum(value > 1 for index, value in enumerate(values) if index % 4 != 3),
                        maximum_absolute_error=max(abs(first - second) for first, second in zip(row["input"], values, strict=True)))
        result.append(item)
    return result


def compare_control(control: dict, candidate: dict) -> list[dict]:
    """Preserve measured conversion changes; equal observations are not HDR compliance."""
    validate_measurement(control)
    validate_measurement(candidate)
    differences = []
    for first, second in zip(control["rows"], candidate["rows"], strict=True):
        for operation in ("read", "repeat", "png"):
            if first[operation] != second[operation]:
                differences.append({"colorSpace": second["colorSpace"], "alpha": second["alpha"],
                                    "operation": operation, "control": first[operation], "candidate": second[operation]})
    return differences
