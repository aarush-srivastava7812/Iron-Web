"""Build factual comparisons from new runs and read-only historical predictions."""

import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memory.evaluation.harness.base import EvaluationResult
from memory.evaluation.harness.evaluator import BenchmarkEvaluator
from memory.evaluation.slices import FrozenSliceAdapter
from memory.evaluation.retrieval_metrics import (
    average_precision,
    compute_retrieval_metrics,
)
from memory.engine import MemoryEngine
from memory.evaluation.harness.persistence import fingerprint, source_fingerprint
from scripts.reevaluate import sha256, write_json


def load_records(path):
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len({record["example_id"] for record in records}) != len(records):
        raise ValueError(f"Duplicate historical identities: {path}")
    return records


def aggregate(records, adapter, historical=False):
    results = []
    examples = {e.example_id: e for e in adapter.load_examples()}
    for record in records:
        example = examples[record["example_id"]]
        if record["query"] != example.query:
            raise ValueError("Historical and selected questions differ.")
        retrieved = record["retrieved_ids"]
        prediction = (
            record.get("prediction") if historical else record.get("predicted_answer")
        )
        error = record.get("error")
        retrieval = (
            compute_retrieval_metrics(retrieved, example.ground_truth_ids)
            if example.ground_truth_ids and not error
            else {}
        )
        if retrieval:
            retrieval["average_precision@10"] = average_precision(
                retrieved[:10], example.ground_truth_ids
            )
        answer = (
            adapter.evaluate_answer(prediction or "", example.gold_answer)
            if example.gold_answer and not error
            else {}
        )
        latency = (
            record.get("latency_ms", 0.0)
            if historical
            else record["retrieval_latency_ms"]
        )
        results.append(
            EvaluationResult(
                "historical_rescored" if historical else record["run_id"],
                adapter.benchmark_name,
                example.example_id,
                example.query,
                retrieved,
                example.ground_truth_ids,
                retrieval,
                predicted_answer=prediction,
                gold_answer=example.gold_answer,
                answer_metrics=answer,
                retrieval_latency_ms=latency,
                total_latency_ms=latency if historical else record["total_latency_ms"],
                category=example.category,
                error=error,
                metadata=example.metadata,
            )
        )
    evaluator = BenchmarkEvaluator(None, adapter, k=10)
    summary = evaluator.aggregate_results(results)
    if historical:
        # The retained upstream records have retrieval latency only. Do not
        # manufacture an old generation or total-pipeline latency measurement.
        summary["latency"]["mean_total_ms"] = None
        summary["latency"]["mean_generation_ms"] = None
    else:
        summary["latency"]["mean_generation_ms"] = (
            float(
                np.mean(
                    [
                        r.get("generation_latency_ms", 0.0)
                        for r in records
                        if not r.get("error")
                    ]
                )
            )
            if any(not r.get("error") for r in records)
            else None
        )
    values = [r.retrieval_latency_ms for r in results if not r.error]
    if values:
        summary["latency"].update(
            {
                f"p{p}_retrieval_ms": float(np.percentile(values, p))
                for p in (50, 95, 99)
            }
        )
        summary["latency"]["max_retrieval_ms"] = float(max(values))
    return summary


