# Iron Web memory

Text memory backed by embedded Qdrant and a FalkorDB graph service. The application saves, updates, deletes and retrieves memories, supports explicit validity intervals, and exposes a local dashboard and an in-process Python tool adapter.

The supported application is in `memory/`, `server.py`, and `web/`. Optional experiments are in `research/`. Earlier designs, phase scripts, reports and unused source are preserved under `archive/2026-10-12/`; they describe the earlier implementation.

## Run

Use Python 3.12 and Docker Desktop (or an existing FalkorDB service). For a new CPU environment:

```powershell
py -3.12 -m venv .venv-cpu
.\.venv-cpu\Scripts\python.exe -m pip install -r requirements.txt -r requirements/dev.txt
docker compose up -d --wait falkordb
.\.venv-cpu\Scripts\python.exe server.py
```

Open `http://127.0.0.1:8080/`. Model files may download on the first operation that needs them. Importing the public API, reading device status, and graph-only searches do not initialize neural models.

The default graph service is `127.0.0.1:6379`, graph `iron_web`. Compose stores its data in the persistent `iron_web_falkordb_data` volume and binds the database port to the local computer. Connection settings live under `falkordb` in `config.yaml`; credentials come from `FALKORDB_USERNAME` / `FALKORDB_PASSWORD`. `FALKORDB_HOST`, `FALKORDB_PORT`, `FALKORDB_GRAPH_NAME` and `FALKORDB_TLS` override configuration. Python callers can select an isolated graph with `MemoryEngine(graph_name="my_graph")`.

For an existing Kùzu installation, preserve its file and run the verified importer once:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements/migration.txt
.\.venv\Scripts\python.exe scripts/migrate_kuzu_to_falkordb.py --source data/kuzu/memory.db --graph-name iron_web
```

The importer opens the legacy database read-only, compares all nodes/relationships/properties, and refuses to overwrite a different populated target graph. Kùzu is required only by this optional import utility. See [migration details](docs/falkordb_migration.md).

The existing `.venv` launcher was repaired and its installed packages were preserved. The CPU and GPU dependency profiles are intended for separate environments. Hosted extraction additionally uses `requirements/nim.txt`, `extraction_policy: nim`, and the process environment variable `NVIDIA_API_KEY`. The default extraction policy is `none`, which saves text without inventing entities.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pytest -m dataset
.\.venv\Scripts\python.exe -m ruff check memory server.py tests research scripts datasets/acquire_datasets.py --select F
.\.venv\Scripts\python.exe scripts/diagnose.py
```

Ordinary tests use declared offline models and actual temporary databases. Dataset tests require the original local inputs. `diagnose.py --models` initializes real models, and `--nim` makes a hosted extraction request; those checks are selected explicitly.
The FalkorDB service must be running for integration tests. Tests use isolated named graphs and remove only their own test graphs.

## Evaluate

```powershell
.\.venv\Scripts\python.exe scripts/evaluate.py locomo --inspect
.\.venv\Scripts\python.exe scripts/evaluate.py locomo --run-id local_example --modes vector hybrid
.\.venv\Scripts\python.exe scripts/export_slice.py locomo data/benchmark_slices/v2/locomo
```

The runner uses local retrieval metrics and a first-context-line answer generator. It records corpus coverage, source/configuration fingerprints, failures, and resumed results. It does not implement the official upstream answer-scoring protocols. New slices retain complete selected conversation histories and cannot overwrite an existing version.

See [current specification](docs/specification.md), [architecture decisions](docs/architecture.md), [dataset notes](datasets/README.md), [research workflows](research/README.md), and [cleanup implementation report](report/cleanup_implementation_report.md).

## Graph backend performance report

The [full 20% analysis](report/full20_graph_analysis_20261013/report.md) compares Kùzu, the initial FalkorDB migration, and the optimized integration on DMR, LoCoMo and LongMemEval. The [PDF](report/full20_graph_analysis_20261013/report.pdf) and CSV tables include fresh ingestion, retrieval metrics, latency distributions, concurrency and memory scope. Optimized warm hybrid search is faster in these cohorts; full-graph copying makes ingestion and frequent updates expensive. Vector-only and reranked latency are not universally improved.

The [latency breakdown](report/latency_breakdown_20261014/report.md) separates local model work, vector search, Redis round trips, graph copying and lock waits on the same evaluated revision and 20% cohorts. It includes individual timing records, all quality metrics, bounded write probes, concurrency measurements and the observed socket timeout. [PDF](report/latency_breakdown_20261014/report.pdf).

The [reranker diagnosis](report/reranker_diagnosis_20261014/report.md) profiles tokenization and inference, compares candidate limits and an optimized FP16 model on every retained 20% question, and lists the measured quality tradeoffs. [PDF](report/reranker_diagnosis_20261014/report.pdf). Converted models remain in ignored profiling data; production model settings are unchanged.

Optional profiling dependencies are in `requirements/profiling.txt`; legacy comparisons additionally use `requirements/migration.txt`. The full test command is `python scripts/full_graph_analysis.py --run-id NEW_RUN_ID --report report/NEW_REPORT`. Retained inputs and the recorded CUDA runtime are required. Do not reuse a completed run ID for different source/configuration settings.
