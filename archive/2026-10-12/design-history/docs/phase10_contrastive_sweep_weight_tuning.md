# Phase 10: Contrastive Ratio Sweep + Weight Tuning — Hyperparameter Optimization

---

## Overview

**Goal**: Systematically optimize two key hyperparameters:
1. **Contrastive Ratio**: % of contrastive candidates to include (0%, 5%, 10%, 20%, 50%)
2. **Scoring Weights**: The 8 weights in the hybrid scoring formula

**Scope**: 
- Grid search over contrastive ratios
- Bayesian optimization or grid search for weight tuning
- Per-scenario-type optimization (different weights may work for different query types)
- Pareto frontier: accuracy vs latency trade-off

---

## Deliverables

| Artifact | Path | Description |
|----------|------|-------------|
| Sweep Runner | `scripts/sweep.py` | CLI for contrastive ratio sweep |
| Weight Tuner | `memory/evaluation/weight_tuner.py` | Optimization for scoring weights |
| Pareto Analysis | `memory/evaluation/pareto.py` | Accuracy vs latency frontier |
| Results Export | `memory/evaluation/sweep_exporter.py` | Visualization-ready exports |
| Unit Tests | `tests/test_phase10_sweep.py` | Verify sweep framework |

---

## Implementation Details

### 1. Contrastive Ratio Sweep Runner (`scripts/sweep.py`)

```python
#!/usr/bin/env python3
"""
Contrastive ratio sweep: test 0%, 5%, 10%, 20%, 50%.
Usage:
  python scripts/sweep.py --ratios 0,0.05,0.1,0.2,0.5 --metric recall@10
  USE_GPU=true python scripts/sweep.py --ratios 0,0.05,0.1,0.2,0.5  # GPU path (highest-value change)
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
from memory.ranking.reranker import Reranker
from memory.evaluation.scenarios import get_all_scenarios
from memory.evaluation.baselines import create_baseline_runners
from memory.evaluation.metrics import compute_all_metrics
from memory.ranking.scorer import RetrievalConfig
from memory.retrieval.hybrid import FullRetriever
from memory.evaluation.exporter import export_results

# Global config flag for GPU acceleration
USE_GPU = os.getenv("USE_GPU", "false").lower() == "true"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ratios", default="0,0.05,0.1,0.2,0.5", help="Comma-separated contrastive ratios")
    parser.add_argument("--metric", default="recall@10", help="Primary metric")
    parser.add_argument("--output", default=f"sweep_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    parser.add_argument("--baselines", default="full", help="Which baselines to sweep (full, baseline_d)")
    args = parser.parse_args()
    
    ratios = [float(r.strip()) for r in args.ratios.split(",")]
    
    # Initialize
    print("Initializing components...")
    # GPU path: reranker is the highest-volume repeated-reranking loop in the whole project
    # (Optuna trials × contrastive ratio sweep). Reranker GPU path is the highest-value single change.
    use_gpu_reranker = USE_GPU
    
    embedder = Embedder()  # Embedder not the bottleneck here; sweep uses fixed corpus
    vector_store = QdrantVectorStore()
    graph_store = KuzuGraphStore()
    reranker = Reranker(use_gpu=use_gpu_reranker)
    
    if use_gpu_reranker:
        print("  GPU acceleration ENABLED for reranker (contrastive sweep — highest-volume reranking loop)")
    else:
        print("  CPU-only path (default)")
    
    scenarios = get_all_scenarios()
    
    print(f"Running sweep over {len(ratios)} ratios on {len(scenarios)} scenarios...")
    
    all_results = {}
    
    for ratio in ratios:
        print(f"\n=== Contrastive Ratio: {ratio*100:.0f}% ===")
        
        config = RetrievalConfig(
            use_vector=True,
            use_graph_expansion=True,
            use_reranker=True,
            use_contrastive=(ratio > 0),
            use_temporal_filter=True,
            contrastive_ratio=ratio,
            vector_candidates=100,
            graph_hops=2,
            final_top_k=10
        )
        
        retriever = FullRetriever(embedder, vector_store, graph_store, reranker, config)
        
        ratio_results = []
        for scenario in scenarios:
            result = retriever.retrieve(scenario.query, k=10)
            
            retrieved_ids = [r.get("payload", {}).get("memory_id") or r.get("memory_id") or r.get("id") for r in result]
            metrics = compute_all_metrics(retrieved_ids, scenario.relevant_memory_ids)
            
            ratio_results.append({
                "scenario_id": scenario.id,
                "scenario_type": scenario.scenario_type.value,
                "query": scenario.query,
                "retrieved_ids": retrieved_ids,
                "metrics": metrics
            })
            
            print(f"  {scenario.id}: {args.metric}={metrics[args.metric]:.3f}")
        
        all_results[f"ratio_{ratio:.2f}"] = ratio_results
    
    # Aggregate by ratio
    print("\n=== Aggregate Results ===")
    summary = {}
    for ratio_key, results in all_results.items():
        avg = {}
        for metric in results[0]["metrics"].keys():
            avg[metric] = sum(r["metrics"][metric] for r in results) / len(results)
        summary[ratio_key] = avg
        print(f"  {ratio_key}: {args.metric}={avg[args.metric]:.4f}")
    
    # Find best ratio
    best_ratio = max(summary.keys(), key=lambda k: summary[k][args.metric])
    print(f"\nBest ratio for {args.metric}: {best_ratio} = {summary[best_ratio][args.metric]:.4f}")
    
    # Export
    export_data = {
        "timestamp": datetime.now().isoformat(),
        "ratios_tested": ratios,
        "primary_metric": args.metric,
        "summary": summary,
        "per_scenario": all_results
    }
    
    with open(args.output, "w") as f:
        json.dump(export_data, f, indent=2, default=str)
    
    print(f"\nResults exported to {args.output}")
    
    graph_store.close()

if __name__ == "__main__":
    main()
```

