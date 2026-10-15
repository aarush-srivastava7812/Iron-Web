"""A payload-accounted LRU; the quota is not a process RSS limit."""

from collections import OrderedDict
from copy import deepcopy
import json
from threading import RLock


class PayloadCache:
    def __init__(self, max_bytes=32 * 1024 * 1024, max_entries=256):
        if max_bytes < 1 or max_entries < 1:
            raise ValueError("Cache bounds must be positive.")
        self.max_bytes, self.max_entries = max_bytes, max_entries
        self.items, self.bytes, self.lock = OrderedDict(), 0, RLock()

    def _remove(self, key):
        item = self.items.pop(key)
        self.bytes -= item[2]

    def get(self, key, now):
        with self.lock:
            if key not in self.items:
                return None
            value, expires, _ = self.items[key]
            if now >= expires:
                self._remove(key)
                return None
            self.items.move_to_end(key)
            return deepcopy(value)

    def put(self, key, value, expires):
        stored = deepcopy(value)
        size = len(json.dumps(stored, ensure_ascii=False, allow_nan=False).encode())
        size += len(repr(key).encode())
        with self.lock:
            if key in self.items:
                self._remove(key)
            if size > self.max_bytes:
                return False
            while self.items and (
                self.bytes + size > self.max_bytes
                or len(self.items) >= self.max_entries
            ):
                self._remove(next(iter(self.items)))
            self.items[key] = (stored, expires, size)
            self.bytes += size
            return True

    def invalidate(self, predicate=lambda key: True):
        with self.lock:
            for key in list(self.items):
                if predicate(key):
                    self._remove(key)
