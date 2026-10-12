# Phase 8: Evaluation Harness — Baselines, Metrics & Scenario Testing

---

## Overview

**Goal**: Build a complete evaluation framework to measure retrieval quality across all baselines (A-D + Full) on hand-labeled test scenarios.

**Scope**:
- Test scenario dataset (6 scenario types from architecture §8)
- Baseline runners (A, B, C, D, Full)
- Metrics: Recall@K, Precision@K, MRR, NDCG, Answer Quality (LLM-as-judge)
- Automated evaluation runner with results export
- Statistical significance testing

---

## Deliverables

| Artifact | Path | Description |
|----------|------|-------------|
| Test Scenarios | `memory/evaluation/scenarios.py` | Hand-labeled query + relevant memory IDs |
| Baseline Runners | `memory/evaluation/baselines.py` | Unified interface for all 5 systems |
| Metrics | `memory/evaluation/metrics.py` | Recall, Precision, MRR, NDCG, LLM judge |
| Evaluation Runner | `scripts/evaluate.py` | CLI to run full evaluation suite |
| Results Export | `memory/evaluation/exporter.py` | JSON/CSV/Markdown export |
| Unit Tests | `tests/test_phase8_evaluation.py` | Verify metrics, runner correctness |

---

## Implementation Details

### 1. Test Scenarios (`memory/evaluation/scenarios.py`)

```python
"""
Hand-labeled test scenarios covering 6 types from architecture_plan.md §8.

Each scenario: query, relevant_memory_ids (ground truth), scenario_type.
"""
from typing import List, Dict, Any
from dataclasses import dataclass
from enum import Enum

class ScenarioType(Enum):
    SIMPLE_RETRIEVAL = "simple_retrieval"           # "what language do I use for DSA"
    HISTORICAL_RETRIEVAL = "historical_retrieval"   # "what did I use previously"
    CURRENT_STATE = "current_state"                 # "what am I using now"
    CONTRADICTION = "contradiction"                 # "didn't I say I use C++"
    MULTI_HOP = "multi_hop"                         # "what tech in my current project"
    RELATED_EXPANSION = "related_expansion"         # "what else relates to my Rust work"

@dataclass
class TestScenario:
    id: str
    query: str
    relevant_memory_ids: List[str]  # Ground truth relevant memory IDs
    scenario_type: ScenarioType
    description: str
    # Optional: expected answer for LLM judge
    expected_answer: str = ""
    # Temporal mode for retrieval
    temporal_mode: str = "auto"  # "now", "historical", "auto"

# === Scenario Dataset ===

SCENARIOS = [
    # --- Simple Retrieval ---
    TestScenario(
        id="simple_001",
        query="What programming language do I use for data structures and algorithms?",
        relevant_memory_ids=["mem-py-dsa", "mem-cpp-dsa"],
        scenario_type=ScenarioType.SIMPLE_RETRIEVAL,
        description="Direct fact lookup: language preference for DSA"
    ),
    TestScenario(
        id="simple_002",
        query="What's my preferred database?",
        relevant_memory_ids=["mem-postgres-pref"],
        scenario_type=ScenarioType.SIMPLE_RETRIEVAL,
        description="Direct preference lookup"
    ),
    
    # --- Historical Retrieval ---
    TestScenario(
        id="hist_001",
        query="What language did I use for DSA before switching to Python?",
        relevant_memory_ids=["mem-cpp-dsa-old"],
        scenario_type=ScenarioType.HISTORICAL_RETRIEVAL,
        description="Requires temporal filtering to superseded memory",
        temporal_mode="historical"
    ),
    TestScenario(
        id="hist_002",
        query="What did I use for backend before Go?",
        relevant_memory_ids=["mem-nodejs-backend-old"],
        scenario_type=ScenarioType.HISTORICAL_RETRIEVAL,
        description="Historical state retrieval",
        temporal_mode="historical"
    ),
    
    # --- Current State ---
    TestScenario(
        id="current_001",
        query="What am I currently using for machine learning?",
        relevant_memory_ids=["mem-py-ml-current"],
        scenario_type=ScenarioType.CURRENT_STATE,
        description="Current state with temporal filtering",
        temporal_mode="now"
    ),
    TestScenario(
        id="current_002",
        query="What's my current backend language?",
        relevant_memory_ids=["mem-go-backend-current"],
        scenario_type=ScenarioType.CURRENT_STATE,
        description="Current preference",
        temporal_mode="now"
    ),
    
    # --- Contradiction ---
    TestScenario(
        id="contra_001",
        query="Didn't I say I use C++ for systems programming?",
        relevant_memory_ids=["mem-cpp-systems", "mem-rust-systems"],
        scenario_type=ScenarioType.CONTRADICTION,
        description="Contradiction detection: C++ vs Rust for systems"
    ),
    TestScenario(
        id="contra_002",
        query="I thought I preferred PostgreSQL, not MySQL?",
        relevant_memory_ids=["mem-postgres-pref", "mem-mysql-mention"],
        scenario_type=ScenarioType.CONTRADICTION,
        description="Contradiction between stated preference and mention"
    ),
    
    # --- Multi-hop ---
    TestScenario(
        id="multihop_001",
        query="What technologies am I using in my current project?",
        relevant_memory_ids=["mem-project-alpha", "mem-py-ml-current", "mem-postgres-current", "mem-docker-current"],
        scenario_type=ScenarioType.MULTI_HOP,
        description="Requires graph expansion from project entity"
    ),
    TestScenario(
        id="multihop_002",
        query="What's the stack for my Rust learning project?",
        relevant_memory_ids=["mem-rust-learning", "mem-cargo", "mem-tokio", "mem-serde"],
        scenario_type=ScenarioType.MULTI_HOP,
        description="Graph traversal from project to dependencies"
    ),
    
    # --- Related Expansion ---
    TestScenario(
        id="related_001",
        query="What else relates to my Rust work?",
        relevant_memory_ids=["mem-rust-systems", "mem-cargo", "mem-tokio", "mem-rust-learning"],
        scenario_type=ScenarioType.RELATED_EXPANSION,
        description="Graph expansion from Rust entity"
    ),
    TestScenario(
        id="related_002",
        query="What tools do I use with Python?",
        relevant_memory_ids=["mem-py-ml", "mem-pandas", "mem-numpy", "mem-jupyter", "mem-pytest"],
        scenario_type=ScenarioType.RELATED_EXPANSION,
        description="Graph expansion from Python entity"
    ),
]


def get_scenarios_by_type(scenario_type: ScenarioType) -> List[TestScenario]:
    return [s for s in SCENARIOS if s.scenario_type == scenario_type]

def get_all_scenarios() -> List[TestScenario]:
    return SCENARIOS
```

