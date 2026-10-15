"""Intake must preserve source semantics before authoritative storage."""

# ruff: noqa: F811 -- Imported pytest fixture is resolved by parameter name.

from copy import deepcopy
import pytest

from examples.nvidia_memory_agents import TravelIntake, parse_object
from tests.test_context_service import actor
from tests.test_context_service import contexts as contexts


def test_a_verbatim_quote_cannot_hide_per_person_units_or_negation():
    for text, predicate, value, quote in [
        (
            "My budget is INR 65000 per person.",
            "budget",
            65000,
            "My budget is INR 65000",
        ),
        (
            "I do not want to change my budget to INR 65000.",
            "budget",
            65000,
            "budget to INR 65000",
        ),
        ("I do not want vegetarian food.", "dietary", "vegetarian", "vegetarian food"),
    ]:
        with pytest.raises(ValueError):
            TravelIntake(
                Model([dict(predicate=predicate, value=value, source_quote=quote)])
            )(text, dict(subject="Riya", scope={"trip_id": "goa"}))


class Model:
    def __init__(self, claims):
        self.claims = claims

    def json(self, *args, **kwargs):
        return {"claims": deepcopy(self.claims)}


def extract(text, fields):
    return TravelIntake(
        Model(
            [
                dict(
                    predicate=p,
                    value=v,
                    source_quote=text,
                    action="supersede",
                    reason="change",
                )
                for p, v in fields.items()
            ]
        )
    )(text, dict(subject="Riya", scope={"trip_id": "goa"}))


@pytest.mark.parametrize(
    "text,fields",
    [
        ("Please change my budget to INR 65000.", {"budget": 65000}),
        ("Could you please lower my budget to INR 65000?", {"budget": 65000}),
        (
            "Change my budget to INR 65000 and walking limit to 50 metres.",
            {"budget": 65000, "max_walk_metres": 50},
        ),
        ("Change my dietary requirement to vegan.", {"dietary": "vegan"}),
    ],
)
def test_updates_are_field_specific_and_support_polite_wording(text, fields):
    claims = extract(text, fields)
    assert {c["predicate"] for c in claims} == set(fields)
    assert all(c["action"] == "supersede" for c in claims)


def test_keep_clause_does_not_inherit_another_fields_change():
    claims = extract(
        "Change my budget to INR 65000 and keep walking limit 500 metres.",
        {"budget": 65000, "max_walk_metres": 500},
    )
    assert [c["action"] for c in claims] == ["supersede", "assert"]


def test_quote_wide_requirement_words_do_not_harden_an_unrelated_preference():
    text = "A step-free hotel is mandatory. Prefer a resort when budget permits."
    claims = extract(text, {"accessibility": "step-free", "hotel_preference": "resort"})
    assert [c["kind"] for c in claims] == ["rule", "preference"]
    claims = extract(
        "For this trip I prefer vegetarian food.", {"dietary": "vegetarian"}
    )
    assert claims[0]["kind"] == "preference"


@pytest.mark.parametrize(
    "source",
    [
        "My budget is INR 65000.50. Walking limit is 500 metres. At most one activity per day.",
        "My budget is INR 65000.50 and walking limit is 500 metres and at most one activity per day.",
    ],
)
def test_daily_activity_units_do_not_change_total_budget_semantics(source):
    claims = extract(
        source,
        {"budget": 65000.50, "max_walk_metres": 500, "max_activities_per_day": 1},
    )
    assert claims[0]["value"] == 65000.50


def test_conditional_request_is_not_promoted_to_a_confirmed_rule():
    assert extract("Maybe change my budget to INR 65000.", {"budget": 65000}) == []


@pytest.mark.parametrize("raw", ['{"amount":1e999}', '{"nested":[{"amount":-1e999}]}'])
def test_json_numeric_overflow_is_rejected(raw):
    with pytest.raises(ValueError):
        parse_object(raw)


