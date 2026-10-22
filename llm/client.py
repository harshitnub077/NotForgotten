"""
Provider-agnostic LLM access with graceful offline degradation.

Every AI feature in NotForgotten has a deterministic fallback, so the app is
fully usable without an API key; an LLM makes cards, grading and tutoring
richer. Provider is chosen by LLM_PROVIDER (groq | openai | anthropic) or,
if unset, by whichever API key is present.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from typing import Any, Dict, Iterator, List, Optional

from dotenv import load_dotenv

load_dotenv()

_DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-5-5",
}
_KEY_ENV = {
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}
_FAILURE_COOLDOWN_S = 60.0

Message = Dict[str, str]


class LLMUnavailable(RuntimeError):
    pass


class LLMClient:
    def __init__(self) -> None:
        self.provider = self._resolve_provider()
        self.model = os.getenv("LLM_MODEL") or _DEFAULT_MODELS.get(self.provider or "", "")
        if self.provider and os.getenv("LLM_PROVIDER", "").lower() != self.provider:
            # LLM_MODEL belongs to the configured provider, not the fallback one.
            self.model = _DEFAULT_MODELS[self.provider]
        self._client: Any = None
        self._lock = threading.Lock()
        self._failed_at: float = 0.0
        self.last_error: Optional[str] = None

    # ── Status ──────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_provider() -> Optional[str]:
        configured = os.getenv("LLM_PROVIDER", "").lower().strip()
        if configured in _KEY_ENV and os.getenv(_KEY_ENV[configured]):
            return configured
        for name, env in _KEY_ENV.items():
            if os.getenv(env):
                return name
        return None

    @property
    def available(self) -> bool:
        if self.provider is None or os.getenv("NOTFORGOTTEN_OFFLINE") == "1":
            return False
        return time.time() - self._failed_at > _FAILURE_COOLDOWN_S

    def status(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model if self.provider else None,
            "available": self.available,
            "last_error": self.last_error,
        }

    # ── SDK plumbing ────────────────────────────────────────────────────

    def _sdk(self) -> Any:
        with self._lock:
            if self._client is not None:
                return self._client
            key = os.getenv(_KEY_ENV[self.provider or ""], "")
            if self.provider == "groq":
                from groq import Groq

                self._client = Groq(api_key=key)
            elif self.provider == "openai":
                from openai import OpenAI

                self._client = OpenAI(api_key=key)
            elif self.provider == "anthropic":
                import anthropic

                self._client = anthropic.Anthropic(api_key=key)
            else:
                raise LLMUnavailable("No LLM provider configured")
            return self._client

    def _mark_failed(self, exc: Exception) -> None:
        self._failed_at = time.time()
        self.last_error = f"{type(exc).__name__}: {str(exc)[:200]}"

    # ── Public API ──────────────────────────────────────────────────────

    def complete(
        self,
        system: str,
        messages: List[Message],
        max_tokens: int = 1024,
        temperature: float = 0.3,
        retries: int = 2,
    ) -> str:
        if not self.available:
            raise LLMUnavailable(self.last_error or "LLM offline")
        delay = 2.0
        for attempt in range(retries + 1):
            try:
                return self._complete_once(system, messages, max_tokens, temperature)
            except Exception as exc:  # noqa: BLE001 — SDKs raise many types
                rate_limited = "429" in str(exc) or "rate" in str(exc).lower()
                if attempt < retries and rate_limited:
                    time.sleep(delay)
                    delay *= 2
                    continue
                self._mark_failed(exc)
                raise LLMUnavailable(self.last_error) from exc
        raise LLMUnavailable("unreachable")

    def _complete_once(
        self, system: str, messages: List[Message], max_tokens: int, temperature: float
    ) -> str:
        sdk = self._sdk()
        if self.provider == "anthropic":
            resp = sdk.messages.create(
                model=self.model,
                system=system,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        resp = sdk.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, *messages],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""

    def stream(
        self,
        system: str,
        messages: List[Message],
        max_tokens: int = 1200,
        temperature: float = 0.5,
    ) -> Iterator[str]:
        if not self.available:
            raise LLMUnavailable(self.last_error or "LLM offline")
        try:
            sdk = self._sdk()
            if self.provider == "anthropic":
                with sdk.messages.stream(
                    model=self.model,
                    system=system,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                ) as s:
                    for text in s.text_stream:
                        yield text
                return
            chunks = sdk.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, *messages],
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )
            for chunk in chunks:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as exc:  # noqa: BLE001
            self._mark_failed(exc)
            raise LLMUnavailable(self.last_error) from exc

    def complete_json(
        self,
        system: str,
        prompt: str,
        max_tokens: int = 1500,
        temperature: float = 0.2,
    ) -> Any:
        text = self.complete(
            system + "\nRespond with valid JSON only. No prose, no markdown fences.",
            [{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return parse_json(text)


def parse_json(text: str) -> Any:
    """Parse the first JSON value in *text*, tolerating fences and chatter."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for open_ch, close_ch in (("[", "]"), ("{", "}")):
        start, end = text.find(open_ch), text.rfind(close_ch)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("No JSON found in LLM output")


_client: Optional[LLMClient] = None


def get_llm() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client


def reset_llm() -> None:
    global _client
    _client = None
