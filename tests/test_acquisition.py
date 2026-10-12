import hashlib
import importlib.util
import io
from pathlib import Path
import pytest

path = Path(__file__).resolve().parents[1] / "datasets/acquire_datasets.py"
spec = importlib.util.spec_from_file_location("project_acquisition", path)
acquisition = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acquisition)


def test_acquisition_hash_check_and_no_overwrite(tmp_path, monkeypatch):
    payload = b"fixture data"
    monkeypatch.setattr(
        acquisition, "urlopen", lambda *args, **kwargs: io.BytesIO(payload)
    )
    target = tmp_path / "data.json"
    receipt = acquisition.acquire(
        "https://fixture.invalid/file", hashlib.sha256(payload).hexdigest(), target
    )
    assert receipt.exists() and target.read_bytes() == payload
    with pytest.raises(FileExistsError):
        acquisition.acquire(
            "https://fixture.invalid/file", hashlib.sha256(payload).hexdigest(), target
        )


def test_hash_mismatch_publishes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        acquisition, "urlopen", lambda *args, **kwargs: io.BytesIO(b"wrong data")
    )
    target = tmp_path / "data.json"
    with pytest.raises(ValueError, match="hash"):
        acquisition.acquire("https://fixture.invalid/file", "0" * 64, target)
    assert not target.exists() and list(tmp_path.iterdir()) == []
