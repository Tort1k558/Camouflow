"""Independent halo/edge-colour reference model; no native or GPU admission."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIMIT = (1 << 64) - 1


def plan(frame_width: int, frame_height: int, x: int, y: int, width: int, height: int, budget: int) -> dict:
    values = (frame_width, frame_height, x, y, width, height)
    if (any(type(value) is not int or not -(1 << 31) <= value < (1 << 31) for value in values)
            or min(frame_width, frame_height) <= 0 or min(width, height) < 0
            or type(budget) is not int or not 0 <= budget <= LIMIT):
        raise ValueError("Invalid bounded readback request")
    rectangle_bytes = width * height * 4
    box = (0, 0, 0, 0)
    mode = "outside"
    if x == y == 0 and width == frame_width and height == frame_height:
        mode = "full-frame-in-place"
    elif width and height:
        left, bottom = max(0, x), max(0, y)
        right, top = min(frame_width, x + width), min(frame_height, y + height)
        if left < right and bottom < top:
            left, bottom = max(0, left - 1), max(0, bottom - 1)
            right, top = min(frame_width, right + 1), min(frame_height, top + 1)
            mode = "halo"
            box = (left, bottom, right - left, top - bottom)
    tile_bytes = box[2] * box[3] * 4
    if rectangle_bytes + tile_bytes > min(LIMIT, budget):
        raise ValueError("Readback budget exceeded")
    return {"mode": mode, "box": box, "rectangle_bytes": rectangle_bytes, "tile_bytes": tile_bytes}


def edge_colour(pixels: list[int], width: int, height: int, seed: bytes) -> list[int]:
    if (len(pixels) != width * height * 4 or not width or not height or len(seed) != 32
            or any(type(value) is not int or not 0 <= value <= 255 for value in pixels)):
        raise ValueError("Invalid reference raster")
    result = pixels.copy()
    for y in range(height):
        for x in range(width):
            offset = (y * width + x) * 4
            if pixels[offset + 3] != 255:
                continue
            colour = bytes(value >> 1 for value in pixels[offset:offset + 3])
            neighbours = ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
            edge = False
            for other_x, other_y in neighbours:
                if not 0 <= other_x < width or not 0 <= other_y < height:
                    continue
                other = (other_y * width + other_x) * 4
                if pixels[other + 3] == 255 and bytes(value >> 1 for value in pixels[other:other + 3]) != colour:
                    edge = True
                    break
            if edge:
                bits = hmac.digest(seed, b"glint.canvas.edge.candidate.v1" + colour, "sha256")[0]
                for channel in range(3):
                    result[offset + channel] = (pixels[offset + channel] & 254) | ((bits >> channel) & 1)
    return result


def rectangle(pixels: list[int], frame_width: int, frame_height: int,
              x: int, y: int, width: int, height: int) -> list[int]:
    result = [165] * (width * height * 4)
    for row in range(height):
        for column in range(width):
            if 0 <= x + column < frame_width and 0 <= y + row < frame_height:
                source = ((y + row) * frame_width + x + column) * 4
                target = (row * width + column) * 4
                result[target:target + 4] = pixels[source:source + 4]
    return result


def local_readback(pixels: list[int], frame_width: int, frame_height: int,
                   x: int, y: int, width: int, height: int, seed: bytes) -> list[int]:
    region = plan(frame_width, frame_height, x, y, width, height, LIMIT)
    result = rectangle(pixels, frame_width, frame_height, x, y, width, height)
    if region["mode"] == "full-frame-in-place":
        return edge_colour(result, width, height, seed)
    if region["mode"] == "halo":
        left, bottom, tile_width, tile_height = region["box"]
        tile = rectangle(pixels, frame_width, frame_height, left, bottom, tile_width, tile_height)
        protected = edge_colour(tile, tile_width, tile_height, seed)
        for row in range(height):
            for column in range(width):
                if 0 <= x + column < frame_width and 0 <= y + row < frame_height:
                    source = ((y + row - bottom) * tile_width + x + column - left) * 4
                    target = (row * width + column) * 4
                    result[target:target + 4] = protected[source:source + 4]
    return result


def verify() -> dict:
    checks = 0
    for seed in (bytes(range(32)), bytes([17] * 32)):
        for frame_width, frame_height in ((1, 1), (3, 3), (7, 6), (9, 7)):
            for pattern in ("uniform", "gradient", "transparent"):
                pixels = []
                for y in range(frame_height):
                    for x in range(frame_width):
                        alpha = 0 if (x + y) % 5 == 0 else 127 if (x + y) % 7 == 0 else 255
                        pixels.extend((17, 34, 51, 255) if pattern == "uniform" else
                                      ((x * 31 + y * 7) % 256, (x * 3 + y * 33) % 256, ((x + y) // 2) * 19,
                                       alpha if pattern == "transparent" else 255))
                full = edge_colour(pixels, frame_width, frame_height, seed)
                for y in range(-2, frame_height + 2):
                    for x in range(-2, frame_width + 2):
                        for height in range(5):
                            for width in range(6):
                                expected = rectangle(full, frame_width, frame_height, x, y, width, height)
                                if local_readback(pixels, frame_width, frame_height, x, y, width, height, seed) != expected:
                                    raise ValueError("Halo model disagrees with full-frame edge protection")
                                checks += 1
    tiny = plan(4096, 4096, 100, 100, 1, 1, 40)
    large = plan(4096, 4096, 0, 0, 4096, 4096, 64 * 1024 * 1024)
    return {"passed": True, "scope": __doc__, "native_compiled": False, "gpu_verified": False,
            "privacy_admitted": False, "crop_equivalence_checks": checks, "tiny_read": tiny, "full_read": large}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if (not args.report.is_absolute() or args.report.exists() or args.report.is_symlink()
            or args.report.resolve().is_relative_to(ROOT)):
        parser.error("A new absolute report outside the public checkout is required")
    names = ("scripts/verify_native_readback_regions.py", "native/drafts/canvas/canvas_readback_candidate.cc",
             "native/drafts/next-readback/rgba8_readback_region.h", "native/drafts/next-readback/rgba8_readback_region.cc",
             "native/drafts/next-readback/rgba8_readback_region_unittest.cc")
    inputs = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}
    report = verify()
    if inputs != {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}:
        raise ValueError("Reference inputs changed during verification")
    report["inputs_sha256"] = inputs
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2)
    print(json.dumps({"passed": True, "crop_equivalence_checks": report["crop_equivalence_checks"], "native_compiled": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
