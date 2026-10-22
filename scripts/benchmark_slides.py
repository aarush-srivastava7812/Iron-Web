"""Large benchmark charts generated only from the existing measurement receipt."""
from html import escape

LABELS = {"locomo": "LoCoMo", "dmr": "DMR / MSC", "longmemeval": "LongMemEval"}
DESCRIPTIONS = {
    "locomo": "Conversation-memory sample: retrieve the sessions that contain the annotated evidence. Lower recall here means more supporting sessions were missed by native retrieval than by BM25.",
    "dmr": "Project MSC conversion: retrieve evidence from multi-session histories. Native retrieval finds evidence for some questions where BM25 finds none in this selected sample.",
    "longmemeval": "Long-history sample with 253 retained sessions. Five questions are too few to establish a broad ranking; the measured BM25 advantage is preserved.",
}


def benchmark_slides(memory):
    slides = []
    for dataset in memory["datasets"]:
        name = LABELS[dataset["benchmark"]]
        baseline, native = dataset["lexical"], dataset["native"]
        delta = 100 * (native["recall_at_5"] - baseline["recall_at_5"])
        bars = "".join(
            f'<div class="dataset-bar"><span>{label}</span><div class="track"><div class="fill {style}" style="width:{100*row["recall_at_5"]:.2f}%"></div></div><strong>{100*row["recall_at_5"]:.1f}%</strong></div>'
            for label, row, style in [("BM25 baseline", baseline, ""), ("Iron Web memory", native, "native")]
        )
        verdict = "Memory retrieves more annotated evidence in this sample." if delta > 0 else "BM25 retrieves more annotated evidence in this sample."
        slides.append(
            f'<p class="eyebrow">Recorded benchmark / {escape(name)}</p><h2>{escape(name)}: evidence retrieval</h2>'
            f'<p class="subtitle">{dataset["questions"]} questions · {dataset["documents"]} history sessions · Recall@5</p>'
            f'<p class="slide-lead">{DESCRIPTIONS[dataset["benchmark"]]}</p>'
            f'<div class="dataset-chart">{bars}</div><div class="dataset-metrics">'
            f'<article><strong>{delta:+.1f} pp</strong><span>Recall change vs BM25</span></article>'
            f'<article><strong>{native["median_ms"]:.1f} ms</strong><span>Memory median latency</span></article>'
            f'<article><strong>{100*native["hit_at_5"]:.0f}%</strong><span>Queries with an evidence hit</span></article></div>'
            f'<p class="benchmark-verdict">{verdict}</p><p class="note">Recorded 22 Oct 2026 · Current CPU source retrieval, no reranker. Sample results, not full-dataset answer accuracy. No TinyFish calls.</p>'
        )
    rows = "".join(
        f'<tr><th scope="row">{LABELS[d["benchmark"]]}</th><td>{d["lexical"]["median_ms"]:.2f} ms</td><td>{d["native"]["median_ms"]:.1f} ms</td><td>{d["ingestion_ms"]/1000:.2f} s</td></tr>'
        for d in memory["datasets"]
    )
    slides.append('<p class="eyebrow">Benchmark / latency</p><h2>Retrieval time, measured locally.</h2><table class="latency-table"><thead><tr><th>Dataset</th><th>BM25 median</th><th>Memory median</th><th>Memory ingestion</th></tr></thead><tbody>' + rows + '</tbody></table><p class="benchmark-verdict">BM25 is faster in all three recorded samples.</p><p class="note">Identical source documents and allowed scope · CPU embeddings · ingestion is a separate one-time measurement, not query latency. These timings do not measure TinyFish or end-to-end trip planning.</p>')
    slides.append('''<p class="eyebrow">Benchmark / how to read the results</p><h2>What these tests establish.</h2><div class="protocol-grid"><article><b>01</b><h3>Same inputs</h3><p>First 20 LoCoMo, 20 DMR/MSC and 5 LongMemEval questions. Complete selected histories retained.</p></article><article><b>02</b><h3>Source retrieval</h3><p>Recall@5: fraction of annotated evidence sessions found. Hit@5: queries with at least one match.</p></article><article><b>03</b><h3>Separate experiments</h3><p>Memory benchmarks use no TinyFish calls. TinyFish reuse and Voyara workflow tests are separate.</p></article></div><p class="benchmark-verdict">Mixed results remain visible. Full-dataset answer accuracy is unmeasured.</p><p class="note">No historical query-time evaluation · no reranker · no generated-answer scoring. DMR is the project’s MSC conversion.</p><a class="receipt-link" href="report/tinyfish_memory/memory-benchmarks.json">Open recorded benchmark results ↗</a>''')
    return slides
