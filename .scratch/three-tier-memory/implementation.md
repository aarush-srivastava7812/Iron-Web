# Three-Tier Memory: Incremental Implementation and Checks

Execution authorized by the user's instruction on 2026-10-15 to build and test every part while building. The resolved decision map remains architecture history; this log records execution and verification.

| Stage | Check before advancing | Observed result |
| --- | --- | --- |
| Existing shared/lifecycle baseline | Run existing actual-store tests before new work | Initially blocked by stopped/broken Docker; rerun passed after repairing only temporary IPC startup state |
| Profile/card contracts | New tests first failed because the component was absent; implement and rerun | 8 passed: current evidence, missing/disputed fields, guidance labels and schema bounds |
| Durable freshness generation | Tests first failed on missing generation method; add transactional journal triggers | 11 combined checks passed; idempotency, restart, rollback, retry, withdrawal and redaction covered |
| RAM/cache/token limits | Tests first failed on missing cache; implement and rerun | 14 combined checks passed; LRU, ownership keys, expiry, payload accounting and actual tokenizer caps |
| Task/profile/mood assembly | Tests first failed on missing assembler; implement and rerun | 19 combined checks passed; exact trip requirements, conservative profile fallback, mood expiry and mandatory overflow |
| Authenticated context integration | Test first failed on missing service interface; wire coherent snapshots and endpoints | 53 shared/lifecycle/context integration checks passed using actual temporary graph/vector stores |
| CPU/GPU card adapter | Tests first failed on absent adapter; implement CPU admission/ownership, then actual CUDA checks | 23 component checks passed; CUDA test exposed missing CUDA 13 libraries, so validate in the retained CUDA 12 runtime without replacing the installed environment |
| Overflow regression | Add a targeted check for optional hot details that exceed one half | Test caught lost optional evidence; fixed routing into additional evidence and rerun passed |
| HTTP generation/handoff | Run real HTTP client callback while changing the budget | Stale response discarded/rebuilt; missing facts skip generation; retries bounded; context dependencies reach handoff |
| Configuration | Test first failed on missing loader; implement strict local configuration | 11 configuration/token/assembly checks passed; no tokenizer/model download at setup |
| CUDA deletion | Real GPU plus actual shared service | 2 opt-in CUDA tests passed: resident matching parity, clearing, revoked handles and deletion |
| Combined regression | Run new tests with existing shared/lifecycle tests | 83 passed, 2 optional GPU checks deselected; [JUnit record](../../report/three_tier_incremental_tests_20261015.xml) |
| Restart and agent authority | Add explicit integration edge cases | 2 additional checks passed: cold rebuilding rejects old proofs; agent proposals remain unconfirmed |
| Real neural-model demonstration | Real BGE embeddings, tokenizer, GPU selection, private users, changes, handoff and redaction | All declared scenarios passed; [final-source results](../../report/three_tier_20261015_verified/results.json) |
| Late temporal/type edge cases | Introduce targeted checks before their fixes | Caught expiry during assembly and Python boolean/number equality collapsing distinct JSON values; both fixed and focused checks passed |
| Prompt overlap | Add an explicit overlapping-card check before fixing assembly | Caught repeated hot/card facts; deduplication fixed; 28 contract/assembly/service checks passed |
| Final verification | Full ordinary suite after the last source change, actual CUDA checks, and final-source demonstration | **215 ordinary tests passed**, 6 optional tests deselected; **2 actual CUDA tests passed**. [Ordinary JUnit](../../report/three_tier_final_suite_20261015.xml), [CUDA JUnit](../../report/three_tier_cuda_tests_20261015.xml). Final demonstration source hashes match the shipped modules; 66 local documentation/report links checked. |

The initial real-model run completed its behavior checks but failed while detecting optional package metadata. The reporter was fixed to record absent distributions explicitly, and the complete run was repeated in a fresh directory. The partial earlier directory is retained rather than overwritten.

Docker startup failed on an inaccessible old `dockerInference` socket. Individual move/removal failed. With the backend stopped, its verified temporary `Docker/run` directory was renamed to `run.stale-three-tier`, preserving its contents; Docker recreated IPC state and the existing FalkorDB container became healthy. No container volume, graph, user source memory or Docker settings were reset.

The optional ONNX builder was installed under ignored `data/context_dependencies`; the GPU check used already-retained `data/evaluation_runtime/cuda12_ort1232` and CUDA library directories through process-local import/DLL paths. The installed application environment and `config.yaml` were preserved.

The actual-model run found CPU warm card selection faster than GPU for its tiny catalog. CPU remains the default; GPU residency is a verified option. Timings are descriptive, ran alongside regression activity, and do not establish a general speedup or final-answer quality. The consumer response model itself was not invoked.

The [usage guide](../../docs/three_tier_memory_usage.md) describes the implemented API, setup, bounds and remaining integration limits. Travel-site combination is still a separate next step.

## Travel-audit fixes authorized on 2026-10-15

The user explicitly requested applying the fixes after the findings-only travel audit. The original audit remains unchanged.

| Change | Failure reproduced before implementation | Verification after fix |
| --- | --- | --- |
| Discover all scoped saved atomic fields; promote rules/instructions | A flight brief omitted `max_walk_metres`; the new test failed on that missing field | All three task briefs include custom rules and scenario facts; context-only work becomes stale after the walking change |
| Inherit trip mood into an empty session | New test found no relaxed card | Inheritance, explicit overrides, disputed/unconfirmed blocking and source-timed expiry pass |
| Trip-aware readiness and snapshots | Unrelated pending trip raised `PendingMemory` for Goa | Goa remains warm/current while another trip is pending and after processing; global and misleading-envelope changes still block; direct graph changes revoke proofs |
| Trip-aware task gates | Handoff still raised `PendingMemory` for an unrelated trip | Handoff, leasing, completion and evidence/prerequisite scope checks pass; global/unknown dependencies remain conservative |
| Multi-clause local interpretation | Original travel intake and a simple two-clause message returned no claims | Original intake yields 14 source-grounded fields; unknown remainders, conflicting amounts/currencies, conditional wording and questions are rejected without partial acceptance |
| Preserve source data when optional cards are removed | Large-card test lost `one specific museum` from the prompt | Removed card's facts and IDs remain in additional evidence |
| Preserve protected profile and session requirements | Trip preference hid a protected profile food rule | All scoped hard rules survive; unlike values for a hard field yield `scope_conflict` |
| Work argument compatibility | New readiness traversal raised `TypeError` on invalid handoff input | Existing public input validation remains in effect |

Final verification: **236 ordinary tests passed**, 6 optional deselected; **2 actual CUDA tests passed**; Ruff passed for edited modules/tests. The [final-source travel replay](../../report/travel_agent_fixes_20261015_final/README.md) passes **24/24 checks**. Both work controls use only context-provided IDs, and both detect the 500 m → 50 m change. The revised INR 58,600 fixture draft fits the INR 65,000 cap; the later 50 m requirement correctly stops the simulated reviewer because no supplied hotel qualifies.

The first replay retained an audit-only incorrect status route; the final-source replay corrects it and preserves the earlier evidence. No application configuration, travel-site integration, booking, commit or deployment was performed.
