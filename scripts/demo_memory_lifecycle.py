"""Exercise the implemented memory core with real embeddings and isolated data."""

# ruff: noqa: E402

import argparse
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from memory.embeddings.embedder import Embedder
from memory.engine import MemoryEngine
from memory.tool_adapter import MemoryToolAdapter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    out = args.report.resolve()
    if out.exists() or not out.is_relative_to(ROOT):
        parser.error("Choose a fresh report directory in the workspace.")
    out.mkdir(parents=True)
    (out / ".gitignore").write_text("vectors/\n", encoding="utf-8")
    name = "lifecycle_demo_" + uuid.uuid4().hex[:12]
    model = Embedder(
        use_gpu=False, cache_dir="C:/Users/User/AppData/Local/Temp/fastembed_cache"
    )
    engine = MemoryEngine(
        config={"extraction_policy": "none"},
        qdrant_path=str(out / "vectors"),
        graph_name=name,
        embedder=model,
    )
    now = int(time.time())
    events = []

    def save(mid, text, claims, at):
        engine.add(
            text,
            memory_id=mid,
            timestamp=at,
            claims=claims,
            source_info=dict(
                origin="user",
                actor_id="demo_user",
                user_confirmed=True,
                quality=0.9,
                recorded_at=at,
            ),
            metadata={"source": "explicit_demonstration_fixture"},
        )
        events.append(
            dict(memory_id=mid, claims=engine.get(mid).metadata["memory_claim_ids"])
        )
        return engine.get(mid).metadata["memory_claim_ids"]

    try:
        old = save(
            "demo_old_budget",
            "The traveller approved a maximum travel budget of 1000.",
            [dict(subject="Traveller", predicate="budget", value=1000, kind="rule")],
            now - 2 * 86400,
        )[0]
        profile = save(
            "demo_profile",
            "The traveller studies AI & Data Science, in year three, and prefers aisle seats.",
            [
                dict(
                    subject="Traveller",
                    predicate="discipline",
                    value="AI & Data Science",
                ),
                dict(subject="Traveller", predicate="study_year", value=3),
                dict(
                    subject="Traveller",
                    predicate="seat_preference",
                    value="aisle",
                    aliases=["seat preference"],
                ),
            ],
            now - 180 * 86400,
        )
        planner = MemoryToolAdapter(engine, agent_id="planner")
        reviewer = MemoryToolAdapter(engine, agent_id="reviewer")
        assert planner.call_tool(
            "record_work",
            dict(
                work_id="trip_plan",
                claim_ids=[old],
                description="Plan based on the approved budget",
            ),
        )["success"]
        assert planner.call_tool(
            "record_work",
            dict(
                work_id="seat_note",
                claim_ids=[profile[2]],
                description="Seat preference recorded",
            ),
        )["success"]
        assert planner.call_tool("complete_work", dict(work_id="seat_note"))["success"]
        new = save(
            "demo_new_budget",
            "The traveller lowered the approved maximum budget to 600.",
            [
                dict(
                    subject="Traveller",
                    predicate="budget",
                    value=600,
                    kind="rule",
                    action="supersede",
                    reason="Explicit user budget change",
                )
            ],
            now - 86400,
        )[0]
        save(
            "demo_confirm_discipline",
            "The traveller reconfirmed the AI & Data Science discipline only.",
            [
                dict(
                    subject="Traveller",
                    predicate="discipline",
                    value="AI & Data Science",
                    action="confirm",
                )
            ],
            now - 5,
        )
        accepted = engine.recall("What is the traveller's current budget?", "Traveller")
        handoff = reviewer.call_tool(
            "handoff_memory", dict(work_ids=["trip_plan", "seat_note"])
        )["result"]
        search = engine.search("Traveller budget 1000", k=5)
        save(
            "demo_employer",
            "The traveller works at Example Systems.",
            [
                dict(
                    subject="Traveller",
                    predicate="employer",
                    value="Example Systems",
                    references=["Example Systems"],
                )
            ],
            now - 10,
        )
        save(
            "demo_location",
            "Example Electrosystems is located in Pune.",
            [
                dict(
                    subject="Example Electrosystems", predicate="location", value="Pune"
                )
            ],
            now - 10,
        )
        save(
            "demo_identity",
            "Example Systems and Example Electrosystems are the same organization.",
            [
                dict(
                    subject="Example Systems",
                    predicate="same_as",
                    value="Example Electrosystems",
                    action="alias",
                )
            ],
            now - 5,
        )
        path = engine.recall_path(
            "Where is the traveller's employer located?",
            "Traveller",
            ["employer", "location"],
        )
        missing = engine.recall("What is the traveller's phone number?", "Traveller")
        proposal = planner.call_tool(
            "add_memory",
            dict(
                content="The planner proposes a conflicting budget of 900.",
                memory_id="demo_proposal",
                claims=[
                    dict(
                        subject="Traveller", predicate="budget", value=900, kind="rule"
                    )
                ],
            ),
        )
        assert proposal["success"]
        dispute = engine.recall("What is the traveller's budget?", "Traveller")
        evidence = dict(
            graph_name=name,
            real_embeddings=model.model_name,
            events=events,
            old_claim=engine.inspect_claim(old),
            new_claim=engine.inspect_claim(new),
            accepted_change_result=accepted,
            unresolved_dispute_result=dispute,
            handoff=handoff,
            missing_answer=missing,
            multi_step_answer=path,
            current_search=[r.model_dump() for r in search],
            score_at_ages={
                str(days): engine.inspect_claim(profile[2], now + days * 86400)[
                    "fuzzy_score"
                ]
                for days in [0, 30, 90, 365]
            },
            checks=dict(
                old_current_score_zero=engine.inspect_claim(old)["fuzzy_score"] == 0,
                new_protection_one=engine.inspect_claim(new)["fuzzy_score"] == 1,
                current_budget_600=accepted["evidence"][0]["value"] == 600,
                dispute_visible=dispute["answer_status"] == "disputed",
                missing_answer_explicit=missing["answer_status"] == "missing",
                alias_path_pune=path["evidence"][0]["value"] == "Pune",
                affected_plan_stale=handoff["work"][0]["work"]["status"] == "stale",
                unaffected_completed_work_retained=handoff["work"][1]["work"]["status"]
                == "completed",
                both_original_sources_retained=bool(
                    engine.get("demo_old_budget") and engine.get("demo_new_budget")
                ),
            ),
        )
        assert all(evidence["checks"].values()), evidence["checks"]
        (out / "results.json").write_text(
            json.dumps(evidence, indent=2, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
        )
        labels = [
            "Entity",
            "Observation",
            "MemoryClaim",
            "MemorySource",
            "MemoryContext",
            "MemoryField",
            "MemoryWork",
        ]
        nodes = []
        for label in labels:
            for row in engine.graph_store.execute(
                f"MATCH(n:{label}) RETURN properties(n)"
            ).rows:
                props = dict(row[0])
                node = dict(id=props["id"], type=label, properties=props)
                if label == "MemoryClaim":
                    node["state"] = engine.inspect_claim(props["id"])
                nodes.append(node)
        links = [
            dict(source=r[0], target=r[1], type=r[2], properties=dict(r[3]))
            for r in engine.graph_store.execute(
                "MATCH(a)-[r]->(b) RETURN a.id,b.id,type(r),properties(r)"
            ).rows
        ]
        (out / "graph.json").write_text(
            json.dumps(
                dict(graph_name=name, nodes=nodes, links=links),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (out / "README.md").write_text(
            "# Implemented memory demo\n\nReal FalkorDB graph and Qdrant vectors; explicit fixture claims and real BGE embeddings. This is not automatic extraction or a production user profile.\n\n"
            + f"Persisted graph: `{name}`. Open [results](results.json) for the checked behavior and [actual graph export](graph.json) for all stored nodes/edges.\n\n"
            + "Protected 1000 → accepted 600 preserves both versions; the former score is zero and the current protected score is one. A later unaccepted 900 proposal creates a dispute without taking protection. Only the affected plan requires review; the completed seat note remains completed. Missing phone information is explicit, and an employer → accepted organization alias → location path returns Pune.\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                dict(
                    report=str(out),
                    graph=name,
                    checks=evidence["checks"],
                    nodes=len(nodes),
                    edges=len(links),
                )
            ),
            flush=True,
        )
    finally:
        engine.close()


if __name__ == "__main__":
    main()
