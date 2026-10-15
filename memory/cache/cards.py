"""Bounded private card matching; CUDA tensors are an optional disposable view."""

import secrets
from threading import RLock

import numpy as np


def normalized(values):
    array = np.array(values, dtype=np.float32, copy=True)
    if not np.isfinite(array).all():
        raise ValueError("Card embeddings must be finite.")
    norms = np.linalg.norm(array, axis=-1, keepdims=True)
    return np.ascontiguousarray(array / np.maximum(norms, np.finfo(np.float32).tiny))


class CardIndex:
    def __init__(
        self,
        *,
        use_gpu=False,
        max_bytes=64 * 1024 * 1024,
        safety_bytes=512 * 1024 * 1024,
        free_bytes=None,
    ):
        if not 1024 <= max_bytes <= 64 * 1024 * 1024 or safety_bytes < 0:
            raise ValueError("Invalid card GPU budget.")
        self.use_gpu, self.max_bytes, self.safety_bytes = (
            use_gpu,
            max_bytes,
            safety_bytes,
        )
        self.free_bytes = free_bytes or self._free_bytes
        self.lock, self.session = RLock(), None
        self.device_matrix, self.matrix = None, None
        self.owner, self.handle, self.ids = None, None, []
        self.fallback_reason = "not_requested" if not use_gpu else "uninitialized"
        self.peak_tensor_bytes = 0

    @staticmethod
    def _free_bytes():
        from memory.device import query_vram_telemetry

        free = query_vram_telemetry()[2]
        return int(free * 1024 * 1024) if free is not None else 0

    def _cuda_session(self):
        if self.session is not None:
            return self.session
        from memory.device import ensure_cuda_dlls_loaded

        ensure_cuda_dlls_loaded()
        import onnxruntime as ort
        from onnx import TensorProto, helper

        if "CUDAExecutionProvider" not in ort.get_available_providers():
            raise RuntimeError("CUDA provider unavailable")
        graph = helper.make_graph(
            [helper.make_node("MatMul", ["cards", "query"], ["scores"])],
            "card_dot",
            [
                helper.make_tensor_value_info(
                    "cards", TensorProto.FLOAT, ["count", "dimension"]
                ),
                helper.make_tensor_value_info(
                    "query", TensorProto.FLOAT, ["dimension", 1]
                ),
            ],
            [helper.make_tensor_value_info("scores", TensorProto.FLOAT, ["count", 1])],
        )
        model = helper.make_model(
            graph, opset_imports=[helper.make_opsetid("", 13)], ir_version=10
        )
        options = ort.SessionOptions()
        options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
        self.session = ort.InferenceSession(
            model.SerializeToString(),
            sess_options=options,
            providers=[
                (
                    "CUDAExecutionProvider",
                    {
                        "gpu_mem_limit": self.max_bytes // 2,
                        "arena_extend_strategy": "kSameAsRequested",
                    },
                )
            ],
        )
        if self.session.get_providers()[0] != "CUDAExecutionProvider":
            self.session = None
            raise RuntimeError("CUDA was not selected")
        return self.session

    def replace(self, owner, ids, vectors):
        matrix = normalized(vectors)
        if (
            not owner
            or matrix.ndim != 2
            or not 1 <= matrix.shape[0] <= 4096
            or matrix.shape[1] < 1
            or len(ids) != matrix.shape[0]
            or len(set(ids)) != len(ids)
        ):
            raise ValueError(
                "Card matrix requires a private owner, unique IDs and at most 4096 finite vectors."
            )
        # Leave half the explicit budget for the execution provider's arena.
        tensor_bytes = matrix.nbytes + matrix.shape[1] * 4 + matrix.shape[0] * 4
        with self.lock:
            self.clear()
            self.owner, self.ids, self.matrix = owner, list(ids), matrix
            self.handle = secrets.token_hex(24)
            if self.use_gpu:
                if tensor_bytes > self.max_bytes // 2:
                    self.fallback_reason = "card_budget_exceeded"
                elif (
                    self.free_bytes()
                    < tensor_bytes + self.safety_bytes + self.max_bytes // 2
                ):
                    self.fallback_reason = "insufficient_free_vram"
                else:
                    try:
                        self._cuda_session()
                        if self.free_bytes() < tensor_bytes + self.safety_bytes:
                            raise MemoryError(
                                "Device headroom changed during initialization"
                            )
                        import onnxruntime as ort

                        self.device_matrix = ort.OrtValue.ortvalue_from_numpy(
                            matrix, "cuda", 0
                        )
                        if self.device_matrix.device_name() != "cuda":
                            raise RuntimeError("Expected CUDA allocation")
                        self.peak_tensor_bytes = max(
                            self.peak_tensor_bytes, tensor_bytes
                        )
                        self.fallback_reason = None
                    except Exception as error:
                        self.device_matrix = None
                        self.fallback_reason = (
                            "cuda_unavailable:" + type(error).__name__
                        )
            return self.handle

    def rank(self, owner, handle, query, limit):
        vector = normalized(query)
        with self.lock:
            if owner != self.owner or handle != self.handle or self.matrix is None:
                raise PermissionError(
                    "Card handle is missing, stale or belongs to another private space."
                )
            if (
                vector.shape != (self.matrix.shape[1],)
                or type(limit) is not int
                or not 0 <= limit <= 4096
            ):
                raise ValueError("Invalid query embedding or selection bound.")
            reference = self.matrix @ vector
            scores = reference
            if self.device_matrix is not None:
                query_value = None
                try:
                    import onnxruntime as ort

                    query_value = ort.OrtValue.ortvalue_from_numpy(
                        vector[:, None], "cuda", 0
                    )
                    binding = self.session.io_binding()
                    binding.bind_ortvalue_input("cards", self.device_matrix)
                    binding.bind_ortvalue_input("query", query_value)
                    binding.bind_output("scores", "cpu")
                    self.session.run_with_iobinding(binding)
                    scores = binding.copy_outputs_to_cpu()[0].reshape(-1)
                    if not np.allclose(scores, reference, atol=1e-5, rtol=1e-5):
                        raise RuntimeError("GPU score parity failed")
                    # Common CPU resolution avoids backend-dependent near ties.
                    cutoff = sorted(scores, reverse=True)[
                        min(max(limit, 1), len(scores)) - 1
                    ]
                    near = np.abs(scores - cutoff) <= 1e-4
                    scores[near] = reference[near]
                except Exception as error:
                    self._clear_device()
                    self.fallback_reason = (
                        "cuda_execution_failed:" + type(error).__name__
                    )
                    scores = reference
                finally:
                    if query_value is not None:
                        try:
                            query_value.update_inplace(
                                np.zeros((vector.shape[0], 1), dtype=np.float32)
                            )
                        except Exception:
                            pass  # A lost device cannot certify physical erasure.
            return sorted(
                range(len(scores)),
                key=lambda i: (-round(float(scores[i]), 5), self.ids[i]),
            )[:limit]

    def _clear_device(self):
        if self.device_matrix is not None:
            device_value, self.device_matrix = self.device_matrix, None
            try:
                device_value.update_inplace(np.zeros_like(self.matrix))
            except Exception:
                pass  # Revoke the view even if a lost device cannot be cleared.

    def clear(self):
        with self.lock:
            self._clear_device()
            self.matrix, self.owner, self.handle, self.ids = None, None, None, []

    def invalidate(self, owner):
        with self.lock:
            if self.owner == owner:
                self.clear()

    def status(self):
        with self.lock:
            return dict(
                device="cuda" if self.device_matrix is not None else "cpu",
                resident_bytes=self.matrix.nbytes
                if self.device_matrix is not None
                else 0,
                peak_owned_tensor_bytes=self.peak_tensor_bytes,
                max_card_budget_bytes=self.max_bytes,
                provider_arena_limit_bytes=self.max_bytes // 2 if self.session else 0,
                fallback_reason=self.fallback_reason,
            )


class CardRouter:
    def __init__(self, **settings):
        self.index, self.key, self.handle = CardIndex(**settings), None, None
        self.lock = RLock()

    def select(self, owner, cards, query, embedder, limit):
        with self.lock:
            ordered = sorted(cards, key=lambda c: c["card_id"])
            key = (
                owner,
                tuple((c["card_id"], c["version"]) for c in ordered),
                type(embedder).__qualname__,
                getattr(embedder, "model_name", ""),
            )
            if self.key != key or self.index.owner != owner:
                vectors = embedder.embed([c["text"] for c in ordered])
                self.handle = self.index.replace(
                    owner, [c["card_id"] for c in ordered], vectors
                )
                self.key = key
            indices = self.index.rank(
                owner, self.handle, embedder.embed_single(query), len(ordered)
            )
            indices.sort(
                key=lambda i: ordered[i].get("mood") is None
            )  # explicit applicable mood first
            return [ordered[i] for i in indices[:limit]], self.index.status()

    def invalidate(self, owner):
        with self.lock:
            self.index.invalidate(owner)
            if self.key and self.key[0] == owner:
                self.key, self.handle = None, None

    def clear(self):
        with self.lock:
            self.index.clear()
            self.key, self.handle = None, None