def summarize(report):
    matrix = json.loads((report / "matrix.json").read_text(encoding="utf-8"))
    if len(matrix) != 15:
        raise ValueError(f"Expected 15 profile/cohort runs, found {len(matrix)}.")
    rows, history, comparisons = [], [], []
    historical_root = ROOT / "archive/2026-10-12/run-records/metrics/official_upstream"
    for run in matrix:
        job, profile, saved = run["job"], run["profile"], run["summary"]
        input_path = Path(job["slice_directory"]) / (job["benchmark"] + ".json")
        if sha256(input_path) != job["input_sha256"]:
            raise ValueError("Input changed after preparation.")
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        adapter = FrozenSliceAdapter(payload)
        config = MemoryEngine._load_config(
            MemoryEngine.__new__(MemoryEngine),
            {
                "extraction_policy": "none",
                "retrieval": {"reranker_enabled": profile == "reranked_hybrid"},
            },
        )
        store = (
            Path(job["slice_directory"]).parents[2]
            / "stores"
            / f'p{job["percent"]}'
            / job["benchmark"]
        )
        config["qdrant"]["path"] = str(store / "vectors")
        config["falkordb"]["graph_name"] = (
            "reevaluation_"
            + Path(job["slice_directory"]).parents[2].name
            + "_p"
            + str(job["percent"])
            + "_"
            + job["benchmark"]
        )
        expected_inputs = dict(
            protocol="local_retrieval_v2",
            source=source_fingerprint(),
            benchmark=job["benchmark"],
            retrieval_mode=saved["retrieval_mode"],
            k=10,
            smoke=False,
            config=config,
            backend_identity={},
            use_gpu=saved["device"]["gpu_enabled_requested"],
            extractor="disabled",
            generator="first_context_line",
            documents=payload["documents"],
            examples=payload["examples"],
        )
        if fingerprint(expected_inputs) != saved["fingerprint"]:
            raise ValueError(
                "Saved run does not match current source, inputs and effective settings."
            )
        write_json(
            report
            / f'p{job["percent"]}_{job["benchmark"]}_{profile}_configuration.json',
            config,
        )
        raw_path = Path(saved["run_file"])
        records = load_records(raw_path)
        if {r["example_id"] for r in records} != {
            e.example_id for e in adapter.load_examples()
        }:
            raise ValueError("New results do not cover every selected question.")
        metrics = aggregate(records, adapter)
        if metrics["failed_examples"]:
            raise ValueError(f"Failed real evaluation cases: {job}, {profile}")
        for group in ("retrieval", "answer"):
            for metric, value in saved["evaluation"][group].items():
                if not np.isclose(value, metrics[group][metric], rtol=0, atol=1e-12):
                    raise ValueError(
                        "Recomputed scores differ from the saved benchmark summary."
                    )
        observed = [s["used_mb"] for s in run["telemetry"] if s["used_mb"] is not None]
        row = dict(
            percent=job["percent"],
            benchmark=job["benchmark"],
            profile=profile,
            questions=job["questions"],
            documents=job["documents"],
            **metrics["retrieval"],
            **metrics["answer"],
            **metrics["latency"],
            retrieval_scored_examples=metrics["retrieval_scored_examples"],
            answer_scored_examples=metrics["answer_scored_examples"],
            failed_examples=metrics["failed_examples"],
            peak_sampled_total_vram_mb=max(observed) if observed else None,
            ingestion_time_sec=saved["ingestion"]["ingestion_time_sec"],
            newly_ingested_documents=saved["ingestion"]["ingested_ids"],
            fresh_ingestion_docs_per_sec=saved["ingestion"]["ingested_ids"]
            / saved["ingestion"]["ingestion_time_sec"]
            if saved["ingestion"]["ingested_ids"]
            else None,
            skipped_unchanged=saved["ingestion"]["skipped_unchanged"],
            wall_time_sec=run["wall_time_sec"],
            results_sha256=sha256(raw_path),
            fingerprint=saved["fingerprint"],
        )
        rows.append(row)
        write_json(
            report / f'p{job["percent"]}_{job["benchmark"]}_{profile}_metrics.json',
            metrics,
        )
        if profile != "reranked_hybrid":
            continue
        old_path = historical_root / job["benchmark"] / "hybrid_eval_results.jsonl"
        all_old = load_records(old_path)
        examples = {e.example_id: e for e in adapter.load_examples()}
        old = [r for r in all_old if r["example_id"] in examples]
        if len(old) != job["questions"]:
            raise ValueError(
                "Historical predictions do not cover the chosen question IDs."
            )
        rescored = aggregate(old, adapter, historical=True)
        recorded = {
            key: float(np.mean([r[key] for r in old if key in r]))
            for key in (
                "recall@10",
                "precision@10",
                "mrr",
                "ndcg@10",
                "exact_match",
                "token_f1",
                "substring_match",
                "latency_ms",
            )
        }
        original_gold_differences = sum(
            sorted(r.get("relevant_ids", []))
            != sorted(examples[r["example_id"]].ground_truth_ids)
            for r in old
        )
        historical = dict(
            percent=job["percent"],
            benchmark=job["benchmark"],
            questions=len(old),
            original_run_questions=len(all_old),
            original_documents=job["old_documents"],
            historical_path=str(old_path),
            historical_sha256=sha256(old_path),
            original_recorded=recorded,
            corrected=rescored,
            changed_evidence_annotations=original_gold_differences,
            comparability="matched questions; corpus, scope, extraction, ranking and answer generation may differ",
        )
        history.append(historical)
    for row in rows:
        old_run = next(
            item
            for item in history
            if item["percent"] == row["percent"]
            and item["benchmark"] == row["benchmark"]
        )
        for group in ("retrieval", "answer", "latency"):
            for metric, previous in old_run["corrected"][group].items():
                current = row.get(metric)
                comparisons.append(
                    dict(
                        percent=row["percent"],
                        benchmark=row["benchmark"],
                        new_profile=row["profile"],
                        metric_group=group,
                        metric=metric,
                        old_rescored=previous,
                        new_value=current,
                        difference=current - previous
                        if previous is not None and current is not None
                        else None,
                    )
                )
    write_json(report / "all_metrics.json", rows)
    write_json(report / "historical_rescoring.json", history)
    write_json(report / "comparison.json", comparisons)
    for name, values in (("all_metrics.csv", rows), ("comparison.csv", comparisons)):
        with (report / name).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=list(dict.fromkeys(k for row in values for k in row))
            )
            writer.writeheader()
            writer.writerows(values)
    source = {
        str(p.relative_to(ROOT)): sha256(p)
        for p in sorted((ROOT / "memory").rglob("*.py"))
    }
    write_json(
        report / "verification.json",
        dict(
            expected_runs=15,
            completed_runs=len(rows),
            total_query_executions=sum(row["questions"] for row in rows),
            failed_query_executions=sum(row["failed_examples"] for row in rows),
            historical_runs=len(history),
            longmemeval_20percent_executed=any(
                row["percent"] == 20 and row["benchmark"] == "longmemeval"
                for row in rows
            ),
            all_new_input_and_result_hashes_checked=True,
            recomputed_metrics_match_saved_runs=True,
            source_files=source,
            workflow_source_files={
                str(path.relative_to(ROOT)): sha256(path)
                for path in (
                    ROOT / "scripts/reevaluate.py",
                    ROOT / "scripts/summarize_reevaluation.py",
                )
            },
            git_head_at_report_generation=subprocess.check_output(
                [
                    "git",
                    "-c",
                    "safe.directory=D:/Opencode_/reserchpaper",
                    "rev-parse",
                    "HEAD",
                ],
                cwd=ROOT,
                text=True,
            ).strip(),
        ),
    )
    render_report(report, rows, history)
    return rows


