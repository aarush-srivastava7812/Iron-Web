"""Improve baseline placement and expose the real subject/evidence/reference graph."""
from pathlib import Path
OUT=Path(__file__).resolve().parent
path=OUT/'viewer.py'
code=path.read_text(encoding='utf-8')
old="subjectIds.forEach((id,i)=>positions[id]={x:500+100*Math.cos(i*6.283/subjectIds.length),y:360+85*Math.sin(i*6.283/subjectIds.length)});objectIds.forEach((id,i)=>positions[id]={x:500+440*Math.cos(i*6.283/objectIds.length),y:360+300*Math.sin(i*6.283/objectIds.length)});"
new="subjectIds.forEach((id,i)=>positions[id]=id==='north'?{x:500,y:360}:{x:500+170*Math.cos(i*6.283/subjectIds.length),y:360+150*Math.sin(i*6.283/subjectIds.length)});objectIds.forEach((id,i)=>{if(!positions[id])positions[id]={x:500+440*Math.cos(i*6.283/objectIds.length),y:360+300*Math.sin(i*6.283/objectIds.length)}});"
assert old in code
code=code.replace(old,new)
code=code.replace('()=>inspectRecord(r.id)','()=>openRecord(r.id)')
marker="function displayChecks(){"
extra=r'''function recordLens(r){
const src=r.sources.map(id=>sourceMap[id]),targets=Object.entries(r.refs);if(r.framework)targets.push(['USING_FRAMEWORK',r.framework]);
node(r.id,500,380,300,r.title,`${r.id} · ${r.kind}`,labels[r.kind],()=>inspectRecord(r.id));
node(r.subject,830,95,240,entityMap[r.subject].name,'SUBJECT · '+entityMap[r.subject].kind,'#8cbafa',()=>detail(entityMap[r.subject].name,[['Type',entityMap[r.subject].kind]],'The subject and owner are distinct roles.',entityMap[r.subject]));line(610,353,735,120,'SUBJECT','#8cbafa');
targets.forEach(([role,id],i)=>{const y=260+i*130;node(id,830,y,260,entityMap[id].name,role,'#e8c27d',()=>detail(entityMap[id].name,[['Role',role],['Type',entityMap[id].kind]],'Role binding is stored on the reference edge.',entityMap[id]));line(650,380,700,y,role==='USING_FRAMEWORK'?role:'REFERENCES: '+role,'#e8c27d')});
src.forEach((s,i)=>{const y=220+i*170;node(s.id,145,y,220,s.id,s.section,'#8cbafa',()=>inspectSource(s.id));line(350,380,255,y,'SUPPORTED_BY','#8cbafa')});
const ctx=m.contexts.find(c=>c.id===r.context);node(ctx.id,500,105,310,ctx.name.split(' / ').pop(),'Context · '+ctx.domain,'#73d5b7');line(500,137,500,345,'CONTAINS','#73d5b7');
svg.append(el('text',{x:500,y:505,'text-anchor':'middle',fill:'#c3d5e9','font-size':14},r.numeric_value==null?r.modality:`${r.numeric_value} ${r.unit} · ${r.modality}`));
svg.append(el('text',{x:500,y:545,'text-anchor':'middle',fill:'#a9bed4','font-size':13},'Source updated 2026-08-21 · effective dates unknown'));
document.querySelector('#caption').textContent='Actual record subgraph: Context, subject, role references/framework, and supporting Sources. Type, numeric value, units, conditions, and attribution are properties of the central record.';
}
function openRecord(id){inspectRecord(id);if(version!==2||mode==='policy')return;mode='record';document.querySelector('#canvas').hidden=false;document.querySelector('#checks').hidden=true;document.querySelector('#scale').hidden=true;document.querySelector('#context').hidden=true;document.querySelector('#viewTitle').textContent='Record, roles, framework, and evidence';clearSvg();recordLens(recordMap[id]);}
'''
assert marker in code
code=code.replace(marker,extra+marker)
code=code.replace("function inspectRecord(id){const r=recordMap[id];detail(r.title,","function inspectRecord(id){const r=recordMap[id];detail((version===1?'Revised record: ':'')+r.title,")
path.write_text(code,encoding='utf-8')
print('Baseline placement and semantic record lens added.')
