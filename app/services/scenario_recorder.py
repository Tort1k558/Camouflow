"""Single-tab browser action capture. No browser or UI ownership."""

from __future__ import annotations

import copy
import asyncio
import time
from urllib.parse import urlsplit


RECORDER_SCRIPT = r"""
(() => {
    if (window.__camouflowRecording) return;
    window.__camouflowRecording = true;
    const pending = new Set();
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
        if (window !== window.top) { send({warning: 'Iframe actions are not supported in this recording version.'}); return; }
        const target = selector(el);
        if (!target) { send({warning: 'An element has no unique stable selector. Add this step manually.'}); return; }
        const password = el.type === 'password';
        const sensitive = password || /password|one-time-code|cc-number|cc-csc/.test(el.autocomplete || '');
        send({action, selector: target, value: sensitive && action === 'type' ? '' : value, sensitive, password});
    };
    document.addEventListener('click', event => {
        if (!event.isTrusted || event.button !== 0) return;
        if (event.target.closest('label')) return;
        const el = event.target.closest('button,a,input,textarea,select,[role="button"],[role="link"]');
        if (!el) { send({warning: 'A non-standard click target was skipped. Review the recording.'}); return; }
        if (event.detail === 0 && enterForm && el.form === enterForm && performance.now() - enterAt < 1000) return;
        if (el.matches('textarea,select,input:not([type="submit"]):not([type="button"])')) return;
        emit(el, 'click');
    }, true);
    document.addEventListener('input', event => {
        if (!event.isTrusted) return;
        const el = event.target;
        if (el.matches('textarea,input:not([type="checkbox"]):not([type="radio"]):not([type="file"])')) emit(el, 'type', el.value);
        else if (el.isContentEditable) send({warning: 'Rich-text editor input is not supported. Add this step manually.'});
    }, true);
    document.addEventListener('change', event => {
        if (!event.isTrusted) return;
        const el = event.target;
        if (el.matches('select')) {
            if (el.multiple) send({warning: 'Multiple selection is not supported. Add this step manually.'});
            else emit(el, 'select_option', el.value);
        } else if (el.matches('input[type="checkbox"],input[type="radio"]')) emit(el, 'set_checked', el.checked ? 'true' : 'false');
        else if (el.matches('input[type="file"]')) send({warning: 'File uploads are not recorded.'});
    }, true);
    document.addEventListener('keydown', event => {
        if (event.isTrusted && event.key === 'Enter' && event.target.matches('input')) {
            enterForm = event.target.form;
            enterAt = performance.now();
            emit(event.target, 'press', 'Enter');
        }
    }, true);
})();
"""


class ScenarioRecorder:
    MAX_STEPS = 1000

    def __init__(self, on_change=None):
        self.steps = [{"action": "start", "tag": "Start"}]
        self.warnings = []
        self.active = False
        self.page = None
        self._last_action_at = 0.0
        self._secrets = {}
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

    def receive(self, source, payload):
        if not self.active or not isinstance(payload, dict):
            return
        if source["page"] != self.page or source["frame"] != self.page.main_frame:
            self.warn("Only the initial tab and its main frame are recorded.")
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
        if action == "type" and payload.get("sensitive"):
            variable = "password" if payload.get("password") else self._secrets.setdefault(selector, f"recorded_secret_{len(self._secrets) + 1}")
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
        if action == "type" and self.steps[-1].get("action") == "type" and self.steps[-1].get("selector") == selector:
            step["tag"] = self.steps[-1]["tag"]
            self.steps[-1] = step
            self._on_change()
        else:
            self._append(step)
        self._last_action_at = time.monotonic()

    def navigated(self, frame):
        if not self.active or frame != self.page.main_frame:
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
        await page.context.expose_binding("__camouflowRecord", self.receive)
        await page.evaluate("window.__camouflowRecord({})")
        await page.context.add_init_script(RECORDER_SCRIPT)
        await page.evaluate(RECORDER_SCRIPT)
        page.on("framenavigated", self.navigated)
        page.context.on("page", self._new_page)

    def _new_page(self, page):
        if self.active:
            self.warn("A new tab was opened. Its actions are not recorded; review the draft.")

    async def stop(self):
        if self.page is not None and not self.page.is_closed():
            try:
                failed = await asyncio.wait_for(self.page.evaluate("window.__camouflowStopRecording?.()"), timeout=3)
                if failed:
                    self.warn("Some browser events could not be delivered. Review this draft before replay.")
            except Exception:
                self.warn("Could not flush the last browser events. Review the final steps.")
        self.active = False
        if self.page is not None:
            self.page.remove_listener("framenavigated", self.navigated)
            self.page.context.remove_listener("page", self._new_page)
