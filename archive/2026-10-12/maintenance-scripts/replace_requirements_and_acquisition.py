from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1]
history=root/'archive/2026-10-12/design-history'
shutil.copy2(root/'requirements.txt',history/'requirements.original.txt')
shutil.copy2(root/'datasets/acquire_datasets.py',history/'acquire_datasets.original.py')
(root/'requirements.txt').write_text('# Default CPU application profile. GPU, hosted extraction, development and SDK research are separate.\n-r requirements/cpu.txt\n',encoding='utf-8')
(root/'datasets/acquire_datasets.py').write_text('''"""Download a declared dataset file to a new destination and verify its content hash.

Existing checkouts and files are never reset or overwritten.
"""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def source_for(benchmark):
    entries = json.loads((ROOT/"datasets/provenance.json").read_text(encoding="utf-8"))
    record = next(r for r in entries if r["benchmark"] == benchmark)
    filename = Path(record["data_file"]).name
    expected = record["file_hashes"][filename]
    if benchmark == "locomo":
        url = f"https://raw.githubusercontent.com/snap-research/locomo/{record['commit_hash']}/data/locomo10.json"
    elif benchmark == "longmemeval":
        url = "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_s_cleaned.json"
    else:
        url = f"https://huggingface.co/datasets/MemGPT/MSC-Self-Instruct/resolve/{record['revision']}/msc_self_instruct.jsonl"
    return url, expected


def acquire(url, expected_sha256, destination):
    destination = Path(destination)
    receipt = destination.with_name(destination.name+".provenance.json")
    if destination.exists() or receipt.exists():
        raise FileExistsError("Destination version already exists.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        digest = hashlib.sha256()
        with tempfile.NamedTemporaryFile("wb", dir=destination.parent, delete=False) as output:
            temporary = Path(output.name)
            with urlopen(url, timeout=120) as response:
                while chunk := response.read(1<<20):
                    digest.update(chunk)
                    output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        if digest.hexdigest() != expected_sha256:
            raise ValueError("Downloaded content does not match the declared source hash; nothing was published.")
        # A hard link publishes without clobbering a file created by another process.
        os.link(temporary, destination)
        with receipt.open("x", encoding="utf-8") as output:
            json.dump(dict(source_url=url, sha256=expected_sha256, data_file=str(destination)), output, indent=2)
        return receipt
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("benchmark", choices=["locomo", "longmemeval", "dmr"])
    parser.add_argument("destination", help="A new file path; use --dataset with this path when evaluating.")
    options = parser.parse_args()
    url, expected = source_for(options.benchmark)
    print(acquire(url, expected, options.destination))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''',encoding='utf-8')
p=root/'scripts/build_dmr_benchmark.py'
s=p.read_text(encoding='utf-8').replace('"""Materialize Phase 2 DMR corpus/query files from the official MSC release."""','"""Create a new derived MSC corpus/query version; preserves raw source and prior versions."""')
s=s.replace('import json','import json\nimport argparse\nimport hashlib',1)
s=s.replace('    if not SOURCE.exists():', '    parser = argparse.ArgumentParser(description=__doc__)\n    parser.add_argument("destination", help="A new derived dataset directory.")\n    output_dir = Path(parser.parse_args().destination)\n    if output_dir.exists():\n        raise FileExistsError("Derived dataset version already exists.")\n    if not SOURCE.exists():',1)
s=s.replace('    OUTPUT.mkdir(parents=True, exist_ok=True)', '    output_dir.mkdir(parents=True)')
s=s.replace('(OUTPUT /', '(output_dir /')
s=s.replace('    print(f"conversations=', '    (output_dir / "conversion_manifest.json").write_text(json.dumps(dict(source=str(SOURCE), source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(), converter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), source_rows=len(rows), documents=len(corpus), questions=len(queries)), indent=2), encoding="utf-8")\n    print(f"conversations=')
s=s.replace('OUTPUT = ROOT / "data" / "benchmarks" / "dmr"\n','')
p.write_text(s,encoding='utf-8')
