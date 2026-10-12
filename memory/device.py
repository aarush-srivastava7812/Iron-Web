"""Observed device status and optional Windows runtime preparation. VRAM values are telemetry; profile targets are not allocation limits."""

import os
import site
import subprocess
from typing import Tuple, Optional, List, Any

from memory.models import DeviceStatus

# os.add_dll_directory returns a handle whose lifetime controls whether the
# directory remains in Windows' DLL search path. Retain these handles for the
# process lifetime rather than letting them be garbage-collected immediately.
_CUDA_DLL_DIRECTORY_HANDLES = []


# Automatically register NVIDIA cuDNN, cuBLAS, and CUDA DLL directories
def ensure_cuda_dlls_loaded() -> bool:
    """Ensure CUDA and cuDNN Windows DLL directories are registered."""
    try:
        registered = False
        for site_pkg in site.getsitepackages():
            if not os.path.exists(site_pkg):
                continue
            # TensorRT's pip wheel places its runtime DLLs directly under
            # site-packages/tensorrt_libs rather than nvidia/<component>/bin.
            tensorrt_bin = os.path.join(site_pkg, "tensorrt_libs")
            if os.path.exists(tensorrt_bin):
                try:
                    _CUDA_DLL_DIRECTORY_HANDLES.append(
                        os.add_dll_directory(tensorrt_bin)
                    )
                    registered = True
                except Exception:
                    pass
                if tensorrt_bin not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = tensorrt_bin + ";" + os.environ.get("PATH", "")
            nvidia_dir = os.path.join(site_pkg, "nvidia")
            if os.path.exists(nvidia_dir):
                # CUDAExecutionProvider also loads cudart64_12.dll. Keep every
                # pip-installed NVIDIA runtime directory on the DLL search path.
                for sub in [
                    "cuda_runtime",
                    "cudnn",
                    "cublas",
                    "cufft",
                    "cuda_nvrtc",
                    "nvjitlink",
                ]:
                    bin_dir = os.path.join(nvidia_dir, sub, "bin")
                    if os.path.exists(bin_dir):
                        try:
                            _CUDA_DLL_DIRECTORY_HANDLES.append(
                                os.add_dll_directory(bin_dir)
                            )
                            registered = True
                        except Exception:
                            pass
                        if bin_dir not in os.environ.get("PATH", ""):
                            os.environ["PATH"] = (
                                bin_dir + ";" + os.environ.get("PATH", "")
                            )
        return registered
    except Exception:
        return False


def configure_tensorrt_cache(cache_path: str) -> str:
    """Configure a local, device-specific TensorRT engine and timing cache."""
    resolved = os.path.abspath(cache_path)
    os.makedirs(resolved, exist_ok=True)
    # These settings are read when ONNX Runtime constructs the TRT session.
    # Engines are intentionally stored under project data: they are not portable
    # across model, ORT/TensorRT version, or GPU changes.
    os.environ["ORT_TENSORRT_ENGINE_CACHE_ENABLE"] = "1"
    os.environ["ORT_TENSORRT_CACHE_PATH"] = resolved
    os.environ["ORT_TENSORRT_TIMING_CACHE_ENABLE"] = "1"
    return resolved


# Informational target for the original 6 GB hardware profile; not an enforced allocator limit.
TOTAL_VRAM_MB: float = 6141.0
RESERVED_BUFFER_MB: float = 1024.0  # 1.0 GB safety buffer
MAX_OPERATIONAL_VRAM_MB: float = 5117.0  # ~5.0 GB maximum budget
SAFE_EMBED_BATCH_SIZE: int = 32
SAFE_RERANK_BATCH_SIZE: int = 16


def query_vram_telemetry() -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Query real-time GPU VRAM from NVIDIA SMI without modifying device state.

    Returns:
        (total_mb, used_mb, free_mb) or (None, None, None) if unavailable.
    """
    try:
        res = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.total,memory.used,memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=2.0,
        )
        line = res.stdout.strip().split("\n")[0]
        parts = [float(x.strip()) for x in line.split(",")]
        if len(parts) >= 3:
            return parts[0], parts[1], parts[2]
    except Exception:
        pass
    return None, None, None


def get_available_onnx_providers() -> List[str]:
    """Retrieve available ONNX Runtime execution providers."""
    try:
        import onnxruntime as ort

        return ort.get_available_providers()
    except ImportError:
        return []


def inspect_device_status(
    use_gpu_requested: bool = True,
    embedder: Optional[Any] = None,
    reranker: Optional[Any] = None,
) -> DeviceStatus:
    """
    Produce an observable DeviceStatus report.
    Inspects real providers on embedder/reranker instances and hardware telemetry.
    """
    providers = get_available_onnx_providers()
    gpu_provider_available = (
        "CUDAExecutionProvider" in providers or "DmlExecutionProvider" in providers
    )

    def active_component_provider(component: Any) -> str:
        """Read the provider selected by the live ONNX session, not its request."""
        fastembed_wrapper = getattr(component, "_model", None)
        onnx_wrapper = getattr(fastembed_wrapper, "model", None)
        session = getattr(onnx_wrapper, "model", None)
        get_providers = getattr(session, "get_providers", None)
        if callable(get_providers):
            selected = get_providers()
            if selected:
                return selected[0]
        requested = getattr(component, "_providers", None)
        return requested[0] if requested else "CPUExecutionProvider"

    # Check the actual providers on initialized instances.
    emb_prov = (
        active_component_provider(embedder) if embedder is not None else "Uninitialized"
    )
    rerank_prov = (
        active_component_provider(reranker) if reranker is not None else "Uninitialized"
    )

    total_mb, used_mb, free_mb = query_vram_telemetry()

    # Determine execution mode and status explanation
    if embedder is None and reranker is None:
        mode = "Uninitialized"
        notes = "No neural model has been initialized."
    elif emb_prov.startswith("Tensorrt") or rerank_prov.startswith("Tensorrt"):
        mode = "GPU (TensorRT)"
        notes = "An initialized model uses TensorrtExecutionProvider."
    elif emb_prov.startswith("CUDA") or rerank_prov.startswith("CUDA"):
        mode = "GPU (CUDA)"
        notes = "An initialized model uses CUDAExecutionProvider."
    elif emb_prov.startswith("Dml") or rerank_prov.startswith("Dml"):
        mode = "GPU (DirectML)"
        notes = "An initialized model uses DmlExecutionProvider."
    elif use_gpu_requested and not gpu_provider_available:
        mode = "CPU Fallback"
        notes = (
            "GPU execution was requested, but no CUDA or DirectML provider is available. "
            "Provider selection uses CPU where necessary."
        )
    elif not use_gpu_requested:
        mode = "CPU Execution"
        notes = "CPU execution configured explicitly."
    else:
        mode = "CPU Fallback"
        notes = "Execution running on CPUExecutionProvider."

    return DeviceStatus(
        gpu_enabled_requested=use_gpu_requested,
        cuda_available="CUDAExecutionProvider" in providers,
        active_providers=providers,
        embedder_provider=emb_prov,
        reranker_provider=rerank_prov,
        vram_total_mb=total_mb,
        vram_used_mb=used_mb,
        vram_free_mb=free_mb,
        vram_budget_mb=MAX_OPERATIONAL_VRAM_MB,
        safety_buffer_mb=RESERVED_BUFFER_MB,
        execution_mode=mode,
        status_notes=notes,
    )
