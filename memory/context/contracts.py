"""Explicit application-owned profiles, card templates and bounded policies."""

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class AgentProfile(Contract):
    actor_id: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=200)
    instructions: str = Field(min_length=1, max_length=16000)

    @field_validator("actor_id", "version", "instructions")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Profile fields must be nonempty.")
        return value


class FieldRule(Contract):
    predicate: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z][A-Za-z0-9_]*$"
    )
    required: bool = False
    profile_fallback: bool = False
    hot: bool = True
    location: str = Field(default="trip", pattern=r"^(trip|profile|session)$")

    @model_validator(mode="after")
    def safe_fallback(self):
        if self.profile_fallback and (self.required or self.location != "trip"):
            raise ValueError(
                "Only optional trip preferences may fall back to a profile."
            )
        return self


class CardTemplate(Contract):
    card_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1, max_length=200)
    task_types: tuple[str, ...] = Field(min_length=1, max_length=16)
    fields: tuple[str, ...] = Field(min_length=1, max_length=32)
    mood: str | None = Field(default=None, min_length=1, max_length=100)
    guidance: str = Field(default="", max_length=4000)


class ContextPolicy(Contract):
    version: str = "context_v1"
    half_tokens: int = Field(default=1024, ge=1, le=16384)
    card_tokens: int = Field(default=512, ge=1, le=4096)
    max_cards: int = Field(default=3, ge=0, le=3)
    evidence_tokens: int = Field(default=2048, ge=1, le=16384)
    context_limit: int = Field(default=8192, ge=128, le=1000000)
    output_tokens: int = Field(default=1024, ge=1)
    cache_seconds: int = Field(default=300, ge=1, le=300)
    mood_seconds: int = Field(default=1800, ge=1, le=86400)
    cache_bytes: int = Field(default=32 * 1024 * 1024, ge=1024, le=32 * 1024 * 1024)
    cache_entries: int = Field(default=256, ge=1, le=256)

    @model_validator(mode="after")
    def output_fits(self):
        if self.output_tokens >= self.context_limit:
            raise ValueError("Reserve less output than the model context limit.")
        return self


class ContextRequest(Contract):
    subject: str = Field(min_length=1, max_length=200)
    scope: dict = Field(min_length=1, max_length=16)
    task_type: str = Field(min_length=1, max_length=100)
    query: str = Field(default="", max_length=16000)
    session_id: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def explicit_trip(self):
        from memory.lifecycle.models import canonical_json

        if (
            not self.subject.strip()
            or not isinstance(self.scope.get("trip_id"), str)
            or not self.scope["trip_id"].strip()
        ):
            raise ValueError("Context requires an explicit subject and trip_id scope.")
        if "session_id" in self.scope:
            raise ValueError("Pass session_id separately from the exact trip scope.")
        if len(canonical_json(self.scope)) > 4000:
            raise ValueError("Context scope is too large.")
        return self
