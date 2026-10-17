"""Agent service settings. Loaded from agents/.env (NVIDIA_API_KEY is manual)."""
from __future__ import annotations

import os
from pathlib import Path

_AGENTS_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> dict[str, str]:
    loaded: dict[str, str] = {}
    if not path.is_file():
        return loaded
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        loaded.setdefault(key.strip(), value.strip())
    return loaded


_file_values = _load_dotenv(_AGENTS_DIR / ".env")
_root_values = _load_dotenv(_AGENTS_DIR.parent / ".env")


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key) or _file_values.get(key) or default


class AgentSettings:
    """Process-wide settings; environment variables win over agents/.env."""

    nvidia_api_key: str = _get("NVIDIA_API_KEY", _root_values.get("NVIDIA_API_KEY", "")).strip("\"'")
    nim_base_url: str = _get("NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")
    nim_model: str = _get("NIM_MODEL", "openai/gpt-oss-20b")
    nim_agent_model: str = _get("NIM_AGENT_MODEL", "openai/gpt-oss-20b")
    nim_agent_protocol: str = _get("NIM_AGENT_PROTOCOL", "json")
    nim_timeout_s: float = float(_get("NIM_TIMEOUT_S", "45"))
    # auto uses NIM when a credential exists; offline is an explicitly labelled demo.
    agent_mode: str = _get("VOYARA_AGENT_MODE", "auto")
    agent_max_turns: int = int(_get("VOYARA_AGENT_MAX_TURNS", "5"))

    travel_api_url: str = _get("TRAVEL_API_URL", "http://127.0.0.1:8000").rstrip("/")
    travel_api_token: str = _get("TRAVEL_API_TOKEN")

    agents_host: str = _get("AGENTS_HOST", "127.0.0.1")
    agents_port: int = int(_get("AGENTS_PORT", "8100"))
    log_level: str = _get("AGENTS_LOG_LEVEL", "INFO")

    # Retrieval / write policy limits
    retrieval_default_k: int = int(_get("MEMORY_RETRIEVAL_K", "8"))
    retrieval_overfetch: int = int(_get("MEMORY_OVERFETCH", "4"))
    max_context_chars: int = int(_get("MEMORY_CONTEXT_CHARS", "1600"))
    min_write_importance: float = float(_get("MEMORY_MIN_IMPORTANCE", "0.45"))

    max_inference_concurrency: int = int(_get("MAX_INFERENCE_CONCURRENCY", "2"))
    max_revision_loops: int = int(_get("MAX_REVISION_LOOPS", "2"))

    @classmethod
    def has_llm(cls) -> bool:
        return bool(cls.nvidia_api_key)


settings = AgentSettings()
