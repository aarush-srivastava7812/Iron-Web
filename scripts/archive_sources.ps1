$ErrorActionPreference = 'Stop'
$workspaceRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$workspacePrefix = $workspaceRoot.TrimEnd('\') + '\'
$moves = @(
    @('memory/retrieval/competitors.py', 'research/retrievers/inspired.py'),
    @('memory/retrieval/contrastive.py', 'research/retrievers/contrastive.py'),
    @('memory/ingestion/mock_nim_extractor.py', 'tests/fixtures/extractor.py'),
    @('memory/mcp_server.py', 'archive/2026-10-12/legacy-code/memory/mcp_server.py')
)
foreach ($name in @('ablations','ablation_runner','baselines','baselines_comparison','contrastive_sweep','report_generator','scenarios')) {
    $moves += ,@("memory/evaluation/$name.py", "archive/2026-10-12/legacy-code/memory/evaluation/$name.py")
}
foreach ($name in @('run_ablations_phase7','run_benchmarks_phase6','run_competitor_benchmarks','populate_kuzu_longmemeval','test_gpu_paths','test_imports','verify_gate2_nim','profile_hybrid_latency','audit_retrieval_modes','capture_screenshots')) {
    $moves += ,@("scripts/$name.py", "archive/2026-10-12/legacy-code/scripts/$name.py")
}
foreach ($name in @('architecture_plan.md','roadmap.txt','hybrid_long_term_ai_memory_full_project_plan.txt','UPDATES_REQUIRED.md')) {
    $moves += ,@($name, "archive/2026-10-12/design-history/$name")
}
foreach ($file in Get-ChildItem -LiteralPath (Join-Path $workspaceRoot 'docs') -File) {
    $moves += ,@("docs/$($file.Name)", "archive/2026-10-12/design-history/docs/$($file.Name)")
}
foreach ($name in @('hybrid_memory_report.md','hybrid_memory_report.tex')) {
    $moves += ,@("report/$name", "archive/2026-10-12/reports/$name")
}
$records = @()
foreach ($pair in $moves) {
    $sourcePath = [IO.Path]::GetFullPath((Join-Path $workspaceRoot $pair[0]))
    $targetPath = [IO.Path]::GetFullPath((Join-Path $workspaceRoot $pair[1]))
    if (-not $sourcePath.StartsWith($workspacePrefix, [StringComparison]::OrdinalIgnoreCase) -or -not $targetPath.StartsWith($workspacePrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Archive path leaves workspace.' }
    if (-not (Test-Path -LiteralPath $sourcePath)) { throw "Missing archive source: $sourcePath" }
    if (Test-Path -LiteralPath $targetPath) { throw "Archive target already exists: $targetPath" }
    $resolvedSource = (Resolve-Path -LiteralPath $sourcePath).Path
    if (-not $resolvedSource.StartsWith($workspacePrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Resolved source leaves workspace.' }
    $hashBefore = (Get-FileHash -LiteralPath $resolvedSource -Algorithm SHA256).Hash.ToLowerInvariant()
    New-Item -ItemType Directory -Path (Split-Path -Parent $targetPath) -Force | Out-Null
    Move-Item -LiteralPath $resolvedSource -Destination $targetPath
    $hashAfter = (Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hashBefore -ne $hashAfter) { throw "Archive verification failed: $targetPath" }
    $records += [pscustomobject]@{source=$pair[0]; target=$pair[1]; sha256=$hashAfter}
}
$records | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $workspaceRoot 'archive/2026-10-12/source_moves.json') -Encoding utf8
Write-Output "Verified $($records.Count) source and document moves."
