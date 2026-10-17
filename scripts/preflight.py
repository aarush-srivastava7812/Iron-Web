"""Read-only local startup checks; never print configuration secret values."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def check(mode="running", offline=False):
    rows = []
    def record(name, ok, detail):
        rows.append(dict(check=name, ok=bool(ok), detail=detail))
    record("Python", sys.version_info >= (3, 12), "Python 3.12+ required")
    for module in ["fastapi", "uvicorn", "httpx", "sqlalchemy", "dotenv", "falkordb", "qdrant_client", "langgraph", "reportlab", "numpy", "yaml", "fastembed", "onnxruntime", "argon2", "jwt"]:
        record("dependency:" + module, importlib.util.find_spec(module) is not None, "Install requirements/application.txt and dashboard/backend/requirements.txt")
    node = shutil.which("node")
    version = (0, 0)
    if node:
        try:
            version = tuple(map(int, subprocess.check_output([node, "--version"], text=True).strip().lstrip("v").split(".")[:2]))
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    record("Node", version >= (22, 12), "Node >=22.12 required by dashboard")
    for frontend in [ROOT / "dashboard/frontend", ROOT / "stitch_ai_travel_booking_platform/frontend"]:
        record(str(frontend.relative_to(ROOT)), (frontend / "node_modules/vite/bin/vite.js").is_file(), "Run npm ci in this frontend")
    record("website build", (ROOT / "stitch_ai_travel_booking_platform/frontend/dist/index.html").is_file(), "Run npm --prefix stitch_ai_travel_booking_platform/frontend run build")
    for port in [8000, 5174, 8200, 6379]:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                listening = True
        except OSError:
            listening = False
        required = port == 6379 or mode == "running"
        record("port:" + str(port), listening == required,
               "must be listening" if required else "must be free before starting this service")
    # Authentication/TLS environment overrides are honored without exposing them.
    if importlib.util.find_spec("falkordb"):
        try:
            sys.path.insert(0, str(ROOT))
            from memory.config import EngineSettings
            from falkordb import FalkorDB
            import yaml
            config = EngineSettings.model_validate(yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))).falkordb
            client = FalkorDB(host=os.getenv("FALKORDB_HOST", config.host),
                             port=int(os.getenv("FALKORDB_PORT", config.port)),
                             username=os.getenv("FALKORDB_USERNAME") or None,
                             password=os.getenv("FALKORDB_PASSWORD") or None,
                             ssl=os.getenv("FALKORDB_TLS", str(config.tls)).lower() in {"true", "1"}, socket_timeout=3)
            record("FalkorDB PING", client.connection.ping(), "Read-only authenticated connection")
            modules = client.connection.module_list()
            record("FalkorDB graph module", any(m.get("name") in {b"graph", "graph"} for m in modules), "Endpoint must be FalkorDB, not plain Redis")
            client.close()
        except Exception as error:
            record("FalkorDB PING", False, type(error).__name__ + ": check service/connection configuration")
    if not offline:
        if importlib.util.find_spec("dotenv"):
            from dotenv import load_dotenv
            load_dotenv(ROOT / "stitch_ai_travel_booking_platform/backend/.env")
        sys.path.insert(0, str(ROOT))
        from agents.config import settings
        record("hosted credential configured", bool(settings.nvidia_api_key), "NVIDIA_API_KEY must be supplied privately; this does not verify validity")
    grant = ROOT / ".scratch/ironweb-live/.env"
    valid_grant = False
    if grant.is_file() and importlib.util.find_spec("dotenv"):
        from dotenv import dotenv_values
        values = dotenv_values(grant)
        valid_grant = all(len(values.get(k) or "") >= 32 for k in ["LOCAL_DASHBOARD_GRANT", "LOCAL_SESSION_SECRET"])
    record("local publication/session setup", valid_grant or (mode == "start" and not grant.exists()), "Launcher creates private grants; existing files must contain strong publication and session secrets")
    for variable in ["DASHBOARD_SOURCE_TOKEN", "DASHBOARD_VIEWER_TOKEN"]:
        if os.getenv(variable):
            record(variable + " strength", len(os.environ[variable]) >= 32, "At least 32 random characters; value never displayed")
    if os.getenv("DASHBOARD_CORS_ORIGINS"):
        origins = os.environ["DASHBOARD_CORS_ORIGINS"].split(",")
        record("explicit CORS origins", all(x.strip().startswith(("http://", "https://")) and "*" not in x for x in origins), "Supply exact origins, never wildcard credentials")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["start", "running"], default="running")
    parser.add_argument("--offline", action="store_true", help="Skip hosted credential presence check; does not change application provider mode")
    args = parser.parse_args()
    rows = check(args.mode, args.offline)
    print(json.dumps(rows, indent=2))
    raise SystemExit(0 if all(row["ok"] for row in rows) else 1)


if __name__ == "__main__":
    main()
