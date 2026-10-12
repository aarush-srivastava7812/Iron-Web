"""Reproduce the offline source inventory and specification checks.

Uses existing project packages; does not download models or invoke cloud APIs.
Diagnostic embeddings are deterministic fixtures, not model inference.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".venv" / "Lib" / "site-packages"))
_packages = ROOT / ".venv" / "Lib" / "site-packages"
for _subdir in ("win32", "win32/lib", "Pythonwin", "pywin32_system32"):
    sys.path.insert(0, str(_packages / _subdir))
_dll_handle = os.add_dll_directory(str(_packages / "pywin32_system32")) if os.name == "nt" and (_packages / "pywin32_system32").exists() else None
OUT = ROOT / "report"


def inventory():
    paths = [ROOT / "server.py", ROOT / "datasets" / "acquire_datasets.py"]
    for folder in ("memory", "scripts", "tests", "web"):
        paths.extend(p for p in (ROOT / folder).rglob("*")
                     if p.is_file() and p.suffix in {".py", ".js", ".css", ".html"})
    records = []
    for path in sorted(paths):
        source = path.read_text(encoding="utf-8-sig")
        entry = {"path": path.relative_to(ROOT).as_posix(),
                 "lines": len(source.splitlines()),
                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        if path.suffix == ".py":
            tree = ast.parse(source)
            entry["imports"] = sorted({n.module or "" for n in ast.walk(tree)
                                       if isinstance(n, ast.ImportFrom)} |
                                      {a.name for n in ast.walk(tree) if isinstance(n, ast.Import)
                                       for a in n.names})
            symbols = []
            def symbol(node, name):
                result = {"name": name, "line": node.lineno, "kind": type(node).__name__}
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    result["signature"] = "(" + ast.unparse(node.args) + ")" + (" -> " + ast.unparse(node.returns) if node.returns else "")
                return result
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    symbols.append(symbol(node, node.name))
                    if isinstance(node, ast.ClassDef):
                        symbols.extend(symbol(m, f"{node.name}.{m.name}")
                                       for m in node.body
                                       if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)))
            entry["symbols"] = symbols
        records.append(entry)
    third_party = {}
    for name in ("letta", "locomo", "longmemeval"):
        files = [p for p in (ROOT / "datasets" / name).rglob("*") if p.is_file()
                 and ".git" not in p.parts and "__pycache__" not in p.parts]
        third_party[name] = {"files": len(files), "python_files": sum(p.suffix == ".py" for p in files)}
    result = {"date": "2026-10-12", "scope": "Project implementation, tools, tests and UI; external checkouts inventoried separately",
              "file_count": len(records), "physical_lines": sum(r["lines"] for r in records),
              "files": records, "external_checkouts": third_party}
    (OUT / "source_inventory.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = ["# Iron Web — Source and API Reference", "", "Review date: 12 October 2026", "",
             "This appendix indexes every reviewed project source file and its Python declarations. "
             "Signatures are transcribed from the source. Declaration does not establish that a path is "
             "wired into the engine or verified at runtime; the specification report describes those boundaries.", "",
             "[Main specification](D:/Opencode_/reserchpaper/report/full_specification_report.md)", "",
             f"Files: {len(records)}. Physical lines: {result['physical_lines']:,}.", "",
             "## File index", "", "| File | Lines |", "|---|---:|"]
    for entry in records:
        absolute = (ROOT / entry["path"]).as_posix()
        lines.append(f"| [{entry['path']}]({absolute}:1) | {entry['lines']} |")
    for entry in records:
        if not entry.get("symbols"):
            continue
        absolute = (ROOT / entry["path"]).as_posix()
        lines.extend(["", f"## {entry['path']}", ""])
        if entry.get("imports"):
            lines.extend(["Imports: " + ", ".join(f"`{i}`" for i in entry["imports"] if i), ""])
        lines.extend(["| Declaration | Source line | Signature |", "|---|---:|---|"])
        for declaration in entry["symbols"]:
            signature = declaration.get("signature", "class").replace("|", "\\|")
            lines.append(f"| [{declaration['name']}]({absolute}:{declaration['line']}) | {declaration['line']} | `{signature}` |")
    (OUT / "source_reference.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def checks():
    import inspect
    import numpy as np
    from memory.engine import MemoryEngine
    from memory.mcp_server import IronWebMCPServer
    from memory.ingestion.mock_nim_extractor import MockNIMExtractor
    from memory.ingestion.pipeline import IngestionPipeline
    from memory.contradiction.detector import SupersessionResolver
    from memory.ranking.scorer import HybridScorer, RetrievalConfig

    class FixtureEmbedder:
        def embed_single(self, text):
            return np.array([1.0, 0.5, 0.25, 0.125], dtype=np.float32)
        def embed(self, texts):
            return np.array([self.embed_single(t) for t in texts])

    class FixtureReranker:
        accelerated = False

    observations = {}
    with TemporaryDirectory(prefix="spec_probe_", dir=OUT) as temp:
        engine = MemoryEngine(config={"qdrant": {"vector_size": 4}},
                              qdrant_path=str(Path(temp) / "qdrant"),
                              kuzu_path=str(Path(temp) / "kuzu.db"),
                              embedder=FixtureEmbedder(), reranker=FixtureReranker(),
                              extractor=MockNIMExtractor(), use_gpu=False)
        try:
            engine.add("An old fact", entity_ids=["topic"], memory_id="old", metadata={"source": "probe"})
            engine.add("A new fact", entity_ids=["topic"], memory_id="new")
            old_obs, new_obs = "obs_old_topic", "obs_new_topic"
            engine.graph_store.add_supersession(old_obs, new_obs, 0.9)
            observations["supersession_exact_ids"] = engine.graph_store.get_relationship_conflicts_batch([old_obs, new_obs])
            observations["supersession_memory_ids"] = engine.graph_store.get_relationship_conflicts_batch(["old", "new"])
            observations["resolver_current_version"] = SupersessionResolver(engine.graph_store).get_current_version(old_obs, 2**31 - 1)
            observations["graph_mode_on_simple_query_count"] = len(engine.search("topic", retrieval_mode="graph"))
            before = engine.graph_store.get_observation(old_obs)
            engine.update("old", metadata={"edited": True})
            after = engine.graph_store.get_observation(old_obs)
            observations["update_graph_provenance"] = {"before_source": before["source"], "before_source_memory_id": before["source_memory_id"],
                                                       "after_source": after["source"], "after_source_memory_id": after["source_memory_id"]}
            observations["mcp_maintenance"] = IronWebMCPServer(engine=engine).call_tool("run_maintenance", {})
            engine.graph_store.upsert_observation("obs_entityless", "entityless", "Entityless fact")
            observations["entityless_delete_result"] = engine.graph_store.delete_memory("entityless")
            observations["entityless_observation_remains"] = engine.graph_store.get_observation("obs_entityless") is not None
        finally:
            engine.close()

    tree = ast.parse((ROOT / "memory" / "ingestion" / "pipeline.py").read_text())
    method = next(m for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "IngestionPipeline"
                  for m in n.body if isinstance(m, ast.FunctionDef) and m.name == "_chunk_text")
    module = ast.Module(body=[method], type_ignores=[])
    namespace = {"List": List}
    exec(compile(module, "chunk_probe", "exec"), namespace)
    steps = 0
    def trace(frame, event, arg):
        nonlocal steps
        if frame.f_code.co_filename == "chunk_probe" and event == "line":
            steps += 1
            if steps > 200:
                raise RuntimeError("Stopped after 200 source-line steps")
        return trace
    sys.settrace(trace)
    try:
        namespace["_chunk_text"](None, "short input", 1000, 200)
        observations["chunk_small_input"] = "terminated"
    except RuntimeError as error:
        observations["chunk_small_input"] = str(error)
    finally:
        sys.settrace(None)

    scorer = HybridScorer(RetrievalConfig())
    observations["default_weights"] = scorer.weights.to_dict()
    observations["future_timestamp_score"] = scorer.score({"score": 0.0, "payload": {"timestamp": 864000, "importance": 0}}, "", [], query_time=0)
    observations["engine_maintenance_signature"] = str(inspect.signature(MemoryEngine.run_maintenance))
    slices = ROOT / "data" / "official_upstream" / "slices"
    manifest = json.loads((slices / "freeze_manifest.json").read_text())
    observations["slice_checks"] = {}
    for name, entry in manifest["slices"].items():
        path = slices / f"{name}_20percent.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        docs = {d["doc_id"] for d in data["documents"]}
        exs = data["examples"]
        observations["slice_checks"][name] = {
            "hash_matches": hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"],
            "documents": len(docs), "examples": len(exs),
            "examples_with_empty_evidence": sum(not e["ground_truth_ids"] for e in exs),
            "examples_with_all_evidence_in_corpus": sum(bool(e["ground_truth_ids"]) and set(e["ground_truth_ids"]).issubset(docs) for e in exs),
            "examples_with_some_missing_evidence": sum(bool(set(e["ground_truth_ids"]) - docs) for e in exs),
            "documents_with_zero_or_missing_timestamp": sum(not d.get("timestamp") for d in data["documents"]),
        }
    (OUT / "spec_verification.json").write_text(json.dumps(observations, indent=2), encoding="utf-8")
    return observations


if __name__ == "__main__":
    inv = inventory()
    facts = checks()
    print(json.dumps({"files": inv["file_count"], "lines": inv["physical_lines"],
                      "external": inv["external_checkouts"], "checks": facts}, indent=2))
