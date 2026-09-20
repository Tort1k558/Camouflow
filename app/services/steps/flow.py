from typing import Dict
import asyncio

from app.storage.db import db_get_scenario, db_get_scenario_path, db_update_stage

from .base import StepResult


class FlowSteps:
    async def _action_run_scenario(self, step: Dict) -> StepResult:
        raw_name = step.get("scenario") or step.get("scenario_name") or step.get("name") or step.get("value")
        scenario_name = self._apply_template(raw_name) if raw_name else ""
        scenario_name = (scenario_name or "").strip()
        if not scenario_name:
            return StepResult.stop("Scenario name is empty for run_scenario action")
        library = getattr(self, "_scenario_library", None)
        nested = library.get(scenario_name) if library is not None else db_get_scenario(scenario_name)
        if not nested:
            return StepResult.stop(f"Scenario {scenario_name} not found")
        display_name = nested.name or scenario_name
        scenario_lower = display_name.lower()
        if any(existing.lower() == scenario_lower for existing in self._scenario_stack):
            return StepResult.stop(f"Recursive scenario call detected for {display_name}")
        self._scenario_stack.append(display_name)
        try:
            ok, reason = await self._execute_steps(
                nested.steps or [],
                display_name,
                scenario_path=db_get_scenario_path(scenario_name),
            )
        finally:
            self._scenario_stack.pop()
        if not ok:
            return StepResult.stop(f"Nested scenario {display_name} failed: {reason or 'unknown reason'}")
        return StepResult.next()

    async def _action_set_tag(self, step: Dict) -> StepResult:
        tag = self._apply_template(step.get("value") or step.get("tag") or step.get("stage") or "")
        tag = tag.strip()
        updater = getattr(self, "_tag_updater", None)
        if updater is not None:
            await asyncio.to_thread(updater, tag)
        else:
            db_update_stage(self.profile_name, tag or None)
        self.account_payload["stage"] = tag
        self.logger.info("Tag for %s -> %s", self.profile_name, tag or "None")
        return StepResult.next()

    async def _action_end(self, step: Dict) -> StepResult:
        self.logger.info("End step triggered; closing browser for %s", self.profile_name)
        try:
            try:
                await self.stop_run_capture()
            finally:
                await self.close(force=True)
        except Exception as exc:
            self.logger.warning("Failed to close browser on end step: %s", exc)
        return StepResult.end()
