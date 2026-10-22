"""Generate the visual presentation from reproducible measurement receipts."""

import datetime as dt
from html import escape
import json
from pathlib import Path
from guide_slides import render_slides

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
        + '<p class="note">One shared memory. Nine coordinated roles. Sources that can be refreshed.</p>'
    )
    roles = [
        ("Atlas", "Destinations"),
        ("Haven", "Stays"),
        ("Saffron", "Food"),
        ("Roam", "Attractions"),
    ]
    contents.append(
        '<p class="eyebrow">01 / Where TinyFish is used</p><h2>Four research roles.<br>One shared evidence layer.</h2><div class="role-grid">'
        + "".join(
            f'<div class="role"><strong>{a}</strong><small>{b}</small></div>'
            for a, b in roles
        )
        + '</div><div class="bus" aria-hidden="true"></div>'
        + flow(
            [
                ("TinyFish", "Public Search → Fetch", "accent"),
                ("Evidence memory", "Quotes · URLs · versions", "soft"),
                ("Planning team", "Itinerary · budget · support", ""),
            ]
        )
        + '<div class="agent-output"><strong>Orchestrator + consultant</strong><span>coordinate →</span><strong>saved trip + dashboard</strong></div><p class="note">SQL: trips + evidence versions · FalkorDB: graph + vectors</p>'
    )
    contents.append(
        '<p class="eyebrow">02 / How TinyFish works with memory</p><h2>Reuse what is fresh.<br>Refresh what has changed.</h2>'
        + flow(
            [
                ("Traveler request", "Recall scoped evidence", ""),
                ("Freshness gate", "Missing? Stale? Conflicting?", "soft"),
            ]
        )
        + '<div class="decision"><div class="lane"><div class="lane-label">FRESH <span>Reuse path</span></div><div class="steps"><span>Recall</span><span class="arrow">→</span><span>Agent context</span></div><p class="note">Skip repeat web requests.</p></div><div class="lane stale"><div class="lane-label">MISSING / STALE <span>Research path</span></div><div class="steps"><span>TinyFish<br>Search</span><span class="arrow">→</span><span>Fetch</span><span class="arrow">→</span><span>Quote gate</span></div><p class="note">Save a version → flag affected plans for review.</p></div></div><div class="guard-row"><span>Exact quotes + source URLs</span><span>Expiry + conflict checks</span><span>Traveler-scoped recall</span></div><p class="safety">Public web evidence never overwrites confirmed traveler preferences.</p>'
    )
    guards = [
        (ablation["stale_exclusion"], "Stale cases excluded"),
        (ablation["unsupported_quote_rejection"], "Unsupported quotes rejected"),
        (ablation["changed_plan_detection"], "Plan-change cases flagged"),
    ]
    guard_cards = metric(
        f"{repeat['memory_reuses']}/10", "Lookups reused saved evidence"
    ) + "".join(metric(f"{g['passed']}/{g['cases']}", label) for g, label in guards)
    contents.append(
        '<p class="eyebrow">03 / TinyFish + memory: measured effect</p><h2>Research once. Reuse safely.</h2><span class="tag">Controlled test · mock transport</span><div class="improvement"><div class="chart-card"><div class="chart-top"><strong class="big">'
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
        '<p class="eyebrow">Test 01 / Memory retrieval</p><h2>Can memory find the evidence?</h2><div class="legend"><span>BM25 lexical baseline</span><span class="native">Iron Web memory</span><b>Recall@5</b></div><div class="bench-head"><span>DATASET / SAMPLE</span><span>RELEVANT SESSIONS FOUND</span><span>RECALL</span><span>CHANGE</span><span>LATENCY</span></div>'
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
        '<p class="eyebrow">Test 02 / Voyara travels</p><h2>Does it work in the product?</h2><p class="subtitle">Chat → dated plan → save → reload → live dashboard</p><div class="travel-metrics">'
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
    html = render_slides(
        contents,
        [
            "Overview",
            "Research agents",
            "Memory + TinyFish",
            "Measured effect",
            "Memory benchmarks",
            "Voyara tests",
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
