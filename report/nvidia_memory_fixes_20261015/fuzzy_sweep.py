"""Probe expected directional behavior without changing score_memory."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from memory.lifecycle.fuzzy import score_memory

cases = []
evaluations = 0
for days in (0, 30, 90, 365):
    for groups in (1, 2, 3):
        for conflicts in (0, 1, 3):
            previous = None
            for q in range(101):
                args = dict(age_seconds=days*86400, half_life_days=90,
                            source_quality=q/100, independent_groups=groups, conflicts=conflicts)
                score = score_memory(**args)["score"]
                evaluations += 1
                if previous is not None and score < previous["score"] - 1e-12:
                    cases.append(dict(previous=previous, current=dict(inputs=args, score=score)))
                previous = dict(inputs=args, score=score)
result = dict(evaluations=evaluations, direction="source_quality increased by 0.01 with other inputs fixed",
              violation_count=len(cases), violations=cases,
              limitation="Finite grid diagnostic; no statistical calibration or causal inference.")
for axis in ("age", "support", "conflict"):
    reversals, checks = [], 0
    for q in (0.1, 0.25, 0.5, 0.75, 0.9):
        for days in ((0,) if axis == "age" else (0, 30, 90, 365)):
            for groups in ((1,) if axis == "support" else (1, 2, 3)):
                for conflicts in ((0,) if axis == "conflict" else (0, 1, 3)):
                    previous = None
                    values = range(366) if axis == "age" else range(4) if axis == "support" else range(21)
                    for value in values:
                        args = dict(age_seconds=(value if axis == "age" else days)*86400,
                                    half_life_days=90, source_quality=q,
                                    independent_groups=value if axis == "support" else groups,
                                    conflicts=value if axis == "conflict" else conflicts)
                        score = score_memory(**args)["score"]
                        checks += 1
                        if previous is not None:
                            delta = score - previous["score"]
                            if (axis == "support" and delta < -1e-12) or (axis != "support" and delta > 1e-12):
                                reversals.append(dict(previous=previous, current=dict(inputs=args, score=score)))
                        previous = dict(inputs=args, score=score)
    result[axis] = dict(evaluations=checks, violation_count=len(reversals), violations=reversals)
(Path(__file__).parent / "fuzzy-sweep.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print("Fuzzy sweep", evaluations, "evaluations;", len(cases), "quality-direction reversals")
for axis in ("age", "support", "conflict"):
    print(axis, result[axis]["evaluations"], "evaluations", result[axis]["violation_count"], "reversals")
