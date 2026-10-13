"""Coordinated writes for embedded vectors and the FalkorDB graph service.

Graph changes use an isolated clone and atomic publication. Vector changes use exact snapshots
and compensation. This is process-level consistency, not crash atomicity.
"""

from contextlib import contextmanager
from memory.models import EngineStorageError


@contextmanager
def coordinated_write(vector_store, graph_store, memory_ids):
    with graph_store.write_lock:
        snapshots = {mid: vector_store.get_memory(mid) for mid in memory_ids}
        graph_rolled_back = False
        graph_store.begin()
        try:
            yield
            graph_store.commit()
            graph_store.finish()
        except Exception as error:
            failures = []
            try:
                graph_store.rollback()
                graph_rolled_back = True
            except Exception as rollback_error:
                failures.append(str(rollback_error))
            for mid, snapshot in snapshots.items():
                try:
                    vector_store.restore_memory(mid, snapshot)
                except Exception as rollback_error:
                    failures.append(str(rollback_error))
            raise EngineStorageError(
                f"Coordinated write failed: {error}. "
                + (
                    "Original state restored."
                    if not failures and graph_rolled_back
                    else f"Rollback incomplete: {failures}"
                ),
                memory_id=next(iter(snapshots), ""),
                rolled_back=graph_rolled_back and not failures,
            ) from error
        finally:
            graph_store.invalidate_entity_name_index()