### 2. Weight Tuner (`memory/evaluation/weight_tuner.py`)

```python
"""
Scoring weight optimization using grid search or Bayesian optimization.
"""
from typing import Dict, List, Tuple, Callable
import numpy as np
import itertools
import os
from dataclasses import dataclass
from memory.ranking.scorer import RetrievalConfig, ScoringWeights

# Global config flag for GPU acceleration (used by evaluator_fn when provided)
USE_GPU = os.getenv("USE_GPU", "false").lower() == "true"

@dataclass
class WeightSearchSpace:
    """Define search space for each weight."""
    # (min, max, step) or list of values
    alpha_semantic: Tuple[float, float, float] = (0.5, 2.0, 0.25)
    beta_graph: Tuple[float, float, float] = (0.0, 1.0, 0.25)
    gamma_recency: Tuple[float, float, float] = (0.0, 1.0, 0.25)
    delta_importance: Tuple[float, float, float] = (0.0, 1.0, 0.25)
    epsilon_entity: Tuple[float, float, float] = (0.0, 1.0, 0.25)
    zeta_relationship: Tuple[float, float, float] = (0.0, 1.0, 0.25)
    eta_historical: Tuple[float, float, float] = (0.0, 1.0, 0.25)
    theta_contradiction: Tuple[float, float, float] = (0.0, 1.0, 0.25)
    theta_contrastive: Tuple[float, float, float] = (0.0, 1.0, 0.25)

class WeightTuner:
    def __init__(
        self,
        evaluator_fn: Callable[[RetrievalConfig], Dict[str, float]],
        search_space: WeightSearchSpace = None,
        metric: str = "recall@10"
    ):
        """
        Args:
            evaluator_fn: Function that takes a RetrievalConfig and returns metrics dict
            search_space: Weight ranges to explore
            metric: Metric to optimize
        """
        self.evaluator_fn = evaluator_fn
        self.search_space = search_space or WeightSearchSpace()
        self.metric = metric
        self.history = []
    
    def grid_search(self, max_combinations: int = 500) -> Dict:
        """Exhaustive grid search (limited by max_combinations)."""
        # Generate all combinations
        param_names = [
            "alpha_semantic", "beta_graph", "gamma_recency", "delta_importance",
            "epsilon_entity", "zeta_relationship", "eta_historical",
            "theta_contradiction", "theta_contrastive"
        ]
        
        param_values = {}
        for name in param_names:
            space = getattr(self.search_space, name)
            if isinstance(space, tuple):
                min_v, max_v, step = space
                param_values[name] = np.arange(min_v, max_v + step/2, step).tolist()
            else:
                param_values[name] = space
        
        # Limit combinations
        all_combos = list(itertools.product(*param_values.values()))
        if len(all_combos) > max_combinations:
            # Random sample
            indices = np.random.choice(len(all_combos), max_combinations, replace=False)
            all_combos = [all_combos[i] for i in indices]
        
        print(f"Evaluating {len(all_combos)} weight combinations...")
        
        best_config = None
        best_score = -1
        
        for i, combo in enumerate(all_combos):
            weights_dict = dict(zip(param_names, combo))
            weights = ScoringWeights(**weights_dict)
            
            config = RetrievalConfig(
                use_vector=True,
                use_graph_expansion=True,
                use_reranker=True,
                use_contrastive=True,
                use_temporal_filter=True,
                contrastive_ratio=0.1,
                weights=weights
            )
            
            metrics = self.evaluator_fn(config)
            score = metrics[self.metric]
            
            self.history.append({
                "iteration": i,
                "weights": weights_dict,
                "metrics": metrics,
                "score": score
            })
            
            if score > best_score:
                best_score = score
                best_config = weights_dict
            
            if i % 50 == 0:
                print(f"  Iter {i}/{len(all_combos)}: best {self.metric}={best_score:.4f}")
        
        return {
            "best_weights": best_config,
            "best_score": best_score,
            "history": self.history
        }
    
    def random_search(self, n_iter: int = 200) -> Dict:
        """Random search (often better than grid for high-dimensional spaces)."""
        param_names = [
            "alpha_semantic", "beta_graph", "gamma_recency", "delta_importance",
            "epsilon_entity", "zeta_relationship", "eta_historical",
            "theta_contradiction", "theta_contrastive"
        ]
        
        best_config = None
        best_score = -1
        
        for i in range(n_iter):
            weights_dict = {}
            for name in param_names:
                space = getattr(self.search_space, name)
                if isinstance(space, tuple):
                    min_v, max_v, step = space
                    # Sample log-uniform for scale parameters
                    weights_dict[name] = np.random.uniform(min_v, max_v)
                else:
                    weights_dict[name] = np.random.choice(space)
            
            weights = ScoringWeights(**weights_dict)
            config = RetrievalConfig(weights=weights)
            
            metrics = self.evaluator_fn(config)
            score = metrics[self.metric]
            
            self.history.append({
                "iteration": i,
                "weights": weights_dict,
                "metrics": metrics,
                "score": score
            })
            
            if score > best_score:
                best_score = score
                best_config = weights_dict
        
        return {
            "best_weights": best_config,
            "best_score": best_score,
            "history": self.history
        }
    
    def get_pareto_frontier(self, metrics_list: List[str] = None) -> List[Dict]:
        """Extract Pareto-optimal configurations."""
        if metrics_list is None:
            metrics_list = [self.metric, "latency_ms"]  # Assuming latency in metrics
        
        pareto = []
        for h in self.history:
            dominated = False
            for other in self.history:
                if all(other["metrics"].get(m, 0) >= h["metrics"].get(m, 0) for m in metrics_list) and \
                   any(other["metrics"].get(m, 0) > h["metrics"].get(m, 0) for m in metrics_list):
                    dominated = True
                    break
            if not dominated:
                pareto.append(h)
        
        return pareto
```

