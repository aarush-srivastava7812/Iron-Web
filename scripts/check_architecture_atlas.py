"""Browser acceptance of the offline architecture atlas and its evidence boundaries."""

import datetime as dt
import json
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from agents.tinyfish import RESEARCH_ROLES
    from build_architecture_atlas import AGENTS

    report_dir = ROOT / "report/architecture_atlas"
    data = json.loads(
        (report_dir / "published-comparison.json").read_text(encoding="utf-8")
    )
    report = dict(
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        mode="Actual offline HTML in Edge; no mocked provider calls or remote resources",
        checks=[],
        runtime_errors=[],
        network_requests=[],
    )
    assert {a["code"] for a in AGENTS if a["connection"] == "direct"} == set(
        RESEARCH_ROLES
    )
    report["checks"].append(
        "Four direct research connections match implemented RESEARCH_ROLES"
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000}, offline=True
        )
        page = context.new_page()
        page.on("pageerror", lambda error: report["runtime_errors"].append(str(error)))
        page.on(
            "request",
            lambda request: report["network_requests"].append(request.url)
            if request.url.startswith(("http:", "https:"))
            else None,
        )
        page.goto((ROOT / "architecture-atlas.html").as_uri() + "#overview")
        expect(page.locator("#title-overview")).to_be_visible()
        expect(page.locator(".view:visible")).to_have_count(1)
        report["checks"].append("Offline page initializes and shows a single view")
        page.get_by_role("button", name="02 Agent map", exact=True).click()
        expect(page.locator(".agent-node")).to_have_count(9)
        expect(page.locator(".agent-edge")).to_have_count(9)
        for agent in AGENTS:
            page.locator('[data-agent="' + agent["id"] + '"]').click()
            expect(page.locator("#agent-name")).to_have_text(agent["name"])
            expect(page.locator("#agent-code")).to_have_text(agent["code"])
            expect(page.locator("#agent-actual")).to_have_text(agent["actual"])
        report["checks"].append(
            "All nine agent nodes reveal correct implementation and recommendation details"
        )
        page.get_by_role("button", name="Direct TinyFish", exact=True).click()
        expect(page.locator(".agent-node:visible")).to_have_count(4)
        page.get_by_role("button", name="Shared evidence", exact=True).click()
        expect(page.locator(".agent-node:visible")).to_have_count(5)
        page.get_by_role("button", name="All nine roles", exact=True).click()
        page.locator('[data-agent="orchestrator"]').focus()
        page.keyboard.press("ArrowRight")
        expect(page.locator("#agent-name")).to_have_text("Trip Consultant")
        report["checks"].append(
            "Direct/shared filters and keyboard agent navigation work"
        )
        page.locator('.hub [data-tool="fetch"]').click()
        expect(page.locator(".agent-edge.direct:not(.inactive)")).to_have_count(3)
        page.locator('[data-agent="explorer"]').click()
        expect(page.locator("#agent-tool-detail")).to_contain_text(
            "normally returns Search discovery"
        )
        page.locator('.hub [data-tool="agent"]').click()
        expect(page.locator(".agent-edge.optional")).to_have_count(4)
        expect(page.locator("#hub-tool-status")).to_contain_text("not the default")
        expect(page.locator("#agent-tool-detail")).to_contain_text("async run")
        page.locator('nav [data-view="tools"]').click()
        expect(page.locator("#tool-cards .tool-card")).to_have_count(3)
        expect(page.locator("#tool-endpoint")).to_contain_text("automation/run-async")
        expect(page.locator("#tool-implementation")).to_contain_text(
            "no automatic Fetch-to-Agent escalation"
        )
        page.locator('[data-tool-card="search"]').click()
        expect(page.locator("#tool-response")).to_have_text(
            "Ranked URLs, titles and snippets"
        )
        page.locator('[data-tool-card="fetch"]').click()
        expect(page.locator("#tool-response")).to_have_text(
            "Readable page text and source URLs"
        )
        page.locator('nav [data-view="agents"]').click()
        page.locator('.hub [data-tool="search"]').click()
        expect(page.locator(".agent-edge.optional")).to_have_count(0)
        report["checks"].append(
            "Search, Fetch and optional Agent show distinct wiring, inputs, outputs and actual client status"
        )
        page.locator("#role-details summary").click()
        expect(page.locator("#roles-table tbody tr")).to_have_count(9)
        expect(page.locator("#roles-table")).to_be_visible()
        report["checks"].append("Full nine-role matrix opens")
        page.locator('nav [data-view="memory"]').click()
        expect(page.locator("#memory-steps button")).to_have_count(7)
        page.locator('[data-memory-step="sql"]').click()
        expect(page.locator("#memory-step-function")).to_contain_text(
            "ExternalKnowledgeVersion"
        )
        page.locator('[data-memory-step="graph"]').click()
        expect(page.locator("#memory-step-function")).to_contain_text("sync_graph")
        expect(page.locator("#memory-step-output")).to_contain_text("NEWER_OBSERVATION")
        page.locator('[data-memory-step="context"]').click()
        expect(page.locator("#memory-step-function")).to_contain_text(
            "MemoryContext.external_evidence"
        )
        expect(page.locator("#memory")).to_contain_text(
            "Agent output needs a separate evidence-ingestion bridge"
        )
        report["checks"].append(
            "TinyFish-to-SQL-to-FalkorDB-to-gateway memory handoffs and Agent ingestion gap are explicit"
        )
        for scenario, expected in [
            ("fresh", "evidence_reused"),
            ("stale", "stale_excluded"),
            ("changed", "evidence_review_required"),
            ("outage", "retry on recall"),
        ]:
            page.locator('[data-memory-scenario="' + scenario + '"]').click()
            expect(page.locator("#memory-scenario")).to_contain_text(expected)
        report["checks"].append(
            "Fresh, stale, changed and graph-outage walkthroughs expose the implemented lifecycle rules"
        )
        page.locator('nav [data-view="comparison"]').click()
        expect(page.locator("#comparison-rows tr")).to_have_count(6)
        for index, row in enumerate(data["rows"]):
            expect(page.locator("#token-chart .chart-row").nth(index)).to_contain_text(
                f'{row["tokens"]:,}'
            )
            expect(
                page.locator("#latency-chart .chart-row").nth(index)
            ).to_contain_text(str(row["task_s"]) + " s")
        expect(page.locator("#comparison-insight")).to_contain_text(
            "53.2% fewer LLM tokens"
        )
        expect(page.locator("#comparison-insight")).to_contain_text("4.3% longer")
        page.get_by_label("Comparison alternative").select_option("Firecrawl")
        expect(page.locator("#comparison-insight")).to_contain_text(
            "26.1% fewer LLM tokens"
        )
        expect(page.locator("#comparison-insight")).to_contain_text("29.4% shorter")
        report["checks"].append(
            "Published numbers match the snapshot; comparator shows token and latency trade-offs"
        )
        with page.expect_download() as download:
            page.get_by_role("button", name="Download source snapshot JSON ↓").click()
        assert (
            json.loads(Path(download.value.path()).read_text(encoding="utf-8")) == data
        )
        report["checks"].append("Download exports the exact attributed data snapshot")
        page.locator('nav [data-view="measurements"]').click()
        expect(page.locator("#local-probes .probe")).to_have_count(4)
        expect(page.locator("#memory-rows tr")).to_have_count(3)
        expect(page.locator("#measurements")).to_contain_text("remain unmeasured")
        expect(page.locator("#measurements")).to_contain_text(
            "Do not add these timings"
        )
        report["checks"].append(
            "Local benchmarks are distinct from published comparisons and missing metrics are labeled"
        )
        for width, height in [
            (1440, 1000),
            (1024, 768),
            (768, 1024),
            (390, 844),
            (320, 568),
        ]:
            page.set_viewport_size({"width": width, "height": height})
            for view in [
                "overview",
                "agents",
                "memory",
                "tools",
                "comparison",
                "measurements",
                "sources",
            ]:
                page.evaluate("id=>{location.hash=id}", view)
                expect(page.locator("#title-" + view)).to_be_visible()
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth + 1"
                ), (width, view)
                if width in [1440, 390]:
                    page.screenshot(
                        path=str(
                            report_dir
                            / f"{view}-{'desktop' if width==1440 else 'mobile'}.png"
                        ),
                        full_page=True,
                    )
        report["checks"].append(
            "Seven views fit five desktop/tablet/mobile viewports without page horizontal overflow"
        )
        page.goto((ROOT / "architecture-atlas.html").as_uri() + "#agents/support")
        expect(page.locator("#agent-name")).to_have_text("Travel Support")
        expect(page.locator("#agent-actual")).to_contain_text("recommended extension")
        report["checks"].append(
            "Agent deep links survive reload and proposed support integration stays labeled"
        )
        page.goto((ROOT / "architecture-atlas.html").as_uri() + "#memory/changed")
        expect(page.locator("#memory-scenario")).to_contain_text(
            "evidence_review_required"
        )
        report["checks"].append("Memory scenario deep links survive reload")
        local_links = page.locator(
            'a[href]:not([href^="http"]):not([href^="#"])'
        ).evaluate_all("nodes=>nodes.map(n=>n.getAttribute('href'))")
        for link in local_links:
            assert (ROOT / link.split("#")[0]).exists(), link
        report["checks"].append("Local source/report/presentation links resolve")
        assert not report["runtime_errors"], report["runtime_errors"]
        assert not report["network_requests"], report["network_requests"]
        report["checks"].append("No runtime errors or remote requests")
        browser.close()
    report["status"] = "passed"
    report["passed"] = len(report["checks"])
    (report_dir / "browser-checks.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
