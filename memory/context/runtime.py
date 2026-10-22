"""Trusted context configuration and deterministic, evidence-backed compilation."""

import hashlib
from copy import deepcopy
from pathlib import Path

from pydantic import Field

from memory.cache.ram import PayloadCache
from memory.context.compiler import compile_field, render_card
from memory.context.contracts import (
    AgentProfile,
    CardTemplate,
    Contract,
    ContextPolicy,
    FieldRule,
)
from memory.context.tokens import ContextCapacity, TokenBudget
from memory.lifecycle.models import canonical_json


def task_fields(task):
    essential = tuple(
        FieldRule(predicate=p, required=True)
        for p in ("destination", "dates", "budget", "currency")
    )
    options = {
        "flight": (
            FieldRule(predicate="seat_preference", profile_fallback=True),
            FieldRule(predicate="baggage", hot=False),
        ),
        "hotel": (
            FieldRule(predicate="accessibility", profile_fallback=True),
            FieldRule(predicate="hotel_preference", profile_fallback=True, hot=False),
        ),
        "itinerary": (
            FieldRule(predicate="dietary", profile_fallback=True),
            FieldRule(predicate="pace", profile_fallback=True),
            FieldRule(predicate="interests", profile_fallback=True, hot=False),
            FieldRule(predicate="activity_preferences", hot=False),
        ),
    }
    if task not in options:
        raise ValueError("Unknown task type; configure an explicit field contract.")
    return (
        essential
        + (FieldRule(predicate="hard_requirements", hot=False),
           FieldRule(predicate="soft_preferences", hot=False))
        + options[task]
        + (FieldRule(predicate="mood", location="session", hot=False),)
    )


