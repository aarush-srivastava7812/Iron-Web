"""Runtime resource observation (RAM/VRAM where supported).

Iron Web does not manage inference KV caches or model residency; this monitor
only *reports* observed device status from the MemoryEngine plus process RSS.
"""
from __future__ import annotations

import os
from typing import Any


class ResourceMonitor:
    def __init__(self, memory_gateway=None) -> None:
        self.gateway = memory_gateway

    def snapshot(self) -> dict[str, Any]:
        data: dict[str, Any] = {"pid": os.getpid()}
        rss_mb = _process_rss_mb()
        if rss_mb is not None:
            data["process_rss_mb"] = rss_mb
        status = self.gateway.device_status() if self.gateway else None
        if status is not None:
            dump = status.model_dump() if hasattr(status, "model_dump") else dict(status)
            data["device"] = {
                "execution_mode": dump.get("execution_mode"),
                "embedder_provider": dump.get("embedder_provider"),
                "active_providers": dump.get("active_providers"),
                "vram_used_mb": dump.get("vram_used_mb"),
                "vram_free_mb": dump.get("vram_free_mb"),
            }
        return data


def _process_rss_mb() -> float | None:
    try:
        import resource  # noqa: F401  (unix only)

        return None  # ru_maxrss is peak, not current; not worth platform tricks here
    except ImportError:
        pass
    try:
        import ctypes

        class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = _PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(_PROCESS_MEMORY_COUNTERS)
        handle = ctypes.windll.kernel32.GetCurrentProcess()  # type: ignore[attr-defined]
        if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):  # type: ignore[attr-defined]
            return counters.WorkingSetSize / (1024 * 1024)
    except Exception:
        return None
    return None