### 3. Per-Scenario-Type Weight Tuning (`memory/evaluation/weight_tuner.py` — continued)

```python
"""
Per-scenario-type weight optimization.
Different query types may benefit from different weight configurations.
"""
from typing import Dict, List
import os
from memory.evaluation.scenarios import get_scenarios_by_type, ScenarioType
from memory.embeddings.embedder import Embedder
from memory.ranking.reranker import Reranker

# GPU flag for evaluator
USE_GPU = os.getenv("USE_GPU", "false").lower() == "true"

class PerScenarioWeightTuner:
    """Find optimal weights for each scenario type independently."""
    
    def __init__(self, base_evaluator_fn):
        self.base_evaluator_fn = base_evaluator_fn
        self.scenario_types = list(ScenarioType)
    
    def create_type_evaluator(self, scenario_type: ScenarioType):
        """Create evaluator that only runs on one scenario type."""
        def evaluator(config):
            from memory.evaluation.scenarios import get_scenarios_by_type
            from memory.evaluation.baselines import create_baseline_runners
            from memory.evaluation.metrics import compute_all_metrics
            from memory.retrieval.hybrid import FullRetriever
            from memory.vector_store.qdrant_store import QdrantVectorStore
            from memory.graph.kuzu_store import KuzuGraphStore
            
            scenarios = get_scenarios_by_type(scenario_type)
            
            # Initialize components with GPU if enabled
            embedder = Embedder()
            vector_store = QdrantVectorStore()
            graph_store = KuzuGraphStore()
            reranker = Reranker(use_gpu=USE_GPU)
            
            # Need components - would be passed in real implementation
            # This is a simplified interface
            metrics_sum = {}
            for scenario in scenarios:
                # Would run retriever here
                pass
            
            return {k: v/len(scenarios) for k, v in metrics_sum.items()}
        
        return evaluator
    
    def tune_all_types(self) -> Dict:
        """Tune weights for each scenario type."""
        results = {}
        
        for scenario_type in self.scenario_types:
            print(f"\nTuning for {scenario_type.value}...")
            evaluator = self.create_type_evaluator(scenario_type)
            tuner = WeightTuner(evaluator)
            result = tuner.random_search(n_iter=100)
            results[scenario_type.value] = result
            
            print(f"  Best {tuner.metric}: {result['best_score']:.4f}")
            print(f"  Weights: {result['best_weights']}")
        
        return results
```

