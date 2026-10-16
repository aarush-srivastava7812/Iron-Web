"""The application and agents are distributed together in this repository."""
from pathlib import Path
import sys

_root = str(Path(__file__).resolve().parents[3])
if _root not in sys.path:
    sys.path.insert(0, _root)
