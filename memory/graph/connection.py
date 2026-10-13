"""FalkorDB result iteration, safe Cypher parameters and shared graph leases."""

import math
import re
from threading import Event, RLock, Thread


def cypher_value(value):
    """Serialize parameters without allowing user text to enter Cypher syntax."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        if "\x00" in value:
            raise ValueError("Cypher strings cannot contain NUL bytes.")
        # FalkorDB preserves literal line controls; JSON-style \n escaping
        # would store a backslash followed by n instead of the original line.
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError("Cypher parameters must be finite.")
        return str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(cypher_value(item) for item in value) + "]"
    if isinstance(value, dict):
        if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) for key in value):
            raise ValueError("Invalid Cypher property name.")
        return (
            "{"
            + ",".join(f"{key}:{cypher_value(item)}" for key, item in value.items())
            + "}"
        )
    raise TypeError(f"Unsupported Cypher parameter type: {type(value).__name__}")


def parameterized(query, parameters):
    if not parameters:
        return query
    if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) for key in parameters):
        raise ValueError("Invalid Cypher parameter name.")
    # Validate identifiers and serialize a CYPHER header independently of the
    # query body. Multiline content must round-trip byte for byte.
    return (
        "CYPHER "
        + " ".join(f"{key}={cypher_value(value)}" for key, value in parameters.items())
        + " "
        + query
    )


class GraphResult:
    def __init__(self, rows, columns=()):
        self.rows = rows
        self.columns = list(columns)
        self.index = 0

    def has_next(self):
        return self.index < len(self.rows)

    def get_next(self):
        if not self.has_next():
            raise StopIteration
        row = self.rows[self.index]
        self.index += 1
        return row

    def get_column_names(self):
        return self.columns.copy()


class GraphConnection:
    def __init__(self, store):
        self.store = store

    def execute(self, query, params=None):
        return self.store.execute(query, params)


class GraphLease:
    """Reentrant thread lock plus a renewed, token-owned Redis lease.

    Every cooperating reader/writer uses the same lock key. A failed renewal
    rejects later queries and publication rather than continuing without a lock.
    """

    def __init__(self, client, key, lease_seconds=60, wait_seconds=30):
        self.mutex = RLock()
        self.lock = client.lock(
            key,
            timeout=lease_seconds,
            blocking_timeout=wait_seconds,
            thread_local=False,
        )
        self.depth = 0
        self.lease_seconds = lease_seconds
        self.stop = Event()
        self.failed = None
        self.heartbeat = None

    def _renew(self):
        while not self.stop.wait(self.lease_seconds / 3):
            try:
                self.lock.extend(self.lease_seconds, replace_ttl=True)
            except Exception as error:
                self.failed = error
                return

    def assert_owned(self):
        if self.failed is not None or not self.lock.owned():
            raise RuntimeError(
                "FalkorDB graph lease was lost; the operation cannot continue."
            )

    @property
    def token(self):
        self.assert_owned()
        return self.lock.local.token

    def __enter__(self):
        self.mutex.acquire()
        try:
            if self.depth == 0:
                if not self.lock.acquire():
                    raise TimeoutError(
                        "Timed out waiting for the FalkorDB graph lease."
                    )
                self.failed = None
                self.stop = Event()
                self.heartbeat = Thread(target=self._renew, daemon=True)
                self.heartbeat.start()
            self.depth += 1
            return self
        except Exception:
            self.mutex.release()
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        self.depth -= 1
        try:
            if self.depth == 0:
                self.stop.set()
                self.heartbeat.join(timeout=5)
                try:
                    self.lock.release()
                except Exception:
                    if exc_type is None:
                        raise
        finally:
            self.mutex.release()
