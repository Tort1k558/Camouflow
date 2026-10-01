"""Minimal OpenAI-compatible chat client for the AI agent.

One transport, no SDK: works with GLM, OpenAI, OpenRouter, Groq, DeepSeek and
a local Ollama (its /v1 endpoint) — anything speaking /chat/completions.
The model is asked to answer with a single JSON object (see actions.py);
we parse strictly and retry once with the validation error as feedback.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

import httpx

from app.services.ai_agent.actions import ActionError, validate_action

DEFAULT_TIMEOUT_S = 90.0
JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class LLMError(RuntimeError):
    """The provider could not be reached or kept returning unusable output."""


@dataclass
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    timeout_s: float = DEFAULT_TIMEOUT_S

    def sanitized(self) -> str:
        return f"model={self.model} base={self.base_url}"


Transport = Callable[[str, str, Dict[str, str], Dict[str, Any]], Awaitable[Tuple[int, Any]]]


class LLMClient:
    def __init__(self, config: LLMConfig, transport: Optional[Transport] = None) -> None:
        self.requests = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.config = config
        self._transport = transport or self._http_transport

    async def _http_transport(self, method: str, url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> Tuple[int, Any]:
        async with httpx.AsyncClient(timeout=self.config.timeout_s) as client:
            response = await client.request(method, url, headers=headers, json=payload)
            try:
                body = response.json()
            except ValueError as exc:
                raise LLMError(f"provider returned non-JSON HTTP {response.status_code}") from exc
            return response.status_code, body

    async def next_action(self, messages: List[Dict[str, Any]], element_count: int = 250) -> Tuple[str, Dict[str, Any]]:
        """Ask the model for one action. Returns (thought, validated action).

        Retries once on malformed/invalid JSON before giving up.
        """
        work = list(messages)
        last_error = ""
        for _attempt in range(2):
            status, body = await self._call(work)
            content = self._content(status, body)
            thought, action, error = self._parse(content, element_count)
            if action is not None:
                return thought, action
            last_error = error
            # Feed the failure back so the model can correct itself once.
            work = work + [
                {"role": "assistant", "content": content[:2000]},
                {"role": "user", "content": f"Invalid reply: {last_error}. Your reply was rejected; no action was executed and no data was saved. Correct the rejected action, do not advance as if it succeeded. Answer again with ONE JSON object: {{\"thought\": \"...\", \"action\": {{...}}}}."},
            ]
        raise LLMError(f"LLM kept returning invalid actions ({last_error})")

    async def _call(self, messages: List[Dict[str, Any]]) -> Tuple[int, Any]:
        base = self.config.base_url.strip().rstrip("/")
        if not base or not self.config.model.strip():
            raise LLMError("AI provider is not configured (base URL / model)")
        url = f"{base}/chat/completions"
        headers = {"Authorization": f"Bearer {self.config.api_key}"} if self.config.api_key else {}
        payload = {"model": self.config.model.strip(), "messages": messages, "temperature": 0}
        try:
            self.requests += 1
            status, body = await self._transport("POST", url, headers, payload)
            usage = body.get("usage") if isinstance(body, dict) else None
            usage = usage if isinstance(usage, dict) else {}
            self.prompt_tokens += self._token_count(usage.get("prompt_tokens"))
            self.completion_tokens += self._token_count(usage.get("completion_tokens"))
            return status, body
        except LLMError:
            raise
        except (httpx.HTTPError, asyncio.TimeoutError, OSError) as exc:
            raise LLMError(f"provider request failed: {exc}") from exc

    @staticmethod
    def _token_count(value):
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0

    def _content(self, status: int, body: Any) -> str:
        if status != 200:
            detail = json.dumps(body)[:500] if body else ""
            raise LLMError(f"provider returned HTTP {status} {detail}")
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected provider response shape: {json.dumps(body)[:300]}") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMError("provider returned empty content")
        return content

    def _parse(self, content: str, element_count: int) -> Tuple[str, Optional[Dict[str, Any]], str]:
        """Returns (thought, action dict or None, error text)."""
        text = content.strip()
        fence = JSON_FENCE_RE.search(text)
        if fence:
            text = fence.group(1).strip()
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return "", None, "no JSON object found"
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            return "", None, f"broken JSON: {exc}"
        if not isinstance(data, dict) or not isinstance(data.get("action"), dict):
            return "", None, 'missing "action" object'
        thought = str(data.get("thought") or "")[:500]
        try:
            return thought, validate_action(data["action"], element_count), ""
        except ActionError as exc:
            return thought, None, str(exc)
