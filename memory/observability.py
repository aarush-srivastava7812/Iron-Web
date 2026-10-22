"""Bounded, disposable observations of real agent work; never a memory authority."""

from collections import deque, OrderedDict
from copy import deepcopy
import logging
import os
import re
from threading import RLock
import time
import uuid

logger = logging.getLogger(__name__)
_SECRET_FIELD = re.compile(r"token|secret|password|authorization|api.?key|handle", re.I)
_SECRET_TEXT = re.compile(
    r"(?:nvapi-|sk-(?:proj-)?)[A-Za-z0-9_-]{12,}|Bearer\s+[A-Za-z0-9._-]+", re.I
)
_PUBLIC_ACCOUNTING_FIELDS = {
    "tokenizer",
    "tokens",
    "input_tokens",
    "half_tokens",
    "card_tokens",
    "evidence_tokens",
    "output_tokens",
}
PACKET_FIELDS = (
    "status",
    "required_issues",
    "agent_text",
    "traveller_text",
    "cards",
    "evidence_text",
    "claim_ids",
    "fields",
    "tokenizer",
    "tokens",
    "residency",
    "cache_hit",
)


def public_value(value):
    """Allow callers to pass source data without leaking credentials or proof tokens."""
    if isinstance(value, dict):
        return {
            str(k): public_value(v)
            for k, v in value.items()
            if not _SECRET_FIELD.search(str(k)) or str(k) in _PUBLIC_ACCOUNTING_FIELDS
        }
    if isinstance(value, (list, tuple)):
        return [public_value(v) for v in value]
    if isinstance(value, str):
        result = _SECRET_TEXT.sub("[redacted credential]", value)
        for key, secret in os.environ.items():
            if _SECRET_FIELD.search(key) and len(secret) >= 8:
                result = result.replace(secret, "[redacted credential]")
        return result[:16000]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:200]


class ObservationLog:
    def __init__(self, limit=500, sink=None):
        self.sink = sink
        self.persistence_error = None
        self.lock, self.events, self.contexts = (
            RLock(),
            deque(maxlen=limit),
            OrderedDict(),
        )
        self.sequence, self.boot = 0, uuid.uuid4().hex

    def emit(self, trip_id, kind, *, agent_id=None, packet=None, **detail):
        # Observability must never turn a successful memory operation into a failure.
        try:
            with self.lock:
                self.sequence += 1
                event = dict(
                    id=self.sequence,
                    boot=self.boot,
                    timestamp=time.time(),
                    trip_id=trip_id,
                    kind=kind,
                    agent_id=agent_id,
                    detail=public_value(detail),
                )
                self.events.append(event)
                if packet is not None:
                    captured = public_value(
                        {k: packet[k] for k in PACKET_FIELDS if k in packet}
                    )
                    event["context"] = deepcopy(captured)
                    self.contexts.pop((trip_id, agent_id), None)
                    while len(self.contexts) >= 256:
                        self.contexts.popitem(last=False)
                    self.contexts[(trip_id, agent_id)] = dict(
                        agent_id=agent_id,
                        captured_at=event["timestamp"],
                        event_id=self.sequence,
                        **captured,
                    )
                if self.sink:
                    self.sink.append(deepcopy(event))
                    self.persistence_error = None
        except Exception:
            self.persistence_error = "Agent history could not be written to disk"
            logger.warning("Could not record a dashboard event", exc_info=False)

    def invalidate(self, trip_id=None, *, purge_history=False):
        with self.lock:
            if purge_history:
                if self.sink:
                    self.sink.redact(trip_id)
                for event in self.events:
                    if trip_id is None or event["trip_id"] == trip_id:
                        event.pop("context", None)
                        event["detail"].pop("changes", None)
                        event["detail"].pop("execution", None)
            for key in list(self.contexts):
                if trip_id is None or key[0] == trip_id:
                    del self.contexts[key]

    def snapshot(self, trip_id):
        with self.lock:
            return deepcopy(
                dict(
                    boot=self.boot,
                    sequence=self.sequence,
                    retained_from=self.events[0]["id"]
                    if self.events
                    else self.sequence + 1,
                    events=[
                        e
                        for e in self.events
                        if trip_id is None or e["trip_id"] in {trip_id, ""}
                    ],
                    contexts=[
                        v
                        for (trip, _), v in self.contexts.items()
                        if trip_id is None or trip == trip_id
                    ],
                )
            )
