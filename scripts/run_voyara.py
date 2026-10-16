"""Run the connected hackathon application from the repository root."""

import argparse
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    backend = root / "stitch_ai_travel_booking_platform" / "backend"
    sys.path[:0] = [str(root), str(backend)]
    from dotenv import load_dotenv

    load_dotenv(backend / ".env")
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
