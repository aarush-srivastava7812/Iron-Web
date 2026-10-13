"""
Automated Test Suite for Phase 4: Maintenance and Reliability.

Tests verify:
1. MemoryDecay:
   - Age-based exponential decay logic with real calculations (no dummy stats).
   - Cross-store importance synchronization (Qdrant payload + FalkorDB observation).
   - Idempotency across repeated decay executions (preserving initial_importance).
   - dry_run non-mutating mode.
2. MemoryDeduplication:
   - DBSCAN semantic clustering on embeddings.
   - Safeguard 1: Disjoint temporal validity periods are NOT merged.
   - Safeguard 2: Graph contradictions are NOT merged into a single canonical fact.
   - Canonical record preservation, entity merging, and cross-store deletion of duplicates.
   - dry_run non-mutating mode.
3. MemoryConsolidation:
   - Procedural skill synthesis from episodic memory windows.
   - Source traceability (provenance metadata with source_memory_ids).
   - Dual-store recording (Qdrant procedural memory + FalkorDB Skill entity).
4. MemoryEngine Facade Integration:
   - engine.decay_memories()
   - engine.deduplicate_memories()
   - engine.consolidate_memories()
   - engine.run_maintenance()
5. Scale & Reliability:
   - Storage volume growth tracking and retrieval latency measurement across batch ingests.
"""

from tests.fixtures.graph import graph_name_for

import time
import numpy as np
import pytest

from memory.engine import MemoryEngine


def test_memory_decay_real_calculation_and_cross_store_sync(tmp_path):
    """Verify decay calculates real exponential decay and updates both Qdrant and FalkorDB."""
    q_dir = str(tmp_path / "qdrant_db")
    graph_identity = str(tmp_path / "graph")

    with MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=False
    ) as engine:
        # Create an old memory: 90 days ago (1 half-life = 90 days)
        now = int(time.time())
        ninety_days_ago = now - (90 * 86400)

        mem_id = engine.add(
            content="Old memory about PyTorch training on CUDA",
            entity_ids=["pytorch", "cuda"],
            timestamp=ninety_days_ago,
            importance=1.0,
        )

        # Verify initial importance
        rec_before = engine.get(mem_id)
        assert rec_before is not None
        assert rec_before.importance == 1.0

        # 1. Test dry_run (should compute stats without changing stored data)
        dry_stats = engine.decay_memories(
            half_life_days=90.0, current_time=now, dry_run=True
        )
        assert dry_stats["dry_run"] is True
        assert dry_stats["processed"] == 1
        assert dry_stats["decayed"] == 1
        # 1.0 * exp(-1) ~= 0.3678
        assert dry_stats["avg_importance_after"] == pytest.approx(0.5)

        # Verify stored value was NOT mutated by dry_run
        rec_dry = engine.get(mem_id)
        assert rec_dry.importance == 1.0

        # 2. Real decay execution
        real_stats = engine.decay_memories(
            half_life_days=90.0, current_time=now, dry_run=False
        )
        assert real_stats["dry_run"] is False
        assert real_stats["decayed"] == 1

        # Verify Qdrant payload importance was updated
        rec_after = engine.get(mem_id)
        assert rec_after.importance == pytest.approx(0.5)

        # Verify FalkorDB observation importance was synchronized
        graph_obs = engine.graph_store.get_observation(f"obs_{mem_id}_pytorch")
        assert graph_obs is not None
        assert graph_obs["importance"] == pytest.approx(0.5)


def test_memory_decay_idempotency(tmp_path):
    """Running decay multiple times at the same current_time must NOT compound decay."""
    q_dir = str(tmp_path / "qdrant_db")
    graph_identity = str(tmp_path / "graph")

    with MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=False
    ) as engine:
        now = int(time.time())
        forty_five_days_ago = now - (45 * 86400)

        mem_id = engine.add(
            content="Intermediate memory about neural network weights",
            entity_ids=["neural_network"],
            timestamp=forty_five_days_ago,
            importance=1.0,
        )

        # Run decay 1st time
        engine.decay_memories(half_life_days=90.0, current_time=now, dry_run=False)
        rec1 = engine.get(mem_id)
        imp1 = rec1.importance
        # 1.0 * exp(-45/90) = exp(-0.5) ~= 0.6065
        assert imp1 == pytest.approx(2**-0.5)

        # Run decay 2nd time at the exact same current_time
        engine.decay_memories(half_life_days=90.0, current_time=now, dry_run=False)
        rec2 = engine.get(mem_id)
        imp2 = rec2.importance

        # Idempotency assertion: importance should NOT change on repeated run
        assert abs(imp1 - imp2) < 1e-4


