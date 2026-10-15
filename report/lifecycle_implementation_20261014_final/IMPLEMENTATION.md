# Memory core implementation checkpoint

Both paused additions are implemented on the existing FalkorDB graph plus embedded Qdrant architecture. The earlier paired vector experiment remains the reason for keeping this placement; it is not repeated or generalized by this fixture.

## Demonstrated behavior

The persisted graph `lifecycle_demo_0c04cf7dc046` contains 41 actual nodes and 58 relationships. [Open the interactive preview](http://127.0.0.1:1305/) while its local server is running, or inspect the complete [node and edge export](graph.json). The viewer shows a focused selection by default; the export also includes subjects, fields, contexts and original observations.

- An approved protected budget of 1,000 is retained after an accepted change to 600. The earlier version's current score becomes zero; its prior protected score remains recorded. The replacement is protected at one.
- The accepted change is a `SUPERSEDES` relationship with a reason. A later agent proposal of 900 creates an unresolved `CONTRADICTS` relationship. Its numerical score does not override the confirmed instruction; recall reports a dispute.
- An ordinary seat preference weakens with age. Its score includes graded inputs and the fuzzy rules used, rather than being presented as a truth probability. Confirming a discipline does not reconfirm the rest of a profile.
- The trip plan records the old budget version it used and requires review. The unrelated completed seat note remains completed. Handoffs include used versions, current evidence and review reasons.
- A missing phone number returns missing evidence. An employer-to-location query follows explicit references and the confirmed organization identity to Pune, with the supporting path.

All nine scripted behavior assertions pass in [results.json](results.json). The original graph/source data remains separate from this named demonstration fixture. The [implementation guide](../../docs/memory_evolution.md) describes the application and agent interfaces, protection boundary, history semantics and explicit limits. The local [Wayfinder map](../../.scratch/graph-memory-roadmap/map.md) records the accepted placement and remaining work.

## Validation

Final regression run: **155 passed, 4 deselected**, in 74.08 seconds. The four exclusions are the repository's default optional neural/dataset markers. Lifecycle and API checks exercise real FalkorDB and embedded Qdrant; ordinary tests use deterministic embedding fixtures. This demo uses the actual cached `BAAI/bge-small-en-v1.5` model on CPU. Changed Python files pass Ruff checks; the CRLF-aware diff whitespace check passes.

Browser verification found no script errors, checked the claim inspector and both view controls, and verified that the accepted replacement is visibly labelled `SUPERSEDES`. See [verification.json](verification.json) and [screenshot](graph.png).

## Read timings on this fixture

These are ten serial warm reads per path on a local 41-node prepared fixture, after one first read. The p95 is the nearest-rank result. Reads include evidence checks; broad search includes the query embedding and the existing combined retrieval pipeline.

| Question/path | Median | p95 | Checked result |
| --- | ---: | ---: | --- |
| Current budget | 66.81 ms | 72.57 ms | Disputed |
| Phone number | 18.66 ms | 22.29 ms | Missing |
| Employer → location | 93.25 ms | 106.64 ms | Supported, Pune |
| Broad combined budget search | 507.12 ms | 537.65 ms | Returned reconciled claim evidence |

Broad retrieval still needs optimization and representative growth/load measurements. These timings are not comparable to the earlier vector-placement corpus measurements: the questions, data and new checks differ. They establish neither throughput nor a speed improvement. No cache research or new cache architecture was added.

## Remaining boundaries

Applications/agents must supply interpreted semantic claims and source attribution. Plain attributed messages are stored as episodes; automatic free-text interpretation into this contract is not implemented. The local API assumes trusted application callers. Authenticated tenant isolation, an asynchronous receipt/interpretation/notification service, distributed work ownership, crash durability proofs and the teammate's travel application remain work in the route.

Fuzzy parameters are initial configurable defaults. A larger held-out question comparison, mechanism ablations and real-input evaluation remain necessary for research claims or customer readiness.
