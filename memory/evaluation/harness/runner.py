"""Local evaluation runner with validated resumability and declared evidence coverage.

This harness does not implement the official upstream answer-scoring protocols.
"""

import json
import re
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from memory.evaluation.harness.base import EvaluationResult
from memory.evaluation.harness.evaluator import BenchmarkEvaluator
from memory.evaluation.harness.longmemeval_adapter import LongMemEvalAdapter
from memory.evaluation.harness.locomo_adapter import LoCoMoAdapter
from memory.evaluation.harness.dmr_adapter import DMRAdapter
from memory.evaluation.harness.persistence import (
    fingerprint,
    source_fingerprint,
    write_atomic,
)


class BenchmarkRunner:
    ADAPTER_REGISTRY = {
        "longmemeval": LongMemEvalAdapter,
        "locomo": LoCoMoAdapter,
        "dmr": DMRAdapter,
    }

    def __init__(self, output_dir="./data/results", run_id=None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id or f"run_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", self.run_id):
            raise ValueError("Run ID contains invalid path characters.")

    def run_benchmark(
        self,
        benchmark_name,
        engine,
        adapter=None,
        max_documents=None,
        max_examples=None,
        retrieval_mode="hybrid",
        k=10,
        resume=True,
        is_smoke_test=False,
    ):
        if (
            max_documents is not None
            and max_documents < 1
            or max_examples is not None
            and max_examples < 1
        ):
            raise ValueError("Dataset limits must be positive.")
        if retrieval_mode not in engine.retrieval_modes or not 1 <= k <= 100:
            raise ValueError("Invalid evaluation retrieval settings.")
        key = benchmark_name.lower()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", key):
            raise ValueError("Invalid benchmark name.")
        if adapter is None:
            if key not in self.ADAPTER_REGISTRY:
                raise ValueError(f"Unknown benchmark: {benchmark_name}")
            adapter = self.ADAPTER_REGISTRY[key]()
        if adapter.benchmark_name != key:
            raise ValueError("Adapter and benchmark name differ.")
        extractor = (
            None if retrieval_mode in {"none", "no_memory"} else engine.extractor
        )
        if not is_smoke_test and getattr(extractor, "is_mock", False):
            raise ValueError(
                "Mock extraction is allowed only in explicitly labelled smoke tests."
            )
        documents = adapter.load_documents(limit=max_documents)
        examples = adapter.load_examples(limit=max_examples)
        document_ids = {d.doc_id for d in documents}
        if len(document_ids) != len(documents) or len(
            {e.example_id for e in examples}
        ) != len(examples):
            raise ValueError("Dataset contains duplicate document or example IDs.")
        uncovered = [
            e.example_id
            for e in examples
            if (set(e.ground_truth_ids) | set(e.metadata.get("corpus_ids", [])))
            - document_ids
            or e.metadata.get("unmapped_evidence")
        ]
        if uncovered and not is_smoke_test:
            raise ValueError(
                f"Evidence is outside the loaded corpus for {len(uncovered)} examples."
            )
        eligible = [e for e in examples if e.example_id not in set(uncovered)]
        if not eligible:
            raise ValueError(
                "The selected corpus covers none of the selected questions."
            )
        stored_ids = engine.memory_ids()
        extra_ids = stored_ids - document_ids
        if extra_ids and not is_smoke_test:
            raise ValueError(
                "Evaluation requires an isolated store containing only the selected corpus."
            )
        inputs = dict(
            protocol="local_retrieval_v2",
            source=source_fingerprint(),
            benchmark=key,
            retrieval_mode=retrieval_mode,
            k=k,
            smoke=is_smoke_test,
            config=engine.config_data,
            backend_identity=getattr(engine, "evaluation_identity", {}),
            use_gpu=engine.use_gpu,
            extractor=type(extractor).__name__ if extractor else "disabled",
            generator="first_context_line",
            documents=[asdict(d) for d in documents],
            examples=[asdict(e) for e in eligible],
        )
        signature = fingerprint(inputs)
        directory = self.output_dir / key
        directory.mkdir(parents=True, exist_ok=True)
        stem = f"{self.run_id}_{retrieval_mode}_{'smoke' if is_smoke_test else 'local'}"
        run_file, manifest_file, summary_file = (
            directory / (stem + suffix)
            for suffix in (".jsonl", "_manifest.json", "_summary.json")
        )
        if not resume and (run_file.exists() or manifest_file.exists()):
            raise FileExistsError(
                "Run already exists. Choose a new run ID for a fresh run."
            )
        if manifest_file.exists():
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            if manifest.get("fingerprint") != signature:
                raise ValueError(
                    "Resume settings, source code or dataset differ from the saved run."
                )
        elif run_file.exists():
            raise ValueError(
                "Existing results have no verifiable manifest; choose a new run ID."
            )
        else:
            manifest = dict(
                fingerprint=signature,
                protocol=inputs["protocol"],
                generator=inputs["generator"],
                document_count=len(documents),
                example_count=len(eligible),
            )
            write_atomic(manifest_file, json.dumps(manifest, indent=2))
        saved = {}
        if run_file.exists():
            for number, line in enumerate(
                run_file.read_text(encoding="utf-8").splitlines(), 1
            ):
                try:
                    result = EvaluationResult(**json.loads(line))
                except (TypeError, ValueError) as error:
                    raise ValueError(
                        f"Invalid result record at line {number}."
                    ) from error
                if (
                    result.run_id != self.run_id
                    or result.benchmark_name != key
                    or result.example_id in saved
                ):
                    raise ValueError(
                        "Saved result identities are invalid or duplicated."
                    )
                saved[result.example_id] = result
        if set(saved) - {e.example_id for e in eligible}:
            raise ValueError(
                "Saved results contain questions outside the selected dataset."
            )
        evaluator = BenchmarkEvaluator(
            engine, adapter, retrieval_mode=retrieval_mode, k=k
        )
        ingest_stats = evaluator.ingest_documents(documents, show_progress=False)
        resumed = sum(not r.error for r in saved.values())
        for example in eligible:
            if example.example_id in saved and not saved[example.example_id].error:
                continue
            try:
                result = evaluator.evaluate_example(example, self.run_id)
            except Exception as error:
                result = EvaluationResult(
                    self.run_id,
                    key,
                    example.example_id,
                    example.query,
                    [],
                    example.ground_truth_ids,
                    {},
                    category=example.category,
                    error=str(error),
                )
            saved[example.example_id] = result
            write_atomic(
                run_file,
                "".join(
                    json.dumps(
                        saved[e.example_id].to_dict(),
                        ensure_ascii=False,
                        allow_nan=False,
                    )
                    + "\n"
                    for e in eligible
                    if e.example_id in saved
                ),
            )
        results = [saved[e.example_id] for e in eligible]
        device = engine.get_device_status()
        summary = dict(
            run_id=self.run_id,
            benchmark=key,
            is_smoke_test=is_smoke_test,
            protocol=inputs["protocol"],
            fingerprint=signature,
            generator=inputs["generator"],
            retrieval_mode=retrieval_mode,
            k=k,
            timestamp=int(time.time()),
            device=device.model_dump(),
            ingestion=ingest_stats,
            evaluation=evaluator.aggregate_results(results),
            coverage=dict(
                selected_examples=len(examples),
                evaluated_examples=len(eligible),
                excluded_missing_evidence=uncovered,
                examples_without_evidence=sum(not e.ground_truth_ids for e in eligible),
                extra_store_records=len(extra_ids),
                documents_without_dates=sum(d.timestamp is None for d in documents),
            ),
            resumed_examples=resumed,
            run_file=str(run_file),
        )
        write_atomic(
            summary_file,
            json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False),
        )
        return summary
