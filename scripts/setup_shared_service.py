"""Create private local credentials for two isolated users and two agents each."""

import argparse
import hashlib
import json
from pathlib import Path
import secrets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=Path("data/shared_service"))
    args = parser.parse_args()
    root = args.runtime.resolve()
    root.mkdir(parents=True, exist_ok=True)
    config_path = root / "service.json"
    keys_path = root / "credentials.json"
    if config_path.exists() or keys_path.exists():
        parser.error("Existing setup preserved; choose a fresh runtime.")
    (root / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")
    principals, keys = [], []
    for tenant in ["traveller-a", "traveller-b"]:
        for actor, role in [
            ("traveller", "user"),
            ("planner", "agent"),
            ("reviewer", "agent"),
        ]:
            token = secrets.token_urlsafe(32)
            keys.append(dict(tenant=tenant, actor=actor, role=role, token=token))
            principals.append(
                dict(
                    tenant=tenant,
                    actor=actor,
                    role=role,
                    token_hash=hashlib.sha256(token.encode()).hexdigest(),
                )
            )
    config_path.write_text(
        json.dumps(
            dict(
                runtime=str(root),
                namespace="shared_" + secrets.token_hex(6),
                travel_interpreter=True,
                principals=principals,
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    keys_path.write_text(json.dumps(keys, indent=2), encoding="utf-8")
    print(
        f"Configuration: {config_path}\nPrivate credentials: {keys_path}\nTokens were not printed. Keep the credentials file private."
    )


if __name__ == "__main__":
    main()
