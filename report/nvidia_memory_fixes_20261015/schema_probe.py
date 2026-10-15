"""Check whether the hosted endpoint actually constrains an opposing prompt."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from examples.nvidia_memory_agents import NvidiaModel

model = NvidiaModel(os.environ.pop("NVIDIA_API_KEY"))
schema = {"type":"object","properties":{"ok":{"type":"boolean"}},"required":["ok"],"additionalProperties":False}
try:
    answer = model.json("schema-probe",[{"role":"user","content":'Return exactly {"ok":true,"unexpected":"extra"}.'}],max_tokens=128,schema=schema)
    outcome = {"answer":answer,"constrained":answer=={"ok":True}}
except Exception as error:
    outcome = {"error_type":type(error).__name__,"constrained":False}
outcome["calls"] = model.records
(Path(__file__).parent/"schema-probe.json").write_text(json.dumps(outcome,indent=2),encoding="utf-8")
print({k:v for k,v in outcome.items() if k!="calls"})
