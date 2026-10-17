# Layout and tokens review

Screenshots: `1440x900.png`, `1280x720.png`, and `1100x760-drawers.png`.

Implemented in this phase:
- 56px brand/breadcrumb/session/agent-filter bar; no hero.
- Three full-height columns at 1280px and wider; explorer/inspector drawers below.
- One 140px bottom replay dock (168px on narrow phones), with transport,
  current event, agent lanes, explicit conflict label, scrubber, and time axis.
- Fit-to-stage graph; optional manual canvas sizes remain contained within it.
- Shared color definitions in src/tokens.css; 12px minimum UI text.
- No Connected Agents block, separate event ticker, or status footer.

Validation: production build passed; 8 Node and 19 browser tests passed. After
aligning dock text to the scrubber event, the build and 3 layout checks passed
again. Tests check exact viewport bounds, shared token values, filtering,
transport, resizing, search drawers, and reduced motion. No backend calls.

The replay model and event fixture were not edited. SHA-256 reference values:
- public/events.json: 9A2059A3C0FA5F5DE5B778E5595CAEF3A0576A3BF761EA8EA6CBE7D968F44680
- src/memory.js: 5617D684390DA0CEB24DB2573410EFA8DD605E11BABBCA4537462708A08C7D21

Graph semantics, inspector tabs, chapter markers, URL state, and follow-live
controls remain for the next phase after this layout review.
