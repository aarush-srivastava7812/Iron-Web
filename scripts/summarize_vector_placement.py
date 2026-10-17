"""Create a readable report from actual vector-placement measurements."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    out = args.report.resolve()
    manifest = json.loads((out / "manifest.json").read_text())
    results = json.loads((out / "comparison.json").read_text())
    workloads = json.loads((out / "workloads.json").read_text())
    lines = ["# Vector placement: measured comparison", "",
        "The existing architecture was tested with local Qdrant vectors and with native indexed FalkorDB vectors. Production placement was not changed.", "",
        "This is a first placement experiment on the retained **5% dataset slices**, including their complete histories. The proposed **5% relative tolerance** is a separate, unconfirmed interpretation of the user's threshold; it is not the sample size or a statistical significance decision.", "",
        "## Matched inputs", "",
        f"- {sum(r['questions'] for r in results.values())} distinct questions; {manifest['rounds']} measured rounds per backend and retrieval path.",
        "- Identical source graph content, bitwise-identical stored vectors and identical payloads; original evaluation stores were hashed before and after. Of 149 questions, 147 have reference evidence; two LoCoMo questions lack evidence annotations and are not classified as unanswerable.",
        f"- Real {manifest['embedding_model']} embeddings; {', '.join(manifest['providers'])}; no synthetic embedding substitute or generated-answer scoring.",
        "- Default application candidate/evidence budgets, reranking disabled, actual current MemoryEngine for complete retrieval and concurrent writes/reads.",
        "- Qdrant is the current embedded exact-search implementation. FalkorDB is a network service using its native cosine vector index. This compares the actual architecture paths, not equivalently deployed vendor products.",
        "- Both graph variants preserve the current entity-name/conflict behavior. No cache research or tuning occurred.", "",
        "## Complete retrieval latency and evidence quality", "",
        "Complete retrieval includes real question embedding, vector lookup, current graph processing, filtering and ranking. Lower latency is better; higher evidence completeness is better.", "",
        "| Dataset | Questions / memories | Qdrant typical / slow (ms) | Falkor typical / slow (ms) | Qdrant evidence recall at 10 | Falkor evidence recall at 10 |", "| --- | --- | --- | --- | --- | --- |"]
    for name, r in results.items():
        v = r['comparison']['complete_retrieval']; q, f = v['qdrant'], v['falkor']
        lines.append(f"| {name} | {r['questions']} / {r['stored_vectors']} | {q['latency']['p50_ms']:.2f} / {q['latency']['p95_ms']:.2f} | {f['latency']['p50_ms']:.2f} / {f['latency']['p95_ms']:.2f} | {q['quality']['recall@10']:.2%} | {f['quality']['recall@10']:.2%} |")
    lines += ["", "Typical means median; slow means the 95th percentile. Evidence recall is the fraction of reference evidence found, not final-answer accuracy. Matching a low baseline score does not establish good retrieval.", "",
        "## Vector lookup alone", "", "| Dataset | Qdrant typical / slow (ms) | Falkor typical / slow (ms) | Identical ordered results |",
        "| --- | --- | --- | --- |"]
    for name, r in results.items():
        v=r['comparison']['vector_lookup']; q, f=v['qdrant']['latency'],v['falkor']['latency']
        lines.append(f"| {name} | {q['p50_ms']:.2f} / {q['p95_ms']:.2f} | {f['p50_ms']:.2f} / {f['p95_ms']:.2f} | {v['same_ordered_results']} / {v['unique_questions']} |")
    lines += ["", "FalkorDB 4.20.7 returned cosine distance in the verified index probe. The experimental adapter converts it to similarity before passing results to the existing scorer. Filters are applied after native vector lookup, with adaptive overfetch to preserve the application's result budget. This work is included in measured time.", "",
        "## Proposed 5% rule: illustrative checks", "",
        "These checks remain provisional. Every latency metric must stay within 1.05 times the Qdrant value; every higher-is-better output metric must stay above 0.95 times the corresponding value. Paired question-block bootstrap intervals appear in comparison.json; repetitions are not treated as extra independent questions.", "",
        "| Dataset / path | Typical latency change | Slow latency change | Recall / relevance / ranking point checks |",
        "| --- | --- | --- | --- |"]
    for name,r in results.items():
        for path,v in r['comparison'].items():
            c=v['checks']; qchecks=[c[m]['provisional_point_check'] for m in ['recall@10','precision@10','ndcg@10']]
            lines.append(f"| {name} / {path} | {(c['p50_ms']['ratio']-1)*100:+.1f}% | {(c['p95_ms']['ratio']-1)*100:+.1f}% | {' / '.join(qchecks)} |")
    lines += ["", "The next placement decision should retain Qdrant unless the measured evidence justifies adopting the candidate. These results do not support a general claim that FalkorDB vectors are intrinsically slower at all sizes or deployments.", "",
        "## Concurrent reads and synchronous ingestion", "",
        "| Dataset | Backend | Workload | Reads | Typical / slow read (ms) | Read errors | Visible writes |",
        "| --- | --- | --- | --- | --- | --- | --- |"]
    for name,rows in workloads.items():
        for row in rows:
            s=row['reads']; writes=row['write_samples']; visible=sum(w.get('visible',False) for w in writes)
            lines.append(f"| {name} | {row['backend']} | {row['workers']} readers{' + writer' if row['mixed'] else ''} | {s['samples']} | {s['p50_ms']:.2f} / {s['p95_ms']:.2f} | {s['errors']} | {str(visible)+' / '+str(len(writes)) if writes else '—'} |")
    lines += ["", "Read times include waiting at the current engine's shared lock. One cooperating engine per graph is used; this is concurrent client submission, not proof of unbounded database parallelism or multi-process tenant authorization. Mixed reads/writes run one trace per backend, so their values are descriptive and not a five-round statistical gate. Write commit and first-visible-check timings are in workloads.json.", "",
        "The current add operation is synchronous. No separate background receipt, interpretation-ready event or durable notification was implemented or claimed by this experiment.", "",
        "## Limits and next work", "",
        "- These datasets were already used in earlier evaluations. They are not held out. There was no tuning on their scores in this run, but a larger untouched set is still needed for a research claim or fine 5% quality judgment.",
        "- The stored baseline graphs must be inspected for relation coverage. Default extraction was disabled; zero-entity graphs do not exercise the richer KG additions. Filter/rollback tests exercise the experimental adapter separately.",
        "- No generated answers, fuzzy scores, protected memories, new contradiction/supersession policy, missing-answer gate, authority rules or shared handoff system were added by this placement experiment.",
        "- Background load and temperature were not controlled. The confirmation pairs each question's two backend calls and alternates their order; the first grouped run is retained separately. Inspect raw timings and intervals rather than interpreting small noisy differences as established gains.",
        "- Persistence is the existing local Qdrant setup versus the existing FalkorDB AOF configuration; crash durability and fsync-equivalent settings were not established. This is not a durability benchmark.",
        "- Candidate setup time is native vector loading/indexing, not a fair index-build comparison against a copied existing Qdrant store. Memory/storage use needs its own recorded comparison before an operating-cost claim.",
        "- Experimental adapter scope is deliberately narrow. Production configuration does not select it, and unsupported filters fail explicitly.",
        "- Use the unchanged placement baseline for the next fuzzy/history and explainable-retrieval additions. Their own effect and latency need separate tests.", "",
        "## Reproduction and evidence", "",
        "Run with the workspace Python environment and the existing local FalkorDB service:", "", "```powershell",
        "& '.\\.venv\\Scripts\\python.exe' scripts/benchmark_vector_placement.py --report report/vector_placement_fresh_run --datasets dmr locomo longmemeval --rounds 5",
        "& '.\\.venv\\Scripts\\python.exe' scripts/summarize_vector_placement.py report/vector_placement_fresh_run", "```", "",
        "Choose a new output directory; the script will not overwrite another experiment. Isolated server graphs are removed after each cohort; copied local stores and evidence are retained.", "",
        "- [Manifest and source fingerprints](manifest.json)",
        "- [Matched latency/quality results and intervals](comparison.json)",
        "- [Concurrent workload details](workloads.json)",
        "- [All scored timings and retrieved evidence IDs](raw.json)",
        "- Each dataset also has frozen questions, index/query-plan evidence and raw records.", "",
        "Native index reference: [FalkorDB vector indexing](https://docs.falkordb.com/cypher/indexing/vector-index). Its runtime behavior was verified rather than assumed from documentation.", ""]
    (out / 'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print(out / 'REPORT.md')


if __name__ == '__main__':
    main()
