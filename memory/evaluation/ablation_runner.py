"""
Phase 9: Ablation Study Framework

Runs controlled experiments to measure the impact of each component.
"""
import os
import json
import time
import numpy as np
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from pathlib import Path
import argparse

from memory.evaluation.ablations import get_ablation_configs, create_retriever_for_ablation, AblationConfig
from memory.evaluation.scenarios import get_scenarios, EvaluationScenario
from memory.evaluation.metrics import evaluate_retrieval, aggregate_metrics
from memory.evaluation.baselines import load_dmr_dataset, load_locomo_dataset, load_longmemeval_dataset


@dataclass
class AblationRunResult:
    ablation_name: str
    scenario_name: str
    metrics: Dict[str, float]
    latency_stats: Dict[str, float]
    num_queries: int
    timestamp: str
    config: Dict[str, Any]


class AblationRunner:
    """Runs ablation studies across scenarios."""
    
    def __init__(
        self,
        embedder,
        vector_store,
        graph_store,
        reranker,
        scenarios: List[EvaluationScenario],
        output_dir: str = "ablation_results",
        use_gpu: bool = False,
        bootstrap_iters: int = 1000,
        confidence: float = 0.95
    ):
        self.embedder = embedder
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.reranker = reranker
        self.scenarios = scenarios
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.use_gpu = use_gpu
        self.bootstrap_iters = bootstrap_iters
        self.confidence = confidence
        self.ablation_configs = get_ablation_configs()
    
    def run_single_ablation(
        self,
        ablation_name: str,
        scenario: EvaluationScenario
    ) -> AblationRunResult:
        """Run one ablation on one scenario."""
        print(f"  Running {ablation_name} on {scenario.name}...")
        
        retriever = create_retriever_for_ablation(
            ablation_name,
            self.embedder,
            self.vector_store,
            self.graph_store,
            self.reranker
        )
        
        # Run evaluation
        queries = scenario.get_queries()
        all_results = []
        latencies = []
        
        for query in queries:
            start = time.perf_counter()
            results = retriever.retrieve(query.text, k=scenario.k)
            elapsed = time.perf_counter() - start
            latencies.append(elapsed * 1000)  # ms
            all_results.append({
                "query_id": query.query_id,
                "retrieved_ids": [r.get("memory_id", r.get("id", "")) for r in results],
                "ground_truth_ids": query.ground_truth_ids
            })
        
        # Compute metrics
        metrics = evaluate_retrieval(all_results, scenario.k)
        
        # Bootstrap confidence intervals
        bootstrap_metrics = self._bootstrap_ci(metrics, all_results, scenario.k)
        
        latency_stats = {
            "mean_ms": np.mean(latencies),
            "median_ms": np.median(latencies),
            "p95_ms": np.percentile(latencies, 95),
            "p99_ms": np.percentile(latencies, 99),
            "std_ms": np.std(latencies)
        }
        
        return AblationRunResult(
            ablation_name=ablation_name,
            scenario_name=scenario.name,
            metrics={**metrics, **bootstrap_metrics},
            latency_stats=latency_stats,
            num_queries=len(queries),
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            config=self.ablation_configs[ablation_name].config_modifier(
                self.ablation_configs["full"].config_modifier(
                    type("obj", (object,), {})()
                )
            ).__dict__ if hasattr(self.ablation_configs[ablation_name].config_modifier(
                self.ablation_configs["full"].config_modifier(type("obj", (object,), {})())
            ), '__dict__') else {}
        )
    
    def _bootstrap_ci(self, metrics: Dict, results: List[Dict], k: int) -> Dict[str, float]:
        """Bootstrap confidence intervals for metrics."""
        n = len(results)
        if n < 10:
            return {}
        
        bootstrap_results = {key: [] for key in metrics.keys()}
        
        for _ in range(self.bootstrap_iters):
            # Sample with replacement
            indices = np.random.choice(n, n, replace=True)
            sample_results = [results[i] for i in indices]
            sample_metrics = evaluate_retrieval(sample_results, k)
            for key, val in sample_metrics.items():
                bootstrap_results[key].append(val)
        
        ci_results = {}
        alpha = (1 - self.confidence) / 2
        for key, values in bootstrap_results.items():
            ci_results[f"{key}_ci_lower"] = float(np.percentile(values, alpha * 100))
            ci_results[f"{key}_ci_upper"] = float(np.percentile(values, (1 - alpha) * 100))
            ci_results[f"{key}_std"] = float(np.std(values))
        
        return ci_results
    
    def run_all(self) -> List[AblationRunResult]:
        """Run all ablations on all scenarios."""
        results = []
        
        for ablation_name, ablation_config in self.ablation_configs.items():
            print(f"\n=== Ablation: {ablation_name} ({ablation_config.description}) ===")
            
            for scenario in self.scenarios:
                try:
                    result = self.run_single_ablation(ablation_name, scenario)
                    results.append(result)
                except Exception as e:
                    print(f"  ERROR on {scenario.name}: {e}")
                    continue
        
        return results
    
    def save_results(self, results: List[AblationRunResult]):
        """Save results to JSON and summary table."""
        # Save raw results
        output_file = self.output_dir / f"ablation_results_{time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump([asdict(r) for r in results], f, indent=2, default=str)
        
        # Save summary table
        summary_file = self.output_dir / f"ablation_summary_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        self._write_summary_csv(results, summary_file)
        
        # Save comparison to full system
        comparison_file = self.output_dir / f"ablation_comparison_{time.strftime('%Y%m%d_%H%M%S')}.md"
        self._write_comparison_md(results, comparison_file)
        
        print(f"\nResults saved to {self.output_dir}")
    
    def _write_summary_csv(self, results: List[AblationRunResult], path: Path):
        import csv
        if not results:
            return
        
        # Flatten metrics
        fieldnames = ["ablation_name", "scenario_name", "num_queries", "timestamp"]
        metric_keys = set()
        for r in results:
            metric_keys.update(r.metrics.keys())
        fieldnames.extend(sorted(metric_keys))
        fieldnames.extend([
            "latency_mean_ms", "latency_median_ms", "latency_p95_ms",
            "latency_p99_ms", "latency_std_ms"
        ])
        
        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                row = {
                    "ablation_name": r.ablation_name,
                    "scenario_name": r.scenario_name,
                    "num_queries": r.num_queries,
                    "timestamp": r.timestamp,
                    **r.metrics,
                    **{f"latency_{k}": v for k, v in r.latency_stats.items()}
                }
                writer.writerow(row)
    
    def _write_comparison_md(self, results: List[AblationRunResult], path: Path):
        """Write markdown comparison table vs full system."""
        # Group by scenario
        by_scenario = {}
        for r in results:
            if r.scenario_name not in by_scenario:
                by_scenario[r.scenario_name] = {}
            by_scenario[r.scenario_name][r.ablation_name] = r
        
        lines = [
            "# Ablation Study Results",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        
        for scenario_name, ablation_results in by_scenario.items():
            lines.append(f"## Scenario: {scenario_name}")
            lines.append("")
            
            # Find full system as baseline
            full = ablation_results.get("full")
            if not full:
                lines.append("*Full system not run, skipping comparison*")
                lines.append("")
                continue
            
            lines.append("| Ablation | Recall@10 | Precision@10 | F1@10 | Latency (ms) | Δ Recall | Δ F1 |")
            lines.append("|----------|-----------|--------------|-------|--------------|----------|------|")
            
            for ablation_name, result in sorted(ablation_results.items()):
                recall = result.metrics.get("recall@10", 0)
                precision = result.metrics.get("precision@10", 0)
                f1 = result.metrics.get("f1@10", 0)
                latency = result.latency_stats.get("mean_ms", 0)
                
                if ablation_name == "full":
                    delta_recall = ""
                    delta_f1 = ""
                else:
                    delta_recall = f"{recall - full.metrics.get('recall@10', 0):+.4f}"
                    delta_f1 = f"{f1 - full.metrics.get('f1@10', 0):+.4f}"
                
                lines.append(
                    f"| {ablation_name} | {recall:.4f} | {precision:.4f} | "
                    f"{f1:.4f} | {latency:.1f} | {delta_recall} | {delta_f1} |"
                )
            
            lines.append("")
        
        with open(path, 'w') as f:
            f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="Run ablation study")
    parser.add_argument("--scenarios", nargs="+", default=["dmr", "locomo"],
                        choices=["dmr", "locomo", "longmemeval", "all"],
                        help="Scenarios to run")
    parser.add_argument("--ablations", nargs="+", default=["all"],
                        help="Specific ablations to run (default: all)")
    parser.add_argument("--output-dir", default="ablation_results", help="Output directory")
    parser.add_argument("--use-gpu", action="store_true", help="Use GPU for embedder/reranker")
    parser.add_argument("--bootstrap", type=int, default=1000, help="Bootstrap iterations")
    parser.add_argument("--confidence", type=float, default=0.95, help="Confidence level")
    args = parser.parse_args()
    
    # Load components (these would be initialized properly in real usage)
    # For now, this is the framework - actual instantiation happens in scripts
    print("Ablation study framework ready.")
    print("Import this module and instantiate AblationRunner with your components.")
    print(f"Available ablations: {list(get_ablation_configs().keys())}")
    print(f"Available scenarios: dmr, locomo, longmemeval")


if __name__ == "__main__":
    main()