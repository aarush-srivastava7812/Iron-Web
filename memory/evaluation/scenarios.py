"""
Evaluation scenarios and test cases.
Handles all 6 scenario types from the architecture.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class ScenarioType(Enum):
    SIMPLE_RETRIEVAL = "simple_retrieval"
    HISTORICAL_RETRIEVAL = "historical_retrieval"
    CURRENT_STATE = "current_state"
    CONTRADICTION = "contradiction"
    MULTI_HOP = "multi_hop"
    RELATED_EXPANSION = "related_expansion"


@dataclass
class TestScenario:
    id: str
    query: str
    relevant_memory_ids: List[str]
    scenario_type: ScenarioType
    description: str
    expected_answer: str = ""
    temporal_mode: str = "auto"


# Pre-defined test scenarios
SCENARIOS = [
    # Simple Retrieval
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
    
    # Historical Retrieval
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
    
    # Current State
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
    
    # Contradiction
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
    
    # Multi-hop
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
    
    # Related Expansion
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


def load_scenarios_from_file(file_path: str) -> List[TestScenario]:
    """Load scenarios from JSON file."""
    import json
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    scenarios = []
    for item in data:
        scenarios.append(TestScenario(
            id=item["id"],
            query=item["query"],
            relevant_memory_ids=item["relevant_memory_ids"],
            scenario_type=ScenarioType(item["scenario_type"]),
            description=item["description"],
            expected_answer=item.get("expected_answer", ""),
            temporal_mode=item.get("temporal_mode", "auto")
        ))
    return scenarios


def save_scenarios_to_file(scenarios: List[TestScenario], file_path: str):
    """Save scenarios to JSON file."""
    import json
    data = []
    for s in scenarios:
        data.append({
            "id": s.id,
            "query": s.query,
            "relevant_memory_ids": s.relevant_memory_ids,
            "scenario_type": s.scenario_type.value,
            "description": s.description,
            "expected_answer": s.expected_answer,
            "temporal_mode": s.temporal_mode
        })
    
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)


# Additional functions for compatibility with evaluation scripts
@dataclass
class Query:
    query_id: str
    text: str
    ground_truth_ids: List[str]


@dataclass
class EvaluationScenario:
    name: str
    queries: List[Query]
    k: int = 10
    corpus_path: Optional[str] = None
    
    def get_queries(self) -> List[Query]:
        return self.queries
    
    def get_corpus(self) -> List[Dict[str, Any]]:
        """Get corpus documents for ingestion."""
        if hasattr(self, "_official_corpus"):
            return self._official_corpus
        if self.corpus_path:
            import json
            from pathlib import Path
            path = Path(self.corpus_path)
            if path.exists():
                with open(path) as f:
                    return json.load(f)
        # Return empty - would be implemented with actual data loading
        return []


def get_scenarios(datasets_dir: str = "./data/benchmarks") -> Dict[str, EvaluationScenario]:
    """
    Load evaluation scenarios from benchmark datasets.
    
    Returns dict of scenario_name -> EvaluationScenario
    """
    from pathlib import Path
    import json
    
    scenarios = {}
    # Prefer the official releases over the historical derived subsets.
    from memory.evaluation.official_corpora import (
        LOCOMO_PATH,
        LONGMEMEVAL_PATH,
        load_official_locomo,
        load_official_longmemeval,
    )
    if LOCOMO_PATH.exists():
        corpus, raw_queries = load_official_locomo()
        scenario = EvaluationScenario("LoCoMo", [Query(**query) for query in raw_queries], k=10)
        scenario._official_corpus = corpus
        scenario._official_source_path = str(LOCOMO_PATH)
        scenarios["locomo"] = scenario
    if LONGMEMEVAL_PATH.exists():
        corpus, raw_queries, _ = load_official_longmemeval()
        scenario = EvaluationScenario("LongMemEval", [Query(**query) for query in raw_queries], k=10)
        scenario._official_corpus = corpus
        scenario._official_source_path = str(LONGMEMEVAL_PATH)
        scenarios["longmemeval"] = scenario
    datasets_path = Path(datasets_dir)
    
    # Try to load DMR
    dmr_path = datasets_path / "dmr" / "dmr.json"
    dmr_corpus = datasets_path / "dmr" / "corpus.json"
    if dmr_path.exists():
        with open(dmr_path) as f:
            data = json.load(f)
        queries = [Query(q["query_id"], q["text"], q["ground_truth_ids"]) for q in data.get("queries", [])]
        scenarios["dmr"] = EvaluationScenario("DMR", queries, k=10, corpus_path=str(dmr_corpus))
    
    # Try to load LoCoMo
    locomo_path = datasets_path / "locomo" / "locomo.json"
    locomo_corpus = datasets_path / "locomo" / "corpus.json"
    if locomo_path.exists() and "locomo" not in scenarios:
        with open(locomo_path) as f:
            data = json.load(f)
        queries = [Query(q["query_id"], q["text"], q["ground_truth_ids"]) for q in data.get("queries", [])]
        scenarios["locomo"] = EvaluationScenario("LoCoMo", queries, k=10, corpus_path=str(locomo_corpus))
    
    # Try to load LongMemEval
    longmemeval_path = datasets_path / "longmemeval" / "longmemeval.json"
    longmemeval_corpus = datasets_path / "longmemeval" / "corpus.json"
    if longmemeval_path.exists() and "longmemeval" not in scenarios:
        with open(longmemeval_path) as f:
            data = json.load(f)
        queries = [Query(q["query_id"], q["text"], q["ground_truth_ids"]) for q in data.get("queries", [])]
        scenarios["longmemeval"] = EvaluationScenario("LongMemEval", queries, k=10, corpus_path=str(longmemeval_corpus))
    
    # If no datasets found, return built-in test scenarios
    if not scenarios:
        # Convert built-in scenarios
        queries = [Query(s.id, s.query, s.relevant_memory_ids) for s in SCENARIOS]
        scenarios["builtin"] = EvaluationScenario("Builtin", queries, k=10)
    
    return scenarios