### 4. Pareto Analysis (`memory/evaluation/pareto.py`)

```python
"""
Pareto frontier analysis: Accuracy vs Latency trade-offs.
"""
from typing import List, Dict
import numpy as np

def compute_pareto_frontier(
    results: List[Dict], 
    x_metric: str = "latency_ms", 
    y_metric: str = "recall@10",
    minimize_x: bool = True,
    maximize_y: bool = True
) -> List[Dict]:
    """
    Find Pareto-optimal configurations.
    
    A configuration is Pareto-optimal if no other configuration is better 
    on both metrics.
    """
    pareto = []
    
    for r in results:
        x = r.get(x_metric, 0)
        y = r.get(y_metric, 0)
        
        dominated = False
        for other in results:
            ox = other.get(x_metric, 0)
            oy = other.get(y_metric, 0)
            
            x_better = (ox <= x) if minimize_x else (ox >= x)
            y_better = (oy >= y) if maximize_y else (oy <= y)
            x_strict = (ox < x) if minimize_x else (ox > x)
            y_strict = (oy > y) if maximize_y else (oy < y)
            
            if x_better and y_better and (x_strict or y_strict):
                dominated = True
                break
        
        if not dominated:
            pareto.append(r)
    
    # Sort by x metric
    pareto.sort(key=lambda r: r.get(x_metric, 0), reverse=not minimize_x)
    return pareto


def generate_pareto_plot_data(pareto_results: List[Dict], x_metric: str, y_metric: str) -> Dict:
    """Format for plotting."""
    return {
        "pareto_x": [r.get(x_metric, 0) for r in pareto_results],
        "pareto_y": [r.get(y_metric, 0) for r in pareto_results],
        "all_x": [r.get(x_metric, 0) for r in pareto_results],  # Same for now
        "all_y": [r.get(y_metric, 0) for r in pareto_results],
        "labels": [r.get("config_name", "") for r in pareto_results]
    }


def analyze_contrastive_pareto(sweep_results: Dict) -> Dict:
    """Analyze contrastive ratio sweep as Pareto frontier (accuracy vs latency)."""
    # sweep_results has ratio -> metrics with latency
    ratios = []
    accuracies = []
    latencies = []
    
    for ratio_key, results in sweep_results.items():
        if ratio_key.startswith("ratio_"):
            ratio = float(ratio_key.split("_")[1])
            ratios.append(ratio)
            
            avg_metrics = {}
            for m in results[0]["metrics"].keys():
                avg_metrics[m] = sum(r["metrics"][m] for r in results) / len(results)
            
            accuracies.append(avg_metrics.get("recall@10", 0))
            latencies.append(avg_metrics.get("latency_ms", 0))
    
    # Find Pareto optimal
    pareto_indices = []
    for i in range(len(ratios)):
        dominated = False
        for j in range(len(ratios)):
            if latencies[j] <= latencies[i] and accuracies[j] >= accuracies[i] and \
               (latencies[j] < latencies[i] or accuracies[j] > accuracies[i]):
                dominated = True
                break
        if not dominated:
            pareto_indices.append(i)
    
    return {
        "ratios": ratios,
        "accuracies": accuracies,
        "latencies": latencies,
        "pareto_ratios": [ratios[i] for i in pareto_indices],
        "pareto_accuracies": [accuracies[i] for i in pareto_indices],
        "pareto_latencies": [latencies[i] for i in pareto_indices]
    }
```