### 2. Baseline Runners (`memory/evaluation/baselines.py`)

```python"""
Unified interface for running all baselines on test scenarios.
"""
from typing import List, Dict, Any
from memory.embeddings.embedder import Embedder
from memory.vector_store.qdrant_store import QdrantVectorStore
from memory.graph.kuzu_store import KuzuGraphStore
from memory.ranking.reranker import Reranker
from memory.retrieval.vector import VectorRetriever
from memory.retrieval.hybrid import (
    BaselineA_Retriever, BaselineB_Retriever, BaselineC_Retriever,
    BaselineD_Retriever, FullRetriever
)
from memory.ranking.scorer import RetrievalConfig

class BaselineRunner:
    """Run a single baseline on all scenarios."""
    
    def __init__(self, name: str, retriever_factory):
        self.name = name
        self.retriever_factory = retriever_factory
    
    def run(self, scenario, top_k: int = 10) -> Dict[str, Any]:
        """Run baseline on one scenario."""
        retriever = self.retriever_factory()
        results = retriever.retrieve(scenario.query, k=top_k)
        
        return {
            "scenario_id": scenario.id,
            "query": scenario.query,
            "baseline": self.name,
            "retrieved_ids": [r.get("payload", {}).get("memory_id") or r.get("memory_id") or r.get("id") for r in results],
            "retrieved_scores": [r.get("final_score") or r.get("hybrid_score") or r.get("rerank_score") or r.get("score", 0) for r in results],
            "raw_results": results
        }


def create_baseline_runners(embedder, vector_store, graph_store, reranker):
    """Factory functions for each baseline."""
    
    config = RetrievalConfig(final_top_k=10)
    
    def make_baseline_a():
        return BaselineA_Retriever(embedder, vector_store)
    
    def make_baseline_b():
        return BaselineB_Retriever(embedder, vector_store, graph_store, reranker, config)
    
    def make_baseline_c():
        return BaselineC_Retriever(embedder, vector_store, graph_store, reranker, config)
    
    def make_baseline_d():
        return BaselineD_Retriever(embedder, vector_store, graph_store, reranker, config)
    
    def make_full():
        return FullRetriever(embedder, vector_store, graph_store, reranker, config)
    
    return {
        "baseline_a": BaselineRunner("Baseline A (Vector)", make_baseline_a),
        "baseline_b": BaselineRunner("Baseline B (Vector+Rerank)", make_baseline_b),
        "baseline_c": BaselineRunner("Baseline C (Vector+Graph+Rerank)", make_baseline_c),
        "baseline_d": BaselineRunner("Baseline D (Vector+Contrastive+Rerank)", make_baseline_d),
        "full": BaselineRunner("Full (Vector+Graph+Contrastive+Rerank)", make_full),
    }
```

