import json
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

from app.storage.db import OUTPUTS_DIR, db_update_account

from .base import StepResult


class DataSteps:
    async def _action_log(self, step: Dict) -> StepResult:
        message = self._apply_template(step.get("value") or step.get("message") or step.get("text") or "")
        self.logger.info("SCENARIO LOG: %s", message)
        return StepResult.next()

    async def _action_http_request(self, step: Dict) -> StepResult:
        if not getattr(self, "context", None):
            return StepResult.stop("Browser context is not initialized for http_request")

        url = self._apply_template(step.get("value") or step.get("url") or "") or ""
        url = url.strip()
        if not url:
            return StepResult.stop("URL is required for http_request")

        options_from_json = self._parse_json_object(step.get("options_json") or step.get("options"), expected_type=dict) or {}
        merged_step = dict(options_from_json)
        merged_step.update({k: v for k, v in (step or {}).items() if v is not None})

        method = self._apply_template(merged_step.get("method") or merged_step.get("http_method") or "GET") or "GET"
        method = method.strip().upper() or "GET"

        headers = merged_step.get("headers")
        headers = self._parse_json_object(headers, expected_type=dict) or headers
        headers = self._apply_template_recursive(headers) if headers is not None else None
        if isinstance(headers, dict):
            headers = {str(k): "" if v is None else str(v) for k, v in headers.items()}
        else:
            headers = None

        params = merged_step.get("params") or merged_step.get("query") or merged_step.get("query_params")
        params = self._parse_json_object(params, expected_type=dict) or params
        params = self._apply_template_recursive(params) if params is not None else None
        if isinstance(params, dict):
            params = {str(k): "" if v is None else str(v) for k, v in params.items()}
        elif isinstance(params, str):
            params = self._apply_template(params)
        else:
            params = None

        data = merged_step.get("data")
        if data is None:
            data = merged_step.get("json")
        if data is None:
            data = merged_step.get("body")
        data = self._apply_template_recursive(data)
        if isinstance(data, str):
            data = self._apply_template(data)
            data = (data or "")

        form = merged_step.get("form")
        form = self._parse_json_object(form, expected_type=dict) or form
        form = self._apply_template_recursive(form) if form is not None else None
        if isinstance(form, dict):
            form = {str(k): "" if v is None else str(v) for k, v in form.items()}
        else:
            form = None

        multipart = merged_step.get("multipart")
        multipart = self._parse_json_object(multipart, expected_type=dict) or multipart
        multipart = self._apply_template_recursive(multipart) if multipart is not None else None
        if isinstance(multipart, dict):
            multipart = {str(k): v for k, v in multipart.items()}
        else:
            multipart = None

        timeout_ms = merged_step.get("timeout_ms")
        timeout_seconds: Optional[float] = None
        if timeout_ms is not None:
            try:
                timeout_seconds = float(timeout_ms) / 1000.0
            except Exception:
                timeout_seconds = None

        fail_on_status_code = merged_step.get("fail_on_status_code")
        ignore_https_errors = merged_step.get("ignore_https_errors")
        max_redirects = merged_step.get("max_redirects")
        max_retries = merged_step.get("max_retries")

        response = await self.context.request.fetch(
            url,
            params=params,
            method=method,
            headers=headers,
            data=data,
            form=form,
            multipart=multipart,
            timeout=timeout_seconds,
            fail_on_status_code=fail_on_status_code,
            ignore_https_errors=ignore_https_errors,
            max_redirects=max_redirects,
            max_retries=max_retries,
        )

        status = int(response.status)
        ok = 200 <= status <= 299
        response_headers = dict(response.headers or {})

        body_text = ""
        body_bytes: Optional[bytes] = None
        try:
            body_text = await response.text()
        except Exception:
            try:
                body_bytes = await response.body()
                body_text = body_bytes.decode("utf-8", errors="replace")
            except Exception:
                body_text = ""

        parsed_json: Optional[object] = None
        try:
            parsed_json = await response.json()
        except Exception:
            parsed_json = None

        save_as = self._apply_template(
            merged_step.get("save_as")
            or merged_step.get("result_prefix")
            or merged_step.get("prefix")
            or merged_step.get("var_prefix")
            or "http"
        )
        save_as = (save_as or "").strip()
        if save_as:
            self.variables[f"{save_as}_url"] = url
            self.variables[f"{save_as}_status"] = str(status)
            self.variables[f"{save_as}_ok"] = "true" if ok else "false"
            self.variables[f"{save_as}_headers"] = json.dumps(response_headers, ensure_ascii=False)
            self.variables[f"{save_as}_body"] = body_text
            if parsed_json is not None:
                try:
                    self.variables[f"{save_as}_json"] = json.dumps(parsed_json, ensure_ascii=False)
                except Exception:
                    self.variables[f"{save_as}_json"] = ""
            else:
                self.variables[f"{save_as}_json"] = ""

        response_var = self._apply_template(merged_step.get("response_var") or merged_step.get("to_var") or "")
        response_var = (response_var or "").strip()
        if response_var:
            payload = {
                "url": url,
                "status": status,
                "ok": ok,
                "headers": response_headers,
                "body": body_text,
            }
            if parsed_json is not None:
                payload["json"] = parsed_json
            self.variables[response_var] = json.dumps(payload, ensure_ascii=False)

        extract_json = merged_step.get("extract_json") or merged_step.get("json_extract")
        extract_json = self._parse_json_object(extract_json, expected_type=dict) or extract_json
        if isinstance(extract_json, dict) and parsed_json is not None:
            for var_name, path in extract_json.items():
                if not var_name:
                    continue
                resolved_path = self._apply_template(str(path)) if path is not None else ""
                value = self._json_path_get(parsed_json, str(resolved_path or ""))
                if value is None:
                    self.variables[str(var_name)] = ""
                elif isinstance(value, (dict, list)):
                    self.variables[str(var_name)] = json.dumps(value, ensure_ascii=False)
                else:
                    self.variables[str(var_name)] = str(value)

        require_success = bool(merged_step.get("require_success"))
        if require_success and not ok:
            return StepResult.stop(f"http_request failed with status {status}")

        await self._persist_profile_vars()
        self.logger.info("HTTP %s %s -> %s", method, url, status)
        return StepResult.next()

    async def _action_write_file(self, step: Dict) -> StepResult:
        filename = self._apply_template(step.get("filename") or step.get("file") or "")
        content = self._apply_template(step.get("value") or step.get("text") or step.get("message") or "")

        filename = (filename or "").strip()
        if not filename:
            return StepResult.stop("File name is required for write_file action")
        candidate = Path(filename)
        if candidate.is_absolute():
            return StepResult.stop("Absolute file paths are not allowed for write_file action")

        file_path = (OUTPUTS_DIR / candidate)

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            return StepResult.stop(f"Cannot create folder for file {file_path}: {exc}")

        payload = str(content or "")
        try:
            if file_path.exists():
                prefix = ""
                try:
                    if file_path.stat().st_size > 0:
                        with file_path.open("rb") as fh:
                            fh.seek(-1, 2)
                            last = fh.read(1)
                        if last not in (b"\n", b"\r"):
                            prefix = "\n"
                        else:
                            prefix = ""
                except Exception:
                    prefix = "\n"
                with file_path.open("a", encoding="utf-8", newline="") as fh:
                    fh.write(prefix + payload + "\n")
            else:
                with file_path.open("w", encoding="utf-8", newline="") as fh:
                    fh.write(payload + "\n")
        except Exception as exc:
            return StepResult.stop(f"Failed to write file {file_path}: {exc}")

        return StepResult.next()

    async def _action_set_var(self, step: Dict) -> StepResult:
        name = step.get("name") or step.get("variable") or step.get("var")
        value = self._apply_template(step.get("value") or step.get("text") or "")
        scope = (step.get("scope") or "profile").lower()
        if name:
            self.variables[name] = value or ""
            if scope in {"shared", "both"}:
                self.shared_manager.set(name, value or "")
                self.shared_vars = self.shared_manager.all()
                self.logger.info("Shared variable %s set to %s", name, value)
            else:
                self.logger.info("Scenario variable %s set to %s", name, value)
            await self._persist_profile_vars()
        return StepResult.next()

    async def _action_parse_var(self, step: Dict) -> StepResult:
        """
        Parse a source string (usually from a variable) using a template pattern like '{{a}};{{b}}'
        and write extracted parts to variables.
        """
        from_var = (step.get("from_var") or step.get("var") or step.get("name") or "").strip()
        if from_var:
            source = str(self.variables.get(from_var, "") or "")
        else:
            source = self._apply_template(step.get("value") or step.get("text") or "") or ""

        pattern = str(step.get("pattern") or step.get("targets_string") or "").strip()
        if not pattern:
            return StepResult.stop("Pattern is required for parse_var")

        names_from_pattern, compiled = self._compile_targets_pattern(pattern)
        if not names_from_pattern or compiled is None:
            return StepResult.stop("Pattern must contain placeholders like {{name}}")

        match = compiled.match(str(source or "").strip())
        if not match:
            return StepResult.stop("Pattern did not match source for parse_var")

        groups = match.groups()
        extracted: Dict[str, str] = {}
        for idx, name in enumerate(names_from_pattern):
            normalized = self._normalize_placeholder_name(name)
            if not normalized:
                continue
            value = groups[idx] if idx < len(groups) else ""
            clean = (value or "").strip()
            extracted[normalized] = clean
            self.variables[normalized] = clean

        update_account_raw = step.get("update_account")
        update_account = True if update_account_raw is None else bool(update_account_raw)
        if update_account and extracted:
            try:
                db_update_account(self.profile_name, extracted)
                self.account_payload.update(extracted)
            except Exception as exc:
                self.logger.warning("Failed to save account data for %s: %s", self.profile_name, exc)

        await self._persist_profile_vars()
        self.logger.info("Parsed %s -> %s", from_var or "value", ", ".join(sorted(extracted.keys())))
        return StepResult.next()

    async def _action_compare(self, step: Dict) -> StepResult:
        """
        Compare variables and/or literals and branch to tags.

        True branch: next_success_step (or true_step).
        False branch: next_error_step (or false_step).
        """
        op = str(step.get("op") or step.get("operator") or "equals").strip().lower()
        case_sensitive = bool(step.get("case_sensitive", False))
        numeric = bool(step.get("numeric", False))

        left_var = (step.get("left_var") or step.get("from_var") or step.get("var") or step.get("name") or "").strip()
        if left_var:
            left = str(self.variables.get(left_var, "") or "")
        else:
            left = self._apply_template(step.get("left") or step.get("a") or "") or ""

        right_var = (step.get("right_var") or step.get("b_var") or "").strip()
        if right_var:
            right = str(self.variables.get(right_var, "") or "")
        else:
            right = self._apply_template(step.get("right") or step.get("b") or step.get("value") or "") or ""

        def _cmp_str(a: str, b: str) -> Tuple[str, str]:
            if case_sensitive:
                return a, b
            return a.lower(), b.lower()

        result: Optional[bool] = None
        try:
            if op in {"is_empty", "empty"}:
                result = (left.strip() == "")
            elif op in {"not_empty", "has_value"}:
                result = (left.strip() != "")
            elif op in {"equals", "eq", "=="}:
                a, b = _cmp_str(left, right)
                result = (a == b)
            elif op in {"not_equals", "ne", "!="}:
                a, b = _cmp_str(left, right)
                result = (a != b)
            elif op in {"contains"}:
                a, b = _cmp_str(left, right)
                result = (b in a)
            elif op in {"not_contains"}:
                a, b = _cmp_str(left, right)
                result = (b not in a)
            elif op in {"startswith"}:
                a, b = _cmp_str(left, right)
                result = a.startswith(b)
            elif op in {"endswith"}:
                a, b = _cmp_str(left, right)
                result = a.endswith(b)
            elif op in {"regex", "re", "match"}:
                flags = 0 if case_sensitive else re.IGNORECASE
                result = re.search(str(right or ""), str(left or ""), flags) is not None
            elif op in {"gt", ">", "gte", ">=", "lt", "<", "lte", "<="}:
                a_raw = left.strip()
                b_raw = right.strip()
                a_num = float(a_raw)
                b_num = float(b_raw)
                if op in {"gt", ">"}:
                    result = a_num > b_num
                elif op in {"gte", ">="}:
                    result = a_num >= b_num
                elif op in {"lt", "<"}:
                    result = a_num < b_num
                else:
                    result = a_num <= b_num
            else:
                return StepResult.stop(f"Unknown compare operator {op}")
        except Exception as exc:
            return StepResult.stop(f"Compare failed: {exc}")

        out_var = (step.get("result_var") or step.get("to_var") or "").strip()
        if out_var:
            self.variables[out_var] = "true" if result else "false"
            await self._persist_profile_vars()

        true_target = step.get("true_step") or step.get("next_success_step")
        false_target = step.get("false_step") or step.get("next_error_step")

        if result:
            if true_target:
                return StepResult.jump(str(true_target))
            return StepResult.next()

        if false_target:
            return StepResult.jump(str(false_target))
        if true_target:
            return StepResult.stop("Compare is false but false branch is not configured")
        return StepResult.next()

    async def _action_extract(self, step: Dict) -> StepResult:
        element = await self._locate_element(step, wait=True)
        if element is None:
            return StepResult.stop("Element not found for extract_text")
        attribute = step.get("attribute")
        content = await element.get_attribute(attribute) if attribute else await element.text_content()
        if content is None:
            content = ""
        if step.get("strip", True):
            content = content.strip()
        target = step.get("to_var") or step.get("var") or step.get("name") or "last_value"
        self.variables[target] = content
        self.logger.info("Saved content to var %s: %s", target, content)
        return StepResult.next()