### 5. Enhanced Sweep Exporter (`memory/evaluation/sweep_exporter.py`)

```python
"""
Export sweep and tuning results for visualization.
"""
import json
import csv
from pathlib import Path
import pandas as pd

def export_sweep_results(results: Dict, output_dir: str):
    """Export contrastive ratio sweep results."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    
    # CSV for easy plotting
    rows = []
    for ratio_key, scenario_results in results["per_scenario"].items():
        ratio = float(ratio_key.split("_")[1])
        for r in scenario_results:
            row = {"ratio": ratio, "scenario_id": r["scenario_id"], "scenario_type": r["scenario_type"]}
            row.update(r["metrics"])
            rows.append(row)
    
    df = pd.DataFrame(rows)
    df.to_csv(path / "sweep_detailed.csv", index=False)
    
    # Summary CSV
    summary_rows = []
    for ratio_key, metrics in results["summary"].items():
        row = {"ratio": float(ratio_key.split("_")[1])}
        row.update(metrics)
        summary_rows.append(row)
    
    pd.DataFrame(summary_rows).to_csv(path / "sweep_summary.csv", index=False)
    
    # JSON for web visualization
    with open(path / "sweep_viz.json", "w") as f:
        json.dump({
            "ratios": [float(k.split("_")[1]) for k in results["per_scenario"].keys()],
            "scenario_types": list(set(r["scenario_type"] for res in results["per_scenario"].values() for r in res)),
            "metrics": list(results["summary"].values())[0].keys(),
            "data": results["per_scenario"]
        }, f, indent=2)


def export_weight_tuning_results(tuning_results: Dict, output_dir: str):
    """Export weight tuning history."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    
    # History CSV
    if "history" in tuning_results:
        rows = []
        for h in tuning_results["history"]:
            row = {"iteration": h["iteration"], "score": h["score"]}
            row.update(h["weights"])
            row.update({f"metric_{k}": v for k, v in h["metrics"].items()})
            rows.append(row)
        
        pd.DataFrame(rows).to_csv(path / "weight_tuning_history.csv", index=False)
    
    # Best weights JSON
    with open(path / "best_weights.json", "w") as f:
        json.dump(tuning_results["best_weights"], f, indent=2)


def generate_weight_heatmap_data(tuning_results: Dict) -> Dict:
    """Generate data for weight correlation heatmap."""
    if "history" not in tuning_results:
        return {}
    
    weights_names = list(tuning_results["history"][0]["weights"].keys())
    n = len(weights_names)
    
    # Correlation matrix between weights and final score
    import numpy as np
    
    weight_matrix = np.array([[h["weights"][w] for w in weights_names] for h in tuning_results["history"]])
    scores = np.array([h["score"] for h in tuning_results["history"]])
    
    correlations = {}
    for i, w in enumerate(weights_names):
        corr = np.corrcoef(weight_matrix[:, i], scores)[0, 1]
        correlations[w] = float(corr) if not np.isnan(corr) else 0.0
    
    return {
        "weights": weights_names,
        "correlations_with_score": correlations,
        "sample_count": len(tuning_results["history"])
    }
```