### 3. Metrics (`memory/evaluation/metrics.py`)

```python
"""
Evaluation metrics: Recall@K, Precision@K, MRR, NDCG, Answer Quality.
"""
from typing import List, Dict, Any
import math
import numpy as np

def recall_at_k(retrieved: List[str], relevant: List[str], k: int) -> float:
    """Recall@K: fraction of relevant items in top-K."""
    if not relevant:
        return 1.0
    retrieved_k = retrieved[:k]
    hits = len(set(retrieved_k) & set(relevant))
    return hits / len(relevant)

def precision_at_k(retrieved: List[str], relevant: List[str], k: int) -> float:
    """Precision@K: fraction of retrieved items that are relevant."""
    if k == 0:
        return 0.0
    retrieved_k = retrieved[:k]
    hits = len(set(retrieved_k) & set(relevant))
    return hits / k

def mrr(retrieved: List[str], relevant: List[str]) -> float:
    """Mean Reciprocal Rank: 1/rank of first relevant item."""
    relevant_set = set(relevant)
    for i, item in enumerate(retrieved, 1):
        if item in relevant_set:
            return 1.0 / i
    return 0.0

def ndcg_at_k(retrieved: List[str], relevant: List[str], k: int) -> float:
    """NDCG@K: Normalized Discounted Cumulative Gain."""
    if not relevant:
        return 1.0
    
    retrieved_k = retrieved[:k]
    relevant_set = set(relevant)
    
    # DCG
    dcg = 0.0
    for i, item in enumerate(retrieved_k, 1):
        if item in relevant_set:
            dcg += 1.0 / math.log2(i + 1)
    
    # IDCG (ideal)
    ideal_relevant = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_relevant + 1))
    
    return dcg / idcg if idcg > 0 else 0.0

def average_precision(retrieved: List[str], relevant: List[str]) -> float:
    """Average Precision (AP) for single query."""
    if not relevant:
        return 1.0
    
    relevant_set = set(relevant)
    hits = 0
    ap = 0.0
    
    for i, item in enumerate(retrieved, 1):
        if item in relevant_set:
            hits += 1
            ap += hits / i
    
    return ap / len(relevant)

def map_score(results: List[Dict], relevant_map: Dict[str, List[str]]) -> float:
    """Mean Average Precision across queries."""
    aps = []
    for r in results:
        scenario_id = r["scenario_id"]
        relevant = relevant_map.get(scenario_id, [])
        ap = average_precision(r["retrieved_ids"], relevant)
        aps.append(ap)
    return np.mean(aps) if aps else 0.0


def compute_all_metrics(retrieved: List[str], relevant: List[str], k_values: List[int] = None) -> Dict[str, float]:
    """Compute all metrics for one query."""
    k_values = k_values or [1, 3, 5, 10]
    
    metrics = {}
    for k in k_values:
        metrics[f"recall@{k}"] = recall_at_k(retrieved, relevant, k)
        metrics[f"precision@{k}"] = precision_at_k(retrieved, relevant, k)
        metrics[f"ndcg@{k}"] = ndcg_at_k(retrieved, relevant, k)
    
    metrics["mrr"] = mrr(retrieved, relevant)
    metrics["ap"] = average_precision(retrieved, relevant)
    
    return metrics


# === LLM-as-Judge Answer Quality ===

class LLMJudge:
    """Use LLM to evaluate answer quality (faithfulness, relevance, completeness)."""
    
    def __init__(self, extractor):  # NIM extractor
        self.extractor = extractor
    
    def evaluate_answer(
        self, 
        query: str, 
        retrieved_context: List[Dict], 
        generated_answer: str,
        ground_truth_answer: str = ""
    ) -> Dict[str, float]:
        """
        Score: faithfulness (0-1), relevance (0-1), completeness (0-1)
        """
        context_text = "\n".join([r.get("text") or r.get("payload", {}).get("text", "") for r in retrieved_context])
        
        prompt = f"""
        Evaluate this answer to the query based on the retrieved context.
        
        Query: {query}
        
        Retrieved Context:
        {context_text}
        
        Generated Answer: {generated_answer}
        
        {f"Ground Truth Answer: {ground_truth_answer}" if ground_truth_answer else ""}
        
        Score each dimension 0-1:
        1. FAITHFULNESS: Does the answer only use information from the context? (No hallucination)
        2. RELEVANCE: Does the answer address the query?
        3. COMPLETENESS: Does the answer cover all relevant information from context?
        
        Output JSON only:
        {{"faithfulness": 0.0, "relevance": 0.0, "completeness": 0.0}}
        """
        
        response = self.extractor.client.chat.completions.create(
            model=self.extractor.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        
        import json
        return json.loads(response.choices[0].message.content)
```

