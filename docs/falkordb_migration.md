# FalkorDB migration

The application graph now uses FalkorDB. Qdrant, extraction and the memory/retrieval behavior remain separate components. Run `docker compose up -d --wait falkordb` before starting the app or its integration tests. The image is pinned to `falkordb/falkordb:v4.20.7`, and append-only data is stored in the `iron_web_falkordb_data` volume. `docker compose down` preserves that volume; deleting it removes the database data.

The supplied image reads startup settings through `REDIS_ARGS` and `FALKORDB_ARGS`. Compose sets the data directory to `/data`, enables append-only logging with `appendfsync everysec`, and sets `RESULTSET_SIZE -1` so graph inventories are complete. The application rejects queries that reach a configured finite result limit; reconnect after changing that server setting.

The application requires the official client from `requirements/storage.txt`. Python uses `FalkorDBGraphStore` and `MemoryEngine(graph_name="...")`; graph names replace the former file-path argument. Named evaluation/test graphs isolate their corpora. Unknown old `kuzu` settings are rejected rather than silently ignored.

Configuration has `falkordb.host`, `port`, `graph_name`, `tls`, `socket_timeout` and `query_timeout_ms`. Environment overrides are `FALKORDB_HOST`, `FALKORDB_PORT`, `FALKORDB_GRAPH_NAME` and `FALKORDB_TLS`. Credentials use `FALKORDB_USERNAME` / `FALKORDB_PASSWORD`; they are not written into effective configuration or result reports. The supplied service is local-only. An existing remote service requires its own access controls and connection settings.

## Import an existing graph

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements/migration.txt
.\.venv\Scripts\python.exe scripts/migrate_kuzu_to_falkordb.py --source data/kuzu/memory.db --graph-name iron_web --report report/my_import.json
```

The utility opens Kùzu read-only. It preserves Entity and Observation properties and all RELATES, ABOUT, CONTRADICTS and SUPERSEDES edges, including direction, parallel versions, timestamps, validity and ownership metadata. Full graph-content comparison and source-file hashing are checked before/after publication. A different populated target is never overwritten. Repeating an identical completed import verifies the content and reports that it was already imported.

The original graph file, vectors, credentials and extraction caches remain local. Kùzu is retained only as an optional import dependency; it is not an application backend. Imported application data is stored in the Docker volume and excluded from Git, like the earlier local stores.

## Verification and historical results

Regression tests exercise real FalkorDB with declared offline neural/extraction fixtures. They cover CRUD, restart/reopen persistence, temporal retrieval, exact deletion, maintenance, identifier constraints, shared clients, parameter round trips and rollback after a lost publication response. New staging/recovery graph tests do not use a simulated graph database.

The earlier 5%/20% reports in `report/reevaluation_20261013` were measured with Kùzu at commit `6d10601`. Their raw numbers have not been changed or rerun as FalkorDB benchmarks. To reproduce that historical run, use its original Git revision and recorded runtime. For a FalkorDB evaluation, choose a new run ID; source/configuration-bound resume deliberately rejects older incompatible runs.

The [architecture decision](architecture/adr-001-falkordb.md) records the transaction trade-offs and practical limits.
