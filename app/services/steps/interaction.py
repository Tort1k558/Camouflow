from typing import Dict

from .base import StepResult


class InteractionSteps:
    async def _action_click(self, step: Dict) -> StepResult:
        element = await self._locate_element(step, wait=True)
        if element is None:
            return StepResult.stop("Element not found for click")
        options = {}
        if step.get("button"):
            options["button"] = step.get("button")
        if step.get("click_delay_ms") is not None:
            options["delay"] = step.get("click_delay_ms")
        await element.click(**options)
        return StepResult.next()

    async def _action_type(self, step: Dict) -> StepResult:
        element = await self._locate_element(step, wait=True)
        if element is None:
            return StepResult.stop("Element not found for typing")
        text = self._apply_template(step.get("value") or step.get("text") or "")
        clear = step.get("clear", True)
        try:
            await element.click()
        except Exception:
            pass
        await self._human_type(element, text, clear=bool(clear))
        return StepResult.next()
