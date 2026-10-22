"""The reported relaxed/solo/50k conversation and bounded response-agent policy."""
# ruff: noqa: F811
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stitch_ai_travel_booking_platform/backend"))
from agents.conversation_agent import ConversationAgent  # noqa: E402
from agents.destination_advisor import DestinationAdvisor  # noqa: E402
from tests.test_application_integration import connected_app, trip, user  # noqa: E402,F401
from tests.test_tinyfish_chat import configure, send  # noqa: E402

QUERY = "I want to go ot the place where I can feel relax, for a solo trip with 50k"


@pytest.fixture(autouse=True)
def local_dialogue(monkeypatch):
    from agents.config import settings
    monkeypatch.setattr(settings, "dialogue_mode", "local")


def test_reported_conversation_recommends_proactively_and_remembers_context(connected_app, monkeypatch):
    configure(monkeypatch)
    client, _ = connected_app
    headers = user(client, "natural_chat")
    path = trip(client, headers)
    first = send(client, headers, path, QUERY)
    draft = first["workspace"]["draft"]
    assert draft["budget"] == 50000 and draft["traveller_count"] == 1
    assert draft["pace"] == "relaxed"
    assert "for a solo trip with 50k" not in draft["soft_preferences"]
    assert len(first["cards"]) == 3
    assert "Where would you like to go?" not in first["reply"]
    assert "Travelers:" not in first["reply"] and "Preferences:" not in first["reply"]
    assert "₹50,000" in first["reply"] and "solo" in first["reply"]
    revision = first["workspace"]["revision"]
    second = send(client, headers, path, "suggest some places")
    names = [item["name"] for item in second["cards"]]
    assert "Jaipur" not in names
    assert names == [item["name"] for item in first["cards"]]
    assert second["workspace"]["revision"] == revision
    why = send(client, headers, path, "why " + names[0])
    assert why["workspace"]["revision"] == revision
    assert "stood out" in why["reply"] and "₹50,000" in why["reply"]
    # Read-only questions may change suggested buttons, not the trip's facts.
    again = send(client, headers, path, "suggest some places")
    chosen = send(client, headers, path, "the second one")
    assert chosen["workspace"]["draft"]["destination"] == again["cards"][1]["name"]
    assert chosen["awaiting"] == "origin"
    located = send(client, headers, path, "Mumbai")
    assert located["awaiting"] == "start_date"
    assert located["workspace"]["draft"]["origin"] == "Mumbai"


def test_discovery_with_facts_and_alternatives_preserves_budget(connected_app, monkeypatch):
    configure(monkeypatch)
    client, _ = connected_app
    headers = user(client, "natural_alternatives")
    path = trip(client, headers)
    first = send(client, headers, path, "suggest a relaxing solo trip with 50k")
    assert first["workspace"]["draft"]["budget"] == 50000
    assert first["workspace"]["draft"]["traveller_count"] == 1
    other = send(client, headers, path, "suggest other places")
    assert not ({c["name"] for c in first["cards"]} & {c["name"] for c in other["cards"]})
    assert other["workspace"]["draft"]["budget"] == 50000


def test_destination_advice_uses_tags_and_does_not_claim_a_verified_total():
    catalog = [dict(id=1, name="City", tags=["culture"], description="Busy markets.", price_inr=20000),
               dict(id=2, name="Hill", tags=["relax", "nature"], description="Quiet, unhurried mornings.", price_inr=19000)]
    advisor = DestinationAdvisor()
    ranked = advisor.suggest(catalog, {"pace": "relaxed", "budget": 50000}, "suggest places")
    assert ranked[0]["name"] == "Hill"
    assert "sample guides" in advisor.reply(ranked, {"budget": 50000})


class Model:
    def __init__(self, answer):
        self.answer, self.calls = answer, []
    def chat_json(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return self.answer


def test_one_model_call_has_history_and_cannot_write_facts(monkeypatch):
    from agents.config import settings
    monkeypatch.setattr(settings, "dialogue_mode", "auto")
    model = Model({"reply": "For your quiet solo break, I'd lean toward the hills. Which option catches your eye?"})
    answer = {"status": "ok", "reply": "Grounded recommendation", "cards": [], "awaiting": "destination"}
    draft = {"budget": 50000, "pace": "relaxed"}
    result = ConversationAgent().respond("suggest some places", draft, answer,
        history=[{"role": "user", "content": "I want to relax on a solo trip"}], client=model)
    assert result["conversation"]["mode"] == "nvidia" and len(model.calls) == 1
    context = json.loads(model.calls[0][0][1]["content"])
    assert context["history"] and context["draft"] == draft
    assert model.calls[0][1]["retry_truncated"] is False
    assert model.calls[0][1]["queue_timeout_s"] < 1
    assert "updates" not in result and draft["budget"] == 50000


def test_provider_cooldown_avoids_repeated_slow_calls(monkeypatch):
    from agents.config import settings
    monkeypatch.setattr(settings, "dialogue_mode", "auto")
    model = Model(None)
    agent = ConversationAgent()
    answer = {"status": "ok", "reply": "A quiet place to unwind.", "cards": []}
    for _ in range(3):
        result = agent.respond("suggest places", {}, answer, client=model)
        assert result["reply"] == answer["reply"]
        assert result["conversation"]["mode"] == "local"
    assert len(model.calls) == 1


def test_model_cannot_add_a_fictitious_price(monkeypatch):
    from agents.config import settings
    monkeypatch.setattr(settings, "dialogue_mode", "auto")
    answer = {"status": "ok", "reply": "We'll need dates for a total.", "cards": []}
    result = ConversationAgent().respond("what will it cost", {"budget": 50000}, answer,
        client=Model({"reply": "Your whole trip is guaranteed to cost INR 12345."}))
    assert result["reply"] == answer["reply"]


def test_model_cannot_turn_a_catalog_guide_into_verified_affordability(monkeypatch):
    from agents.config import settings
    monkeypatch.setattr(settings, "dialogue_mode", "auto")
    answer = {"status": "ok", "reply": "Full costs depend on your dates and starting city.", "cards": []}
    result = ConversationAgent().respond("suggest places", {"budget": 50000}, answer,
        client=Model({"reply": "All these trips are well within your budget, leaving room for flights."}))
    assert result["reply"] == answer["reply"]
    assert result["conversation"]["reason"] == "unverified_affordability"
