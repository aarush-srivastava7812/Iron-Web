"""
Phase 10: Contrastive Sweep & Weight Tuning

Runs contrastive ratio sweep and Optuna-based weight optimization.
"""
import os
import json
import time
import numpy as np
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import argparse
from collections import defaultdict

try:
    import optuna
    from optuna.samplers import TPESampler
    OPTUNA_AVAILABLE = True
except ImportError:
    optuna = None
    TPESampler = None
    OPTUNA_AVAILABLE = False

from memory.evaluation.scenarios import get_scenarios, EvaluationScenario
from memory.evaluation.metrics import evaluate_retrieval
from memory.retrieval.contrastive import ContrastiveRetriever
from memory.retrieval.hybrid import HybridRetriever, RetrievalConfig
from memory.ranking.scorer import ScoringWeights
from memory.evaluation.baselines import load_dmr_dataset, load_locomo_dataset


@dataclass
class ContrastiveSweepResult:
    ratio: float
    scenario_name: str
    metrics: Dict[str, float]
    latency_stats: Dict[str, float]
    num_queries: int
    timestamp: str


@dataclass
class WeightTuningResult:
    scenario_name: str
    best_weights: Dict[str, float]
    best_metrics: Dict[str, float]
    best_trial_number: int
    n_trials: int
    study_name: str
    timestamp: str


