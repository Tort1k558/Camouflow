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
        required = step.get("required_variable")
        if required and not self.variables.get(str(required)):
            return StepResult.stop(f"Required profile variable is missing: {required}")
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

    async def _action_select_option(self, step: Dict) -> StepResult:
        element = await self._locate_element(step, wait=True)
        if element is None:
            return StepResult.stop("Element not found for selection")
        await element.select_option(value=self._apply_template(step.get("value", "")))
        return StepResult.next()

    async def _action_set_checked(self, step: Dict) -> StepResult:
        value = str(step.get("value", "")).lower()
        if value not in {"true", "false"}:
            return StepResult.stop("Checkbox value must be true or false")
        element = await self._locate_element(step, wait=True)
        if element is None:
            return StepResult.stop("Checkbox not found")
        await element.set_checked(value == "true")
        return StepResult.next()

    async def _action_press(self, step: Dict) -> StepResult:
        key = str(step.get("value", ""))
        if not key:
            return StepResult.stop("Key is required")
        element = await self._locate_element(step, wait=True)
        if element is None:
            return StepResult.stop("Element not found for key press")
        await element.press(key)
        return StepResult.next()
