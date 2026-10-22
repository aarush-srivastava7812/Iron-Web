"""Generate the visual presentation from reproducible measurement receipts."""

import datetime as dt
from html import escape
import json
from pathlib import Path
from guide_slides import render_slides
from memory_architecture_slides import hybrid_memory_slide, tinyfish_agents_slide
from benchmark_slides import benchmark_slides
from presentation_sections import explanatory_sections

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report/tinyfish_memory"


def read(name):
    path = OUT / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def node(title, detail, style=""):
    return f'<div class="node {style}"><strong>{title}</strong><small>{detail}</small></div>'


def flow(items, hero=False):
    return (
        '<div class="hero-flow" role="img" aria-label="Memory recalls evidence, TinyFish researches missing evidence, Voyara uses it to plan travel">'
        + '<span class="arrow" aria-hidden="true">→</span>'.join(
            node(*i) for i in items
        )
        + "</div>"
        if hero
        else '<div class="flow">'
        + '<span class="arrow" aria-hidden="true">→</span>'.join(
            node(*i) for i in items
        )
        + "</div>"
    )


def metric(value, label, note=""):
    return (
        f'<article class="metric"><strong>{escape(str(value))}</strong><span>{escape(label)}</span>'
        + (f"<small>{escape(note)}</small>" if note else "")
        + "</article>"
    )