class ContrastiveSweepRunner:
    """Runs contrastive ratio sweep across scenarios."""
    
    def __init__(
        self,
        embedder,
        vector_store,
        graph_store,
        reranker,
        scenarios: List[EvaluationScenario],
        output_dir: str = "contrastive_sweep_results",
        use_gpu: bool = False,
        ratios: List[float] = None
    ):
        self.embedder = embedder
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.reranker = reranker
        self.scenarios = scenarios
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.use_gpu = use_gpu
        self.ratios = ratios or [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]
    
    def run_sweep(self) -> List[ContrastiveSweepResult]:
        """Run contrastive ratio sweep on all scenarios."""
        results = []
        
        for scenario in self.scenarios:
            print(f"\n=== Scenario: {scenario.name} ===")
            
            for ratio in self.ratios:
                print(f"  Ratio: {ratio}")
                
                # Create retriever with this contrastive ratio
                config = RetrievalConfig(
                    use_vector=True,
                    use_graph_expansion=True,
                    use_reranker=True,
                    use_contrastive=ratio > 0,
                    use_temporal_filter=True,
                    contrastive_ratio=ratio,
                    vector_candidates=100,
                    graph_hops=2,
                    final_top_k=scenario.k,
                    weights=ScoringWeights()
                )
                
                retriever = HybridRetriever(
                    self.embedder,
                    self.vector_store,
                    self.graph_store,
                    self.reranker,
                    config
                )
                
                # Evaluate
                queries = scenario.get_queries()
                all_results = []
                latencies = []
                
                for query in queries:
                    start = time.perf_counter()
                    retrieved = retriever.retrieve(query.text, k=scenario.k)
                    elapsed = time.perf_counter() - start
                    latencies.append(elapsed * 1000)
                    all_results.append({
                        "query_id": query.query_id,
                        "retrieved_ids": [r.get("memory_id", r.get("id", "")) for r in retrieved],
                        "ground_truth_ids": query.ground_truth_ids
                    })
                
                metrics = evaluate_retrieval(all_results, scenario.k)
                
                result = ContrastiveSweepResult(
                    ratio=ratio,
                    scenario_name=scenario.name,
                    metrics=metrics,
                    latency_stats={
                        "mean_ms": np.mean(latencies),
                        "median_ms": np.median(latencies),
                        "p95_ms": np.percentile(latencies, 95),
                        "p99_ms": np.percentile(latencies, 99),
                        "std_ms": np.std(latencies)
                    },
                    num_queries=len(queries),
                    timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
                )
                
                results.append(result)
        
        return results
    
    def find_pareto_frontier(self, results: List[ContrastiveSweepResult]) -> List[Tuple[float, float, str]]:
        """Find Pareto-optimal (recall, latency) points per scenario."""
        by_scenario = defaultdict(list)
        for r in results:
            by_scenario[r.scenario_name].append(r)
        
        pareto_points = []
        
        for scenario_name, scenario_results in by_scenario.items():
            # Sort by recall descending, then latency ascending
            sorted_results = sorted(
                scenario_results,
                key=lambda x: (-x.metrics.get("recall@10", 0), x.latency_stats.get("mean_ms", float('inf')))
            )
            
            best_latency = float('inf')
            for r in sorted_results:
                recall = r.metrics.get("recall@10", 0)
                latency = r.latency_stats.get("mean_ms", float('inf'))
                
                if latency < best_latency:
                    pareto_points.append((r.ratio, recall, scenario_name))
                    best_latency = latency
        
        return pareto_points
    
    def save_results(self, results: List[ContrastiveSweepResult]):
        """Save sweep results."""
        output_file = self.output_dir / f"contrastive_sweep_{time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump([asdict(r) for r in results], f, indent=2, default=str)
        
        # Save Pareto frontier
        pareto = self.find_pareto_frontier(results)
        pareto_file = self.output_dir / f"pareto_frontier_{time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(pareto_file, 'w') as f:
            json.dump([{"ratio": r, "recall": rec, "scenario": s} for r, rec, s in pareto], f, indent=2)
        
        # Save summary markdown
        summary_file = self.output_dir / f"sweep_summary_{time.strftime('%Y%m%d_%H%M%S')}.md"
        self._write_summary_md(results, pareto, summary_file)
        
        print(f"\nResults saved to {self.output_dir}")
    
    def _write_summary_md(self, results: List[ContrastiveSweepResult], pareto: List, path: Path):
        by_scenario = defaultdict(list)
        for r in results:
            by_scenario[r.scenario_name].append(r)
        
        lines = [
            "# Contrastive Ratio Sweep Results",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        
        for scenario_name, scenario_results in by_scenario.items():
            lines.append(f"## Scenario: {scenario_name}")
            lines.append("")
            lines.append("| Ratio | Recall@10 | Precision@10 | F1@10 | Latency (ms) | Pareto |")
            lines.append("|-------|-----------|--------------|-------|--------------|--------|")
            
            pareto_ratios = set(r for r, _, s in pareto if s == scenario_name)
            
            for r in sorted(scenario_results, key=lambda x: x.ratio):
                recall = r.metrics.get("recall@10", 0)
                precision = r.metrics.get("precision@10", 0)
                f1 = r.metrics.get("f1@10", 0)
                latency = r.latency_stats.get("mean_ms", 0)
                pareto_mark = "✓" if r.ratio in pareto_ratios else ""
                
                lines.append(
                    f"| {r.ratio:.2f} | {recall:.4f} | {precision:.4f} | "
                    f"{f1:.4f} | {latency:.1f} | {pareto_mark} |"
                )
            
            lines.append("")
        
        lines.append("## Pareto Frontier")
        lines.append("")
        lines.append("| Scenario | Ratio | Recall@10 |")
        lines.append("|----------|-------|-----------|")
        for ratio, recall, scenario in pareto:
            lines.append(f"| {scenario} | {ratio:.2f} | {recall:.4f} |")
        
        with open(path, 'w') as f:
            f.write("\n".join(lines))


class WeightTuner:
    """Optuna-based weight optimization for retrieval scoring."""
    
    # Weight parameter bounds
    WEIGHT_BOUNDS = {
        "alpha_semantic": (0.1, 5.0),
        "beta_graph": (0.0, 3.0),
        "gamma_recency": (0.0, 2.0),
        "delta_importance": (0.0, 2.0),
        "epsilon_entity": (0.0, 2.0),
        "zeta_relationship": (0.0, 2.0),
        "eta_historical": (0.0, 2.0),
        "theta_contradiction": (0.0, 2.0),
    }
    
    def __init__(
        self,
        embedder,
        vector_store,
        graph_store,
        reranker,
        scenarios: List[EvaluationScenario],
        output_dir: str = "weight_tuning_results",
        use_gpu: bool = False,
        n_trials: int = 50,
        metric: str = "f1@10"
    ):
        if not OPTUNA_AVAILABLE:
            raise ImportError(
                "optuna is required for WeightTuningRunner. "
                "Please install optuna (e.g. pip install optuna) to use hyperparameter tuning."
            )
        self.embedder = embedder
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.reranker = reranker
        self.scenarios = scenarios
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.use_gpu = use_gpu
        self.n_trials = n_trials
        self.metric = metric
    
    def _create_retriever(self, weights: ScoringWeights, contrastive_ratio: float = 0.1):
        config = RetrievalConfig(
            use_vector=True,
            use_graph_expansion=True,
            use_reranker=True,
            use_contrastive=True,
            use_temporal_filter=True,
            contrastive_ratio=contrastive_ratio,
            vector_candidates=100,
            graph_hops=2,
            final_top_k=10,
            weights=weights
        )
        return HybridRetriever(
            self.embedder, self.vector_store, self.graph_store, self.reranker, config
        )
    
    def _objective(self, trial: Any, scenario: EvaluationScenario) -> float:
        """Optuna objective function."""
        # Sample weights
        weights = ScoringWeights(
            alpha_semantic=trial.suggest_float("alpha_semantic", *self.WEIGHT_BOUNDS["alpha_semantic"]),
            beta_graph=trial.suggest_float("beta_graph", *self.WEIGHT_BOUNDS["beta_graph"]),
            gamma_recency=trial.suggest_float("gamma_recency", *self.WEIGHT_BOUNDS["gamma_recency"]),
            delta_importance=trial.suggest_float("delta_importance", *self.WEIGHT_BOUNDS["delta_importance"]),
            epsilon_entity=trial.suggest_float("epsilon_entity", *self.WEIGHT_BOUNDS["epsilon_entity"]),
            zeta_relationship=trial.suggest_float("zeta_relationship", *self.WEIGHT_BOUNDS["zeta_relationship"]),
            eta_historical=trial.suggest_float("eta_historical", *self.WEIGHT_BOUNDS["eta_historical"]),
            theta_contradiction=trial.suggest_float("theta_contradiction", *self.WEIGHT_BOUNDS["theta_contradiction"]),
        )
        
        retriever = self._create_retriever(weights)
        
        # Evaluate on scenario
        queries = scenario.get_queries()
        all_results = []
        
        for query in queries:
            retrieved = retriever.retrieve(query.text, k=scenario.k)
            all_results.append({
                "query_id": query.query_id,
                "retrieved_ids": [r.get("memory_id", r.get("id", "")) for r in retrieved],
                "ground_truth_ids": query.ground_truth_ids
            })
        
        metrics = evaluate_retrieval(all_results, scenario.k)
        return metrics.get(self.metric, 0.0)
    
    def tune_scenario(self, scenario: EvaluationScenario) -> WeightTuningResult:
        """Tune weights for a single scenario."""
        print(f"\n=== Tuning weights for {scenario.name} ({self.n_trials} trials) ===")
        
        study_name = f"weight_tuning_{scenario.name}_{time.strftime('%Y%m%d_%H%M%S')}"
        study = optuna.create_study(
            direction="maximize",
            sampler=TPESampler(seed=42),
            study_name=study_name
        )
        
        study.optimize(
            lambda trial: self._objective(trial, scenario),
            n_trials=self.n_trials,
            show_progress_bar=True
        )
        
        best_params = study.best_params
        best_weights = ScoringWeights(**best_params)
        
        # Final evaluation with best weights
        retriever = self._create_retriever(best_weights)
        queries = scenario.get_queries()
        all_results = []
        
        for query in queries:
            retrieved = retriever.retrieve(query.text, k=scenario.k)
            all_results.append({
                "query_id": query.query_id,
                "retrieved_ids": [r.get("memory_id", r.get("id", "")) for r in retrieved],
                "ground_truth_ids": query.ground_truth_ids
            })
        
        best_metrics = evaluate_retrieval(all_results, scenario.k)
        
        result = WeightTuningResult(
            scenario_name=scenario.name,
            best_weights=best_params,
            best_metrics=best_metrics,
            best_trial_number=study.best_trial.number,
            n_trials=len(study.trials),
            study_name=study_name,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
        )
        
        # Save study
        study_file = self.output_dir / f"{study_name}.pkl"
        import pickle
        with open(study_file, 'wb') as f:
            pickle.dump(study, f)
        
        return result
    
    def tune_all(self) -> List[WeightTuningResult]:
        """Tune weights for all scenarios."""
        results = []
        
        for scenario in self.scenarios:
            result = self.tune_scenario(scenario)
            results.append(result)
        
        return results
    
    def save_results(self, results: List[WeightTuningResult]):
        """Save tuning results."""
        output_file = self.output_dir / f"weight_tuning_{time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump([asdict(r) for r in results], f, indent=2, default=str)
        
        # Save best weights summary
        summary_file = self.output_dir / f"best_weights_{time.strftime('%Y%m%d_%H%M%S')}.md"
        self._write_weights_md(results, summary_file)
        
        print(f"\nWeight tuning results saved to {self.output_dir}")
    
    def _write_weights_md(self, results: List[WeightTuningResult], path: Path):
        lines = [
            "# Weight Tuning Results",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Optimization metric: {self.metric}",
            f"Trials per scenario: {self.n_trials}",
            "",
        ]
        
        for r in results:
            lines.append(f"## Scenario: {r.scenario_name}")
            lines.append("")
            lines.append(f"**Best trial:** #{r.best_trial_number} / {r.n_trials}")
            lines.append(f"**Best {self.metric}:** {r.best_metrics.get(self.metric, 0):.4f}")
            lines.append("")
            lines.append("### Best Weights")
            lines.append("")
            lines.append("| Weight | Value |")
            lines.append("|--------|-------|")
            for name, value in r.best_weights.items():
                lines.append(f"| {name} | {value:.4f} |")
            lines.append("")
            lines.append("### Full Metrics")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            for name, value in r.best_metrics.items():
                lines.append(f"| {name} | {value:.4f} |")
            lines.append("")
        
        with open(path, 'w') as f:
            f.write("\n".join(lines))


class PerScenarioWeightTuner:
    """Tune separate weights per scenario for production deployment."""
    
    def __init__(
        self,
        embedder,
        vector_store,
        graph_store,
        reranker,
        scenarios: List[EvaluationScenario],
        output_dir: str = "per_scenario_weights",
        use_gpu: bool = False
    ):
        self.embedder = embedder
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.reranker = reranker
        self.scenarios = scenarios
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.use_gpu = use_gpu
    
    def tune(self, n_trials: int = 30) -> Dict[str, ScoringWeights]:
        """Tune per-scenario weights."""
        tuner = WeightTuner(
            self.embedder, self.vector_store, self.graph_store, self.reranker,
            self.scenarios, str(self.output_dir), self.use_gpu, n_trials
        )
        results = tuner.tune_all()
        tuner.save_results(results)
        
        return {r.scenario_name: ScoringWeights(**r.best_weights) for r in results}


def main():
    parser = argparse.ArgumentParser(description="Contrastive sweep & weight tuning")
    parser.add_argument("--mode", choices=["sweep", "tune", "both"], default="both")
    parser.add_argument("--scenarios", nargs="+", default=["dmr", "locomo"],
                        choices=["dmr", "locomo", "longmemeval", "all"])
    parser.add_argument("--output-dir", default="phase10_results")
    parser.add_argument("--use-gpu", action="store_true", help="Use GPU for reranker")
    parser.add_argument("--ratios", nargs="+", type=float, default=None,
                        help="Contrastive ratios to sweep")
    parser.add_argument("--n-trials", type=int, default=50, help="Optuna trials per scenario")
    parser.add_argument("--metric", default="f1@10", help="Optimization metric")
    args = parser.parse_args()
    
    print("Phase 10: Contrastive Sweep & Weight Tuning Framework")
    print("Import this module and instantiate runners with your components.")
    print(f"Default ratios: [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]")


if __name__ == "__main__":
    main()