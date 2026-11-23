"""Configurable OpenAI-compatible transport for PubPartner.

This is used for gateways and local servers that expose chat/completions. The
base URL is never taken from model output; it must be supplied by trusted local
configuration or a user-owned provider record.
"""
from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from .bot_llm_adapter import BotLLMAdapter, _TIMEOUT


class OpenAICompatibleBotAdapter(BotLLMAdapter):
    provider_name = "openai_compatible"

    def __init__(
        self,
        *,
        api_key: str = "",
        base_url: str,
        default_model: str = "",
        require_api_key: bool = True,
        extra_headers: Optional[Dict[str, str]] = None,
        timeout: float | None = None,
    ) -> None:
        normalized = str(base_url or "").strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("base_url must be an explicit http:// or https:// URL")
        self.api_key = str(api_key or "")
        self.base_url = normalized
        self.default_model = str(default_model or "")
        self.require_api_key = bool(require_api_key)
        self.extra_headers = {str(k): str(v) for k, v in dict(extra_headers or {}).items()}
        self.timeout = float(timeout or _TIMEOUT)

    def is_available(self) -> bool:
        return bool(self.base_url) and (bool(self.api_key) or not self.require_api_key)

    async def stream(
        self,
        prompt: str,
        *,
        system: str = "",
        history: Optional[List[Dict[str, Any]]] = None,
        model: str = "",
        temperature: float = 0.8,
    ) -> AsyncGenerator[str, None]:
        if not self.is_available():
            return
        resolved_model = str(model or self.default_model or "").strip()
        if not resolved_model:
            return
        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        for entry in history or []:
            role = str(entry.get("role") or "").lower()
            if role not in {"system", "user", "assistant"}:
                uid = str(entry.get("user_id") or entry.get("sender_id") or "")
                role = "assistant" if uid.startswith(("bot-", "agent:")) else "user"
            text = str(entry.get("content") or entry.get("text") or "").strip()
            if text:
                messages.append({"role": role, "content": text})
        messages.append({"role": "user", "content": str(prompt or "")})

        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers.setdefault("Authorization", f"Bearer {self.api_key}")
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json={
                        "model": resolved_model,
                        "messages": messages,
                        "temperature": max(0.0, min(float(temperature), 2.0)),
                        "max_tokens": 1024,
                        "stream": True,
                    },
                ) as resp:
                    if resp.status_code != 200:
                        await resp.aread()
                        return
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line[6:].strip()
                        if not data or data == "[DONE]":
                            continue
                        try:
                            event = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = event.get("choices") or []
                        if not choices:
                            continue
                        choice = choices[0] or {}
                        delta = choice.get("delta") or {}
                        text = delta.get("content")
                        if text is None:
                            text = (choice.get("message") or {}).get("content")
                        if text:
                            yield str(text)
        except Exception:
            return


__all__ = ["OpenAICompatibleBotAdapter"]
