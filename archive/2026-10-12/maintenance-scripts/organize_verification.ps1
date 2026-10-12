$ErrorActionPreference = 'Stop'
$workspaceRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$prefix = $workspaceRoot.TrimEnd('\') + '\'
$implementation = @('apply_adapter_cleanup.py','apply_config_cleanup.py','apply_configuration_and_identity.py','apply_consistency_followup.py','apply_engine_validation.py','apply_final_source_cleanup.py','apply_graph_cleanup.py','apply_ingestion_cleanup.py','apply_lazy_engine.py','apply_maintenance_cleanup.py','apply_metrics_cleanup.py','apply_package_cleanup.py','apply_relation_cleanup.py','apply_retrieval_cleanup.py','apply_scope_cleanup.py','apply_storage_cleanup.py','apply_store_and_extraction_cleanup.py','clean_model_interfaces.py','fix_relationship_parameters.py','replace_requirements_and_acquisition.py','update_dataset_notes.py','write_benchmark_runner.py','write_cached_extractor.py','write_research_retrievers.py','write_retrieval_modules.py','write_server_cleanup.py','archive_remaining_scripts.ps1','archive_state.ps1','cleanup_disposable_state.ps1')
$review = @('cleanup_file_review.py','cleanup_probes.py','cleanup_review.py','spec_inspection.py')
$pairs = @()
foreach ($name in $implementation) { $pairs += ,@("report/$name", "archive/2026-10-12/maintenance-scripts/$name") }
foreach ($name in $review) { $pairs += ,@("report/$name", "archive/2026-10-12/review-evidence/$name") }
$pairs += ,@('scripts/archive_sources.ps1','archive/2026-10-12/maintenance-scripts/archive_sources.ps1')
foreach ($name in @('dashboard_verification.json','dashboard_verification.png','disposable_cleanup.json')) { $pairs += ,@("report/$name", "report/verification/$name") }
$records = @()
foreach ($pair in $pairs) {
    $source = [IO.Path]::GetFullPath((Join-Path $workspaceRoot $pair[0]))
    $target = [IO.Path]::GetFullPath((Join-Path $workspaceRoot $pair[1]))
    if (-not $source.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or -not $target.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Path leaves workspace.' }
    if (-not (Test-Path -LiteralPath $source)) { continue }
    if (Test-Path -LiteralPath $target) { throw "Target exists: $target" }
    $before = (Get-FileHash -LiteralPath $source).Hash
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    Move-Item -LiteralPath $source -Destination $target
    $after = (Get-FileHash -LiteralPath $target).Hash
    if ($before -ne $after) { throw 'Evidence move changed content.' }
    $records += [pscustomobject]@{source=$pair[0]; target=$pair[1]; sha256=$after.ToLowerInvariant()}
}
foreach ($name in @('final_verification_temp','final_dataset_temp')) {
    $path = [IO.Path]::GetFullPath((Join-Path $workspaceRoot "report/$name"))
    if (Test-Path -LiteralPath $path) {
        $resolved = (Resolve-Path -LiteralPath $path).Path
        if (-not $resolved.StartsWith((Join-Path $workspaceRoot 'report').TrimEnd('\')+'\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Test directory leaves report.' }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
$records | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $workspaceRoot 'archive/2026-10-12/evidence_moves.json') -Encoding utf8
Write-Output "Organized and verified $($records.Count) implementation/evidence files; unrelated reports retained."
