"""Memory Gateway contract tests against the real MemoryEngine."""
from __future__ import annotations

import time

from agents.schemas import MemoryWriteProposal


def _proposal(user_id="user-a", agent_id="explore_agent", content=None,
              kind="preference", importance=0.8, session_id="s1", **kwargs):
    return MemoryWriteProposal(
        user_id=user_id, session_id=session_id, agent_id=agent_id,
        content=content or "Prefers quiet beach destinations over nightlife",
        kind=kind, importance=importance, **kwargs,
    )


def test_write_then_retrieve_roundtrip(gateway):
    result = gateway.propose_write(_proposal())
    assert result.status == "stored"
    assert result.memory_id

    context = gateway.retrieve(
        query="quiet beach destinations preference",
        user_id="user-a", agent_id="explore_agent", use_cache=False,
    )
    assert context.items, "stored memory should be retrievable"
    assert any("quiet beach" in item.content for item in context.items)
    top = next(item for item in context.items if "quiet beach" in item.content)
    assert top.provenance.agent_id == "explore_agent"
    assert top.provenance.memory_id == result.memory_id


def test_user_isolation(gateway):
    gateway.propose_write(_proposal(user_id="user-a",
                                    content="User A loves mountain monasteries"))
    gateway.propose_write(_proposal(user_id="user-b",
                                    content="User B only travels by overnight train"))
    context_b = gateway.retrieve(query="mountain monasteries", user_id="user-b",
                                 agent_id="explore_agent", use_cache=False,
                                 limit=20)
    assert all("User A" not in item.content for item in context_b.items)


def test_duplicate_writes_are_safe(gateway):
    first = gateway.propose_write(_proposal(content="Always books aisle seats on flights"))
    second = gateway.propose_write(_proposal(content="Always books aisle seats on flights"))
    assert first.status == "stored"
    assert second.status == "duplicate"
    assert second.memory_id == first.memory_id


def test_policy_rejects_noise_and_secrets(gateway):
    short = gateway.propose_write(_proposal(content="ok thanks"))
    assert short.status == "rejected" and "noise" in short.reason

    secret = gateway.propose_write(_proposal(content="My api key is abc123def456"))
    assert secret.status == "rejected"

    low = gateway.propose_write(_proposal(importance=0.1,
                                          content="Maybe likes window seats sometimes"))
    assert low.status == "rejected" and "importance" in low.reason


def test_temporal_retrieval_expires_memories(gateway):
    future = int(time.time()) + 60
    past = int(time.time()) - 60
    proposal = _proposal(user_id="user-temporal",
                         content="Currently prefers budget hostels for short trips")
    stored = gateway.propose_write(proposal)
    assert stored.status == "stored"
    # Re-write the same record with a validity window that already ended, using
    # the engine update path the gateway leaves intact.
    gateway.engine.update(stored.memory_id, valid_from=past - 10, valid_until=past)

    now_context = gateway.retrieve(query="budget hostels short trips",
                                   user_id="user-temporal", agent_id="stay_agent",
                                   temporal_mode="now", use_cache=False, limit=20)
    assert all("budget hostels" not in i.content.lower() or i.provenance.valid_until
               for i in now_context.items)
    assert not any(item.provenance.memory_id == stored.memory_id
                   for item in now_context.items)

    historical = gateway.retrieve(query="budget hostels short trips",
                                  user_id="user-temporal", agent_id="stay_agent",
                                  temporal_mode="historical", use_cache=False, limit=20)
    assert any(item.provenance.memory_id == stored.memory_id for item in historical.items)


def test_retrieval_cache_avoids_repeat_queries(gateway):
    gateway.propose_write(_proposal(user_id="user-cache",
                                    content="Prefers early morning departures"))
    calls = {"n": 0}
    original = gateway.engine.search

    def counting(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    gateway.engine.search = counting  # type: ignore[method-assign]
    try:
        gateway.retrieve(query="early departures", user_id="user-cache",
                         agent_id="stay_agent", use_cache=True)
        gateway.retrieve(query="early departures", user_id="user-cache",
                         agent_id="stay_agent", use_cache=True)
        assert calls["n"] == 1, "second identical retrieval must hit the cache"
    finally:
        gateway.engine.search = original  # type: ignore[method-assign]
