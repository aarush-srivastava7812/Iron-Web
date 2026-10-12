"""Isolated checks for cleanup planning. Uses fixture embeddings and temporary stores."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report"
PACKAGES = ROOT / ".venv" / "Lib" / "site-packages"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PACKAGES))
for directory in ("win32", "win32/lib", "Pythonwin", "pywin32_system32"):
    sys.path.insert(0, str(PACKAGES / directory))
_dll = os.add_dll_directory(str(PACKAGES / "pywin32_system32")) if os.name == "nt" else None

import numpy as np
from memory.engine import MemoryEngine
from memory.models import EngineStorageError
from memory.ingestion.mock_nim_extractor import MockNIMExtractor
from memory.evaluation.harness import BenchmarkAdapter, BenchmarkDocument, BenchmarkExample, BenchmarkRunner
from memory.evaluation.harness.base import ndcg_at_k, recall_at_k


class FixtureEmbedder:
    def embed_single(self, text):
        return np.array([1.0, 0.5, 0.25, 0.125], dtype=np.float32)
    def embed(self, texts):
        return np.array([self.embed_single(text) for text in texts])


class FixtureReranker:
    accelerated = False


class FixtureAdapter(BenchmarkAdapter):
    @property
    def benchmark_name(self):
        return "fixture"
    def load_documents(self, limit=None):
        return [BenchmarkDocument("probe_doc", "One fact", metadata={"source": "probe"})]
    def load_examples(self, limit=None):
        return [BenchmarkExample("probe_example", "One fact", ["probe_doc"], "One fact")]


def main():
    findings = {}
    with TemporaryDirectory(prefix="cleanup_probe_", dir=OUT) as temp:
        def engine(name):
            return MemoryEngine(config={"qdrant": {"vector_size": 4}},
                qdrant_path=str(Path(temp) / name / "qdrant"), kuzu_path=str(Path(temp) / name / "kuzu.db"),
                embedder=FixtureEmbedder(), reranker=FixtureReranker(), extractor=MockNIMExtractor(), use_gpu=False)

        with engine("identity") as e:
            e.add("Short ID memory", memory_id="a", entity_ids=["topic"])
            e.add("Long ID memory", memory_id="a_b", entity_ids=["topic"])
            e.delete("a")
            findings["prefix_deletion"] = {"other_vector_survives": e.vector_store.get_memory("a_b") is not None,
                "other_graph_observation_survives": e.graph_store.get_observation("obs_a_b_topic") is not None}
            e.add("Original text", memory_id="metadata", entity_ids=["topic"], metadata={"text": "Overridden text", "memory_id": "other_id"})
            point = e.vector_store.get_memory("metadata")
            findings["reserved_metadata_override"] = {"vector_text": point["payload"]["text"], "vector_memory_id": point["payload"]["memory_id"],
                "graph_text": e.graph_store.get_observation("obs_metadata_topic")["content"]}

        with engine("time") as e:
            e.add("Expired fact", memory_id="expired", entity_ids=["topic"], valid_from=0, valid_until=100)
            e.search("topic", retrieval_mode="vector", temporal_mode="auto", query_time=200)
            findings["vector_mode_cache"] = {"expired_ids_in_now_after_auto": [r.memory_id for r in e.search("topic", retrieval_mode="vector", temporal_mode="now", query_time=200)]}
            findings["unequal_batch_lists"] = {"added_count": len(e.add_batch(["First", "Second"], metadatas=[{}])), "requested_count": 2}

        with engine("update") as e:
            e.add("Original text", memory_id="target", entity_ids=["first", "second"], metadata={"note": "original"})
            original_upsert = e.graph_store.upsert_observation
            calls = 0
            def fail_second(*args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise RuntimeError("Injected failure on second graph observation")
                return original_upsert(*args, **kwargs)
            e.graph_store.upsert_observation = fail_second
            try:
                e.update("target", content="Changed text", metadata={"note": "changed"})
            except EngineStorageError as error:
                findings["partial_update_rollback"] = {"reported_rolled_back": error.rolled_back,
                    "vector_text": e.vector_store.get_memory("target")["payload"]["text"],
                    "vector_note": e.vector_store.get_memory("target")["payload"]["note"],
                    "first_graph_text": e.graph_store.get_observation("obs_target_first")["content"],
                    "second_graph_text": e.graph_store.get_observation("obs_target_second")["content"]}

        with engine("replacement") as e:
            e.add("Existing memory", memory_id="stable", entity_ids=["topic"])
            def fail(*args, **kwargs):
                raise RuntimeError("Injected graph failure")
            e.graph_store.upsert_observation = fail
            try:
                e.add("Replacement memory", memory_id="stable", entity_ids=["topic"])
            except EngineStorageError:
                findings["failed_replacement"] = {"previous_vector_survives": e.vector_store.get_memory("stable") is not None,
                    "previous_graph_survives": e.graph_store.get_observation("obs_stable_topic") is not None}

        with engine("dedup") as e:
            e.add("Same fact", memory_id="canonical", entity_ids=["entity_one"], importance=0.9)
            e.add("Same fact", memory_id="duplicate", entity_ids=["entity_two"], importance=0.8)
            e.deduplicate_memories()
            findings["dedup_associations"] = {"vector_entities": e.get("canonical").entity_ids,
                "new_graph_association_exists": e.graph_store.get_observation("obs_canonical_entity_two") is not None,
                "duplicate_vector_exists": e.get("duplicate") is not None}

        with engine("mock") as e:
            e.add("Python development", memory_id="python")
            first = e.graph_store.get_entity("ent_1")["name"]
            e.add("React development", memory_id="react")
            findings["mock_entity_collision"] = {"first_name": first, "name_after_second_document": e.graph_store.get_entity("ent_1")["name"]}

        with engine("resume") as e:
            e.get_device_status = lambda: SimpleNamespace(cuda_available=False, active_providers=["Fixture"], vram_total_mb=None, vram_used_mb=None)
            runner = BenchmarkRunner(output_dir=str(Path(temp) / "runs"), run_id="probe")
            kwargs = dict(benchmark_name="fixture", engine=e, adapter=FixtureAdapter(), retrieval_mode="vector", resume=True, is_smoke_test=True)
            first = runner.run_benchmark(**kwargs)
            second = runner.run_benchmark(**kwargs)
            findings["resume_aggregation"] = {"first_example_count": first["evaluation"].get("total_examples"), "second_evaluation": second["evaluation"]}

    findings["duplicate_retrieval_ndcg"] = ndcg_at_k(["doc", "doc"], ["doc"], 2)
    findings["no_evidence_recall"] = recall_at_k([], [], 10)
    (OUT / "cleanup_probe_results.json").write_text(json.dumps(findings, indent=2), encoding="utf-8")
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
