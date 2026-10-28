"""Owned editing, web-font and export checks; not an authenticity score."""

import asyncio
from copy import deepcopy
import hashlib
import math
from pathlib import Path
import re
from urllib.parse import urlsplit

from scripts.native_font_contexts import FontFixtureHandler

NOTE = "Glint note 0123"
MIXED = "Latin / Кириллица / العربية / עברית / हिन्दी / 你好 / e\u0301 / 👩‍💻"
DRAFT = "Draft " + MIXED
APPROVED = "Approved 42 / " + MIXED
SAMPLE = "iiiiWW"
ARTIFACTS = {"workspace.png", "note.txt", "print.pdf"}
HTML = """<!doctype html><meta charset="utf-8"><title>Glint text workspace</title>
<style>
body{margin:0;background:#f3f5ef;color:#172a19;font:16px Arial,sans-serif}
main{max-width:760px;margin:28px auto}h1{font-size:24px}section{background:white;
border:1px solid #d5dece;border-radius:8px;padding:18px;margin:14px 0}
textarea,[contenteditable]{box-sizing:border-box;width:100%;font:18px Arial,sans-serif;
min-height:72px;padding:10px;border:1px solid #9da993;border-radius:4px}
.web{font:20px GlintWorkloadFont;white-space:pre}#web-dom{display:inline-block}
button{padding:10px 18px;background:#d4f569;border:1px solid #b4ce62;border-radius:4px}
canvas{display:block}svg{display:block;height:48px;width:320px}
@media print{body{background:white}button{display:none}main{margin:0}}
</style><main><h1>Glint text workspace</h1>
<section><label for="note">Plain text</label><textarea id="note" spellcheck="false"></textarea></section>
<section><div id="editor" contenteditable="true" role="textbox" spellcheck="false"></div></section>
<section><span id="selection-word">Glint</span>.</section>
<section><span id="web-dom" class="web">iiiiWW</span>
<svg><text id="web-svg" class="web" x="0" y="28">iiiiWW</text></svg>
<canvas id="web-canvas" width="320" height="64"></canvas></section>
<button id="export">Export note</button></main><script>
window.editEvents = {note: [], editor: []};
for (const id of ['note', 'editor']) document.getElementById(id).addEventListener('input', event => {
  window.editEvents[id].push({type: event.inputType, trusted: event.isTrusted});
});
document.getElementById('export').onclick = () => {
  const text = document.getElementById('note').value + '\\n' + document.getElementById('editor').innerText;
  const url = URL.createObjectURL(new Blob([text], {type:'text/plain;charset=utf-8'}));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'glint-note.txt';
  document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
};
</script>"""

READ_FONT = """async url => {
  const font = new FontFace('GlintWorkloadFont', 'url(' + JSON.stringify(url) + ')');
  await font.load(); document.fonts.add(font); await document.fonts.ready;
  const span = document.getElementById('web-dom');
  const svg = document.getElementById('web-svg');
  const canvas = document.getElementById('web-canvas');
  const context = canvas.getContext('2d', {alpha:false, colorSpace:'srgb', willReadFrequently:true});
  if (!context) throw new Error('Owned workload Canvas unavailable');
  context.fillStyle = '#ffffff'; context.fillRect(0, 0, canvas.width, canvas.height);
  context.font = '20px monospace'; const fallbackWidth = context.measureText('iiiiWW').width;
  context.font = '20px GlintWorkloadFont'; const canvasWidth = context.measureText('iiiiWW').width;
  context.fillStyle = '#172a19'; context.fillText('iiiiWW', 8, 36);
  const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
  let inkPixels = 0;
  for (let index = 0; index < pixels.length; index += 4) {
    if (pixels[index] < 255 || pixels[index + 1] < 255 || pixels[index + 2] < 255) inkPixels++;
  }
  const blob = await new Promise((resolve, reject) => canvas.toBlob(value =>
    value ? resolve(value) : reject(new Error('Owned workload PNG missing')), 'image/png'));
  const bitmap = await createImageBitmap(blob);
  let roundTripMatches;
  try {
    const decoded = document.createElement('canvas'); decoded.width = canvas.width; decoded.height = canvas.height;
    const copy = decoded.getContext('2d', {colorSpace:'srgb', willReadFrequently:true});
    if (!copy) throw new Error('Owned workload PNG decoding Canvas unavailable');
    copy.drawImage(bitmap, 0, 0);
    const restored = copy.getImageData(0, 0, canvas.width, canvas.height).data;
    roundTripMatches = pixels.length === restored.length && pixels.every((value, index) => value === restored[index]);
  } finally { bitmap.close(); }
  const digest = await crypto.subtle.digest('SHA-256', pixels);
  return {loaded: font.status === 'loaded' && document.fonts.check('20px GlintWorkloadFont'),
    domWidth: span.getBoundingClientRect().width, svgWidth: svg.getComputedTextLength(), canvasWidth, fallbackWidth,
    pixels: Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2,'0')).join(''),
    inkPixels,
    pngBytes: blob.size, roundTripMatches};
}"""


