# Application and three-tier memory integration verification

Verified on 2026-10-16 in the local Windows/Python 3.12 environment.

| Check | Result |
| --- | --- |
| Full memory suite, including the application integration | 323 passed; 6 optional neural/dataset/GPU tests deselected |
| Focused application integration | 10 passed |
| Existing application backend | 15 passed |
| Frontend production type-check/build | Passed |
| Static syntax/import checks (Ruff E9/F) | Passed |
| Live browser signup, confirmed trip, plan, budget change, reload | Passed |
| Mobile horizontal overflow / browser runtime errors | None found |

The focused tests are included in the full-suite count. The separate backend
suite adds 15 tests, for 338 passing tests across the two final suites.

The automated integration tests use real isolated FalkorDB graphs, temporary
Qdrant stores, the actual shared-memory service/context compiler and actual
LangGraph workflows. Their embedding model is the existing declared offline
fixture. The browser check separately ran the actual application with real
`BAAI/bge-small-en-v1.5` embeddings on `CPUExecutionProvider`.

Covered behavior includes current budget replacement, user/trip isolation,
profile inheritance, restart, retraction without old-value resurrection, source
deletion, unsupported rules, insufficient budgets, unknown destinations, pending
updates, unavailable storage and bounded retries when a draft becomes stale.

The browser check exercised the visible confirmation form and resumed the chat
after reloading. It also checked the final helper at 390px width. Its compact
diagnostics contain no credentials or context proof tokens.

- [Full suite JUnit](full-suite.xml)
- [Focused integration JUnit](integration-tests.xml)
- [Backend JUnit](backend-tests.xml)
- [Browser diagnostics](browser-check.json)
- [Desktop screenshot](desktop.png)
- [Mobile screenshot](mobile.png)
- [Reproduction and limitations](../../docs/application_memory_integration.md)

This verifies the connected CPU/catalog demonstration. It does not measure a
hosted generative model, application-level CUDA matching, supplier availability,
external booking execution, production load or general conversational quality.
The existing locked frontend dependency audit findings were not remediated by
this integration. No runtime databases, user journals or credentials are included.
