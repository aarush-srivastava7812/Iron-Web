"""The optional legacy import is read-only, exact and refuses conflicting targets."""

import pytest
from memory.graph import FalkorDBGraphStore
from scripts.migrate_kuzu_to_falkordb import import_graph, file_hash
from tests.fixtures.graph import graph_name_for


def test_legacy_import_preserves_source_and_refuses_overwrite(tmp_path):
    kuzu = pytest.importorskip("kuzu")
    source = tmp_path / "legacy.db"
    database = kuzu.Database(str(source))
    connection = kuzu.Connection(database)
    connection.execute("CREATE NODE TABLE Entity(id STRING PRIMARY KEY,name STRING)")
    connection.execute(
        "CREATE NODE TABLE Observation(id STRING PRIMARY KEY,content STRING)"
    )
    connection.execute(
        "CREATE REL TABLE ABOUT(FROM Observation TO Entity,relevance DOUBLE)"
    )
    connection.execute("CREATE (e:Entity {id:'one',name:'Alice'})")
    connection.execute(
        "CREATE (o:Observation {id:'fact',content:$text})", {"text": "first\nsecond"}
    )
    connection.execute(
        "MATCH(o:Observation),(e:Entity) CREATE(o)-[:ABOUT {relevance:0.75}]->(e)"
    )
    connection.close()
    database.close()
    before = file_hash(source)
    with FalkorDBGraphStore(graph_name_for(tmp_path)) as graph:
        report = import_graph(source, graph)
        assert report["source_unchanged"] and report["nodes"] == {
            "Entity": 1,
            "Observation": 1,
        }
        assert report["edges"]["ABOUT"] == 1
        assert import_graph(source, graph)["already_imported"]
        graph.upsert_entity("extra", "new data", "Concept")
        with pytest.raises(FileExistsError):
            import_graph(source, graph)
        assert graph.get_entity("extra") is not None
    assert file_hash(source) == before
