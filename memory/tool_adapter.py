"""In-process Python tool adapter. This module does not provide an MCP transport."""

from memory.engine import MemoryEngine
from memory.models import EngineStorageError


class MemoryToolAdapter:
    def __init__(self, engine=None, agent_id="agent"):
        self.engine = engine if engine is not None else MemoryEngine()
        if not isinstance(agent_id, str) or not agent_id.strip():
            raise ValueError("Agent ID must be nonempty.")
        self.agent_id = agent_id

    def get_tool_definitions(self):
        definitions = [
            (
                "add_memory",
                "Save a memory.",
                {
                    "content": {"type": "string"},
                    "metadata": {"type": "object"},
                    "claims": {"type": "array", "items": {"type": "object"}},
                    "source_info": {"type": "object"},
                },
                ["content"],
            ),
            (
                "search_memory",
                "Search saved memories.",
                {
                    "query": {"type": "string"},
                    "k": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                ["query"],
            ),
            (
                "get_memory",
                "Read a saved memory by ID.",
                {"memory_id": {"type": "string"}},
                ["memory_id"],
            ),
            (
                "delete_memory",
                "Delete a saved memory by ID.",
                {"memory_id": {"type": "string"}},
                ["memory_id"],
            ),
            (
                "get_device_telemetry",
                "Read observed execution providers and device memory.",
                {},
                [],
            ),
            (
                "run_maintenance",
                "Run the listed maintenance tasks; an empty list runs none.",
                {
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["decay", "dedup", "consolidate"],
                        },
                    },
                    "dry_run": {"type": "boolean", "default": True},
                },
                [],
            ),
        ]
        definitions.extend(
            [
                (
                    "recall_memory",
                    "Retrieve a declared field with source evidence and an explicit missing/disputed status.",
                    {
                        "query": {"type": "string"},
                        "subject": {"type": "string"},
                        "predicate": {"type": "string"},
                        "scope": {"type": "object"},
                    },
                    ["query", "subject"],
                ),
                (
                    "recall_path",
                    "Follow up to four explicit graph field relationships, preserving evidence at each step.",
                    {
                        "query": {"type": "string"},
                        "subject": {"type": "string"},
                        "predicates": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": 4,
                        },
                    },
                    ["query", "subject", "predicates"],
                ),
                (
                    "inspect_claim",
                    "Read a claim's current score, state and score explanation.",
                    {"claim_id": {"type": "string"}},
                    ["claim_id"],
                ),
                (
                    "record_work",
                    "Record exact claim versions used by a decision or task.",
                    {
                        "work_id": {"type": "string"},
                        "claim_ids": {"type": "array", "items": {"type": "string"}},
                        "depends_on": {"type": "array", "items": {"type": "string"}},
                        "description": {"type": "string"},
                    },
                    ["work_id", "claim_ids"],
                ),
                (
                    "handoff_memory",
                    "Read used and current memory versions plus work requiring review.",
                    {"work_ids": {"type": "array", "items": {"type": "string"}}},
                    ["work_ids"],
                ),
                (
                    "complete_work",
                    "Mark owned work completed only after current evidence is checked.",
                    {"work_id": {"type": "string"}},
                    ["work_id"],
                ),
            ]
        )
        return [
            dict(
                name=name,
                description=description,
                inputSchema=dict(
                    type="object", properties=properties, required=required
                ),
            )
            for name, description, properties, required in definitions
        ]

    def call_tool(self, name, arguments):
        methods = {
            "add_memory": self.engine.add,
            "search_memory": self.engine.search,
            "get_memory": self.engine.get,
            "delete_memory": self.engine.delete,
            "get_device_telemetry": self.engine.get_device_status,
            "run_maintenance": self.engine.run_maintenance,
            "recall_memory": self.engine.recall,
            "recall_path": self.engine.recall_path,
            "inspect_claim": self.engine.inspect_claim,
            "record_work": self.engine.record_work,
            "handoff_memory": self.engine.handoff,
            "complete_work": self.engine.complete_work,
        }
        if name not in methods or not isinstance(arguments, dict):
            return dict(success=False, error="Unknown tool or invalid argument object.")
        arguments = dict(arguments)
        if name == "delete_memory" and arguments.get("user_confirmed"):
            return dict(
                success=False,
                error="An agent cannot confirm deletion of retained user evidence.",
            )
        if name == "add_memory" and (
            "claims" in arguments or "source_info" in arguments
        ):
            source = arguments.get("source_info") or {}
            if (
                not isinstance(source, dict)
                or source.get("user_confirmed")
                or source.get("origin") == "user"
            ):
                return dict(
                    success=False,
                    error="An agent cannot impersonate a confirmed user source.",
                )
            try:
                quality = min(float(source.get("quality", 0.5)), 0.5)
            except (ValueError, TypeError):
                return dict(
                    success=False, error="Agent source quality must be numeric."
                )
            source = dict(
                source,
                origin="agent",
                actor_id=self.agent_id,
                user_confirmed=False,
                evidence_group="agent_assertions",
                quality=quality,
            )
            arguments["source_info"] = source
        if name in {"record_work", "complete_work"}:
            arguments["agent_id"] = self.agent_id
        if name == "run_maintenance":
            arguments.setdefault("dry_run", True)
        try:
            result = methods[name](**arguments)
            if hasattr(result, "model_dump"):
                result = result.model_dump()
            elif isinstance(result, list):
                result = [
                    value.model_dump() if hasattr(value, "model_dump") else value
                    for value in result
                ]
            return dict(success=True, result=result)
        except EngineStorageError as error:
            return dict(success=False, error=str(error), rolled_back=error.rolled_back)
        except (ValueError, TypeError, RuntimeError) as error:
            return dict(success=False, error=str(error))
