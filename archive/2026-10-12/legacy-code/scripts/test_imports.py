#!/usr/bin/env python3
"""
Test script to verify all imports and basic functionality work.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("Testing imports...")

# Test core modules
try:
    from memory.embeddings.embedder import Embedder, get_embedder
    print("✓ memory.embeddings.embedder")
except Exception as e:
    print(f"✗ memory.embeddings.embedder: {e}")

try:
    from memory.vector_store.qdrant_store import QdrantVectorStore
    print("✓ memory.vector_store.qdrant_store")
except Exception as e:
    print(f"✗ memory.vector_store.qdrant_store: {e}")

try:
    from memory.graph.kuzu_store import KuzuGraphStore
    print("✓ memory.graph.kuzu_store")
except Exception as e:
    print(f"✗ memory.graph.kuzu_store: {e}")

try:
    from memory.retrieval.vector import VectorRetriever
    print("✓ memory.retrieval.vector")
except Exception as e:
    print(f"✗ memory.retrieval.vector: {e}")

try:
    from memory.retrieval.hybrid import HybridRetriever, RetrievalConfig
    print("✓ memory.retrieval.hybrid")
except Exception as e:
    print(f"✗ memory.retrieval.hybrid: {e}")

try:
    from memory.retrieval.contrastive import ContrastiveRetriever
    print("✓ memory.retrieval.contrastive")
except Exception as e:
    print(f"✗ memory.retrieval.contrastive: {e}")

try:
    from memory.ranking.reranker import Reranker, get_reranker
    print("✓ memory.ranking.reranker")
except Exception as e:
    print(f"✗ memory.ranking.reranker: {e}")

try:
    from memory.ranking.scorer import ScoringWeights
    print("✓ memory.ranking.scorer")
except Exception as e:
    print(f"✗ memory.ranking.scorer: {e}")

try:
    from memory.temporal.filter import TemporalFilter
    print("✓ memory.temporal.filter")
except Exception as e:
    print(f"✗ memory.temporal.filter: {e}")

try:
    from memory.contradiction.detector import ContradictionDetector
    print("✓ memory.contradiction.detector")
except Exception as e:
    print(f"✗ memory.contradiction.detector: {e}")

try:
    from memory.maintenance.maintenance import MaintenanceManager
    print("✓ memory.maintenance.maintenance")
except Exception as e:
    print(f"✗ memory.maintenance.maintenance: {e}")

try:
    from memory.ingestion.pipeline import IngestionPipeline
    print("✓ memory.ingestion.pipeline")
except Exception as e:
    print(f"✗ memory.ingestion.pipeline: {e}")

try:
    from memory.ingestion.nim_extractor import NIMExtractor
    print("✓ memory.ingestion.nim_extractor")
except Exception as e:
    print(f"✗ memory.ingestion.nim_extractor: {e}")

# Test evaluation modules
try:
    from memory.evaluation.scenarios import get_scenarios, EvaluationScenario
    print("✓ memory.evaluation.scenarios")
except Exception as e:
    print(f"✗ memory.evaluation.scenarios: {e}")

try:
    from memory.evaluation.metrics import evaluate_retrieval
    print("✓ memory.evaluation.metrics")
except Exception as e:
    print(f"✗ memory.evaluation.metrics: {e}")

try:
    from memory.evaluation.ablations import get_ablation_configs
    print("✓ memory.evaluation.ablations")
except Exception as e:
    print(f"✗ memory.evaluation.ablations: {e}")

try:
    from memory.evaluation.ablation_runner import AblationRunner
    print("✓ memory.evaluation.ablation_runner")
except Exception as e:
    print(f"✗ memory.evaluation.ablation_runner: {e}")

try:
    from memory.evaluation.contrastive_sweep import ContrastiveSweepRunner, WeightTuner
    print("✓ memory.evaluation.contrastive_sweep")
except Exception as e:
    print(f"✗ memory.evaluation.contrastive_sweep: {e}")

try:
    from memory.evaluation.report_generator import ReportGenerator
    print("✓ memory.evaluation.report_generator")
except Exception as e:
    print(f"✗ memory.evaluation.report_generator: {e}")

# Test config loading
try:
    import yaml
    with open(Path(__file__).parent.parent / "config.yaml") as f:
        config = yaml.safe_load(f)
    print("✓ config.yaml loads correctly")
except Exception as e:
    print(f"✗ config.yaml: {e}")

print("\nAll import tests completed!")