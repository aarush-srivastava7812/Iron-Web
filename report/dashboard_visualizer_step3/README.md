# Dashboard review: steps 1–3

- `desktop.png`: 1600 × 1000 browser capture.
- `mobile.png`: 390px viewport capture of the responsive layout.
- Data: exactly 40 local mock events and three agents; one computed stale-write conflict.
- Checks: production build, six event/graph tests and six browser tests passed.
- No backend/API requests are made by this React preview.

Run `npm run dev` in `dashboard/frontend` and open http://127.0.0.1:5174/.
Agent wiring, heatmap, decay widgets and full scrub replay remain deferred.
