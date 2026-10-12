"""Run the isolated real-NIM extraction gate without exposing credentials."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

spec = importlib.util.spec_from_file_location(
    "nim_extractor_direct", ROOT / "memory" / "ingestion" / "nim_extractor.py"
)
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load memory/ingestion/nim_extractor.py")

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

result = module.NIMExtractor(
    model="meta/llama-3.2-11b-vision-instruct"
).extract_entities_and_relations(
    "Ada switched from Python to Rust for systems programming in the Atlas project."
)

print(f"entities={len(result['entities'])}")
print(f"relations={len(result['relations'])}")
print(f"entity_names={[entity['name'] for entity in result['entities']]}")
print(f"relation_types={[relation['type'] for relation in result['relations']]}")
