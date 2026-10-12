# Phase 9: Ablation Study Framework — Component Contribution Analysis

---

## Overview

**Goal**: Systematically measure the contribution of each component by removing one at a time from the full system and measuring performance delta.

**Scope**:
- Ablation configurations (Full minus one component)
- Statistical significance testing
- Component interaction analysis
- Visualization-ready results export

---

## Deliverables

| Artifact | Path | Description |
|----------|------|-------------|
| Ablation Configs | `memory/evaluation/ablations.py` | All ablation variants |
| Ablation Runner | `scripts/ablate.py` | CLI to run ablation study |
| Statistical Tests | `memory/evaluation/stats.py` | Significance testing |
| Results Analysis | `memory/evaluation/ablation_analysis.py` | Delta computation, visualization data |
| Unit Tests | `tests/test_phase9_ablation.py` | Verify ablation framework |

---

## Implementation Details

### 1. Ablation Configurations (`memory/evaluation/ablations.py`)

```python
"""
Ablation study configurations: Full system minus one component each.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Callable
from memory.ranking.scorer import RetrievalConfig, ScoringWeights

@dataclass
class AblationConfig:
    name: str
    description: str
    config_modifier: Callable[[RetrievalConfig], RetrievalConfig]
    expected_impact: str  # "high", "medium", "low"

# Base Full configuration
def full_config() -> RetrievalConfig:
    return RetrievalConfig(
        use_vector=True,
        use_graph_expansion=True,
        use_reranker=True,
        use_contrastive=True,
        use_temporal_filter=True,
        contrastive_ratio=0.1,
        vector_candidates=100,
        graph_hops=2,
        final_top_k=10,
        weights=ScoringWeights()
    )

# Ablation variants
ABLATIONS = {
    "full": AblationConfig(
        name="Full System",
        description="All components enabled",
        config_modifier=lambda c: c,
        expected_impact="baseline"
    ),
    
    "no_graph": AblationConfig(
        name="No Graph Expansion",
        description="Disable graph expansion (Iron Web layer)",
        config_modifier=lambda c: RetrievalConfig(
            **{**c.__dict__, "use_graph_expansion": False}
        ),
        expected_impact="high"  # Major for multi-hop, related expansion
    ),
    
    "no_contrastive": AblationConfig(
        name="No Contrastive Retrieval",
        description="Disable contrastive candidates",
        config_modifier=lambda c: RetrievalConfig(
            **{**c.__dict__, "use_contrastive": False, "contrastive_ratio": 0.0}
        ),
        expected_impact="medium"  # Helps precision, discrimination
    ),
    
    "no_reranker": AblationConfig(
        name="No Cross-Encoder Reranker",
        description="Disable bge-reranker-base reranking",
        config_modifier=lambda c: RetrievalConfig(
            **{**c.__dict__, "use_reranker": False}
        ),
        expected_impact="high"  # Major precision boost
    ),
    
    "no_temporal": AblationConfig(
        name="No Temporal Filtering",
        description="Disable valid_from/valid_until filtering",
        config_modifier=lambda c: RetrievalConfig(
            **{**c.__dict__, "use_temporal_filter": False}
        ),
        expected_impact="high"  # Critical for historical/current queries
    ),
    
    "no_vector": AblationConfig(
        name="No Vector Search (Graph Only)",
        description="Graph-only retrieval (experimental)",
        config_modifier=lambda c: RetrievalConfig(
            **{**c.__dict__, "use_vector": False, "use_graph_expansion": True}
        ),
        expected_impact="very_high"  # Vector is primary retrieval
    ),
    
    "no_weights": AblationConfig(
        name="Uniform Weights (No Learned Scoring)",
        description="All scoring weights = 1.0 (uniform)",
        config_modifier=lambda c: RetrievalConfig(
            **{**c.__dict__, "weights": ScoringWeights(
                alpha_semantic=1.0, beta_graph=1.0, gamma_recency=1.0,
                delta_importance=1.0, epsilon_entity=1.0, zeta_relationship=1.0,
                eta_historical=1.0, theta_contradiction=1.0
            )}
        ),
        expected_impact="medium"  # Weight tuning matters
    ),
    
    "vector_only": AblationConfig(
        name="Vector Only (Baseline A)",
        description="Pure vector similarity, no graph, no rerank",
        config_modifier=lambda c: RetrievalConfig(
            use_vector=True,
            use_graph_expansion=False,
            use_reranker=False,
            use_contrastive=False,
            use_temporal_filter=False,
            contrastive_ratio=0.0,
            vector_candidates=100,
            graph_hops=2,
            final_top_k=10,
            weights=ScoringWeights()
        ),
        expected_impact="baseline_a"
    ),
}


def get_ablation_configs() -> Dict[str, AblationConfig]:
    return ABLATIONS


def create_retriever_for_ablation(ablation_name: str, embedder, vector_store, graph_store, reranker):
    """Factory to create retriever with ablation config."""
    from memory.retrieval.hybrid import HybridRetriever
    
    config = ABLATIONS[ablation_name].config_modifier(full_config())
    return HybridRetriever(embedder, vector_store, graph_store, reranker, config)
```

