# Reproduce the reevaluation

Run from the project root using the existing Python environment and the recorded original datasets. All stores and inputs are isolated under `data/reevaluation/reevaluation_20261013/`; active application stores are not used.

The isolated runtime directories were new destinations when installed:

```powershell
.\.venv\Scripts\python.exe -m pip install --target data/evaluation_runtime/cuda12_ort1232 --no-deps onnxruntime-gpu==1.23.2 nvidia-cuda-runtime-cu12==12.9.79
.\.venv\Scripts\python.exe -m pip install --target data/evaluation_runtime/cuda12_extra --no-deps nvidia-cufft-cu12==11.4.1.4 nvidia-nvjitlink-cu12==12.9.86
```

Existing cuBLAS, cuDNN and FastEmbed dependencies are recorded in `preflight.json`. The evaluation script selects these isolated runtime directories only for its own process and requires both live models to report CUDA execution. Model weights may download when not cached. No hosted extraction request is made.

```powershell
.\.venv\Scripts\python.exe scripts/reevaluate.py --run-id reevaluation_20261013 --report report/reevaluation_20261013
.\.venv\Scripts\python.exe scripts/summarize_reevaluation.py report/reevaluation_20261013
```

The first command resumes only when source code, input contents and effective settings match the saved manifests. To make a fresh run, choose a new run ID and report destination. Inputs are checked against the preserved historical slice hashes, then reconstructed with complete selected histories. The second command independently reconstructs the run fingerprints, checks all selected query identities, recomputes current and historical metrics, and writes the comparison tables.

The saved old hybrid predictions are reused from `archive/2026-10-12/run-records/metrics/official_upstream`. They are not rerun or overwritten. Five-percent old comparisons are matched subsets of the saved twenty-percent runs. Twenty-percent LongMemEval is deliberately absent from the execution plan.
