"""Owned DOM/SVG/Canvas samples for human inspection, not authenticity scores."""

import html
import math
import re

from scripts.native_font_rendering import FONTS

TEXT = "Glint: AaMm 0123"
HTML = """<!doctype html><meta charset="utf-8"><title>Glint rendering samples</title>
<style>
body{margin:0;background:#f3f5ef;color:#172a19;font:14px system-ui,sans-serif}
main{width:760px;margin:28px auto}h1{font-size:24px;margin:0 0 8px}
p{color:#566653;margin:0 0 24px}.labels,.samples{display:grid;grid-template-columns:repeat(3,224px);gap:12px}
.labels{padding:0 18px;margin-bottom:8px;color:#566653}.row{background:white;border:1px solid #d5dece;
border-radius:8px;padding:18px;margin-bottom:14px}.family{font:12px system-ui;margin:0 0 12px;color:#566653}
.dom{height:56px;display:flex;align-items:center;padding-left:8px}canvas,svg{display:block;width:224px;height:56px}
.samples>div{overflow:visible}svg text{fill:#172a19}
</style><main><h1>Glint rendering samples</h1>
<p>Same text and requested font. Compare layout and rasterization, not a human score.</p>
<div class="labels"><span>DOM</span><span>SVG</span><span>Canvas</span></div>
""" + "".join(
    f'<section class="row" data-font="{html.escape(font, quote=True)}">'
    f'<p class="family">{html.escape(font)}</p><div class="samples">'
    f'<div class="dom"><span style="font:{html.escape(font, quote=True)}">{TEXT}</span></div>'
    f'<svg width="224" height="56"><text x="8" y="36" style="font:{html.escape(font, quote=True)}">{TEXT}</text></svg>'
    '<canvas width="224" height="56"></canvas></div></section>' for font in FONTS
) + "</main>"

READ = """async () => {
  await document.fonts.ready;
  const result = [];
  for (const row of document.querySelectorAll('.row')) {
    const font = row.dataset.font;
    const span = row.querySelector('.dom span');
    const range = document.createRange(); range.selectNodeContents(span);
    const rect = range.getBoundingClientRect();
    const text = row.querySelector('svg text');
    const canvas = row.querySelector('canvas');
    const context = canvas.getContext('2d', {alpha: false, colorSpace: 'srgb', willReadFrequently: true});
    if (!context) throw new Error('Owned visible Canvas unavailable');
    context.fillStyle = '#ffffff'; context.fillRect(0, 0, 224, 56);
    context.font = font; context.fillStyle = '#172a19';
    context.fillText('Glint: AaMm 0123', 8, 36);
    const pixels = context.getImageData(0, 0, 224, 56).data;
    const digest = await crypto.subtle.digest('SHA-256', pixels);
    result.push({font, domWidth: rect.width, domHeight: rect.height,
      svgWidth: text.getComputedTextLength(), canvasWidth: context.measureText('Glint: AaMm 0123').width,
      canvasPixelSha256: Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, '0')).join('')});
  }
  return {rows: result};
}"""


def validate_measurement(value: dict) -> None:
    if (not isinstance(value, dict) or set(value) != {"rows"} or not isinstance(value["rows"], list)
            or len(value["rows"]) != len(FONTS)):
        raise ValueError("Visible rendering requires all three requested font samples")
    for row, font in zip(value["rows"], FONTS, strict=True):
        if (not isinstance(row, dict) or set(row) != {"font", "domWidth", "domHeight", "svgWidth", "canvasWidth", "canvasPixelSha256"}
                or row["font"] != font
                or any(type(row[key]) not in (int, float) or not math.isfinite(row[key]) or not 0 < row[key] <= 512
                       for key in ("domWidth", "domHeight", "svgWidth", "canvasWidth"))
                or not isinstance(row["canvasPixelSha256"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", row["canvasPixelSha256"])):
            raise ValueError("Visible rendering observation is incomplete or blank")


async def collect(page) -> dict:
    """Use only an owned loopback page; callers capture/inspect screenshots."""
    await page.set_content(HTML, wait_until="load", timeout=30000)
    value = await page.evaluate(READ)
    validate_measurement(value)
    return value


def compare_control(control: dict, candidate: dict) -> list[dict]:
    validate_measurement(control)
    validate_measurement(candidate)
    return [{"font": after["font"], "fields": [key for key in after if before[key] != after[key]]}
            for before, after in zip(control["rows"], candidate["rows"], strict=True) if before != after]
