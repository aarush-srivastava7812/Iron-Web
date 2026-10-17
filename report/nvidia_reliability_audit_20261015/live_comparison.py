"""Small paired diagnostic on captured prompts; no memory-core changes."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from openai import OpenAI
from examples.nvidia_memory_agents import TravelIntake, check_plan, parse_object

OUT = Path(__file__).parent / "live"
OLD = ROOT / "report/nvidia_multi_agent_20261015_verified/model_calls"
MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"


class AuditModel:
    def __init__(self, key):
        self.client = OpenAI(api_key=key, base_url="https://integrate.api.nvidia.com/v1",
                             timeout=60, max_retries=0)
        self.rows = []

    def json(self, label, messages, max_tokens=5000, thinking=False):
        if label.startswith("intake-"):
            label = "intake-audit-" + str(len(self.rows) + 1)
        row = dict(label=label, model=MODEL, temperature=0, top_p=0.95,
                   max_tokens=max_tokens, enable_thinking=thinking, messages=messages,
                   input_sha256=hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest())
        begin = time.perf_counter()
        content, first, reasoning_chars = [], None, 0
        try:
            with self.client.chat.completions.create(model=MODEL, messages=messages,
                temperature=0, top_p=0.95, max_tokens=max_tokens, stream=True,
                stream_options={"include_usage": True},
                extra_body={"chat_template_kwargs": {"enable_thinking": thinking}}) as stream:
                for chunk in stream:
                    if chunk.usage:
                        row["usage"] = chunk.usage.model_dump()
                    if not chunk.choices:
                        continue
                    choice = chunk.choices[0]
                    reasoning_chars += len(getattr(choice.delta, "reasoning_content", None) or "")
                    if choice.delta.content:
                        if first is None:
                            first = time.perf_counter()
                        content.append(choice.delta.content)
                    if choice.finish_reason:
                        row["finish_reason"] = choice.finish_reason
            row.update(content="".join(content), reasoning_character_count=reasoning_chars,
                       ttft_answer_ms=(first-begin)*1000 if first else None)
            if row.get("finish_reason") == "length":
                raise ValueError("Truncated response")
            row["parsed"] = parse_object(row["content"])
            return row["parsed"]
        except Exception as error:
            row["error_type"] = type(error).__name__
            return None
        finally:
            row["elapsed_ms"] = (time.perf_counter()-begin)*1000
            self.rows.append(row)
            (OUT / (label + ".json")).write_text(json.dumps(row, indent=2), encoding="utf-8")
            print(label, row.get("error_type", "ok"), round(row["elapsed_ms"], 1), "ms", flush=True)


def main():
    OUT.mkdir(exist_ok=True)
    model = AuditModel(os.environ.pop("NVIDIA_API_KEY"))
    fixture = json.loads((ROOT / "report/travel_agent_fixes_20261015_final/travel_fixture.json").read_text())
    start = time.perf_counter()
    assessments = []
    # Alternate order to reduce simple run-order confounding. Only n=1 per cell.
    for label, order in [("planner-initial", [False, True]),
                         ("planner-revised", [True, False]),
                         ("reviewer-initial", [False, True])]:
        captured = json.loads((OLD / (label + ".json")).read_text(encoding="utf-8"))
        for thinking in order:
            name = label + ("-thinking" if thinking else "-direct")
            answer = model.json(name, captured["messages"], max_tokens=5000, thinking=thinking)
            check = None
            if answer is not None and label.startswith("planner"):
                check = check_plan(answer, fixture, budget=90000 if label.endswith("initial") else 65000, walking=500)
            elif answer is not None:
                check = dict(rejects_incorrect_total=answer.get("decision")=="reject",
                             current_budget=answer.get("budget_inr")==90000,
                             current_walking=answer.get("max_walk_metres")==500,
                             # Inspect explanation separately; a reject alone does not show correct reasoning.
                             issues=answer.get("issues"))
            assessments.append(dict(label=name, checks=check))
    for label, source in [
        ("polite-change", "Please change my total trip budget to INR 65000."),
        ("two-changes", "Change my total trip budget to INR 65000 and my maximum walking distance to 50 metres.")]:
        intake = TravelIntake(model)
        try:
            claims = intake(source, dict(subject="Riya", scope={"trip_id":"goa-family"}))
            assessments.append(dict(label=label, source=source, normalized_claims=claims,
                                    normalizations=intake.normalizations))
        except Exception as error:
            assessments.append(dict(label=label, error_type=type(error).__name__))
    summary = dict(calls=len(model.rows), elapsed_seconds=time.perf_counter()-start,
                   assessments=assessments, temperature=0, top_p=0.95,
                   note="Diagnostic n=1 per cell; paired cells use identical captured prompts and max_tokens=5000. Intake uses its existing 2800-token request. No thinking text is saved.")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("Calls:", len(model.rows), "total seconds:", round(summary["elapsed_seconds"], 3), flush=True)


if __name__ == "__main__":
    main()
