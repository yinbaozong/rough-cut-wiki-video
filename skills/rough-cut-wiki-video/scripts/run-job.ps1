<#
.SYNOPSIS
One command from footage to a registered Jianying draft.

.DESCRIPTION
Pins Simplified Chinese recognition, optional glossary repair, parallel audio
extraction, and fingerprint-gated staging validation. Save this file as UTF-8
with BOM so Windows PowerShell 5.1 can parse Chinese strings.

.EXAMPLE
.\run-job.ps1 -JobName tray-disassembly `
    -Media 'E:\footage\tray' `
    -WikiText '移除底壳固定螺丝，取出底壳，安装底壳预锁紧固定螺丝，全部螺丝安装完成后再最终锁紧。' `
    -JobRoot 'E:\roughcut-jobs' `
    -Lexicon 'E:\glossary.txt'
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$JobName,
    [Parameter(Mandatory = $true)][string]$Media,
    [string]$WikiText,
    [string]$WikiFile,
    [string]$DraftName,
    [string]$JobRoot = (Join-Path (Get-Location) 'jobs'),
    [string]$Lexicon,
    [string]$Drafts = 'D:\Software\JianyingPro Drafts',
    [string]$UserData = "$env:LOCALAPPDATA\JianyingPro\User Data",
    [string]$FfmpegBin,
    [int]$Workers = 6,
    [int]$BatchSize = 2,
    [int]$ChunkLength = 10,
    [int]$CpuThreads = 0,
    [switch]$ReuseTakes,
    [switch]$NoDraft,
    [switch]$ForceStaging,
    [switch]$SkipLexiconReview
)

$ErrorActionPreference = 'Stop'
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = 'utf-8'

$skill = Split-Path -Parent $PSScriptRoot
$python = Join-Path $skill '.venv\Scripts\python.exe'
$cli = Join-Path $PSScriptRoot 'roughcut.py'
$job = Join-Path $JobRoot $JobName
$output = Join-Path $job 'output'
$state = Join-Path $JobRoot '.roughcut-state'
$fingerprintFile = Join-Path $state 'jianying-fingerprint.json'

foreach ($required in @($python, $cli)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing skill runtime: $required" }
}
if (-not (Test-Path -LiteralPath $Media)) { throw "Media folder is unreachable: $Media" }
if ($FfmpegBin -and (Test-Path -LiteralPath $FfmpegBin)) { $env:PATH = "$FfmpegBin;$env:PATH" }
New-Item -ItemType Directory -Force -Path $job, $output, $state | Out-Null

$wikiPath = Join-Path $job 'wiki.md'
if ($WikiFile) {
    Copy-Item -LiteralPath $WikiFile -Destination $wikiPath -Force
} elseif ($WikiText) {
    $clauses = $WikiText -split '[，,。；;]' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    $lines = @("# Source wiki text (unchanged)", "# $WikiText", "")
    $index = 1
    foreach ($clause in $clauses) {
        $lines += "$index. $clause"
        $index++
    }
    Set-Content -LiteralPath $wikiPath -Value $lines -Encoding utf8
} elseif (-not (Test-Path -LiteralPath $wikiPath)) {
    throw 'Provide -WikiText or -WikiFile, or place wiki.md in the job folder first.'
}

$runArgs = @(
    $cli, 'run',
    '--media', $Media,
    '--wiki', $wikiPath,
    '--output', $output,
    '--workers', $Workers,
    '--batch-size', $BatchSize,
    '--chunk-length', $ChunkLength
)
if ($CpuThreads -gt 0) { $runArgs += @('--cpu-threads', $CpuThreads) }
if ($Lexicon -and (Test-Path -LiteralPath $Lexicon)) { $runArgs += @('--lexicon', $Lexicon) }
$corrections = Join-Path $job 'corrections.json'
if (Test-Path -LiteralPath $corrections) { $runArgs += @('--corrections', $corrections) }
if ($ReuseTakes) { $runArgs += '--reuse-takes' }

Write-Host "[1/3] Analyzing footage -> $output" -ForegroundColor Cyan
$started = Get-Date
& $python @runArgs
if ($LASTEXITCODE -ne 0) { throw "Analysis failed with exit code $LASTEXITCODE" }
Write-Host ("      done in {0:n1}s" -f ((Get-Date) - $started).TotalSeconds) -ForegroundColor DarkGray

if ($NoDraft) {
    Write-Host "Skipping Jianying draft (-NoDraft). Review $output\review.md" -ForegroundColor Yellow
    return
}

# Pinyin similarity finds real homophone errors but cannot tell them from wrong
# terms that merely sound alike, so an undecided proposal means the timeline may
# still move. Building a draft now would just be thrown away.
$reviewFile = Join-Path $output 'lexicon-review.json'
if (-not $SkipLexiconReview -and (Test-Path -LiteralPath $reviewFile)) {
    $pending = (Get-Content -LiteralPath $reviewFile -Raw -Encoding utf8 | ConvertFrom-Json).pending
    if ($pending -gt 0) {
        Write-Host ''
        Write-Host "Stopping before the draft: $pending term repair(s) need a decision." -ForegroundColor Yellow
        Write-Host "  1. Open $reviewFile and set each decision to accept or reject."
        Write-Host '  2. Re-run this command with -ReuseTakes to apply them in seconds.'
        Write-Host '  Use -SkipLexiconReview to build the draft without deciding.'
        Write-Host "  Details are also listed in $output\review.md"
        return
    }
}

$plan = Join-Path $output 'edit-plan.json'
$current = & $python $cli fingerprint --drafts $Drafts | Out-String
if ($LASTEXITCODE -ne 0) { throw 'Unable to read the Jianying fingerprint' }
$previous = if (Test-Path -LiteralPath $fingerprintFile) { Get-Content -LiteralPath $fingerprintFile -Raw } else { '' }
$normalize = { param($text) ($text -replace '\s', '') }
$needsStaging = $ForceStaging -or ((& $normalize $current) -ne (& $normalize $previous))

if ($needsStaging) {
    $staging = Join-Path $job 'jianying-staging'
    Write-Host '[2/3] Jianying changed since last run; validating encoding in an isolated staging draft' -ForegroundColor Cyan
    if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
    & $python $cli jianying10 --plan $plan --drafts $staging --name "$JobName-compat" --allow-replace
    if ($LASTEXITCODE -ne 0) { throw 'Staging validation failed; not touching the Jianying homepage index' }
    Remove-Item -LiteralPath $staging -Recurse -Force
    Set-Content -LiteralPath $fingerprintFile -Value $current -Encoding utf8
    Write-Host '      staging passed and fingerprint recorded' -ForegroundColor DarkGray
} else {
    Write-Host '[2/3] Fingerprint unchanged; skipping staging validation' -ForegroundColor DarkGray
}

if (Get-Process -Name 'JianyingPro' -ErrorAction SilentlyContinue) {
    throw 'JianyingPro is running. Fully exit it so the homepage index can be updated safely.'
}
$name = if ($DraftName) { $DraftName } else { "$JobName-roughcut" }
Write-Host "[3/3] Building registered draft: $name" -ForegroundColor Cyan
& $python $cli jianying10 --plan $plan --drafts $Drafts --name $name --user-data $UserData --allow-replace
if ($LASTEXITCODE -ne 0) { throw "Draft registration failed with exit code $LASTEXITCODE" }

Write-Host ''
Write-Host "Draft ready: $name" -ForegroundColor Green
Write-Host "Review report: $output\review.md"
Write-Host 'Open Jianying; the draft appears on the homepage.'
