"""Observe Canvas colour-space/storage API compatibility, not HDR fidelity."""

CASES = (("srgb", "rgba-unorm8"), ("display-p3", "rgba-unorm8"),
         ("srgb", "rgba-float16"), ("display-p3", "rgba-float16"))

READ = """async () => {
  const rows = [];
  for (const [colorSpace, pixelFormat] of [
      ['srgb', 'rgba-unorm8'], ['display-p3', 'rgba-unorm8'],
      ['srgb', 'rgba-float16'], ['display-p3', 'rgba-float16']]) {
    const canvas = new OffscreenCanvas(16, 16);
    try {
      const colorType = pixelFormat === 'rgba-float16' ? 'float16' : 'unorm8';
      const context = canvas.getContext('2d', {colorSpace, colorType, willReadFrequently: true});
      if (!context) throw new Error('Owned Canvas context unavailable');
      context.fillStyle = 'rgb(17, 34, 51)';
      context.fillRect(0, 0, 16, 16);
      const attributes = context.getContextAttributes();
      const row = {colorSpace, pixelFormat, contextColorSpace: attributes.colorSpace,
        contextColorType: attributes.colorType};
      try {
        const image = context.getImageData(0, 0, 16, 16, {colorSpace, pixelFormat});
        row.read = {status: 'ok', colorSpace: image.colorSpace, pixelFormat: image.pixelFormat,
          dataType: image.data.constructor.name, length: image.data.length,
          finite: image.data.every(Number.isFinite)};
      } catch (error) {
        row.read = {status: 'error', name: error instanceof DOMException ? error.name : 'non-DOM-exception'};
      }
      try {
        const blob = await canvas.convertToBlob({type: 'image/png'});
        row.export = {status: 'ok', mime: blob.type, bytes: blob.size};
      } catch (error) {
        row.export = {status: 'error', name: error instanceof DOMException ? error.name : 'non-DOM-exception'};
      }
      rows.push(row);
    } finally { canvas.width = 0; }
  }
  return {rows};
}"""

WORKER_READ = """async code => {
  const source = '(' + code + ')().then(value => self.postMessage({value}), '
    + 'error => self.postMessage({error: String(error.message)}));';
  const url = URL.createObjectURL(new Blob([source], {type: 'text/javascript'}));
  let worker, timer;
  try {
    return await new Promise((resolve, reject) => {
      timer = setTimeout(() => reject(new Error('Owned Canvas format worker timed out')), 30000);
      worker = new Worker(url);
      worker.onmessage = event => {
        if (event.data.error) reject(new Error(event.data.error));
        else resolve(event.data.value);
      };
      worker.onerror = () => reject(new Error('Owned Canvas format worker failed'));
      worker.onmessageerror = () => reject(new Error('Owned Canvas format worker response failed'));
    });
  } finally { clearTimeout(timer); worker?.terminate(); URL.revokeObjectURL(url); }
}"""


def validate_measurement(measured: dict) -> None:
    if (not isinstance(measured, dict) or set(measured) != {"rows"}
            or not isinstance(measured["rows"], list) or len(measured["rows"]) != len(CASES)):
        raise ValueError("Canvas format coverage is incomplete")
    for row, (colour, storage) in zip(measured["rows"], CASES, strict=True):
        if (not isinstance(row, dict) or set(row) != {"colorSpace", "pixelFormat", "contextColorSpace", "contextColorType", "read", "export"}
                or row["colorSpace"] != colour or row["pixelFormat"] != storage
                or row["contextColorSpace"] != colour
                or row["contextColorType"] != ("float16" if storage == "rgba-float16" else "unorm8")):
            raise ValueError("Canvas format was not observed as requested")
        for operation in ("read", "export"):
            result = row[operation]
            if not isinstance(result, dict):
                raise ValueError("Canvas format operation is malformed")
            if result.get("status") == "error":
                if set(result) != {"status", "name"} or not isinstance(result["name"], str) or not result["name"]:
                    raise ValueError("Canvas format error was not observed")
            elif operation == "read" and result.get("status") == "ok":
                expected_type = "Uint8ClampedArray" if storage == "rgba-unorm8" else "Float16Array"
                if (set(result) != {"status", "colorSpace", "pixelFormat", "dataType", "length", "finite"}
                        or result["colorSpace"] != colour or result["pixelFormat"] != storage
                        or result["dataType"] != expected_type or type(result["length"]) is not int
                        or result["length"] != 1024 or result["finite"] is not True):
                    raise ValueError("Canvas storage/colour-space observation is inconsistent")
            elif operation == "export" and result.get("status") == "ok":
                if (set(result) != {"status", "mime", "bytes"} or result["mime"] != "image/png"
                        or type(result["bytes"]) is not int or not 0 < result["bytes"] <= 1024 * 1024):
                    raise ValueError("Canvas PNG observation is invalid")
            else:
                raise ValueError("Canvas format operation was not completed")


def compare_control(control: dict, candidate: dict) -> list[dict]:
    validate_measurement(control)
    validate_measurement(candidate)
    differences = []
    for original, current in zip(control["rows"], candidate["rows"], strict=True):
        for operation in ("read", "export"):
            first, second = original[operation], current[operation]
            # PNG lengths are content observations, not API compatibility verdicts.
            if (first["status"], first.get("name")) != (second["status"], second.get("name")):
                differences.append({"colorSpace": current["colorSpace"], "pixelFormat": current["pixelFormat"],
                                    "operation": operation, "control": first, "candidate": second})
    return differences
