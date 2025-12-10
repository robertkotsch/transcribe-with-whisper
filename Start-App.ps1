Write-Host "Starting Media Intelligence Station..." -ForegroundColor Cyan

# Check dependencies
if (-not (Test-Path "backend\services\pipeline.py")) {
    Write-Host "Error: Backend files missing." -ForegroundColor Red
    exit
}

# Check/Create Virtual Environment
$venvPath = ".venv"
$pythonPath = "python" # Default fallback
$pipPath = "pip"

if (-not (Test-Path $venvPath)) {
    Write-Host "Creating local virtual environment (.venv)..." -ForegroundColor Cyan
    Start-Process -FilePath "python" -ArgumentList "-m venv $venvPath" -Wait -NoNewWindow
}

if (Test-Path "$venvPath\Scripts\python.exe") {
    $pythonPath = ".\$venvPath\Scripts\python.exe"
    $pipPath = ".\$venvPath\Scripts\pip.exe"
    Write-Host "Using virtual environment: $venvPath" -ForegroundColor Cyan
}
else {
    Write-Host "Warning: Virtual environment not found. Using global Python." -ForegroundColor Yellow
}

# Install Backend Dependencies
if (Test-Path "backend\requirements.txt") {
    Write-Host "Checking backend dependencies..."

    # Check for CUDA availability
    $cudaAvailable = & $pythonPath -c "import torch; print(torch.cuda.is_available())" 2>$null
    
    if ($cudaAvailable -ne "True") {
        Write-Host "CUDA not detected. Installing PyTorch with CUDA support..." -ForegroundColor Yellow
        & $pipPath uninstall -y torch torchvision torchaudio
        & $pipPath install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
    }

    & $pipPath install -r backend\requirements.txt | Out-Null
}

# Start Backend
Write-Host "Launching Backend (FastAPI)..." -ForegroundColor Green
$backendProcess = Start-Process -FilePath $pythonPath -ArgumentList "-m uvicorn backend.main:app --reload --port 8000" -PassThru -NoNewWindow
Start-Sleep -Seconds 2

# Start Frontend
Write-Host "Launching Frontend (Vite)..." -ForegroundColor Green
Set-Location frontend
# Ensure dependencies are installed (first run only)
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing frontend dependencies..."
    pnpm install
}
$frontendProcess = Start-Process -FilePath "pnpm" -ArgumentList "run dev" -PassThru -NoNewWindow

Write-Host "All systems go!" -ForegroundColor Cyan
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
    Write-Host "Services stopped." -ForegroundColor Green
}
