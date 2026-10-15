"""Configuration must declare the actual local consumer tokenizer; never download."""

import pytest
from tokenizers import Tokenizer, models

from memory.context.runtime import runtime_from_config


def test_configuration_builds_a_recoverable_profile_without_loading_models(tmp_path):
    Tokenizer(models.WordLevel({"[UNK]": 0}, unk_token="[UNK]")).save(
        str(tmp_path / "tokenizer.json")
    )
    config = dict(
        tokenizer_path="tokenizer.json",
        tokenizer_id="explicit-consumer",
        profiles=[
            dict(actor_id="planner", version="1", instructions="Plan practical trips.")
        ],
        use_gpu=False,
    )
    configured = runtime_from_config(config, tmp_path)
    assert configured.profiles["planner"].version == "1"
    assert configured.tokens.identity.startswith("explicit-consumer:")
    assert (
        configured.ranker.index.session is None
        and configured.ranker.index.matrix is None
    )
    assert configured.cache.bytes == 0
    assert runtime_from_config(config, tmp_path).fingerprint == configured.fingerprint


def test_configuration_rejects_unknown_fields_and_missing_tokenizer(tmp_path):
    with pytest.raises(ValueError):
        runtime_from_config(
            dict(
                tokenizer_path="missing",
                tokenizer_id="consumer",
                profiles=[],
                mystery=True,
            ),
            tmp_path,
        )
    with pytest.raises((ValueError, OSError)):
        runtime_from_config(
            dict(tokenizer_path="missing", tokenizer_id="consumer", profiles=[]),
            tmp_path,
        )