### 4. Evaluation Runner (`scripts/evaluate.py`)

```python
#!/usr/bin/env python3
"""
Full evaluation runner.
Usage:
  python scripts/evaluate.py --baselines all --output results.json
  python scripts/evaluate.py --baselines baseline_a,baseline_c,full --scenarios simple_retrieval,historical_retrieval
  USE_GPU=true python scripts/evaluate.py --baselines all --output results.json  # GPU path (LongMemEval only)
"""
import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.embeddings.embedder import Embedder
from memory.vector_store.qdrant_store import QdrantVectorStore
from memory.graph.kuzu_store import KuzuGraphStore
from memory.ingestion.nim_extractor import NIMExtractor
from memory.ranking.reranker import Reranker
from memory.evaluation.scenarios import get_all_scenarios, get_scenarios_by_type, ScenarioType
from memory.evaluation.baselines import create_baseline_runners
from memory.evaluation.metrics import compute_all_metrics, map_score
from memory.evaluation.exporter import export_results

# Global config flag for GPU acceleration
USE_GPU = os.getenv("USE_GPU", "false").lower() == "true"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baselines", default="all", help="Comma-separated: baseline_a,baseline_b,baseline_c,baseline_d,full")
    parser.add_argument("--scenarios", default="all", help="Comma-separated scenario types or 'all'")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--output", default=f"eval_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    parser.add_argument("--judge", action="store_true", help="Run LLM-as-judge evaluation")
    parser.add_argument("--benchmark", default="local", help="Benchmark name: 'local', 'longmemeval', 'locomo'")
    args = parser.parse_args()
    
    # Initialize components
    print("Initializing components...")
    # GPU path: only for LongMemEval benchmark (large corpus ingestion + reranking)
    use_gpu_for_embedding = USE_GPU and args.benchmark == "longmemeval"
    use_gpu_for_reranker = USE_GPU and args.benchmark == "longmemeval"
    
    embedder = Embedder(use_gpu=use_gpu_for_embedding)
    vector_store = QdrantVectorStore()
    graph_store = KuzuGraphStore()
    reranker = Reranker(use_gpu=use_gpu_for_reranker)
    extractor = NIMExtractor() if args.judge else None
    
    if use_gpu_for_embedding:
        print("  GPU acceleration ENABLED for embedder (LongMemEval)")
    if use_gpu_for_reranker:
        print("  GPU acceleration ENABLED for reranker (LongMemEval)")
    
    # Get baseline runners
    runners = create_baseline_runners(embedder, vector_store, graph_store, reranker)
    
    # Filter baselines
    if args.baselines != "all":
        selected = args.baselines.split(",")
        runners = {k: v for k, v in runners.items() if k in selected}
    
    # Get scenarios
    if args.scenarios == "all":
        scenarios = get_all_scenarios()
    else:
        scenario_types = [ScenarioType(s.strip()) for s in args.scenarios.split(",")]
        scenarios = []
        for st in scenario_types:
            scenarios.extend(get_scenarios_by_type(st))
    
    print(f"Running {len(runners)} baselines on {len(scenarios)} scenarios...")
    
    # Run evaluation
    all_results = []
    relevant_map = {s.id: s.relevant_memory_ids for s in scenarios}
    
    for baseline_name, runner in runners.items():
        print(f"\n--- {baseline_name} ---")
        for scenario in scenarios:
            result = runner.run(scenario, top_k=args.top_k)
            
            # Compute metrics
            metrics = compute_all_metrics(
                result["retrieved_ids"],
                scenario.relevant_memory_ids
            )
            result["metrics"] = metrics
            
            print(f"  {scenario.id}: R@10={metrics['recall@10']:.3f}, P@5={metrics['precision@5']:.3f}, MRR={metrics['mrr']:.3f}")
            all_results.append(result)
    
    # Aggregate metrics by baseline
    print("\n=== Aggregate Results ===")
    for baseline_name in runners.keys():
        baseline_results = [r for r in all_results if r["baseline"] == runners[baseline_name].name]
        if baseline_results:
            avg_recall10 = np.mean([r["metrics"]["recall@10"] for r in baseline_results])
            avg_precision5 = np.mean([r["metrics"]["precision@5"] for r in baseline_results])
            avg_mrr = np.mean([r["metrics"]["mrr"] for r in baseline_results])
            avg_ndcg10 = np.mean([r["metrics"]["ndcg@10"] for r in baseline_results])
            print(f"  {baseline_name}: R@10={avg_recall10:.3f}, P@5={avg_precision5:.3f}, MRR={avg_mrr:.3f}, NDCG@10={avg_ndcg10:.3f}")
    
    # Export results
    export_results(all_results, args.output)
    print(f"\nResults exported to {args.output}")
    
    graph_store.close()

if __name__ == "__main__":
    main()
```