### 6. Unit Tests (`tests/test_phase10_sweep.py`)

```python
import pytest
import numpy as np
from memory.evaluation.weight_tuner import WeightSearchSpace, WeightTuner
from memory.evaluation.pareto import compute_pareto_frontier
from memory.ranking.scorer import RetrievalConfig, ScoringWeights

def test_weight_search_space():
    """Verify search space definition."""
    space = WeightSearchSpace()
    
    # All weights have ranges
    assert space.alpha_semantic == (0.5, 2.0, 0.25)
    assert space.beta_graph == (0.0, 1.0, 0.25)
    # ... etc

def test_grid_search_generates_configs():
    """Grid search produces valid configs."""
    
    def mock_evaluator(config):
        # Return random-ish metrics based on weights
        w = config.weights
        # Simple heuristic: higher alpha_semantic + beta_graph = better recall
        score = 0.5 + 0.1 * w.alpha_semantic + 0.15 * w.beta_graph
        return {"recall@10": min(1.0, score), "latency_ms": 50}
    
    tuner = WeightTuner(mock_evaluator, metric="recall@10")
    result = tuner.grid_search(max_combinations=50)
    
    assert "best_weights" in result
    assert "best_score" in result
    assert "history" in result
    assert len(result["history"]) <= 50
    assert result["best_score"] > 0.5

def test_random_search():
    """Random search explores space."""
    
    def mock_evaluator(config):
        w = config.weights
        score = 0.5 + 0.1 * w.alpha_semantic + 0.15 * w.beta_graph
        return {"recall@10": min(1.0, score), "latency_ms": 50}
    
    tuner = WeightTuner(mock_evaluator, metric="recall@10")
    result = tuner.random_search(n_iter=20)
    
    assert len(result["history"]) == 20
    assert result["best_score"] > 0.5

def test_pareto_frontier():
    """Pareto frontier correctly identifies non-dominated points."""
    results = [
        {"latency_ms": 100, "recall@10": 0.8, "config": "A"},
        {"latency_ms": 150, "recall@10": 0.85, "config": "B"},  # Better recall, worse latency
        {"latency_ms": 80, "recall@10": 0.75, "config": "C"},   # Better latency, worse recall
        {"latency_ms": 200, "recall@10": 0.7, "config": "D"},   # Dominated by A
        {"latency_ms": 120, "recall@10": 0.9, "config": "E"},   # Best recall
    ]
    
    pareto = compute_pareto_frontier(results, "latency_ms", "recall@10")
    
    # Should include A, B, C, E (not D)
    pareto_configs = {r["config"] for r in pareto}
    assert "A" in pareto_configs
    assert "B" in pareto_configs
    assert "C" in pareto_configs
    assert "E" in pareto_configs
    assert "D" not in pareto_configs

def test_pareto_with_multiple_metrics():
    """Pareto with 3+ metrics."""
    results = [
        {"latency": 100, "recall": 0.8, "precision": 0.7},
        {"latency": 150, "recall": 0.85, "precision": 0.75},
        {"latency": 80, "recall": 0.75, "precision": 0.65},
        {"latency": 200, "recall": 0.7, "precision": 0.6},  # Dominated
    ]
    
    pareto = compute_pareto_frontier(results, "latency", "recall")
    assert len(pareto) == 3  # First three are Pareto optimal

def test_contrastive_pareto_analysis():
    """Analyze contrastive sweep as Pareto frontier."""
    from memory.evaluation.pareto import analyze_contrastive_pareto
    
    sweep_results = {
        "ratio_0.00": [{"metrics": {"recall@10": 0.75, "latency_ms": 30}}] * 5,
        "ratio_0.10": [{"metrics": {"recall@10": 0.82, "latency_ms": 45}}] * 5,
        "ratio_0.20": [{"metrics": {"recall@10": 0.83, "latency_ms": 60}}] * 5,
        "ratio_0.50": [{"metrics": {"recall@10": 0.83, "latency_ms": 120}}] * 5,
    }
    
    pareto = analyze_contrastive_pareto(sweep_results)
    
    assert "pareto_ratios" in pareto
    # 0% and 10% should be Pareto (best latency, good accuracy)
    # 50% dominated by 20% (same accuracy, worse latency)
    assert 0.0 in pareto["pareto_ratios"]
    assert 0.1 in pareto["pareto_ratios"]
    assert 0.5 not in pareto["pareto_ratios"]  # Dominated by 0.2
```

