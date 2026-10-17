"""Show only available report nodes in earlier receipt-stage graph lenses."""
from pathlib import Path
p=Path(__file__).resolve().parent/'viewer.py';t=p.read_text(encoding='utf-8')
t=t.replace('9 field confirmations','9 confirmation links · 6 earlier fields')
t=t.replace("['Confirmed fields',9]","['Confirmation links',9]")
t=t.replace("function organization(){const accepted", "function organization(){if(stage===1){node('inditech',500,180,400,'Inditech Electrosystems','Earlier canonical organization','blue');node('employment',500,450,400,'Reported employment','Earlier report · later status unknown','gold',()=>inspect(m.facets.find(f=>f.slot==='employment.organization')));edge('M500 415 L500 215',640,315,'employer role','blue');document.querySelector('#caption').textContent='Only the earlier employment report is available at this receipt stage. The later internship mention has not arrived.';return}const accepted")
t=t.replace("function projects(){node", "function projects(){if(stage===1){node('gdpe',500,180,480,'GDPE','Earlier elevator maintenance knowledge system','blue');node('sih',500,460,480,'SIH / GGSIPU2624','Earlier preference-prediction task','blue');document.querySelector('#caption').textContent='The newer platform and PrefIQ reports have not arrived at this receipt stage.';return}node")
t=t.replace("document.querySelector('#scoreMeaning').textContent=t.state_rule;", "document.querySelector('#scoreMeaning').textContent=(f.batch>stage&&!f.synthetic_case?'This field arrives in a later receipt stage; showing its score preview. ':'')+t.state_rule;")
p.write_text(t,encoding='utf-8')
print('Stage-one lenses preserve receipt order; nine links correctly identify six distinct earlier fields.')
