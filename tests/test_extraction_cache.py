"""Cache-contract fixtures; no hosted inference is invoked."""

import hashlib
import json
import pytest
from memory.ingestion.cached_nim_extractor import CachedNIMExtractor


class ProtocolDelegate:
    is_mock = (
        False  # Exercises the wrapper's non-mock protocol contract, not model quality.
    )
    model = "fixture/model"
    base_url = "https://integrate.api.nvidia.com/v1"
    calls = 0

    def extract_entities_and_relations(self, text, context=None):
        self.calls += 1
        return dict(
            entities=[dict(id="ent_1", name="Python", type="Technology")],
            relations=[],
            temporal=dict(valid_from=0, valid_until=2**63 - 1),
            importance=0.5,
            is_mock=False,
            extractor_name="fixture_protocol_delegate",
        )


def test_cache_hits_do_not_call_delegate(tmp_path):
    delegate = ProtocolDelegate()
    cache = CachedNIMExtractor(str(tmp_path), delegate)
    first = cache.extract_entities_and_relations("text")
    second = cache.extract_entities_and_relations("text")
    assert first == second and delegate.calls == 1
    assert first["entities"][0]["id"] != "ent_1"


def test_legacy_response_migrates_without_reissue(tmp_path):
    delegate = ProtocolDelegate()
    raw = delegate.extract_entities_and_relations("text")
    key = hashlib.sha256(f"{delegate.model}\x00text\x00".encode()).hexdigest()
    legacy = tmp_path / (delegate.model.replace("/", "_") + "_" + key + ".json")
    legacy.write_text(json.dumps(raw))
    before = legacy.read_bytes()
    delegate.calls = 0
    cache = CachedNIMExtractor(str(tmp_path), delegate)
    result = cache.extract_entities_and_relations("text")
    assert delegate.calls == 0 and result["entities"]
    assert legacy.read_bytes() == before


def test_corrupt_entry_never_silently_contacts_delegate(tmp_path):
    delegate = ProtocolDelegate()
    cache = CachedNIMExtractor(str(tmp_path), delegate)
    cache._cache_path("text", None).write_text("invalid JSON")
    with pytest.raises(ValueError):
        cache.extract_entities_and_relations("text")
    assert delegate.calls == 0


def test_mock_delegate_cannot_be_marked_as_real(tmp_path):
    from tests.fixtures.extractor import MockNIMExtractor

    with pytest.raises(ValueError, match="mock"):
        CachedNIMExtractor(str(tmp_path), MockNIMExtractor())
