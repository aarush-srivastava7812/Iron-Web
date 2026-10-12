# Research workflows

The modules in this directory are optional and are not imported by the ordinary application API.

`ResearchEngine` exposes three project-owned mechanisms:

- `entity_neighborhood`: dense retrieval with one-hop entity expansion.
- `dense_lexical_fusion`: actual reciprocal-rank fusion of dense ranks and keyword-overlap ranks within the dense shortlist. It is not a BM25 index.
- `temporal_room`: grouping of a dense shortlist by UTC day, followed by selection of the two groups with the highest summed scores.

These mechanisms do not implement Mem0, Zep or MemPalace. The normal engine rejects those brand names as search modes.

The standalone contrastive experiment samples lower-ranked candidates and computes a diagnostic margin. It does not train a model, establish that sampled items are wrong, or contribute to the ordinary application's score. Earlier Optuna/sweep and phase-report code is preserved in the legacy archive.

## Genuine package adapters

`upstream/packages.py` contains optional adapters that call the actual `mem0ai`, `zep-cloud` and `mempalace` packages. `upstream/backend.py` adapts them to the shared local runner. `upstream/compare.py` groups questions by complete conversation history and uses isolated namespaces.

```powershell
python research/upstream/compare.py locomo mem0 --slice-version data/benchmark_slices/v2/locomo --run-id sdk_example
```

Install the selected package profile in a separate environment. Credentials belong in the process environment. Package ingestion/search errors are surfaced, and returned identifiers must map to the selected corpus. The Mem0 configuration sets `infer=False`. The GPU option is implemented for the MemPalace adapter; other package providers are uninspected by this adapter.

The comparison uses local retrieval metrics and first-context-line answers. It does not run the official upstream answer-scoring protocols. The cleanup verification exercised the shared backend contract with a declared fixture package; live SDK, hosted extraction and GPU model runs were not repeated.