### 2. Statistical Tests (`memory/evaluation/stats.py`)

```python
"""
Statistical significance testing for ablation results.
"""
from typing import List, Dict, Tuple
import numpy as np
from scipy import stats

def paired_ttest(baseline_scores: List[float], ablation_scores: List[float]) -> Dict:
    """Paired t-test for per-query score differences."""
    if len(baseline_scores) != len(ablation_scores):
        raise ValueError("Score lists must be same length")
    
    t_stat, p_value = stats.ttest_rel(baseline_scores, ablation_scores)
    
    # Effect size (Cohen's d for paired samples)
    diffs = np.array(baseline_scores) - np.array(ablation_scores)
    cohens_d = np.mean(diffs) / np.std(diffs) if np.std(diffs) > 0 else 0
    
    return {
        "t_statistic": float(t_stat),
        "p_value": float(p_value),
        "significant": p_value < 0.05,
        "cohens_d": float(cohens_d),
        "mean_diff": float(np.mean(diffs)),
        "std_diff": float(np.std(diffs))
    }

def wilcoxon_signed_rank(baseline_scores: List[float], ablation_scores: List[float]) -> Dict:
    """Non-parametric Wilcoxon signed-rank test."""
    stat, p_value = stats.wilcoxon(baseline_scores, ablation_scores, alternative='two-sided')
    
    return {
        "statistic": float(stat),
        "p_value": float(p_value),
        "significant": p_value < 0.05
    }

def bootstrap_confidence_interval(
    baseline_scores: List[float], 
    ablation_scores: List[float],
    n_bootstrap: int = 10000,
    confidence: float = 0.95
) -> Dict:
    """Bootstrap CI for mean difference."""
    diffs = np.array(baseline_scores) - np.array(ablation_scores)
    n = len(diffs)
    
    bootstrap_means = []
    for _ in range(n_bootstrap):
        sample = np.random.choice(diffs, size=n, replace=True)
        bootstrap_means.append(np.mean(sample))
    
    alpha = (1 - confidence) / 2
    lower = np.percentile(bootstrap_means, alpha * 100)
    upper = np.percentile(bootstrap_means, (1 - alpha) * 100)
    
    return {
        "mean_diff": float(np.mean(diffs)),
        "ci_lower": float(lower),
        "ci_upper": float(upper),
        "significant": not (lower <= 0 <= upper)  # CI doesn't cross 0
    }

def compute_all_significance(
    full_results: List[Dict],
    ablation_results: List[Dict],
    metric: str = "recall@10"
) -> Dict:
    """Compute significance for one ablation vs full."""
    # Match by scenario_id
    full_by_scenario = {r["scenario_id"]: r for r in full_results}
    ablation_by_scenario = {r["scenario_id"]: r for r in ablation_results}
    
    common_scenarios = set(full_by_scenario.keys()) & set(ablation_by_scenario.keys())
    
    full_scores = [full_by_scenario[s]["metrics"][metric] for s in common_scenarios]
    ablation_scores = [ablation_by_scenario[s]["metrics"][metric] for s in common_scenarios]
    
    return {
        "metric": metric,
        "n_scenarios": len(common_scenarios),
        "full_mean": float(np.mean(full_scores)),
        "ablation_mean": float(np.mean(ablation_scores)),
        "delta": float(np.mean(full_scores) - np.mean(ablation_scores)),
        "ttest": paired_ttest(full_scores, ablation_scores),
        "wilcoxon": wilcoxon_signed_rank(full_scores, ablation_scores),
        "bootstrap": bootstrap_confidence_interval(full_scores, ablation_scores)
    }
```

### 3. Ablation Runner (`scripts/ablate.py`)

