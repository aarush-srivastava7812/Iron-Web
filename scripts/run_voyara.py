"""Run the connected hackathon application from the repository root."""

import argparse
import os
import secrets
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--agent-mode", choices=["tinyfish", "nvidia", "offline", "auto"],
                        help="Select a provider for this local process only")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    backend = root / "stitch_ai_travel_booking_platform" / "backend"
    sys.path[:0] = [str(root), str(backend)]
    from dotenv import load_dotenv

    load_dotenv(backend / ".env")
    if args.agent_mode:
        os.environ["VOYARA_AGENT_MODE"] = args.agent_mode
    os.environ.setdefault("TINYFISH_CACHE_PATH", str(root / ".scratch" / "tinyfish-public-research"))
    os.environ.setdefault("DEV_LOGIN_ENABLED", "true")
    os.environ.setdefault("COOKIE_SECURE", "false")
    if not os.environ.get("SECRET_KEY") or os.environ["SECRET_KEY"].startswith(("dev-only", "change-me")):
        private = root / ".scratch" / "voyara-local"
        private.mkdir(parents=True, exist_ok=True)
        secret_file = private / "session.secret"
        if not secret_file.exists():
            secret_file.write_text(secrets.token_urlsafe(48), encoding="utf-8")
        os.environ["SECRET_KEY"] = secret_file.read_text(encoding="utf-8").strip()
    data = root / "data" / "voyara_app"
    data.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault(
        "DATABASE_URL", "sqlite:///" + (data / "travel.db").as_posix()
    )
    from seed import run
    import uvicorn

    run()
    # One web process owns the embedded journals/Qdrant stores. The shared
    # memory RuntimeLock rejects competing owners rather than corrupting them.
    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port, workers=1)


if __name__ == "__main__":
    main()
