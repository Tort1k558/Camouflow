import asyncio
from typing import Dict

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .base import StepResult


class NavigationSteps:
    async def _action_goto(self, step: Dict) -> StepResult:
        url = self._apply_template(step.get("value") or step.get("url") or "")
        wait_until = step.get("wait_until") or "load"
        timeout = step.get("timeout_ms")
        await self.page.goto(url, wait_until=wait_until, timeout=timeout)
        return StepResult.next()

    async def _action_wait_for_load_state(self, step: Dict) -> StepResult:
        state = step.get("state") or step.get("wait_until") or "load"
        timeout = step.get("timeout_ms")
        await self.page.wait_for_load_state(state=state, timeout=timeout)
        return StepResult.next()

    async def _action_wait_element(self, step: Dict) -> StepResult:
        frame = await self._resolve_frame(step)
        locator = self._build_locator(frame, step)
        if locator is None:
            return StepResult.stop("Selector is empty for wait_element")
        state = self._selector_state(step)
        timeout = step.get("timeout_ms")
        try:
            await locator.wait_for(state=state, timeout=timeout)
            return StepResult.next()
        except PlaywrightTimeoutError:
            selector = self._apply_template(step.get("selector") or "")
            return StepResult.stop(f"Selector {selector} not found")

    async def _action_sleep(self, step: Dict) -> StepResult:
        seconds = step.get("seconds")
        if seconds is None:
            seconds = (step.get("timeout_ms") or 0) / 1000
        try:
            seconds_float = float(seconds)
        except (TypeError, ValueError):
            seconds_float = 0.0
        await asyncio.sleep(max(0.0, seconds_float))
        return StepResult.next()

    async def _action_new_tab(self, step: Dict) -> StepResult:
        url = self._apply_template(step.get("value") or step.get("url") or "")
        page = await self.context.new_page()
        self.page = page
        if url:
            await page.goto(url, wait_until=step.get("wait_until") or "load", timeout=step.get("timeout_ms"))
        return StepResult.next()

    async def _action_switch_tab(self, step: Dict) -> StepResult:
        idx = step.get("index") if step.get("index") is not None else step.get("tab_index")
        if idx is None and step.get("from_var"):
            try:
                idx = int(self.variables.get(step.get("from_var"), 0))
            except (TypeError, ValueError):
                idx = 0
        if idx is None:
            idx = 0
        pages = self.context.pages if self.context else []
        try:
            idx_int = int(idx)
        except (TypeError, ValueError):
            idx_int = 0
        if 0 <= idx_int < len(pages):
            self.page = pages[idx_int]
            await self.page.bring_to_front()
            return StepResult.next()
        return StepResult.stop(f"Tab index {idx_int} is out of range")

    async def _action_close_tab(self, step: Dict) -> StepResult:
        pages = self.context.pages if self.context else []
        target = self.page
        idx = step.get("index") if step.get("index") is not None else step.get("tab_index")
        if idx is not None and 0 <= int(idx) < len(pages):
            target = pages[int(idx)]
        if target:
            await target.close()
        remaining = self.context.pages if self.context else []
        if remaining:
            self.page = remaining[0]
        return StepResult.next()
