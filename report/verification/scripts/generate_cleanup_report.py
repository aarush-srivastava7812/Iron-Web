import ast
import hashlib
import json
from pathlib import Path

root = next(parent for parent in Path(__file__).resolve().parents if (parent/"server.py").exists() and (parent/"memory").is_dir())
manifest = json.loads((root/'archive/2026-10-12/state_manifest.json').read_text(encoding='utf-8-sig'))
paths = [root/'server.py', *sorted((root/'memory').rglob('*.py')), *sorted((root/'scripts').glob('*.py')), root/'datasets/acquire_datasets.py', *sorted((root/'research').rglob('*.py')), *sorted((root/'web').glob('*'))]
inventory = []
for path in paths:
    if not path.is_file():
        continue
    data = path.read_bytes()
    if path.suffix == '.py':
        ast.parse(data.decode('utf-8'), filename=str(path))
    inventory.append(dict(path=str(path.relative_to(root)), lines=len(data.splitlines()), sha256=hashlib.sha256(data).hexdigest()))
verification = root/'report/verification'
verification.mkdir(exist_ok=True)
(verification/'current_source_inventory.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')
rows = [
('Reliable saving and deletion','Failed saves, replacements, updates and enrichment restore earlier state. Deletion uses exact ownership; shared information remains available.'),
('Conservative duplicate removal','Similar statements, different conversations and episodes stay separate. Exact semantic copies retain original metadata and entity associations.'),
('Remove fabricated extraction','Missing credentials or failed extraction no longer create simulated facts. Genuine cached responses are validated and retained.'),
('Reject incomplete input','Mismatched batches, invalid records, nonterminating chunk settings and incomplete extraction JSON are rejected before storage.'),
('Consistent time and fact versions','Current and historical searches follow the requested time. Only the old fact is marked superseded after its effective date; relationship intervals retain history.'),
('Checkable evaluation scores','Repeated results cannot increase credit, absent evidence is unscored, and resumed summaries include saved results. Context, dates, source and settings are checked.'),
('Remove preset dashboard claims','Fixed scores, invented comparisons and unconditional GPU labels were removed. Missing results and observed device state are displayed directly.'),
('Offline regression coverage','Ordinary checks use declared fixtures with actual temporary databases. Dataset checks are separately selectable; acquisition and shared package contracts have coverage.'),
('Visible errors and validated requests','Malformed input and service/storage failures produce errors. User text is rendered as text, and shared-store operations are serialized.'),
('One ingestion path','The pipeline, pre-extracted input and evaluator use the same engine writes and rollback protection.'),
('One evaluation contract','Core and optional package backends share local metrics, coverage checks, checkpoint persistence and result aggregation.'),
('Effective settings','Unknown settings fail validation. Declared paths, batch sizes, retrieval limits, score weights and optional components are connected to their actual behavior.'),
('Remove inactive score components','Unused relationship-strength and contrastive score terms and trace-only fusion were removed from normal ranking.'),
('Rank complete candidates','Graph evidence joins before ranking. CPU and GPU use the same bounded pool, requested result counts are retained, and original IDs/metadata survive.'),
('Load optional work when needed','Imports, graph-only search, status and maintenance previews avoid model initialization. Device status describes observed providers rather than promised acceleration.'),
('Accurate tool interface','The former MCP-labelled facade was retired. The current interface is an in-process Python adapter with working maintenance arguments.'),
('Accurate research names','Project-owned mechanisms use descriptive names. Genuine package adapters are separate; local metrics are not labelled as official benchmark scoring.'),
('Retire disconnected experiments','Earlier sweep/Optuna and duplicate phase frameworks are preserved in the legacy archive. The standalone sampling experiment remains explicitly optional.'),
('Consolidate entry points','Shared evaluation, slice export and diagnostics replace duplicate phase/gate scripts. The separate graph-population workaround and nonexistent Excel hook are retired.'),
('Current factual documentation','Current specification, architecture, setup and dataset notes replace completion claims and old examples. Earlier documents remain dated historical evidence.'),
('Separate dependencies','Storage, CPU, GPU, extraction, development and SDK research profiles are separate. Unused Neo4j and broad mandatory research packages were removed from application requirements.'),
('Remove unused code and controls','Unused imports, aliases, ineffective local indexes, unsupported model flags, duplicate prompts and silent fallback paths were removed or replaced.'),
('Archive unrelated source','Unused Letta and unrelated benchmark checkout material moved intact. Original records, licenses, provenance and evaluator references remain available.'),
('Preserve unique state','Historical outputs and experiment stores moved with before/after checksums. Active stores, caches, frozen inputs, papers and credentials stayed unchanged; known test data and caches were removed.'),
]
lines = ['# Cleanup implementation report','', '**Date:** 13 October 2026 (cleanup began 12 October)  ', '**Branch:** `cleanup/verified-memory`  ', '**Baseline:** `724c551`  ', '**Status:** Local implementation and preservation checks completed.','',
    'The cleanup was applied in verified stages and committed after substantial changes. The earlier full specification and removal plan describe the baseline; the current specification describes the revised application.','',
    '## Changes in priority order','', '| Priority | Change | Plain-language synopsis |','|---|---|---|']