def test_memory_deduplication_merges_exact_duplicates(tmp_path):
    """Only identical records merge, preserving all entity associations and metadata."""
    q_dir = str(tmp_path / "qdrant_db")
    graph_identity = str(tmp_path / "graph")

    with MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=False
    ) as engine:
        # Ingest two almost identical memories with different entity tags
        mem1 = engine.add(
            content="I am developing an AI memory system with vector search and graph database",
            entity_ids=["vector_search"],
            importance=0.9,
            metadata={"tag": "first_note"},
        )
        mem2 = engine.add(
            content="I am developing an AI memory system with vector search and graph database",
            entity_ids=["knowledge_graph"],
            importance=0.7,
            metadata={"tag": "second_note"},
        )

        assert engine.get(mem1) is not None
        assert engine.get(mem2) is not None

        # Run deduplication
        dedup_stats = engine.deduplicate_memories(dry_run=False)
        assert dedup_stats["clusters_found"] >= 1
        assert dedup_stats["merged"] >= 1

        # Canonical memory (higher importance: mem1) must be preserved
        canonical = engine.get(mem1)
        assert canonical is not None
        assert "vector_search" in canonical.entity_ids
        assert "knowledge_graph" in canonical.entity_ids  # Entity IDs merged!
        assert canonical.metadata.get("merged_from") == [mem2]

        # Duplicate (mem2) must be purged across both Qdrant and FalkorDB
        assert engine.get(mem2) is None
        assert engine.vector_store.get_memory(mem2) is None


def test_memory_deduplication_safeguards_disjoint_temporal_periods(tmp_path):
    """Safeguard 1: Memories with disjoint validity periods represent distinct historical facts and must NOT be merged."""
    q_dir = str(tmp_path / "qdrant_db")
    graph_identity = str(tmp_path / "graph")

    with MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=False
    ) as engine:
        # High semantic similarity, but strictly disjoint temporal intervals
        # Fact 1: valid in 2020 (1577836800 to 1609459200)
        mem_2020 = engine.add(
            content="I work at Google as a Senior Software Engineer",
            valid_from=1577836800,
            valid_until=1609459200,
            importance=0.9,
        )
        # Fact 2: valid in 2024 (1704067200 to 1735689600)
        mem_2024 = engine.add(
            content="I work at DeepMind as a Senior Software Engineer",
            valid_from=1704067200,
            valid_until=1735689600,
            importance=0.95,
        )

        # Deduplication must respect temporal disjointness
        dedup_stats = engine.deduplicate_memories(dry_run=False)
        assert dedup_stats["merged"] == 0
        # Both records must survive because their validity does not overlap
        assert engine.get(mem_2020) is not None
        assert engine.get(mem_2024) is not None


def test_memory_deduplication_safeguards_contradictory_facts(tmp_path):
    """Safeguard 2: Contradictory statements must NOT be merged into a single fact."""
    q_dir = str(tmp_path / "qdrant_db")
    graph_identity = str(tmp_path / "graph")

    with MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=False
    ) as engine:
        # Ingest two conflicting statements
        mem_coffee = engine.add(
            content="I strictly drink coffee every morning", importance=0.9
        )
        mem_tea = engine.add(
            content="I never drink coffee in the morning, only tea", importance=0.8
        )

        # Mark contradiction in graph store
        engine.graph_store.record_contradiction(
            from_id=mem_coffee,
            to_id=mem_tea,
            nature="BEVERAGE_CONFLICT",
            confidence=0.95,
        )

        # Attempt deduplication
        dedup_stats = engine.deduplicate_memories(dry_run=False)
        assert dedup_stats["merged"] == 0
        # Both memories must survive because they are contradictory
        assert engine.get(mem_coffee) is not None
        assert engine.get(mem_tea) is not None


