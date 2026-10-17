"""Allow comparison tables to scroll inside a narrow panel on mobile."""
from pathlib import Path
p=Path(__file__).resolve().parent/'viewer.py';t=p.read_text(encoding='utf-8')
t=t.replace('.panel{padding:20px;', '.panel{min-width:0;padding:20px;')
t=t.replace('select,button{font:inherit;', 'select,button{min-width:0;font:inherit;')
p.write_text(t,encoding='utf-8')
print('Comparison panels constrained to the viewport.')
