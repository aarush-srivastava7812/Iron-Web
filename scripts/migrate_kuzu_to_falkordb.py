"""Read a legacy Kùzu graph without modifying it and verify its FalkorDB import."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

NODE_LABELS = ("Entity", "Observation")
EDGE_LABELS = {
    "RELATES": ("Entity", "Entity"),
    "ABOUT": ("Observation", "Entity"),
    "CONTRADICTS": ("Observation", "Observation"),
    "SUPERSEDES": ("Observation", "Observation"),
}


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical(snapshot):
    return {
        kind: {
            label: sorted(
                records,
                key=lambda row: json.dumps(
                    row, sort_keys=True, ensure_ascii=False, allow_nan=False
                ),
            )
            for label, records in labels.items()
        }
        for kind, labels in snapshot.items()
    }


def snapshot_hash(snapshot):
    value = json.dumps(
        canonical(snapshot), sort_keys=True, ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(value.encode()).hexdigest()


def legacy_snapshot(path):
    import kuzu

    database = kuzu.Database(str(path), read_only=True)
    connection = kuzu.Connection(database)

    def rows(query):
        result = connection.execute(query)
        columns = result.get_column_names()
        output = []
        while result.has_next():
            output.append(dict(zip(columns, result.get_next())))
        return output

    try:
        tables = {row["name"] for row in rows("CALL show_tables() RETURN name")}
        unsupported = tables - set(NODE_LABELS) - set(EDGE_LABELS)
        if unsupported:
            raise ValueError(f"Unsupported legacy graph tables: {sorted(unsupported)}")
        snapshot = dict(nodes={}, edges={})
        for label in NODE_LABELS:
            snapshot["nodes"][label] = (
                [
                    {
                        key.split(".", 1)[1]: value
                        for key, value in row.items()
                        if value is not None
                    }
                    for row in rows(f"MATCH (n:{label}) RETURN n.*")
                ]
                if label in tables
                else []
            )
        for label, (source, target) in EDGE_LABELS.items():
            snapshot["edges"][label] = []
            if label not in tables:
                continue
            for row in rows(
                f"MATCH (a:{source})-[r:{label}]->(b:{target}) RETURN a.id AS source_id,b.id AS target_id,r.*"
            ):
                snapshot["edges"][label].append(
                    dict(
                        source=row["source_id"],
                        target=row["target_id"],
                        properties={
                            key.split(".", 1)[1]: value
                            for key, value in row.items()
                            if key.startswith("r.") and value is not None
                        },
                    )
                )
        return canonical(snapshot)
    finally:
        connection.close()
        database.close()


def falkor_snapshot(store):
    snapshot = dict(nodes={}, edges={})
    for label in NODE_LABELS:
        snapshot["nodes"][label] = [
            dict(row[0])
            for row in store.execute(f"MATCH (n:{label}) RETURN properties(n)").rows
        ]
    for label, (source, target) in EDGE_LABELS.items():
        snapshot["edges"][label] = [
            dict(source=row[0], target=row[1], properties=dict(row[2]))
            for row in store.execute(
                f"MATCH (a:{source})-[r:{label}]->(b:{target}) RETURN a.id,b.id,properties(r)"
            ).rows
        ]
    return canonical(snapshot)


def import_graph(source_path, store):
    source_path = Path(source_path).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    before = file_hash(source_path)
    source = legacy_snapshot(source_path)
    expected = snapshot_hash(source)
    with store.write_lock:
        current = falkor_snapshot(store)
        if snapshot_hash(current) == expected:
            already_imported = True
        elif any(records for labels in current.values() for records in labels.values()):
            raise FileExistsError(
                "The target graph contains different data. Choose a new graph name; it will not be overwritten."
            )
        else:
            already_imported = False
            store.begin()
            try:
                for label, records in source["nodes"].items():
                    ids = [record.get("id") for record in records]
                    if any(
                        not isinstance(identifier, str) or not identifier
                        for identifier in ids
                    ) or len(set(ids)) != len(ids):
                        raise ValueError(
                            "Legacy graph contains missing or duplicate node identifiers."
                        )
                    for start in range(0, len(records), 100):
                        store.execute(
                            f"UNWIND $rows AS row CREATE (n:{label} {{id:row.id}}) SET n += row",
                            {"rows": records[start : start + 100]},
                        )
                for label, records in source["edges"].items():
                    source_label, target_label = EDGE_LABELS[label]
                    for start in range(0, len(records), 100):
                        store.execute(
                            f"UNWIND $rows AS row MATCH (a:{source_label} {{id:row.source}}),(b:{target_label} {{id:row.target}}) CREATE (a)-[r:{label}]->(b) SET r += row.properties",
                            {"rows": records[start : start + 100]},
                        )
                if snapshot_hash(falkor_snapshot(store)) != expected:
                    raise ValueError(
                        "Imported nodes, edges, direction or property values differ from the legacy graph."
                    )
                if file_hash(source_path) != before:
                    raise RuntimeError(
                        "Legacy file changed while it was being imported."
                    )
                store.commit()
                store.finish()
            except Exception:
                store.rollback()
                raise
        if snapshot_hash(falkor_snapshot(store)) != expected:
            raise ValueError("Published graph verification failed.")
    after = file_hash(source_path)
    if before != after:
        raise RuntimeError("Legacy file changed during migration.")
    return dict(
        source=str(source_path),
        source_sha256=before,
        source_unchanged=True,
        target_graph=store.graph_name,
        already_imported=already_imported,
        graph_content_sha256=expected,
        nodes={label: len(records) for label, records in source["nodes"].items()},
        edges={label: len(records) for label, records in source["edges"].items()},
        exact_properties_and_direction_verified=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(ROOT / "data/kuzu/memory.db"))
    parser.add_argument("--graph-name", default="iron_web")
    parser.add_argument("--report")
    options = parser.parse_args()
    from memory.graph import FalkorDBGraphStore

    with FalkorDBGraphStore(graph_name=options.graph_name) as store:
        result = import_graph(options.source, store)
    if options.report:
        path = Path(options.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        from memory.evaluation.harness.persistence import write_atomic

        write_atomic(path, json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
