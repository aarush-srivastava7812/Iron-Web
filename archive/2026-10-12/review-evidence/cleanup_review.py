"""Read-only structural evidence for the cleanup plan; writes report artifacts only."""
from __future__ import annotations

import ast
from collections import Counter, defaultdict
from difflib import SequenceMatcher
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report"


def main():
    previous = json.loads((OUT / "source_inventory.json").read_text(encoding="utf-8"))
    source_records = []
    functions = []
    uses = defaultdict(list)
    for entry in previous["files"]:
        path = ROOT / entry["path"]
        source = path.read_text(encoding="utf-8-sig")
        record = {"path": entry["path"], "lines": len(source.splitlines()),
                  "unchanged_since_specification": hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]}
        if path.suffix == ".py":
            tree = ast.parse(source)
            loaded_names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
            imported = []
            unused = []
            for node in tree.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        name = alias.asname or alias.name.split(".")[0]
                        item = {"name": name, "module": node.module if isinstance(node, ast.ImportFrom) else alias.name,
                                "line": node.lineno}
                        imported.append(item)
                        is_future = isinstance(node, ast.ImportFrom) and node.module == "__future__"
                        if name not in loaded_names and not is_future:
                            unused.append(item)
            record["imports"] = imported
            record["unused_import_candidates"] = unused
            record["suppressed_exception_handlers"] = [n.lineno for n in ast.walk(tree)
                if isinstance(n, ast.ExceptHandler) and all(isinstance(s, ast.Pass) for s in n.body)]
            record["branches"] = sum(isinstance(n, (ast.If, ast.For, ast.While, ast.Try)) for n in ast.walk(tree))
            for n in ast.walk(tree):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                    uses[n.id].append({"file": entry["path"], "line": n.lineno, "use": "name"})
                elif isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load):
                    uses[n.attr].append({"file": entry["path"], "line": n.lineno, "use": "attribute"})
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    body = list(n.body)
                    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                        body = body[1:]
                    canonical = ast.dump(ast.Module(body=body, type_ignores=[]), include_attributes=False)
                    functions.append({"file": entry["path"], "name": n.name, "line": n.lineno,
                                      "lines": n.end_lineno - n.lineno + 1, "canonical": canonical})
        source_records.append(record)
    duplicate_groups = defaultdict(list)
    for f in functions:
        if f["lines"] >= 8:
            duplicate_groups[f["canonical"]].append({k: v for k, v in f.items() if k != "canonical"})
    exact = [g for g in duplicate_groups.values() if len(g) > 1]
    ingestion = [f for f in functions if f["file"] == "memory/ingestion/pipeline.py" and f["name"] in {"ingest_text", "ingest_text_with_extraction"}]
    ingestion_similarity = SequenceMatcher(None, ingestion[0]["canonical"], ingestion[1]["canonical"], autojunk=False).ratio()

    directory_stats = defaultdict(lambda: {"files": 0, "bytes": 0})
    data_stats = defaultdict(lambda: {"files": 0, "bytes": 0})
    cache_stats = {"files": 0, "bytes": 0}
    artifact_extensions = Counter()
    for current, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in names:
            path = Path(current) / name
            rel = path.relative_to(ROOT)
            try:
                size = path.stat().st_size
            except OSError:
                continue
            top = rel.parts[0] if len(rel.parts) > 1 else "root files"
            directory_stats[top]["files"] += 1
            directory_stats[top]["bytes"] += size
            if top == "data" and len(rel.parts) > 1:
                data_stats[rel.parts[1]]["files"] += 1
                data_stats[rel.parts[1]]["bytes"] += size
            if "__pycache__" in rel.parts and top != ".venv":
                cache_stats["files"] += 1
                cache_stats["bytes"] += size
            if top in {"metrics", "results", "report", "screenshots"}:
                artifact_extensions[path.suffix] += 1

    docs = []
    for folder in (ROOT / "docs",):
        for path in sorted(folder.glob("*.md")):
            text = path.read_text(encoding="utf-8-sig")
            docs.append({"path": path.relative_to(ROOT).as_posix(), "lines": len(text.splitlines()),
                         "code_fences": text.count("```"), "hash": hashlib.sha256(path.read_bytes()).hexdigest()})
    data = {"review_date": "2026-10-12", "scope": "All 69 project implementation files; document and storage inventory; external code is separate",
            "sources": source_records, "exact_function_duplicates": exact,
            "ingestion_body_similarity": ingestion_similarity,
            "symbol_references": dict(uses), "directories": dict(directory_stats), "data_groups": dict(data_stats),
            "project_bytecode_cache": cache_stats, "artifact_extensions": dict(artifact_extensions), "documents": docs}
    (OUT / "cleanup_audit_evidence.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(json.dumps({"source_files": len(source_records), "source_lines": sum(r["lines"] for r in source_records),
                      "changed_sources": [r["path"] for r in source_records if not r["unchanged_since_specification"]],
                      "exact_duplicates": exact, "ingestion_body_similarity": round(ingestion_similarity, 4),
                      "directories": dict(directory_stats), "data_groups": dict(data_stats),
                      "project_bytecode_cache": cache_stats, "documentation_lines": sum(d["lines"] for d in docs)}, indent=2))


if __name__ == "__main__":
    main()
