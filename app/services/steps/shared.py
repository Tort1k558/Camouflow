from typing import Dict, List

from app.storage.db import db_update_account

from .base import StepResult


class SharedSteps:
    async def _action_pop_shared(self, step: Dict) -> StepResult:
        """
        Pop first item from shared variable (list or newline-separated string) and map it to variables using targets_string.
        """
        key_raw = step.get("value")
        key = (self._apply_template(key_raw) or "").strip()
        if not key:
            return StepResult.stop("Shared key (value) is required for pop_shared")

        def _split_pool(val) -> List[str]:
            if isinstance(val, list):
                return [str(v).strip() for v in val if str(v).strip()]
            if isinstance(val, str):
                raw = val.replace("\r\n", "\n")
                return [ln.strip() for ln in raw.split("\n") if ln.strip()]
            return [str(val).strip()] if val else []

        pool = self.shared_manager.get(key, "")
        items = _split_pool(pool)
        if not items:
            msg = f"No items in shared var {key}"
            return StepResult.stop(msg)

        item = items.pop(0)
        remaining = "\n".join(items)
        self.shared_manager.set(key, remaining)
        self.shared_vars = self.shared_manager.all()
        self.variables[key] = remaining
        self._persist_shared_setting(key, remaining)

        pattern = str(step.get("pattern") or step.get("targets_string") or "").strip()
        if not pattern:
            return StepResult.stop("Pattern (targets_string) is required for pop_shared")
        names_from_pattern, compiled = self._compile_targets_pattern(pattern)
        if not names_from_pattern or compiled is None:
            return StepResult.stop("Pattern must contain placeholders like {{name}}")
        account_updates: Dict[str, str] = {}
        match = compiled.match(item.strip())
        if not match:
            return StepResult.stop(f"Pattern did not match shared value for {key}")
        groups = match.groups()
        for idx, name in enumerate(names_from_pattern):
            normalized = self._normalize_placeholder_name(name)
            if not normalized:
                continue
            value = groups[idx] if idx < len(groups) else ""
            clean = value.strip()
            self.variables[normalized] = clean
            account_updates[normalized] = clean

        self.logger.info("Popped from shared %s -> %s", key, item)
        if account_updates:
            try:
                db_update_account(self.profile_name, account_updates)
                self.account_payload.update(account_updates)
            except Exception as exc:
                self.logger.warning("Failed to save account data for %s: %s", self.profile_name, exc)
        await self._persist_profile_vars()
        return StepResult.next()