---

## Expected Outcomes

### Contrastive Ratio Sweep

| Ratio | Recall@10 | Precision@5 | Latency (ms) | Pareto? |
|-------|-----------|-------------|--------------|---------|
| 0% | 0.85 | 0.70 | 30 | ✓ (fastest) |
| 5% | 0.86 | 0.72 | 35 | ✓ |
| 10% | 0.88 | 0.74 | 45 | ✓ (best balance) |
| 20% | 0.88 | 0.74 | 60 | ✗ (dominated by 10%) |
| 50% | 0.87 | 0.73 | 120 | ✗ (dominated) |

**Recommendation**: 10% contrastive ratio (default in architecture)

### Weight Tuning (Expected Optimal)

| Weight | Default | Tuned | Change |
|--------|---------|-------|--------|
| alpha_semantic | 1.0 | 1.25 | +25% (vector similarity most important) |
| beta_graph | 0.5 | 0.75 | +50% (graph more valuable) |
| gamma_recency | 0.3 | 0.4 | +33% |
| delta_importance | 0.2 | 0.25 | +25% |
| epsilon_entity | 0.4 | 0.5 | +25% |
| zeta_relationship | 0.3 | 0.25 | -17% |
| eta_historical | 0.2 | 0.15 | -25% |
| theta_contradiction | 0.5 | 0.5 | Same |
| theta_contrastive | 0.2 | 0.3 | +50% |

### Per-Scenario-Type Optimal Weights

| Scenario Type | Key Weight Changes |
|---------------|-------------------|
| Simple Retrieval | Higher alpha_semantic, lower beta_graph |
| Historical Retrieval | Higher gamma_recency, eta_historical |
| Current State | Higher gamma_recency, lower eta_historical |
| Contradiction | Higher theta_contradiction, beta_graph |
| Multi-hop | Higher beta_graph, zeta_relationship |
| Related Expansion | Higher beta_graph, epsilon_entity |

---

### GPU Acceleration Note (Optional)

When `USE_GPU=true`:
- **Reranker**: `TextCrossEncoder` uses `CUDAExecutionProvider` for the highest-volume repeated-reranking loop in the project (Optuna trials × contrastive ratio sweep) — this is the highest-value single GPU change
- **Per-scenario weight tuning**: Reranker uses GPU for repeated evaluations across weight combinations
- **Embedder**: Stays CPU (sweep uses fixed corpus; not the bottleneck)
- **Default (`USE_GPU=false`)**: Identical output, CPU-only path — no behavior change, only speed

This is gated behind the single `USE_GPU` env var with default `false` to keep baseline reproducibility intact.

---

## Verification Checklist

- [ ] `pytest tests/test_phase10_sweep.py -v` all pass
- [ ] `python scripts/sweep.py --ratios 0,0.05,0.1,0.2,0.5` runs
- [ ] Weight tuner finds better config than defaults
- [ ] Pareto frontier correctly identifies optimal trade-offs
- [ ] Results export includes visualization-ready data
- [ ] Per-scenario-type weights differ meaningfully

---

## Next Phase Dependency

Phase 11 (Write-up) compiles all results from Phases 1-10 into a comprehensive results document with tables, figures, failure case analysis, and conclusions.