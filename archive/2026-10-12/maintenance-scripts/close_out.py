from pathlib import Path
import runpy
import json
import hashlib
root = Path(__file__).resolve().parents[1]
generator = root/'report/verification/scripts/generate_cleanup_report.py'
source = generator.read_text(encoding='utf-8').replace('100 passing tests', '101 passing tests')
source = source.replace("    '| `8f56d0f` | Separate application and verified research workflows |',", "    '| `8f56d0f` | Separate application and verified research workflows |',\n    '| `f65cc35` | Retain unique graph evidence during duplicate cleanup |',")
generator.write_text(source, encoding='utf-8')
runpy.run_path(str(generator), run_name='__main__')
for name in ('finalize_reports.py',):
    original = root/'report'/name
    destination = root/'archive/2026-10-12/maintenance-scripts'/name
    if not original.resolve().is_relative_to(root) or not destination.resolve().is_relative_to(root):
        raise ValueError('Path leaves workspace.')
    original.rename(destination)
print('Final report records 101 offline tests and the verified provenance follow-up.')
