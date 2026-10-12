from pathlib import Path
import runpy
import subprocess
import hashlib
import json

root = Path(__file__).resolve().parents[1]
generator = root/'report/generate_cleanup_report.py'
source = generator.read_text(encoding='utf-8').replace('**Date:** 12 October 2026', '**Date:** 13 October 2026 (cleanup began 12 October)')
generator.write_text(source, encoding='utf-8')
runpy.run_path(str(generator), run_name='__main__')
verification = root/'report/verification'
commands = [
    [str(root/'.venv/Scripts/python.exe'), '-m', 'ruff', 'check', 'memory', 'server.py', 'tests', 'research', 'scripts', 'datasets/acquire_datasets.py', '--select', 'F'],
    [str(root/'.venv/Scripts/python.exe'), '-m', 'ruff', 'format', '--check', 'memory', 'server.py', 'tests', 'research', 'scripts', 'datasets/acquire_datasets.py'],
    [str(root/'.venv/Scripts/python.exe'), '-m', 'pip', 'check'],
]
outputs = []
for command in commands:
    result = subprocess.run(command, cwd=root, text=True, capture_output=True, check=True)
    outputs.append(' '.join(command[1:])+'\n'+result.stdout+result.stderr)
(verification/'static_checks.txt').write_text('\n'.join(outputs), encoding='utf-8')
scripts = verification/'scripts'
scripts.mkdir(exist_ok=True)
records = []
for name in ('ui_preview.py','verify_dashboard.py','generate_cleanup_report.py'):
    original = root/'report'/name
    target = scripts/name
    text = original.read_text(encoding='utf-8')
    text = text.replace('Path(__file__).resolve().parents[1]', 'next(parent for parent in Path(__file__).resolve().parents if (parent/"server.py").exists() and (parent/"memory").is_dir())')
    if name=='verify_dashboard.py':
        text = text.replace('report/dashboard_verification', 'report/verification/dashboard_verification')
    original.write_text(text, encoding='utf-8')
    original.rename(target)
    records.append(dict(source='report/'+name, target=str(target.relative_to(root)), sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
original = root/'report/organize_verification.ps1'
target = root/'archive/2026-10-12/maintenance-scripts/organize_verification.ps1'
original.rename(target)
records.append(dict(source='report/organize_verification.ps1', target=str(target.relative_to(root)), sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
(verification/'organization.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
print('Final report, static checks and reproducible browser verification scripts organized.')