def test_grounded_coordinated_update_replaces_both_rules_without_a_dispute(contexts):
    service, _ = contexts
    scope = {"trip_id": "summer"}
    source = "Please change my budget to INR 65000 and walking limit to 50 metres."
    service.submit(
        actor(contexts, "user"),
        dict(
            event_id="original",
            subject="Traveller",
            text="Original structured limits",
            confirmed=True,
            scope=scope,
            claims=[
                dict(
                    subject="Traveller", predicate=p, value=v, kind="rule", scope=scope
                )
                for p, v in {"budget": 90000, "max_walk_metres": 500}.items()
            ],
        ),
    )
    while service.process_one():
        pass
    service.interpreter = TravelIntake(
        Model(
            [
                dict(
                    predicate=p,
                    value=v,
                    source_quote=source,
                    action="supersede",
                    reason="update",
                )
                for p, v in {"budget": 65000, "max_walk_metres": 50}.items()
            ]
        )
    )
    service.submit(
        actor(contexts, "user"),
        dict(
            event_id="both",
            subject="Traveller",
            text=source,
            confirmed=True,
            scope=scope,
        ),
    )
    while service.process_one():
        pass
    assert service.receipt(actor(contexts, "user"), "both")["status"] == "ready"
    for predicate, value in {"budget": 65000, "max_walk_metres": 50}.items():
        answer = service.recall(
            actor(contexts),
            query=predicate,
            subject="Traveller",
            predicate=predicate,
            scope=scope,
        )
        assert answer["answer_status"] == "supported"
        assert answer["evidence"][0]["value"] == value
        assert answer["evidence"][0]["protected"]


@pytest.mark.parametrize(
    "predicate,value,source",
    [
        ("budget", 90000, "My total budget is INR 65000."),
        ("budget", 90000, "My budget is INR 65000. The hotel costs INR 90000."),
        ("budget", 65000, "My budget is INR 65000 per person."),
        ("budget", -1, "My budget is INR 65000."),
        ("traveller_count", 1.5, "Plan for two adults."),
        ("traveller_count", -2, "Plan for two adults."),
        ("max_walk_metres", -50, "Walking limit is 50 metres."),
        ("max_activities_per_day", 0.5, "At most one activity per day."),
        ("destination", ["Goa"], "Plan Goa."),
        ("interests", "food", "I like food."),
        ("dates", "2026-12-110 to 2026-12-14", "Dates 2026-12-10 to 2026-12-14."),
        ("dates", "2026-12-14 to 2026-12-10", "Dates 2026-12-14 to 2026-12-10."),
        ("mood", "relaxed", "I want a relaxed pace."),
    ],
)
def test_invalid_or_ungrounded_values_reject_the_whole_extraction(
    predicate, value, source
):
    with pytest.raises(ValueError):
        extract(source, {predicate: value})


@pytest.mark.parametrize(
    "source,fields",
    [
        ("Budget unclear, destination Goa.", {"budget": "", "destination": "Goa"}),
        ("My budget is INR 65000 and walking limit is 50 metres.", {"budget": 65000}),
        (
            "My budget is INR 65000 and I must have a sign-language interpreter.",
            {"budget": 65000},
        ),
    ],
)
def test_incomplete_messages_are_not_partially_accepted(source, fields):
    with pytest.raises(ValueError):
        extract(source, fields)


def test_missing_or_invented_quotes_are_rejected():
    for quote in (None, "My budget is INR 90000."):
        with pytest.raises(ValueError):
            TravelIntake(
                Model([dict(predicate="budget", value=90000, source_quote=quote)])
            )("My budget is INR 65000.", dict(subject="Riya", scope={"trip_id": "goa"}))


@pytest.mark.parametrize(
    "raw", ['{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}', '{"x":1,"x":2}']
)
def test_invalid_json_numeric_constants_and_duplicate_fields_are_rejected(raw):
    with pytest.raises(ValueError):
        parse_object(raw)


def test_wrong_extraction_is_preserved_as_failed_receipt_without_semantic_writes(
    contexts,
):
    service, _ = contexts
    service.interpreter = TravelIntake(
        Model(
            [
                dict(
                    predicate="budget",
                    value=90000,
                    action="assert",
                    reason="",
                    source_quote="My budget is INR 65000.",
                )
            ]
        )
    )
    service.submit(
        actor(contexts, "user"),
        dict(
            event_id="misread",
            subject="Traveller",
            text="My budget is INR 65000.",
            confirmed=True,
            scope={"trip_id": "summer"},
        ),
    )
    while service.process_one():
        pass
    assert service.receipt(actor(contexts, "user"), "misread")["status"] == "failed"
    assert service.engine("A").vector_store.count() == 0
    assert (
        service.engine("A")
        .graph_store.execute("MATCH(c:MemoryClaim) RETURN count(c)")
        .rows[0][0]
        == 0
    )
    assert (
        service.history(actor(contexts, "user"))["events"][0]["text"]
        == "My budget is INR 65000."
    )
