# ========================================
# Media Intelligence Station - Start Script
# ========================================

Write-Host "Starting Media Intelligence Station..." -ForegroundColor Cyan

# Force UTF-8 so libraries that print Unicode (e.g. EasyOCR progress bars) don't
# crash on the Windows cp1252 console codec.
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# Check dependencies
if (-not (Test-Path "backend\services\pipeline.py")) {
    Write-Host "Error: Backend files missing." -ForegroundColor Red
    exit
}

# ========================================
# VLM Note: OCR disabled
# ========================================
# PaddleOCR container removed due to serving setup issues.
# VLM (Ollama llava) provides rich visual descriptions including text content.
# To use VLM: ensure 'ollama pull llava' has been run.

# ========================================
# Python Virtual Environment
# ========================================
$venvPath = ".venv"
$pythonPath = "python"

# Resolve Python 3.11 (required — many deps have no wheels for newer versions)
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
Write-Host ("Using " + (& $basePython[0] $basePython[1..99] --version 2>&1)) -ForegroundColor Cyan

# Create or repair the venv if missing or pointing to a different user's Python
$needsVenv = $false
if (-not (Test-Path "$venvPath\Scripts\python.exe")) {
    $needsVenv = $true
} else {
    $pythonPath = ".\$venvPath\Scripts\python.exe"
    $pyTest = & $pythonPath -c "print('ok')" 2>&1
    if ($pyTest -notcontains "ok") {
        Write-Host "Venv broken (created by a different user). Recreating..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $venvPath
        $needsVenv = $true
    }
}

if ($needsVenv) {
    Write-Host "Creating virtual environment (.venv) with Python 3.11..." -ForegroundColor Cyan
    & $basePython[0] $basePython[1..99] -m venv $venvPath
    if (-not (Test-Path "$venvPath\Scripts\python.exe")) {
        Write-Host "Error: Failed to create virtual environment." -ForegroundColor Red
        exit 1
    }
}

$pythonPath = ".\$venvPath\Scripts\python.exe"
Write-Host "Using virtual environment: $venvPath" -ForegroundColor Cyan

# Install Backend Dependencies
if (Test-Path "backend\requirements.txt") {
    Write-Host "Checking backend dependencies..."

    # Install requirements FIRST. A transitive dep (e.g. nemo) can pull a CPU-only
    # torch from PyPI, so the CUDA check/repair must run AFTER this, not before.
    & $pythonPath -m pip install -r backend\requirements.txt

    # Ensure a CUDA-enabled PyTorch build (driver supports CUDA 13.x -> cu130).
    $cudaAvailable = & $pythonPath -c "import torch; print(torch.cuda.is_available())" 2>$null
    if ($cudaAvailable -ne "True") {
        Write-Host "CUDA not active in torch. Installing CUDA build (cu130)..." -ForegroundColor Yellow
        & $pythonPath -m pip uninstall -y torch torchvision torchaudio
        & $pythonPath -m pip install torch==2.12.1 torchvision==0.27.1 --index-url https://download.pytorch.org/whl/cu130
    }
    else {
        Write-Host "CUDA active in torch." -ForegroundColor Green
    }
}

# ========================================
# Start Services
# ========================================

# Start Backend
Write-Host "Launching Backend (FastAPI)..." -ForegroundColor Green
$backendProcess = Start-Process -FilePath $pythonPath -ArgumentList "-m uvicorn backend.main:app --reload --reload-dir backend --port 8000" -PassThru -NoNewWindow
Start-Sleep -Seconds 2

# Start Frontend
Write-Host "Launching Frontend (Vite)..." -ForegroundColor Green
Set-Location frontend

# Suppress interactive prompts in pnpm and other Node.js tools
$env:CI = "true"

# Resolve pnpm: prefer direct pnpm.cmd, fall back to corepack
if (Get-Command "pnpm.cmd" -ErrorAction SilentlyContinue) {
    $pnpmExe = "pnpm.cmd"
} elseif (Get-Command "corepack" -ErrorAction SilentlyContinue) {
    Write-Host "pnpm.cmd not in PATH, using corepack pnpm..." -ForegroundColor Yellow
    $pnpmExe = "corepack"
} else {
    Write-Host "Error: pnpm not found. Run: npm install -g pnpm" -ForegroundColor Red
    exit 1
}

# Always sync dependencies — fast no-op if up to date, repairs broken node_modules
Write-Host "Syncing frontend dependencies..."
if ($pnpmExe -eq "corepack") { & $pnpmExe pnpm install } else { & $pnpmExe install }

# Launch Vite: use pnpm.cmd if available, otherwise invoke vite.cmd directly from node_modules
if ($pnpmExe -eq "pnpm.cmd") {
    $frontendProcess = Start-Process -FilePath "pnpm.cmd" -ArgumentList "run dev" -PassThru -NoNewWindow
} else {
    $viteCmd = "node_modules\.bin\vite.cmd"
    if (-not (Test-Path $viteCmd)) {
        Write-Host "Error: vite not found in node_modules. pnpm install may have failed." -ForegroundColor Red
        exit 1
    }
    $frontendProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $viteCmd -PassThru -NoNewWindow
}

# Wait until Vite actually listens on :5173 (up to 20 s) before declaring success
$viteReady = $false
Write-Host "Waiting for frontend on :5173..." -ForegroundColor Gray
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    try {
        $tcp = [System.Net.Sockets.TcpClient]::new()
        $tcp.Connect('127.0.0.1', 5173)
        $tcp.Close()
        $viteReady = $true
        break
    } catch { }
}

if ($viteReady) {
    Write-Host "All systems go!" -ForegroundColor Cyan
} else {
    Write-Host "Warning: Frontend did not start on :5173 - check the Vite process." -ForegroundColor Yellow
}
Write-Host "OPEN BROWSER TO: http://localhost:5173" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop servers."

# Keep script running to allow cleanup
try {
    # Wait for either process to exit (or script interruption)
    Wait-Process -Id $backendProcess.Id, $frontendProcess.Id
}
catch {
    # If standard error occurs
    Write-Host "Error during execution: $_" -ForegroundColor Red
}
finally {
    # This block runs on exit, error, OR Ctrl+C
    Write-Host "`nStopping services..." -ForegroundColor Yellow
    Stop-Process -Id $backendProcess.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $frontendProcess.Id -ErrorAction SilentlyContinue
    # Note: We don't stop the PaddleOCR container - it can persist for next run
    Write-Host "Services stopped." -ForegroundColor Green
    Write-Host "Note: PaddleOCR container left running. Stop manually: podman stop paddleocr" -ForegroundColor Gray
}
