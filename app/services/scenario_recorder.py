"""Browser action capture using the existing replay frame selectors."""

from __future__ import annotations

import copy
import asyncio
import time
from urllib.parse import urlsplit

RECORDING_ENGINES = frozenset({"camoufox", "native"})


RECORDER_SCRIPT = r"""
(() => {
    // document.open can clear listeners without replacing the document or window.
    const previous = window.__camouflowRecorderState;
    previous?.controller.abort();
    const pending = previous?.document === document ? previous.pending : new Set();
    const controller = new AbortController();
    window.__camouflowRecorderState = {document, pending, controller};
    window.__camouflowRecording = true;
    window.__camouflowRecordingDocument = document;
    let enterForm = null;
    let enterAt = 0;
    const send = payload => {
        const task = window.__camouflowRecord(payload).catch(() => { window.__camouflowRecordingError = true; });
        pending.add(task);
        task.finally(() => pending.delete(task));
    };
    window.__camouflowStopRecording = async () => {
        window.__camouflowRecording = false;
        await Promise.all([...pending]);
        return Boolean(window.__camouflowRecordingError);
    };
    const selector = el => {
        for (const attr of ['data-testid', 'id', 'name', 'aria-label', 'placeholder', 'title']) {
            const value = el.getAttribute(attr);
            if (!value || value.includes('{{')) continue;
            const candidate = el.tagName.toLowerCase() + '[' + attr + '=' + JSON.stringify(value) + ']';
            try {
                if (document.querySelectorAll(candidate).length === 1) return candidate;
            } catch (_) {}
        }
        if (el.matches('button,a,[role="button"],[role="link"]')) {
            const text = el.textContent.trim().replace(/\s+/g, ' ');
            const tag = el.tagName.toLowerCase();
            if (text && text.length <= 100 && !text.includes('{{') &&
                [...document.querySelectorAll(tag)].filter(item => item.textContent.trim().replace(/\s+/g, ' ') === text).length === 1) {
                return tag + ':text-is(' + JSON.stringify(text) + ')';
            }
        }
        return '';
    };
    const emit = (el, action, value = '') => {
        if (!window.__camouflowRecording) return;
        const target = selector(el);
        if (!target) { send({warning: 'An element has no unique stable selector. Add this step manually.'}); return; }
        const password = el.type === 'password';
        const sensitive = password || /password|one-time-code|cc-number|cc-csc/i.test(el.getAttribute('autocomplete') || '');
        const label = (el.getAttribute('aria-label') || (el.labels && el.labels[0] ? el.labels[0].textContent : '') || el.getAttribute('placeholder') || '').trim().replace(/\s+/g, ' ').slice(0, 100);
        send({action, selector: target, value: sensitive && action === 'type' ? '' : value, sensitive, password, field_label: label});
    };
    document.addEventListener('click', event => {
        if (!event.isTrusted || event.button !== 0) return;
        if (event.target.closest('label')) return;
        const el = event.target.closest('button,a,input,textarea,select,[role="button"],[role="link"]');
        if (!el) { send({warning: 'A non-standard click target was skipped. Review the recording.'}); return; }
        if (event.detail === 0 && enterForm && el.form === enterForm && performance.now() - enterAt < 1000) return;
        if (el.matches('textarea,select,input:not([type="submit"]):not([type="button"])')) return;
        emit(el, 'click');
    }, {capture: true, signal: controller.signal});
    document.addEventListener('input', event => {
        if (!event.isTrusted) return;
        const el = event.target;
        if (el.matches('textarea,input:not([type="checkbox"]):not([type="radio"]):not([type="file"])')) emit(el, 'type', el.value);
        else if (el.isContentEditable) send({warning: 'Rich-text editor input is not supported. Add this step manually.'});
    }, {capture: true, signal: controller.signal});
    document.addEventListener('change', event => {
        if (!event.isTrusted) return;
        const el = event.target;
        if (el.matches('select')) {
            if (el.multiple) send({warning: 'Multiple selection is not supported. Add this step manually.'});
            else emit(el, 'select_option', el.value);
        } else if (el.matches('input[type="checkbox"],input[type="radio"]')) emit(el, 'set_checked', el.checked ? 'true' : 'false');
        else if (el.matches('input[type="file"]')) send({warning: 'File uploads are not recorded.'});
    }, {capture: true, signal: controller.signal});
    document.addEventListener('keydown', event => {
        if (event.isTrusted && event.key === 'Enter' && event.target.matches('input')) {
            enterForm = event.target.form;
            enterAt = performance.now();
            emit(event.target, 'press', 'Enter');
        }
    }, {capture: true, signal: controller.signal});
})();
"""

FRAME_SELECTOR_SCRIPT = r"""el => {
    for (const attr of ['data-testid', 'id', 'name', 'aria-label', 'title']) {
        const value = el.getAttribute(attr);
        if (!value || value.includes('{{')) continue;
        const candidate = el.tagName.toLowerCase() + '[' + attr + '=' + JSON.stringify(value) + ']';
        try {
            if (el.ownerDocument.querySelectorAll(candidate).length === 1) return candidate;
        } catch (_) {}
    }
    return '';
}"""


