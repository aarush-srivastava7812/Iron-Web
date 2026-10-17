"""Keep the control inspector scoped to the selected synthetic node."""
from pathlib import Path
p=Path(__file__).resolve().parent/'viewer.py'
t=p.read_text(encoding='utf-8')
t=t.replace("function inspect(f){selectedFacet", "function inspect(f){selectedFacet")
t=t.replace("['Modality',recMap[f.record_id].modality]", "['Modality',f.synthetic_case?'SYNTHETIC test; not incoming data':recMap[f.record_id].modality]")
t=t.replace("for(const sid of f.sources){", "if(f.synthetic_case){txt(b,'div','Synthetic control: '+m.counterfactuals.fixtures.find(c=>c.case===f.synthetic_case).text,'source')}else for(const sid of f.sources){")
t=t.replace("'gold');node(b.id,760,300,360,'Synthetic new claim',`${b.slot} = ${JSON.stringify(b.value)}`,'green');", "'gold',()=>inspect(facetMap[a.id]));node(b.id,760,300,360,'Synthetic new claim',`${b.slot} = ${JSON.stringify(b.value)}`,'green',()=>inspect(facetMap[b.id]));")
t=t.replace("500,235+i*45,e.type", "500,268+i*45,e.type")
start="const d=document.querySelector('#detail');d.replaceChildren();txt(d,'h2',c.case);txt(d,'p',c.reason);const de=document.createElement('details');d.append(de);txt(de,'summary','Stored before/after states and fuzzy trace');txt(de,'pre',JSON.stringify(c,null,2))"
assert start in t
t=t.replace(start,"inspect(facetMap[b.id]);const d=document.querySelector('#detail');txt(d,'p',c.reason);const de=document.createElement('details');d.append(de);txt(de,'summary','Stored before/after states');txt(de,'pre',JSON.stringify(c,null,2))")
t=t.replace("view=key;render()", "view=key;if(view!=='controls'&&facetMap[selectedFacet].synthetic_case)inspect(m.facets.find(f=>f.slot==='education.year'));render()")
needle="for(const f of m.facets){const o=document.createElement('option');"
assert needle in t
t=t.replace(needle,"for(const c of m.counterfactuals.fixtures)for(const f of[c.old,c.new])facetMap[f.id]={...f,synthetic_case:c.case};for(const f of Object.values(facetMap)){const o=document.createElement('option');")
t=t.replace("o.textContent=`${f.record_id} · ${f.slot}","o.textContent=`${f.synthetic_case?'SYNTHETIC '+f.synthetic_case:f.record_id} · ${f.slot}")
p.write_text(t,encoding='utf-8')
print('Synthetic node selection now drives the inspector; relationship labels aligned to their arrows.')
