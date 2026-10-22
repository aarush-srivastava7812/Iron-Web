"""Durable receipts, prepared interpretations and replayable notifications.

This queue is not a second semantic memory store. FalkorDB remains authoritative
for accepted claims and task state; Qdrant remains the vector discovery store.
"""

import json
import hashlib
import sqlite3
from threading import RLock
import time


class EventJournal:
    def __init__(self, path):
        self.lock = RLock()
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS events (
          tenant TEXT NOT NULL, id TEXT NOT NULL, digest TEXT NOT NULL,
          actor TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL,
          submitted REAL NOT NULL, started REAL, ready REAL, attempts INTEGER DEFAULT 0,
          prepared TEXT, memory_id TEXT NOT NULL, error TEXT,
          blocks_work INTEGER NOT NULL, sequence INTEGER PRIMARY KEY AUTOINCREMENT,
          UNIQUE(tenant,id));
        CREATE INDEX IF NOT EXISTS queue_status ON events(status,sequence);
        CREATE TABLE IF NOT EXISTS notices (
          tenant TEXT NOT NULL, id TEXT NOT NULL, event_id TEXT NOT NULL,
          payload TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(tenant,id));
        CREATE TABLE IF NOT EXISTS acknowledgments (
          tenant TEXT NOT NULL, id TEXT NOT NULL, actor TEXT NOT NULL,
          PRIMARY KEY(tenant,id,actor));
        CREATE TABLE IF NOT EXISTS space_state (
          tenant TEXT PRIMARY KEY, generation INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS memory_barriers (
          tenant TEXT NOT NULL, change_id TEXT NOT NULL, target_id TEXT NOT NULL,
          relation TEXT NOT NULL, recorded_at INTEGER NOT NULL, effective_at INTEGER NOT NULL,
          PRIMARY KEY(tenant,change_id,target_id,relation));
        INSERT OR IGNORE INTO space_state SELECT DISTINCT tenant,1 FROM events;
        CREATE TRIGGER IF NOT EXISTS events_generation_insert AFTER INSERT ON events
        BEGIN
          INSERT INTO space_state VALUES(NEW.tenant,1)
          ON CONFLICT(tenant) DO UPDATE SET generation=generation+1;
        END;
        CREATE TRIGGER IF NOT EXISTS events_generation_update AFTER UPDATE ON events
        BEGIN
          INSERT INTO space_state VALUES(NEW.tenant,1)
          ON CONFLICT(tenant) DO UPDATE SET generation=generation+1;
        END;
        CREATE TRIGGER IF NOT EXISTS events_generation_delete AFTER DELETE ON events
        BEGIN
          INSERT INTO space_state VALUES(OLD.tenant,1)
          ON CONFLICT(tenant) DO UPDATE SET generation=generation+1;
        END;
        """)
        # Only one service owns this journal. An interrupted worker is replayed.
        with self.db:
            self.db.execute(
                "UPDATE events SET status='queued' WHERE status='interpreting'"
            )

    def generation(self, tenant):
        """Durable epoch; triggers cover every transactional event mutation."""
        with self.lock:
            row = self.db.execute(
                "SELECT generation FROM space_state WHERE tenant=?", (tenant,)
            ).fetchone()
            return row[0] if row else 0

    @staticmethod
    def public(row):
        if row is None:
            return None
        result = {
            k: row[k]
            for k in (
                "id",
                "status",
                "submitted",
                "started",
                "ready",
                "attempts",
                "memory_id",
                "error",
                "blocks_work",
            )
        }
        prepared = json.loads(row["prepared"]) if row["prepared"] else {}
        claims = prepared.get("claims") or []
        result.update(
            interpretation=prepared.get("mode"),
            claim_kinds=sorted({c["kind"] for c in claims}),
            semantic_claim_count=sum(c["kind"] != "episode" for c in claims),
        )
        return result

    def get(self, tenant, eid):
        with self.lock:
            return self.db.execute(
                "SELECT * FROM events WHERE tenant=? AND id=?", (tenant, eid)
            ).fetchone()

    def submit(self, tenant, eid, digest, actor, payload, mid, blocks):
        with self.lock, self.db:
            previous = self.get(tenant, eid)
            if previous:
                if previous["digest"] != digest or previous["actor"] != actor:
                    raise ValueError(
                        "Event ID already belongs to different immutable input."
                    )
                return self.public(previous)
            self.db.execute(
                "INSERT INTO events(tenant,id,digest,actor,payload,status,submitted,memory_id,blocks_work) VALUES(?,?,?,?,?,'queued',?,?,?)",
                (
                    tenant,
                    eid,
                    digest,
                    actor,
                    json.dumps(payload, allow_nan=False),
                    time.time(),
                    mid,
                    int(blocks),
                ),
            )
            return self.public(self.get(tenant, eid))

    def take(self):
        with self.lock, self.db:
            row = self.db.execute(
                "SELECT e.* FROM events e WHERE e.status='queued' AND NOT EXISTS "
                "(SELECT 1 FROM events running WHERE running.tenant=e.tenant AND running.status='interpreting') "
                "ORDER BY e.sequence LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            self.db.execute(
                "UPDATE events SET status='interpreting',started=?,attempts=attempts+1 WHERE sequence=?",
                (time.time(), row["sequence"]),
            )
            return self.get(row["tenant"], row["id"])

    def prepared(self, row, value):
        with self.lock, self.db:
            self.db.execute(
                "UPDATE events SET prepared=? WHERE sequence=?",
                (json.dumps(value, allow_nan=False), row["sequence"]),
            )

    def finish(self, row, notification, status="ready", reason=None):
        with self.lock, self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO notices VALUES(?,?,?,?,?)",
                (
                    row["tenant"],
                    row["id"],
                    row["id"],
                    json.dumps(notification, allow_nan=False),
                    time.time(),
                ),
            )
            self.db.execute(
                "UPDATE events SET status=?,ready=?,error=? WHERE sequence=?",
                (status, time.time(), reason, row["sequence"]),
            )

    def fail(self, row, message):
        with self.lock, self.db:
            self.db.execute(
                "UPDATE events SET status='failed',error=? WHERE sequence=?",
                (message[:2000], row["sequence"]),
            )

    @staticmethod
    def affects_scope(payload, scope):
        """Unknown/global/identity changes block all trips; explicit trips do not.

        Structured claims are authoritative, including multi-trip events. Never
        trust a narrow envelope to hide a broader claim inside the same event.
        """
        if not scope or not scope.get("trip_id"):
            return True
        claims = payload.get("claims")
        if claims:
            return any(
                c.get("action") == "alias"
                or not c.get("scope", {}).get("trip_id")
                or c["scope"]["trip_id"] == scope["trip_id"]
                for c in claims
            )
        event_scope = payload.get("scope", {})
        return (
            not event_scope.get("trip_id") or event_scope["trip_id"] == scope["trip_id"]
        )

    def scope_fingerprint(self, tenant, scope):
        """Hash relevant durable rows, including pending and withdrawn transitions.

        Unlike a tenant-wide epoch this survives unrelated trip writes. Streaming
        rows avoids an unbounded in-memory event copy; deletion changes the hash.
        """
        digest = hashlib.sha256()
        with self.lock:
            for row in self.db.execute(
                "SELECT * FROM events WHERE tenant=? ORDER BY sequence", (tenant,)
            ):
                if self.affects_scope(json.loads(row["payload"]), scope):
                    digest.update(
                        json.dumps(
                            dict(row), sort_keys=True, separators=(",", ":")
                        ).encode()
                    )
                    digest.update(b"\n")
        return digest.hexdigest()

    def pending(self, tenant, scope=None):
        with self.lock:
            return [
                self.public(r)
                for r in self.db.execute(
                    "SELECT * FROM events WHERE tenant=? AND blocks_work=1 AND status IN ('queued','interpreting','failed','needs_review') ORDER BY sequence",
                    (tenant,),
                )
                if self.affects_scope(json.loads(r["payload"]), scope)
            ]

    def retry(self, tenant, eid):
        with self.lock, self.db:
            row = self.get(tenant, eid)
            if row is None or row["status"] != "failed":
                raise ValueError("Only a failed receipt can be retried.")
            self.db.execute(
                "UPDATE events SET status='queued',error=NULL WHERE tenant=? AND id=?",
                (tenant, eid),
            )
            return self.public(self.get(tenant, eid))

    def notices(self, tenant, actor):
        with self.lock:
            return [
                dict(
                    id=r["id"],
                    event_id=r["event_id"],
                    created=r["created"],
                    **json.loads(r["payload"]),
                )
                for r in self.db.execute(
                    "SELECT n.* FROM notices n WHERE n.tenant=? AND NOT EXISTS(SELECT 1 FROM acknowledgments a WHERE a.tenant=n.tenant AND a.id=n.id AND a.actor=?) ORDER BY n.created",
                    (tenant, actor),
                )
            ]

    def acknowledge(self, tenant, actor, nid):
        with self.lock, self.db:
            if not self.db.execute(
                "SELECT 1 FROM notices WHERE tenant=? AND id=?", (tenant, nid)
            ).fetchone():
                raise ValueError("Unknown notification.")
            self.db.execute(
                "INSERT OR IGNORE INTO acknowledgments VALUES(?,?,?)",
                (tenant, nid, actor),
            )

    def export(self, tenant):
        with self.lock:
            return [
                dict(r)
                for r in self.db.execute(
                    "SELECT * FROM events WHERE tenant=? ORDER BY sequence", (tenant,)
                )
            ]

    def close(self):
        with self.lock:
            self.db.close()

    def history(self, tenant, limit=50, after=0, session_id=None):
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 200
            or not isinstance(after, int)
            or isinstance(after, bool)
            or after < 0
        ):
            raise ValueError(
                "History requires a limit of 1–200 and a nonnegative cursor."
            )
        if session_id is not None and not isinstance(session_id, str):
            raise ValueError("Session ID must be text.")
        with self.lock:
            rows = self.db.execute(
                "SELECT * FROM events WHERE tenant=? AND sequence>? "
                "AND (? IS NULL OR json_extract(payload,'$.session_id')=?) ORDER BY sequence LIMIT ?",
                (tenant, after, session_id, session_id, limit),
            ).fetchall()
            items = []
            for row in rows:
                payload = json.loads(row["payload"])
                items.append(
                    dict(
                        receipt=self.public(row),
                        cursor=row["sequence"],
                        actor=row["actor"],
                        text=payload.get("text"),
                        subject=payload.get("subject"),
                        scope=payload.get("scope"),
                        session_id=payload.get("session_id"),
                    )
                )
            return dict(
                events=items, next_cursor=rows[-1]["sequence"] if rows else after
            )

    def redact(self, row, actor):
        with self.lock, self.db:
            notification = json.dumps(
                dict(memory_id=row["memory_id"], status="redacted", by=actor)
            )
            self.db.execute(
                "UPDATE events SET payload='{}',prepared=NULL,status='redacted',ready=?,error=NULL WHERE sequence=?",
                (time.time(), row["sequence"]),
            )
            self.db.execute(
                "UPDATE notices SET payload=? WHERE tenant=? AND event_id=?",
                (notification, row["tenant"], row["id"]),
            )
            self.db.execute(
                "INSERT OR IGNORE INTO notices VALUES(?,?,?,?,?)",
                (
                    row["tenant"],
                    row["id"] + ":redacted",
                    row["id"],
                    notification,
                    time.time(),
                ),
            )
