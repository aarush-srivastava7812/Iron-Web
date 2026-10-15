"""Provider stalls must terminate before an intake value can be accepted."""

from types import SimpleNamespace
import pytest

from examples.nvidia_memory_agents import NvidiaModel


def test_schema_requests_bound_formatting_and_abort_a_whitespace_stall():
    recorded = {}

    class Stream:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def __iter__(self):
            yield SimpleNamespace(
                usage=None,
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(content="{\n" + " " * 300),
                        finish_reason=None,
                    )
                ],
            )

    def create(**kwargs):
        recorded.update(kwargs)
        return Stream()

    model = NvidiaModel.__new__(NvidiaModel)
    model.model, model.records, model.on_record = "fixture", [], None
    model.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    schema = {"type": "object"}
    with pytest.raises(ValueError, match="stalled"):
        model.json("stall", [{"role": "user", "content": "fixture"}], schema=schema)
    assert recorded["extra_body"]["guided_json"] == schema
    assert recorded["extra_body"]["guided_whitespace_pattern"] == r"[ \n\t]{0,1}"
    assert model.records[0]["error_type"] == "ValueError"
