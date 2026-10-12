import json
import subprocess
import sys
import pytest
from memory.engine import MemoryEngine
from memory.evaluation.slices import export_slice, load_slice
from memory.evaluation.harness.base import BenchmarkDocument, BenchmarkExample
from tests.test_evaluation_regressions import FixtureAdapter
from research.engine import ResearchEngine


def test_public_import_does_not_load_optional_clients():
    output = subprocess.check_output(
        [
            sys.executable,
            "-c",
            "import sys; from memory import MemoryEngine; print(any(n in sys.modules for n in ['fastembed','openai','kuzu','qdrant_client']))",
        ],
        text=True,
    )
    assert output.strip() == "False"


def test_scoped_retrieval_excludes_other_conversations(tmp_path):
    with MemoryEngine(
        config={},
        qdrant_path=str(tmp_path / "vectors"),
        kuzu_path=str(tmp_path / "graph.db"),
    ) as engine:
        engine.add("topic fact one", memory_id="one", entity_ids=["topic"])
        engine.add("topic fact other", memory_id="other", entity_ids=["topic"])
        for mode in ("vector", "graph", "hybrid"):
            assert [
                r.memory_id
                for r in engine.search(
                    "topic", retrieval_mode=mode, document_ids=["one"]
                )
            ] == ["one"]


def test_research_mechanisms_have_explicit_names(tmp_path):
    with ResearchEngine(
        config={},
        qdrant_path=str(tmp_path / "vectors"),
        kuzu_path=str(tmp_path / "graph.db"),
    ) as engine:
        engine.add("Python topic", memory_id="one", entity_ids=["python"])
        for mode in ("entity_neighborhood", "dense_lexical_fusion", "temporal_room"):
            result = engine.search("Python", retrieval_mode=mode)
            assert (
                result
                and result[0].retrieval_method == mode
                and result[0].memory_id == "one"
            )


def test_slice_preserves_complete_context_and_cannot_overwrite(tmp_path):
    class Scoped(FixtureAdapter):
        def load_documents(self, limit=None):
            return [
                BenchmarkDocument("answer", "answer"),
                BenchmarkDocument("distractor", "distractor"),
            ]

        def load_examples(self, limit=None):
            return [
                BenchmarkExample(
                    "one",
                    "question",
                    ["answer"],
                    metadata={"corpus_ids": ["answer", "distractor"]},
                )
            ]

    directory = tmp_path / "v2"
    export_slice(Scoped(), directory, fraction=0.2)
    adapter = load_slice(directory, "fixture")
    assert len(adapter.load_documents()) == 2
    with pytest.raises(FileExistsError):
        export_slice(Scoped(), directory)
    payload_path = directory / "fixture.json"
    payload = json.loads(payload_path.read_text())
    payload["documents"][0]["text"] = "changed"
    payload_path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="manifest"):
        load_slice(directory, "fixture")


def test_package_adapter_uses_shared_runner_and_surfaces_failures(tmp_path):
    from memory.evaluation.harness.runner import BenchmarkRunner
    from research.upstream.backend import SDKBackend

    class FixturePackage:
        name = "fixture_package"
        configuration = {"package": "fixture", "version": "test"}

        def setup_and_ingest(self, documents):
            self.documents = documents

        def search(self, query, k):
            return [d["doc_id"] for d in self.documents][:k], [
                d["text"] for d in self.documents
            ][:k]

    backend = SDKBackend(FixturePackage())
    runner = BenchmarkRunner(str(tmp_path / "results"), "sdk_fixture")
    result = runner.run_benchmark(
        "fixture",
        backend,
        adapter=FixtureAdapter(),
        retrieval_mode=backend.package.name,
        is_smoke_test=True,
    )
    assert result["evaluation"]["total_examples"] == 2
    assert result["protocol"] == "local_retrieval_v2"
    assert result["device"]["cuda_available"] is None

    def fail(query, k):
        raise RuntimeError("actual provider failure")

    backend.package.search = fail
    with pytest.raises(RuntimeError, match="actual provider failure"):
        backend.search("query")
