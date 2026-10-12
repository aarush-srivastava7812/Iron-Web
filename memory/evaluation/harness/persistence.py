"""Stable fingerprints and atomic checkpoints for local evaluation runs."""

import hashlib
import json
import os
import tempfile
from pathlib import Path


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def source_fingerprint(extra_directories=()):
    root = Path(__file__).resolve().parents[3]
    paths = set()
    for name in ("memory", *extra_directories):
        directory = (root / name).resolve()
        if not directory.is_relative_to(root):
            raise ValueError("Evaluation source directory leaves the project.")
        paths.update(directory.rglob("*.py"))
    return fingerprint(
        {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths)
        }
    )


def write_atomic(path, text):
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
