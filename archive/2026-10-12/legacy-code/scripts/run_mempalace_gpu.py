"""Launch the unmodified MemPalace CLI with Windows CUDA DLL directories registered.

The official package supports ``MEMPALACE_EMBEDDING_DEVICE=cuda`` but the
Windows CUDA wheels keep their DLLs outside PATH.  This wrapper only prepares
the process environment; all indexing/search behavior remains MemPalace's.
"""
from __future__ import annotations

import os
import site
import sys
from pathlib import Path


def _register_nvidia_dlls() -> list[object]:
    handles: list[object] = []
    directories: list[str] = []
    for root in map(Path, site.getsitepackages()):
        nvidia = root / "nvidia"
        if not nvidia.exists():
            continue
        for dll_dir in nvidia.glob("*/bin"):
            if dll_dir.is_dir():
                directories.append(str(dll_dir))
                handles.append(os.add_dll_directory(str(dll_dir)))
    # Some CUDA libraries load peer DLLs dynamically rather than through the
    # normal extension-module loader, for which PATH is still consulted.
    if directories:
        os.environ["PATH"] = os.pathsep.join(directories + [os.environ.get("PATH", "")])
    return handles


def main() -> int:
    if os.name != "nt":
        raise RuntimeError("This launcher is only needed on Windows.")
    handles = _register_nvidia_dlls()
    if not handles:
        raise RuntimeError("NVIDIA runtime DLL directories were not found.")
    os.environ.setdefault("MEMPALACE_EMBEDDING_DEVICE", "cuda")
    from mempalace.cli import main as mempalace_main

    mempalace_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
