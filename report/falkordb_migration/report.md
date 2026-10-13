# FalkorDB migration verification

Date: 13 October 2026. Implementation commit: `0ee86c9`.

## Changes

The active graph backend is FalkorDB, using the official Python client and the pinned `falkordb/falkordb:v4.20.7` Compose service. Qdrant remains the vector store. Application configuration, public imports, graph queries, maintenance, evaluation scripts and tests use named graphs in place of Kùzu file paths. The optional legacy importer is the only remaining runtime use of Kùzu.

Native indexes and unique/mandatory identifier constraints preserve graph lookup and ID requirements. Cooperating clients use a renewable Redis lease. Coordinated writes use an isolated graph copy, atomic publication and a recovery copy; caught errors restore the prior graph and exact vector snapshots. Tests cover a lost publication response, shared-client cache refresh, duplicate IDs, multiline text and a failed lease renewal. Finite server result limits are detected so incomplete results are rejected.

## Existing data

The active legacy file was opened read-only. Its SHA-256 remained `18386f5ea1da1be1e3adf24ad03ebdfb1d36a4c68a8975eb70fc9a62313428c1`.

| Graph data | Count |
| --- | ---: |
| Entity nodes | 10 |
| Observation nodes | 42 |
| RELATES relationships | 17 |
| ABOUT relationships | 42 |
| CONTRADICTS relationships | 0 |
| SUPERSEDES relationships | 0 |

Every node property, relationship property, direction and multiplicity was compared. Canonical graph SHA-256: `0fe2c0951eb8b49911b45ed382bc5a68177072834b37e5169d68f512dcdb4286`.

The existing Qdrant store has 112 records. Both the old graph and the imported graph cover the same 13 source memory records. The other 99 vector records were already unlinked; this migration does not infer or rebuild their graph history. Credentials, vectors, source graph files and extraction caches are excluded from the commit.

## Validation

- Full regression suite: 113 passed, 4 dataset tests deselected. These tests use real FalkorDB with offline neural/provider fixtures.
- Dataset checks: 4 passed, 113 deselected.
- Targeted transaction and migration checks after the final result-limit change: 8 passed.
- Python dependency validation: no broken requirements.
- Ruff F checks across memory, tests and scripts: passed.
- Container recreation: the importer reported `already_imported: true` and the exact graph hash remained unchanged.

The image startup script requires environment arguments. Runtime checks confirm `appendonly=yes`, `appendfsync=everysec`, `dir=/data`, and `RESULTSET_SIZE=-1`. The named volume is `iron_web_falkordb_data`; the host port is bound to `127.0.0.1:6379`. The corrected configuration was tested by recreating the container, rather than relying only on a restart of its filesystem.

Evidence: [legacy comparison](legacy_import.json), [recreated-service comparison](recreated_service_verification.json), [runtime settings](runtime_verification.json), [active-store check](active_store_verification.json), [regression output](regression_tests.txt), and [dataset output](dataset_tests.txt).

## Operational limits

Run `docker compose up -d --wait falkordb` before starting the application. Compose retains its named volume when the service is stopped or removed without volume deletion. Append-only logging uses one-second fsync; it is not a zero-loss guarantee during a host failure.

Graph copying adds work proportional to graph size for coordinated writes. Raw external graph writes do not participate in the application lease protocol. Process crashes can leave staging or recovery copies, and Qdrant/FalkorDB crash atomicity is not provided. The architecture decision documents these limits.

The previous 5%/20% evaluation and latency figures were measured with Kùzu at commit `6d10601`. They were preserved and have not been rerun as FalkorDB performance measurements. This report makes no latency improvement claim.

Setup and import instructions: [migration guide](../../docs/falkordb_migration.md). Design record: [ADR-001](../../docs/architecture/adr-001-falkordb.md).
