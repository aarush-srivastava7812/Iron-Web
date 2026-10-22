"""Build an offline architecture atlas from source-backed comparisons and local receipts."""

from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "report/architecture_atlas"

AGENTS = [
    dict(
        id="orchestrator",
        name="Orchestrator",
        code="travel_orchestrator",
        role="Delegate tasks and coordinate the trip.",
        recommendation="Decide when live web research is necessary.",
        actual="Coordinates specialist execution and evidence flow. No direct TinyFish research adapter for this role.",
        connection="shared",
        value="Conditional",
        topic="Research policy",
        x=50,
        y=5,
    ),
    dict(
        id="consultant",
        name="Trip Consultant",
        code="trip_consultant",
        role="Understand traveler needs and recommend trip types.",
        recommendation="Usually unnecessary; use live research for unfamiliar destinations.",
        actual="Uses local requirements and shared eligible evidence. Destination research is performed by research specialists.",
        connection="shared",
        value="Occasional",
        topic="Traveler brief",
        x=79,
        y=14,
    ),
    dict(
        id="explorer",
        name="Explorer Agent",
        code="explore_agent",
        role="Discover attractions, activities and local experiences.",
        recommendation="Search and fetch current destination information.",
        actual="Atlas directly uses the TinyFish research adapter in TinyFish mode; can return discovery leads when venue details are unverified.",
        connection="direct",
        value="High",
        topic="Destinations",
        x=94,
        y=40,
    ),
    dict(
        id="stay",
        name="Stay Agent",
        code="stay_agent",
        role="Find suitable hotels and stays.",
        recommendation="Research hotel details; confirm date-specific prices and availability with suppliers.",
        actual="Haven directly researches public hotel sources and indicative rates. Trip dates stay local; this does not verify live availability.",
        connection="direct",
        value="High",
        topic="Hotels + stays",
        x=88,
        y=70,
    ),
    dict(
        id="food",
        name="Food Agent",
        code="food_guide_agent",
        role="Recommend restaurants for cuisine, location and budget.",
        recommendation="Discover menus, opening hours, restaurants and source URLs.",
        actual="Saffron directly researches public restaurant and menu sources. Private dietary preferences and budget filtering stay local.",
        connection="direct",
        value="High",
        topic="Food + menus",
        x=65,
        y=89,
    ),
    dict(
        id="guide",
        name="Tour Guide",
        code="tour_guide_agent",
        role="Explain places, culture and historical context.",
        recommendation="Research facts and current visiting information when needed.",
        actual="Roam directly researches attraction sources, indicative admission fees and visiting-hour caveats.",
        connection="direct",
        value="Medium",
        topic="Attractions",
        x=35,
        y=89,
    ),
    dict(
        id="planner",
        name="Itinerary Planner",
        code="itinerary_planner",
        role="Arrange activities, travel times and meals.",
        recommendation="Prefer the database and routing services; use TinyFish evidence to fill information gaps.",
        actual="Uses local planning and validation plus the shared evidence snapshot. No direct TinyFish adapter. Live routing is not established by this diagram.",
        connection="shared",
        value="Gap filling",
        topic="Schedule",
        x=12,
        y=70,
    ),
    dict(
        id="budget",
        name="Budget Reviewer",
        code="budget_booking_agent",
        role="Check total estimated cost against the budget.",
        recommendation="Prefer structured prices and supplier quotes; gather indicative web prices when needed.",
        actual="Computes seeded estimates locally, with source-backed indicative prices where available. No direct TinyFish adapter; no real booking is executed.",
        connection="shared",
        value="Indicative",
        topic="Cost review",
        x=6,
        y=40,
    ),
    dict(
        id="support",
        name="Travel Support",
        code="travel_support_agent",
        role="Help with disruptions, cancellations and changes.",
        recommendation="High value for current advisories, operator policies and travel updates.",
        actual="Uses shared evidence today. A dedicated advisory/policy TinyFish research adapter is a recommended extension, not an implemented direct integration.",
        connection="shared",
        value="High · proposed",
        topic="Support",
        x=21,
        y=14,
    ),
]

TOOLS = {
    "search": dict(
        name="Search",
        status="Default discovery path",
        endpoint="GET https://api.search.tinyfish.ai",
        request="Public destination + research topic",
        response="Ranked URLs, titles and snippets",
        roles=["explorer", "stay", "food", "guide"],
        implementation="The four research roles call TinyFishSearchClient.research. Search results are discovery leads, not verified venue attributes.",
        example="Jaipur attractions official tourism",
        next="Selected URLs → Fetch; source links can remain useful when extraction is unavailable.",
    ),
    "fetch": dict(
        name="Fetch",
        status="Conditional reading + memory refresh",
        endpoint="POST https://api.fetch.tinyfish.ai",
        request="Selected public source URLs; format=markdown",
        response="Readable page text and source URLs",
        roles=["stay", "food", "guide"],
        implementation="Stay, Food and Tour Guide call Fetch for venue extraction when the configured reader is available. Explorer normally stays at discovery. The destination-memory refresh service separately uses Search + Fetch.",
        example="Read public hotel, menu or attraction pages",
        next="Page text → optional NIM reader → exact quote/name gate → versioned evidence memory.",
    ),
    "agent": dict(
        name="Agent",
        status="Optional client · not the default",
        endpoint="POST /v1/automation/run-async · GET /v1/runs/{id}",
        request="Public HTTPS URL + bounded read-only goal + output schema",
        response="Run ID → polled status → schema-checked research result",
        roles=["explorer", "stay", "food", "guide"],
        implementation="TinyFishClient can be injected into the four research adapters. It submits an async automation run, polls until completion and cancels on timeout. The default runtime injects TinyFishSearchClient instead; no automatic Fetch-to-Agent escalation is wired.",
        example="Open a public attraction page and read a detail behind a tab",
        next="Structured result → local schema/source-URL checks → research result. It is not a confirmed booking or an automatically quote-verified SQL memory version.",
    ),
}

