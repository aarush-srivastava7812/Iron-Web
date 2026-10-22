"""Explanatory sections for the architecture presentation, grounded in local code."""
from html import escape


def cards(items):
    return '<div class="explanation-grid">' + ''.join(
        f'<article><span class="step-label">{i:02d}</span><h3>{escape(title)}</h3><p>{escape(body)}</p></article>'
        for i, (title, body) in enumerate(items, 1)
    ) + '</div>'


def section(chapter, title, lead, items, takeaway):
    return (f'<p class="eyebrow">{escape(chapter)}</p><h2>{escape(title)}</h2>'
            f'<p class="slide-lead">{escape(lead)}</p>' + cards(items)
            + f'<p class="takeaway"><b>Key point</b> {escape(takeaway)}</p>')


def explanatory_sections():
    return {
        "system": section("01 / System overview", "Three parts, with distinct responsibilities.",
            "Voyara coordinates a travel conversation, Iron Web preserves memory, and TinyFish supplies current public web evidence.", [
                ("Voyara · product + agents", "The traveler explains needs and revises a trip. Nine local agent roles coordinate research, itinerary planning, budget review and support. Trips and user edits remain editable and persistent."),
                ("Iron Web · shared memory", "FalkorDB stores source vectors alongside graph relationships and claim history. Exact claim recall and semantic discovery serve different questions. SQL separately preserves trips and external evidence versions."),
                ("TinyFish · web research", "Search discovers URLs; Fetch reads public pages. Quoted evidence can enter the destination research ledger. An optional Agent adapter supports asynchronous browser goals for research roles."),
            ], "Personal preferences and public web observations have separate authority and freshness rules."),
        "vector-memory": section("02 / Memory foundations · vector", "Find relevant memories even when words change.",
            "Vector retrieval represents source text as embeddings and searches for semantically nearby sources.", [
                ("What enters the index", "A stored source has text, an identity and metadata. Its embedding makes it discoverable without requiring the next query to repeat the original wording."),
                ("Why it is useful", "A query about peaceful accommodation can discover relevant source text about quiet stays. This is an illustration of semantic matching, not a scored query from our benchmark."),
                ("What similarity cannot decide", "A nearby result is a candidate, not a truth certificate. Scope, validity and source status still matter. Exact preference values and claim history require structured recall."),
            ], "Semantic similarity improves discovery; it does not replace provenance or confirmation."),
        "graph-memory": section("02 / Memory foundations · knowledge graph", "Keep the relationships behind a memory.",
            "The graph connects sources, entities and structured claims so the system can inspect where a value came from and how it changed.", [
                ("Claims + provenance", "Structured claims associate a subject with a field and value, backed by source records. Scope, authority and confirmation rules determine how claims are accepted and recalled."),
                ("Versions + time", "Claim history preserves changes rather than treating every old statement as the latest value. Historical exact recall needs an explicit subject, field and relevant time."),
                ("How vectors complement it", "Graph structure supports explicit relationships, while embeddings find related source text. Both use shared source identities in FalkorDB; the system does not maintain two unrelated memory copies."),
            ], "Web evidence is indexed as external source evidence; it does not become a confirmed traveler preference."),
        "evidence": section("03 / TinyFish → durable memory", "From a web page to reusable evidence.",
            "The implemented persistence path starts with a completed destination research job using Search and Fetch.", [
                ("Capture + check", "Search returns candidate URLs and Fetch returns readable pages. An evidence quote must occur in the fetched page and have a valid public source URL. A snippet alone cannot satisfy this gate."),
                ("Save + index", "SQL commits an evidence version with its owner, source URL, quote, timestamps and expiry. Graph indexing then adds source vectors and links to external entities, topics, cited pages and older observations."),
                ("Recall + refresh", "Recall selects eligible evidence for the owner and excludes stale or conflicting candidates. Missing evidence can queue bounded background research. Changed high-impact evidence flags dependent plans for review."),
            ], "SQL evidence stays durable if graph indexing is pending. A quote match verifies provenance, not factual truth."),
        "tools": section("03 / TinyFish tools", "Choose a tool for the research step.",
            "The three tools have distinct contracts. Their availability should not be confused with every agent calling every tool.", [
                ("Search · discover", "Default research client for Atlas, Haven, Saffron and Roam. It submits public destination or topic queries and returns candidate sources. Traveler preferences are not included in the public query."),
                ("Fetch · read", "Turns selected URLs into readable page content. Destination research uses it for evidence capture. Haven, Saffron and Roam use it conditionally for venue extraction when a reader is configured."),
                ("Agent · interact", "Optional injectable client for asynchronous browser goals, with polling and timeout cancellation. It can replace the default research client; there is no automatic Search → Fetch → Agent escalation."),
            ], "Direct role results need an explicit bridge before entering the SQL evidence ledger."),
        "workflow": section("04 / Product workflow", "How a request becomes a revisable trip.",
            "Example walkthrough: the traveler requests a short trip, then changes a preference or revisits saved research.", [
                ("Understand + delegate", "The consultant and orchestrator interpret the request and coordinate specialist roles. Relevant stored preferences and eligible external evidence become context for the task."),
                ("Research + plan", "Research roles discover destination, stay, food and attraction information. Planning and budget roles consume shared evidence and structured estimates. Research output is not a reservation or a verified booking quote."),
                ("Save + revise", "A trip can be saved, reloaded and duplicated. A changed preference can guide a revision. Changed external evidence can flag a plan for review; it does not silently rewrite or book the trip."),
            ], "The dashboard separates saved project replay from the explicit Follow live mode."),
        "conclusion": section("06 / Conclusions + next steps", "A shared memory with a refreshable view of the world.",
            "The architecture combines semantic discovery, structured recall and sourced web research. Evaluation measures these responsibilities separately.", [
                ("Implemented", "Shared vector + graph storage, nine coordinated roles, Search/Fetch destination research, versioned external evidence, freshness checks and editable trip workflows."),
                ("Measured", "Controlled evidence reuse reduces repeated fixture HTTP requests. Local retrieval samples have mixed results. Product checks cover saved trips and dashboard behavior; they are not a live answer-quality benchmark."),
                ("Next validation", "Evaluate larger samples and generated answers, test historical-time recall, measure hosted end-to-end latency, and validate the optional Agent path plus the role-to-ledger bridge."),
            ], "Keep measured results, architectural illustrations and optional integrations clearly distinguished."),
    }
