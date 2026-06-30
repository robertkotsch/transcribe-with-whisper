# ========================================
# Media Intelligence Station - Update Script
# ========================================
# Pulls latest code and syncs all dependencies.
# Bitdefender note: pip and pnpm handle their own downloads internally;
# this script never invokes Invoke-WebRequest or curl, which avoids
# the malware-downloader heuristic that triggers on PS1 URL fetches.

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:CI = "true"

Write-Host "Updating Media Intelligence Station..." -ForegroundColor Cyan

# ========================================
# Git pull
# ========================================
Write-Host "`n[1/3] Pulling latest code..." -ForegroundColor Cyan
git pull
if ($LASTEXITCODE -ne 0) {
    Write-Host "Warning: git pull failed (uncommitted changes or no remote?). Continuing with local code." -ForegroundColor Yellow
}

# ========================================
# Python 3.11 + venv
# ========================================
Write-Host "`n[2/3] Updating backend dependencies..." -ForegroundColor Cyan

$venvPath = ".venv"
$basePython = $null
foreach ($candidate in @(@("py", "-3.11"), @("python3.11"))) {
    try {
        $ver = & $candidate[0] $candidate[1..99] --version 2>&1
        if ($ver -match "Python 3\.11") { $basePython = $candidate; break }
    } catch {}
}
if (-not $basePython) {
    Write-Host "Error: Python 3.11 not found. Run: py install 3.11" -ForegroundColor Red
    exit 1
}

# Repair venv if it points to a different user's Python
$pythonPath = "python"
if (Test-Path "$venvPath\Scripts\python.exe") {
    $pythonPath = ".\$venvPath\Scripts\python.exe"
    $pyTest = & $pythonPath -c "print('ok')" 2>&1
    if ($pyTest -notcontains "ok") {
        Write-Host "Venv broken (created by a different user). Recreating..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $venvPath
    }
}

if (-not (Test-Path "$venvPath\Scripts\python.exe")) {
    Write-Host "Creating virtual environment with Python 3.11..." -ForegroundColor Yellow
    & $basePython[0] $basePython[1..99] -m venv $venvPath
}
$pythonPath = ".\$venvPath\Scripts\python.exe"

# Update Python packages
& $pythonPath -m pip install --upgrade pip | Out-Null
& $pythonPath -m pip install -r backend\requirements.txt

# Repair CUDA torch if needed (pip may have downgraded it to CPU-only)
$cudaAvailable = & $pythonPath -c "import torch; print(torch.cuda.is_available())" 2>$null
if ($cudaAvailable -ne "True") {
    Write-Host "CUDA not active in torch. Reinstalling CUDA build (cu130)..." -ForegroundColor Yellow
    & $pythonPath -m pip uninstall -y torch torchvision torchaudio
    & $pythonPath -m pip install torch==2.12.1 torchvision==0.27.1 --index-url https://download.pytorch.org/whl/cu130
} else {
    Write-Host "CUDA active in torch." -ForegroundColor Green
}

# ========================================
# Frontend (pnpm install with hoisted layout — avoids Bitdefender junction issues)
# ========================================
Write-Host "`n[3/3] Updating frontend dependencies..." -ForegroundColor Cyan
Set-Location frontend

if (Get-Command "pnpm.cmd" -ErrorAction SilentlyContinue) {
    $pnpmExe = "pnpm.cmd"
} elseif (Get-Command "corepack" -ErrorAction SilentlyContinue) {
    Write-Host "pnpm.cmd not in PATH, using corepack pnpm..." -ForegroundColor Yellow
    $pnpmExe = "corepack"
} else {
    Write-Host "Error: pnpm not found. Run: npm install -g pnpm" -ForegroundColor Red
    exit 1
}

if ($pnpmExe -eq "corepack") { & $pnpmExe pnpm install } else { & $pnpmExe install }

Set-Location ..

Write-Host "`nUpdate complete. Run Start-App.bat to launch." -ForegroundColor Green
