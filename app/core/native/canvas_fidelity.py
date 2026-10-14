"""Bounded Canvas pixel-fidelity measurements, not fingerprint acceptance."""

from __future__ import annotations

CASES = ("opaque-palette", "opaque-gradient", "transparent-palette")
WIDTH = 32
HEIGHT = 24
CHANNELS = WIDTH * HEIGHT * 4

READ = """async () => {
  const width = 32, height = 24;
  const compare = (expected, actual) => {
    if (expected.length !== actual.length) throw new Error('Pixel length changed');
    let changedChannels = 0, changedPixels = 0, alphaChanges = 0, maximumError = 0;
    for (let i = 0; i < actual.length; i += 4) {
      let changed = false;
      for (let channel = 0; channel < 4; channel++) {
        const error = Math.abs(expected[i + channel] - actual[i + channel]);
        if (error) { changedChannels++; changed = true; }
        if (channel === 3 && error) alphaChanges++;
        maximumError = Math.max(maximumError, error);
      }
      if (changed) changedPixels++;
    }
    return {changedChannels, changedPixels, alphaChanges, maximumError};
  };
  const rows = [];
  for (const name of ['opaque-palette', 'opaque-gradient', 'transparent-palette']) {
    const canvas = new OffscreenCanvas(width, height);
    const context = canvas.getContext('2d', {willReadFrequently: true});
    if (!context) throw new Error('Canvas 2D unavailable');
    const input = new Uint8ClampedArray(width * height * 4);
    for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
      const offset = (y * width + x) * 4;
      const gradient = name === 'opaque-gradient';
      input[offset] = gradient ? (x * 7 + y * 3) % 256 : [17, 52, 127, 254][x % 4];
      input[offset + 1] = gradient ? (x * 5 + y * 11) % 256 : [34, 86, 128, 255][y % 4];
      input[offset + 2] = gradient ? (x * 13 + y * 17) % 256 : 51;
      input[offset + 3] = name === 'transparent-palette' ? 128 : 255;
    }
    context.putImageData(new ImageData(input.slice(), width, height), 0, 0);
    const read = () => context.getImageData(0, 0, width, height).data;
    const first = read(), repeated = read();
    const single = context.getImageData(11, 9, 1, 1).data;
    const expectedSingle = first.slice((9 * width + 11) * 4, (9 * width + 12) * 4);
    const bitmap = await createImageBitmap(await canvas.convertToBlob({type: 'image/png'}));
    let exported;
    try {
      const copy = new OffscreenCanvas(width, height);
      const destination = copy.getContext('2d', {willReadFrequently: true});
      destination.drawImage(bitmap, 0, 0);
      exported = destination.getImageData(0, 0, width, height).data;
    } finally { bitmap.close(); }
    const copy = new OffscreenCanvas(width, height);
    const destination = copy.getContext('2d', {willReadFrequently: true});
    destination.putImageData(new ImageData(first.slice(), width, height), 0, 0);
    rows.push({name, input: compare(input, first), repeat: compare(first, repeated),
      single: compare(expectedSingle, single), export: compare(first, exported),
      rewrite: compare(first, destination.getImageData(0, 0, width, height).data)});
  }
  return {width, height, rows};
}"""


def validate_measurement(measured: dict) -> None:
    if (not isinstance(measured, dict) or set(measured) != {"width", "height", "rows"}
            or type(measured["width"]) is not int or measured["width"] != WIDTH
            or type(measured["height"]) is not int or measured["height"] != HEIGHT
            or not isinstance(measured["rows"], list) or len(measured["rows"]) != len(CASES)):
        raise ValueError("Canvas fidelity requires the complete bounded measurement")
    for row, name in zip(measured["rows"], CASES, strict=True):
        if not isinstance(row, dict) or set(row) != {"name", "input", "repeat", "single", "export", "rewrite"} or row["name"] != name:
            raise ValueError("Canvas fidelity cases are missing or out of order")
        for operation in ("input", "repeat", "single", "export", "rewrite"):
            metrics = row[operation]
            pixels = 1 if operation == "single" else WIDTH * HEIGHT
            if (not isinstance(metrics, dict)
                    or set(metrics) != {"changedChannels", "changedPixels", "alphaChanges", "maximumError"}
                    or any(type(value) is not int for value in metrics.values())
                    or not 0 <= metrics["changedPixels"] <= pixels
                    or not metrics["changedPixels"] <= metrics["changedChannels"] <= 4 * metrics["changedPixels"]
                    or not 0 <= metrics["alphaChanges"] <= metrics["changedPixels"]
                    or not 0 <= metrics["maximumError"] <= 255
                    or bool(metrics["maximumError"]) != bool(metrics["changedChannels"])):
                raise ValueError(f"Invalid Canvas fidelity metrics: {name}/{operation}")


def compare_control(control: dict, candidate: dict) -> dict:
    """Keep observed control differences, including transparent premultiplication."""
    validate_measurement(control)
    validate_measurement(candidate)
    differences = []
    for original, current in zip(control["rows"], candidate["rows"], strict=True):
        for operation in ("input", "repeat", "single", "export", "rewrite"):
            if original[operation] != current[operation]:
                differences.append({"case": current["name"], "operation": operation,
                                    "control": original[operation], "candidate": current[operation]})
    return {"matches_control": not differences, "differences": differences,
            "scope": "Pixel fidelity only; matching metrics do not prove matching pixels or anti-bot acceptance"}
