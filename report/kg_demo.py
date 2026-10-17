"""Isolated, reproducible KG inspection. Test vectors; real extraction if available."""
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memory.engine import MemoryEngine
from memory.ingestion.nim_extractor import NIMExtractor


class StorageTestEmbedder:
    """Deterministic test vectors, not a neural semantic model."""
    dimension = 384
    def embed_single(self, text):
        vector = np.zeros(384, dtype=np.float32)
        for word in re.findall(r"\w+", text.casefold()):
            vector[int.from_bytes(hashlib.sha256(word.encode()).digest()[:4], "little") % 384] += 1
        norm = np.linalg.norm(vector)
        return vector / norm if norm else vector


def rows(graph, query):
    result = graph.conn.execute(query)
    columns = result.get_column_names()
    output = []
    while result.has_next():
        output.append(dict(zip(columns, result.get_next())))
    return output


def export(engine):
    graph = engine.graph_store
    return {
        "entities": rows(graph, "MATCH (e:Entity) RETURN e.id AS id, e.name AS name, e.entity_type AS type, e.description AS description, e.importance AS importance ORDER BY e.id"),
        "observations": rows(graph, "MATCH (o:Observation) RETURN o.id AS id, o.entity_id AS entity_id, o.content AS content, o.source_memory_id AS memory_id, o.source AS source, o.valid_from AS valid_from, o.valid_until AS valid_until, o.importance AS importance ORDER BY o.id"),
        "edges": rows(graph, "MATCH (a:Entity)-[r:RELATES]->(b:Entity) RETURN a.id AS source, b.id AS target, r.relation_type AS type, r.confidence AS confidence, r.valid_from AS valid_from, r.valid_until AS valid_until")
            + rows(graph, "MATCH (o:Observation)-[r:ABOUT]->(e:Entity) RETURN o.id AS source, e.id AS target, 'ABOUT' AS type, r.relevance AS relevance")
            + rows(graph, "MATCH (a:Observation)-[r:CONTRADICTS]->(b:Observation) RETURN a.id AS source, b.id AS target, 'CONTRADICTS' AS type, r.confidence AS confidence")
            + rows(graph, "MATCH (a:Observation)-[r:SUPERSEDES]->(b:Observation) RETURN a.id AS source, b.id AS target, 'SUPERSEDES' AS type, r.confidence AS confidence"),
    }


def main():
    out = ROOT / "report" / ("kg_demo_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    out.mkdir()
    samples = ["Maya maintains Project Atlas.", "Project Atlas uses Python and PostgreSQL.",
               "Project Atlas now uses SQLite instead of PostgreSQL."]
    evidence = {"samples": samples, "embedding": "StorageTestEmbedder: deterministic 384-dimensional test vectors; no semantic quality claim",
                "created_at": datetime.now(timezone.utc).isoformat(), "output_directory": str(out), "extractions": []}
    for mode in ("default", "nim"):
        config = {"extraction_policy": "none", "qdrant": {"path": str(out/mode/"qdrant")}, "kuzu": {"path": str(out/mode/"graph.db")}}
        with MemoryEngine(config=config, embedder=StorageTestEmbedder()) as engine:
            extractor = None
            if mode == "nim":
                key = os.getenv("NVIDIA_API_KEY") or dotenv_values(ROOT/".env").get("NVIDIA_API_KEY")
                extractor = NIMExtractor(api_key=key, timeout=30)
            for index, text in enumerate(samples, 1):
                extraction = None
                if extractor:
                    print(f"Real NIM extraction {index}/{len(samples)}", flush=True)
                    try:
                        # One bounded attempt per sample; no automatic retry loop.
                        extraction = NIMExtractor.extract_entities_and_relations.__wrapped__(extractor, text)
                    except Exception as error:
                        evidence["extraction_failure"] = {"sample": index, "exception_type": type(error).__name__}
                        print(f"Extraction failed: {type(error).__name__}; no fabricated fallback", flush=True)
                        break
                    evidence["extractions"].append({"memory_id": f"sample_{index}", "text": text, "result": extraction})
                engine.add(text, memory_id=f"sample_{index}", metadata={"source": "isolated_kg_demo"}, extraction=extraction)
            evidence[mode] = export(engine)
            evidence[mode]["vector_records"] = [{"memory_id": f"sample_{i}", "point": engine.vector_store.get_memory(f"sample_{i}")} for i in range(1, 4)]
    (out/"evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(out), "counts": {m: {"entities": len(evidence[m]["entities"]), "observations": len(evidence[m]["observations"]), "edges": len(evidence[m]["edges"])} for m in ("default", "nim")}, "extraction_failure": evidence.get("extraction_failure")}), flush=True)


if __name__ == "__main__":
    main()
