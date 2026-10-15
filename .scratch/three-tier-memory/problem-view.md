# Problems the Three-Tier Design Must Solve

Planning asset, 2026-10-14. These are counterexamples to test, not bugs reproduced in a new cache implementation. The new cache does not exist yet. Detailed resolutions live in the [decision map](map.md).

| Concrete problem | What goes wrong without a rule | Required behavior |
| --- | --- | --- |
| Warm luxury card retains a INR 100,000 limit; the user changes it to INR 60,000 | The model plans against the old limit | Block while the event is pending; rebuild from the accepted change; dependent work needs review |
| An unclear confirmed message arrives after the cache was warmed | The cached old requirement appears to have been reapproved | Preserve the current service's `needs_review` gate even on cache hits |
| User usually likes hikes, but asks for a restful family trip | A general persona overrules the current trip | Keep general preferences and exact trip requirements separate; use the explicit trip requirement for this task |
| Yesterday's adventurous mood remains in a card | A temporary state becomes a permanent preference | Require an explicit mood/session scope and expiration; do not guess a lasting personality |
| Planner and reviewer use cards containing different budget versions | A handoff hides why an earlier plan changed | Carry exact used claim IDs and current handoff state; reacquire evidence before continuing |
| Two users both have a trip named `summer` | A task-name cache key leaks another user's memory | Bind every private entry and GPU slot handle to authenticated user space, subject and exact scope |
| Someone copies a `persona.md` file to GPU memory | The model never consumes the bytes | Define an actual GPU matching representation and explicitly serialize selected text into model context |
| An existing GPU embedder produces a CPU NumPy array | GPU inference is mistaken for resident card storage | Verify device-resident tensors and live resident-byte accounting independently |
| Every card becomes a long prompt | More tokens increase prefill cost and bury constraints | Bound card count and tokens; deduplicate evidence; reject missing/overflowing mandatory constraints |
| A profile fills more than its assigned half | Silent truncation loses important rules | Keep equal caps; move soft detail to cards; report mandatory-capacity overflow |
| The GPU is occupied or out of memory | Memory access fails despite usable durable memory | Evict/rebuild derived cards and use the equivalent CPU selection path |
| Accepted evidence is deleted but card text/tensors survive | The cache resurrects removed information | Invalidate host/GPU derivatives and in-flight contexts; rebuild only from retained evidence |
| A model returns a recommendation while the user submits a change | A valid-at-start answer becomes stale before emission | Recheck readiness and generation before emitting; discard/reassemble if changed |
| A stale remote booking happens between validation and provider execution | Task completion checks cannot undo the external action | Keep the provider's conditional action/idempotency contract separate; no new exactly-once promise |
| Caching is expected to solve slow ingestion | Graph-copy writes remain expensive | Measure reads and writes separately; cache work does not remove the current graph-copy bottleneck |

The central risk is **a fast answer built from the wrong current requirements**. Cache hit rate is useful only after current evidence, user isolation and missing-information behavior are preserved.
