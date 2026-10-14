"""Owned first-script rendering fixtures, without browser API overrides."""

from __future__ import annotations

import json

from app.core.native import canvas_fidelity
from scripts import native_canvas_formats, native_canvas_hdr, native_font_rendering
from scripts.verify_native_runtime import FixtureHandler

SCOPES = ("document", "iframe", "dedicated-classic", "dedicated-module",
          "shared-classic", "shared-module", "service-classic", "service-module")

PROBE = """let requests = 0;
const fontProbe = (async () => {
  const start = {phase: typeof document === 'undefined' ? 'worker-global' : 'parser',
    readyState: typeof document === 'undefined' ? null : document.readyState,
    requestsAtStart: requests};
  return {start, text: await (TEXT)(), fidelity: await (FIDELITY)(), formats: await (FORMATS)(), hdr: await (HDR)()};
})();
fontProbe.catch(() => {});
""".replace("TEXT", native_font_rendering.READ).replace("FIDELITY", canvas_fidelity.READ).replace("FORMATS", native_canvas_formats.READ).replace("HDR", native_canvas_hdr.READ)


def worker_source(kind: str) -> bytes:
    if kind == "dedicated":
        handler = """self.onmessage = () => {
          requests++; fontProbe.then(value => self.postMessage({value}),
            error => self.postMessage({error: String(error.message)}));
        };"""
    elif kind == "shared":
        handler = """self.onconnect = event => {
          const port = event.ports[0];
          port.onmessage = () => { requests++; fontProbe.then(value => port.postMessage({value}),
            error => port.postMessage({error: String(error.message)})); };
          port.start();
        };"""
    elif kind == "service":
        handler = """self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
        self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
        self.addEventListener('message', event => {
          requests++; event.waitUntil(fontProbe.then(value => event.ports[0].postMessage({value}),
            error => event.ports[0].postMessage({error: String(error.message)})));
        });"""
    else:
        raise ValueError("Unknown font fixture worker kind")
    return (PROBE + handler).encode("utf-8")


class FontFixtureHandler(FixtureHandler):
    def do_GET(self):
        if self.path == "/font-probe":
            body = ('<!doctype html><html><head><meta charset="utf-8"><script>'
                    + PROBE + '\nwindow.fontProbe = fontProbe;</script></head><body></body></html>').encode("utf-8")
            mime = "text/html; charset=utf-8"
        elif self.path in {f"/font-{kind}-{mode}.js"
                           for kind in ("dedicated", "shared", "service") for mode in ("classic", "module")}:
            body = worker_source(self.path.split("-")[1])
            mime = "application/javascript"
        else:
            return super().do_GET()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


WORKER_READ = """async ({kind, type}) => {
  let worker, registration, channel, timer;
  const abort = new AbortController();
  try {
    return await new Promise((resolve, reject) => {
      timer = setTimeout(() => reject(new Error('First-script font worker timed out')), 30000);
      const receive = event => event.data.error ? reject(new Error(event.data.error)) : resolve(event.data.value);
      const failed = () => reject(new Error('First-script font worker failed'));
      (async () => {
        const url = '/font-' + kind + '-' + type + '.js';
        if (kind === 'dedicated') {
          worker = new Worker(url, {type});
          worker.onmessage = receive; worker.onmessageerror = failed; worker.onerror = failed;
          worker.postMessage('measure');
        } else if (kind === 'shared') {
          worker = new SharedWorker(url, {type});
          worker.onerror = failed; worker.port.onmessage = receive; worker.port.onmessageerror = failed;
          worker.port.start(); worker.port.postMessage('measure');
        } else if (kind === 'service') {
          registration = await navigator.serviceWorker.register(url, {type, scope: '/font-scope-' + type + '/'});
          const active = registration.active || registration.installing || registration.waiting;
          if (!active) throw new Error('Font service worker missing');
          await new Promise((ready, fail) => {
            const changed = () => {
              if (active.state === 'activated') ready();
              else if (active.state === 'redundant') fail(new Error('Font service worker became redundant'));
            };
            active.addEventListener('statechange', changed, {signal: abort.signal}); changed();
          });
          channel = new MessageChannel();
          channel.port1.onmessage = receive; channel.port1.onmessageerror = failed;
          active.postMessage('measure', [channel.port2]);
        } else throw new Error('Unknown font worker kind');
      })().catch(reject);
    });
  } finally {
    clearTimeout(timer); abort.abort();
    if (worker instanceof Worker) worker.terminate();
    if (worker instanceof SharedWorker) worker.port.close();
    channel?.port1.close(); channel?.port2.close();
    if (registration) await registration.unregister();
  }
}"""


def validate_scope(scope: str, value: dict) -> None:
    if scope not in SCOPES:
        raise ValueError("Unknown font measurement scope")
    if not isinstance(value, dict) or set(value) != {"start", "text", "fidelity", "formats", "hdr"}:
        raise ValueError("First-script rendering observation is incomplete")
    expected = {"phase": "parser", "readyState": "loading", "requestsAtStart": 0} if scope in {
        "document", "iframe"} else {"phase": "worker-global", "readyState": None, "requestsAtStart": 0}
    if (not isinstance(value["start"], dict) or value["start"] != expected
            or type(value["start"].get("requestsAtStart")) is not int):
        raise ValueError("Rendering did not start in the owned first script")
    native_font_rendering.validate_measurement(value["text"])
    canvas_fidelity.validate_measurement(value["fidelity"])
    native_canvas_formats.validate_measurement(value["formats"])
    native_canvas_hdr.validate_measurement(value["hdr"])


async def collect(page, base_url: str) -> dict:
    """Collect a fresh owned page; callers own browser/profile cleanup."""
    result = {}
    await page.goto(base_url + "/font-probe", wait_until="domcontentloaded", timeout=30000)
    result["document"] = await page.evaluate("window.fontProbe")
    await page.evaluate("""() => new Promise((resolve, reject) => {
      const frame = document.createElement('iframe'); frame.name = 'font-child';
      const timer = setTimeout(() => reject(new Error('Font iframe timed out')), 30000);
      frame.onload = () => {clearTimeout(timer); resolve();};
      frame.onerror = () => {clearTimeout(timer); reject(new Error('Font iframe failed'));};
      frame.src = '/font-probe'; document.body.appendChild(frame);
    })""")
    frame = page.frame(name="font-child")
    if frame is None:
        raise ValueError("Owned font iframe is missing")
    result["iframe"] = await frame.evaluate("window.fontProbe")
    for scope in SCOPES[2:]:
        kind, mode = scope.split("-", 1)
        result[scope] = await page.evaluate(WORKER_READ, {"kind": kind, "type": mode})
    for scope, value in result.items():
        validate_scope(scope, value)
    # Verify serialization while the owned browser is still available for cleanup.
    json.dumps(result, allow_nan=False)
    return result
