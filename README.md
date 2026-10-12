# Iron Web memory

Local text memory backed by embedded Qdrant and Kùzu. The application saves, updates, deletes and retrieves memories, supports explicit validity intervals, and exposes a local dashboard and an in-process Python tool adapter.

The supported application is in `memory/`, `server.py`, and `web/`. Optional experiments are in `research/`. Earlier designs, phase scripts, reports and unused source are preserved under `archive/2026-10-12/`; they describe the earlier implementation.

## Run

Use Python 3.12. For a new CPU environment:

```powershell
py -3.12 -m venv .venv-cpu
.\.venv-cpu\Scripts\python.exe -m pip install -r requirements.txt -r requirements/dev.txt
.\.venv-cpu\Scripts\python.exe server.py
```

Open `http://127.0.0.1:8080/`. Model files may download on the first operation that needs them. Importing the public API, reading device status, and graph-only searches do not initialize neural models.

The existing `.venv` launcher was repaired and its installed packages were preserved. The CPU and GPU dependency profiles are intended for separate environments. Hosted extraction additionally uses `requirements/nim.txt`, `extraction_policy: nim`, and the process environment variable `NVIDIA_API_KEY`. The default extraction policy is `none`, which saves text without inventing entities.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pytest -m dataset
.\.venv\Scripts\python.exe -m ruff check memory server.py tests research scripts datasets/acquire_datasets.py --select F
.\.venv\Scripts\python.exe scripts/diagnose.py
```

Ordinary tests use declared offline models and actual temporary databases. Dataset tests require the original local inputs. `diagnose.py --models` initializes real models, and `--nim` makes a hosted extraction request; those checks are selected explicitly.

## Evaluate

```powershell
.\.venv\Scripts\python.exe scripts/evaluate.py locomo --inspect
.\.venv\Scripts\python.exe scripts/evaluate.py locomo --run-id local_example --modes vector hybrid
.\.venv\Scripts\python.exe scripts/export_slice.py locomo data/benchmark_slices/v2/locomo
```

The runner uses local retrieval metrics and a first-context-line answer generator. It records corpus coverage, source/configuration fingerprints, failures, and resumed results. It does not implement the official upstream answer-scoring protocols. New slices retain complete selected conversation histories and cannot overwrite an existing version.

See [current specification](docs/specification.md), [architecture decisions](docs/architecture.md), [dataset notes](datasets/README.md), [research workflows](research/README.md), and [cleanup implementation report](report/cleanup_implementation_report.md).
