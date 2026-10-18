"""Start the single-owner travel API and its private graph in one cloud container."""

import os
from pathlib import Path
import sys
import subprocess
import time


def main():
    root = Path(__file__).resolve().parents[2]
    backend = root / "stitch_ai_travel_booking_platform" / "backend"
    sys.path[:0] = [str(root), str(backend)]

    from dotenv import load_dotenv
    load_dotenv("/etc/secrets/voyara.env")

    secret = os.environ.get("SECRET_KEY", "")
    if len(secret) < 32 or secret.startswith(("dev-only", "change-me")):
        raise RuntimeError("Set a strong SECRET_KEY before starting the cloud API.")
    data = Path(os.environ.get("VOYARA_DATA_PATH", "/data"))
    data.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("DATABASE_URL", "sqlite:///" + (data / "travel.db").as_posix())
    os.environ.setdefault("AGENT_MEMORY_PATH", str(data / "memory"))
    os.environ.setdefault("FASTEMBED_CACHE_PATH", str(data / "models"))
    os.environ.setdefault("COOKIE_SECURE", "true")
    os.environ["DEV_LOGIN_ENABLED"] = "false"

    graph = None
    if not os.environ.get("FALKORDB_HOST"):
        graph_data = data / "graph"
        graph_data.mkdir(parents=True, exist_ok=True)
        os.environ["FALKORDB_HOST"] = "127.0.0.1"
        os.environ["FALKORDB_PORT"] = "6379"
        graph = subprocess.Popen([
            "redis-server", "--bind", "127.0.0.1", "--port", "6379",
            "--dir", str(graph_data), "--appendonly", "yes", "--appendfsync", "everysec",
            "--save", "", "--loadmodule", "/usr/local/lib/falkordb.so",
            "MAX_QUEUED_QUERIES", "25", "TIMEOUT", "1000", "RESULTSET_SIZE", "-1",
        ])

    try:
        if graph:
            from redis import Redis
            from redis.exceptions import ConnectionError as RedisConnectionError

            connection = Redis(host="127.0.0.1", port=6379, socket_connect_timeout=1)
            for _ in range(100):
                if graph.poll() is not None:
                    raise RuntimeError("The private FalkorDB process exited during startup.")
                try:
                    if connection.ping():
                        break
                except RedisConnectionError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("The private FalkorDB process did not become ready.")
            connection.close()

        from seed import run
        import uvicorn

        run()
        # Embedded Qdrant and journals require one owner and one service replica.
        uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), workers=1)
    finally:
        if graph and graph.poll() is None:
            graph.terminate()
            try:
                graph.wait(timeout=30)
            except subprocess.TimeoutExpired:
                graph.kill()
                graph.wait()


if __name__ == "__main__":
    main()