```python
#!/usr/bin/env python3
"""
Ablation study runner.
Usage:
  python scripts/ablate.py --ablations all --metric recall@10
  python scripts/ablate.py --ablations no_graph,no_reranker,no_temporal
  USE_GPU=true python scripts/ablate.py --ablations all  # GPU path (gated by config flag)
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
from memory.evaluation.ablations import get_ablation_configs, create_retriever_for_ablation
from memory.evaluation.stats import compute_all_significance
from memory.evaluation.exporter import export_results

# Global config flag for GPU acceleration (default false for reproducibility)
USE_GPU = os.getenv("USE_GPU", "false").lower() == "true"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ablations", default="all", help="Comma-separated ablation names or 'all'")
    parser.add_argument("--metric", default="recall@10", help="Primary metric for significance")
    parser.add_argument("--output", default=f"ablation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    parser.add_argument("--use-gpu", action="store_true", help="Enable GPU for embedder/reranker (overrides USE_GPU env)")
    args = parser.parse_args()
    
    # GPU flag: CLI arg overrides env var, default false for reproducibility
    use_gpu = args.use_gpu or USE_GPU
    
    # Initialize
    print("Initializing components...")
    embedder = Embedder(use_gpu=use_gpu)
    vector_store = QdrantVectorStore()
    graph_store = KuzuGraphStore()
    reranker = Reranker(use_gpu=use_gpu)
    
    if use_gpu:
        print("  GPU acceleration ENABLED for embedder and reranker (ablation study)")
    else:
        print("  CPU-only path (default) — reproducible baseline")
    
    scenarios = get_all_scenarios()
    ablations = get_ablation_configs()
    
    # Filter ablations
    if args.ablations != "all":
        selected = args.ablations.split(",")
        ablations = {k: v for k, v in ablations.items() if k in selected}
    
    # Always include full as baseline
    if "full" not in ablations:
        ablations["full"] = get_ablation_configs()["full"]
    
    print(f"Running {len(ablations)} configurations on {len(scenarios)} scenarios...")
    
    # Run all ablations
    all_results = {}
    
    for ablation_name, ablation_config in ablations.items():
        print(f"\n--- {ablation_config.name} ---")
        retriever = create_retriever_for_ablation(ablation_name, embedder, vector_store, graph_store, reranker)
        
        results = []
        for scenario in scenarios:
            result = retriever.retrieve(scenario.query, k=10)
            
            retrieved_ids = [r.get("payload", {}).get("memory_id") or r.get("memory_id") or r.get("id") for r in result]
            metrics = compute_all_metrics(retrieved_ids, scenario.relevant_memory_ids)
            
            results.append({
                "scenario_id": scenario.id,
                "query": scenario.query,
                "scenario_type": scenario.scenario_type.value,
                "retrieved_ids": retrieved_ids,
                "metrics": metrics
            })
            
            print(f"  {scenario.id}: {args.metric}={metrics[args.metric]:.3f}")
        
        all_results[ablation_name] = results
    
    # Compute significance vs full
    print("\n=== Significance Analysis ===")
    full_results = all_results["full"]
    
    significance_results = {}
    for ablation_name, results in all_results.items():
        if ablation_name == "full":
            continue
        
        sig = compute_all_significance(full_results, results, args.metric)
        significance_results[ablation_name] = sig
        
        print(f"\n{ablations[ablation_name].name}:")
        print(f"  Full mean: {sig['full_mean']:.4f}")
        print(f"  Ablation mean: {sig['ablation_mean']:.4f}")
        print(f"  Delta: {sig['delta']:.4f}")
        print(f"  p-value (t-test): {sig['ttest']['p_value']:.4f} {'*' if sig['ttest']['significant'] else ''}")
        print(f"  Cohen's d: {sig['ttest']['cohens_d']:.3f}")
        print(f"  Bootstrap CI: [{sig['bootstrap']['ci_lower']:.4f}, {sig['bootstrap']['ci_upper']:.4f}]")
    
    # Export
    export_data = {
        "timestamp": datetime.now().isoformat(),
        "primary_metric": args.metric,
        "ablations": {k: v.name for k, v in ablations.items()},
        "results": all_results,
        "significance": significance_results
    }
    
    with open(args.output, "w") as f:
        json.dump(export_data, f, indent=2, default=str)
    
    print(f"\nResults exported to {args.output}")
    
    graph_store.close()

if __name__ == "__main__":
    main()
```

### 4. Ablation Analysis (`memory/evaluation/ablation_analysis.py`)