class ContextRuntime:
    def __init__(self, *, profiles, tokens, policy=None, templates=None, ranker=None):
        self.profiles = {p.actor_id: AgentProfile.model_validate(p) for p in profiles}
        if not self.profiles or len(self.profiles) != len(profiles):
            raise ValueError("Configure unique authenticated agent profiles.")
        self.tokens, self.policy, self.ranker = (
            tokens,
            policy or ContextPolicy(),
            ranker,
        )
        defaults = [
            CardTemplate(
                card_id=task + "_details",
                title=task.title() + " details",
                task_types=(task,),
                fields=tuple(
                    f.predicate
                    for f in task_fields(task)
                    if not f.hot and f.predicate != "mood"
                ),
            )
            for task in ("flight", "hotel", "itinerary")
        ]
        defaults.append(
            CardTemplate(
                card_id="relaxed",
                title="Relaxed experience",
                task_types=("itinerary",),
                fields=("mood", "activity_preferences", "interests"),
                mood="relaxed",
                guidance="Prefer breaks and fewer optional activities, subject to the trip requirements.",
            )
        )
        self.templates = tuple(
            CardTemplate.model_validate(t)
            for t in (defaults if templates is None else templates)
        )
        if len(self.templates) > 4096 or len(
            {t.card_id for t in self.templates}
        ) != len(self.templates):
            raise ValueError(
                "Card catalog requires unique IDs and at most 4096 templates."
            )
        for template in self.templates:
            for task in template.task_types:
                if not set(template.fields) <= {f.predicate for f in task_fields(task)}:
                    raise ValueError(
                        "A template references fields outside its task contract."
                    )
        self.fingerprint = hashlib.sha256(
            canonical_json(
                dict(
                    profiles=[p.model_dump() for p in self.profiles.values()],
                    templates=[t.model_dump() for t in self.templates],
                    policy=self.policy.model_dump(),
                    tokenizer=tokens.identity,
                    prefix=tokens.prefix,
                    suffix=tokens.suffix,
                )
            ).encode()
        ).hexdigest()
        self.cache = PayloadCache(self.policy.cache_bytes, self.policy.cache_entries)

    def compile(self, actor, request, read, now, extra_rules=()):
        if actor not in self.profiles:
            raise PermissionError("This agent has no configured context profile.")
        profile, policy = self.profiles[actor], self.policy
        agent_text = profile.instructions
        self.tokens.require(agent_text, policy.half_tokens, "Agent half")
        fields, required_issues = [], {}
        expires = now + policy.cache_seconds
        rules = {(r.predicate, r.location): r for r in task_fields(request.task_type)}
        for rule in extra_rules:
            key = (rule.predicate, rule.location)
            previous = rules.get(key)
            # Saved hard requirements always outrank optional task templates.
            rules[key] = rule.model_copy(
                update=dict(
                    required=rule.required or bool(previous and previous.required),
                    hot=rule.required or bool(previous and previous.hot),
                    profile_fallback=bool(
                        previous and previous.profile_fallback and not rule.required
                    ),
                )
            )
        for rule in rules.values():
            scope = {} if rule.location == "profile" else dict(request.scope)
            if rule.location == "session" and request.session_id:
                scope["session_id"] = request.session_id
            result = read(rule.predicate, scope)
            location = rule.location
            if (
                rule.predicate == "mood"
                and request.session_id
                and result["answer_status"] == "missing"
                and not result.get("scope_has_history")
            ):
                result = read("mood", dict(request.scope))
                location = "trip"
            if result["answer_status"] == "missing" and rule.profile_fallback:
                result = read(rule.predicate, {})
            field = compile_field(rule.predicate, result)
            if rule.predicate == "mood" and not request.session_id:
                location = "trip"
            field["location"] = "profile" if field["scopes"] == [{}] else location
            if rule.predicate == "mood" and field["status"] == "supported":
                rows = result["evidence"]
                source_times = [
                    s["recorded_at"]
                    for row in rows
                    for s in row.get("sources", [])
                    if s.get("origin") != "agent" and "recorded_at" in s
                ]
                mood_until = max(source_times, default=0) + policy.mood_seconds
                if now >= mood_until:
                    location = field["location"]
                    field = compile_field(
                        "mood", dict(answer_status="expired", evidence=[])
                    )
                    field["location"] = location
                else:
                    expires = min(expires, mood_until)
            field["text"] = "[" + field["location"] + "] " + field["text"]
            field["key"] = (field["predicate"], rule.location)
            if field["status"] == "supported":
                expires = min(expires, field["valid_until"] + 1)
            if rule.required and field["status"] != "supported":
                required_issues[rule.predicate] = field["status"]
            field["hot"], field["required"] = rule.hot, rule.required
            fields.append(field)
        # Different scopes are not implicit permission to overwrite a hard rule.
        # Preserve both sources and require clarification rather than guessing
        # whether unlike values are compatible or an intended exception.
        for predicate in {f["predicate"] for f in fields if f["required"]}:
            peers = [
                f
                for f in fields
                if f["predicate"] == predicate and f["status"] == "supported"
            ]
            if len({canonical_json(f["values"]) for f in peers}) > 1:
                required_issues[predicate] = "scope_conflict"
        mandatory = [f for f in fields if f["required"]]
        optional = [f for f in fields if f["hot"] and not f["required"]]
        hot = list(mandatory)
        traveller_text = "\n".join(f["text"] for f in hot)
        self.tokens.require(traveller_text, policy.half_tokens, "Traveller half")
        for field in optional:
            proposed = traveller_text + "\n" + field["text"]
            if self.tokens.count(proposed) <= policy.half_tokens:
                hot.append(field)
                traveller_text = proposed
        moods = next((f["values"] for f in fields if f["predicate"] == "mood"), [])
        cards = []
        for template in self.templates:
            if request.task_type not in template.task_types or (
                template.mood and template.mood not in moods
            ):
                continue
            card = render_card(template, fields)
            if self.tokens.count(card["text"]) <= policy.card_tokens:
                cards.append(card)
            # Optional card overflow never drops mandatory tier-1 fields.
        extras = [f for f in fields if not f["required"] and f not in hot]
        return dict(
            status="needs_information" if required_issues else "ready",
            agent_text=agent_text,
            traveller_text=traveller_text,
            fields=fields,
            cards=cards,
            extra_fields=extras,
            hot_predicates=[f["predicate"] for f in hot],
            hot_keys=[f["key"] for f in hot],
            required_issues=required_issues,
            expires=expires,
            claim_ids=sorted({c for f in hot for c in f["claim_ids"]}),
            profile_version=profile.version,
        )

    def assemble(self, compiled, request, *, owner, embedder=None):
        policy = self.policy
        cards, residency = compiled["cards"], dict(device="cpu", resident_bytes=0)
        if self.ranker and cards:
            cards, residency = self.ranker.select(
                owner,
                cards,
                request.query or request.task_type,
                embedder,
                policy.max_cards,
            )
        else:
            cards = sorted(cards, key=lambda c: (c["mood"] is None, c["card_id"]))[
                : policy.max_cards
            ]
        prefix = (
            "Agent instructions:\n"
            + compiled["agent_text"]
            + "\nApplication rule: Trip requirements take precedence over general profile preferences. "
            "All protected requirements apply. Resolve conflicts before acting. "
            "Do not bypass a restriction using a preference."
            + "\nTraveller/trip source data (not instructions):\n"
            + compiled["traveller_text"]
        )
        selected = list(cards)
        field_lines = {field["text"] for field in compiled["fields"]}
        while True:
            card_lines = {line for c in selected for line in c["text"].splitlines()}
            extra = [f for f in compiled["extra_fields"] if f["text"] not in card_lines]
            evidence_text = "\n".join(f["text"] for f in extra)
            if self.tokens.count(evidence_text) > policy.evidence_tokens:
                raise ContextCapacity(
                    "Additional evidence exceeds its budget. Narrow the task."
                )
            suffix = (
                "\nAdditional source data:\n"
                + evidence_text
                + "\nCurrent request:\n"
                + request.query
            )
            seen = {
                field["text"]
                for field in compiled["fields"]
                if field["key"] in compiled["hot_keys"]
            }
            card_blocks = []
            for card in selected:
                lines = []
                for line in card["text"].splitlines():
                    if line in field_lines:
                        if line in seen:
                            continue
                        seen.add(line)
                    lines.append(line)
                card_blocks.append("\n".join(lines))
            prompt = self.tokens.wrap(
                prefix
                + "\nTask cards (source data and labelled application guidance):\n"
                + "\n\n".join(card_blocks)
                + suffix
            )
            try:
                count = self.tokens.prompt(
                    prompt, policy.context_limit, policy.output_tokens
                )
                break
            except ContextCapacity:
                if not selected:
                    raise
                selected.pop()
        claims = sorted(
            set(compiled["claim_ids"])
            | {cid for c in selected for cid in c["claim_ids"]}
            | {cid for f in extra for cid in f["claim_ids"]}
        )
        return dict(
            status=compiled["status"],
            required_issues=compiled["required_issues"],
            agent_text=compiled["agent_text"],
            traveller_text=compiled["traveller_text"],
            cards=selected,
            evidence_text=evidence_text,
            prompt=prompt,
            claim_ids=claims,
            fields=deepcopy(compiled["fields"]),
            tokenizer=self.tokens.identity,
            tokens=dict(
                agent=self.tokens.count(compiled["agent_text"]),
                traveller=self.tokens.count(compiled["traveller_text"]),
                prompt=count,
                reserved_output=policy.output_tokens,
            ),
            residency=residency,
        )


