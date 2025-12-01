<#
.SYNOPSIS
    Batch-transcribes all MP4/MOV videos in a given folder.
    Extracts audio, runs Whisper GPU transcription, and saves .txt + .srt outputs
    in subfolders named after each video, with optional summarization and grammar correction.

.EXAMPLE
    .\Transcribe-Folder.ps1 "C:\Users\User\Downloads\Audio"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$SourceFolder
)

# --- prerequisite checks ---
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "ffmpeg not found. Install it and add to PATH." -ForegroundColor Yellow
    exit 1
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found. Install Python 3.10+ and add to PATH." -ForegroundColor Yellow
    exit 1
}

# --- check whisper installation ---
Write-Host "Checking Whisper installation..."
$pkg = python -m pip show whisper 2>$null
if (-not $pkg) {
    python -m pip install git+https://github.com/openai/whisper.git
}
Write-Host "Whisper available."

# --- check torch / CUDA ---
Write-Host "Checking CUDA..."
try {
    $torch = & python -c 'import torch; print(torch.cuda.is_available())'
    if ($torch -notmatch "True") {
        python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
    }
} catch {
    python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
}

# --- process all video files ---
$videoFiles = Get-ChildItem -Path $SourceFolder -File -Recurse |
    Where-Object { $_.Extension -match '\.mp4$|\.mov$' }

if (-not $videoFiles) {
    Write-Host "No .mp4 or .mov files found in $SourceFolder"
    exit 0
}

foreach ($file in $videoFiles) {
    Write-Host ""
    Write-Host ("Processing file: " + $file.Name)

    $BaseName = [System.IO.Path]::GetFileNameWithoutExtension($file.Name)
    $FileDir  = [System.IO.Path]::GetDirectoryName($file.FullName)
    $OutputDir = Join-Path $FileDir $BaseName

    if (-not (Test-Path $OutputDir)) {
        New-Item -ItemType Directory -Path $OutputDir | Out-Null
    }

    $WavFile = Join-Path $OutputDir ($BaseName + ".wav")
    $TxtFile = Join-Path $OutputDir ($BaseName + ".txt")
    $SrtFile = Join-Path $OutputDir ($BaseName + ".srt")

    # --- extract audio ---
    Write-Host "Extracting audio..."
    ffmpeg -y -i $file.FullName -vn -acodec pcm_s16le -ar 16000 -ac 1 $WavFile | Out-Null

    # --- run whisper ---
    Write-Host "Transcribing audio with Whisper on GPU..."
    python -m whisper $WavFile --model small --device cuda --output_format all --output_dir "$OutputDir"

    # --- optional summarization ---
    $SummaryFile = Join-Path $OutputDir ($BaseName + "_summary.txt")
    if (Test-Path $TxtFile) {
        Write-Host "Generating summary with Ollama..."
        $Prompt = "Summarize this transcript in 5 bullet points:"
        $Transcript = Get-Content $TxtFile -Raw
        $Command = @"
echo "$Prompt

$Transcript" | ollama run llama3
"@
        $Summary = Invoke-Expression $Command
        $Summary | Out-File -FilePath $SummaryFile -Encoding UTF8
    }

    # --- optional grammar & spell check ---
    $CleanFile = Join-Path $OutputDir ($BaseName + "_clean.txt")
    if (Test-Path $TxtFile) {
        Write-Host "Running grammar & spell check with Ollama..."
        $Prompt = "Please correct grammar, spelling, and punctuation in the following transcript. Keep the original meaning and formatting as much as possible:"
        $Transcript = Get-Content $TxtFile -Raw
        $Command = @"
echo "$Prompt

$Transcript" | ollama run llama3
"@
        $CleanedText = Invoke-Expression $Command
        $CleanedText | Out-File -FilePath $CleanFile -Encoding UTF8
    }

    Write-Host ("Done: " + $file.Name)
    Write-Host ("   Text: " + $TxtFile)
    Write-Host ("   Subtitles: " + $SrtFile)
}

Write-Host ""
Write-Host "All video files processed successfully!"
Write-Host ""
