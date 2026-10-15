"""Two real-model checks for the originally broken natural update wording."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from examples.nvidia_memory_agents import NvidiaModel, TravelIntake

model = NvidiaModel(os.environ.pop("NVIDIA_API_KEY"))
intake = TravelIntake(model)
cases = []
for source, expected in [
    ("Please change my total trip budget to INR 65000.", {"budget":65000}),
    ("Please change my total trip budget to INR 65000 and my maximum walking distance to 50 metres.", {"budget":65000,"max_walk_metres":50}),
]:
    row = dict(source=source,expected=expected)
    try:
        claims = intake(source,dict(subject="Riya",scope={"trip_id":"goa-family"}))
        row.update(claims=claims,passed={c["predicate"]:c["value"] for c in claims}==expected and all(c["action"]=="supersede" for c in claims))
    except Exception as error:
        row.update(passed=False,error_type=type(error).__name__)
    cases.append(row)
    print("Update check:",row["passed"],flush=True)
result = dict(cases=cases,calls=model.records,normalizations=intake.normalizations)
(Path(__file__).parent/"live-update-check.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
assert all(c["passed"] for c in cases)