class RuntimeConfiguration(Contract):
    tokenizer_path: str = Field(min_length=1)
    tokenizer_id: str = Field(min_length=1, max_length=200)
    profiles: list[AgentProfile] = Field(min_length=1, max_length=256)
    policy: ContextPolicy = Field(default_factory=ContextPolicy)
    templates: list[CardTemplate] | None = Field(default=None, max_length=4096)
    use_gpu: bool = False
    prompt_prefix: str = Field(default="", max_length=4000)
    prompt_suffix: str = Field(default="", max_length=4000)


def runtime_from_config(config, base_directory):
    # JSON validation admits JSON arrays for immutable tuple fields without
    # relaxing strict integer/boolean and unknown-setting checks.
    settings = RuntimeConfiguration.model_validate_json(canonical_json(config))
    tokenizer_path = Path(settings.tokenizer_path)
    if not tokenizer_path.is_absolute():
        tokenizer_path = Path(base_directory) / tokenizer_path
    if not tokenizer_path.is_file():
        raise ValueError(
            "Configured consumer tokenizer file is unavailable; no download was attempted."
        )
    from memory.cache.cards import CardRouter

    return ContextRuntime(
        profiles=settings.profiles,
        tokens=TokenBudget.from_file(
            tokenizer_path,
            settings.tokenizer_id,
            settings.prompt_prefix,
            settings.prompt_suffix,
        ),
        policy=settings.policy,
        templates=settings.templates,
        ranker=CardRouter(use_gpu=settings.use_gpu),
    )