```python
"""
Analysis utilities for ablation results: delta tables, interaction effects, visualization data.
"""
from typing import Dict, List, Any
import numpy as np
import pandas as pd

def compute_delta_table(significance_results: Dict, metric: str = "recall@10") -> pd.DataFrame:
    """Create delta table: ablation vs full for each scenario type."""
    rows = []
    
    for ablation_name, sig in significance_results.items():
        row = {
            "ablation": ablation_name,
            "delta": sig["delta"],
            "p_value": sig["ttest"]["p_value"],
            "significant": sig["ttest"]["significant"],
            "cohens_d": sig["ttest"]["cohens_d"],
            "ci_lower": sig["bootstrap"]["ci_lower"],
            "ci_upper": sig["bootstrap"]["ci_upper"]
        }
        rows.append(row)
    
    df = pd.DataFrame(rows)
    df = df.sort_values("delta", ascending=False)  # Biggest impact first
    return df


def compute_per_scenario_type_deltas(
    full_results: List[Dict],
    ablation_results: Dict[str, List[Dict]],
    scenarios_by_type: Dict
) -> Dict:
    """Compute deltas broken down by scenario type."""
    from memory.evaluation.stats import compute_all_significance
    
    deltas_by_type = {}
    
    for scenario_type, scenario_list in scenarios_by_type.items():
        scenario_ids = [s.id for s in scenario_list]
        
        full_subset = [r for r in full_results if r["scenario_id"] in scenario_ids]
        
        deltas_by_type[scenario_type] = {}
        for ablation_name, abla_results in ablation_results.items():
            if ablation_name == "full":
                continue
            
            abla_subset = [r for r in abla_results if r["scenario_id"] in scenario_ids]
            
            if full_subset and abla_subset:
                sig = compute_all_significance(full_subset, abla_subset, "recall@10")
                deltas_by_type[scenario_type][ablation_name] = {
                    "delta": sig["delta"],
                    "significant": sig["ttest"]["significant"],
                    "p_value": sig["ttest"]["p_value"]
                }
    
    return deltas_by_type


def generate_interaction_matrix(
    all_ablation_results: Dict[str, List[Dict]],
    metric: str = "recall@10"
) -> pd.DataFrame:
    """
    Pairwise interaction analysis: does removing A and B together 
    have more/less impact than sum of individual removals?
    """
    # This would require running combined ablations (no_graph + no_reranker, etc.)
    # Placeholder for future extension
    pass


def format_ablation_summary(significance_results: Dict, ablations_meta: Dict) -> str:
    """Generate human-readable ablation summary."""
    lines = ["# Ablation Study Summary\n"]
    
    # Sort by impact
    sorted_ablations = sorted(
        significance_results.items(), 
        key=lambda x: x[1]["delta"], 
        reverse=True
    )
    
    lines.append("## Component Impact Ranking (by Recall@10 delta)\n")
    lines.append("| Component | Delta | p-value | Significant | Cohen's d | 95% CI |")
    lines.append("|-----------|-------|---------|-------------|-----------|--------|")
    
    for ablation_name, sig in sorted_ablations:
        meta = ablations_meta.get(ablation_name, {})
        name = meta.get("name", ablation_name)
        sig_marker = "*" if sig["ttest"]["significant"] else ""
        lines.append(
            f"| {name} | {sig['delta']:.4f} | {sig['ttest']['p_value']:.4f} "
            f"| {sig_marker} | {sig['ttest']['cohens_d']:.3f} | "
            f"[{sig['bootstrap']['ci_lower']:.4f}, {sig['bootstrap']['ci_upper']:.4f}] |"
        )
    
    lines.append("\n*Delta = Full - Ablation (positive = component helps)*\n")
    
    # Interpretation
    lines.append("## Interpretation\n")
    for ablation_name, sig in sorted_ablations:
        meta = ablations_meta.get(ablation_name, {})
        name = meta.get("name", ablation_name)
        impact = meta.get("expected_impact", "unknown")
        
        if sig["delta"] > 0.05 and sig["ttest"]["significant"]:
            lines.append(f"- **{name}**: **Large positive impact** (Δ={sig['delta']:.3f}, p={sig['ttest']['p_value']:.4f}). Critical component.")
        elif sig["delta"] > 0.01 and sig["ttest"]["significant"]:
            lines.append(f"- **{name}**: **Moderate positive impact** (Δ={sig['delta']:.3f}, p={sig['ttest']['p_value']:.4f}). Meaningful contribution.")
        elif sig["ttest"]["significant"]:
            lines.append(f"- **{name}**: **Small but significant impact** (Δ={sig['delta']:.3f}, p={sig['ttest']['p_value']:.4f}).")
        else:
            lines.append(f"- **{name}**: **No significant impact** (Δ={sig['delta']:.3f}, p={sig['ttest']['p_value']:.4f}).")
    
    return "\n".join(lines)


def export_ablation_for_plotting(significance_results: Dict, output_path: str):
    """Export data formatted for plotting (bar charts, forest plots)."""
    import json
    
    plot_data = {
        "ablations": [],
        "deltas": [],
        "ci_lower": [],
        "ci_upper": [],
        "p_values": [],
        "significant": []
    }
    
    for ablation_name, sig in significance_results.items():
        plot_data["ablations"].append(ablation_name)
        plot_data["deltas"].append(sig["delta"])
        plot_data["ci_lower"].append(sig["bootstrap"]["ci_lower"])
        plot_data["ci_upper"].append(sig["bootstrap"]["ci_upper"])
        plot_data["p_values"].append(sig["ttest"]["p_value"])
        plot_data["significant"].append(sig["ttest"]["significant"])
    
    with open(output_path, "w") as f:
        json.dump(plot_data, f, indent=2)
```

