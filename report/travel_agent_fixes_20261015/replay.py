"""Replay the original travel scenario against a fresh post-fix audit service."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path

import harness

OUT = Path(__file__).resolve().parent


def call(spec):
    path = OUT / "requests" / (spec["label"] + ".json")
    harness.save(path, spec)
    with redirect_stdout(io.StringIO()):
        harness.call(path)
    recorded = json.loads((OUT / "exchanges" / (spec["label"] + ".json")).read_text(encoding="utf-8"))
    print(json.dumps(dict(label=spec["label"], http_status=recorded["http_status"],
                         status=recorded["response"].get("status") if isinstance(recorded["response"], dict) else "results")), flush=True)


def run():
    original = sorted((OUT / "requests").glob("*.json"))
    for path in original:
        if int(path.stem[:2]) >= 66:
            continue  # Stop only after recording the additional controls.
        spec = json.loads(path.read_text(encoding="utf-8"))
        call(spec)
    base = dict(tenant="riya", actor="user")
    call(dict(base, label="67-ambiguous-intake", path="/v1/events", body=dict(
        event_id="ambiguous-intake", subject="Riya", scope={"trip_id": "goa-family"}, confirmed=True,
        text="Budget is INR 65000 total. Wheelchair assistance at the airport, only if needed.")))
    call(dict(label="68-process-ambiguous", path="/audit/drain", body={}))
    call(dict(label="69-ambiguous-status", path="/v1/events/status", actor="user", body=dict(eid="ambiguous-intake")))
    call(dict(label="70-ambiguous-blocks", path="/v1/context", body=dict(
        subject="Riya", scope={"trip_id": "goa-family"}, task_type="itinerary")))
    call(dict(base, label="71-resolve-ambiguous", path="/v1/events/withdraw", body=dict(eid="ambiguous-intake")))
    call(json.loads((OUT / "requests/66-stop-audit-service.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    run()
