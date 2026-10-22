from .store import Embeddings, VectorMemory


def build_workflow(*args, **kwargs):
    """Load optional LangGraph integration only when a workflow is requested."""
    from .workflow import build_workflow as create

    return create(*args, **kwargs)

__all__ = ["Embeddings", "VectorMemory", "build_workflow"]
