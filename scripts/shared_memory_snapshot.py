"""Back up a stopped shared-memory runtime or restore into a fresh directory."""

# ruff: noqa: E402
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from memory.shared.snapshot import cold_backup, restore_fresh


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    save = commands.add_parser("backup")
    save.add_argument("--config", type=Path, required=True)
    save.add_argument("--destination", type=Path, required=True)
    restore = commands.add_parser("restore")
    restore.add_argument("--snapshot", type=Path, required=True)
    restore.add_argument("--runtime", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "backup":
        config = json.loads(args.config.read_text(encoding="utf-8"))
        result = cold_backup(
            config["runtime"],
            config["principals"],
            config["namespace"],
            args.destination,
        )
    else:
        result = restore_fresh(args.snapshot, args.runtime)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
