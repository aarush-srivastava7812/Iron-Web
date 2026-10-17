from agents.agentic import ToolAgent
from agents.schemas import AgentResult


def action(name, arguments):
    import json
    return {"tool_calls": [{"id": name, "function": {"name": name, "arguments": json.dumps(arguments)}}]}


def test_invalid_tool_response_retries_without_repeating_successful_operation():
    class Client:
        calls = 0

        def tool_turn(self, messages, tools, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return action("inspect_brief", {})
            if self.calls == 2:
                raise RuntimeError("NVIDIA returned no valid tool action")
            return action("finish", {"summary": "Confirmed the observed brief."})

    invocations = []

    def inspect():
        invocations.append(True)
        return AgentResult(agent_id="trip_consultant", status="ok", summary="Confirmed brief")

    client = Client()
    result = ToolAgent("trip_consultant", client=client).run(inspect)
    assert result.status == "ok" and result.execution.completed
    assert len(invocations) == 1 and client.calls == 3
    assert any("Invalid provider tool action" in line for line in result.execution.observations)


def test_invalid_tool_protocol_cannot_bypass_observed_tool_requirement():
    class Client:
        calls = 0

        def tool_turn(self, *args, **kwargs):
            self.calls += 1
            raise RuntimeError("NVIDIA returned no valid tool action")

    client = Client()
    result = ToolAgent("trip_consultant", client=client).run(lambda: None)
    assert result.status == "failed" and not result.execution.completed
    assert 2 <= client.calls <= 8
