$ErrorActionPreference = 'Stop'
$workspaceRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$workspacePrefix = $workspaceRoot.TrimEnd('\') + '\'
$records = @()
foreach ($name in @('run_ablation_matrix_frozen','export_official_20percent_slice','freeze_official_slices','official_upstream_preflight','run_official_upstream_benchmarks','run_mempalace_gpu')) {
    $sourcePath = [IO.Path]::GetFullPath((Join-Path $workspaceRoot "scripts/$name.py"))
    $targetPath = [IO.Path]::GetFullPath((Join-Path $workspaceRoot "archive/2026-10-12/legacy-code/scripts/$name.py"))
    if (-not $sourcePath.StartsWith($workspacePrefix, [StringComparison]::OrdinalIgnoreCase) -or -not $targetPath.StartsWith($workspacePrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Archive path leaves workspace.' }
    if (Test-Path -LiteralPath $targetPath) { throw "Target already exists: $targetPath" }
    $hashBefore = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
    Move-Item -LiteralPath $sourcePath -Destination $targetPath
    $hashAfter = (Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hashBefore -ne $hashAfter) { throw 'Archive verification failed.' }
    $records += [pscustomobject]@{source="scripts/$name.py"; target="archive/2026-10-12/legacy-code/scripts/$name.py"; sha256=$hashAfter}
}
$records | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $workspaceRoot 'archive/2026-10-12/script_moves.json') -Encoding utf8
Write-Output "Verified $($records.Count) remaining script moves."
