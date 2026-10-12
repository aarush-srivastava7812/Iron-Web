#!/usr/bin/env python3
"""
Test GPU configuration paths.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

print("Testing GPU configuration paths...")

# Test USE_GPU flag
print(f"USE_GPU env var: {os.getenv('USE_GPU', 'not set')}")
print(f"Default USE_GPU: {os.getenv('USE_GPU', 'false').lower() == 'true'}")

# Test config loading
import yaml
with open(Path(__file__).parent.parent / "config.yaml") as f:
    config = yaml.safe_load(f)

print(f"\nEmbeddings providers (default): {config['embeddings']['providers']}")
print(f"Reranker providers (default): {config['reranker']['providers']}")

# Simulate GPU enabled
os.environ["USE_GPU"] = "true"
USE_GPU = os.getenv("USE_GPU", "false").lower() == "true"

if USE_GPU:
    config["embeddings"]["providers"] = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    config["reranker"]["providers"] = ["CUDAExecutionProvider", "CPUExecutionProvider"]

print(f"\nWith USE_GPU=true:")
print(f"Embeddings providers: {config['embeddings']['providers']}")
print(f"Reranker providers: {config['reranker']['providers']}")

# Test embedder with providers
from memory.embeddings.embedder import get_embedder

print("\nTesting embedder initialization...")
try:
    embedder = get_embedder(
        model_name="BAAI/bge-small-en-v1.5",
        providers=["CPUExecutionProvider"],
        batch_size=32
    )
    print("✓ CPU embedder initialized")
except Exception as e:
    print(f"✗ CPU embedder failed: {e}")

# Test reranker
from memory.ranking.reranker import get_reranker

print("\nTesting reranker initialization...")
try:
    reranker = get_reranker(
        model_name="BAAI/bge-reranker-base",
        providers=["CPUExecutionProvider"],
        batch_size=16
    )
    print("✓ CPU reranker initialized")
except Exception as e:
    print(f"✗ CPU reranker failed: {e}")

print("\nGPU path tests completed!")