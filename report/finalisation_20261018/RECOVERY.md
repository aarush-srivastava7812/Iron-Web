# Recovery decision — 18 October 2026

## Evidence

The original v4.20.7 instance crashes replaying GRAPH.EFFECT on test graph keys.
It is stopped. A byte-identical SHA-256-verified backup volume remains unchanged.
The initial ten-effect and test_app-only trial repairs failed on further fixture
rollback keys. With explicit user approval, a final new trial omitted 43,384
operations confined to `test_` / `agents_test_` keys (including braced staging,
rollback and metadata keys), 40,217,323 bytes of the 41,229,758-byte increment log.
No operation mixed fixture and non-fixture keys. Every other command byte was
retained. Only this approved trial log was altered; the source and backup were
read-only throughout.

The final trial starts and passes PING, then restarts successfully on the same
image. Read-only counts of 22 non-fixture graphs match across that restart,
including 13 `voyara_` application graphs and seven claims for the fresh Kerala
acceptance trip. Base-RDB fixture graphs can remain; no blanket graph cleanup
was performed. Exact semantic equality to the original unstartable database
cannot be established, and a successful replay does not prove the engine bug
cannot recur.

The trial was stopped cleanly and copied byte-for-byte into an activation volume.
The original and pristine backup were rechecked and still match. The user then
explicitly approved live cutover and final tests. The activation volume is now
live on 6379 using the same image; website and relay were restarted from source.
Fresh hosted acceptance passed, followed by live consistency checks. See
`recovery-copy.json`, `recovery-aof-inventory.json`,
`recovery-repair.json`, `recovery-test-namespaces.json`,
`recovery-test-fixtures.json` and `recovery-validation.json`.

| Volume | Purpose / status |
| --- | --- |
| `iron_web_falkordb_data` | Original crash-reproducing persisted data; preserved, stopped. |
| `iron_web_falkordb_recovery_20261018` | Pristine verified recovery copy; never started or altered. |
| `iron_web_falkordb_repair_fixtures_20261018` | Approved fixture-filtered diagnostic repair; starts and restarts, now stopped. |
| `iron_web_falkordb_recovered_live_20261018` | Verified cold copy activated with explicit user approval; live on 6379. |

## Approved cutover procedure — executed

1. Stop website and relay owners so no memory operation is in flight.
2. Activate the prepared volume using the existing pinned image and explicit
   override, retaining original/backup volumes:

   ```powershell
   docker compose -f compose.yaml -f compose.recovery.yaml up -d --wait falkordb
   ```

   This replaces the stopped service container and binds the activation copy to
   local port 6379. It does not edit or delete the original volume. The data model,
   provider/model and agent tool contracts remain unchanged.
3. Restart website and relay from current source, retaining their existing
   private environment and embedded-store directories. Start/reuse the frontend
   and run preflight. Verify the current published account/trip, vectors, receipts
   and graph health agree before new hosted writes.
4. Rerun regional hosted acceptance and the real-feed browser checks in fresh
   report directories. Keep full regression load on the separate disposable DB
   at port 6389. Finish with a controlled restart/reconnect check and report any
   failure. New live writes go to the activation volume only. These verification
   results are recorded in `post_recovery/`; the known engine defect has not been
   proven fixed merely by removing fixture history.

## Rollback and remaining risk

Stop the memory owner before switching volumes. Preserve activation data too;
rolling back volumes after new writes could lose newer state or disagree with
embedded Qdrant/journal files. The original volume is a forensic fallback, not a
known-working rollback: it still crashes. Do not claim automatic rollback or
delete it. Coordinate any later application-store restore separately.

Use `-f compose.yaml -f compose.recovery.yaml` consistently after an approved
cutover; plain Compose still names the preserved failing original volume. No
`down -v`, FLUSHDB, RDB-only rollback, major upgrade, history rewrite or further
graph/data deletion is authorized by the proposed cutover. If the production
restart fails again, stop and preserve the new evidence.
