"""Validate public writes before allocating models or mutating either store."""

import json
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from memory.schema import validate_metadata
from memory.lifecycle.models import ClaimInput, SourceInput


class MemoryInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    content: str
    metadata: dict | None = None
    entity_ids: list[str] | None = None
    timestamp: int | None = Field(default=None, ge=-(2**63), le=2**63 - 1)
    valid_from: int = Field(default=0, ge=-(2**63), le=2**63 - 1)
    valid_until: int = Field(default=2**63 - 1, ge=-(2**63), le=2**63 - 1)
    importance: float = Field(default=1.0, ge=0, le=1, allow_inf_nan=False)
    memory_id: str | None = None
    claims: list[ClaimInput] | None = Field(default=None, max_length=32)
    source_info: SourceInput | None = None

    @field_validator("content", "memory_id")
    @classmethod
    def nonempty(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Text and identifiers must be nonempty.")
        return value

    @field_validator("entity_ids")
    @classmethod
    def entity_identifiers(cls, value):
        if value is not None and any(not eid.strip() for eid in value):
            raise ValueError("Entity identifiers must be nonempty.")
        return list(dict.fromkeys(value)) if value is not None else None

    @model_validator(mode="after")
    def check_record(self):
        validate_metadata(self.metadata)
        if {
            "memory_claim_ids",
            "memory_source_id",
            "memory_versioned",
            "memory_evidence",
            "answer_status",
        }.intersection(self.metadata or {}):
            raise ValueError("Metadata cannot forge lifecycle-managed fields.")
        if self.claims is not None and (not self.claims or self.source_info is None):
            raise ValueError(
                "Typed claims need a source_info object and a nonempty claim list."
            )
        if self.source_info is not None and self.entity_ids is not None:
            raise ValueError(
                "Versioned input declares subjects/references through claims, not entity_ids."
            )
        json.dumps(self.metadata, allow_nan=False)
        if (
            self.metadata
            and self.metadata.get("source") is not None
            and not isinstance(self.metadata["source"], str)
        ):
            raise ValueError("Metadata source must be a string.")
        if self.metadata and self.metadata.get("memory_type", "semantic") not in {
            "semantic",
            "episodic",
            "procedural",
        }:
            raise ValueError("Unknown memory type.")
        if self.valid_from > self.valid_until:
            raise ValueError("Validity start cannot exceed expiration.")
        return self