### 5. Unit Tests (`tests/test_phase9_ablation.py`)

```python
import pytest
import numpy as np
from memory.evaluation.ablations import get_ablation_configs, full_config
from memory.evaluation.stats import paired_ttest, wilcoxon_signed_rank, bootstrap_confidence_interval
from memory.ranking.scorer import RetrievalConfig

def test_ablation_configs_exist():
    """Verify all planned ablations are defined."""
    ablations = get_ablation_configs()
    
    required = ["full", "no_graph", "no_contrastive", "no_reranker", "no_temporal", "vector_only"]
    for req in required:
        assert req in ablations, f"Missing ablation: {req}"
    
    # Verify each has required fields
    for name, config in ablations.items():
        assert config.name
        assert config.description
        assert config.expected_impact
        assert callable(config.config_modifier)

def test_config_modifiers_produce_valid_configs():
    """Each ablation modifier produces a valid RetrievalConfig."""
    base = full_config()
    ablations = get_ablation_configs()
    
    for name, config in ablations.items():
        modified = config.config_modifier(base)
        assert isinstance(modified, RetrievalConfig)
        assert hasattr(modified, "use_vector")
        assert hasattr(modified, "use_graph_expansion")
        assert hasattr(modified, "use_reranker")
        assert hasattr(modified, "use_contrastive")
        assert hasattr(modified, "use_temporal_filter")

def test_no_graph_disables_graph():
    """No graph ablation disables graph expansion."""
    base = full_config()
    ablations = get_ablation_configs()
    modified = ablations["no_graph"].config_modifier(base)
    
    assert modified.use_vector == True
    assert modified.use_graph_expansion == False
    assert modified.use_reranker == True
    assert modified.use_contrastive == True

def test_no_reranker_disables_reranker():
    base = full_config()
    ablations = get_ablation_configs()
    modified = ablations["no_reranker"].config_modifier(base)
    
    assert modified.use_reranker == False
    assert modified.use_graph_expansion == True

def test_no_temporal_disables_temporal():
    base = full_config()
    ablations = get_ablation_configs()
    modified = ablations["no_temporal"].config_modifier(base)
    
    assert modified.use_temporal_filter == False

def test_vector_only_is_baseline_a():
    base = full_config()
    ablations = get_ablation_configs()
    modified = ablations["vector_only"].config_modifier(base)
    
    assert modified.use_vector == True
    assert modified.use_graph_expansion == False
    assert modified.use_reranker == False
    assert modified.use_contrastive == False
    assert modified.use_temporal_filter == False

def test_paired_ttest():
    """Test paired t-test detects known differences."""
    # Large difference
    baseline = [0.8, 0.85, 0.9, 0.75, 0.85]
    ablation = [0.5, 0.55, 0.6, 0.45, 0.55]
    
    result = paired_ttest(baseline, ablation)
    
    assert result["significant"] == True
    assert result["p_value"] < 0.05
    assert result["mean_diff"] > 0.2
    assert result["cohens_d"] > 0.8  # Large effect
    
    # No difference
    baseline2 = [0.8, 0.8, 0.8, 0.8, 0.8]
    ablation2 = [0.81, 0.79, 0.8, 0.8, 0.8]
    
    result2 = paired_ttest(baseline2, ablation2)
    assert result2["significant"] == False
    assert result2["p_value"] > 0.05

def test_wilcoxon_signed_rank():
    """Test non-parametric test."""
    baseline = [0.8, 0.85, 0.9, 0.75, 0.85]
    ablation = [0.5, 0.55, 0.6, 0.45, 0.55]
    
    result = wilcoxon_signed_rank(baseline, ablation)
    assert result["significant"] == True
    assert result["p_value"] < 0.05

def test_bootstrap_ci():
    """Test bootstrap confidence interval."""
    baseline = [0.8] * 20
    ablation = [0.6] * 20
    
    result = bootstrap_confidence_interval(baseline, ablation, n_bootstrap=1000)
    
    assert result["mean_diff"] == 0.2
    assert result["ci_lower"] > 0.1
    assert result["ci_upper"] < 0.3
    assert result["significant"] == True
    
    # Zero difference
    baseline2 = [0.8] * 20
    ablation2 = [0.8] * 20
    
    result2 = bootstrap_confidence_interval(baseline2, ablation2, n_bootstrap=1000)
    assert abs(result2["mean_diff"]) < 0.01
    assert result2["ci_lower"] <= 0 <= result2["ci_upper"]
    assert result2["significant"] == False

def test_compute_all_significance():
    """Test full significance computation."""
    from memory.evaluation.stats import compute_all_significance
    
    full_results = [
        {"scenario_id": "s1", "metrics": {"recall@10": 0.8}},
        {"scenario_id": "s2", "metrics": {"recall@10": 0.9}},
        {"scenario_id": "s3", "metrics": {"recall@10": 0.7}},
    ]
    
    ablation_results = [
        {"scenario_id": "s1", "metrics": {"recall@10": 0.5}},
        {"scenario_id": "s2", "metrics": {"recall@10": 0.6}},
        {"scenario_id": "s3", "metrics": {"recall@10": 0.4}},
    ]
    
    sig = compute_all_significance(full_results, ablation_results, "recall@10")
    
    assert sig["n_scenarios"] == 3
    assert sig["delta"] > 0.2
    assert sig["ttest"]["significant"] == True
```

