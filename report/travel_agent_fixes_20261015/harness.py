"""Post-fix audit fixture server and sanitized API recorder."""

import argparse
import hashlib
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import sys
from threading import Thread
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PRIVATE = ROOT / "data/travel_agent_fixes_20261015"
sys.path.insert(0, str(ROOT))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
DLL_HANDLES = []
for directory in (ROOT / "data/evaluation_runtime").glob("*/nvidia/*/bin"):
    if os.name == "nt":
        DLL_HANDLES.append(os.add_dll_directory(str(directory.resolve())))
    os.environ["PATH"] = str(directory.resolve()) + os.pathsep + os.environ["PATH"]


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def clean(data):
    if isinstance(data, dict):
        return {key: "<redacted>" if "token" in key and key != "tokens" and key != "token_count" else clean(value) for key, value in data.items()}
    if isinstance(data, list):
        return [clean(value) for value in data]
    return data


def serve():
    from memory.cache.cards import CardRouter
    from memory.context.contracts import AgentProfile
    from memory.context.runtime import ContextRuntime
    from memory.context.tokens import TokenBudget
    from memory.embeddings.embedder import Embedder
    from memory.engine import MemoryEngine
    from memory.shared.interpreter import TravelInterpreter
    from memory.shared.service import SharedMemoryService
    from shared_server import handler_for
    PRIVATE.mkdir(parents=True, exist_ok=True)
    state_path = PRIVATE / "connection.json"
    if state_path.exists():
        raise ValueError("This audit runtime already exists; preserve it.")
    counter_path = Path.home()/".cache/huggingface/hub_backup/models--mistralai--Mistral-7B-Instruct-v0.1/snapshots/2dcff66eac0c01dc50e4c41eea959968232187fe/tokenizer.json"
    model = Embedder(use_gpu=False, cache_dir=str(Path(os.environ["TEMP"])/"fastembed_cache"))
    runtime = ContextRuntime(profiles=[
        AgentProfile(actor_id="planner", version="audit-v1", instructions="Act as the travel planner. Use current memory and fixture quotes. Make a draft, expose unknowns, and send it to the reviewer before any action."),
        AgentProfile(actor_id="reviewer", version="audit-v1", instructions="Act as the independent review role. Check the draft against current evidence, total costs and requirements. Use memory tools for missing constraints. Return a reasoned approval or rejection.")],
        tokens=TokenBudget.from_file(counter_path,"Mistral-7B-Instruct-v0.1-plain-audit"), ranker=CardRouter(use_gpu=True))
    credentials, keys = [], {}
    for tenant in ["riya", "arjun"]:
        keys[tenant] = {}
        for actor, role in [("user","user"),("planner","agent"),("reviewer","agent")]:
            token = secrets.token_hex(24)
            keys[tenant][actor]=token
            credentials.append(dict(tenant=tenant, actor=actor, role=role, token_hash=hashlib.sha256(token.encode()).hexdigest()))
    service = SharedMemoryService(PRIVATE/"runtime", credentials, namespace="test_travel_fixes_20261015",
        engine_factory=lambda path,name: MemoryEngine(config={"extraction_policy":"none"}, qdrant_path=str(path),graph_name=name,embedder=model,use_gpu=False),
        interpreter=TravelInterpreter(), context_runtime=runtime, autostart=False)
    audit_key=secrets.token_hex(24)
    base=handler_for(service)
    class Handler(base):
        def do_POST(self):
            if not self.path.startswith("/audit/"):
                return super().do_POST()
            if self.headers.get("X-Audit-Key") != audit_key:
                return self.send({"error":"Audit credential required"},403)
            if self.path == "/audit/drain":
                processed=0
                while service.process_one():
                    processed+=1
                return self.send(dict(processed=processed))
            if self.path == "/audit/status":
                index=runtime.ranker.index
                return self.send(dict(residency=index.status(),catalog_handle_hash=hashlib.sha256((index.handle or "").encode()).hexdigest(),
                    cache_bytes=runtime.cache.bytes,graphs={t:dict(name=e.graph_name,vectors=e.vector_store.count(),nodes=e.graph_store.get_node_counts()) for t,e in service.engines.items()}))
            if self.path == "/audit/stop":
                self.send(dict(stopped=True))
                Thread(target=self.server.shutdown,daemon=True).start()
                return
            return self.send({"error":"Unknown audit action"},404)
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    save(state_path,dict(url="http://127.0.0.1:"+str(server.server_port),keys=keys,audit_key=audit_key))
    print(json.dumps(dict(ready=True,private_state=str(state_path),fixture_only=True)),flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        service.close()


def resolve(value):
    if isinstance(value,str) and value.startswith("$response:"):
        _,label,field=value.split(":",2)
        result = json.loads((PRIVATE/"responses"/(label+".json")).read_text(encoding="utf-8"))
        for part in field.split("."):
            result = result[part]
        return result
    if isinstance(value,dict):
        return {k:resolve(v) for k,v in value.items()}
    if isinstance(value,list):
        return [resolve(v) for v in value]
    return value


def call(request_path):
    connection=json.loads((PRIVATE/"connection.json").read_text(encoding="utf-8"))
    specification=json.loads(Path(request_path).read_text(encoding="utf-8"))
    label=specification["label"]
    tenant,actor=specification.get("tenant","riya"),specification.get("actor","planner")
    body=resolve(specification.get("body",{}))
    headers={"Content-Type":"application/json"}
    if specification["path"].startswith("/audit/"):
        headers["X-Audit-Key"]=connection["audit_key"]
    else:
        headers["Authorization"]="Bearer "+connection["keys"][tenant][actor]
    request=Request(connection["url"]+specification["path"],data=json.dumps(body,allow_nan=False).encode(),headers=headers)
    start=time.perf_counter()
    try:
        with urlopen(request,timeout=120) as response:
            status,result=response.status,json.load(response)
    except HTTPError as error:
        status,result=error.code,json.load(error)
    elapsed=(time.perf_counter()-start)*1000
    save(PRIVATE/"responses"/(label+".json"),result)
    record=dict(label=label,tenant=tenant,actor=actor,path=specification["path"],request=clean(body),http_status=status,response=clean(result),elapsed_ms=elapsed)
    save(OUT/"exchanges"/(label+".json"),record)
    with (OUT/"transcript.ndjson").open("a",encoding="utf-8") as stream:
        stream.write(json.dumps(record,ensure_ascii=False)+"\n")
    print(json.dumps(record,indent=2,ensure_ascii=False))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["serve","call"])
    parser.add_argument("request",nargs="?")
    args=parser.parse_args()
    serve() if args.action=="serve" else call(args.request)