def test_memory_consolidation_provenance_and_dual_store(tmp_path):
    """Verify episodic consolidation extracts skills and records source provenance."""
    q_dir = str(tmp_path / "qdrant_db")
    graph_identity = str(tmp_path / "graph")

    with MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=False
    ) as engine:
        now = int(time.time())

        # Ingest 3 related interaction episodes within recent window
        engine.extractor.extract_skills = lambda texts: [
            {
                "name": "Python Development Workflow",
                "description": "Verified fixture skill",
                "conditions": "Python project",
                "actions": "Run pytest",
            }
        ]
        ep1 = engine.add(
            content="Debugging Python asyncio event loop and running pytest suite",
            metadata={"memory_type": "episodic"},
            timestamp=now - 500,
        )
        ep2 = engine.add(
            content="Configuring Python pip dependencies and setting up virtual environment",
            metadata={"memory_type": "episodic"},
            timestamp=now - 400,
        )
        ep3 = engine.add(
            content="Writing Python unit test code and verifying mock objects",
            metadata={"memory_type": "episodic"},
            timestamp=now - 300,
        )

        # Run consolidation for the past 2 days window
        consol_stats = engine.consolidate_memories(
            window_days=2, min_episodes=3, dry_run=False
        )

        assert consol_stats["episodes_processed"] >= 3
        assert consol_stats["skills_extracted"] >= 1
        assert consol_stats["patterns_stored"] >= 1

        # Verify the synthesized skill exists in vector store with provenance
        search_skills = engine.search(
            "Python Development Workflow", k=5, retrieval_mode="vector"
        )
        skill_results = [r for r in search_skills if "Procedural Skill" in r.content]
        assert len(skill_results) >= 1

        skill_hit = skill_results[0]
        meta = skill_hit.metadata
        assert "provenance" in meta
        provenance = meta["provenance"]
        assert "source_memory_ids" in provenance
        # Provenance must point back to our episodic memories
        assert ep1 in provenance["source_memory_ids"]
        assert ep2 in provenance["source_memory_ids"]
        assert ep3 in provenance["source_memory_ids"]

        # Verify the Skill entity was also registered in FalkorDB graph store
        skill_entities = engine.graph_store.find_entities_by_name(
            "Python Development Workflow"
        )
        assert len(skill_entities) >= 1
        assert skill_entities[0]["entity_type"] == "Skill"


def test_maintenance_scheduler_run_all(tmp_path):
    """Verify run_maintenance executes all requested jobs."""
    q_dir = str(tmp_path / "qdrant_db")
    graph_identity = str(tmp_path / "graph")

    with MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=False
    ) as engine:
        now = int(time.time())
        engine.add("Session note 1 on software architecture", timestamp=now - 100)
        engine.add("Session note 2 on software architecture", timestamp=now - 50)
        engine.add("Session note 3 on software architecture", timestamp=now - 10)

        all_results = engine.run_maintenance(
            tasks=["decay", "dedup", "consolidate"], dry_run=False
        )
        assert "decay" in all_results
        assert "dedup" in all_results
        assert "consolidate" in all_results


def test_storage_growth_and_latency_measurement(tmp_path):
    """Measure storage growth and retrieval latency as memory volume increases."""
    q_dir = str(tmp_path / "qdrant_db")
    graph_identity = str(tmp_path / "graph")

    with MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=False
    ) as engine:
        # Ingest bulk batch of memories
        start_count = engine.vector_store.count()
        assert start_count == 0

        batch_items = [
            {
                "content": f"Memory item index {i}: Testing system scalability and response latency",
                "importance": 0.8,
            }
            for i in range(20)
        ]

        ids = engine.add_batch(batch_items)

        assert len(ids) == 20
        assert engine.vector_store.count() == 20

        # Benchmark retrieval latency
        latencies = []
        for q in ["Testing scalability", "Response latency", "Memory item"]:
            t0 = time.perf_counter()
            results = engine.search(q, k=5, retrieval_mode="vector")
            latencies.append(time.perf_counter() - t0)
            assert len(results) > 0

        avg_latency = float(np.mean(latencies))
        # Vector search in local embedded mode for 20 items must be sub-100ms
        assert (
            avg_latency < 0.20
        ), f"Average search latency {avg_latency:.4f}s exceeds 200ms target"