---

## Expected Outcomes

### Ablation Impact Ranking (Hypothesized)

| Rank | Ablation | Expected Delta (Recall@10) | Rationale |
|------|----------|---------------------------|-----------|
| 1 | no_vector | -0.30 to -0.40 | Vector is primary retrieval |
| 2 | no_graph | -0.15 to -0.25 | Critical for multi-hop, related |
| 3 | no_reranker | -0.10 to -0.20 | Major precision boost |
| 4 | no_temporal | -0.10 to -0.20 | Critical for historical/current |
| 5 | no_contrastive | -0.03 to -0.08 | Precision improvement |
| 6 | no_weights | -0.02 to -0.05 | Weight tuning matters less |

### Per-Scenario-Type Impact

| Scenario Type | Most Critical Component |
|---------------|------------------------|
| Simple Retrieval | Vector (reranker helps) |
| Historical Retrieval | Temporal filtering |
| Current State | Temporal filtering |
| Contradiction | Graph (contradiction edges) |
| Multi-hop | Graph expansion |
| Related Expansion | Graph expansion |

---

### GPU Acceleration Note (Optional)

When `USE_GPU=true` or `--use-gpu`:
- **Embedder**: FastEmbed uses `CUDAExecutionProvider` for repeated re-embedding across ablation configs
- **Reranker**: `TextCrossEncoder` uses `CUDAExecutionProvider` for repeated reranking across ablation configs
- **Default (`USE_GPU=false`)**: Identical output, CPU-only path — ensures baseline ablation results stay reproducible on CPU-only hardware for anyone re-running the repo

This is gated behind the single `USE_GPU` env var (or `--use-gpu` CLI flag) with default `false` to keep baseline reproducibility intact.

---

## Verification Checklist

- [ ] `pytest tests/test_phase9_ablation.py -v` all pass
- [ ] `python scripts/ablate.py --ablations all` runs all ablations
- [ ] Significance tests compute correctly
- [ ] Delta table generated and sorted by impact
- [ ] Per-scenario-type breakdown available
- [ ] Results export includes statistical metadata

---

## Next Phase Dependency

Phase 10 (Contrastive Ratio Sweep + Weight Tuning) uses the evaluation harness to systematically vary contrastive_ratio (0%, 5%, 10%, 20%, 50%) and scoring weights to find optimal configuration.