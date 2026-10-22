"""TinyFish chat intake is local, prompt, and separate from confirmed memory."""

# ruff: noqa: F811 -- Imported pytest fixture is resolved by parameter name.
from agents.config import settings
from agents.tinyfish import (
    ResearchItem,
    RESEARCH_ROLES,
    TinyFishClient,
    TinyFishSearchClient,
)
from tests.test_application_integration import connected_app, trip, user  # noqa: F401


def configure(monkeypatch):
    from app import journey

    monkeypatch.setattr(settings, "agent_mode", "tinyfish")

    def forbidden(*args, **kwargs):
        raise AssertionError("Draft intake must not call a hosted provider")

    monkeypatch.setattr(journey, "get_nim_client", forbidden)
    monkeypatch.setattr(TinyFishClient, "research", forbidden)
    monkeypatch.setattr(TinyFishSearchClient, "research_city", forbidden)


def send(client, headers, path, text):
    response = client.post(
        path + "/chat", headers=headers, json={"content": text, "page": "plan"}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_exact_agra_message_returns_questions_without_hosted_inference(
    connected_app, monkeypatch
):
    configure(monkeypatch)
    client, _ = connected_app
    headers = user(client, "agra_chat")
    path = trip(client, headers)
    reply = send(
        client, headers, path, "i want to go for a trip to agra can you plan it"
    )
    assert reply["status"] == "ok"
    assert reply["workspace"]["draft"]["destination"] == "Agra"
    assert "departure date" in reply["reply"] and reply["awaiting"] == "start_date"
    assert not reply["workspace"]["confirmed"] and not reply["workspace"]["plan_ready"]
    assert len(reply["workspace"]["missing_fields"]) == 4
    assert reply["cards"] == []
    requirements = client.get(path + "/requirements", headers=headers).json()
    assert not any(
        f["predicate"] == "destination" and f["status"] == "supported"
        for f in requirements["fields"]
    )
    details = send(
        client,
        headers,
        path,
        "2026-12-01 for three days, two adults, INR 30,000 total, relaxed, vegetarian, culture",
    )
    draft = details["workspace"]["draft"]
    assert draft["end_date"] == "2026-12-03" and draft["traveller_count"] == 2
    assert draft["budget"] == 30000 and draft["destination"] == "Agra"
    assert not details["workspace"]["missing_fields"]
    assert "confirm" in details["reply"].lower()
    other = user(client, "agra_intruder")
    assert client.get(path + "/workspace", headers=other).status_code == 404


def test_local_intake_preserves_draft_on_ambiguous_or_invalid_updates(
    connected_app, monkeypatch
):
    configure(monkeypatch)
    client, _ = connected_app
    headers = user(client, "agra_validation")
    path = trip(client, headers)
    initial = send(client, headers, path, "Plan a trip to Agra")["workspace"]
    for message in ("Maybe Jaipur instead of Agra", "INR 10000 per person"):
        result = send(client, headers, path, message)
        assert result["status"] == "needs_clarification"
        assert result["workspace"]["revision"] == initial["revision"]
        assert result["workspace"]["draft"] == initial["draft"]
    invalid_date = send(client, headers, path, "Start 2026-02-30 for three days")
    assert invalid_date["status"] == "needs_clarification"
    assert invalid_date["workspace"]["draft"]["destination"] == "Agra"
    assert not invalid_date["workspace"]["draft"].get("start_date")
    # Keep the independently valid duration while asking to correct the date.
    assert invalid_date["workspace"]["draft"]["duration_days"] == 3
    protected = send(
        client, headers, path, "I need wheelchair access and must avoid stairs"
    )
    assert protected["workspace"]["draft"]["hard_requirements"]
    assert "need verification" in protected["reply"]


def test_agra_confirmation_keeps_destination_without_substituting_catalog_city(
    connected_app, monkeypatch
):
    configure(monkeypatch)
    captured = []

    def research(self, city, purpose):
        captured.append((city, purpose))
        basis = (
            "per_room_night"
            if purpose == RESEARCH_ROLES["stay_agent"][1]
            else "per_guest_meal"
            if purpose == RESEARCH_ROLES["food_guide_agent"][1]
            else "per_guest_visit"
        )
        return "test-agra-run", [
            ResearchItem.model_validate(
                {
                    "name": "Agra web finding",
                    "source_url": "https://example.com/agra",
                    "location": city,
                    "description": "Test public research",
                    "price_inr": 1000,
                    "price_basis": basis,
                    "currency": "INR",
                    "dietary": "vegetarian",
                    "price_note": "Indicative only",
                    "candidate_type": "venue",
                }
            )
        ]

    monkeypatch.setattr(TinyFishSearchClient, "research_city", research)
    client, _ = connected_app
    headers = user(client, "agra_confirmation")
    path = trip(client, headers)
    work = send(
        client,
        headers,
        path,
        "Agra, 2026-12-01 for three days, two adults, INR 30000 total",
    )["workspace"]
    response = client.post(
        path + "/confirm",
        headers=headers,
        json={"expected_revision": work["revision"], "mode": "ai"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["orchestration"]["status"] == "ok", data
    assert data["orchestration"]["trip_brief"]["destination"] == "Agra"
    assert data["orchestration"]["itinerary"]["title"] == "3-day trip to Agra"
    assert len(captured) == 4
    assert all(city == "Agra" and "30000" not in purpose for city, purpose in captured)
