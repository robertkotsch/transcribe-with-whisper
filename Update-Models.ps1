# ========================================
# Update-Models - sync Ollama models to the VRAM tier
# ========================================
# Reads backend/models.config.json (the single source of truth), detects this
# machine's GPU VRAM, picks the matching tier, and `ollama pull`s the text + VLM
# models it needs. Whisper sizes are NOT pulled here - openai-whisper downloads
# those automatically on first use.
#
# Usage:
#   .\Update-Models.ps1                 # pull the models for this machine's tier
#   .\Update-Models.ps1 -VramOverrideGB 24   # force a tier (e.g. preview the 4090 set)
#   .\Update-Models.ps1 -Prune          # also remove Ollama models not used by ANY tier
#   .\Update-Models.ps1 -WhatIf         # show what would happen, change nothing
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [double]$VramOverrideGB,
    [switch]$Prune
)

$ErrorActionPreference = "Stop"
$configPath = Join-Path $PSScriptRoot "backend\models.config.json"

if (-not (Test-Path $configPath)) {
    Write-Host "ERROR: Config not found: $configPath" -ForegroundColor Red
    exit 1
}

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: 'ollama' not found on PATH. Install Ollama first." -ForegroundColor Red
    exit 1
}

# --- Detect VRAM (override wins, else nvidia-smi, else 0 = CPU tier) ---
function Get-GpuVramGB {
    if ($VramOverrideGB -gt 0) { return $VramOverrideGB }
    try {
        $raw = & nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>$null
        if ($LASTEXITCODE -eq 0 -and $raw) {
            return [math]::Round([double]($raw | Select-Object -First 1) / 1024, 1)
        }
    }
    catch {}
    return 0
}

$vram = Get-GpuVramGB
Write-Host "Detected VRAM: $(if ($vram -gt 0) { "$vram GB" } else { 'none (CPU tier)' })" -ForegroundColor Cyan

# --- Load config and pick the tier (highest min_vram_gb that fits) ---
$config = Get-Content $configPath -Raw | ConvertFrom-Json
$tiers = $config.tiers | Sort-Object -Property min_vram_gb -Descending
$tier = $tiers | Where-Object { $vram -ge $_.min_vram_gb } | Select-Object -First 1

if (-not $tier) {
    Write-Host "ERROR: No matching tier in config." -ForegroundColor Red
    exit 1
}

Write-Host "Selected tier: $($tier.name)" -ForegroundColor Green
Write-Host "  Whisper (auto-downloaded): $($tier.whisper)" -ForegroundColor Gray
Write-Host "  Text LLM (Ollama):         $($tier.text)" -ForegroundColor Gray
Write-Host "  Vision VLM (Ollama):       $($tier.vlm)" -ForegroundColor Gray

# --- Pull the Ollama models this tier needs ---
$needed = @($tier.text, $tier.vlm) | Select-Object -Unique
foreach ($model in $needed) {
    if ($PSCmdlet.ShouldProcess($model, "ollama pull")) {
        Write-Host "`nPulling $model ..." -ForegroundColor Cyan
        & ollama pull $model
    }
}

# --- Optional: prune Ollama models not referenced by ANY tier in the config ---
if ($Prune) {
    $keep = @()
    foreach ($t in $config.tiers) { $keep += $t.text; $keep += $t.vlm }
    $keep = $keep | Select-Object -Unique

    $installed = (& ollama list) | Select-Object -Skip 1 | ForEach-Object {
        ($_ -split '\s+')[0]
    } | Where-Object { $_ }

    $stale = $installed | Where-Object { $keep -notcontains $_ }
    if (-not $stale) {
        Write-Host "`nPrune: nothing to remove (all installed models are in the config)." -ForegroundColor Green
    }
    foreach ($model in $stale) {
        if ($PSCmdlet.ShouldProcess($model, "ollama rm")) {
            Write-Host "Removing stale model: $model" -ForegroundColor Yellow
            & ollama rm $model
        }
    }
}

Write-Host "`nDone. Models are in sync with the '$($tier.name)' tier." -ForegroundColor Cyan
