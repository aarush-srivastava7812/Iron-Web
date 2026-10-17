"""Extend a KG demo with explicitly supplied extraction and inspect stored rows."""
import json
import sys
from pathlib import Path
import html

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from report.kg_demo import StorageTestEmbedder, export
from memory.engine import MemoryEngine


def main():
    out = Path(sys.argv[1]).resolve()
    evidence = json.loads((out/"evidence.json").read_text(encoding="utf-8"))
    def entity(id, name, type):
        return dict(id=id, name=name, type=type, description="Explicit demonstration input")
    atlas = entity("atlas", "Project Atlas", "Project")
    maya = entity("maya", "Maya", "Person")
    python = entity("python", "Python", "Technology")
    pg = entity("postgres", "PostgreSQL", "Technology")
    sqlite = entity("sqlite", "SQLite", "Technology")
    def extraction(entities, edges):
        return dict(entities=entities, relations=[dict(zip(("from", "to", "type", "confidence"), edge)) for edge in edges],
                    temporal={"valid_from": 0, "valid_until": 2**63-1}, importance=.8,
                    extractor_name="explicit demonstration input; not neural extraction", is_mock=True)
    inputs = [extraction([maya, atlas], [("maya", "atlas", "MAINTAINS", 1.)]),
              extraction([atlas, python, pg], [("atlas", "python", "USES", 1.), ("atlas", "postgres", "USES", 1.)]),
              extraction([atlas, sqlite, pg], [("atlas", "sqlite", "USES", 1.), ("atlas", "postgres", "AVOIDS", 1.)])]
    config = {"extraction_policy": "none", "qdrant": {"path": str(out/"supplied"/"qdrant")},
              "kuzu": {"path": str(out/"supplied"/"graph.db")}}
    with MemoryEngine(config=config, embedder=StorageTestEmbedder()) as engine:
        for index, (text, raw) in enumerate(zip(evidence["samples"], inputs), 1):
            engine.add(text, memory_id=f"sample_{index}", metadata={"source": "explicit_kg_demonstration"}, extraction=raw)
        evidence["supplied_inputs"] = inputs
        evidence["supplied"] = export(engine)
        evidence["supplied"]["vector_records"] = [{"memory_id": f"sample_{i}", "point": engine.vector_store.get_memory(f"sample_{i}")} for i in range(1, 4)]
    (out/"evidence.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    # Reopen the persisted database and verify it yields exactly the exported graph.
    from memory.graph.kuzu_store import KuzuGraphStore
    graph = KuzuGraphStore(str(out/"supplied"/"graph.db"))
    class GraphHolder:
        graph_store = graph
    persisted = export(GraphHolder())
    assert {k: evidence["supplied"][k] for k in ("entities", "observations", "edges")} == persisted
    graph.close()
    evidence["persistence_verified"] = True
    (out/"evidence.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    create_view(out, evidence)
    print(json.dumps({"output": str(out), "persistence_verified": True,
                      "counts": {k: len(persisted[k]) for k in ("entities", "observations", "edges")},
                      "entity_names": [e["name"] for e in persisted["entities"]],
                      "relations": [e for e in persisted["edges"] if e["type"] != "ABOUT"]}, indent=2))


def create_view(out, evidence):
    template = r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>KG inspection — actual database export</title><style>
*{box-sizing:border-box}body{margin:0;background:#101823;color:#e3edf8;font:15px system-ui}header{padding:22px 30px;border-bottom:1px solid #334355}h1{font-size:24px;margin:0 0 8px}p{line-height:1.5;margin:7px 0;color:#b8c8d9}.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:14px}button,select{padding:8px 12px;border:1px solid #58718e;border-radius:6px;background:#1d2d41;color:white;cursor:pointer}main{display:grid;grid-template-columns:minmax(500px,1fr) 340px;gap:15px;padding:20px}.canvas{border:1px solid #334355;border-radius:10px;background:#142031}svg{display:block;width:100%;height:750px}aside{padding:18px;background:#192739;border-radius:10px;overflow:auto}pre{white-space:pre-wrap;word-break:break-word;font-size:12px;line-height:1.5}.node{cursor:grab}.edge text{font-size:12px;fill:#bfd0e3;paint-order:stroke;stroke:#142031;stroke-width:5px}.node text{pointer-events:none;fill:white;text-anchor:middle;font-size:13px}.node:focus{outline:none}.node:focus rect{stroke:white;stroke-width:3}a{color:#94c9ff}small{color:#adbed2}#counts{margin-left:auto} @media(max-width:850px){main{grid-template-columns:1fr;padding:10px}svg{height:600px}aside{max-height:400px}}
</style><header><h1>Knowledge graph: actual stored nodes and edges</h1><p>Database export from an isolated run of the project's MemoryEngine. No production memories were changed.</p><p id="policy"></p><div class="toolbar"><select id="mode" aria-label="Choose ingestion run"><option value="supplied">Explicit structured input</option><option value="default">Default: extraction disabled</option></select><label><input type="checkbox" id="obs" checked> Show observation nodes</label><button id="reset">Reset layout</button><span id="counts"></span></div></header>
<main><div class="canvas"><svg id="graph" viewBox="0 0 1100 850" role="img" aria-label="Exported knowledge graph"></svg></div><aside><b>Click a node or edge to inspect its stored fields.</b><p>Blue = Entity. Amber = Observation. Solid arrows = entity relationships. Dashed arrows = ABOUT.</p><div id="detail"></div><hr><b>Submitted sentences</b><div id="samples"></div><hr><a href="evidence.json">Open full export, extraction input, and vectors</a><p><small>Embedding: deterministic storage test vectors. Structured extraction: explicitly supplied, is_mock=true. NIM attempt failed; no neural extraction was substituted.</small></p></aside></main>
<script>const evidence=__EVIDENCE__;const NS='http://www.w3.org/2000/svg';const svg=document.querySelector('#graph');let coords={},drag=null,edgeViews=[];
function el(tag,attrs={},text){const n=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;return n}
function detail(obj){const box=document.querySelector('#detail');box.replaceChildren();const pre=document.createElement('pre');pre.textContent=JSON.stringify(obj,null,2);box.append(pre)}
for(let i=0;i<evidence.samples.length;i++){let p=document.createElement('p');p.textContent=`sample_${i+1}: ${evidence.samples[i]}`;document.querySelector('#samples').append(p)}
function draw(){const mode=document.querySelector('#mode').value,data=evidence[mode],show=document.querySelector('#obs').checked;svg.replaceChildren();coords={};edgeViews=[];
document.querySelector('#policy').textContent=mode==='supplied'?'Actual Kùzu graph produced from explicitly supplied entities and relationships. These were not inferred by a model.':'Actual default ingestion: three Observation nodes, zero Entities, zero edges. Extraction was disabled.';
document.querySelector('#counts').textContent=`Stored: ${data.entities.length} entities · ${data.observations.length} observations · ${data.edges.length} edges`;
const defs=el('defs'),marker=el('marker',{id:'arrow',viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:6,markerHeight:6,orient:'auto-start-reverse'});marker.append(el('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#87a9ca'}));defs.append(marker);svg.append(defs);
const entities=[...data.entities].sort((a,b)=>a.name.localeCompare(b.name));entities.forEach((e,i)=>coords[e.id]={x:100+i*220,y:210});
let obs=show?data.observations:[];for(let row=1;row<=3;row++){const group=obs.filter(o=>o.memory_id===`sample_${row}`);group.forEach((o,i)=>coords[o.id]={x:550+(i-(group.length-1)/2)*310,y:370+(row-1)*185});svg.append(el('text',{x:30,y:330+(row-1)*185,fill:'#a7bed7','font-size':16},`Memory ${row}`))}
for(const e of data.edges){if(!coords[e.source]||!coords[e.target])continue;const g=el('g',{class:'edge'}),path=el('path',{fill:'none',stroke:e.type==='ABOUT'?'#58718e':'#8fbadd','stroke-width':e.type==='ABOUT'?1.3:2,'stroke-dasharray':e.type==='ABOUT'?'6 5':'','marker-end':'url(#arrow)'}),label=el('text',{'text-anchor':'middle'},e.type);g.append(path,label);g.addEventListener('click',()=>detail(e));svg.append(g);edgeViews.push({e,path,label})}
const nodes=[...entities.map(e=>({...e,kind:'Entity'})),...obs.map(o=>({...o,kind:'Observation'}))];for(const n of nodes){const p=coords[n.id],g=el('g',{class:'node',transform:`translate(${p.x},${p.y})`,tabindex:0,role:'button','aria-label':n.name||n.id});g.append(el('rect',{x:-90,y:-30,width:180,height:60,rx:12,fill:n.kind==='Entity'?'#214b77':'#6d4b1f',stroke:n.kind==='Entity'?'#74b3f0':'#dfb467'}));g.append(el('text',{y:-4},n.name||`${n.memory_id} observation`));g.append(el('text',{y:16,'font-size':11},n.kind==='Entity'?n.type:entities.find(e=>e.id===n.entity_id)?.name||'No entity link'));g.addEventListener('click',()=>detail(n));g.addEventListener('keydown',ev=>{if(ev.key==='Enter')detail(n)});g.addEventListener('pointerdown',ev=>{drag={id:n.id,g};g.setPointerCapture(ev.pointerId)});g.addEventListener('pointermove',ev=>{if(!drag||drag.id!==n.id)return;const p=new DOMPoint(ev.clientX,ev.clientY).matrixTransform(svg.getScreenCTM().inverse());coords[n.id]={x:p.x,y:p.y};g.setAttribute('transform',`translate(${p.x},${p.y})`);updateEdges()});g.addEventListener('pointerup',()=>drag=null);svg.append(g)}updateEdges();detail({run:mode,persistence_verified:evidence.persistence_verified,database:mode+'/graph.db',notes:'All displayed nodes and edges were queried from Kùzu.'})}
function updateEdges(){for(const{e,path,label}of edgeViews){const a=coords[e.source],b=coords[e.target];let d,tx,ty;if(e.type==='ABOUT'){d=`M ${a.x} ${a.y-30} L ${b.x} ${b.y+30}`;tx=(a.x+b.x)/2;ty=(a.y+b.y)/2}else{const bend=e.type==='AVOIDS'?150:70;d=`M ${a.x} ${a.y-30} Q ${(a.x+b.x)/2} ${Math.min(a.y,b.y)-bend} ${b.x} ${b.y-30}`;tx=(a.x+b.x)/2;ty=(a.y+b.y)/2-bend/2-20}path.setAttribute('d',d);label.setAttribute('x',tx);label.setAttribute('y',ty)}}
document.querySelector('#mode').addEventListener('change',draw);document.querySelector('#obs').addEventListener('change',draw);document.querySelector('#reset').addEventListener('click',draw);draw();</script></html>'''
    (out/"graph.html").write_text(template.replace('__EVIDENCE__', json.dumps(evidence, ensure_ascii=False).replace('<', '\\u003c')), encoding='utf-8')
    (out/"queries.cypher").write_text("""// Run against supplied/graph.db
MATCH (e:Entity) RETURN e.*;
MATCH (o:Observation) RETURN o.id, o.content, o.entity_id, o.source_memory_id;
MATCH (a:Entity)-[r:RELATES]->(b:Entity) RETURN a.name, r.relation_type, b.name, r.confidence;
MATCH (o:Observation)-[r:ABOUT]->(e:Entity) RETURN o.source_memory_id, o.id, e.name;
MATCH (a:Observation)-[r:CONTRADICTS]->(b:Observation) RETURN a.id, r.*, b.id;
MATCH (a:Observation)-[r:SUPERSEDES]->(b:Observation) RETURN a.id, r.*, b.id;
""", encoding='utf-8')


if __name__ == '__main__':
    main()