def main():
    ablation, live, site, memory = [
        read(name)
        for name in [
            "benchmark.json",
            "live-research.json",
            "site-smoke.json",
            "memory-benchmarks.json",
        ]
    ]
    if memory.get("status") != "passed":
        raise SystemExit(
            "Complete the fresh memory benchmark before publishing metrics."
        )
    repeat = ablation["repeated_requests"]
    timings = site["timings"]
    travel = [c for c in site["checks"] if c["area"] == "travel"]
    dashboard = [c for c in site["checks"] if c["area"] == "dashboard"]
    travel_pass = sum(c["status"] == "passed" for c in travel)
    dashboard_pass = sum(c["status"] == "passed" for c in dashboard)
    checked = (
        dt.datetime.fromisoformat(site["generated_at"])
        .astimezone(dt.timezone(dt.timedelta(hours=5, minutes=30)))
        .strftime("%d %b %Y · %H:%M IST")
    )
    contents = []
    contents.append(
        '<p class="eyebrow">Memory-driven multi-agent travel</p><h1>Remember the traveler.<br>Recheck the world.</h1>'
        + flow(
            [
                ("Iron Web", "Preferences + evidence history", "soft"),
                ("TinyFish", "Search + Fetch public sources", "accent"),
                ("Voyara", "Editable, evidence-grounded trips", ""),
            ],
            hero=True,
        )
        + '<p class="slide-lead">Voyara combines persistent traveler context with current destination research. The goal is to preserve what the traveler has told us while keeping changing web information traceable and refreshable.</p><div class="presentation-agenda"><span>01 System overview</span><span>02 Hybrid memory</span><span>03 TinyFish + agents</span><span>04 Product workflow</span><span>05 Evaluation</span><span>06 Next steps</span></div>'
    )
    contents.append(tinyfish_agents_slide())
    contents.append(hybrid_memory_slide())
    guards = [
        (ablation["stale_exclusion"], "Stale cases excluded"),
        (ablation["unsupported_quote_rejection"], "Unsupported quotes rejected"),
        (ablation["changed_plan_detection"], "Plan-change cases flagged"),
    ]
    guard_cards = metric(
        f"{repeat['memory_reuses']}/10", "Lookups reused saved evidence"
    ) + "".join(metric(f"{g['passed']}/{g['cases']}", label) for g, label in guards)
    contents.append(
        '<p class="eyebrow">05 / Evaluation · TinyFish + memory</p><h2>Research once. Reuse safely.</h2><p class="slide-lead">Ten identical controlled lookups compare repeated Search/Fetch requests with reuse of eligible saved evidence. The safety cases independently exercise stale data, unsupported quotes and plan-change detection.</p><span class="tag">Controlled test · mock transport</span><div class="improvement"><div class="chart-card"><div class="chart-top"><strong class="big">'
        + str(repeat["reduction_percent"])
        + '%</strong><small>fewer repeated HTTP requests</small></div><div class="request-row"><span>Uncached</span><div class="track"><div class="fill" style="width:100%"></div></div><b>'
        + str(repeat["baseline_http_requests"])
        + '</b></div><div class="request-row"><span>With memory</span><div class="track"><div class="fill native" style="width:10%"></div></div><b>'
        + str(repeat["memory_http_requests"])
        + '</b></div><p class="note">10 identical lookups · same source fixture</p></div><div class="metrics">'
        + guard_cards
        + '</div></div><div class="provider-strip"><span class="provider-label"><span class="tag live">Real TinyFish call</span>Jaipur Search + Fetch</span><b>'
        + str(live["sources"])
        + " sources</b><b>"
        + str(live["fetched_pages"])
        + " pages</b><b>"
        + f"{live['elapsed_ms']/1000:.2f}"
        + ' s</b></div><p class="note">Live run: '
        + escape(live["fetched_at"][:10])
        + " · extraction disabled; connectivity only. Controlled results are not production savings or answer accuracy.</p>"
    )
    # Present measured motivation, then hybrid memory, then its agent consumers.
    contents[1], contents[3] = contents[3], contents[1]
    rows = []
    for d in memory["datasets"]:
        lexical, native = d["lexical"], d["native"]
        change = 100 * (native["recall_at_5"] - lexical["recall_at_5"])
        label = {"locomo": "LoCoMo", "dmr": "DMR / MSC", "longmemeval": "LongMemEval"}[
            d["benchmark"]
        ]
        pair = (
            '<div class="bar-pair" role="img" aria-label="'
            + escape(
                f"{label} recall at 5: lexical {100*lexical['recall_at_5']:.1f} percent; memory {100*native['recall_at_5']:.1f} percent"
            )
            + '"><div class="track"><div class="fill" style="width:'
            + f"{100*lexical['recall_at_5']:.2f}"
            + '%"></div></div><div class="track"><div class="fill native" style="width:'
            + f"{100*native['recall_at_5']:.2f}"
            + '%"></div></div></div>'
        )
        rows.append(
            f'<div class="bench-row"><div class="bench-name"><strong>{label}</strong><small>{d["questions"]} queries · {d["documents"]} sessions</small></div>{pair}<div class="bench-value">{100*native["recall_at_5"]:.1f}%<small>memory recall</small></div><div class="delta {"negative" if change<0 else ""}">{change:+.1f} pp</div><div class="bench-value">{native["median_ms"]:.0f}<small>median ms</small></div></div>'
        )
    contents.append(
        '<p class="eyebrow">05 / Evaluation · memory retrieval</p><h2>Can memory find the evidence?</h2><p class="slide-lead">BM25 and the current memory engine receive the same documents and questions. Recall@5 measures the fraction of annotated evidence sessions found among the first five results.</p><div class="legend"><span>BM25 lexical baseline</span><span class="native">Iron Web memory</span><b>Recall@5</b></div><div class="bench-head"><span>DATASET / SAMPLE</span><span>RELEVANT SESSIONS FOUND</span><span>RECALL</span><span>CHANGE</span><span>LATENCY</span></div>'
        + "".join(rows)
        + '<div class="results-note"><span><b>Same histories, same questions.</b> CPU · no reranker · release-order samples.</span><span><b>Mixed results are retained.</b> Full dataset answer accuracy remains unmeasured.</span></div><p class="note">Complete selected histories. DMR is the project’s MSC conversion. Source retrieval only; no historical-time or generated-answer scoring. No TinyFish calls in this test.</p>'
    )
    cards = [
        (
            f"{travel_pass}/{len(travel)}",
            "Travel checks passed",
            "Chat · plan · save · duplicate · mobile",
        ),
        (
            f"{dashboard_pass}/{len(dashboard)}",
            "Live dashboard checks passed",
            "8 views · live feed · ownership + mobile",
        ),
        (
            f"{timings['chat_median_ms']:.0f} ms",
            "Draft-chat response",
            "Median of 5 local turns; not AI research",
        ),
        ("5/5", "Chat turns survived reload", "Actual saved conversation"),
        ("3 days", "Dated plan + budget reconciled", "Seeded price estimates"),
        (
            str(len(site["browser_errors"])),
            "Browser runtime errors",
            "Actual localhost browser test",
        ),
    ]
    # These values are derived from successful checks, never inferred from UI fixtures.
    dialogue = next(c for c in travel if c["name"].startswith("Five-turn"))
    plan = next(c for c in travel if c["name"].startswith("Dated itinerary"))
    cards[3] = (
        f"{dialogue.get('detail',{}).get('turns',0)}/5"
        if dialogue["status"] == "passed"
        else "Failed",
        cards[3][1],
        cards[3][2],
    )
    cards[4] = (
        f"{plan.get('detail',{}).get('days',0)} days"
        if plan["status"] == "passed"
        else "Failed",
        cards[4][1],
        cards[4][2],
    )
    contents.append(
        '<p class="eyebrow">05 / Evaluation · Voyara travels</p><h2>Does it work in the product?</h2><p class="subtitle">Chat → dated plan → save → reload → live dashboard</p><p class="slide-lead">A synthetic traveler exercises the running product. Checks cover persisted conversation, a dated plan, budget reconciliation, trip duplication and owner-scoped dashboard views.</p><div class="travel-metrics">'
        + "".join(metric(*c) for c in cards)
        + '</div><p class="note">'
        + checked
        + ' · Actual HTTP + browser tests · No substituted dashboard feed · No paid research started by this test.</p><button class="report-button" id="open-reports" type="button">Measurement details &amp; reports ↗</button>'
    )
    details = (
        "<p><b>Two independent evaluations.</b> The memory sample tests source retrieval on LoCoMo (20 questions), project DMR / MSC (20), and LongMemEval (5). The Voyara test checks the running travel product and owner-scoped dashboard. Neither establishes a TinyFish-caused benchmark accuracy improvement.</p><p><b>Memory protocol.</b> First questions in release order; all sessions of selected histories retained, including distractors. BM25 k1=1.5, b=0.75 and the native engine share documents and allowed scopes. Recall@5 is the fraction of annotated evidence sessions retrieved. Current CPU embeddings; no reranker or answer model. Historical query time is not applied. Per-question IDs, metrics, input hashes and MRR are in the report.</p><p><b>TinyFish lifecycle protocol.</b> Same ten seeded lookups, comparing an uncached Search/Fetch loop against evidence recall. Stale, unsupported quotation and changed-plan cases are separate controlled challenges. Their passing counts do not establish live factual accuracy, provider cost savings, or performance of the previous release.</p><p><b>Live provider protocol.</b> One recorded public Jaipur query, Search + Fetch, extraction disabled. The live provider test is separate from the seeded lifecycle experiment and the product smoke test. Traveler preferences are not submitted.</p><p><b>Voyara protocol.</b> Synthetic traveler, five draft-chat turns, seeded three-day itinerary and cost reconciliation, save/retrieve/duplicate, responsive layouts, three authenticated feed samples, eight dashboard views and owner isolation. Test-owned SQL account removed. Timings describe localhost and seeded planning, not hosted LLM planning. Result: "
        + escape(site["status"])
        + '.</p><div class="sources">'
        + "".join(
            f'<a href="report/tinyfish_memory/{path}">{label}</a>'
            for path, label in [
                ("memory-benchmarks.json", "Memory benchmark rows"),
                ("benchmark.json", "TinyFish controlled test"),
                ("live-research.json", "Live provider receipt"),
                ("site-smoke.json", "Live site measurements"),
                ("ui-tests.json", "Build and unit checks"),
            ]
        )
        + '</div><p class="sources"><a href="http://127.0.0.1:8094/">Open Voyara</a><a href="http://127.0.0.1:5174/tinyfish">Open dashboard</a><a href="docs/tinyfish_memory_refresh.md">Implementation</a></p>'
    )
    sections = explanatory_sections()
    original = contents
    contents = [
        original[0], sections["system"], original[2], original[3],
        sections["vector-memory"], sections["graph-memory"], sections["evidence"],
        sections["tools"], sections["workflow"], original[1], original[4], original[5],
        *benchmark_slides(memory), sections["conclusion"],
    ]
    html = render_slides(
        contents,
        [
            "Overview",
            "System overview",
            "Hybrid memory + TinyFish",
            "Agents + three tools",
            "Vector memory explained",
            "Knowledge graph explained",
            "Evidence memory lifecycle",
            "Search, Fetch and Agent",
            "Voyara workflow",
            "Measured evidence reuse",
            "Memory benchmarks",
            "Voyara tests",
            "LoCoMo results",
            "DMR / MSC results",
            "LongMemEval results",
            "Retrieval latency",
            "Benchmark method",
            "Conclusions + next steps",
        ],
        details,
    )
    for name in ["memory-system-explained.html", "system-explained.html"]:
        (ROOT / name).write_text(html, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "slides": len(contents),
                "bytes": len(html.encode()),
                "site_status": site["status"],
            }
        )
    )


if __name__ == "__main__":
    main()
