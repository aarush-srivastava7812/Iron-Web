"""Independent checks of captured outcomes, core hashes and artifact hygiene."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
RUN = OUT / "live_run_5"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


results, decisions = read(RUN/"results.json"), read(RUN/"decisions.json")
quotes = read(RUN/"travel_fixture.json")
independent = {}
for label, expected, budget in (("planner-initial",72600,90000),("planner-revised",64600,65000)):
    plan = decisions[label]
    # This recomputation deliberately does not import the application checker.
    cost = next(f["total_for_two"] for f in quotes["flight_offers"] if f["id"]==plan["flight_id"])
    cost += next(h["four_night_total"] for h in quotes["hotel_offers"] if h["id"]==plan["hotel_id"])
    cost += sum(a["cost_for_two"] for a in quotes["activity_offers"] if a["id"] in plan["activity_ids"])
    cost += sum(quotes["fixed_costs"].values())
    assert cost == expected == plan["total_inr"] and cost <= budget
    independent[label] = dict(recomputed_total=cost,current_budget=budget,passed=True)
pause = decisions["planner-no-suitable-hotel"]
assert min(h["walk_from_dropoff_metres"] for h in quotes["hotel_offers"]) > 50
assert pause["decision"]=="pause" and pause["flight_id"] is None and pause["hotel_id"] is None and pause["total_inr"] is None and pause["activity_ids"]==[]
assert decisions["reviewer-no-suitable-hotel"]["decision"]=="pause"
assert decisions["reviewer-negative-control"]["decision"]=="reject"
assert results["failure"] is None and all(results["checks"].values())
metadata = read(RUN/"metadata-sample.json")
assert metadata["source"].get("event_id")
assert all(c["source_event_ids"] for c in metadata["context"]["cards"])

source = read(RUN/"source-hashes.json")
core_matches = {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest for p,digest in source.items()}
assert all(core_matches.values())

tests = {}
for name in ("full-suite.xml","gpu-tests.xml","final-agent-tests.xml"):
    suites = list(ET.parse(OUT/name).getroot().iter("testsuite"))
    tests[name] = [{k:s.get(k) for k in ("tests","failures","errors","skipped","time")} for s in suites]
    assert all(int(s.get("failures","0"))==0 and int(s.get("errors","0"))==0 for s in suites)
fuzzy = read(OUT/"fuzzy-sweep.json")
assert fuzzy["violation_count"]==0 and all(fuzzy[k]["violation_count"]==0 for k in ("age","support","conflict"))
assert all(c["passed"] for c in read(OUT/"live-update-check.json")["cases"])

hits = []
for path in OUT.rglob("*"):
    if not path.is_file() or "__pycache__" in path.parts:
        continue
    data = path.read_bytes()
    if re.search(rb"nvapi-[A-Za-z0-9_-]{30,}", data):
        hits.append(str(path.relative_to(OUT)))
    if path.suffix==".json":
        def visit(value):
            if isinstance(value,dict):
                for key,item in value.items():
                    if key in {"api_key","token_hash","context_token","lease_token"} and item not in (None,"<redacted>"):
                        hits.append(str(path.relative_to(OUT))+":"+key)
                    visit(item)
            elif isinstance(value,list):
                for item in value:
                    visit(item)
        visit(read(path))
assert not hits

paths = [ROOT/p for p in source] + [ROOT/p for p in (
    "examples/nvidia_memory_agents.py","examples/travel_intake.py","examples/travel_planning.py",
    "examples/fixtures/travel_catalog.json","scripts/evaluate_nvidia_memory.py",
    "tests/test_memory_reliability_fixes.py","tests/test_guarded_travel_agents.py",
    "tests/test_travel_intake_grounding.py","tests/test_nvidia_stream_safety.py",
    "tests/test_nvidia_memory_evaluation.py")]
verification = dict(
    head=subprocess.check_output(["git","-c","safe.directory="+ROOT.as_posix(),"rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
    uncommitted_changes=True, independent_outcomes=independent, tests=tests,
    live_checks=results["counts"], core_hashes_match_live_run=core_matches,
    fuzzy_evaluations=fuzzy["evaluations"]+sum(fuzzy[k]["evaluations"] for k in ("age","support","conflict")),
    secret_scan_hits=hits,
    final_source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
)
(OUT/"verification.json").write_text(json.dumps(verification,indent=2),encoding="utf-8")
print("Independent totals, pause/rejection, provenance, core hashes, tests and credential scan verified.")
print(json.dumps(verification["tests"]))
