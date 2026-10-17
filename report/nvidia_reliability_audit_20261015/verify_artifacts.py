"""Verify audit evidence, unchanged implementation and basic secret hygiene."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
old = ROOT / "report/nvidia_multi_agent_20261015_verified"

# Canonical absolute Windows file links for the local Codex report viewer.
readme = OUT / "README.md"
readme.write_text(readme.read_text(encoding="utf-8").replace("(/D:/", "(D:/"), encoding="utf-8")

hash_sets = {}
for name in ("source-hashes.json", "runner-hashes.json"):
    expected = json.loads((old / name).read_text(encoding="utf-8"))
    results = []
    for raw_path, digest in expected.items():
        path = ROOT / raw_path
        results.append(dict(path=raw_path, unchanged=path.is_file() and
            hashlib.sha256(path.read_bytes()).hexdigest() == digest))
    hash_sets[name] = results

tests = {}
for path in OUT.glob("*.xml"):
    suites = ET.parse(path).getroot().iter("testsuite")
    tests[path.name] = [{k:s.get(k) for k in ("tests", "failures", "errors", "skipped", "time")} for s in suites]

live = [json.loads(p.read_text(encoding="utf-8")) for p in (OUT/"live").glob("*.json") if p.name != "summary.json"]
pairs = {}
for label in ("planner-initial", "planner-revised", "reviewer-initial"):
    rows = [r for r in live if r["label"].startswith(label)]
    assert len(rows) == 2
    pairs[label] = dict(identical_messages=rows[0]["messages"] == rows[1]["messages"],
        identical_token_cap=rows[0]["max_tokens"] == rows[1]["max_tokens"],
        identical_temperature=rows[0]["temperature"] == rows[1]["temperature"],
        identical_top_p=rows[0]["top_p"] == rows[1]["top_p"],
        thinking_flags=sorted(r["enable_thinking"] for r in rows))

secret_hits = []
for path in OUT.rglob("*"):
    if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
        continue
    content = path.read_bytes()
    if re.search(rb"nvapi-[A-Za-z0-9_-]{30,}", content):
        secret_hits.append(str(path.relative_to(OUT)))
    if path.suffix == ".json":
        value = json.loads(content)
        def check(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in {"lease_token", "context_token", "api_key", "token_hash"} and item not in (None, "<redacted>"):
                        secret_hits.append(str(path.relative_to(OUT)) + ":" + key)
                    check(item)
            elif isinstance(value, list):
                for item in value:
                    check(item)
        check(value)

result = dict(
    head=subprocess.check_output(["git", "-c", "safe.directory="+ROOT.as_posix(), "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    implementation_hash_checks=hash_sets, pytest=tests, paired_input_checks=pairs,
    secret_scan_hits=secret_hits,
    plaintext_key_file_exists=(ROOT / "data/nvidia_live_eval/key.txt").exists(),
    audit_files={str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(OUT.rglob("*")) if p.is_file() and p.name != "verification.json"
                 and "__pycache__" not in p.parts},
)
(OUT/"verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
assert all(r["unchanged"] for rows in hash_sets.values() for r in rows), "Implementation changed"
assert not secret_hits and not result["plaintext_key_file_exists"]
assert all(all(row.values()) for row in pairs.values())
print("Verified", sum(map(len, hash_sets.values())), "unchanged implementation files;", len(live), "live calls; no credential/proof values found.")
print("Tests:", tests)
