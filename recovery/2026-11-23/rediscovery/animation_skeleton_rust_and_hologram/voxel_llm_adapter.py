"""
modules/voxel_llm_adapter.py
────────────────────────────
Unified LLM adapter for voxel text-to-block generation.

LOCAL keyword engine  →  always available, zero latency, no network
Anthropic (Claude)    →  opt-in, requires ANTHROPIC_API_KEY
OpenAI (GPT)          →  opt-in, requires OPENAI_API_KEY
Gemini (Google)       →  opt-in, requires GEMINI_API_KEY or GOOGLE_API_KEY

Design rules:
  • Local is ALWAYS the default. Cloud is NEVER called unless use_cloud=True.
  • Every cloud adapter falls back to local on ANY failure — no exceptions bubble up.
  • Adding a new provider = subclass VoxelLLMAdapter, register in PROVIDER_REGISTRY.
  • No provider-specific logic leaks outside its own class.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Shared system prompt ──────────────────────────────────────────────────────

VOXEL_SYSTEM_PROMPT = """\
You are a 3D voxel prop generator for a live broadcast set-building tool called PubWorld.

Given a plain-English description, output a JSON object with exactly two keys:
  "label": short snake_case name for the prop  (e.g. "jay_silent_bob_stash")
  "blocks": array of block objects, each with integer x, y, z and optional "color" (CSS hex)

Rules:
- Keep block counts under 80. Favour readable silhouettes over solid fills.
- Origin is (0,0,0). Y is UP. Build compactly near the origin.
- Use color to suggest material:
    wood      "#c0a060"
    metal     "#8898aa"
    stone     "#888888"
    fabric    "#9b6b9b"
    glass     "#aaddff"
    neon      "#ff44cc"
    plastic   "#dd4444"
- No markdown, no explanation, no extra keys. Output the raw JSON object ONLY.
- If the request is impossible, output: {"label":"block","blocks":[{"x":0,"y":0,"z":0}]}
"""

_MAX_BLOCKS = 80
_TIMEOUT = 20.0


# ── Block model (minimal, no pydantic dependency here) ───────────────────────

def _validate_blocks(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate and cap raw block dicts. Returns clean list or empty."""
    out = []
    for b in raw[:_MAX_BLOCKS]:
        try:
            clean = {
                "x": int(b.get("x", 0)),
                "y": int(b.get("y", 0)),
                "z": int(b.get("z", 0)),
            }
            if b.get("color"):
                clean["color"] = str(b["color"])
            out.append(clean)
        except Exception:
            continue
    return out


