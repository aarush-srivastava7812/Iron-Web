$ErrorActionPreference = 'Stop'
$workspaceRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$reportRoot = Join-Path $workspaceRoot 'report'
$reportPrefix = $reportRoot.TrimEnd('\') + '\'
$names = @('api_verified_temp','architecture_final_temp','cache_verified_temp','consistency_test_temp','consistency_verified_temp','dataset_verified_temp','evaluation_final_temp','evaluation_test_temp','evaluation_verified_temp','full_suite_temp','ingestion_final_temp','ingestion_test_temp','ingestion_verified_temp','latest_suite_temp','package_final_temp','pre_archive_final_temp','pre_cleanup_temp','relationship_test_temp','research_test_temp','research_verified_temp','retrieval_final_temp','retrieval_test_temp','retrieval_verified_temp','scope_test_temp','shared_runner_temp','storage_test_temp','storage_verified_temp','ui_preview_temp','validation_test_temp')
$removed = @()
foreach ($name in $names) {
    $path = [IO.Path]::GetFullPath((Join-Path $reportRoot $name))
    if (-not $path.StartsWith($reportPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Temporary path leaves report directory.' }
    if (Test-Path -LiteralPath $path) {
        $resolved = (Resolve-Path -LiteralPath $path).Path
        if (-not $resolved.StartsWith($reportPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Resolved temporary path leaves report directory.' }
        Remove-Item -LiteralPath $resolved -Recurse -Force
        $removed += $name
    }
}
foreach ($name in @('schema_probe.db','schema_probe.db.wal')) {
    $path = [IO.Path]::GetFullPath((Join-Path $reportRoot $name))
    if ($path.StartsWith($reportPrefix, [StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $path)) { Remove-Item -LiteralPath $path -Force }
}
$workspacePrefix = $workspaceRoot.TrimEnd('\') + '\'
$cacheRoots = @('memory','tests','scripts','research')
foreach ($name in $cacheRoots) {
    foreach ($directory in Get-ChildItem -LiteralPath (Join-Path $workspaceRoot $name) -Directory -Recurse -Filter '__pycache__') {
        $resolved = (Resolve-Path -LiteralPath $directory.FullName).Path
        if (-not $resolved.StartsWith($workspacePrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Cache path leaves workspace.' }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
foreach ($name in @('__pycache__','.pytest_cache','.ruff_cache','report/__pycache__')) {
    $path = [IO.Path]::GetFullPath((Join-Path $workspaceRoot $name))
    if (Test-Path -LiteralPath $path) {
        $resolved = (Resolve-Path -LiteralPath $path).Path
        if (-not $resolved.StartsWith($workspacePrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Cache path leaves workspace.' }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
[pscustomobject]@{removed_test_directories=$removed; unrelated_reports_untouched=$true; environment_packages_untouched=$true} | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $reportRoot 'disposable_cleanup.json') -Encoding utf8
Write-Output "Removed $($removed.Count) known test directories; retained logs, unrelated reports and environment packages."