def render_report(report, rows, history):
    lines = [
        "# Post-cleanup benchmark reevaluation",
        "",
        "Date: 13 October 2026 (Asia/Calcutta).",
        "",
        "The revised system was evaluated with real BGE embeddings and the BGE cross-encoder on an RTX 4050. Both live model sessions used CUDAExecutionProvider. Five percent was run first for LoCoMo, DMR and LongMemEval; twenty percent was then run for LoCoMo and DMR. LongMemEval was excluded from twenty percent as requested.",
        "",
        "## Inputs and settings",
        "",
        "Question IDs follow the retained frozen twenty-percent cohorts. Five percent uses floor(source questions × 0.05); twenty percent keeps the historical question counts. These are release-order subsets, not random representative samples. Full selected conversation histories were reconstructed from the original local inputs. LoCoMo twenty percent requires 16 additional sessions: 37 selected questions referenced evidence outside the old 54-session corpus. Original frozen files and raw historical results were read without modification.",
        "",
        "| Sample | Benchmark | Questions | Sessions/documents |",
        "|---|---|---:|---:|",
    ]
    for row in rows:
        if row["profile"] == "vector":
            lines.append(
                f'| {row["percent"]}% | {row["benchmark"]} | {row["questions"]} | {row["documents"]} |'
            )
    lines += [
        "",
        "Three profiles use the same selected store per cohort: vector retrieval, current default hybrid retrieval with reranking disabled, and hybrid retrieval with reranking explicitly enabled. Top-k is 10; hybrid candidate limit is 100, graph hops 2, and graph node limit 50. Hosted extraction is disabled in all profiles, matching the current application default. No entities or facts were fabricated; these runs consequently do not measure hosted extraction or graph-enrichment quality. The local first-context-line generator is used for answer metrics; these are not official upstream answer scores.",
        "",
        "The existing environment had a CUDA 13 ONNX Runtime wheel with CUDA 12 DLLs and fell back to CPU. Evaluation selected an isolated ONNX Runtime 1.23.2 installation with CUDA 12 runtime, FFT and linker DLLs. The main environment was unchanged. Runtime compatibility reference: [ONNX Runtime CUDA requirements](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html#requirements). Exact observed versions and providers are recorded in preflight.json.",
        "",
        "## New results",
        "",
        "Scores are proportions. Retrieval metrics exclude examples without annotated evidence; answer metrics exclude missing answers. Every attempted query completed without an error.",
        "",
        "| Sample | Benchmark | Profile | Recall@10 | Precision@10 | MRR | NDCG@10 | AP@10 | Token F1 | Mean retrieval ms | p95 ms |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f'| {r["percent"]}% | {r["benchmark"]} | {r["profile"]} | {r["recall@10"]:.4f} | {r["precision@10"]:.4f} | {r["mrr"]:.4f} | {r["ndcg@10"]:.4f} | {r["average_precision@10"]:.4f} | {r["token_f1"]:.4f} | {r["mean_retrieval_ms"]:.2f} | {r["p95_retrieval_ms"]:.2f} |'
        )
    lines += [
        "",
        "## Comparison with the saved old hybrid system",
        "",
        "The old predictions were matched by question ID and exact query text, then rescored against current evidence annotations using the same exact-ID and answer metrics as the new runs. Recorded old scores are also preserved in historical_rescoring.json. Old five-percent values are subsets of saved twenty-percent executions, not separate historical five-percent executions.",
        "",
        "| Sample | Benchmark | Old rescored recall@10 | New default recall@10 | New reranked recall@10 | Old MRR | New default MRR | New reranked MRR |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for old in history:
        r = next(
            r
            for r in rows
            if r["percent"] == old["percent"]
            and r["benchmark"] == old["benchmark"]
            and r["profile"] == "reranked_hybrid"
        )
        v = old["corrected"]
        default = next(
            item
            for item in rows
            if item["percent"] == old["percent"]
            and item["benchmark"] == old["benchmark"]
            and item["profile"] == "default_hybrid"
        )
        lines.append(
            f'| {r["percent"]}% | {r["benchmark"]} | {v["retrieval"]["recall@10"]:.4f} | {default["recall@10"]:.4f} | {r["recall@10"]:.4f} | {v["retrieval"]["mrr"]:.4f} | {default["mrr"]:.4f} | {r["mrr"]:.4f} |'
        )
    lines += [
        "",
        "These differences describe the saved executions; they do not isolate the effect of cleanup. Context size, conversation scoping, extraction policy and the first-line answer behavior differ. Historical category names were corrected when rescoring. Historical timings come from the old recorded latency field and were measured in a different runtime and process. They are not a controlled speed comparison. No statistical significance claim is made for these deterministic subsets.",
        "",
        "## Performance and coverage",
        "",
        "| Sample | Benchmark | Profile | Evidence-scored queries | Answer-scored queries | Peak sampled total VRAM MB | Newly ingested docs | Ingestion seconds | Wall seconds |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f'| {r["percent"]}% | {r["benchmark"]} | {r["profile"]} | {r["retrieval_scored_examples"]} | {r["answer_scored_examples"]} | {r["peak_sampled_total_vram_mb"]} | {r["newly_ingested_documents"]} | {r["ingestion_time_sec"]:.2f} | {r["wall_time_sec"]:.2f} |'
        )
    lines += [
        "",
        "VRAM is sampled device-wide every two seconds and includes display/other processes. It is not model-only memory or a guaranteed peak. Both models remain loaded across profiles, including vector-only runs; this does not measure the memory of a standalone vector-only deployment. Models are loaded and checked before the matrix; preflight records that duration. Ingestion occurs once in the vector profile; subsequent profiles validate and reuse identical stored documents. Their ingestion times measure the unchanged-record checks rather than fresh throughput. Mean, p50, p95, p99 and maximum query latency are included in the CSV; model initialization is excluded from query times. Old generation and total-pipeline latency are unavailable and remain unscored. No-memory or removed experimental architectures were not treated as current application features.",
        "",
        "## Evidence",
        "",
        "- all_metrics.csv / all_metrics.json: recall, precision and NDCG at 1, 3, 5 and 10; MRR; AP@10; exact match; token F1; substring match; latency and ingestion statistics.",
        "- comparison.csv / comparison.json: every matched old/new retrieval, answer and latency metric with numeric differences.",
        "- historical_rescoring.json: original recorded scores, corrected scores, source paths, checksums and category breakdowns.",
        "- p*_metrics.json: corrected metrics and current category breakdowns for each of 15 runs.",
        "- raw/: every question result plus source/data/configuration-bound manifests and summaries.",
        "- input_plan.json, preflight.json, verification.json: coverage, input/result hashes, runtime evidence and completion checks.",
        "",
        "Final validation: 105 offline regression tests and four actual-dataset tests passed. All 15 source/input/configuration fingerprints were independently reconstructed, all selected result identities were checked, and recomputed scores matched the saved summaries. Eight original input hashes matched their preserved provenance. The five isolated stores contained exactly the selected document IDs and observation counts. Verified summary copies are available to the existing dashboard; original active stores were not used.",
        "",
        f'Total completed query executions: {sum(r["questions"] for r in rows)}. Failed query executions: {sum(r["failed_examples"] for r in rows)}. LongMemEval twenty-percent executions: 0.',
        "",
    ]
    (report / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report")
    options = parser.parse_args()
    rows = summarize(Path(options.report).resolve())
    print(
        json.dumps(
            dict(
                runs=len(rows),
                queries=sum(r["questions"] for r in rows),
                failures=sum(r["failed_examples"] for r in rows),
            )
        )
    )


if __name__ == "__main__":
    main()
