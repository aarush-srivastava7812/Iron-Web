"""Typed claims. Identity, authority and scope come from application code."""

import json
import math
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def canonical(value):
    def normalize(item):
        if isinstance(item, float) and math.isfinite(item) and item.is_integer():
            return int(item)
        if isinstance(item, dict):
            if any(not isinstance(k, str) for k in item):
                raise ValueError("JSON keys must be strings.")
            return {k: normalize(v) for k, v in item.items()}
        if isinstance(item, list):
            return [normalize(v) for v in item]
        if item is not None and not isinstance(item, (str, int, float, bool)):
            raise ValueError("Values must be JSON compatible.")
        return item

    return json.dumps(
        normalize(value),
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    subject: str = Field(min_length=1, max_length=200)
    predicate: str = Field(min_length=1, max_length=128)
    value: Any
    kind: Literal["fact", "preference", "rule", "instruction", "episode", "procedure"] = "fact"
    importance: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)
    cardinality: Literal["single", "multiple"] = "single"
    action: Literal["assert", "supersede", "correct", "retract"] = "assert"
    object_id: str | None = Field(default=None, min_length=1, max_length=200)
    object_ids: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(
        default_factory=list, max_length=32
    )
    evidence: str | None = Field(default=None, min_length=1, max_length=1024)
    valid_from: int | None = Field(default=None, ge=0)
    valid_until: int = Field(default=2**63 - 1, ge=0, le=2**63 - 1)

    @field_validator("subject", "predicate", "object_id")
    @classmethod
    def nonempty(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Identity and predicate cannot be blank.")
        return value.strip() if value is not None else value

    @model_validator(mode="after")
    def valid(self):
        if any(not ref.strip() for ref in self.object_ids):
            raise ValueError("Entity references cannot be blank.")
        self.object_ids = [ref.strip() for ref in self.object_ids]
        if len(self.object_ids) != len(set(self.object_ids)) or (
            self.object_id and self.object_ids
        ):
            raise ValueError("Use unique object_ids or a single object_id.")
        if len(self.object_ids) > 1 and self.cardinality != "multiple":
            raise ValueError("Multiple object references require multiple cardinality.")
        canonical(self.value)
        if self.value is None and self.action != "retract":
            raise ValueError("Unknown values cannot become facts.")
        if self.action == "retract" and self.value is not None:
            raise ValueError("Retraction must use a null value.")
        if self.action == "correct" and self.valid_from is None:
            raise ValueError("A correction must state when the corrected fact applies.")
        if self.valid_from is not None and self.valid_from > self.valid_until:
            raise ValueError("Invalid validity interval.")
        return self
