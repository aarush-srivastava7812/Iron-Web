"""Bounded cache behavior and real token accounting, checked independently."""

import pytest

from memory.cache.ram import PayloadCache
from memory.context.tokens import TokenBudget, ContextCapacity


def test_lru_budget_expiration_and_returned_values_are_isolated():
    cache = PayloadCache(max_bytes=200, max_entries=2)
    cache.put("A", {"text": "first"}, expires=10)
    cache.put("B", {"text": "second"}, expires=10)
    result = cache.get("A", now=1)
    result["text"] = "mutated"
    cache.put("C", {"text": "third"}, expires=10)
    assert cache.get("B", now=1) is None
    assert cache.get("A", now=1)["text"] == "first"
    assert cache.get("A", now=10) is None
    assert cache.get("C", now=10) is None and cache.bytes == 0
    assert not cache.put("large", {"text": "x" * 300}, expires=20)
    assert cache.bytes == 0


def test_explicit_invalidation_discards_private_payloads():
    cache = PayloadCache(max_bytes=500, max_entries=4)
    cache.put(("A", "trip"), {"secret": "A"}, expires=10)
    cache.put(("B", "trip"), {"secret": "B"}, expires=10)
    cache.invalidate(lambda key: key[0] == "A")
    assert cache.get(("A", "trip"), 1) is None
    assert cache.get(("B", "trip"), 1)["secret"] == "B"


def test_equal_halves_and_full_prompt_use_the_actual_tokenizer():
    from tokenizers import Tokenizer, models, pre_tokenizers

    tokenizer = Tokenizer(
        models.WordLevel({"[UNK]": 0, "one": 1, "two": 2}, unk_token="[UNK]")
    )
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    budget = TokenBudget(tokenizer, "declared-test-tokenizer")
    assert budget.count("one two one") == 3
    assert budget.require("one two", 2, "agent") == 2
    with pytest.raises(ContextCapacity):
        budget.require("one two one", 2, "traveller")
    with pytest.raises(ContextCapacity):
        budget.prompt("one two one", context_limit=4, reserved_output=2)
