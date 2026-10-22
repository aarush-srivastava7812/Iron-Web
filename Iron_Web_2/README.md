# Iron Web 2

Independent local FalkorDB foundation for the rebuild. No original graph data
has been imported and the existing application still uses its original settings.

## Database

- Image: `falkordb/falkordb:v4.20.7` (pinned to the version already used locally).
- Container: `iron-web-2-falkordb`.
- Host connection: `127.0.0.1:6380` (container port `6379`).
- Intended application graph: `iron_web_2`; application schema is not installed yet.
- Data: `data/falkordb/` in this folder, excluded from Git.
- Persistence: AOF enabled, fsync every second. This is not a backup.
- Local access only. Browser UI is disabled.
- `.env.example` documents connection settings for the future backend; it is not
  automatically loaded into the existing application.

Run these commands from this folder:

```powershell
docker compose up -d --wait
docker compose ps
docker compose exec -T falkordb redis-cli PING
docker compose stop
```

The original container `iron-web-falkordb` and its Docker volume are separate.
Stopping this service preserves its data. Do not remove `data/` to stop it.
