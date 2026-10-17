# Travel chatbot and personal catalog verification — 17 October 2026

The implementation follows the supplied Voyara reference images and written
plan, scoped to a local hackathon demo. It reuses the existing server-side
NVIDIA configuration. No credentials are included in these artifacts.

Verified results:

- 27 focused regression tests passed: chat/workspace/PDF, plan editing,
  application memory integration and website catalog.
- Seven targeted tests passed again after the final shared-stay synchronization
  change, with `VOYARA_AGENT_MODE=offline`.
- The standalone existing backend API suite passed (15 tests).
- The opt-in hosted journey test passed: two conversational draft turns,
  explicit confirmation, all seven specialist executions in NVIDIA mode, and
  authenticated PDF export. See `live_journey.json`.
- Nine browser checks passed, including live NVIDIA chat with exact server-owned
  pricing, retry after provider failure, history, hotel and flight edit links,
  shared selections, PDF download, logout isolation and responsive widths.
  See `browser_checks.json` and the accompanying screenshots.
- Frontend production build, Python undefined-name/import checks and Git patch
  whitespace checks passed.
- The sample PDF has nine pages and eight private edit links. The regional guide
  layout was visually inspected. `Kerala_Travel_Book.pdf` uses a hosted specialist
  result; `Browser_Travel_Book.pdf` comes from the isolated browser journey.
- The refreshed local app at port 8088 returned HTTP 200 for health and the
  regional photograph, and exposed the chat/export routes and catalog with
  twelve hotels and twelve experiences.

Tests use synthetic inventory and isolated real graph/vector stores with the
declared offline embedding fixture. Hosted checks verify NVIDIA conversational
and specialist decisions; they do not verify live embeddings or supplier data.
Sample trip IDs identify verification fixtures rather than a real holiday.
Downloaded PDFs remain fixed, owner-protected snapshots.

See [the usage guide](../../docs/travel_chat_catalog.md) for the demo flow,
shared data model, pricing scope and commands.
