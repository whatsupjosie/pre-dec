"""Provider dispatch for PubPartner live-loop turns.

PubPartner owns one small dispatch contract while reusing PubCast's tested LLM
adapters. Missing keys, optional services, or local runtimes are reported
honestly and never crash the friend loop.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .provider_capabilities import (
    canonical_provider,
    provider_capability,
    provider_catalog,
    supported_provider_ids,
)


@dataclass
class ProviderResult:
    ok: bool
    provider: str
    model: str = "unknown"
    available: bool = True
    raw_response: str = ""
    error: str = ""
    usage: Dict[str, Any] = field(default_factory=dict)
    latency_ms: int = 0
    warnings: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "provider": self.provider,
            "model": self.model,
            "available": self.available,
            "raw_response": self.raw_response,
            "error": self.error,
            "usage": self.usage,
            "latency_ms": self.latency_ms,
            "warnings": self.warnings,
        }


class PubPartnerProviderDispatcher:
    """Dispatch FCP1 prompts through built-in and PubCast universal adapters."""

    def __init__(self) -> None:
        self.byok_manager: Any = None

    def set_byok_manager(self, manager: Any) -> None:
        self.byok_manager = manager

    def configured_providers(self) -> List[str]:
        return supported_provider_ids()

    def catalog(self) -> List[Dict[str, Any]]:
        return provider_catalog()

    async def status(
        self,
        provider: str = "all",
        config: Optional[Dict[str, Any]] = None,
        *,
        user_id: str = "anon",
    ) -> Dict[str, Any]:
        if isinstance(config, str):
            config = {"provider": config}
        config = dict(config or {})
        provider = canonical_provider(provider or config.get("provider") or "all")
        if provider == "all":
            return {
                "ok": True,
                "providers": {
                    name: await self.status(name, {**config, "provider": name}, user_id=user_id)
                    for name in self.configured_providers()
                },
            }
        if provider in {"mock", "echo", "offline"}:
            return {"ok": True, "provider": provider, "available": True, "reason": "built_in"}
        if provider == "ollama":
            try:
                from .ollama_provider import check_ollama_health
                health = await check_ollama_health(
                    str(config.get("host") or ""),
                    str(config.get("model") or ""),
                )
                return {"ok": True, "provider": provider, **health}
            except Exception as exc:
                return {
                    "ok": True,
                    "provider": provider,
                    "available": False,
                    "alive": False,
                    "models": [],
                    "error": f"{type(exc).__name__}: {exc}",
                }
        if provider == "openai_compatible":
            base_url = str(config.get("base_url") or "").strip()
            require_key = bool(config.get("require_api_key", True))
            _, api_key, _, credential_source = self._resolve_credentials(provider, config, user_id=user_id)
            available = bool(base_url) and (bool(api_key) or not require_key)
            reason = "configured" if available else ("missing_base_url" if not base_url else "missing_api_key")
            return {
                "ok": True,
                "provider": provider,
                "available": available,
                "reason": reason,
                "credential_source": credential_source,
            }

        capability = provider_capability(provider)
        if capability is None:
            return {"ok": False, "provider": provider, "available": False, "reason": "unknown_provider"}
        resolved_provider, api_key, model, credential_source = self._resolve_credentials(
            provider, config, user_id=user_id
        )
        env_name = capability.credential_env
        available = bool(api_key)
        return {
            "ok": True,
            "provider": resolved_provider,
            "available": available,
            "reason": "credential_available" if available else f"missing_credential:{env_name or provider}",
            "credential_source": credential_source,
            "model": model or str(config.get("model") or ""),
        }

    async def dispatch(
        self,
        turn: Dict[str, Any],
        provider_config: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        if isinstance(provider_config, str):
            provider_config = {"provider": provider_config}
        provider_config = dict(provider_config or {})
        fcp1 = turn.get("fcp1") or {}
        fcp1_provider = (fcp1.get("norm") or {}).get("p")
        requested = provider_config.get("provider") or provider_config.get("name") or fcp1_provider or "mock"
        provider = canonical_provider(str(requested))
        model = str(
            provider_config.get("model")
            or (fcp1.get("norm") or {}).get("model")
            or "unknown"
        )
        user_id = str((fcp1.get("u") or {}).get("id") or "anon")
        started = time.time()
        try:
            if provider == "mock":
                result = self._mock(turn, model=model)
            elif provider == "echo":
                result = self._echo(turn, model=model)
            elif provider == "offline":
                result = self._offline(turn, model=model)
            elif provider == "ollama":
                result = await self._ollama(turn, model=model, config=provider_config)
            elif provider == "openai_compatible":
                result = await self._openai_compatible(
                    turn, model=model, config=provider_config, user_id=user_id
                )
            elif provider in {"openai", "anthropic", "gemini", "mistral", "groq", "opencode_zen"}:
                result = await self._universal(
                    turn, provider=provider, model=model, config=provider_config, user_id=user_id
                )
            else:
                result = ProviderResult(
                    ok=False,
                    provider=provider,
                    model=model,
                    available=False,
                    error="unknown provider",
                )
        except Exception as exc:
            result = ProviderResult(
                ok=False,
                provider=provider,
                model=model,
                available=False,
                error=f"provider dispatch failed: {type(exc).__name__}: {exc}",
            )
        result.latency_ms = int((time.time() - started) * 1000)
        return result

    def _resolve_credentials(
        self,
        provider: str,
        config: Dict[str, Any],
        *,
        user_id: str,
    ) -> Tuple[str, str, str, str]:
        """Resolve provider/model/key without serializing the secret.

        Priority: encrypted user-owned BYOK record, then named environment key.
        Inline keys are ignored unless an internal caller explicitly sets
        allow_inline_key=true; ordinary route payloads should use BYOK records.
        """
        provider = canonical_provider(provider)
        model = str(config.get("model") or "")
        credential_id = str(config.get("credential_model_id") or "").strip()
        if credential_id and self.byok_manager is not None:
            try:
                resolved = self.byok_manager.resolve_model_credentials(
                    user_id, credential_id, expected_provider=provider
                )
            except Exception:
                resolved = None
            if resolved:
                stored, secrets = resolved
                stored_provider = canonical_provider(str(getattr(stored, "provider", provider)))
                stored_model = str(getattr(stored, "model_name", "") or model)
                return stored_provider, str(secrets.get("api_key") or ""), stored_model, "encrypted_byok"

        if bool(config.get("allow_inline_key")):
            inline = str(config.get("api_key") or "").strip()
            if inline:
                return provider, inline, model, "internal_inline"

        capability = provider_capability(provider)
        env_name = str(config.get("api_key_env") or (capability.credential_env if capability else ""))
        env_key = os.getenv(env_name, "").strip() if env_name else ""
        return provider, env_key, model, f"env:{env_name}" if env_key else "none"

    def _source_label(self, turn: Dict[str, Any]) -> str:
        source = turn.get("source") or {}
        return str(source.get("id") or "source")

    def _task_goal(self, turn: Dict[str, Any]) -> str:
        task = (turn.get("fcp1") or {}).get("task") or {}
        return str(task.get("goal") or task.get("mode") or "answer_as_friend")

    def _mock(self, turn: Dict[str, Any], *, model: str) -> ProviderResult:
        source_id = self._source_label(turn)
        goal = self._task_goal(turn)
        prompt_policy = turn.get("prompt_policy") or {}
        ref_note = (
            "I will use the preserved source reference before quoting exact text."
            if prompt_policy.get("requires_restore_before_quote")
            else "I can work from the included turn text."
        )
        raw = (
            "Sure, here's the useful answer.\n"
            f"Source preserved as {source_id}. {ref_note}\n"
            f"Goal: {goal}.\n"
            "Next: keep the friend voice pass conservative and do not rewrite exact artifacts."
        )
        return ProviderResult(
            ok=True,
            provider="mock",
            model=model or "mock-v1",
            raw_response=raw,
            usage={"simulated": True},
        )

    def _echo(self, turn: Dict[str, Any], *, model: str) -> ProviderResult:
        raw = str(turn.get("llm_prompt_text") or "")[:4000]
        return ProviderResult(
            ok=True,
            provider="echo",
            model=model or "echo-v1",
            raw_response=raw,
            usage={"echo_chars": len(raw)},
        )

    def _offline(self, turn: Dict[str, Any], *, model: str) -> ProviderResult:
        fcp1 = turn.get("fcp1") or {}
        friend = fcp1.get("f") or {}
        name = friend.get("name") or friend.get("id") or "your friend"
        source_id = self._source_label(turn)
        prompt_policy = turn.get("prompt_policy") or {}
        if prompt_policy.get("include_source_text"):
            msg = ((fcp1.get("msg") or {}).get("text") or "").strip()
            preview = msg[:180] + ("…" if len(msg) > 180 else "")
            raw = f"{name}: I have the message. I preserved the original as {source_id}. {preview}"
        else:
            raw = (
                f"{name}: I preserved the original as {source_id}. I only have a reference in "
                "the token-light prompt, so I will not quote it unless the source is restored."
            )
        return ProviderResult(
            ok=True,
            provider="offline",
            model=model or "offline-rule-v1",
            raw_response=raw,
            usage={"local_rule_based": True},
        )

    async def _ollama(self, turn: Dict[str, Any], *, model: str, config: Dict[str, Any]) -> ProviderResult:
        status = await self.status("ollama", config)
        if not status.get("alive"):
            return ProviderResult(
                ok=False,
                provider="ollama",
                model=model or str(config.get("model") or "unknown"),
                available=False,
                error=status.get("error") or "ollama unavailable",
            )
        warnings: List[str] = []
        if status.get("selected_model") and status.get("models") and not status.get("model_available"):
            warnings.append(f"selected model not listed locally: {status.get('selected_model')}")
        from .ollama_provider import call_ollama
        response = await call_ollama(
            str(turn.get("llm_prompt_text") or ""),
            model=model if model != "unknown" else str(config.get("model") or ""),
            host=str(config.get("host") or ""),
            temperature=float(config.get("temperature", 0.7)),
            max_tokens=int(config.get("max_tokens", 512)),
            timeout=float(config.get("timeout", 60.0)),
        )
        if not response:
            return ProviderResult(
                ok=False,
                provider="ollama",
                model=model or "unknown",
                available=False,
                error="ollama returned empty response",
            )
        return ProviderResult(
            ok=True,
            provider="ollama",
            model=model or "unknown",
            raw_response=response,
            warnings=warnings,
        )

    async def _universal(
        self,
        turn: Dict[str, Any],
        *,
        provider: str,
        model: str,
        config: Dict[str, Any],
        user_id: str,
    ) -> ProviderResult:
        from .llm_framework import get_adapter_for_provider

        resolved_provider, api_key, stored_model, credential_source = self._resolve_credentials(
            provider, config, user_id=user_id
        )
        if not api_key:
            capability = provider_capability(resolved_provider)
            missing = capability.credential_env if capability else resolved_provider
            return ProviderResult(
                ok=False,
                provider=resolved_provider,
                model=stored_model or model or "unknown",
                available=False,
                error=f"missing env/key {missing}",
                usage={"credential_source": credential_source},
            )
        adapter = get_adapter_for_provider(resolved_provider, api_key=api_key)
        if not adapter.is_available():
            return ProviderResult(
                ok=False,
                provider=resolved_provider,
                model=stored_model or model or "unknown",
                available=False,
                error="provider adapter unavailable",
                usage={"credential_source": credential_source},
            )
        target_model = stored_model or ("" if model == "unknown" else model) or str(config.get("default_model") or "")
        prompt = str(turn.get("llm_prompt_text") or "")
        system = "You are an interchangeable reasoning engine behind PubPartner. Follow the FCP1 packet. Do not pretend to be Alex. Preserve source references."
        response = await adapter.complete(
            prompt,
            system=system,
            history=None,
            model=target_model,
            temperature=float(config.get("temperature", 0.7)),
        )
        if not response.strip():
            return ProviderResult(
                ok=False,
                provider=resolved_provider,
                model=target_model or "provider-default",
                available=False,
                error="provider returned no usable text",
                usage={"credential_source": credential_source},
            )
        return ProviderResult(
            ok=True,
            provider=resolved_provider,
            model=target_model or "provider-default",
            raw_response=response,
            usage={"credential_source": credential_source, "adapter": type(adapter).__name__},
        )

    async def _openai_compatible(
        self,
        turn: Dict[str, Any],
        *,
        model: str,
        config: Dict[str, Any],
        user_id: str,
    ) -> ProviderResult:
        from .openai_compatible_provider import OpenAICompatibleBotAdapter

        _, api_key, stored_model, credential_source = self._resolve_credentials(
            "openai_compatible", config, user_id=user_id
        )
        base_url = str(config.get("base_url") or "").strip()
        require_key = bool(config.get("require_api_key", True))
        target_model = stored_model or ("" if model == "unknown" else model) or str(config.get("default_model") or "")
        if not base_url:
            return ProviderResult(
                ok=False,
                provider="openai_compatible",
                model=target_model or "unknown",
                available=False,
                error="missing trusted base_url",
            )
        try:
            adapter = OpenAICompatibleBotAdapter(
                api_key=api_key,
                base_url=base_url,
                default_model=target_model,
                require_api_key=require_key,
                extra_headers=config.get("extra_headers") if isinstance(config.get("extra_headers"), dict) else None,
                timeout=float(config.get("timeout", 60.0)),
            )
        except ValueError as exc:
            return ProviderResult(
                ok=False,
                provider="openai_compatible",
                model=target_model or "unknown",
                available=False,
                error=str(exc),
            )
        if not adapter.is_available():
            return ProviderResult(
                ok=False,
                provider="openai_compatible",
                model=target_model or "unknown",
                available=False,
                error="OpenAI-compatible endpoint is missing a required credential or model",
                usage={"credential_source": credential_source},
            )
        response = await adapter.complete(
            str(turn.get("llm_prompt_text") or ""),
            system="You are an interchangeable reasoning engine behind PubPartner. Follow FCP1. Do not pretend to be Alex.",
            model=target_model,
            temperature=float(config.get("temperature", 0.7)),
        )
        if not response.strip():
            return ProviderResult(
                ok=False,
                provider="openai_compatible",
                model=target_model or "unknown",
                available=False,
                error="endpoint returned no usable text",
                usage={"credential_source": credential_source},
            )
        return ProviderResult(
            ok=True,
            provider="openai_compatible",
            model=target_model or "unknown",
            raw_response=response,
            usage={
                "credential_source": credential_source,
                "adapter": type(adapter).__name__,
                "base_url_configured": True,
            },
        )
