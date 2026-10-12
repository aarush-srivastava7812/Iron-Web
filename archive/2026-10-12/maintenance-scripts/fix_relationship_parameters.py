from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'memory/graph/kuzu_store.py'
s=p.read_text(encoding='utf-8')
a=s.index('    def upsert_relation(');b=s.index('    def get_relations(',a)
block=s[a:b].replace('start=valid_from, end=valid_until','vf=valid_from, vu=valid_until').replace('$start','$vf').replace('$end','$vu').replace('"start", "end"','"vf", "vu"')
s=s[:a]+block+s[b:]
p.write_text(s,encoding='utf-8')
p=root/'tests/test_storage_persistence.py'
s=p.read_text(encoding='utf-8').replace('        quantization=False,\n','')
p.write_text(s,encoding='utf-8')
