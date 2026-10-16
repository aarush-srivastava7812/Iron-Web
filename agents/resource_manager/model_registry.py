"""Shared NVIDIA NIM chat client.

One lazy, process-wide client is shared by every logical agent — several
agents do not mean several loaded models. Uses the OpenAI-compatible
``/v1/chat/completions`` endpoint with ``NVIDIA_API_KEY`` from agents/.env.
When no key is configured, :meth:`available` is False and callers must use
their deterministic fallbacks.
"""
from __future__ import annotations

import json
import logging
import threading

import httpx

from agents.config import settings
from .scheduler import inference_semaphore

logger = logging.getLogger(__name__)


class NimClient:
    """Thread-safe, lazily-initialized NIM chat client with a bounded timeout."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._client: httpx.Client | None = None

    @property
    def available(self) -> bool:
        return settings.has_llm()

    def _get_client(self) -> httpx.Client:
        with self._lock:
            if self._client is None:
                self._client = httpx.Client(
                    base_url=settings.nim_base_url,
                    headers={
                        "Authorization": f"Bearer {settings.nvidia_api_key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    timeout=settings.nim_timeout_s,
                )
            return self._client

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 900,
        json_mode: bool = False,
    ) -> str | None:
        """Return the assistant message content, or None on any failure.

        Inference concurrency is bounded by the shared scheduler semaphore;
        a slow or failed NIM call degrades to the caller's fallback path.
        Reasoning models (e.g. gpt-oss) spend budget on ``reasoning`` before
        ``content``, so a truncated reply is retried once with more tokens.
        """
        if not self.available:
            return None
        payload: dict = {
            "model": settings.nim_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            with inference_semaphore():
                response = self._get_client().post("/chat/completions", json=payload)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"].get("content")
                if content:
                    return content
                # Reasoning consumed the budget: retry once with a larger cap.
                payload["max_tokens"] = min(max_tokens * 3, 4000)
                response = self._get_client().post("/chat/completions", json=payload)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"].get("content") or None
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
            logger.warning("NIM chat failed (%s); caller should use its fallback.", error)
            return None

    def chat_json(self, messages: list[dict[str, str]], **kwargs) -> dict | None:
        """Chat expecting a JSON object back; returns None unless it parses."""
        text = self.chat(messages, json_mode=True, **kwargs)
        if not text:
            return None
        try:
            return json.loads(text)
        except ValueError:
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except ValueError:
                    return None
            return None

    def close(self) -> None:
        with self._lock:
            if self._client is not None:
                self._client.close()
                self._client = None


_nim_client: NimClient | None = None


def get_nim_client() -> NimClient:
    global _nim_client
    if _nim_client is None:
        _nim_client = NimClient()
    return _nim_client
