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
import uuid

import httpx

from agents.config import settings
from .scheduler import inference_semaphore
from .run_metrics import observed_request

logger = logging.getLogger(__name__)


_usage_lock = threading.Lock()
_usage = {"requests": 0, "successful": 0, "input_tokens": 0, "output_tokens": 0, "usage_responses": 0}

def record_usage(data):
    with _usage_lock:
        _usage["successful"] += 1
        usage = data.get("usage") or {}
        if usage:
            _usage["usage_responses"] += 1
            _usage["input_tokens"] += usage.get("prompt_tokens") or 0
            _usage["output_tokens"] += usage.get("completion_tokens") or 0

def inference_usage():
    with _usage_lock:
        return dict(_usage, scope="website process since start", source="measured", provider="NVIDIA NIM")

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
        model: str | None = None,
        timeout_s: float | None = None,
        queue_timeout_s: float = 30,
        retry_truncated: bool = True,
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
            "model": model or settings.nim_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if "gpt-oss" in payload["model"]:
            payload["reasoning_effort"] = "low"
        if "nemotron-3" in payload["model"] or "nemotron-nano-3" in payload["model"]:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        try:
            with inference_semaphore(timeout_s=queue_timeout_s):
                with _usage_lock:
                    _usage["requests"] += 1
                request_options = {"timeout": timeout_s} if timeout_s is not None else {}
                response = observed_request(self._get_client(), "post", "/chat/completions", provider="NVIDIA NIM", json=payload, **request_options)
                response.raise_for_status()
                data = response.json()
                record_usage(data)
                content = data["choices"][0]["message"].get("content")
                if content:
                    return content
                if not retry_truncated:
                    return None
                # Reasoning consumed the budget: retry once with a larger cap.
                payload["max_tokens"] = min(max_tokens * 3, 4000)
                with _usage_lock:
                    _usage["requests"] += 1
                response = observed_request(self._get_client(), "post", "/chat/completions", provider="NVIDIA NIM", json=payload)
                response.raise_for_status()
                data = response.json()
                record_usage(data)
                return data["choices"][0]["message"].get("content") or None
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, TimeoutError) as error:
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

    def tool_turn(self, messages: list[dict], tools: list[dict], *, temperature: float) -> dict:
        """One actual model decision. Tool execution belongs to the agent loop.

        No fixed seed or cached answer. Never silently substitute an offline
        result for a failed hosted run, and never return hidden reasoning.
        """
        if not self.available:
            raise RuntimeError("NVIDIA_API_KEY is missing")
        if settings.nim_agent_protocol == "json":
            # JSON actions avoid hosted-model function-parser defects while
            # retaining the same real observe/act loop and tool allowlist.
            converted = []
            for message in messages:
                if message["role"] == "system":
                    content = message["content"] + "\nAvailable tools: " + json.dumps(tools) + (
                        '\nReturn exactly one JSON action: {"tool":"tool_name","arguments":{}}. '
                        'Use finish with summary and optional selected_indices only after observing tool results. '
                        'No prose outside the JSON. Never fabricate tool observations.')
                    converted.append({"role": "system", "content": content})
                elif message.get("tool_calls"):
                    function = message["tool_calls"][0]["function"]
                    converted.append({"role": "assistant", "content": json.dumps(
                        {"tool": function["name"], "arguments": json.loads(function["arguments"])})})
                elif message["role"] == "tool":
                    converted.append({"role": "user", "content": "Actual tool observation:\n" + message["content"]})
                else:
                    converted.append(message)
            # Carry the bounded work log as data in a fresh user turn. Some
            # hosted gpt-oss templates emit empty final content when replaying
            # assistant JSON actions as conversation turns.
            converted = [converted[0], {"role": "user", "content": json.dumps(
                {"working_history": converted[1:], "next_step": "Choose the next tool action from the actual observations."})}]
            action = self.chat_json(converted, temperature=temperature, max_tokens=1600,
                                    model=settings.nim_agent_model)
            if not action or not isinstance(action.get("tool"), str) or not isinstance(action.get("arguments"), dict):
                raise RuntimeError("NVIDIA returned no valid tool action")
            return {"role": "assistant", "content": None, "tool_calls": [{"id": uuid.uuid4().hex,
                "type": "function", "function": {"name": action["tool"], "arguments": json.dumps(action["arguments"])}}]}
        if settings.nim_agent_protocol != "native":
            raise ValueError("NIM_AGENT_PROTOCOL must be json or native")
        payload = dict(model=settings.nim_agent_model, messages=messages, tools=tools,
                       tool_choice="auto", temperature=temperature, max_tokens=2400)
        if "gpt-oss" in settings.nim_agent_model:
            payload["reasoning_effort"] = "low"
        if "nemotron-3" in settings.nim_agent_model or "nemotron-nano-3" in settings.nim_agent_model:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        with inference_semaphore():
            with _usage_lock:
                _usage["requests"] += 1
            response = observed_request(self._get_client(), "post", "/chat/completions", provider="NVIDIA NIM", json=payload)
            response.raise_for_status()
            data = response.json()
            record_usage(data)
            message = data["choices"][0]["message"]
        # Hosted gpt-oss sometimes leaves a Harmony channel suffix attached to
        # a function name. Strip only that exact transport artifact; the agent
        # still validates the resulting name against its own tool allowlist.
        for call in message.get("tool_calls") or []:
            function = call.get("function", {})
            name = function.get("name", "")
            if name.endswith("<|channel|>commentary"):
                function["name"] = name.removesuffix("<|channel|>commentary")
        return {key: message[key] for key in ("role", "content", "tool_calls") if key in message}

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
