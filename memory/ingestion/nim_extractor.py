"""
NVIDIA NIM extractor for entity/relation extraction from text.
OpenAI-compatible client for NIM endpoints.
"""
from typing import List, Dict, Any, Optional
import os
import json
import re
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential


from memory.ingestion.extractor import BaseExtractor, validate_extraction


class NIMExtractor(BaseExtractor):
    """
    NVIDIA NIM extractor for structured information extraction.
    Extracts entities, relations, temporal validity, and contradiction detection.
    Real inference model: is_mock=False.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "meta/llama-3.1-70b-instruct",
        timeout: float = 60.0
    ):
        """
        Initialize NIM extractor.
        
        Args:
            api_key: NVIDIA API key (or from NVIDIA_API_KEY env var)
            base_url: NIM endpoint URL
            model: Model identifier
            timeout: Request timeout
        """
        self.api_key = api_key or os.getenv("NVIDIA_API_KEY")
        self.base_url = base_url or os.getenv("NVIDIA_NIM_URL", "https://integrate.api.nvidia.com/v1")
        self.model = model
        
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY required for NIM extractor")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout
        )

    @property
    def is_mock(self) -> bool:
        return False
    
    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3)
    )
    def extract_entities_and_relations(
        self,
        text: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract entities, relations, and temporal info from text.
        
        Returns:
            {
                "entities": [{"id", "name", "type", "description"}],
                "relations": [{"from", "to", "type", "confidence"}],
                "temporal": {"valid_from", "valid_until"},
                "importance": 0.0-1.0
            }
        """
        prompt = self._build_extraction_prompt(text, context)
        
        # Use response_format only for models that support it; many NIM models
        # are reasoning models that don't support structured outputs.
        # We'll try without first, then parse JSON from the response.
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=4096
        )
        
        content = response.choices[0].message.content
        result = self._parse_json_from_response(content)
        normalized = self._normalize_extraction(result)
        return validate_extraction(normalized, extractor_name=f"nim:{self.model}", is_mock=False).to_dict()
    
    def _build_extraction_prompt(self, text: str, context: Optional[str]) -> str:
        ctx = f"\nContext: {context}" if context else ""
        
        return f"""
        Extract structured information from the following text.{ctx}
        
        Text: {text}
        
        Extract:
        1. Entities: people, projects, technologies, concepts, organizations
        2. Relations: USES, PREFERS, SUPERSEDES, CONTRADICTS, RELATED_TO, PART_OF, HAS_SKILL, AVOIDS, LEARNED
        3. Temporal validity: when does this fact apply? (valid_from, valid_unix timestamps)
        4. Importance: how important is this memory? (0.0-1.0)
        
        Output JSON only:
        {{
            "entities": [
                {{"id": "ent_1", "name": "Python", "type": "Technology", "description": "Programming language"}}
            ],
            "relations": [
                {{"from": "ent_1", "to": "ent_2", "type": "USES", "confidence": 0.9}}
            ],
            "temporal": {{"valid_from": 0, "valid_until": 2147483647}},
            "importance": 0.8
        }}
        """
    
    def _parse_json_from_response(self, content: str) -> Dict[str, Any]:
        """Extract and parse JSON from model response, handling thinking process text."""
        # Try direct parse first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON object in markdown code blocks
        json_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_block_match:
            try:
                return json.loads(json_block_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try to find JSON object directly in the text (largest {...} block)
        json_match = re.search(r'(\{.*\})', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Truncated-JSON salvage: long documents can exhaust max_tokens mid-object.
        # Parse the balanced {...} objects inside "entities"/"relations" arrays
        # even when the outer JSON object never closed.
        salvaged = self._salvage_truncated(content)
        if salvaged is not None:
            return salvaged
        
        # Last resort: return empty structure
        return {
            "entities": [],
            "relations": [],
            "temporal": {"valid_from": 0, "valid_until": 2**31 - 1},
            "importance": 0.5
        }
    
    def _salvage_truncated(self, content: str) -> Optional[Dict[str, Any]]:
        """Salvage entities/relations from a truncated JSON response."""
        entities = self._parse_array_objects(content, "entities")
        relations = self._parse_array_objects(content, "relations")
        if not entities and not relations:
            return None
        temporal = {"valid_from": 0, "valid_until": 2**31 - 1}
        m = re.search(r'"valid_from"\s*:\s*(-?\d+)', content)
        if m:
            temporal["valid_from"] = int(m.group(1))
        m = re.search(r'"valid_until"\s*:\s*(-?\d+)', content)
        if m:
            temporal["valid_until"] = int(m.group(1))
        importance = 0.5
        m = re.search(r'"importance"\s*:\s*([0-9.]+)', content)
        if m:
            try:
                importance = float(m.group(1))
            except ValueError:
                pass
        return {
            "entities": entities,
            "relations": relations,
            "temporal": temporal,
            "importance": importance
        }
    
    def _parse_array_objects(self, content: str, key: str) -> List[Dict[str, Any]]:
        """Parse balanced {...} objects inside a possibly-unterminated JSON array."""
        m = re.search(rf'"{key}"\s*:\s*\[', content)
        if not m:
            return []
        objs: List[Dict[str, Any]] = []
        i = m.end()
        n = len(content)
        while i < n:
            brace = content.find('{', i)
            if brace == -1:
                break
            depth = 0
            in_str = False
            esc = False
            j = brace
            complete = False
            while j < n:
                ch = content[j]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == '\\':
                        esc = True
                    elif ch == '"':
                        in_str = False
                else:
                    if ch == '"':
                        in_str = True
                    elif ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            complete = True
                            break
                j += 1
            if not complete:
                break  # truncated object - stop salvaging
            try:
                objs.append(json.loads(content[brace:j + 1]))
            except json.JSONDecodeError:
                pass
            i = j + 1
        return objs
    
    def _normalize_extraction(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize and validate extraction output."""
        entities = raw.get("entities", [])
        relations = raw.get("relations", [])
        
        # Ensure entity IDs are prefixed
        entity_map = {}
        for i, ent in enumerate(entities):
            # Skip relation-like objects the model may have placed in the
            # entities array ({"from": ..., "to": ..., "type": ...}).
            if "from" in ent or "to" in ent:
                continue
            eid = ent.get("id") or f"ent_{i}"
            entity_map[eid] = {
                "id": eid,
                "name": ent.get("name", ""),
                "type": ent.get("type", "Concept"),
                "description": ent.get("description", "")
            }
        
        # Fix relation references
        normalized_relations = []
        for rel in relations:
            from_id = rel.get("from")
            to_id = rel.get("to")
            if from_id in entity_map and to_id in entity_map:
                normalized_relations.append({
                    "from": from_id,
                    "to": to_id,
                    "type": rel.get("type", "RELATED_TO"),
                    "confidence": rel.get("confidence", 0.5)
                })
        
        temporal = raw.get("temporal", {})
        valid_from = temporal.get("valid_from", 0)
        valid_until = temporal.get("valid_until", 2**31 - 1)
        
        return {
            "entities": list(entity_map.values()),
            "relations": normalized_relations,
            "temporal": {"valid_from": valid_from, "valid_until": valid_until},
            "importance": raw.get("importance", 0.5)
        }
    
    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3)
    )
    def judge_answer_quality(
        self,
        query: str,
        context: str,
        answer: str,
        ground_truth: str = ""
    ) -> Dict[str, float]:
        """
        LLM-as-judge for answer quality evaluation.
        Returns faithfulness, relevance, completeness scores.
        """
        prompt = f"""
        Evaluate this answer based on the retrieved context.
        
        Query: {query}
        
        Retrieved Context:
        {context}
        
        Generated Answer: {answer}
        
        {f"Ground Truth Answer: {ground_truth}" if ground_truth else ""}
        
        Score each dimension 0.0-1.0:
        1. FAITHFULNESS: Does the answer only use information from the context? (No hallucination)
        2. RELEVANCE: Does the answer address the query?
        3. COMPLETENESS: Does the answer cover all relevant information from context?
        
        Output JSON only:
        {{"faithfulness": 0.0, "relevance": 0.0, "completeness": 0.0}}
        """
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"},
            max_tokens=512
        )
        
        return json.loads(response.choices[0].message.content)
    
    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3)
    )
    def detect_contradiction(
        self,
        text1: str,
        text2: str
    ) -> Dict[str, Any]:
        """Detect contradiction between two texts."""
        prompt = f"""
        Determine if these two statements contradict each other.
        
        Statement 1: {text1}
        Statement 2: {text2}
        
        Output JSON only:
        {{"is_contradiction": true/false, "confidence": 0.0-1.0, "reasoning": "..."}}
        """
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"},
            max_tokens=512
        )
        
        return json.loads(response.choices[0].message.content)
    
    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3)
    )
    def detect_supersession(
        self,
        old_text: str,
        new_text: str
    ) -> Dict[str, Any]:
        """Detect if new text supersedes old text."""
        prompt = f"""
        Determine if the NEW statement supersedes/replaces the OLD statement 
        (i.e., represents an updated preference, fact, or state).
        
        OLD: {old_text}
        NEW: {new_text}
        
        Output JSON only:
        {{"is_supersession": true/false, "confidence": 0.0-1.0, "reasoning": "..."}}
        """
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"},
            max_tokens=512
        )
        
        return json.loads(response.choices[0].message.content)
    
    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3)
    )
    def extract_skills(
        self,
        episode_texts: List[str]
    ) -> List[Dict[str, Any]]:
        """Extract skill patterns from episodic memories."""
        prompt = f"""
        Analyze these episodic memories and extract reusable skills/patterns:
        
        {chr(10).join([f'- {t}' for t in episode_texts[:20]])}
        
        Output JSON array of skills:
        [{{"name": "...", "description": "...", "conditions": "...", "actions": "..."}}]
        """
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"},
            max_tokens=2048
        )
        
        result = json.loads(response.choices[0].message.content)
        return result.get("skills", [])