"""Utility retention, never factual confidence. Database evidence is not evicted.

Half-life and reinforcement are explicit heuristics, not a learned probability.
Only application-confirmed importance=1 (or a confirmed rule) can be pinned.
The cache is disposable and bounded even for pinned, still-valid evidence.
"""

from collections import namedtuple
from dataclasses import dataclass
import json
import math
from threading import RLock
import time

from cachetools import TLRUCache


@dataclass(frozen=True)
class RetentionPolicy:
    half_life_days: float = 90.0
    reinforcement: float = 0.15
    relevance_distance: float = 0.5
    dedup_seconds: int = 900

    def __post_init__(self):
        if not math.isfinite(self.half_life_days) or self.half_life_days <= 0:
            raise ValueError("Half-life must be finite and positive.")
        if not 0 < self.reinforcement < 1:
            raise ValueError("Reinforcement must be between zero and one.")
        if not 0 < self.relevance_distance < 2 or self.dedup_seconds <= 0:
            raise ValueError("Invalid relevance or deduplication bound.")

    def score(self, state, now):
        if state.get("pinned", False):
            return 1.0
        age = max(0.0, now - state["last_decay_at"])
        return min(0.99, state["retention_base"]) * 2 ** (
            -age / (state["half_life_days"] * 86400)
        )

    def reinforce(self, state, now):
        score = self.score(state, now)
        return (
            1.0
            if state.get("pinned")
            else min(0.99, score + self.reinforcement * (0.99 - score))
        )


class EvidenceCache:
    """Two library-managed TLRU segments, serialized byte and entry limits.

    Reserved capacity prevents an ordinary scan from evicting pinned results.
    Both segments expire; a pin is not a promise of infinite RAM residency.
    """

    def __init__(self, maxbytes=2 * 1024 * 1024, maxentries=128, timer=time.monotonic):
        if maxbytes < 1024 or maxentries < 4:
            raise ValueError("Cache capacity is too small.")
        self.lock = RLock()
        self.maxentries = maxentries
        self.limits = (maxentries - maxentries // 4, maxentries // 4)
        self.parts = [
            TLRUCache(
                maxsize=budget,
                ttu=lambda key, item, now: now + item[1],
                timer=timer,
                getsizeof=lambda item: item[2],
            )
            for budget in (maxbytes - maxbytes // 4, maxbytes // 4)
        ]
        self.hits = self.misses = 0

    def get(self, key):
        with self.lock:
            for part in self.parts:
                if key in part:
                    self.hits += 1
                    return json.loads(part[key][0])
            self.misses += 1
            return None

    def put(self, key, value, *, score=0.0, eligible=False, ttl=30.0):
        if ttl <= 0:
            return
        payload = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        size = len(payload) + len(repr(key).encode())
        index = int(eligible and score == 1.0)
        with self.lock:
            part = self.parts[index]
            if size > part.maxsize:
                return
            self.parts[1 - index].pop(key, None)
            if key not in part:
                while len(part) >= self.limits[index]:
                    part.popitem()
            part[key] = (payload, ttl, size)

    def cache_clear(self):
        with self.lock:
            for part in self.parts:
                part.clear()

    def cache_info(self):
        with self.lock:
            Info = namedtuple("CacheInfo", "hits misses maxsize currsize bytes")
            return Info(
                self.hits,
                self.misses,
                self.maxentries,
                sum(len(p) for p in self.parts),
                sum(p.currsize for p in self.parts),
            )
