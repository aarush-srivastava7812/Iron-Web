# Hybrid Long-Term AI Memory - Documentation Index

> **Project**: Optimized Hybrid Long-Term Memory Architecture for AI Agents  
> **Stack**: LangGraph · LangSmith · Qdrant · FastEmbed · Kuzu · Contrastive Retrieval  
> **Goal**: <50ms p99 latency, production-ready, minimal complexity

---

## 📁 Phase Documentation

| Phase | Title | Description | Status |
|-------|-------|-------------|--------|
| **1** | [Baseline A: Vector-Only Memory](phase1_baseline_a.md) | Qdrant + FastEmbed semantic retrieval, LangGraph checkpointer for episodic | ✅ Complete |
| **2** | [Graph Representation + Kuzu Schema](phase2_graph_representation.md) | Entities, relations, observations schema; Kuzu embedded graph DB | ✅ Complete |
| **3** | [Hybrid Retrieval: Vector + Graph + Reranker](phase3_hybrid_retrieval.md) | Parallel retrieval, reciprocal rank fusion, cross-encoder reranking | ✅ Complete |
| **4** | [Contrastive Retrieval](phase4_contrastive_retrieval.md) | Contrastive query expansion, negative sampling, margin-based loss | ✅ Complete |
| **5** | [Temporal Fields: valid_from / valid_until](phase5_temporal_fields.md) | Bitemporal memory, time-travel queries, version chains | ✅ Complete |
| **6** | [Contradiction & Supersession Detection](phase6_contradiction_supersession.md) | LLM-as-judge + embedding similarity, automated resolution | ✅ Complete |
| **7** | [Maintenance: Decay, Dedup, Consolidation](phase7_maintenance.md) | Background jobs, importance decay, semantic dedup, procedural consolidation | ✅ Complete |
| **8** | [Evaluation Harness](phase8_evaluation_harness.md) | LangSmith datasets, custom evaluators, CI/CD integration | ✅ Complete |
| **9** | [Ablation Study Framework](phase9_ablation_study.md) | Component isolation, statistical significance, effect sizes | ✅ Complete |
| **10** | [Contrastive Ratio Sweep + Weight Tuning](phase10_contrastive_sweep_weight_tuning.md) | Hyperparameter search, Pareto frontiers, Optuna integration | ✅ Complete |
| **11** | [Write-up & Results Documentation](phase11_writeup.md) | Final report, reproducibility, deployment guide | ✅ Complete |

---

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r ../requirements.txt

# Start Qdrant (vector DB)
docker run -d -p 6333:6333 qdrant/qdrant:v1.9.0

# Run Phase 1 baseline
python -m src.memory.baseline_a

# Run evaluations
python -m src.eval.run_all --phase 1
```

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        LangGraph Agent                           │
└──────────────────────────┬──────────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │    MemoryCoordinator    │  ← LangGraph Node
              └────────────┬────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  Episodic     │ │  Semantic     │ │  Procedural   │
│  (Checkpointer)│ │  (Qdrant)     │ │  (Qdrant)     │
└───────────────┘ └───────┬───────┘ └───────┬───────┘
                          │                  │
                   ┌──────▼──────┐    ┌──────▼──────┐
                   │   Kuzu      │    │  Skills/    │
                   │   Graph     │    │  Patterns   │
                   └─────────────┘    └─────────────┘
```

---

## 📊 Key Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Write latency (p99)** | <50ms | Episodic checkpoint + semantic upsert |
| **Read latency (p99)** | <50ms | Hybrid retrieval + reranking |
| **Recall@10** | >0.85 | LoCoMo / LT-Mem benchmarks |
| **Contradiction detection F1** | >0.80 | Synthetic + human-annotated |
| **Consolidation throughput** | >1000 facts/min | Background async job |

---

## 🔧 Configuration

All configuration via environment variables (see `.env.example`):

```bash
# Core
LANGSMITH_API_KEY=...
OPENAI_API_KEY=...

# Vector DB
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=memory_semantic

# Embeddings (FastEmbed - CPU, no PyTorch)
FASTEMBED_MODEL=BAAI/bge-small-en-v1.5
FASTEMBED_QUANTIZE=INT8

# Graph DB
KUZU_DB_PATH=./data/kuzu.db

# Retrieval weights
VECTOR_WEIGHT=0.5
GRAPH_WEIGHT=0.3
TEMPORAL_WEIGHT=0.2
```

---

## 📖 Reading Order

1. **Start here** → `architecture_plan.md` (root) for full architecture
2. **Implementation** → Phase 1 → Phase 2 → ... sequentially
3. **Evaluation** → Phase 8 → Phase 9 → Phase 10
4. **Results** → Phase 11

---

## 🧪 Running Experiments

```bash
# Full ablation suite (Phases 1-4 variants)
python -m src.eval.ablation --all

# Contrastive ratio sweep
python -m src.eval.contrastive_sweep --ratios 0.1,0.2,0.3,0.4,0.5

# Weight tuning with Optuna
python -m src.eval.weight_tuning --trials 100

# Generate final report
python -m src.eval.report --output docs/RESULTS.md
```

---

## 📚 References

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangSmith Documentation](https://docs.smith.langchain.com/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [FastEmbed Documentation](https://qdrant.github.io/fastembed/)
- [Kuzu Documentation](https://kuzudb.com/)
- [LoCoMo Benchmark](https://github.com/snap-research/LoCoMo)
- [LT-Mem Paper](https://arxiv.org/abs/2501.13956)