### 5. Results Exporter (`memory/evaluation/exporter.py`)

```python
"""
Export evaluation results to JSON, CSV, Markdown.
"""
from typing import List, Dict, Any
import json
import csv
from pathlib import Path
import pandas as pd

def export_results(results: List[Dict], output_path: str):
    """Export to multiple formats based on extension."""
    path = Path(output_path)
    
    # Always save JSON (full data)
    json_path = path.with_suffix(".json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    # CSV summary
    csv_path = path.with_suffix(".csv")
    _export_csv(results, csv_path)
    
    # Markdown table
    md_path = path.with_suffix(".md")
    _export_markdown(results, md_path)
    
    print(f"Exported: {json_path}, {csv_path}, {md_path}")


def _export_csv(results: List[Dict], csv_path: Path):
    """Flatten results to CSV."""
    rows = []
    for r in results:
        row = {
            "scenario_id": r["scenario_id"],
            "query": r["query"],
            "baseline": r["baseline"],
            "retrieved_count": len(r["retrieved_ids"]),
        }
        row.update(r["metrics"])
        rows.append(row)
    
    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False)


def _export_markdown(results: List[Dict], md_path: Path):
    """Generate markdown summary table."""
    # Aggregate by baseline
    baselines = {}
    for r in results:
        name = r["baseline"]
        if name not in baselines:
            baselines[name] = []
        baselines[name].append(r["metrics"])
    
    lines = ["# Evaluation Results\n"]
    lines.append(f"Generated: {datetime.now().isoformat()}\n")
    
    # Summary table
    lines.append("## Summary by Baseline\n")
    lines.append("| Baseline | Recall@10 | Precision@5 | MRR | NDCG@10 |")
    lines.append("|----------|-----------|-------------|-----|---------|")
    
    for name, metrics_list in baselines.items():
        avg = {k: np.mean([m[k] for m in metrics_list]) for k in metrics_list[0].keys()}
        lines.append(f"| {name} | {avg['recall@10']:.3f} | {avg['precision@5']:.3f} | {avg['mrr']:.3f} | {avg['ndcg@10']:.3f} |")
    
    lines.append("")
    
    # Per-scenario detail
    lines.append("## Per-Scenario Detail\n")
    for r in results:
        m = r["metrics"]
        lines.append(f"### {r['scenario_id']} ({r['baseline']})")
        lines.append(f"**Query**: {r['query']}")
        lines.append(f"**Retrieved**: {r['retrieved_ids'][:5]}...")
        lines.append(f"**Metrics**: R@10={m['recall@10']:.3f}, P@5={m['precision@5']:.3f}, MRR={m['mrr']:.3f}")
        lines.append("")
    
    with open(md_path, "w") as f:
        f.write("\n".join(lines))


def generate_latex_table(results: List[Dict]) -> str:
    """Generate LaTeX table for paper."""
    baselines = {}
    for r in results:
        name = r["baseline"]
        if name not in baselines:
            baselines[name] = []
        baselines[name].append(r["metrics"])
    
    lines = [
        "\\begin{table}[htbp]",
        "\\centering",
        "\\caption{Retrieval Performance Comparison}",
        "\\begin{tabular}{lcccc}",
        "\\toprule",
        "Baseline & Recall@10 & Precision@5 & MRR & NDCG@10 \\\\",
        "\\midrule"
    ]
    
    for name, metrics_list in baselines.items():
        avg = {k: np.mean([m[k] for m in metrics_list]) for k in metrics_list[0].keys()}
        short_name = name.split("(")[0].strip()
        lines.append(f"{short_name} & {avg['recall@10']:.3f} & {avg['precision@5']:.3f} & {avg['mrr']:.3f} & {avg['ndcg@10']:.3f} \\\\")
    
    lines.extend([
        "\\bottomrule",
        "\\end{tabular}",
        "\\label{tab:retrieval-comparison}",
        "\\end{table}"
    ])
    
    return "\n".join(lines)
```

