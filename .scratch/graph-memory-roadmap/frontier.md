# Next Work and Decisions

Generated snapshot of the local Wayfinder tracker. The map and individual tickets remain canonical; this file stores no decision answers.

[Shared Agent Memory: Hackathon, Research and Reuse](map.md)

## First memory-core task

The first memory-core contract and local verification are complete. See the [shared-service guide](../../docs/shared_memory_service.md), [actual two-agent demo](../../report/shared_memory_20261014_final/results.json), and [delivery route](../../docs/memory_delivery_route.md). The remaining map decisions need the real teammate application/ownership and actual pilot partner. Larger blind/model-driven research and event submission remain future execution gates.

## Available now

- [Focused Travel Demonstration and Two-Person Boundary](issues/03-focused-demo-and-team-boundary.md)
- [First Company Pilot and Product Readiness](issues/09-first-company-pilot-and-product-readiness.md)

## Other open work and decisions

| Work or decision | Waiting on |
| --- | --- |
| [Staged Route, Integration Gates and Cut Lines](issues/10-staged-route-and-cut-lines.md) | [Focused Travel Demonstration and Two-Person Boundary](issues/03-focused-demo-and-team-boundary.md); [First Company Pilot and Product Readiness](issues/09-first-company-pilot-and-product-readiness.md) |

## Decision relationships

Arrows mean “this result or decision is needed before the next one.” Green items contain completed research or user decisions, blue items are available work/discussions, and orange items wait on prerequisites.

```mermaid
flowchart TD
    D01["Event Boundaries and FalkorDB Guarantees"]
    D02["Existing Research and a Testable Paper Contribution"]
    D03["Focused Travel Demonstration and Two-Person Boundary"]
    D04["Memory Changes, Evidence and Authority"]
    D05["Live Ingestion, Shared Tasks and Private User Spaces"]
    D06["Retrieval and Fuzzy Scores: Separate Responsibilities"]
    D07["Vector Placement Within the Existing Architecture"]
    D08["Research Hypothesis and Fair Evaluation"]
    D09["First Company Pilot and Product Readiness"]
    D10["Staged Route, Integration Gates and Cut Lines"]
    D11["FalkorDB Versus Qdrant: Vector Latency and Output Quality"]
    D12["Existing Architecture, Reference Use and Work Order"]
    D07 --> D04
    D01 --> D05
    D04 --> D05
    D04 --> D06
    D01 --> D07
    D11 --> D07
    D12 --> D07
    D02 --> D08
    D04 --> D08
    D06 --> D08
    D07 --> D09
    D03 --> D10
    D05 --> D10
    D06 --> D10
    D07 --> D10
    D08 --> D10
    D09 --> D10
    D01 --> D11
    D12 --> D11
    classDef researched fill:#204c3b,stroke:#8cd6b3,color:#eefaf4
    classDef ready fill:#234761,stroke:#9dcaed,color:#f2f8fc
    classDef waiting fill:#51422a,stroke:#dbbd81,color:#fcf7eb
    class D01 researched
    class D02 researched
    class D03 ready
    class D04 researched
    class D05 researched
    class D06 researched
    class D07 researched
    class D08 researched
    class D09 ready
    class D10 waiting
    class D11 researched
    class D12 researched
```

To work a ticket, claim it before investigating. Human decisions remain open until the live discussion resolves them. Execution status and evidence live in the individual tickets.