def _parse_llm_response(text: str) -> Optional[Tuple[str, List[Dict[str, Any]]]]:
    """Parse LLM JSON response. Returns (label, blocks) or None."""
    text = text.strip()
    # Strip accidental markdown fences
    if text.startswith("```"):
        lines = [l for l in text.splitlines() if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        parsed = json.loads(text)
        label = str(parsed.get("label") or "prop").replace(" ", "_")[:64]
        raw_blocks = parsed.get("blocks") or []
        if not isinstance(raw_blocks, list):
            return None
        blocks = _validate_blocks(raw_blocks)
        if not blocks:
            return None
        return label, blocks
    except Exception:
        return None


# ── Base adapter ──────────────────────────────────────────────────────────────

class VoxelLLMAdapter(ABC):
    """Base class for all voxel generation adapters."""

    provider_name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this adapter can actually make calls right now."""
        ...

    @abstractmethod
    async def generate(self, prompt: str) -> Optional[Tuple[str, List[Dict[str, Any]]]]:
        """
        Generate voxel blocks from a text prompt.
        Returns (label, blocks) or None on failure.
        Never raises — all errors return None.
        """
        ...


# ── Anthropic adapter ─────────────────────────────────────────────────────────

class AnthropicVoxelAdapter(VoxelLLMAdapter):
    provider_name = "anthropic"

    # Use Haiku — fastest and cheapest for structured JSON generation
    MODEL = "claude-haiku-4-5-20251001"

    def is_available(self) -> bool:
        return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())

    async def generate(self, prompt: str) -> Optional[Tuple[str, List[Dict[str, Any]]]]:
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            return None
        try:
            import httpx
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.MODEL,
                        "max_tokens": 1024,
                        "system": VOXEL_SYSTEM_PROMPT,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
            if resp.status_code != 200:
                logger.warning("Anthropic voxel gen HTTP %s", resp.status_code)
                return None
            data = resp.json()
            text = "".join(
                b.get("text", "") for b in data.get("content", [])
                if b.get("type") == "text"
            )
            return _parse_llm_response(text)
        except Exception as exc:
            logger.warning("AnthropicVoxelAdapter error: %s", exc)
            return None


# ── OpenAI adapter ────────────────────────────────────────────────────────────

class OpenAIVoxelAdapter(VoxelLLMAdapter):
    provider_name = "openai"

    MODEL = "gpt-4o-mini"  # fast + cheap for JSON generation

    def is_available(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY", "").strip())

    async def generate(self, prompt: str) -> Optional[Tuple[str, List[Dict[str, Any]]]]:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            return None
        try:
            import httpx
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.MODEL,
                        "max_tokens": 1024,
                        "temperature": 0.3,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": VOXEL_SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
            if resp.status_code != 200:
                logger.warning("OpenAI voxel gen HTTP %s", resp.status_code)
                return None
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            return _parse_llm_response(text)
        except Exception as exc:
            logger.warning("OpenAIVoxelAdapter error: %s", exc)
            return None


# ── Gemini adapter ────────────────────────────────────────────────────────────

class GeminiVoxelAdapter(VoxelLLMAdapter):
    provider_name = "gemini"

    MODEL = "gemini-1.5-flash"  # fast + cheap

    def is_available(self) -> bool:
        return bool(
            os.getenv("GEMINI_API_KEY", "").strip() or
            os.getenv("GOOGLE_API_KEY", "").strip()
        )

    async def generate(self, prompt: str) -> Optional[Tuple[str, List[Dict[str, Any]]]]:
        api_key = (
            os.getenv("GEMINI_API_KEY", "").strip() or
            os.getenv("GOOGLE_API_KEY", "").strip()
        )
        if not api_key:
            return None
        try:
            import httpx
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.MODEL}:generateContent"
            )
            full_prompt = VOXEL_SYSTEM_PROMPT + "\n\nUser request: " + prompt
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    url,
                    params={"key": api_key},
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{"role": "user", "parts": [{"text": full_prompt}]}],
                        "generationConfig": {
                            "responseMimeType": "application/json",
                            "maxOutputTokens": 1024,
                            "temperature": 0.3,
                        },
                    },
                )
            if resp.status_code != 200:
                logger.warning("Gemini voxel gen HTTP %s", resp.status_code)
                return None
            data = resp.json()
            candidates = data.get("candidates") or []
            if not candidates:
                return None
            parts = candidates[0].get("content", {}).get("parts") or []
            text = "".join(p.get("text", "") for p in parts)
            return _parse_llm_response(text)
        except Exception as exc:
            logger.warning("GeminiVoxelAdapter error: %s", exc)
            return None


# ── Provider registry ─────────────────────────────────────────────────────────
# Order matters — first available wins when provider="auto"

PROVIDER_REGISTRY: Dict[str, VoxelLLMAdapter] = {
    "anthropic": AnthropicVoxelAdapter(),
    "openai":    OpenAIVoxelAdapter(),
    "gemini":    GeminiVoxelAdapter(),
}


# ── Public API ────────────────────────────────────────────────────────────────

def get_available_providers() -> Dict[str, bool]:
    """Instant check — no network calls. Returns {provider_name: is_available}."""
    return {name: adapter.is_available() for name, adapter in PROVIDER_REGISTRY.items()}


async def generate_with_cloud(
    prompt: str,
    provider: str = "auto",
) -> Tuple[Optional[Tuple[str, List[Dict[str, Any]]]], str]:
    """
    Attempt cloud generation. Returns (result, provider_used).
    result is None if all cloud providers fail — caller should fall back to local.

    provider="auto"  → try available providers in registry order
    provider="anthropic"|"openai"|"gemini"  → use that specific one only
    """
    if provider == "auto":
        for name, adapter in PROVIDER_REGISTRY.items():
            if adapter.is_available():
                result = await adapter.generate(prompt)
                if result is not None:
                    return result, name
        return None, "none"
    else:
        adapter = PROVIDER_REGISTRY.get(provider)
        if adapter is None:
            logger.warning("Unknown provider '%s', falling back", provider)
            return None, "none"
        if not adapter.is_available():
            return None, "none"
        result = await adapter.generate(prompt)
        return result, provider if result else "none"
