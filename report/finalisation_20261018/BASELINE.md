# Baseline: 18 October 2026

Revision: `245829251f5222fbabe0d1c25b00170e9edabd1c`.
No source edits were made before these commands completed. Existing local report
images/snapshot edits and the untracked system report were preserved.

| Suite / command | Result before edits |
| --- | --- |
| `VOYARA_AGENT_MODE=offline python -m pytest tests -q --tb=short` | 341 passed, 2 skipped, 6 deselected, 4 fixture setup errors |
| `VOYARA_AGENT_MODE=offline python -m pytest agents/tests -q --tb=short` | 41 passed |
| `python -m pytest stitch_ai_travel_booking_platform/backend/tests -q` from root | 4 collection errors: missing backend import path |
| Same with repository root and application backend on `PYTHONPATH`, offline | 45 passed, 2 failed |
| `npm --prefix dashboard/frontend test` | 12 passed |
| `npm --prefix dashboard/frontend run test:browser` | 2 passed (retained real feed, not a new plan) |
| `npm --prefix dashboard/frontend run build` | passed |

Core errors: `connected_app` fixture not found in four memory-dashboard tests when
collected with the whole suite. Website failures: undated legacy food request
expected 201 but returned 422; unsupported Business cabin expected 422 but returned
200. Ruff additionally reports an indirect Pydantic item annotation as F821;
this is not yet proof of a runtime NameError.

Services at baseline: website 8000 (PID 40628), relay 8200 (48156), Vite 5174
(48624), FalkorDB 6379 (32760), all loopback. The Python application had been
started before the latest source pull; these checks do not validate fresh startup.

Private logs/JUnit XML: ignored `.scratch/finalise-20261018/`. No raw credentials
or session exports are included. The latest imported catalog/booking merge remains
unverified end-to-end until Phase 2.