class ScenarioRecorder:
    MAX_STEPS = 1000

    def __init__(self, on_change=None):
        self.steps = [{"action": "start", "tag": "Start"}]
        self.warnings = []
        self.active = False
        self.page = None
        self._last_action_at = 0.0
        self._secrets = {}
        self._event_lock = asyncio.Lock()
        self._on_change = on_change or (lambda: None)

    def snapshot(self):
        return copy.deepcopy(self.steps), list(self.warnings)

    def warn(self, message):
        if message not in self.warnings and len(self.warnings) < 20:
            self.warnings.append(message)
            self._on_change()

    def _append(self, step):
        if len(self.steps) >= self.MAX_STEPS:
            self.active = False
            self.warn("Recording stopped at 1,000 steps. Save or discard this draft.")
            return
        step["tag"] = f"Step{len(self.steps)}"
        self.steps.append(step)
        self._on_change()

    async def _frame_selectors(self, frame):
        selectors = []
        while frame != self.page.main_frame:
            if frame is None or len(selectors) >= 8:
                self.warn("A frame outside the recorded document or deeper than 8 levels was skipped.")
                return None
            try:
                element = await frame.frame_element()
                selector = await element.evaluate(FRAME_SELECTOR_SCRIPT)
            except Exception:
                self.warn("A detached frame action was skipped; review the draft.")
                return None
            if not isinstance(selector, str) or not selector or len(selector) > 2000:
                self.warn("An iframe needs a unique stable id, name or test attribute to record its actions.")
                return None
            selectors.insert(0, selector)
            frame = frame.parent_frame
        return selectors

    async def _receive_event(self, source, payload):
        async with self._event_lock:
            if not self.active or source["page"] != self.page:
                return
            selectors = await self._frame_selectors(source["frame"])
            if selectors is not None:
                self.receive(source, payload, frame_selectors=selectors)

    def receive(self, source, payload, *, frame_selectors=None):
        if not self.active or not isinstance(payload, dict):
            return
        if source["page"] != self.page or (source["frame"] != self.page.main_frame and frame_selectors is None):
            self.warn("An action outside the recorded tab or with no verified frame was skipped.")
            return
        if payload.get("warning"):
            self.warn(str(payload["warning"])[:200])
            return
        action = payload.get("action")
        selector = payload.get("selector")
        value = payload.get("value", "")
        if action not in {"click", "type", "select_option", "set_checked", "press"}:
            return
        if not isinstance(selector, str) or not selector or len(selector) > 2000 or "{{" in selector:
            self.warn("An unsupported selector was skipped.")
            return
        if not isinstance(value, str) or len(value) > 10000:
            self.warn("An oversized field was skipped.")
            return
        step = {"action": action, "selector": selector, "selector_type": "css", "timeout_ms": 15000}
        if frame_selectors:
            step["frame_selector"] = list(frame_selectors)
        label = payload.get("field_label")
        if isinstance(label, str) and label.strip():
            step["field_label"] = label.strip()[:100]
        if action == "type" and payload.get("sensitive"):
            scope = (tuple(frame_selectors or []), selector)
            variable = "password" if payload.get("password") else self._secrets.setdefault(scope, f"recorded_secret_{len(self._secrets) + 1}")
            value = "{{" + variable + "}}"
            step["required_variable"] = variable
            self.warn("Sensitive fields use profile variables; their values are not recorded.")
        elif action == "type" and "{{" in value:
            self.warn("Template syntax in typed text needs manual review; this input was skipped.")
            return
        if action != "click":
            step["value"] = value
        if action == "type":
            step["clear"] = True
        if action == "type" and self.steps[-1].get("action") == "type" and self.steps[-1].get("selector") == selector and self.steps[-1].get("frame_selector", []) == (frame_selectors or []):
            step["tag"] = self.steps[-1]["tag"]
            self.steps[-1] = step
            self._on_change()
        else:
            self._append(step)
        self._last_action_at = time.monotonic()

    def navigated(self, frame):
        if not self.active:
            return
        if frame != self.page.main_frame:
            return
        url = frame.url
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"}:
            self.warn("Only HTTP and HTTPS navigation is recorded.")
            return
        if parsed.username or parsed.password or "{{" in url:
            self.warn("A URL containing credentials or template syntax was not recorded.")
            return
        if self.steps[-1].get("action") in {"click", "press", "select_option"} and time.monotonic() - self._last_action_at < 5:
            self._append({"action": "wait_for_load_state", "state": "domcontentloaded"})
        else:
            self._append({"action": "goto", "url": url, "value": url})

    async def attach(self, page):
        self.page = page
        self.active = True
        await page.context.expose_binding("__camouflowRecord", self._receive_event)
        await page.evaluate("window.__camouflowRecord({})")
        await page.context.add_init_script(RECORDER_SCRIPT)
        for frame in page.frames:
            try:
                await frame.evaluate(RECORDER_SCRIPT)
            except Exception:
                self.warn("A frame could not be instrumented; review its actions before replay.")
        page.on("framenavigated", self._frame_navigated)
        page.context.on("page", self._new_page)

    async def _frame_navigated(self, frame):
        if not self.active:
            return
        self.navigated(frame)
        try:
            await frame.evaluate(RECORDER_SCRIPT)
        except Exception:
            if self.active:
                self.warn("A frame could not be instrumented; review its actions before replay.")

    def _new_page(self, page):
        if self.active:
            self.warn("A new tab was opened. Its actions are not recorded; review the draft.")

    async def stop(self):
        if self.page is not None and not self.page.is_closed():
            try:
                results = await asyncio.wait_for(asyncio.gather(*[
                    frame.evaluate("window.__camouflowStopRecording?.()") for frame in self.page.frames
                ], return_exceptions=True), timeout=3)
                if any(isinstance(result, Exception) or result for result in results):
                    self.warn("Some browser events could not be delivered. Review this draft before replay.")
            except Exception:
                self.warn("Could not flush the last browser events. Review the final steps.")
        self.active = False
        if self.page is not None:
            self.page.remove_listener("framenavigated", self._frame_navigated)
            self.page.context.remove_listener("page", self._new_page)
