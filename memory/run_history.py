"""Tenant-local durable observations and agent summaries; never a fact store."""

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from threading import RLock


class RunHistory:
    def __init__(self, path):
        self.path, self.lock = Path(path), RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS observations (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, boot TEXT NOT NULL,
                    event_id INTEGER NOT NULL, trip_id TEXT, agent_id TEXT,
                    kind TEXT NOT NULL, timestamp REAL NOT NULL, payload TEXT NOT NULL,
                    UNIQUE(boot,event_id));
                CREATE INDEX IF NOT EXISTS observation_trip ON observations(trip_id,sequence);
                CREATE TABLE IF NOT EXISTS runs (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL UNIQUE,
                    workflow_id TEXT, trip_id TEXT, agent_id TEXT NOT NULL,
                    status TEXT NOT NULL, started_at REAL, finished_at REAL,
                    elapsed_ms REAL, summary TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS runs_trip ON runs(trip_id,sequence);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def append(self, event):
        detail = dict(event["detail"], observation_boot=event["boot"])
        with self.lock, self.connect() as db:
            cursor = db.execute(
                "INSERT OR IGNORE INTO observations(boot,event_id,trip_id,agent_id,kind,timestamp,payload) VALUES(?,?,?,?,?,?,?)",
                (
                    event["boot"],
                    event["id"],
                    event["trip_id"],
                    event["agent_id"],
                    event["kind"],
                    event["timestamp"],
                    json.dumps(event, allow_nan=False),
                ),
            )
            if not cursor.rowcount:
                return
            if event["kind"] == "context_failed":
                detail = dict(
                    detail,
                    run_id="context:" + event["boot"] + ":" + str(event["id"]),
                    status="failed",
                    summary="Memory retrieval failed before agent execution",
                    elapsed_ms=detail.get("latency_ms"),
                    started_at=event["timestamp"]
                    - (detail.get("latency_ms") or 0) / 1000,
                    memory=dict(retrieval_ms=detail.get("latency_ms")),
                )
            if event["kind"] not in {
                "agent_started",
                "agent_completed",
                "context_failed",
            } or not detail.get("run_id"):
                return
            started = event["kind"] == "agent_started"
            db.execute(
                """INSERT INTO runs(run_id,workflow_id,trip_id,agent_id,status,started_at,finished_at,elapsed_ms,summary,payload)
                VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(run_id) DO UPDATE SET
                status=excluded.status, finished_at=excluded.finished_at, elapsed_ms=excluded.elapsed_ms,
                summary=excluded.summary, payload=excluded.payload""",
                (
                    detail["run_id"],
                    detail.get("workflow_id"),
                    event["trip_id"],
                    event["agent_id"],
                    "running" if started else detail.get("status", "failed"),
                    detail.get("started_at", event["timestamp"]),
                    None if started else event["timestamp"],
                    detail.get("elapsed_ms"),
                    detail.get("summary", "Agent started"),
                    json.dumps(detail, allow_nan=False),
                ),
            )

    def page(
        self,
        *,
        trip_id=None,
        agent_id=None,
        before=None,
        limit=30,
        include_details=True,
    ):
        limit = max(1, min(int(limit), 100))
        clauses, args = [], []
        for column, value in (("trip_id", trip_id), ("agent_id", agent_id)):
            if value is not None:
                clauses.append(column + "=?")
                args.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.lock, self.connect() as db:
            totals = dict(
                db.execute(
                    "SELECT count(*) AS total, sum(CASE WHEN status='running' THEN 1 ELSE 0 END) AS running FROM runs"
                    + where,
                    args,
                ).fetchone()
            )
            if before is not None:
                clauses.append("sequence<?")
                args.append(before)
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            rows = db.execute(
                "SELECT * FROM runs" + where + " ORDER BY sequence DESC LIMIT ?",
                [*args, limit + 1],
            ).fetchall()
        output = []
        for row in rows[:limit]:
            payload = json.loads(row["payload"])
            if not include_details:
                payload = {
                    key: value
                    for key, value in payload.items()
                    if key not in {"result", "execution"}
                }
            output.append({**dict(row), "payload": payload})
        return dict(
            rows=output,
            next_before=rows[limit - 1]["sequence"] if len(rows) > limit else None,
            **totals,
            durable=True,
            units=dict(elapsed_ms="milliseconds", timestamp="Unix seconds"),
        )

    def detail(self, run_id):
        with self.lock, self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return {**dict(row), "payload": json.loads(row["payload"])} if row else None

    def redact(self, trip_id=None):
        # Forgetting a trip removes private result/context text from history too.
        clause, args = (
            (" WHERE trip_id=?", (trip_id,)) if trip_id is not None else ("", ())
        )
        with self.lock, self.connect() as db:
            db.execute("DELETE FROM observations" + clause, args)
            db.execute(
                "UPDATE runs SET summary='Details removed at traveler request', payload='{}'"
                + clause,
                args,
            )
