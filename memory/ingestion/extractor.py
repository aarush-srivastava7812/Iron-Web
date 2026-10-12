"""
Unified Extractor Protocol and Data Models for Iron Web / Hybrid Memory.
Provides formal typing, validation, and marking for real (NIM) vs mock extraction.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
import hashlib
import unicodedata


def canonicalize_entities(raw):
    """Derive cross-document identities from normalized type/name, remapping edges."""
    if not isinstance(raw, dict):
        raise ValueError("Extraction must be a JSON object.")
    result = dict(raw)
    entities, mapping = [], {}
    for entity in raw.get("entities", []):
        if not isinstance(entity, dict) or not entity.get("name"):
            raise ValueError("Extracted entities require a name.")
        key = unicodedata.normalize(
            "NFKC", entity.get("type", "Concept") + ":" + entity["name"]
        ).casefold()
        key = " ".join(key.split())
        eid = "ent_" + hashlib.sha256(key.encode()).hexdigest()[:24]
        mapping[entity.get("id", entity["name"])] = eid
        entities.append(dict(entity, id=eid))
    relations = []
    for relation in raw.get("relations", []):
        source, target = (
            relation.get("from", relation.get("from_id")),
            relation.get("to", relation.get("to_id")),
        )
        if source not in mapping or target not in mapping:
            raise ValueError("Extraction relation references an unknown entity.")
        relations.append(
            dict(relation, **{"from": mapping[source], "to": mapping[target]})
        )
    result.update(entities=entities, relations=relations)
    return result


class ExtractedEntity(BaseModel):
    """Normalized entity extracted from text."""

    id: str
    name: str
    type: str = "Concept"
    description: str = ""

    @field_validator("id")
    @classmethod
    def clean_id(cls, v: str) -> str:
        cleaned = v.strip().lower().replace(" ", "_")
        return cleaned if cleaned else "ent_unknown"


class ExtractedRelation(BaseModel):
    """Normalized semantic relationship between two entities."""

    from_id: str
    to_id: str
    type: str = "RELATED_TO"
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class ExtractedTemporal(BaseModel):
    """Validity interval timestamps (bitemporal event/validity bounds)."""

    valid_from: int = 0
    valid_until: int = 2**63 - 1

    @field_validator("valid_until")
    @classmethod
    def check_bounds(cls, v: int, info) -> int:
        if v < info.data.get("valid_from", 0):
            raise ValueError("Validity start cannot exceed expiration.")
        return v


class ExtractionResult(BaseModel):
    """
    Validated extraction result returned by all extractor implementations.
    Explicitly tracks whether extraction was performed by a real model or mock.
    """

    entities: List[ExtractedEntity] = Field(default_factory=list)
    relations: List[ExtractedRelation] = Field(default_factory=list)
    temporal: ExtractedTemporal = Field(default_factory=ExtractedTemporal)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    extractor_name: str = "unknown"
    is_mock: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to standard dictionary matching legacy ingestion pipeline expectations."""
        return {
            "entities": [e.model_dump() for e in self.entities],
            "relations": [
                {
                    "from": r.from_id,
                    "to": r.to_id,
                    "type": r.type,
                    "confidence": r.confidence,
                }
                for r in self.relations
            ],
            "temporal": {
                "valid_from": self.temporal.valid_from,
                "valid_until": self.temporal.valid_until,
            },
            "importance": self.importance,
            "extractor_name": self.extractor_name,
            "is_mock": self.is_mock,
        }


def validate_extraction(
    raw: Dict[str, Any], extractor_name: str = "extractor", is_mock: bool = False
) -> ExtractionResult:
    """
    Validate and normalize extraction data structures before writing to stores.
    Guarantees schema compliance and referential integrity of relations.
    """
    raw_entities = raw.get("entities", [])
    raw_relations = raw.get("relations", [])
    raw_temporal = raw.get("temporal", {})
    raw_importance = raw.get("importance", 0.5)

    entities: List[ExtractedEntity] = []
    seen_ids = set()

    for idx, e in enumerate(raw_entities):
        eid = str(e.get("id") or f"ent_{idx}").strip().lower().replace(" ", "_")
        name = str(e.get("name") or eid).strip()
        etype = str(e.get("type") or "Concept").strip()
        desc = str(e.get("description") or "").strip()
        if eid not in seen_ids:
            seen_ids.add(eid)
            entities.append(
                ExtractedEntity(id=eid, name=name, type=etype, description=desc)
            )

    # Validate relations (ensure endpoints exist in extracted entities)
    relations: List[ExtractedRelation] = []
    for r in raw_relations:
        from_id = (
            str(r.get("from") or r.get("from_id") or "")
            .strip()
            .lower()
            .replace(" ", "_")
        )
        to_id = (
            str(r.get("to") or r.get("to_id") or "").strip().lower().replace(" ", "_")
        )
        rtype = str(r.get("type") or "RELATED_TO").strip()
        conf = float(r.get("confidence", 0.7))

        if from_id in seen_ids and to_id in seen_ids and from_id != to_id:
            relations.append(
                ExtractedRelation(
                    from_id=from_id, to_id=to_id, type=rtype, confidence=conf
                )
            )

    # Validate temporal
    vf = (
        int(raw_temporal.get("valid_from", 0))
        if raw_temporal.get("valid_from") is not None
        else 0
    )
    vu = (
        int(raw_temporal.get("valid_until", 2**63 - 1))
        if raw_temporal.get("valid_until") is not None
        else 2**63 - 1
    )
    if vu < vf:
        raise ValueError("Extraction contains an invalid validity interval.")

    # Validate importance
    imp = float(raw_importance) if raw_importance is not None else 0.5

    return ExtractionResult(
        entities=entities,
        relations=relations,
        temporal=ExtractedTemporal(valid_from=vf, valid_until=vu),
        importance=imp,
        extractor_name=extractor_name,
        is_mock=is_mock,
    )


class BaseExtractor(ABC):
    """Abstract base class for all memory extractors."""

    @property
    @abstractmethod
    def is_mock(self) -> bool:
        """Indicate whether this extractor is a mock or a real neural model."""
        pass

    @abstractmethod
    def extract_entities_and_relations(
        self, text: str, context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Extract entities, relations, temporal validity, and importance."""
        pass

    @abstractmethod
    def detect_contradiction(self, text1: str, text2: str) -> Dict[str, Any]:
        """Determine if two statements contradict."""
        pass

    @abstractmethod
    def detect_supersession(self, old_text: str, new_text: str) -> Dict[str, Any]:
        """Determine if a new statement supersedes an older statement."""
        pass

    @abstractmethod
    def judge_answer_quality(
        self, query: str, context: str, answer: str, ground_truth: str = ""
    ) -> Dict[str, float]:
        """Evaluate generated answer quality."""
        pass