MEMORY_STEPS = [
    dict(
        id="research",
        title="TinyFish → research payload",
        label="1 · Research",
        function="destination_research.retrieve() / submit()",
        detail="Search returns URLs. Fetch returns public page text. A completed destination job keeps pages and proposed exact quotations in DestinationResearch.payload.",
        file="stitch_ai_travel_booking_platform/backend/app/destination_research.py",
        output="sources[] · pages[] · findings[topic].statements[]",
    ),
    dict(
        id="gate",
        title="Payload → exact-quote gate",
        label="2 · Validate",
        function="external_memory.ingest(db, job)",
        detail="Each quotation must occur verbatim in a fetched page with an accepted public URL. A snippet alone cannot become a stored statement. Unsupported quotations are dropped; empty evidence stays missing.",
        file="stitch_ai_travel_booking_platform/backend/app/external_memory.py",
        output="Accepted source statements; fingerprint; freshness; conflict candidate",
    ),
    dict(
        id="sql",
        title="Validated statements → SQL history",
        label="3 · Persist",
        function="ExternalKnowledgeVersion + ExternalMemoryEvent",
        detail="Version identity includes the owner, research job and topic. Rows retain previous_id, quote/URL pairs, retrieved_at and expires_at. SQL commits before optional graph indexing, preserving replayable evidence history.",
        file="stitch_ai_travel_booking_platform/backend/app/models.py",
        output="Owner-scoped durable versions + lifecycle events",
    ),
    dict(
        id="graph",
        title="SQL version → FalkorDB Source + vectors",
        label="4 · Index",
        function="external_memory.sync_graph(db, traveler, rows)",
        detail="engine.add writes a source-only external_evidence memory with a vector. Explicit graph links connect the source to its destination, topic, cited page and an available previous source version. No Traveller preference claims are created.",
        file="stitch_ai_travel_booking_platform/backend/app/external_memory.py",
        output="Source + embedding + ABOUT_EXTERNAL_ENTITY / TOPIC + CITES + NEWER_OBSERVATION",
    ),
    dict(
        id="recall",
        title="SQL + optional ranking → eligible evidence",
        label="5 · Recall",
        function="external_memory.recall(..., traveler=...)",
        detail="Recall selects the owner's latest topic versions, withholds missing, stale and conflict-candidate evidence, and optionally uses FalkorDB vectors to rank eligible versions. SQL still supplies exact evidence if the graph is unavailable.",
        file="stitch_ai_travel_booking_platform/backend/app/external_memory.py",
        output="evidence[] · missing_topics · stale_topics · conflict_topics · refresh",
    ),
    dict(
        id="context",
        title="Eligible evidence → every specialist's context",
        label="6 · Share",
        function="agent_runtime.reply() → ThreeTierGateway → MemoryContext.external_evidence",
        detail="The runtime obtains catalog.external_context before creating the workflow. ThreeTierGateway carries that eligible snapshot separately from confirmed preference items. Specialists receive the same external evidence rather than issuing a new lookup for each read.",
        file="agents/memory_gateway/three_tier.py",
        output="Scoped user memory + a separate external_evidence[] field",
    ),
    dict(
        id="refresh",
        title="Recall gaps → refresh; changed sources → review",
        label="7 · Refresh",
        function="recall() → destination_research.submit(); ingest() → invalidate_trips()",
        detail="Missing, expired or conflicting topics can queue bounded background Search/Fetch. Running work is reused and recent failures have a cooldown. A changed high-impact source version flags relevant saved plans for review; it does not silently rewrite the itinerary.",
        file="stitch_ai_travel_booking_platform/backend/app/external_memory.py",
        output="Refresh job ID; new version; evidence_review_required; dashboard events",
    ),
]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main():
    published = load("report/architecture_atlas/published-comparison.json")
    site = load("report/tinyfish_memory/site-smoke.json")
    live = load("report/tinyfish_memory/live-research.json")
    lifecycle = load("report/tinyfish_memory/benchmark.json")
    memory = load("report/tinyfish_memory/memory-benchmarks.json")
    payload = dict(
        agents=AGENTS,
        tools=TOOLS,
        memory_steps=MEMORY_STEPS,
        published=published,
        site=site,
        live=live,
        lifecycle=lifecycle,
        memory=memory,
    )
    # Script-safe JSON; no remote requests, API keys, private sessions or user records are embedded.
    encoded = (
        json.dumps(payload, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    document = (ROOT / "scripts/architecture_atlas.template.html").read_text(
        encoding="utf-8"
    )
    script = (ROOT / "scripts/architecture_atlas.js").read_text(encoding="utf-8")
    rows = "".join(
        '<tr><th scope="row">'
        + escape(a["name"])
        + "</th><td>"
        + escape(a["role"])
        + "</td><td>"
        + escape(a["recommendation"])
        + '</td><td><span class="status '
        + a["connection"]
        + '">'
        + ("Direct adapter" if a["connection"] == "direct" else "Shared evidence")
        + "</span></td></tr>"
        for a in AGENTS
    )
    document = (
        document.replace("{{ROLE_ROWS}}", rows)
        .replace("{{DATA}}", encoded)
        .replace("{{SCRIPT}}", script)
    )
    (ROOT / "architecture-atlas.html").write_text(
        document, encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "output": "architecture-atlas.html",
                "agents": len(AGENTS),
                "bytes": len(document.encode()),
            }
        )
    )


if __name__ == "__main__":
    main()
