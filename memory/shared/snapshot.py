"""Cold, private snapshots and fresh-target restoration for local deployments.

No global database flush/restart or overwrite is used. A snapshot requires the
service owner to stop first, keeps its runtime lock while copying closed vector
files, and exports only that deployment's named graph records as JSON.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil

from memory.lifecycle.models import canonical_json
from memory.shared.service import SharedMemoryService, RuntimeLock
from memory.storage import coordinated_write


def tenant_key(root, namespace, tenant):
    return hashlib.sha256(
        canonical_json([str(Path(root).resolve()), namespace, tenant]).encode()
    ).hexdigest()[:24]


def cold_backup(runtime, credentials, namespace, destination, engine_factory=None):
    root, output = Path(runtime).resolve(), Path(destination).resolve()
    if not root.exists() or output.exists() or output.is_relative_to(root):
        raise ValueError(
            "Use an existing stopped runtime and a fresh destination outside it."
        )
    owner = SharedMemoryService(
        root,
        credentials,
        namespace=namespace,
        engine_factory=engine_factory,
        autostart=False,
    )
    output.mkdir(parents=True)
    (output / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")
    graphs = []
    try:
        for tenant in sorted({p.tenant for _, p in owner.credentials}):
            engine = owner.engine(tenant)
            with engine.graph_store.write_lock, engine._operation_lock:
                records = dict(
                    nodes=engine.graph_store.execute(
                        "MATCH(n) RETURN labels(n),properties(n)"
                    ).rows,
                    edges=engine.graph_store.execute(
                        "MATCH(a)-[r]->(b) RETURN labels(a),a.id,type(r),labels(b),b.id,properties(r)"
                    ).rows,
                )
                data = canonical_json(records).encode()
                graphs.append(
                    dict(
                        tenant=tenant,
                        directory=tenant_key(root, namespace, tenant),
                        records=records,
                        sha256=hashlib.sha256(data).hexdigest(),
                        backend=getattr(engine, "backend", "legacy"),
                    )
                )
        # Embedded vectors must be closed before their SQLite/memmap files are
        # copied. The runtime lock stays held throughout this operation.
        for engine in owner.engines.values():
            engine.close()
        owner.journal.close()
        shutil.copytree(
            root, output / "runtime", ignore=shutil.ignore_patterns("owner.lock")
        )
        (output / "snapshot.json").write_text(
            json.dumps(
                dict(
                    format="shared_memory_snapshot_v3",
                    namespace=namespace,
                    credentials=credentials,
                    graphs=graphs,
                ),
                indent=2,
            ),
            encoding="utf-8",
        )
        return dict(
            snapshot=str(output), tenants=len(graphs), contains_private_data=True
        )
    finally:
        for engine in owner.engines.values():
            engine.close()
        owner.journal.close()
        owner.runtime_lock.close()


def restore_fresh(snapshot, runtime, engine_factory=None):
    source, target = Path(snapshot).resolve(), Path(runtime).resolve()
    if target.exists() or target.is_relative_to(source):
        raise ValueError("Restore requires a fresh destination outside the snapshot.")
    manifest = json.loads((source / "snapshot.json").read_text(encoding="utf-8"))
    if manifest["format"] not in {"shared_memory_snapshot_v2", "shared_memory_snapshot_v3"}:
        raise ValueError("Unsupported snapshot format.")
    payloads = []
    for item in manifest["graphs"]:
        raw = canonical_json(item["records"]).encode()
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("Snapshot checksum failed.")
        if not __import__("re").fullmatch(r"[a-f0-9]{24}", item["directory"]):
            raise ValueError("Invalid snapshot vector directory.")
        for labels, props in item["records"]["nodes"]:
            if not labels or not isinstance(props.get("id"), str) or not props["id"]:
                raise ValueError(
                    "Snapshot nodes require labels and stable string identities."
                )
        for labels in (
            [n[0] for n in item["records"]["nodes"]]
            + [e[0] for e in item["records"]["edges"]]
            + [e[3] for e in item["records"]["edges"]]
        ):
            if any(
                not __import__("re").fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", label)
                for label in labels
            ):
                raise ValueError("Invalid graph label in snapshot.")
        if any(
            not __import__("re").fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", e[2])
            for e in item["records"]["edges"]
        ):
            raise ValueError("Invalid graph relationship in snapshot.")
        payloads.append(item)
    target.mkdir(parents=True)
    lock = RuntimeLock(target / "owner.lock")
    from falkordb import FalkorDB

    client = FalkorDB(
        host=os.getenv("FALKORDB_HOST", "127.0.0.1"),
        port=int(os.getenv("FALKORDB_PORT", "6379")),
        username=os.getenv("FALKORDB_USERNAME"),
        password=os.getenv("FALKORDB_PASSWORD"),
        ssl=os.getenv("FALKORDB_TLS", "false").lower() == "true",
    )
    try:
        names = [
            manifest["namespace"]
            + "_"
            + tenant_key(target, manifest["namespace"], item["tenant"])
            for item in payloads
        ]
        names = [("iron_web_2_test" if name.startswith("test_") else "iron_web_2_app") + "_" + hashlib.sha256(name.encode()).hexdigest()[:24]
                 if item.get("backend") == "iron_web_2" else name for name, item in zip(names, payloads)]
        if any(client.connection.exists(name) for name in names):
            raise ValueError(
                "A target graph already exists; existing graph data is preserved."
            )
        shutil.copytree(
            source / "runtime",
            target,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("tenants", "owner.lock"),
        )
        for item in payloads:
            key = tenant_key(target, manifest["namespace"], item["tenant"])
            destination = target / "tenants" / key
            shutil.copytree(source / "runtime/tenants" / item["directory"], destination)
        config_path = target / "service.json"
        if config_path.exists():
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["runtime"] = str(target)
            config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    finally:
        client.close()
        lock.close()
    restored = SharedMemoryService(
        target,
        manifest["credentials"],
        namespace=manifest["namespace"],
        engine_factory=engine_factory,
        autostart=False,
        replay=False,
    )
    try:
        for item in payloads:
            engine = restored.engine(item["tenant"])
            engine.lifecycle.ensure_schema()
            with engine.graph_store.write_lock, engine._operation_lock, coordinated_write(
                engine.vector_store, engine.graph_store, []
            ):
                for labels, props in item["records"]["nodes"]:
                    properties = dict(props)
                    embedding = properties.pop("embedding", None)
                    engine.graph_store.execute(
                        "MERGE(n:"
                        + ":".join(labels)
                        + " {id:$props.id}) SET n += $props"
                        + (" SET n.embedding=vecf32($embedding)" if embedding is not None else ""),
                        {"props": properties, **({"embedding": embedding} if embedding is not None else {})},
                    )
                for (
                    source_labels,
                    source_id,
                    relation,
                    target_labels,
                    target_id,
                    properties,
                ) in item["records"]["edges"]:
                    engine.graph_store.execute(
                        "MATCH(a:"
                        + ":".join(source_labels)
                        + " {id:$sid}),(b:"
                        + ":".join(target_labels)
                        + " {id:$tid}) CREATE(a)-[r:"
                        + relation
                        + "]->(b) SET r += $props",
                        {"sid": source_id, "tid": target_id, "props": properties},
                    )
            engine.graph_store.execute(
                "MATCH(w:MemoryWork) SET w.lease_token='',w.lease_until=0 "
                "WITH w WHERE w.status <> 'completed' SET w.agent_id=''"
            )
        return dict(
            runtime=str(target),
            tenants=len(payloads),
            active_execution_leases_restored=False,
        )
    finally:
        restored.close()
