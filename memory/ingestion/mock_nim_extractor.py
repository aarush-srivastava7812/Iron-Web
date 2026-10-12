from typing import List, Dict, Any, Optional
import json

from memory.ingestion.extractor import BaseExtractor, validate_extraction


class MockNIMExtractor(BaseExtractor):
    """
    Mock NVIDIA NIM extractor for testing.
    Returns deterministic mock extractions based on text content.
    Clearly marked as is_mock=True.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "mock",
        timeout: float = 60.0
    ):
        self.model = model

    @property
    def is_mock(self) -> bool:
        return True
    
    def extract_entities_and_relations(
        self,
        text: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract entities, relations, and temporal info from text.
        Mock implementation based on keyword matching.
        """
        text_lower = text.lower()
        entities = []
        relations = []
        entity_counter = 0
        
        # Simple keyword-based entity extraction for testing
        entity_keywords = {
            "python": {"name": "Python", "type": "Technology", "description": "Programming language"},
            "javascript": {"name": "JavaScript", "type": "Technology", "description": "Programming language"},
            "react": {"name": "React", "type": "Technology", "description": "JavaScript library"},
            "node.js": {"name": "Node.js", "type": "Technology", "description": "JavaScript runtime"},
            "api": {"name": "API", "type": "Concept", "description": "Application Programming Interface"},
            "database": {"name": "Database", "type": "Technology", "description": "Data storage system"},
            "sql": {"name": "SQL", "type": "Technology", "description": "Query language"},
            "docker": {"name": "Docker", "type": "Technology", "description": "Container platform"},
            "kubernetes": {"name": "Kubernetes", "type": "Technology", "description": "Container orchestration"},
            "aws": {"name": "AWS", "type": "Organization", "description": "Cloud provider"},
            "github": {"name": "GitHub", "type": "Organization", "description": "Code hosting platform"},
            "openai": {"name": "OpenAI", "type": "Organization", "description": "AI research company"},
            "gpt": {"name": "GPT", "type": "Technology", "description": "Language model"},
            "llm": {"name": "LLM", "type": "Technology", "description": "Large Language Model"},
            "embedding": {"name": "Embedding", "type": "Concept", "description": "Vector representation"},
            "vector": {"name": "Vector", "type": "Concept", "description": "Mathematical vector"},
            "memory": {"name": "Memory", "type": "Concept", "description": "Information storage"},
            "graph": {"name": "Graph", "type": "Concept", "description": "Data structure"},
            "rag": {"name": "RAG", "type": "Technology", "description": "Retrieval-Augmented Generation"},
        }
        
        for keyword, info in entity_keywords.items():
            if keyword in text_lower:
                entity_counter += 1
                entities.append({
                    "id": f"ent_{entity_counter}",
                    "name": info["name"],
                    "type": info["type"],
                    "description": info["description"]
                })
        
        # Add generic entities if none found
        if not entities:
            entities.append({
                "id": "ent_1",
                "name": "Document",
                "type": "Concept",
                "description": "Text document"
            })
        
        # Create simple relations between consecutive entities
        for i in range(len(entities) - 1):
            relations.append({
                "from": entities[i]["id"],
                "to": entities[i + 1]["id"],
                "type": "RELATED_TO",
                "confidence": 0.7
            })
        
        raw_result = {
            "entities": entities,
            "relations": relations,
            "temporal": {"valid_from": 0, "valid_until": 2**63 - 1},
            "importance": 0.8
        }
        return validate_extraction(raw_result, extractor_name="mock_nim_extractor", is_mock=True).to_dict()
    
    def judge_answer_quality(
        self,
        query: str,
        context: str,
        answer: str,
        ground_truth: str = ""
    ) -> Dict[str, float]:
        """Mock LLM-as-judge."""
        return {"faithfulness": 0.8, "relevance": 0.8, "completeness": 0.7}
    
    def detect_contradiction(
        self,
        text1: str,
        text2: str
    ) -> Dict[str, Any]:
        """Mock contradiction detection."""
        return {"is_contradiction": False, "confidence": 0.5, "reasoning": "Mock detection"}
    
    def detect_supersession(
        self,
        old_text: str,
        new_text: str
    ) -> Dict[str, Any]:
        """Mock supersession detection."""
        return {"is_supersession": False, "confidence": 0.5, "reasoning": "Mock detection"}
    
    def extract_skills(
        self,
        episode_texts: List[str]
    ) -> List[Dict[str, Any]]:
        """Mock skill extraction."""
        return []
