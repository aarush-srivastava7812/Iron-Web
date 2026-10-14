"""Verify reranker experiments and write their factual latency/quality analysis."""

import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "report/reranker_diagnosis_20261014"
WORK = ROOT / "data/reranker_diagnosis"
NAMES = ("dmr", "locomo", "longmemeval")
VARIANTS = ("baseline", "cap20", "fp16_optimized")


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def table(headers, rows):
    return (
        "\n".join(
            [
                "| " + " | ".join(headers) + " |",
                "| " + " | ".join("---" for _ in headers) + " |",
                *("| " + " | ".join(str(v) for v in row) + " |" for row in rows),
            ]
        )
        + "\n"
    )


def csv_file(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    sys.path.insert(
        0, str(ROOT / "data/latency_breakdown/latency_breakdown_20261014/source")
    )
    from memory.evaluation.slices import load_slice
    from scripts.summarize_reevaluation import aggregate
    import numpy as np

    full = json.loads((REPORT / "full_summary.json").read_text(encoding="utf-8"))
    pilot = json.loads((REPORT / "pilot_summary.json").read_text(encoding="utf-8"))
    prior = json.loads(
        (ROOT / "report/full20_graph_analysis_20261013/state.json").read_text(
            encoding="utf-8"
        )
    )
    inspection = json.loads((REPORT / "model_graph.json").read_text(encoding="utf-8"))
    optimized = json.loads((REPORT / "optimizer.json").read_text(encoding="utf-8"))
    accuracy, latency, components, ranking = [], [], [], []
    for name in NAMES:
        cases = {
            c["example_id"]: c
            for c in json.loads(
                (WORK / (name + "_cases.json")).read_text(encoding="utf-8")
            )
        }
        adapter = load_slice(Path(prior["jobs"][name]["input"]).parent, name)
        for variant in VARIANTS:
            assert full[variant]["status"] == "complete"
            rows = [
                r
                for r in map(
                    json.loads,
                    (REPORT / f"full_{variant}.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines(),
                )
                if r["dataset"] == name
            ]
            assert set(r["example_id"] for r in rows) == set(cases) and len(
                rows
            ) == len(cases)
            evaluations = []
            for row in rows:
                case = cases[row["example_id"]]
                evaluated = dict(case["reference"])
                evaluated.update(
                    run_id="reranker_diagnosis",
                    retrieved_ids=row["retrieved_ids"],
                    predicted_answer=row["predicted_answer"],
                    retrieval_latency_ms=0,
                    generation_latency_ms=0,
                    total_latency_ms=0,
                    error=None,
                )
                evaluations.append(evaluated)
                if variant == "baseline":
                    assert row["retrieved_ids"] == case["reference"]["retrieved_ids"]
                    assert (
                        row["predicted_answer"] == case["reference"]["predicted_answer"]
                    )
                assert (
                    abs(
                        sum(
                            row[k]
                            for k in (
                                "tokenize_ms",
                                "input_build_ms",
                                "inference_ms",
                                "other_ms",
                            )
                        )
                        - row["rerank_ms"]
                    )
                    < 1e-6
                )
            calculated = aggregate(evaluations, adapter)
            saved = full[variant]["datasets"][name]
            saved["quality"].pop(
                "latency", None
            )  # Full engine latency was not measured in this experiment.
            for group in ("retrieval", "answer"):
                for metric, value in calculated[group].items():
                    assert np.isclose(
                        value, saved["quality"][group][metric], rtol=0, atol=1e-12
                    )
                    baseline = full["baseline"]["datasets"][name]["quality"][group][
                        metric
                    ]
                    accuracy.append(
                        dict(
                            dataset=name,
                            variant=variant,
                            group=group,
                            metric=metric,
                            value=value,
                            difference=value - baseline,
                        )
                    )
                    if variant == "baseline":
                        assert np.isclose(
                            value,
                            prior["retrieval"][name]["reranked_hybrid"][
                                "falkordb_after"
                            ][group][metric],
                            rtol=0,
                            atol=1e-12,
                        )
            assert np.isclose(
                np.mean([r["rerank_ms"] for r in rows]),
                saved["mean_ms"],
                rtol=0,
                atol=1e-9,
            )
            latency.append(
                dict(
                    dataset=name,
                    variant=variant,
                    mean_ms=saved["mean_ms"],
                    p95_ms=saved["p95_ms"],
                    samples=len(rows),
                    reduction_percent=100
                    * (
                        1
                        - saved["mean_ms"]
                        / full["baseline"]["datasets"][name]["mean_ms"]
                    ),
                )
            )
            for key, value in saved["component_mean_ms"].items():
                components.append(
                    dict(
                        dataset=name,
                        variant=variant,
                        component=key,
                        mean_ms=value,
                        percent=100 * value / saved["mean_ms"],
                    )
                )
            ranking.append(
                dict(
                    dataset=name,
                    variant=variant,
                    queries=len(rows),
                    exact_top10=sum(r["ranking_matches_previous"] for r in rows),
                    exact_top1=sum(
                        r["retrieved_ids"][:1]
                        == cases[r["example_id"]]["reference"]["retrieved_ids"][:1]
                        for r in rows
                    ),
                    exact_predictions=sum(
                        r["predicted_answer"]
                        == cases[r["example_id"]]["reference"]["predicted_answer"]
                        for r in rows
                    ),
                )
            )
    for v in pilot.values():
        for c in v.get("datasets", {}).values():
            c["quality"].pop("latency", None)
    dump(REPORT / "full_summary.json", full)
    dump(REPORT / "pilot_summary.json", pilot)
    csv_file(REPORT / "quality_metrics.csv", accuracy)
    csv_file(REPORT / "latency.csv", latency)
    csv_file(REPORT / "components.csv", components)
    csv_file(REPORT / "ranking_changes.csv", ranking)
    text = [
        "# Reranker diagnosis and tested measures\n",
        "Analysis date: 14 October 2026. Latency values measure the reranking stage only.\n",
        "## Findings\n",
        "The main cost is repeated local transformer inference. The current reranker is a cross-encoder: "
        "it reads the question together with every candidate document and performs a separate relevance "
        "calculation for each pair. [The BGE model card](https://huggingface.co/BAAI/bge-reranker-base) "
        "describes this query/passage scoring behavior. No network request or graph database command "
        "occurs inside this model stage.\n",
        f"The cached model has {inspection['parameter_elements']:,} parameter elements, 12 layers, "
        f"768 hidden dimensions and float32 weights. Its file occupies {inspection['weights_bytes']:,} "
        "bytes. The tokenizer permits 512 tokens per question/document pair. The original export runs "
        "attention using separate matrix operations. Operator profiling placed all observed heavy "
        "MatMul, FusedMatMul and Gemm operations on CUDA. The CPU operators were small shape operations "
        "such as Gather, Unsqueeze and Reshape.\n",
        "The application sends complete conversation documents to the tokenizer and scores the whole "
        "candidate pool. DMR scores 100 candidates per query, LoCoMo 19–32, and LongMemEval 38–56. With "
        "batch size 16, DMR requires seven model calls. The final result limit of ten is applied after "
        "scoring; changing only top_k does not reduce the number of documents sent to the model.\n",
        "## Test scope\n",
        "The experiments retain all 597 questions from the previous 20% cohorts and their exact candidate "
        "pools. Each of three variants scores every question: 1,791 measured reranking requests. The "
        "original variant reproduces every previously returned ID, ordering and predicted answer. All "
        "17 quality metrics were recomputed. DMR and LongMemEval each have 100 scored questions. LoCoMo "
        "has 397 questions, 395 retrieval-scored examples and 328 answer-scored examples; missing/empty "
        "references are excluded from the corresponding metric denominators.\n",
        "The application source is pinned to the revision used in the preceding latency report. The "
        "current reranker file has no working-tree changes. Newer lifecycle/shared-memory changes are "
        "outside this experiment. Candidate pools come from private copies of the original embedded "
        "vector stores. The verified benchmark graphs have no entities or edges, so graph lookup is "
        "represented as empty when constructing those pools. Original baseline output equality verifies "
        "that this reconstruction gives the same reranked results on every question.\n",
        "BAAI/bge-reranker-base runs locally with ONNX Runtime 1.23.2 on the RTX 4050 Laptop GPU. Model "
        "loading, conversion, embedding, vector search, Redis checks, graph operations and result "
        "generation/scoring are excluded from reranking latency. All variants use the same deterministic "
        "shuffled question order, two warm-up requests, and one complete measured pass. The FP32 variants "
        "run first; the session is released before loading FP16 to avoid holding two large sessions. "
        "This fixed variant order does not control thermal/power conditions. GPU snapshots are retained "
        "in full_telemetry.jsonl; they are instantaneous samples, not kernel timings or peak memory.\n",
        "## Time inside the original reranker\n",
    ]
    text.append(
        table(
            ["Dataset", "Total ms", "Tokenize", "Build inputs", "ONNX run", "Other"],
            [
                [
                    n,
                    f"{full['baseline']['datasets'][n]['mean_ms']:.2f}",
                    *(
                        f"{full['baseline']['datasets'][n]['component_mean_ms'][k]:.2f}"
                        for k in (
                            "tokenize_ms",
                            "input_build_ms",
                            "inference_ms",
                            "other_ms",
                        )
                    ),
                ]
                for n in NAMES
            ],
        )
    )
    text.append(
        "ONNX run includes model execution, input/output transfers and synchronization. Tokenization "
        "runs on the CPU and processes the supplied text before limiting the encoded input. Other "
        "includes constructing pairs, collecting scores, sorting and timer overhead. The operator "
        "profile records provider placement and host node durations; it does not use CUPTI and "
        "must not be interpreted as a separate GPU kernel time breakdown.\n"
    )
    text.append(
        table(
            [
                "Dataset",
                "Mean model batches",
                "Mean padded tokens",
                "Mean active tokens",
                "Padding share",
            ],
            [
                [
                    n,
                    f"{c['mean_batches']:.2f}",
                    f"{c['mean_padded_tokens']:.0f}",
                    f"{c['mean_active_tokens']:.0f}",
                    f"{100*(1-c['mean_active_tokens']/c['mean_padded_tokens']):.1f}%",
                ]
                for n, c in full["baseline"]["datasets"].items()
            ],
        )
    )
    text.extend(
        [
            "## Full-cohort measures tested\n",
            "Original uses FP32, batch 16, 512-token inputs and the full candidate pool. The candidate "
            "limit scores the first 20 candidates in the original vector retrieval order; remaining "
            "candidates are omitted. Fused FP16 keeps every candidate and the same 512-token limit, "
            "but uses an offline optimized mixed-precision model.\n",
        ]
    )
    text.append(
        table(
            [
                "Dataset",
                "Original ms",
                "20 candidates ms",
                "Fused FP16 ms",
                "FP16 reduction",
            ],
            [
                [
                    n,
                    f"{full['baseline']['datasets'][n]['mean_ms']:.2f}",
                    f"{full['cap20']['datasets'][n]['mean_ms']:.2f}",
                    f"{full['fp16_optimized']['datasets'][n]['mean_ms']:.2f}",
                    f"{100*(1-full['fp16_optimized']['datasets'][n]['mean_ms']/full['baseline']['datasets'][n]['mean_ms']):.1f}%",
                ]
                for n in NAMES
            ],
        )
    )
    text.append(
        "The optimizer fused 12 Attention, 12 BiasGelu and 24 SkipLayerNormalization operators. "
        f"The converted file occupies {optimized['output_bytes']:,} bytes. This experiment combines "
        "operator fusion and reduced precision, so it does not isolate their individual speed "
        "contributions. [ONNX Runtime's transformer optimizer](https://onnxruntime.ai/docs/performance/transformers-optimization.html) "
        "supports offline fusions and mixed precision when normal session optimization leaves "
        "some patterns unfused. The initial generic FP16 conversion did not pass model type "
        "validation; only the ONNX Runtime transformer conversion was successfully benchmarked.\n"
    )
    text.extend(
        [
            "## Quality changes\n",
            "Values below are fractions, with each variant compared against the original model. "
            "The full quality_metrics.csv includes all 17 metrics and their numerical differences. "
            "A change in ordering can occur even when aggregated quality values remain unchanged.\n",
        ]
    )
    text.append(
        table(
            [
                "Dataset",
                "Variant",
                "Recall@10",
                "MRR",
                "nDCG@10",
                "Token F1",
                "Exact top ten",
            ],
            [
                [
                    n,
                    v,
                    f"{full[v]['datasets'][n]['quality']['retrieval']['recall@10']:.4f}",
                    f"{full[v]['datasets'][n]['quality']['retrieval']['mrr']:.4f}",
                    f"{full[v]['datasets'][n]['quality']['retrieval']['ndcg@10']:.4f}",
                    f"{full[v]['datasets'][n]['quality']['answer']['token_f1']:.4f}",
                    str(
                        next(
                            r["exact_top10"]
                            for r in ranking
                            if r["dataset"] == n and r["variant"] == v
                        )
                    )
                    + "/"
                    + str(full[v]["datasets"][n]["samples"]),
                ]
                for n in NAMES
                for v in VARIANTS
            ],
        )
    )
    for variant in ("cap20", "fp16_optimized"):
        changed = [
            r
            for r in accuracy
            if r["variant"] == variant and abs(r["difference"]) > 1e-12
        ]
        text.append(
            f"{variant}: {len(changed)} of 51 dataset/metric values changed by more than 1e-12. "
            "The exact deltas are exported, including changes in both directions.\n"
        )
        if changed:
            text.append(
                table(
                    ["Dataset", "Metric", "Difference"],
                    [
                        [r["dataset"], r["metric"], f"{r['difference']:+.6f}"]
                        for r in changed
                    ],
                )
            )
    text.extend(
        [
            "## Smaller pilot experiments\n",
            "Eight deterministic questions per dataset were also used to test batches of 8 and 32, "
            "a 40-candidate limit and a 256-token limit. These pilot timings are descriptive, not "
            "confidence intervals. Variants were executed in separate blocks, so small timing "
            "differences can reflect changing runtime conditions. Shorter input limits and reduced "
            "candidate pools change the information available to the reranker.\n",
        ]
    )
    text.append(
        table(
            ["Variant", "DMR ms", "LoCoMo ms", "LongMemEval ms"],
            [
                [v, *(f"{pilot[v]['datasets'][n]['mean_ms']:.2f}" for n in NAMES)]
                for v in (
                    "baseline",
                    "batch8",
                    "batch32",
                    "cap20",
                    "cap40",
                    "length256",
                    "fp16_optimized",
                )
            ],
        )
    )
    text.extend(
        [
            "## Measures in priority order\n",
            "1. Use a validated fused FP16 model on CUDA as the first performance candidate. It keeps "
            "the same model family, candidate pool and input limit. Numerical changes and observed "
            "quality deltas still need an explicit acceptance criterion before changing the default. "
            "Cache the converted model once, identify it by source-model/runtime hashes, verify finite "
            "scores, and keep the original FP32 model available for CPU execution. The prototype "
            "already produces and measures the optimized artifact; production loading is unchanged.\n",
            "2. Add a separate configurable number of candidates to rerank before inference. A final "
            "result limit alone does not reduce model work. The measured 20-candidate variant shows "
            "the latency/quality tradeoff; apply a cap only where the full metric/category results "
            "meet the intended quality requirement. Graph-derived candidates would also need an "
            "explicit inclusion policy; these observation-only benchmarks do not test that case.\n",
            "3. Reduce repeated text preparation by storing relevant passages or caching document "
            "tokens with model/tokenizer and document-version keys. This matters especially for "
            "LongMemEval after inference is faster. Simply cutting a character prefix is not equivalent "
            "to the current tokenizer and could remove relevant evidence. Chunk selection and token "
            "caching were not measured in this run.\n",
            "4. Make reranking optional for requests whose latency requirement is more important than "
            "its measured ranking benefit. An adaptive rule based on query/candidate confidence needs "
            "calibration and quality evaluation. Cache scores for repeated identical query/document "
            "pairs where versions and model identity match; this helps repeats rather than new prompts.\n",
            "5. Investigate a smaller cross-encoder if a stricter response-time target remains unmet. "
            "This changes the model and requires evaluation on the actual memory tasks. No smaller "
            "model speed or quality result is claimed here. Batch tuning can be revisited after model "
            "optimization; the current pilot does not support increasing batch size as the main fix.\n",
            "6. For simultaneous requests, move expensive model execution out of the graph lease "
            "only after defining consistent snapshot/revision behavior. The previous latency report "
            "measured substantial mutex waiting because the existing lock covers the entire request. "
            "This changes concurrency semantics and was not applied or tested here.\n",
            "## Reproduction\n",
            "Install the isolated inspection dependencies into data/reranker_diagnosis/runtime. Run "
            "scripts/diagnose_reranker.py with --phase prepare, then --phase optimize, then --phase "
            "full --variants baseline,cap20,fp16_optimized. Run scripts/build_reranker_report.py to "
            "recompute quality and generate this document. The retained inputs, original vector stores, "
            "pinned source checkout and model cache are required. Large converted models and candidate "
            "texts remain under ignored data; report files contain measured summaries and per-query "
            "records. No live graph, original corpus or application setting was changed.\n",
            "## References\n",
            "[BGE model behavior](https://huggingface.co/BAAI/bge-reranker-base), "
            "[ONNX Runtime transformer optimization](https://onnxruntime.ai/docs/performance/transformers-optimization.html), "
            "[float16 and mixed precision](https://onnxruntime.ai/docs/performance/model-optimizations/float16.html), "
            "[profiling limitations](https://onnxruntime.ai/docs/performance/tune-performance/profiling-tools.html).\n",
        ]
    )
    (REPORT / "report.md").write_text("\n".join(text), encoding="utf-8", newline="\n")
    dump(
        REPORT / "verification.json",
        dict(
            measured_requests=1791,
            full_variants=3,
            original_output_equality=True,
            quality_values=153,
            component_accounting=True,
            application_changes=False,
            scoring_counts={
                n: {
                    k: full["baseline"]["datasets"][n]["quality"][k]
                    for k in ("retrieval_scored_examples", "answer_scored_examples")
                }
                for n in NAMES
            },
        ),
    )
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures = REPORT / "figures"
    figures.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 4.4))
    x = np.arange(3)
    for i, v in enumerate(VARIANTS):
        label = {
            "baseline": "Original FP32",
            "cap20": "20 candidates",
            "fp16_optimized": "Optimized FP16",
        }[v]
        bars = ax.bar(
            x + (i - 1) * 0.24,
            [full[v]["datasets"][n]["mean_ms"] for n in NAMES],
            0.24,
            label=label,
        )
        ax.bar_label(bars, fmt="%.0f", fontsize=8, padding=3)
    ax.set_xticks(x, NAMES)
    ax.set_ylabel("Mean reranking wall time (ms)")
    ax.set_title("Same 20% query cohorts: reranker variants")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(figures / "reranked_hybrid.png", dpi=170)
    fig.savefig(figures / "reranked_hybrid.pdf")
    plt.close(fig)
    print(str(REPORT / "report.md"))


if __name__ == "__main__":
    main()
