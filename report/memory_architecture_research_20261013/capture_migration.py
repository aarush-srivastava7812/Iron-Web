"""Snapshot read-only architecture evidence while the migration changes in parallel."""
import ast,hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
paths=['config.yaml','compose.yaml','requirements/storage.txt','memory/engine.py','memory/storage.py',
       'memory/graph/connection.py','memory/graph/falkordb_store.py','memory/retrieval/hybrid.py',
       'memory/vector_store/qdrant_store.py','memory/tool_adapter.py','memory/schema.py',
       'docs/architecture.md','docs/specification.md','research/upstream/packages.py']
snap=OUT/'migration_snapshot';snap.mkdir(exist_ok=True)
manifest=[]
for rel in paths:
    src=ROOT/rel;raw=src.read_bytes();target=snap/(rel.replace('/','__')+'.txt')
    if rel.endswith('.py'):ast.parse(raw.decode('utf-8'))
    target.write_bytes(raw)
    manifest.append({'source':rel,'snapshot':str(target),'sha256':hashlib.sha256(raw).hexdigest()})
head=subprocess.check_output(['git','-c','safe.directory='+str(ROOT).replace('\\','/'),'rev-parse','HEAD'],cwd=ROOT,text=True).strip()
record={'observed_at_utc':datetime.now(timezone.utc).isoformat(),'tracked_head':head,
        'workspace_is_in_progress':True,'runtime_measurements_performed':False,'snapshots':manifest}
(OUT/'migration_snapshot.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps({'snapshots':len(manifest),'tracked_head':head,'observed_at_utc':record['observed_at_utc']},indent=2))
