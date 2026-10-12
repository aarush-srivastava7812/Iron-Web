$ErrorActionPreference = 'Stop'
$workspaceRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$workspacePrefix = $workspaceRoot.TrimEnd('\') + '\'
function Assert-WorkspacePath([string]$path) {
    $full = [IO.Path]::GetFullPath($path)
    if (-not $full.StartsWith($workspacePrefix, [StringComparison]::OrdinalIgnoreCase)) { throw "Path leaves workspace: $full" }
    return $full
}
function Get-TreeFingerprint([string]$path) {
    $item = Get-Item -LiteralPath $path -Force
    $files = if ($item.PSIsContainer) { @(Get-ChildItem -LiteralPath $path -File -Recurse -Force) } else { @($item) }
    $rows = @()
    $size = 0L
    foreach ($file in ($files | Sort-Object FullName)) {
        $relative = if ($item.PSIsContainer) { $file.FullName.Substring($path.Length).TrimStart('\') } else { $file.Name }
        $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        $rows += "$relative`t$hash`t$($file.Length)"
        $size += $file.Length
    }
    $bytes = [Text.Encoding]::UTF8.GetBytes(($rows -join "`n"))
    $digest = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
    return [pscustomobject]@{files=$files.Count; bytes=$size; sha256=$digest}
}
$preserved = @('data/qdrant','data/kuzu/memory.db','data/extraction_cache','data/tensorrt_cache','data/cache','data/benchmarks','data/official_upstream/slices','researchpapers','datasets/dmr/msc_self_instruct.jsonl','datasets/locomo/data','datasets/locomo/task_eval','datasets/locomo/LICENSE.txt','datasets/longmemeval/data','datasets/longmemeval/src/evaluation','datasets/longmemeval/src/utils','datasets/longmemeval/LICENSE')
$before = @{}
foreach ($relative in $preserved) {
    $path = Assert-WorkspacePath (Join-Path $workspaceRoot $relative)
    if (Test-Path -LiteralPath $path) { $before[$relative] = Get-TreeFingerprint $path }
}
$credentialPath = Join-Path $workspaceRoot '.env'
$credentialBefore = if (Test-Path -LiteralPath $credentialPath) { (Get-FileHash -LiteralPath $credentialPath).Hash } else { $null }
$moves = @(@('datasets/letta','external-checkouts/letta'), @('metrics','run-records/metrics'), @('results','run-records/results'), @('screenshots','run-records/screenshots'), @('data/results','run-records/data-results'))
foreach ($name in @('ablation_matrix_frozen','ablation_run','benchmark_run','benchmark_runs_competitors','gpu_probe_qdrant','qdrant_gate4_probe')) { $moves += ,@("data/$name", "data/$name") }
foreach ($name in @('locomo','locomo_dryrun','longmemeval_dryrun','test_fresh.db','test_fresh2.db')) { $moves += ,@("data/kuzu/$name", "data/kuzu/$name") }
foreach ($name in @('hybrid_dbs','mem0_dbs','mempalace','mempalace_inputs','zep_dbs')) { $moves += ,@("data/official_upstream/$name", "data/official_upstream/$name") }
foreach ($name in @('generative_agents','prompt_examples','scripts','static','.git','index.html','hf_icon.png','requirements.txt')) { $moves += ,@("datasets/locomo/$name", "external-checkouts/locomo/$name") }
foreach ($name in @('assets','.git','requirements-full.txt','requirements-lite.txt')) { $moves += ,@("datasets/longmemeval/$name", "external-checkouts/longmemeval/$name") }
foreach ($name in @('generation','index_expansion','retrieval')) { $moves += ,@("datasets/longmemeval/src/$name", "external-checkouts/longmemeval/src/$name") }
$records = @()
foreach ($pair in $moves) {
    $source = Assert-WorkspacePath (Join-Path $workspaceRoot $pair[0])
    if (-not (Test-Path -LiteralPath $source)) { continue }
    $target = Assert-WorkspacePath (Join-Path $workspaceRoot "archive/2026-10-12/$($pair[1])")
    if (Test-Path -LiteralPath $target) { throw "Archive target already exists: $target" }
    $fingerprint = Get-TreeFingerprint $source
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    Move-Item -LiteralPath $source -Destination $target
    $after = Get-TreeFingerprint $target
    if ($fingerprint.sha256 -ne $after.sha256 -or $fingerprint.files -ne $after.files) { throw "Archive verification failed: $target" }
    $records += [pscustomobject]@{source=$pair[0]; target="archive/2026-10-12/$($pair[1])"; files=$after.files; bytes=$after.bytes; sha256=$after.sha256}
}
$preservation = @()
foreach ($relative in $before.Keys) {
    $after = Get-TreeFingerprint (Join-Path $workspaceRoot $relative)
    if ($before[$relative].sha256 -ne $after.sha256) { throw "Preserved input changed: $relative" }
    $preservation += [pscustomobject]@{path=$relative; unchanged=$true; files=$after.files}
}
$credentialAfter = if (Test-Path -LiteralPath $credentialPath) { (Get-FileHash -LiteralPath $credentialPath).Hash } else { $null }
if ($credentialBefore -ne $credentialAfter) { throw 'Credential file changed.' }
New-Item -ItemType Directory -Path (Join-Path $workspaceRoot 'data/results') -Force | Out-Null
[pscustomobject]@{moves=$records; preserved=$preservation; credentials_unchanged=$true} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $workspaceRoot 'archive/2026-10-12/state_manifest.json') -Encoding utf8
Write-Output "Verified $($records.Count) archived groups and $($preservation.Count) preserved input groups; credentials unchanged."
