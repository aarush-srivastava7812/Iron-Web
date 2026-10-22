"""Build compact, offline presentation guides from recorded measurements."""

import datetime as dt
from html import escape
import json
from pathlib import Path
import re

from guide_slides import as_slides

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report/tinyfish_memory"


def read(name):
    path = OUT / name
    return json.loads(path.read_text(encoding="utf8")) if path.exists() else {}


def main():
    benchmark, live, site, checks = (
        read(name)
        for name in [
            "benchmark.json",
            "live-research.json",
            "site-smoke.json",
            "ui-tests.json",
        ]
    )
    timings = site.get("timings", {})
    travel = [c for c in site.get("checks", []) if c["area"] == "travel"]
    passed = sum(c["status"] == "passed" for c in travel)
    blocked = any(c["status"] == "blocked" for c in site.get("checks", []))
    tested_at = site.get("generated_at")
    tested = (
        dt.datetime.fromisoformat(tested_at)
        .astimezone(dt.timezone(dt.timedelta(hours=5, minutes=30)))
        .strftime("%d %b %Y · %H:%M IST")
        if tested_at
        else "Not measured yet"
    )

    def ms(key):
        return f"{timings[key]:.0f} ms" if key in timings else "—"

    repeat, stale, changed = (
        benchmark.get(key, {})
        for key in ["repeated_requests", "stale_exclusion", "changed_plan_detection"]
    )
    metrics = [
        (
            ms("chat_median_ms"),
            "Chat response",
            "Median of five real local draft-chat turns; excludes trip research.",
            "Local browser test",
        ),
        (
            f'{timings["travel_home_ready_ms"]/1000:.2f} s'
            if "travel_home_ready_ms" in timings
            else "—",
            "Travel page ready",
            "Navigation to homepage with the assistant launcher available.",
            "Local browser test",
        ),
        (
            f'{repeat.get("reduction_percent", "—")}%',
            "Fewer repeat requests",
            f'{repeat.get("baseline_http_requests", "—")} → {repeat.get("memory_http_requests", "—")} mock HTTP requests over ten identical lookups.',
            "Controlled ablation",
        ),
        (
            f'{stale.get("passed", "—")}/{stale.get("cases", "—")}',
            "Stale cases excluded",
            "Expired observations stayed out of current agent evidence.",
            "Controlled challenge",
        ),
        (
            f'{changed.get("passed", "—")}/{changed.get("cases", "—")}',
            "Changed plans flagged",
            "Changed high-impact evidence triggered itinerary review.",
            "Controlled challenge",
        ),
        (
            f'{live.get("sources", "—")} sources',
            "Live TinyFish research",
            f'{live.get("fetched_pages", "—")} fetched pages · {live.get("elapsed_ms", 0)/1000:.2f} s for one public Jaipur query.',
            "Live provider check",
        ),
    ]
    cards = "".join(
        f'<article class="metric"><span class="scope">{escape(scope)}</span><strong>{escape(value)}</strong><h3>{escape(label)}</h3><p>{escape(note)}</p></article>'
        for value, label, note, scope in metrics
    )
    rows = "".join(
        f'<tr><th>{escape(item["label"])}</th><td>{item["passed"]}/{item["total"]}</td><td>{escape(item["scope"])}</td></tr>'
        for item in checks.get("checks", [])
    )
    dashboard = (
        "Live feed blocked · HTTP 503"
        if blocked
        else "Live feed tested"
        if site.get("status") == "passed"
        else "Not measured"
    )
    notice = (
        '<p class="notice"><strong>Current environment limit:</strong> Docker Desktop cannot access its local inference socket. FalkorDB is unavailable, so the live dashboard feed returns HTTP 503. Outage messaging, retry and mobile display passed. Dashboard data views were tested separately using labelled fixtures.</p>'
        if blocked
        else ""
    )
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Main architecture, memory features, TinyFish integration and measured results of a memory-driven multi-agent travel system.">
<title>TinyFish × Iron Web · system overview</title>
<style>
:root{{--ink:#142f2c;--muted:#41615a;--green:#174c40;--line:#cbd9cd;--paper:#f7f8f1;--soft:#eaf0e6}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth;scroll-padding-top:78px}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.65 system-ui,-apple-system,"Segoe UI",sans-serif}}a{{color:var(--green);text-underline-offset:4px}}.skip{{position:absolute;top:-80px;left:12px}}.skip:focus{{top:8px;background:white;padding:10px;z-index:9}}header.top{{border-bottom:1px solid var(--line);background:var(--paper);position:sticky;top:0;z-index:2}}.bar{{max-width:1160px;margin:auto;padding:16px 28px;display:flex;align-items:center;justify-content:space-between;gap:20px}}.brand{{font-weight:850;letter-spacing:-.03em;color:var(--green);white-space:nowrap}}nav{{display:flex;gap:20px}}nav a{{font-size:13px;font-weight:650;text-decoration:none}}main{{max-width:1160px;margin:auto;padding:0 28px}}.hero{{padding:64px 0 38px;max-width:900px}}.eyebrow,.scope{{text-transform:uppercase;letter-spacing:.09em;font-size:10px;font-weight:750;color:var(--muted)}}h1{{font-size:clamp(38px,5.5vw,66px);letter-spacing:-.055em;line-height:1.08;margin:18px 0 22px;max-width:18ch}}.hero>p{{font-size:18px;max-width:68ch;color:var(--muted)}}.pill{{display:inline-block;background:var(--soft);border:1px solid var(--line);padding:6px 11px;border-radius:20px;font-size:11px;margin-right:7px}}section.chapter{{padding:34px 0;border-top:1px solid var(--line)}}h2{{font-size:28px;line-height:1.2;letter-spacing:-.035em;margin:8px 0 20px}}h3{{font-size:15px;line-height:1.35;margin:10px 0}}p{{margin:10px 0}}.flow{{list-style:none;display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px;margin:24px 0;padding:0}}.flow li{{background:var(--green);color:#f3fff4;padding:18px 14px;border-radius:10px;position:relative;font-size:12px}}.flow b{{display:block;color:#acdabd;font-size:10px;margin-bottom:7px}}.flow li:not(:last-child):after{{content:'→';position:absolute;right:-10px;top:39%;color:var(--green);font-size:17px}}.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}}.card{{padding:20px;background:white;border:1px solid var(--line);border-radius:12px}}.card p{{font-size:13px;color:var(--muted)}}.features{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:18px 0}}.features>div{{border-left:3px solid #377859;padding:2px 16px}}.features p{{font-size:13px;color:var(--muted)}}.metrics{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}}.metric{{background:var(--soft);border:1px solid var(--line);border-radius:12px;padding:20px}}.metric strong{{display:block;font-size:35px;line-height:1.15;margin-top:14px;letter-spacing:-.04em;font-variant-numeric:tabular-nums}}.metric h3{{margin:14px 0 8px}}.metric p{{font-size:12px;color:var(--muted)}}.method{{font-size:12px;color:var(--muted);margin:20px 0;max-width:90ch}}.notice{{border-left:3px solid #a26c1f;background:#f8eedc;padding:15px 18px;font-size:12px}}.table-scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:12px;margin:22px 0}}th,td{{text-align:left;padding:12px 9px;border-bottom:1px solid var(--line)}}th{{font-weight:700}}thead{{background:var(--soft)}}.sources{{display:flex;flex-wrap:wrap;gap:10px 18px;font-size:12px}}footer{{padding:26px 0 40px;font-size:11px;color:var(--muted);border-top:1px solid var(--line)}}a:focus-visible{{outline:3px solid #4f9970;outline-offset:5px}}details{{padding:14px 0;font-size:12px}}summary{{cursor:pointer;font-weight:700}}
@media(max-width:760px){{.bar{{padding:12px 20px;align-items:flex-start;flex-direction:column;gap:8px}}nav{{gap:16px}}main{{padding:0 20px}}.hero{{padding-top:34px}}.hero>p{{font-size:16px}}.grid,.metrics{{grid-template-columns:1fr 1fr}}.flow{{grid-template-columns:repeat(3,minmax(0,1fr))}}.flow li:after{{display:none}}html{{scroll-padding-top:110px}}}}
@media(max-width:450px){{.grid,.metrics,.features{{grid-template-columns:1fr}}h2{{font-size:25px}}.flow{{grid-template-columns:1fr 1fr}}.metric strong{{font-size:31px}}}}
@media(prefers-reduced-motion:reduce){{html{{scroll-behavior:auto}}}}@media print{{header.top,.skip{{display:none}}.hero{{padding-top:10px}}main{{padding:0}}.metrics{{grid-template-columns:repeat(3,1fr)}}.metric,.card{{break-inside:avoid}}section.chapter{{padding:20px 0}}body{{font-size:11px}}h1{{font-size:40px}}.metric{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
</style></head><body>
<a class="skip" href="#main">Skip to main content</a>
<header class="top"><div class="bar"><a class="brand" href="#main">IRON WEB × TINYFISH</a><nav aria-label="Main sections"><a href="#system">System</a><a href="#memory">Memory</a><a href="#tinyfish">TinyFish</a><a href="#results">Results</a></nav></div></header>
<main id="main"><div class="hero"><div class="eyebrow">Memory-driven multi-agent travel system</div><h1>A team that remembers.<br>A system that checks.</h1><p>Voyara brings specialist agents, shared memory and TinyFish web research together to turn travel requirements into editable plans with traceable evidence.</p><span class="pill">9 coordinated roles</span><span class="pill">Public research · private preferences</span></div>
<section class="chapter" id="system"><div class="eyebrow">01 / The main system</div><h2>One request. A coordinated team.</h2><ol class="flow" aria-label="System workflow"><li><b>01 / UNDERSTAND</b>Traveler request</li><li><b>02 / RECALL</b>Scoped preferences</li><li><b>03 / COORDINATE</b>Specialist agents</li><li><b>04 / RESEARCH</b>TinyFish Search + Fetch</li><li><b>05 / PRESERVE</b>Versioned evidence</li><li><b>06 / DELIVER</b>Validated trip + dashboard</li></ol><div class="grid"><article class="card"><h3>Research team</h3><p>Atlas, Haven, Saffron and Roam research destinations, stays, food and attractions through TinyFish mode.</p></article><article class="card"><h3>Planning team</h3><p>Consultant, itinerary, budget and support roles apply requirements and local validation. The orchestrator coordinates them.</p></article><article class="card"><h3>Persistent workspace</h3><p>SQL saves trips and evidence history. FalkorDB holds the native memory graph and vectors. The dashboard shows recorded work.</p></article></div></section>
<section class="chapter" id="memory"><div class="eyebrow">02 / Why memory matters</div><h2>Keep preferences. Track changing evidence.</h2><div class="features"><div><h3>Personalized retrieval</h3><p>Recall relevant, owner-scoped preferences and evidence across agent runs.</p></div><div><h3>Temporal history</h3><p>Preserve previous observations, source URLs and retrieval timestamps.</p></div><div><h3>Freshness and conflicts</h3><p>Exclude expired or differing observations from current external evidence.</p></div><div><h3>Plan review</h3><p>Flag saved plans when important source evidence changes.</p></div></div></section>
<section class="chapter" id="tinyfish"><div class="eyebrow">03 / TinyFish's role</div><h2>The bridge between memory and the live web.</h2><p>Recall checks for missing, stale or disputed travel evidence. TinyFish discovers public sources and fetches page content. Exact quotations become versioned observations that agents can reuse; refresh runs in the background.</p><p class="method">Freshness does not establish truth or trip-date applicability. Web content cannot change confirmed user preferences. Identity, budgets and travel dates stay local; external queries use public destinations and topics.</p></section>
<section class="chapter" id="results"><div class="eyebrow">04 / Measured results</div><h2>What we tested. What improved.</h2><div class="metrics">{cards}</div><p class="method">Local timings are single-machine observations, not production guarantees. The 90% reduction and challenge counts use mock transport and seeded evidence. The live TinyFish check is separate; extraction was disabled.</p><div class="table-scroll"><table aria-label="Verification results"><thead><tr><th>Check</th><th>Result</th><th>Scope</th></tr></thead><tbody><tr><th>Travel website</th><td>{passed}/{len(travel)} passed</td><td>Actual HTTP + browser; chat, persistence, budget and mobile</td></tr><tr><th>Dashboard live feed</th><td>{escape(dashboard)}</td><td>Actual authenticated session</td></tr>{rows}<tr><th>Browser runtime errors</th><td>{len(site.get('browser_errors', [])) if site else '—'}</td><td>Actual local smoke test</td></tr></tbody></table></div>{notice}<details><summary>Measurement details and reports</summary><p>Chat maximum: {escape(ms('chat_max_ms'))}. Estimated three-day trip creation: {escape(ms('trip_create_ms'))}; this measures the seeded itinerary API, not live AI research. Synthetic test accounts were removed. Tested: {escape(tested)}.</p><div class="sources"><a href="report/tinyfish_memory/site-smoke.json">Live site measurements</a><a href="report/tinyfish_memory/ui-tests.json">Test results</a><a href="report/tinyfish_memory/benchmark.json">Controlled benchmark</a><a href="report/tinyfish_memory/live-research.json">Live TinyFish record</a></div></details></section>
<footer>Branch: codex/tinyfish-memory-refresh · Unmerged · Prices are estimates; reservations remain simulated.<br><a href="http://127.0.0.1:8094">Travel site</a> · <a href="http://127.0.0.1:5174/tinyfish">TinyFish dashboard</a> · <a href="docs/tinyfish_memory_refresh.md">Implementation details</a></footer></main></body></html>"""

    def check_count(label):
        row = next(
            (row for row in checks.get("checks", []) if row["label"] == label), None
        )
        return f'{row["passed"]}/{row["total"]}' if row else "—"

    builds = [
        row for row in checks.get("checks", []) if "production build" in row["label"]
    ]
    verification = [
        ("Travel website", f"{passed}/{len(travel)}", "Actual local HTTP + browser"),
        (
            "Memory checks",
            check_count("Memory and presentation tests"),
            "Isolated SQL and gateway contracts",
        ),
        (
            "Dashboard unit checks",
            check_count("Dashboard unit tests"),
            "JavaScript unit tests",
        ),
        (
            "Browser checks",
            check_count("Dashboard and guide browser checks"),
            "Labelled fixtures + generated HTML",
        ),
        (
            "Production builds",
            f'{sum(row["status"] == "passed" for row in builds)}/{len(builds)}'
            if builds
            else "—",
            "Travel site and dashboard",
        ),
        (
            "Dashboard live feed",
            "Blocked"
            if blocked
            else "Tested"
            if site.get("status") == "passed"
            else "—",
            "HTTP 503 / FalkorDB unavailable"
            if blocked
            else "Actual authenticated session",
        ),
    ]
    details = re.search(
        r"<details><summary>.*?</summary>(.*?)</details>", document, re.S
    ).group(1)
    document = as_slides(
        document, verification=verification, notice=notice, details=details
    )
    for name in ["memory-system-explained.html", "system-explained.html"]:
        path = ROOT / name
        path.write_text(document, encoding="utf8", newline="\n")
        print(f"Updated {name}: {path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
