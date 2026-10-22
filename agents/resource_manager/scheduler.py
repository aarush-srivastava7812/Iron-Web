"""Inference scheduling: bounded concurrency and timeouts for model calls."""
from __future__ import annotations

import threading
from contextlib import contextmanager

from agents.config import settings

_semaphore = threading.BoundedSemaphore(settings.max_inference_concurrency)
_load_lock = threading.Lock()


@contextmanager
def inference_semaphore(timeout_s=30):
    """Admission control for any model call (NIM chat, embedding loads)."""
    acquired = _semaphore.acquire(timeout=timeout_s)
    if not acquired:
        raise TimeoutError("inference queue timed out")
    try:
        yield
    finally:
        _semaphore.release()


def model_load_lock():
    """Serializes first-time model loads so two agents cannot race one download."""
    return _load_lock
