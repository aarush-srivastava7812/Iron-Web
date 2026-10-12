"""
Phase 8: Model Context Protocol (MCP) Server for Iron Web Memory Engine.

Exposes standard JSON-RPC 2.0 tools for AI agents (Forge, OpenCode, Claude, etc.):
- `add_memory`: Ingest facts, dialogues, or observations into dual-store.
- `search_memory`: Retrieve memories via Vector, Graph, or Full Hybrid retrieval.
- `get_memory`: Retrieve memory record by ID.
- `delete_memory`: Remove a memory across Qdrant and Kùzu stores.
- `get_device_telemetry`: Inspect RTX 4050 GPU VRAM usage and CUDA provider status.
- `run_maintenance`: Execute decay, semantic deduplication, and consolidation.
"""
from __future__ import annotations

import sys
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from memory.engine import MemoryEngine

logger = logging.getLogger("iron_web_mcp")


class IronWebMCPServer:
    """Model Context Protocol (MCP) compliant tool provider for MemoryEngine."""

    def __init__(self, engine: Optional[MemoryEngine] = None, use_gpu: bool = True):
        self.engine = engine or MemoryEngine(use_gpu=use_gpu)

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Return MCP tool schemas for agent registration."""
        return [
            {
                "name": "add_memory",
                "description": "Store a new memory in the dual-store long-term memory engine.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Text content of the memory"},
                        "entity_ids": {"type": "array", "items": {"type": "string"}, "description": "Optional linked entities"},
                        "valid_from": {"type": "integer", "description": "Validity start unix timestamp"},
                        "valid_until": {"type": "integer", "description": "Validity expiration unix timestamp"},
                        "importance": {"type": "number", "description": "Memory importance (0.0 to 1.0)"},
                        "metadata": {"type": "object", "description": "Key-value metadata dictionary"}
                    },
                    "required": ["content"]
                }
            },
            {
                "name": "search_memory",
                "description": "Search long-term memory using hybrid vector, graph expansion, or cross-encoder reranking.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query text"},
                        "k": {"type": "integer", "default": 10, "description": "Number of memories to return"},
                        "temporal_mode": {"type": "string", "enum": ["auto", "now", "historical"], "default": "auto"},
                        "query_time": {"type": "integer", "description": "Reference timestamp for point-in-time search"},
                        "retrieval_mode": {
                            "type": "string",
                            "enum": ["hybrid", "vector", "graph", "hybrid_no_rerank", "no_memory"],
                            "default": "hybrid",
                            "description": "Retrieval architecture configuration"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_memory",
                "description": "Retrieve a specific memory record by its stable memory_id.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "memory_id": {"type": "string", "description": "Unique memory ID"}
                    },
                    "required": ["memory_id"]
                }
            },
            {
                "name": "delete_memory",
                "description": "Safely delete a memory record from both vector and graph stores.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "memory_id": {"type": "string", "description": "Unique memory ID to delete"}
                    },
                    "required": ["memory_id"]
                }
            },
            {
                "name": "get_device_telemetry",
                "description": "Get real-time NVIDIA RTX 4050 GPU VRAM usage and CUDA provider status.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "run_maintenance",
                "description": "Execute background memory decay, DBSCAN deduplication, and consolidation.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "decay": {"type": "boolean", "default": True},
                        "deduplicate": {"type": "boolean", "default": True},
                        "consolidate": {"type": "boolean", "default": True}
                    }
                }
            }
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch an MCP tool call to the underlying MemoryEngine."""
        try:
            if name == "add_memory":
                mem_id = self.engine.add(
                    content=arguments["content"],
                    entity_ids=arguments.get("entity_ids"),
                    valid_from=arguments.get("valid_from", 0),
                    valid_until=arguments.get("valid_until", 2**31 - 1),
                    importance=arguments.get("importance", 1.0),
                    metadata=arguments.get("metadata", {})
                )
                return {"success": True, "memory_id": mem_id}

            elif name == "search_memory":
                hits = self.engine.search(
                    query=arguments["query"],
                    k=arguments.get("k", 10),
                    temporal_mode=arguments.get("temporal_mode", "auto"),
                    query_time=arguments.get("query_time"),
                    retrieval_mode=arguments.get("retrieval_mode", "hybrid")
                )
                return {
                    "success": True,
                    "count": len(hits),
                    "results": [
                        {
                            "memory_id": h.memory_id,
                            "content": h.content,
                            "score": h.score,
                            "retrieval_method": h.retrieval_method,
                            "timestamp": h.timestamp,
                            "valid_from": h.valid_from,
                            "valid_until": h.valid_until,
                            "importance": h.importance,
                            "is_superseded": h.is_superseded,
                            "retrieval_trace": h.retrieval_trace
                        }
                        for h in hits
                    ]
                }

            elif name == "get_memory":
                record = self.engine.get(arguments["memory_id"])
                if record is None:
                    return {"success": False, "error": f"Memory {arguments['memory_id']} not found."}
                return {
                    "success": True,
                    "record": {
                        "memory_id": record.memory_id,
                        "content": record.content,
                        "timestamp": record.timestamp,
                        "valid_from": record.valid_from,
                        "valid_until": record.valid_until,
                        "importance": record.importance,
                        "entity_ids": record.entity_ids,
                        "metadata": record.metadata
                    }
                }

            elif name == "delete_memory":
                ok = self.engine.delete(arguments["memory_id"])
                return {"success": ok}

            elif name == "get_device_telemetry":
                status = self.engine.get_device_status()
                return {
                    "success": True,
                    "telemetry": {
                        "execution_mode": status.execution_mode,
                        "cuda_available": status.cuda_available,
                        "active_providers": status.active_providers,
                        "embedder_provider": status.embedder_provider,
                        "reranker_provider": status.reranker_provider,
                        "vram_total_mb": status.vram_total_mb,
                        "vram_used_mb": status.vram_used_mb,
                        "vram_free_mb": status.vram_free_mb,
                        "vram_budget_mb": status.vram_budget_mb,
                        "safety_buffer_mb": status.safety_buffer_mb,
                        "status_notes": status.status_notes
                    }
                }

            elif name == "run_maintenance":
                res = self.engine.run_maintenance(
                    decay=arguments.get("decay", True),
                    deduplicate=arguments.get("deduplicate", True),
                    consolidate=arguments.get("consolidate", True)
                )
                return {"success": True, "maintenance_summary": res}

            else:
                return {"success": False, "error": f"Unknown tool: {name}"}

        except Exception as e:
            logger.error(f"Error calling MCP tool '{name}': {e}", exc_info=True)
            return {"success": False, "error": str(e)}