### 6. Unit Tests (`tests/test_phase8_evaluation.py`)

```python
import pytest
import numpy as np
from memory.evaluation.metrics import (
    recall_at_k, precision_at_k, mrr, ndcg_at_k, 
    average_precision, compute_all_metrics, map_score
)
from memory.evaluation.scenarios import get_all_scenarios, ScenarioType

def test_recall_at_k():
    retrieved = ["a", "b", "c", "d", "e"]
    relevant = ["a", "c", "f"]
    
    assert recall_at_k(retrieved, relevant, 1) == 1/3  # a
    assert recall_at_k(retrieved, relevant, 3) == 2/3  # a, c
    assert recall_at_k(retrieved, relevant, 5) == 2/3
    assert recall_at_k(retrieved, [], 5) == 1.0  # Empty relevant

def test_precision_at_k():
    retrieved = ["a", "b", "c", "d", "e"]
    relevant = ["a", "c", "f"]
    
    assert precision_at_k(retrieved, relevant, 1) == 1.0  # a
    assert precision_at_k(retrieved, relevant, 3) == 2/3  # a, c
    assert precision_at_k(retrieved, relevant, 5) == 2/5

def test_mrr():
    retrieved = ["x", "y", "a", "b", "c"]
    relevant = ["a", "c"]
    
    assert mrr(retrieved, relevant) == 1/3  # First relevant at position 3
    
    retrieved2 = ["a", "b", "c"]
    assert mrr(retrieved2, relevant) == 1.0  # First relevant at position 1
    
    retrieved3 = ["x", "y", "z"]
    assert mrr(retrieved3, relevant) == 0.0  # No relevant

def test_ndcg_at_k():
    retrieved = ["a", "x", "c", "y", "z"]
    relevant = ["a", "c"]
    
    # DCG = 1/log2(2) + 1/log2(4) = 1 + 0.5 = 1.5
    # IDCG = 1/log2(2) + 1/log2(3) = 1 + 0.63 = 1.63
    ndcg = ndcg_at_k(retrieved, relevant, 5)
    assert 0.9 < ndcg < 1.0
    
    # Perfect ranking
    retrieved_perfect = ["a", "c", "x", "y", "z"]
    assert ndcg_at_k(retrieved_perfect, relevant, 5) == 1.0

def test_average_precision():
    retrieved = ["a", "x", "c", "y", "z"]
    relevant = ["a", "c"]
    
    # P@1=1, P@3=2/3 => AP = (1 + 2/3)/2 = 0.833
    ap = average_precision(retrieved, relevant)
    assert abs(ap - 0.833) < 0.01

def test_compute_all_metrics():
    retrieved = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
    relevant = ["a", "c", "e"]
    
    metrics = compute_all_metrics(retrieved, relevant)
    
    assert "recall@1" in metrics
    assert "recall@10" in metrics
    assert "precision@5" in metrics
    assert "ndcg@10" in metrics
    assert "mrr" in metrics
    assert "ap" in metrics
    
    # Specific values
    assert metrics["recall@10"] == 1.0  # All 3 found in top 10
    assert metrics["mrr"] == 1.0  # First relevant at position 1

def test_map_score():
    results = [
        {"scenario_id": "s1", "retrieved_ids": ["a", "b", "c"], "metrics": {}},
        {"scenario_id": "s2", "retrieved_ids": ["x", "a", "y"], "metrics": {}},
    ]
    relevant_map = {"s1": ["a", "c"], "s2": ["a"]}
    
    map_val = map_score(results, relevant_map)
    # s1: AP = (1 + 2/3)/2 = 0.833
    # s2: AP = 1/2 = 0.5
    # MAP = (0.833 + 0.5)/2 = 0.667
    assert abs(map_val - 0.667) < 0.01

def test_scenario_types():
    """Verify all 6 scenario types have test cases."""
    scenarios = get_all_scenarios()
    types_covered = set(s.scenario_type for s in scenarios)
    
    assert ScenarioType.SIMPLE_RETRIEVAL in types_covered
    assert ScenarioType.HISTORICAL_RETRIEVAL in types_covered
    assert ScenarioType.CURRENT_STATE in types_covered
    assert ScenarioType.CONTRADICTION in types_covered
    assert ScenarioType.MULTI_HOP in types_covered
    assert ScenarioType.RELATED_EXPANSION in types_covered
    
    # At least 2 per type
    for st in ScenarioType:
        count = len([s for s in scenarios if s.scenario_type == st])
        assert count >= 2, f"Need at least 2 scenarios for {st.value}"

def test_scenario_structure():
    """Verify scenarios have required fields."""
    for s in get_all_scenarios():
        assert s.id
        assert s.query
        assert isinstance(s.relevant_memory_ids, list)
        assert len(s.relevant_memory_ids) > 0
        assert s.scenario_type in ScenarioType
        assert s.description
```

