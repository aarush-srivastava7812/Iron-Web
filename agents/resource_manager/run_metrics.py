"""Per-operation accounting, isolated across parallel specialist threads."""

from contextlib import contextmanager
from contextvars import ContextVar
import time

_meter = ContextVar("agent_run_metrics", default=None)


@contextmanager
def capture_metrics():
    values = {
        "requests": 0,
        "failed_requests": 0,
        "http_ms": 0.0,
        "input_tokens": None,
        "output_tokens": None,
        "usage_responses": 0,
        "providers": {},
        "cost": None,
        "cost_note": "Provider billing was not returned",
        "scope": "direct calls in this agent operation",
    }
    reset = _meter.set(values)
    try:
        yield values
    finally:
        _meter.reset(reset)


def observed_request(client, method, url, *, provider, **kwargs):
    values = _meter.get()
    started = time.perf_counter()
    if values is not None:
        values["requests"] += 1
        values["providers"][provider] = values["providers"].get(provider, 0) + 1
    try:
        response = getattr(client, method)(url, **kwargs)
        if values is not None:
            values["failed_requests"] += int(response.status_code >= 400)
            if provider == "NVIDIA NIM" and response.status_code < 400:
                try:
                    usage = response.json().get("usage") or {}
                    if usage:
                        values["usage_responses"] += 1
                        for field, key in (
                            ("input_tokens", "prompt_tokens"),
                            ("output_tokens", "completion_tokens"),
                        ):
                            if isinstance(usage.get(key), int):
                                values[field] = (values[field] or 0) + usage[key]
                except (ValueError, AttributeError):
                    pass
        return response
    except Exception:
        if values is not None:
            values["failed_requests"] += 1
        raise
    finally:
        if values is not None:
            values["http_ms"] = round(
                values["http_ms"] + (time.perf_counter() - started) * 1000, 2
            )


def resource_sample(gateway, cpu_started):
    """Shared process/device samples are not exclusive per-agent allocations."""
    from agents.resource_manager.resource_monitor import _process_rss_mb

    rss = _process_rss_mb()
    result = dict(
        process_cpu_ms=round((time.process_time() - cpu_started) * 1000, 2),
        ram_bytes=int(rss * 1048576) if rss is not None else None,
        vram_bytes=None,
        gpu_util=None,
        scope="shared website process/device sample; concurrent work is included",
    )
    try:
        if hasattr(gateway, "service"):
            engine = gateway.service.engine(gateway.user_id)
            device = engine.get_device_status().model_dump()
            result["device"] = device
            if device.get("vram_used_mb") is not None:
                result["vram_bytes"] = int(device["vram_used_mb"] * 1048576)
    except Exception:
        result["device_note"] = "Device telemetry unavailable"
    return result
