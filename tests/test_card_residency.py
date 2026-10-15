"""Card owner/handle isolation and CPU fallback, plus opt-in actual CUDA proof."""

import numpy as np
import pytest

from memory.cache.cards import CardIndex, CardRouter
from tests.conftest import FixtureEmbedder


def test_index_replacement_revokes_handles_and_keeps_owners_separate():
    index = CardIndex(use_gpu=False)
    first = index.replace(
        "A", ["first", "second"], np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    )
    assert index.rank("A", first, np.array([1.0, 0.0], dtype=np.float32), 1) == [0]
    with pytest.raises(PermissionError):
        index.rank("B", first, np.array([1.0, 0.0], dtype=np.float32), 1)
    second = index.replace("A", ["new"], np.array([[0.0, 1.0]], dtype=np.float32))
    with pytest.raises(PermissionError):
        index.rank("A", first, np.array([1.0, 0.0], dtype=np.float32), 1)
    assert first != second
    index.invalidate("A")
    with pytest.raises(PermissionError):
        index.rank("A", second, np.array([1.0, 0.0], dtype=np.float32), 1)


def test_admission_pressure_falls_back_without_changing_selection():
    index = CardIndex(
        use_gpu=True, max_bytes=1024, safety_bytes=512, free_bytes=lambda: 0
    )
    handle = index.replace("A", ["a", "b"], np.eye(2, dtype=np.float32))
    assert index.rank("A", handle, np.array([0.0, 1.0], dtype=np.float32), 1) == [1]
    assert index.status()["device"] == "cpu" and index.status()["resident_bytes"] == 0
    assert index.status()["fallback_reason"] == "insufficient_free_vram"


def test_router_filters_ranking_priority_and_returns_source_text():
    router = CardRouter(use_gpu=False)
    cards = [
        dict(card_id="general", version="1", text="hotel beach", mood=None),
        dict(card_id="mood", version="1", text="restful holiday", mood="relaxed"),
    ]
    selected, status = router.select("A", cards, "hotel beach", FixtureEmbedder(), 1)
    assert selected[0]["card_id"] == "mood" and status["device"] == "cpu"
    router.invalidate("A")
    assert router.index.status()["resident_bytes"] == 0


def test_invalid_vectors_cannot_enter_a_catalog():
    index = CardIndex(use_gpu=False)
    with pytest.raises(ValueError):
        index.replace("A", ["bad"], np.array([[np.nan, 1.0]], dtype=np.float32))
    with pytest.raises(ValueError):
        index.replace("A", ["one"], np.ones((4097, 2), dtype=np.float32))


def test_allocation_failure_uses_verified_cpu_matrix(monkeypatch):
    index = CardIndex(use_gpu=True, free_bytes=lambda: 2 * 1024**3)

    def unavailable():
        raise MemoryError("Injected allocation failure")

    monkeypatch.setattr(index, "_cuda_session", unavailable)
    handle = index.replace("A", ["a", "b"], np.eye(2, dtype=np.float32))
    assert index.rank("A", handle, np.array([0.0, 1.0], dtype=np.float32), 1) == [1]
    assert index.status()["fallback_reason"] == "cuda_unavailable:MemoryError"


@pytest.mark.gpu
def test_actual_cuda_residency_selection_and_clear():
    rng = np.random.default_rng(20261015)
    matrix = rng.normal(size=(64, 384)).astype(np.float32)
    index = CardIndex(use_gpu=True)
    handle = index.replace("gpu-proof", [str(i) for i in range(64)], matrix)
    status = index.status()
    assert status["device"] == "cuda", status
    assert status["resident_bytes"] >= matrix.nbytes
    assert index.device_matrix.device_name() == "cuda"
    cpu = CardIndex(use_gpu=False)
    reference = cpu.replace("gpu-proof", [str(i) for i in range(64)], matrix)
    for query in rng.normal(size=(12, 384)).astype(np.float32):
        assert index.rank("gpu-proof", handle, query, 3) == cpu.rank(
            "gpu-proof", reference, query, 3
        )
    index.clear()
    assert index.status()["resident_bytes"] == 0
