"""Isolated dashboard verification; does not open the user's active stores."""
import sys
from pathlib import Path
root = next(parent for parent in Path(__file__).resolve().parents if (parent/"server.py").exists() and (parent/"memory").is_dir())
sys.path.insert(0, str(root))
sys.path.insert(0, str(root/"tests"))
from conftest import FixtureEmbedder, FixtureReranker
from memory.engine import MemoryEngine
import server
with MemoryEngine(config={}, qdrant_path=str(root/"report/ui_preview_temp/vectors"),
                  kuzu_path=str(root/"report/ui_preview_temp/graph.db"),
                  embedder=FixtureEmbedder(), reranker=FixtureReranker()) as engine:
    engine.add("<script>window.unexpected = true</script> A Python memory.", memory_id="ui_fixture", entity_ids=["python"])
    server._ENGINE = engine
    server.run_server(18765)
