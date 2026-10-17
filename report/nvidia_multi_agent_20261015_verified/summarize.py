"""Build a report from captured responses; never rerun or rewrite model output."""

import csv
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from examples.nvidia_memory_agents import check_plan, offer_catalog
from falkordb import FalkorDB

OUT = Path(__file__).resolve().parent


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    result, storage, calls, corpus, decisions, fuzzy = [read(name) for name in (
        "results.json", "storage.json", "model-latency.json", "ingestion.json", "decisions.json", "fuzzy-results.json")]
    fixture = read("travel_fixture.json")
    previous = {}
    corrected = {}
    for label, budget, walking in [("planner-initial",90000,500), ("planner-revised",65000,500), ("planner-no-suitable-hotel",65000,50)]:
        previous[label] = read("agents/"+label+"-oracle.json")
        corrected[label] = check_plan(decisions[label], fixture, budget=budget, walking=walking)
        save("agents/"+label+"-oracle.json", corrected[label])
    if not (OUT / "oracle-before-date-boundary-correction.json").exists():
        save("oracle-before-date-boundary-correction.json", previous)
    assert all(all(corrected[label].values()) == result["checks"][label+"_all_constraints"] for label in corrected)
    memory_checks = {k:v for k,v in result["checks"].items() if not k.startswith(("planner-","reviewer-")) and k not in {
        "initial_reviewer_agrees_with_oracle", "revised_reviewer_agrees_with_oracle", "reviewer_rejects_injected_bad_plan", "both_agents_stop_when_no_hotel_fits"}}
    # Reviewer negative control is an agent behavior check despite its prefix.
    agent_checks = {k:v for k,v in result["checks"].items() if k not in memory_checks}
    ttfts = [r["ttft_ms"] for r in calls if r.get("ttft_ms") is not None]
    usage = {key:sum((r.get("usage") or {}).get(key,0) or 0 for r in calls) for key in ("prompt_tokens","completion_tokens","total_tokens")}
    cached = sum(((r.get("usage") or {}).get("prompt_tokens_details") or {}).get("cached_tokens",0) or 0 for r in calls)
    attempts = []
    for folder, note in [
        ("nvidia_multi_agent_20261015", "Stopped: preference/rule and capitalization conflict"),
        ("nvidia_multi_agent_20261015_normalized", "Completed diagnostic; catalog accidentally exposed future budget, excluded from final agent assessment"),
        ("nvidia_multi_agent_20261015_final", "Stopped: model emitted description text in kind enum"),
        ("nvidia_multi_agent_20261015_evaluated", "Stopped: model invented a hotel supersession with no target"),
        ("nvidia_multi_agent_20261015_verified", "Completed supplier-only, schema-guarded controlled run")]:
        data=json.loads((ROOT/"report"/folder/"results.json").read_text())
        attempts.append(dict(folder=folder, note=note, elapsed_s=data["elapsed_ms"]/1000, calls=data["model_calls"]))
    s = storage["after_full_scenario"]
    private=ROOT/"data/nvidia_memory_runs"/result["run_id"]
    client=FalkorDB(host="127.0.0.1",port=6379)
    try:
        native=client.connection.execute_command("GRAPH.MEMORY", "USAGE", s["tier3"]["graph"])
    finally:
        client.close()
    save("native-graph-memory.json", dict(raw=native, note="This server reports integer MB fields (all zero for this small graph). Generic Redis MEMORY USAGE returned 64 bytes for the key wrapper, not graph contents. Exact per-graph physical bytes are unresolved; use the separately labelled serialized logical size and counts."))
    closed_files={str(p.relative_to(private)):p.stat().st_size for p in private.rglob("*") if p.is_file()}
    save("closed-runtime-files.json", closed_files)
    metadata=read("metadata-sample.json")
    cards=read("contexts/initial.json")["cards"]
    (OUT/"persona-cards").mkdir(exist_ok=True)
    for card in cards:
        (OUT/"persona-cards"/(card["card_id"]+".md")).write_text(card["text"],encoding="utf-8")
    empty_events = all(not card.get("source_event_ids") for card in cards)
    summary=dict(memory_checks=dict(passed=sum(memory_checks.values()),total=len(memory_checks)),
        agent_checks=dict(passed=sum(agent_checks.values()),total=len(agent_checks)),
        failed_checks=[k for k,v in result["checks"].items() if not v],
        provider_ttft_p50_ms=statistics.median(ttfts),provider_usage=usage,provider_cached_prompt_tokens=cached,
        all_attempts=attempts,all_attempts_elapsed_s=sum(a["elapsed_s"] for a in attempts),
        all_attempts_model_calls=sum(a["calls"] for a in attempts),card_source_event_ids_empty=empty_events,
        corrected_oracle_note="Arrival-day activity is allowed; corrected inclusive date boundary. Model responses unchanged; all four aggregate failures unchanged.",
        actual_cost_of_selected_initial_and_revised_offers_inr=72600,
        compliant_alternative_cost_inr=58600)
    save("analysis.json", summary)
    save("runner-hashes.json", {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in [
        "examples/nvidia_memory_agents.py","scripts/evaluate_nvidia_memory.py","tests/test_nvidia_memory_evaluation.py"]})
    for name, rows in [("checks.csv", [dict(check=k,passed=v) for k,v in result["checks"].items()]),
                       ("model-latency.csv", [dict(label=r["label"],ttft_ms=r.get("ttft_ms"),elapsed_ms=r["elapsed_ms"],prompt_tokens=(r.get("usage") or {}).get("prompt_tokens"),completion_tokens=(r.get("usage") or {}).get("completion_tokens")) for r in calls])]:
        with (OUT/name).open("w",newline="",encoding="utf-8") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    m = result["memory_benchmarks"]
    w = storage["after_intake_and_cache_warm"]
    lines = [
        "# Live NVIDIA multi-agent memory evaluation — 15 October 2026", "",
        "**Memory state handling passed the tested controls; the complete agent system is not reliable enough to approve travel plans.** Real NVIDIA model responses still contained arithmetic, budget-use and review errors. This replaces the earlier assistant roleplay with actual hosted inference.", "",
        f"The final controlled run took **{result['elapsed_ms']/1000:.2f} seconds**, including local setup, API calls, memory benchmarks and restart checks. It made **{len(calls)} model calls**: 8 intake calls and 7 calls across two distinct planner/reviewer roles using `{result['model']}`. The same model weights serve both roles. There were **{sum(memory_checks.values())}/{len(memory_checks)} automated memory checks** and **{sum(agent_checks.values())}/{len(agent_checks)} agent/output checks** passing: **46/50 combined checks**, not a statistical accuracy estimate. One further metadata gap was found by inspection.", "",
        "## Measured time", "", "| Operation | Median | p95 | Samples |", "| --- | ---: | ---: | ---: |",
        f"| Build context without RAM reuse, CPU cards | {m['uncached_cpu']['warm']['p50_ms']:.1f} ms | {m['uncached_cpu']['warm']['p95_ms']:.1f} ms | 12 |",
        f"| Warm context, CPU cards | {m['ram_cpu']['warm']['p50_ms']:.1f} ms | {m['ram_cpu']['warm']['p95_ms']:.1f} ms | 12 |",
        f"| Warm context, CUDA cards | {m['ram_gpu']['warm']['p50_ms']:.1f} ms | {m['ram_gpu']['warm']['p95_ms']:.1f} ms | 12 |",
        f"| NVIDIA complete response, all call roles | {result['model_latency']['p50_ms']/1000:.2f} s | {result['model_latency']['p95_ms']/1000:.2f} s | 15 |",
        f"| Save ingestion receipt | {result['local_http_latency']['/v1/events']['p50_ms']:.1f} ms | {result['local_http_latency']['/v1/events']['p95_ms']:.1f} ms | 8 |",
        f"| Validate current context proof | {result['local_http_latency']['/v1/context/validate']['p50_ms']:.1f} ms | {result['local_http_latency']['/v1/context/validate']['p95_ms']:.1f} ms | 9 |", "",
        f"Median NVIDIA time to first visible token: **{statistics.median(ttfts):.1f} ms**. Local startup: **{result['initialization_ms']/1000:.2f} s**. Hybrid search: **{m['hybrid_search_single_ms']:.1f} ms**, one sample. Sum of remote call durations: **{result['sum_model_call_ms']/1000:.2f} s**. Receipt acknowledgment is not completed interpretation; intake-ready times below include the hosted interpretation and durable write.", "",
        f"The same prompt and evidence were checked across all three context modes. RAM reuse reduced local median preparation time by about **{m['uncached_cpu']['warm']['p50_ms']/m['ram_cpu']['warm']['p50_ms']:.1f}×** in this small run. GPU matching did not beat CPU for the two-card catalog. First GPU-mode context after resetting its adapter took {m['ram_gpu']['first_ms']:.1f} ms. These sequential 12-sample runs are descriptive, not a load benchmark.", "",
        f"Provider usage: **{usage['prompt_tokens']} input + {usage['completion_tokens']} output = {usage['total_tokens']} tokens**; provider-reported cached input tokens: **{cached}**. Our RAM cache avoids rebuilding the brief; it does **not** avoid sending that brief to NVIDIA. Local counts use NVIDIA's official matching tokenizer; provider counts additionally include complete role instructions, supplier catalog and chat formatting. The model disables thinking for this evaluation; reported reasoning-token counts were zero.", "",
        "## Data stored in each tier", "", "These are overlapping representations, not three disjoint partitions. Bytes are exact for the stated serialization/tensor/file measurement, not total machine memory.", "",
        "| Tier | After initial ingestion and warming | At end of the scenario |", "| --- | --- | --- |",
        f"| 1: accounted RAM cache payload | {w['tier1']['accounted_ram_payload_bytes']:,} B, {w['tier1']['cache_entries']} cached contexts | {s['tier1']['accounted_ram_payload_bytes']:,} B, {s['tier1']['cache_entries']} contexts |",
        f"| 1: agent/traveller hot text within it | {w['tier1']['agent_text_utf8_bytes']:,} / {w['tier1']['traveller_text_utf8_bytes']:,} B | {s['tier1']['agent_text_utf8_bytes']:,} / {s['tier1']['traveller_text_utf8_bytes']:,} B |",
        f"| 2: unique cached Markdown card text | {w['tier2']['cached_card_text_utf8_bytes']:,} B, {w['tier2']['unique_cached_cards']} card versions | {s['tier2']['cached_card_text_utf8_bytes']:,} B, {s['tier2']['unique_cached_cards']} versions |",
        "| 2: active CUDA card vectors | **3,072 B**, 2 × 384 float32 dimensions | **3,072 B**, 2 active cards |",
        f"| 3: graph logical JSON size | {w['tier3']['graph_serialized_logical_bytes']:,} B; {w['tier3']['node_total']} nodes, {w['tier3']['edge_total']} edges | {s['tier3']['graph_serialized_logical_bytes']:,} B; {s['tier3']['node_total']} nodes, {s['tier3']['edge_total']} edges |",
        f"| 3: vectors | {w['tier3']['vector_count']} vectors, {w['tier3']['raw_vector_float32_bytes']:,} B raw | {s['tier3']['vector_count']} vectors, {s['tier3']['raw_vector_float32_bytes']:,} B raw |",
        f"| 3: vector payload JSON | {w['tier3']['vector_payload_json_bytes']:,} B | {s['tier3']['vector_payload_json_bytes']:,} B |",
        f"| 3: Qdrant files, primary user | {w['tier3']['qdrant_directory_bytes']:,} B | {s['tier3']['qdrant_directory_bytes']:,} B |",
        f"| Auxiliary SQLite journal, while open | {sum(w['tier3']['journal_files_bytes'].values()):,} B incl. WAL/shared-memory files | {sum(s['tier3']['journal_files_bytes'].values()):,} B incl. WAL/shared-memory files |", "",
        f"The final graph contains **8 source records, 27 claims, 3 scopes, 17 field definitions and 2 work records**. Entire closed local runtime files occupied **{result['physical_disk_after_close_bytes']:,} B**, including the empty second-user isolation control; this excludes the graph hosted in Docker. The SQLite WAL is checkpointed on close, so open-file totals cannot be added to the closed-runtime total.", "",
        f"The ordinary process working set reached approximately **{s['process_peak_working_set_bytes']/1024/1024:.1f} MiB**, far larger than the cache payload because Python, the official tokenizer, local BGE encoder, ONNX/CUDA libraries and clients also consume memory. Tier 2 retains a 3,072 B CPU fallback matrix; peak owned card/query/result tensors were 4,616 B. CUDA provider/context overhead is separate. The 32 MiB provider arena value is a configured limit, not a measured allocation.", "",
        "Card text remains in host RAM; CUDA holds its matching vectors, not Markdown files, model weights or a generative KV cache. RAM payload accounting includes card/field copies, so adding its total to card-text totals double-counts data. The final RAM counts include the empty second-user context used for isolation testing.", "",
        "FalkorDB's native memory command reported integer MB values of zero for this tiny graph; the generic Redis key counter reported a 64 B wrapper. Neither establishes that the graph occupies zero/64 B. Its exact physical footprint remains unresolved; the table deliberately reports logical serialized size and object counts. [Native counter evidence](native-graph-memory.json), [all snapshots](storage.json), [closed files](closed-runtime-files.json).", "",
        "## What was ingested", "",
        f"**{len(corpus)} raw source messages, {result['ingested_source_utf8_bytes']} UTF-8 bytes, produced {result['interpreted_claims']} atomic claims.** Every message used `/v1/events` with text, authenticated actor, subject and scope. No caller chose a memory tier or directly wrote cache/persona files.", "",
        "| Message | Scope/actor | Claims | Saved receipt | Ready, incl. model |", "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in corpus:
        lines.append(f"| {row['event_id']} | `{row['scope']}` / {row['actor']} | {len(row['interpreted_claims'])} | {row['receipt_ms']:.1f} ms | {row['ready_ms']/1000:.2f} s |")
    lines += ["", "Messages covered usual vegetarian/active/aisle/interests preferences; the Goa dates, two adults, Delhi departure, INR 90,000 cap, step-free access, 500 m walking, no boats, morning flights and one activity per day; explicit relaxed mood; budget reduction to 65,000; walking reduction to 50 m; a separate Bengaluru trip; and two agents repeating the user's aisle preference. [Exact text and normalized claims](ingestion.json).", "",
        f"The fictional supplier offers/prices are external per-call task data, **not ingested semantic memory**. Their compact catalog contains {len(json.dumps(offer_catalog(fixture)).encode()):,} B of JSON. Expected future budgets and test answers were excluded from the final agent prompts. [Fixture](travel_fixture.json), [complete captured model requests/responses](model-latency.json).", "",
        "## How automatic routing and persona construction work", "",
        "1. The application supplies authenticated identity, subject and explicit trip/profile scope. It does not infer identity or trust from prose. Nemotron extracts named travel values; a small application schema supplies permitted field types and source-grounded change actions. This schema and its canonical labels are configured, not learned.",
        "2. **Tier 3 receives every retained source and claim first.** Each message gets a 384-dimensional BGE vector. The graph keeps facts, protection, changes, scopes, sources and work dependencies. The SQLite journal tracks whether interpretation is ready.",
        "3. **Tier 1 is built on request.** Up to 1,024 tokens describe the authenticated agent role; another 1,024 hold required trip fields and saved rules, then optional important preferences if they fit. Missing/conflicting hard requirements block readiness. General preferences inherit only through the configured scope rules.",
        "4. **Tier 2 is a derivative view.** Configured task templates render evidence-backed Markdown from current fields. Explicit relaxed mood admits the relaxed template; it is not a psychological inference. The system embeds eligible card text and ranks it using the request, with up to three selected cards. Reads do not renew the source mood's expiry. [Actual relaxed card](persona-cards/relaxed.md), [itinerary card](persona-cards/itinerary_details.md).",
        "5. Source/configuration/time changes invalidate derivatives and old context proofs. Restart emptied the volatile tiers and rebuilt them from retained tier-3 data. There is no exclusive 'move this fact to cache and remove it from storage' operation.", "",
        "**Fuzzy scoring does not currently choose cache tiers.** Tier inclusion follows field importance, rule status, scope, task templates and token budgets. Fuzzy scoring contributes reliability/ranking within the durable memory layer. Persona/role/template definitions are application-owned; free-form input alone does not invent new specialist agents or card types.", "",
        "## Fuzzy logic results", "", "| Control | Score |", "| --- | ---: |",
        f"| Actual current aisle preference | {fuzzy['actual_before']['fuzzy_score']:.6f} |",
        f"| After both agents repeated it | {fuzzy['actual_after_agent_repetition']['fuzzy_score']:.6f} |",
    ]
    for row in fuzzy["actual_time_controls"]:
        lines.append(f"| Same ordinary preference at +{row['days']} days | {row['fuzzy_score']:.6f} |")
    for name,row in fuzzy["mathematical_controls"].items():
        lines.append(f"| Mathematical control: {name} | {row['score']:.6f} |")
    lines += ["| Current user-confirmed budget rule | 1.000000 |", "| Superseded budget | 0.000000 |", "",
        "Ordinary scores blend freshness, source quality, independent support and disagreement using overlapping low/medium/high memberships. Time then reduces ordinary relevance. Agents repeating one source did not count as independent corroboration; the tiny score difference above is elapsed time. Confirmed protected rules bypass decay while current, and superseded versions cannot become current through a high score. Scores are **not calibrated probabilities**. The day and source-quality comparisons are controlled calculations, not days of elapsed observation or additional real independent witnesses. [Full membership and fired-rule traces](fuzzy-results.json).", "",
        "## Agent behavior and problems", "",
        "| Stage | Actual model response | Independent finding |", "| --- | --- | --- |",
        "| Initial plan | Comfort flight + resort; claimed total **INR 76,600**, cap 90,000 | Correct selected-offer total is **72,600**. The model added its own numbers incorrectly. Both activity dates are distinct and inside the trip; the evaluator's original arrival-day exclusion was corrected. |",
        "| Initial reviewer | Rejected, but returned `budget_inr: 76600` | It confused the candidate total with the saved **90,000** cap, even though the current memory contained 90,000. Its detailed comments repeatedly called items compliant despite the reject decision. |",
        "| Revised plan | Read the new **65,000** cap but retained comfort + resort; claimed **79,000** and admitted exceeding the cap | Actual selected cost is still **72,600**, over budget. A compliant fixture alternative exists at **58,600**. Good memory retrieval did not force the model to obey the constraint. |",
        "| Revised reviewer / deliberately bad control | Rejected both | It caught the overspend and rejected a deliberately injected late-flight/stairs/boat candidate. Some explanations still repeated bad arithmetic or invented additional walking concerns. |",
        "| 50 m walking limit | Planner paused with no supplier IDs; reviewer said reject | Both read 50 m and stopped approving travel. The reviewer failed the requested `pause` response classification. Both repeated an invented 'morning means before 09:00' reason; the real reason to pause is that all hotels require at least 80 m walking. |", "",
        "The memory controls passed: relevant pending changes blocked reads; accepted budget changes revoked old proofs and marked completed work for review; context-only work detected the later walking change; unrelated trips remained warm/current; another user saw no trip data; source recall/search and cold reconstruction worked; GPU/CPU modes returned the same evidence. All seven responses cited existing claim IDs, but this check does not establish that every relevant claim was cited or obeyed.", "",
        "Work records in this evaluation were deliberately registered/completed by the runner to probe version/dependency behavior, using the complete context-provided claim list. **A completed work status validates ownership/evidence state, not travel arithmetic or feasibility.** The real agents did not successfully produce an approved compliant revised plan. No itinerary was executed.", "",
        "### Intake and provenance gaps", "",
        "Unrestricted model extraction was not reliable by itself. Earlier attempts promoted a preference to a rule, produced case-only value differences, copied descriptions into enum fields and invented a supersession with no active target. The core rejected these cases without partially applying them. The final intake adapter adds deterministic canonical types, removes empty extracted values, keeps usual preferences distinct from hard rules, and allows budget/walking supersession only when grounded in an explicit change request. This is a bounded travel adapter, not general automatic understanding. [Normalization log](intake-normalizations.json).", "",
        "The actual card metadata has **empty `source_event_ids` arrays**. Claim IDs still resolve to graph sources, and the receipt ID is retained inside the source's `metadata_json.service_receipt`, so source evidence was not lost. The convenient direct card-to-event list is missing and needs a follow-up core fix. This evaluation did not modify the memory core.", "",
        "## Metadata actually retained", "",
        "| Location | Examples from this run |", "| --- | --- |",
        "| Source | source/memory IDs, original text, user/agent origin, actor ID, confirmation, source quality, evidence group, recorded/received timestamps, immutable digest, receipt/interpreter/session metadata |",
        "| Claim | predicate/value, fact/preference/rule kind, subject and exact scope, source/group IDs, validity, accepted/protected flags, action/reason, half-life, score at creation, replacement/end metadata and references |",
        "| Vector payload | original source text, timestamps, entity IDs, importance, claim/source IDs, versioned-memory and extraction markers |",
        "| Cached fields/cards | current status, value, exact claim IDs, scope/location, required/hot flags, template version, mood/task tags, generation/expiry, tokenizer identity and token counts; direct source-event lists currently empty |",
        "| Work/journal | cited versions, prerequisite IDs, owner/lease and completion/review state; durable event receipt, queue status, attempts, prepared interpretation and errors |", "",
        "Current fuzzy score, memberships and fired rules are computed on read; they are not all stored as independent permanent facts. Context/lease credentials are redacted in public artifacts. The supplied NVIDIA key was held only in process memory/environment and was not written to report or source files. [Actual metadata sample](metadata-sample.json).", "",
        "## All attempts and reproducibility", "", "| Attempt | Time | Model calls | Disposition |", "| --- | ---: | ---: | --- |",
    ]
    for attempt in attempts:
        lines.append(f"| [{attempt['folder']}](../{attempt['folder']}/results.json) | {attempt['elapsed_s']:.2f} s | {attempt['calls']} | {attempt['note']} |")
    lines += ["", f"Total measured execution across these five attempts: **{sum(a['elapsed_s'] for a in attempts):.2f} s**, **{sum(a['calls'] for a in attempts)} model calls**. This excludes coding, tokenizer downloads, model-list probes and offline test time. None of the failed or contaminated runs is counted as a successful controlled agent run.", "",
        "The first catalog probe found the older Mistral endpoint listed but inaccessible for this account; Nemotron's endpoint worked. The final run uses NVIDIA's official 17.1 MB tokenizer and config. An earlier Mistral tokenizer was also downloaded during model selection; no hosted-model weights were downloaded. [NVIDIA API reference](https://docs.api.nvidia.com/nim/reference/llm-apis), [official model/tokenizer](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16). The tokenizer's SHA-256 is recorded in `results.json.consumer_tokenizer`.", "",
        "Implementation: [small agent classes](../../examples/nvidia_memory_agents.py), [runner](../../scripts/evaluate_nvidia_memory.py), [offline evaluator tests](../../tests/test_nvidia_memory_evaluation.py). The final evaluator/context contract check passed **23 tests**; Ruff passed for new source/tests. [JUnit](evaluator_tests.xml). Original source/core hashes are retained; no `memory/` module changed during this request. The date-boundary correction only re-evaluated captured responses; it did not rerun or repair model answers and did not change the aggregate 46/50 result.", "",
        "```powershell", "$env:NVIDIA_API_KEY = <set privately in your process>", "$env:PYTHONPATH = <your compatible CUDA/ONNX runtime paths>", "& '.\\.venv\\Scripts\\python.exe' scripts/evaluate_nvidia_memory.py --report report/FRESH_RUN --tokenizer PATH_TO_OFFICIAL_TOKENIZER --gpu", "```", "",
        "The local service has been stopped; isolated graph/vector evidence remains. Model responses, raw latency samples, storage snapshots, corpus, fuzzy traces and failures are all retained in this directory. This was a single synthetic scenario, same-model agents, sequential calls, explicit orchestration and a deliberately small catalog. Larger workloads, autonomous tool selection and production answer reliability were not established.", "",
        "[Machine-readable results](results.json) · [analysis](analysis.json) · [all checks](checks.csv) · [model timings](model-latency.csv) · [full local API transcript](http-transcript.json)",
    ]
    (OUT/"README.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__ == "__main__":
    main()
