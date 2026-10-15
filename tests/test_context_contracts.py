"""Small context contracts tested before service/cache integration."""

import pytest

from memory.context.contracts import (
    AgentProfile,
    CardTemplate,
    FieldRule,
    ContextPolicy,
)
from memory.context.compiler import compile_field, render_card


def evidence(value, **extra):
    return dict(
        claim_id="claim-1",
        memory_id="event-1",
        predicate="budget",
        value=value,
        scope={"trip_id": "A"},
        accepted_for_current_use=True,
        valid_from=0,
        valid_until=2**63 - 1,
        kind="rule",
        protected=True,
        sources=[dict(event_id="message-1")],
        **extra,
    )


def test_contracts_reject_unknown_configuration_and_required_profile_fallback():
    with pytest.raises(ValueError):
        FieldRule(predicate="budget", required=True, profile_fallback=True)
    with pytest.raises(ValueError):
        AgentProfile(
            actor_id="planner", version="1", instructions="plan", grants=["book"]
        )
    with pytest.raises(ValueError):
        ContextPolicy(half_tokens=0)


def test_card_uses_current_evidence_and_retains_missing_fields():
    budget = compile_field(
        "budget", {"answer_status": "supported", "evidence": [evidence(60000)]}
    )
    dates = compile_field("dates", {"answer_status": "missing", "evidence": []})
    card = render_card(
        CardTemplate(
            card_id="flight",
            title="Flight preferences",
            task_types=("flight",),
            fields=("budget", "dates"),
        ),
        [budget, dates],
    )
    assert "60000" in card["text"] and "dates: missing" in card["text"]
    assert card["claim_ids"] == ["claim-1"]
    assert card["source_event_ids"] == ["message-1"]


@pytest.mark.parametrize(
    "status", ["missing", "disputed", "unconfirmed", "unresolved_question"]
)
def test_unusable_evidence_is_not_turned_into_a_fact(status):
    field = compile_field(
        "budget", {"answer_status": status, "evidence": [evidence(100000)]}
    )
    assert field["status"] == status and not field["values"]
    assert "100000" not in field["text"]


def test_malformed_supported_evidence_fails_closed():
    row = evidence(100000)
    row["accepted_for_current_use"] = False
    with pytest.raises(ValueError):
        compile_field("budget", {"answer_status": "supported", "evidence": [row]})


def test_supported_values_keep_json_type_identity():
    first, second = evidence(True), evidence(1)
    second["claim_id"] = "claim-2"
    field = compile_field(
        "budget", {"answer_status": "supported", "evidence": [first, second]}
    )
    assert len(field["values"]) == 2


def test_card_guidance_is_labelled_and_hash_changes_with_evidence():
    template = CardTemplate(
        card_id="relaxed",
        title="Relaxed pace",
        task_types=("itinerary",),
        fields=("budget",),
        mood="relaxed",
        guidance="Leave breaks.",
    )
    before = render_card(
        template,
        [
            compile_field(
                "budget", {"answer_status": "supported", "evidence": [evidence(100000)]}
            )
        ],
    )
    after = render_card(
        template,
        [
            compile_field(
                "budget", {"answer_status": "supported", "evidence": [evidence(60000)]}
            )
        ],
    )
    assert "Application guidance" in after["text"] and "claim-1" in after["text"]
    assert before["version"] != after["version"]
