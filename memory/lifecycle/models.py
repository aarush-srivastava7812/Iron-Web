"""Explicit ingestion contracts; source authority is not inferred from text."""

import json
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def canonical_json(value):
    def normalize(item):
        if isinstance(item, float) and item.is_integer():
            return int(item)
        if isinstance(item, dict):
            return {key: normalize(v) for key, v in item.items()}
        if isinstance(item, list):
            return [normalize(v) for v in item]
        return item

    return json.dumps(
        normalize(value),
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


class SourceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    origin: Literal["user", "agent", "tool", "import"] = "agent"
    actor_id: str = Field(min_length=1, max_length=200)
    user_confirmed: bool = False
    event_id: str | None = Field(default=None, min_length=1, max_length=200)
    evidence_group: str | None = Field(default=None, min_length=1, max_length=200)
    quality: float = Field(default=0.7, ge=0, le=1, allow_inf_nan=False)
    recorded_at: int | None = Field(default=None, ge=0, le=2**63 - 1)

    @model_validator(mode="after")
    def authority(self):
        if self.user_confirmed and self.origin != "user":
            raise ValueError("Only a user-origin source can be user-confirmed.")
        if not self.actor_id.strip():
            raise ValueError("Source actor must be nonempty.")
        return self

    def support_group(self):
        # Agents repeating one another are not independent corroboration.
        return self.evidence_group or (
            "agent_assertions"
            if self.origin == "agent"
            else self.origin + ":" + self.actor_id
        )


class ClaimInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    subject: str = Field(min_length=1, max_length=200)
    predicate: str = Field(min_length=1, max_length=128)
    value: Any
    kind: Literal[
        "fact", "preference", "instruction", "rule", "episode", "procedure"
    ] = "fact"
    scope: dict = Field(default_factory=dict)
    cardinality: Literal["single", "multiple"] = "single"
    action: Literal["assert", "confirm", "correct", "supersede", "alias", "retract"] = (
        "assert"
    )
    targets: list[str] | None = Field(default=None, max_length=64)
    protected: bool | None = None
    valid_from: int = Field(default=0, ge=0, le=2**63 - 1)
    valid_until: int = Field(default=2**63 - 1, ge=0, le=2**63 - 1)
    effective_at: int | None = Field(default=None, ge=0, le=2**63 - 1)
    half_life_days: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    aliases: list[str] = Field(default_factory=list, max_length=16)
    references: list[str] = Field(default_factory=list, max_length=16)
    reason: str = Field(default="", max_length=2000)

    @field_validator("subject", "predicate")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Claim subject and predicate must be nonempty.")
        return value.strip()

    @model_validator(mode="after")
    def validate_claim(self):
        canonical_json(self.value)
        canonical_json(self.scope)
        if self.value is None and self.action != "retract":
            raise ValueError("An unknown value is not an answerable claim.")
        if self.valid_from > self.valid_until:
            raise ValueError("Claim validity start cannot exceed its end.")
        if self.protected and self.kind not in {"instruction", "rule"}:
            raise ValueError("Only instructions and rules may receive protection.")
        if self.targets is not None and (
            not self.targets or any(not s.strip() for s in self.targets)
        ):
            raise ValueError("Targets must contain nonempty claim IDs.")
        if any(not s.strip() for s in self.references + self.aliases):
            raise ValueError(
                "Claim reference names and question labels must be nonempty."
            )
        if self.kind == "episode":
            self.cardinality = "multiple"
        if self.action == "alias" and (
            not isinstance(self.value, str) or not self.value.strip()
        ):
            raise ValueError("An alias requires a nonempty canonical subject name.")
        if self.action == "alias" and self.scope:
            raise ValueError(
                "Accepted identities are graph-wide; scoped names need distinct subject identifiers."
            )
        return self