class WorkloadFixtureHandler(FontFixtureHandler):
    def do_GET(self):
        if self.path != "/owned-workload-font.ttf":
            return super().do_GET()
        body = self.server.workload_font_bytes
        self.send_response(200)
        self.send_header("Content-Type", "font/ttf")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


def validate(value: dict) -> None:
    if not isinstance(value, dict) or set(value) != {"note", "editor", "selection", "font", "download", "pdf", "artifacts"}:
        raise ValueError("Incomplete editing/font/export workload")
    for key, expected, events in (("note", NOTE, {"historyUndo", "deleteContentBackward"}),
                                  ("editor", APPROVED, {"historyUndo", "historyRedo", "insertText"})):
        row = value[key]
        if (not isinstance(row, dict) or set(row) != {"value", "undo", "events", "trusted"}
                or row["value"] != expected or row["undo"] != (NOTE if key == "note" else DRAFT)
                or row["trusted"] is not True or not isinstance(row["events"], list)
                or not 1 <= len(row["events"]) <= 64 or not all(isinstance(event, str) for event in row["events"])
                or len(set(row["events"])) != len(row["events"]) or not events.issubset(row["events"])):
            raise ValueError("Native editing/undo/redo failed")
    if (value["selection"] != {"text": "Glint", "noteRange": [0, len(NOTE)]}
            or any(type(index) is not int for index in value["selection"]["noteRange"])):
        raise ValueError(f"Native text selection failed: {value['selection']!r}")
    font = value["font"]
    if (not isinstance(font, dict) or set(font) != {"loaded", "domWidth", "svgWidth", "canvasWidth", "fallbackWidth",
                                                    "pixels", "inkPixels", "pngBytes", "roundTripMatches", "networkSha256"}
            or font["loaded"] is not True or font["roundTripMatches"] is not True
            or any(type(font[key]) not in (int, float) or not math.isfinite(font[key]) or not 0 < font[key] <= 8192
                   for key in ("domWidth", "svgWidth", "canvasWidth", "fallbackWidth"))
            or any(abs(font[key] - font["canvasWidth"]) > .03125 for key in ("domWidth", "svgWidth"))
            or abs(font["fallbackWidth"] - font["canvasWidth"]) < 1
            or type(font["inkPixels"]) is not int or not 0 < font["inkPixels"] <= 320 * 64
            or type(font["pngBytes"]) is not int or not 64 <= font["pngBytes"] <= 4 * 1024**2
            or any(not isinstance(font[key], str) or not re.fullmatch(r"[0-9a-f]{64}", font[key])
                   for key in ("pixels", "networkSha256"))):
        raise ValueError("Downloaded font, DOM/SVG/Canvas metrics or PNG round trip failed")
    text = NOTE + "\n" + APPROVED
    if value["download"] != {"text": text, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}:
        raise ValueError("Native text download changed its UTF-8 content")
    if (not isinstance(value["pdf"], dict) or set(value["pdf"]) != {"headerValid", "bytes", "screenMediaRestored"}
            or value["pdf"]["headerValid"] is not True or value["pdf"]["screenMediaRestored"] is not True
            or type(value["pdf"]["bytes"]) is not int
            or not 1024 <= value["pdf"]["bytes"] <= 8 * 1024**2):
        raise ValueError("Native PDF export is missing or invalid")
    if (not isinstance(value["artifacts"], dict) or set(value["artifacts"]) != ARTIFACTS
            or value["artifacts"]["note.txt"] != value["download"]["sha256"]
            or any(not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
                   for digest in value["artifacts"].values())):
        raise ValueError("Workload artifact hashes are incomplete")


def semantics(value: dict) -> dict:
    validate(value)
    result = deepcopy(value)
    del result["artifacts"]
    del result["font"]["pixels"], result["font"]["inkPixels"], result["font"]["pngBytes"], result["pdf"]["bytes"]
    return result


def artifacts_unchanged(directory: Path, value: dict) -> bool:
    validate(value)
    return (directory == directory.resolve() and directory.is_dir()
            and all((directory / name) == (directory / name).resolve()
                    and hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest
                    for name, digest in value["artifacts"].items()))


