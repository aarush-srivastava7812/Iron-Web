"""Correct annotation terminology and recompute analysis from frozen timings.

This never reruns queries or changes raw measurements. Empty ground-truth IDs
mean missing reference labels, not proof that a question has no answer.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.benchmark_vector_placement import compare


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("report",type=Path);a=p.parse_args();out=a.report.resolve()
    original=out/"comparison_before_annotation_correction.json"
    if original.exists():p.error("Analysis already finalized; preserve existing evidence.")
    shutil.copy2(out/"comparison.json",original)
    manifest=json.loads((out/"manifest.json").read_text())
    results=json.loads(original.read_text())
    for name,result in results.items():
        rows=json.loads((out/(name+"_raw.json")).read_text())
        result["comparison"]=compare(rows,manifest["rounds"],manifest["tolerance_provisional"])
    (out/"comparison.json").write_text(json.dumps(results,indent=2,allow_nan=False),encoding="utf-8")
    (out/"analysis_revision.json").write_text(json.dumps(dict(
        raw_timings_changed=False,raw_evidence_ids_changed=False,
        changes=["Reference-free questions labelled unscorable rather than unavailable",
                 "Failed queries remain zero-score observations rather than being removed from quality",
                 "Intervals wholly outside the provisional tolerance labelled fail rather than inconclusive"],
        measured_source="source_snapshot",analysis_source_sha256=hashlib.sha256((ROOT/"scripts/benchmark_vector_placement.py").read_bytes()).hexdigest()
    ),indent=2),encoding="utf-8")
    print("Recomputed analysis from frozen measurements:",out)


if __name__=="__main__":main()