---

## Expected Outcomes

| Baseline | Recall@10 | Precision@5 | MRR | NDCG@10 |
|----------|-----------|-------------|-----|---------|
| A (Vector) | 0.75 | 0.55 | 0.60 | 0.65 |
| B (Vector+Rerank) | 0.78 | 0.62 | 0.65 | 0.70 |
| C (Vector+Graph+Rerank) | 0.85 | 0.68 | 0.72 | 0.78 |
| D (Vector+Contrastive+Rerank) | 0.80 | 0.65 | 0.68 | 0.73 |
| Full | 0.88 | 0.72 | 0.75 | 0.82 |

**Per-scenario-type breakdown** (expected):

| Scenario Type | Best Baseline | Why |
|---------------|---------------|-----|
| Simple Retrieval | A or B | Vector similarity sufficient |
| Historical Retrieval | C or Full | Temporal + graph needed |
| Current State | C or Full | Temporal filtering |
| Contradiction | Full | Contradiction edges + graph |
| Multi-hop | C or Full | Graph expansion critical |
| Related Expansion | C or Full | Graph expansion critical |

---

### GPU Acceleration Note (Optional)

When `USE_GPU=true` and `--benchmark longmemeval`:
- **Embedder**: FastEmbed uses `CUDAExecutionProvider` for ~500 questions × ~115K-token history ingestion (single largest bottleneck)
- **Reranker**: `TextCrossEncoder` uses `CUDAExecutionProvider` for large per-query candidate pools
- **DMR/LoCoMo**: Stay CPU (small enough)
- **Default (`USE_GPU=false`)**: Identical output, CPU-only path — no behavior change, only speed

This is gated behind the single `USE_GPU` env var + `--benchmark` flag to keep baseline reproducibility intact.

---

## Verification Checklist

- [ ] `pytest tests/test_phase8_evaluation.py -v` all pass
- [ ] `python scripts/evaluate.py --baselines all --output results.json` runs
- [ ] Results exported to JSON, CSV, Markdown
- [ ] Metrics match expected ranges
- [ ] Per-scenario-type breakdown available
- [ ] LLM judge evaluation runs (optional, requires API)

---

## Next Phase Dependency

Phase 9 (Ablation Study) uses this harness to run controlled ablations: remove one component at a time from Full and measure delta.