for number, (title, synopsis) in enumerate(rows, 1):
    lines.append(f'| {number} | {title} | {synopsis} |')
lines += ['', '## Verification', '',
    '- Pre-change checks reproduced ten failures with forty passing checks. The failing cases included exact deletion, rollback, time filtering, graph-only retrieval and metric credit.',
    '- Final offline suite: 101 passing tests; four dataset tests are independently selectable.',
    '- Original dataset suite: four passing tests. Source hashes and repository revisions matched the existing provenance record.',
    '- Actual HTTP checks covered save/search, malformed input, reserved fields and cross-origin rejection.',
    '- Headless Edge checks covered desktop/mobile layout, saving, searching, literal script-like text and the empty evaluation state.',
    '- F-series static checks, Python parsing/compilation, JavaScript syntax and installed dependency consistency checks passed.',
    f'- Archive checks verified {len(manifest["moves"])} relocated groups containing {sum(m["files"] for m in manifest["moves"]):,} files and {sum(m["bytes"] for m in manifest["moves"]):,} bytes. Sixteen retained input groups and the credential file stayed unchanged.',
    f'- Current supported/research source inventory contains {len(inventory)} files and {sum(item["lines"] for item in inventory):,} physical lines. Python files were parsed and their hashes recorded.', '',
    '## Commits', '',
    '| Commit | Substantial change |','|---|---|',
    '| `724c551` | Preserve pre-cleanup source and reviews |',
    '| `1543729` | Restore complete memory state after failed writes |',
    '| `48991e3` | Remove fabricated extraction and unsafe maintenance |',
    '| `46c44b9` | Rank complete time-aware retrieval candidates |',
    '| `ed06e85` | Make evaluation scores and checkpoints verifiable |',
    '| `66314f7` | Show observed status and verified dashboard results |',
    '| `8f56d0f` | Separate application and verified research workflows |',
    '| `f65cc35` | Retain unique graph evidence during duplicate cleanup |', '',
    'The final preservation/report commit follows this implementation record. Commits are local; no remote publication was performed.', '',
    '## Evidence and current documentation', '',
    '- [Current specification](../docs/specification.md)',
    '- [Architecture decisions](../docs/architecture.md)',
    '- [Source relocation records](../archive/2026-10-12/source_moves.json)',
    '- [Additional script relocations](../archive/2026-10-12/script_moves.json)',
    '- [State preservation manifest](../archive/2026-10-12/state_manifest.json)',
    '- [Final source inventory](verification/current_source_inventory.json)',
    '- [Offline suite output](verification/final_test_output.txt)',
    '- [Dataset verification output](verification/dataset_test_output.txt)',
    '- [Dashboard verification](verification/dashboard_verification.json)', '',
    '## Scope and limits', '',
    'The verification exercised real local storage/query code and the live HTTP/browser paths using declared offline model fixtures. Real neural inference, GPU execution and hosted SDK/model benchmarks were not repeated. No benchmark-quality improvement or model latency guarantee is inferred from the fixture tests.', '',
    'Coordinated storage compensates caught failures in the running process; it does not provide a durable crash-atomic transaction across both databases. Existing user data and historical outputs were retained rather than silently reconstructed. CPU/GPU model profiles are intended for separate environments; the existing environment and its packages were preserved after repairing its launcher.', '',
    'Historical output uses earlier inputs and metric definitions. It remains evidence of those runs, not a current evaluation claim.']
(root/'report/cleanup_implementation_report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
print('Implementation report and current source inventory written.')
