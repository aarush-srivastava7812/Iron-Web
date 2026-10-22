r"""Start a persistent local constraint-agent demo without competing for live memory.

Usage: .\.venv\Scripts\python.exe scripts/run_query_agent_demo.py
The normal website on 8094 and its memory dashboard can remain running.
"""
import os
from pathlib import Path
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    demo = root / ".scratch" / "query-agent-demo"
    demo.mkdir(parents=True, exist_ok=True)
    os.environ["DATABASE_URL"] = "sqlite:///" + (demo / "travel.db").as_posix()
    os.environ["AGENT_MEMORY_PATH"] = str(demo / "memory")
    if "--device" not in sys.argv:
        sys.argv.extend(["--device", "cpu"])
    if "--agent-mode" not in sys.argv:
        sys.argv.extend(["--agent-mode", "tinyfish"])
    if "--dialogue-mode" not in sys.argv:
        sys.argv.extend(["--dialogue-mode", "auto"])
    from run_voyara import main as run
    run()


if __name__ == "__main__":
    main()