def assess(runs: dict, modes: tuple[str, ...]) -> dict:
    if (not isinstance(runs, dict) or not isinstance(modes, tuple) or not modes or modes[0] != "off"
            or any(not isinstance(mode, str) for mode in modes) or len(set(modes)) != len(modes)
            or set(runs) != set(modes) or any(not isinstance(rounds, list) or len(rounds) != 2 for rounds in runs.values())):
        raise ValueError("Every workload mode requires two complete starts")
    control = semantics(runs["off"][0])
    differences = [{"mode": mode, "round": index} for mode, rounds in runs.items()
                   for index, value in enumerate(rounds) if semantics(value) != control]
    return {"passed": not differences, "semantic_differences": differences,
            "scope": "Editing/selection/font metrics/export checks only; not IME, PDF content equivalence or anti-bot admission"}


async def collect(page, base_url: str, artifacts: Path, font_sha256: str) -> dict:
    origin = urlsplit(base_url)
    if (origin.scheme != "http" or origin.hostname != "127.0.0.1" or not origin.port
            or origin.username is not None or origin.password is not None or origin.path not in ("", "/")
            or origin.query or origin.fragment or not re.fullmatch(r"[0-9a-f]{64}", font_sha256)):
        raise ValueError("Workloads require the exact owned loopback font fixture")
    if not artifacts.is_absolute() or artifacts != artifacts.resolve() or artifacts.exists() or not artifacts.parent.is_dir():
        raise ValueError("Fresh canonical private workload artifacts are required")
    artifacts.mkdir()
    await page.goto(base_url.rstrip("/") + "/", wait_until="domcontentloaded", timeout=30000)
    await page.set_content(HTML, wait_until="load", timeout=30000)
    note = page.locator("#note")
    await note.fill(NOTE)
    await note.press("End")
    await note.press("Backspace")
    if await note.input_value() != NOTE[:-1]:
        raise ValueError("Native deletion changed the wrong text")
    await note.press("Control+Z")
    note_undo = await note.input_value()
    await note.press("Home")
    await note.press("Shift+End")
    note_range = await note.evaluate("element => [element.selectionStart, element.selectionEnd]")
    editor = page.locator("#editor")
    await editor.fill("Draft ")
    await editor.press("End")
    await page.keyboard.insert_text(MIXED)
    if await editor.inner_text() != DRAFT:
        raise ValueError("Unicode text insertion changed content")
    await editor.press("Control+A")
    await page.keyboard.insert_text(APPROVED)
    await editor.press("Control+Z")
    editor_undo = await editor.inner_text()
    await editor.press("Control+Y")
    await page.locator("#selection-word").dblclick()
    selection = await page.evaluate("window.getSelection().toString()")
    font_url = base_url.rstrip("/") + "/owned-workload-font.ttf"
    async with page.expect_response(font_url, timeout=10000) as response_info:
        font = await asyncio.wait_for(page.evaluate(READ_FONT, font_url), timeout=30)
    response = await response_info.value
    font["networkSha256"] = hashlib.sha256(await asyncio.wait_for(response.body(), timeout=30)).hexdigest()
    if response.status != 200 or font["networkSha256"] != font_sha256:
        raise ValueError("Workload font response differs from the measured input")
    async with page.expect_download(timeout=10000) as download_info:
        await page.locator("#export").click()
    download = await download_info.value
    if download.suggested_filename != "glint-note.txt" or await asyncio.wait_for(download.failure(), timeout=30) is not None:
        raise ValueError("Owned note download failed")
    await asyncio.wait_for(download.save_as(artifacts / "note.txt"), timeout=30)
    downloaded = (artifacts / "note.txt").read_bytes()
    pdf = await asyncio.wait_for(page.pdf(print_background=True), timeout=30)
    (artifacts / "print.pdf").write_bytes(pdf)
    await page.screenshot(path=str(artifacts / "workspace.png"), full_page=True, timeout=30000)
    events = await page.evaluate("window.editEvents")
    def edit_result(key, text, undo):
        return {"value": text, "undo": undo, "events": sorted({row["type"] for row in events[key]}),
                "trusted": bool(events[key]) and all(row["trusted"] is True for row in events[key])}
    result = {"note": edit_result("note", await note.input_value(), note_undo),
              "editor": edit_result("editor", await editor.inner_text(), editor_undo),
              "selection": {"text": selection, "noteRange": note_range}, "font": font,
              "download": {"text": downloaded.decode("utf-8"), "sha256": hashlib.sha256(downloaded).hexdigest()},
              "pdf": {"headerValid": pdf.startswith(b"%PDF-"), "bytes": len(pdf),
                      "screenMediaRestored": await page.evaluate("matchMedia('screen').matches")},
              "artifacts": {name: hashlib.sha256((artifacts / name).read_bytes()).hexdigest() for name in sorted(ARTIFACTS)}}
    validate(result)
    return result
