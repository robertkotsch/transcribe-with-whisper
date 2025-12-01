<#
.SYNOPSIS
  AI Media Intelligence Pipeline

.PARAMETER SourceFolder
  Path to folder containing video files

.PARAMETER SkipExisting
  Skip processing if output files exist

.PARAMETER OnlyTranscribe
  Only run Whisper transcription

.PARAMETER OnlyCorrect
  Only run grammar correction

.PARAMETER OnlySubtitles
  Only format subtitles

.PARAMETER OnlyAudit
  Only run content audit

.PARAMETER OnlyQA
  Only generate questions and answers

.PARAMETER OnlyInsights
  Only compile insight report

.PARAMETER HighQualityQuestions
  Enable two-stage question validation (slower, better quality)

.PARAMETER MarkdownOutput
  Generate .md files instead of .txt for Audit, QA, and Insights

.EXAMPLE
  .\Transcribe-Folder.ps1 "C:\Media"
  .\Transcribe-Folder.ps1 "C:\Media" -SkipExisting
  .\Transcribe-Folder.ps1 "C:\Media" -OnlyQA -HighQualityQuestions -MarkdownOutput
#>

param(
  [Parameter(Mandatory = $true)]
  [string]$SourceFolder,
  [switch]$SkipExisting,
  [switch]$OnlyTranscribe,
  [switch]$OnlyCorrect,
  [switch]$OnlySubtitles,
  [switch]$OnlyAudit,
  [switch]$OnlyQA,
  [switch]$OnlyInsights,
  [switch]$HighQualityQuestions,
  [switch]$MarkdownOutput
)

$ModelMap = @{
  "German"  = @{
    "Correction" = "qwen2"
    "Refinement" = "mistral"
    "Subtitles"  = "mistral"
    "Audit"      = "mistral"
    "Questions"  = "mistral"
    "Answers"    = "mistral"
    "Summary"    = "mistral"
  }
  "English" = @{
    "Correction" = "llama3"
    "Refinement" = "mistral"
    "Subtitles"  = "mistral"
    "Audit"      = "mistral"
    "Questions"  = "mistral"
    "Answers"    = "mistral"
    "Summary"    = "mistral"
  }
}

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$StagesSelected = $OnlyTranscribe -or $OnlyCorrect -or $OnlySubtitles -or $OnlyAudit -or $OnlyQA -or $OnlyInsights
$ShouldTranscribe = (-not $StagesSelected) -or $OnlyTranscribe
$ShouldCorrect = (-not $StagesSelected) -or $OnlyCorrect
$ShouldSubtitles = (-not $StagesSelected) -or $OnlySubtitles
$ShouldAudit = (-not $StagesSelected) -or $OnlyAudit
$ShouldQA = (-not $StagesSelected) -or $OnlyQA
$ShouldInsights = (-not $StagesSelected) -or $OnlyInsights

Write-Host "=== Pipeline Configuration ===" -ForegroundColor Cyan
Write-Host "Transcribe:  $ShouldTranscribe"
Write-Host "Correct:     $ShouldCorrect"
Write-Host "Subtitles:   $ShouldSubtitles"
Write-Host "Audit:       $ShouldAudit"
Write-Host "QA:          $ShouldQA"
Write-Host "Insights:    $ShouldInsights"
Write-Host "Quality:     $(if ($HighQualityQuestions) {'HIGH'} else {'STANDARD'})"
Write-Host "Format:      $(if ($MarkdownOutput) {'MARKDOWN'} else {'TEXT'})"
Write-Host "============================" -ForegroundColor Cyan
Write-Host ""

function Invoke-TextCorrection($inputPath, $lang, $suffix, $CorrectionModel, $RefinementModel) {
  if (-not (Test-Path $inputPath)) { return }

  $base = [System.IO.Path]::GetFileNameWithoutExtension($inputPath)
  $dir = [System.IO.Path]::GetDirectoryName($inputPath)
  $ext = [System.IO.Path]::GetExtension($inputPath)
  
  $cleanPath = Join-Path $dir ($base + $suffix + $ext)
  $cleanPathStr = [string]$cleanPath
  $refinedPath = $cleanPathStr.Replace('_clean', '_refined')

  if ($SkipExisting -and (Test-Path $refinedPath)) {
    Write-Host "Skipping correction for $base (already refined)"
    return
  }

  # Build explicit language instruction
  $langInstruction = if ($lang -eq "German") { "auf Deutsch (in German language)" } else { "in English" }

  Write-Host "Correcting $base with $CorrectionModel (keeping in $lang)..."
  $Prompt = "Correct ONLY grammar, spelling, and punctuation errors in this $lang text. DO NOT translate. DO NOT change the language. Your output must be $langInstruction. Keep all meaning and formatting intact."
  $Text = Get-Content $inputPath -Raw -Encoding UTF8
  $Corrected = ("$Prompt`n`n$Text") | & ollama run $CorrectionModel

  # Filter out Ollama status messages
  if ($Corrected) {
    $Corrected = $Corrected | Where-Object {
      $_ -notmatch '^(pulling|verifying|writing|success|total duration|load duration|prompt eval|eval rate)'
    }
  }

  if (-not $Corrected) {
    Write-Host "WARNING: No output from correction step" -ForegroundColor Yellow
    return
  }

  $Corrected | Out-File -FilePath $cleanPathStr -Encoding UTF8

  Write-Host "Refining idiomatic phrasing with $RefinementModel..."
  $PromptRefine = "Rewrite this $lang transcript into natural, idiomatic, grammatically correct $lang language. DO NOT translate to any other language. Your output MUST be $langInstruction. Keep all meaning intact."
  $Refined = ("$PromptRefine`n`n$Corrected") | & ollama run $RefinementModel

  # Filter out Ollama status messages
  if ($Refined) {
    $Refined = $Refined | Where-Object {
      $_ -notmatch '^(pulling|verifying|writing|success|total duration|load duration|prompt eval|eval rate)'
    }
  }

  if (-not $Refined) {
    Write-Host "WARNING: No output from refinement step" -ForegroundColor Yellow
    return
  }

  $Refined | Out-File -FilePath $refinedPath -Encoding UTF8
}

function Invoke-NetflixSubtitles($inputSrt, $model) {
  if (-not (Test-Path $inputSrt)) { return }
  $base = [System.IO.Path]::GetFileNameWithoutExtension($inputSrt)
  $dir = [System.IO.Path]::GetDirectoryName($inputSrt)
  $out = Join-Path $dir ($base + "_netflix.srt")

  if ($SkipExisting -and (Test-Path $out)) {
    Write-Host "Skipping Netflix formatting for $base"
    return
  }

  Write-Host "Netflix-formatting $base..."
  $Prompt = "Reformat to Netflix style: max 42 chars/line, 2 lines, 1-7s duration. Return valid .srt only."
  $Content = Get-Content $inputSrt -Raw -Encoding UTF8
  ("$Prompt`n`n$Content") | & ollama run $model | Out-File -FilePath $out -Encoding UTF8
}

function Invoke-ContentAudit($inputTxt, $lang, $model, $useMarkdown) {
  if (-not (Test-Path $inputTxt)) { return }
  $base = [System.IO.Path]::GetFileNameWithoutExtension($inputTxt)
  $dir = [System.IO.Path]::GetDirectoryName($inputTxt)
  $ext = if ($useMarkdown) { ".md" } else { ".txt" }
  $out = Join-Path $dir ($base + "_audit" + $ext)

  if ($SkipExisting -and (Test-Path $out)) {
    Write-Host "Skipping audit for $base"
    return
  }

  Write-Host "Auditing $base..."

  if ($useMarkdown) {
    $Prompt = "Analyze this $lang transcript and return a Markdown report with ## headings, **bold** for emphasis, bullet points. Cover: clarity, information level, tone, bias."
  }
  else {
    $Prompt = "Analyze this $lang transcript for: clarity, information level, tone, bias. Return structured report in $lang."
  }

  $Text = Get-Content $inputTxt -Raw -Encoding UTF8
  Write-Host "  Text length: $($Text.Length) chars, Model: $model"

  # Capture output without stderr contamination
  $ErrorActionPreference = 'Continue'
  $Result = ("$Prompt`n`n$Text") | & ollama run $model

  if ($Result) {
    # Filter out Ollama status/error lines that might have leaked through
    $CleanResult = $Result | Where-Object {
      $_ -notmatch '^(pulling|verifying|writing|success|total duration|load duration|prompt eval|eval rate)'
    }

    if ($CleanResult) {
      $CleanResult | Out-File -FilePath $out -Encoding UTF8
      Write-Host "  Output generated successfully"
    }
    else {
      Write-Host "WARNING: Output contained only Ollama status messages" -ForegroundColor Yellow
    }
  }
  else {
    Write-Host "WARNING: No output from Ollama for audit (model: $model)" -ForegroundColor Yellow
  }
}

function Invoke-QuestionGeneration($inputTxt, $lang, $model, $highQuality, $useMarkdown) {
  if (-not (Test-Path $inputTxt)) { return }
  $base = [System.IO.Path]::GetFileNameWithoutExtension($inputTxt)
  $dir = [System.IO.Path]::GetDirectoryName($inputTxt)
  $ext = if ($useMarkdown) { ".md" } else { ".txt" }
  $out = Join-Path $dir ($base + "_questions" + $ext)

  if ($SkipExisting -and (Test-Path $out)) {
    Write-Host "Skipping questions for $base"
    return
  }

  $Text = Get-Content $inputTxt -Raw -Encoding UTF8
  
  $basePrompt = @"
Analyze this $lang transcript and generate questions NOT answered in the content.
ONLY include questions where the answer is NOT explicitly stated.
Focus on: information gaps, logical next steps, implied assumptions, practical applications, edge cases.
EXCLUDE questions where the answer is directly stated or can be inferred.
Return 10-20 numbered questions in $lang.
"@

  if ($highQuality) {
    Write-Host "Generating questions for $base (HIGH QUALITY)..."
    Write-Host "  Stage 1/2: Generating candidates..."
    $Candidates = ("$basePrompt Generate 20-30 candidates.`n`n$Text") | & ollama run $model

    Write-Host "  Stage 2/2: Validating..."
    $ValidatePrompt = "Review these questions against the transcript. Remove any that ARE answered. Return 10-20 best questions in $lang.`n`n--- TRANSCRIPT ---`n$Text`n`n--- QUESTIONS ---`n$Candidates"
    $Final = $ValidatePrompt | & ollama run $model
  }
  else {
    Write-Host "Generating questions for $base..."
    $Final = ("$basePrompt`n`n$Text") | & ollama run $model
  }

  if (-not $Final) {
    Write-Host "WARNING: No output from Ollama for questions" -ForegroundColor Yellow
    return
  }

  # Filter out Ollama status messages
  $Final = $Final | Where-Object {
    $_ -notmatch '^(pulling|verifying|writing|success|total duration|load duration|prompt eval|eval rate)'
  }

  if (-not $Final) {
    Write-Host "WARNING: Output contained only Ollama status messages" -ForegroundColor Yellow
    return
  }

  if ($useMarkdown) {
    $output = "# Open Questions`n`nGenerated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')`n`n$Final"
    $output | Out-File -FilePath $out -Encoding UTF8
  }
  else {
    $Final | Out-File -FilePath $out -Encoding UTF8
  }
}

function Invoke-AnswerGeneration($inputTxt, $questionsPath, $lang, $model, $useMarkdown) {
  if (-not (Test-Path $inputTxt)) {
    Write-Host "WARNING: Input transcript not found: $inputTxt" -ForegroundColor Yellow
    return
  }
  if (-not (Test-Path $questionsPath)) {
    Write-Host "WARNING: Questions file not found: $questionsPath" -ForegroundColor Yellow
    return
  }

  $base = [System.IO.Path]::GetFileNameWithoutExtension($inputTxt)
  $dir = [System.IO.Path]::GetDirectoryName($inputTxt)
  $ext = if ($useMarkdown) { ".md" } else { ".txt" }
  $out = Join-Path $dir ($base + "_answers" + $ext)

  if ($SkipExisting -and (Test-Path $out)) {
    Write-Host "Skipping answers for $base"
    return
  }

  Write-Host "Answering questions for $base..."
  Write-Host "  Questions from: $questionsPath"
  $Questions = Get-Content $questionsPath -Raw -Encoding UTF8
  $Transcript = Get-Content $inputTxt -Raw -Encoding UTF8

  $Prompt = "Answer these questions based ONLY on the transcript. If unclear, propose hypotheses. Format: Q1: [question] A1: [answer]`n`n--- TRANSCRIPT ---`n$Transcript`n`n--- QUESTIONS ---`n$Questions"
  $Answers = $Prompt | & ollama run $model

  if (-not $Answers) {
    Write-Host "WARNING: No output from Ollama for answers" -ForegroundColor Yellow
    return
  }

  # Filter out Ollama status messages
  $Answers = $Answers | Where-Object {
    $_ -notmatch '^(pulling|verifying|writing|success|total duration|load duration|prompt eval|eval rate)'
  }

  if (-not $Answers) {
    Write-Host "WARNING: Output contained only Ollama status messages" -ForegroundColor Yellow
    return
  }

  if ($useMarkdown) {
    $output = "# Answers`n`nGenerated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')`n`n$Answers"
    $output | Out-File -FilePath $out -Encoding UTF8
  }
  else {
    $Answers | Out-File -FilePath $out -Encoding UTF8
  }
}

function Invoke-Summarize($inputTxt, $lang, $model) {
  if (-not (Test-Path $inputTxt)) { return }
  $base = [System.IO.Path]::GetFileNameWithoutExtension($inputTxt)
  $dir = [System.IO.Path]::GetDirectoryName($inputTxt)
  $out = Join-Path $dir ($base + "_summary.txt")

  if ($SkipExisting -and (Test-Path $out)) {
    Write-Host "Skipping summary for $base"
    return
  }

  Write-Host "Summarizing $base..."
  $Text = Get-Content $inputTxt -Raw -Encoding UTF8
  $Summary = ("Summarize this $lang transcript into 5 bullet points.`n`n$Text") | & ollama run $model

  if (-not $Summary) {
    Write-Host "WARNING: No output from Ollama for summary" -ForegroundColor Yellow
    return
  }

  # Filter out Ollama status messages
  $Summary = $Summary | Where-Object {
    $_ -notmatch '^(pulling|verifying|writing|success|total duration|load duration|prompt eval|eval rate)'
  }

  if ($Summary) {
    $Summary | Out-File -FilePath $out -Encoding UTF8
  }
  else {
    Write-Host "WARNING: Output contained only Ollama status messages" -ForegroundColor Yellow
  }
}

function Invoke-InsightComposer($baseDir, $baseName, $useMarkdown) {
  $ext = if ($useMarkdown) { ".md" } else { ".txt" }
  $insight = Join-Path $baseDir ($baseName + "_insights" + $ext)

  if ($SkipExisting -and (Test-Path $insight)) {
    Write-Host "Skipping insight composition for $baseName"
    return
  }

  Write-Host "Creating Insight Report for $baseName..."

  # Files are generated from refined transcript, so use _refined prefix
  $summaryFile = Join-Path $baseDir ($baseName + "_refined_summary.txt")
  $auditFile = Join-Path $baseDir ($baseName + "_refined_audit" + $ext)
  $questionsFile = Join-Path $baseDir ($baseName + "_refined_questions" + $ext)
  $answersFile = Join-Path $baseDir ($baseName + "_refined_answers" + $ext)

  # Fallback to .txt if .md not found
  if (-not (Test-Path $auditFile)) { $auditFile = Join-Path $baseDir ($baseName + "_refined_audit.txt") }
  if (-not (Test-Path $questionsFile)) { $questionsFile = Join-Path $baseDir ($baseName + "_refined_questions.txt") }
  if (-not (Test-Path $answersFile)) { $answersFile = Join-Path $baseDir ($baseName + "_refined_answers.txt") }

  Write-Host "Looking for files:"
  Write-Host "  Summary: $summaryFile (exists: $(Test-Path $summaryFile))"
  Write-Host "  Audit: $auditFile (exists: $(Test-Path $auditFile))"
  Write-Host "  Questions: $questionsFile (exists: $(Test-Path $questionsFile))"
  Write-Host "  Answers: $answersFile (exists: $(Test-Path $answersFile))"

  if ($useMarkdown) {
    $r = @("# AI Insight Report", "", "**Generated:** $(Get-Date -Format 'yyyy-MM-dd HH:mm')", "", "---", "", "## Summary", "")
    if (Test-Path $summaryFile) { $r += Get-Content $summaryFile -Raw -Encoding UTF8 } else { $r += "> Not available" }
    $r += "", "---", "", "## Content Audit", ""
    if (Test-Path $auditFile) { $r += Get-Content $auditFile -Raw -Encoding UTF8 } else { $r += "> Not available" }
    $r += "", "---", "", "## Open Questions", ""
    if (Test-Path $questionsFile) { $r += Get-Content $questionsFile -Raw -Encoding UTF8 } else { $r += "> Not available" }
    $r += "", "---", "", "## Answers", ""
    if (Test-Path $answersFile) { $r += Get-Content $answersFile -Raw -Encoding UTF8 } else { $r += "> Not available" }
    $r += "", "---", "", "*End of Report*"
  }
  else {
    $r = @("=============================", " AI INSIGHT REPORT", "=============================", "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')", "", "## Summary", "")
    if (Test-Path $summaryFile) { $r += Get-Content $summaryFile -Raw -Encoding UTF8 } else { $r += "(not available)" }
    $r += "", "## Audit", ""
    if (Test-Path $auditFile) { $r += Get-Content $auditFile -Raw -Encoding UTF8 } else { $r += "(not available)" }
    $r += "", "## Questions", ""
    if (Test-Path $questionsFile) { $r += Get-Content $questionsFile -Raw -Encoding UTF8 } else { $r += "(not available)" }
    $r += "", "## Answers", ""
    if (Test-Path $answersFile) { $r += Get-Content $answersFile -Raw -Encoding UTF8 } else { $r += "(not available)" }
    $r += "", "=============================", " END OF REPORT", "============================="
  }

  $r | Out-File -FilePath $insight -Encoding UTF8
}

if ($ShouldTranscribe) {
  if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: ffmpeg not found" -ForegroundColor Red
    exit 1
  }
  if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Python not found" -ForegroundColor Red
    exit 1
  }
}

# Validate Ollama is available for AI processing stages
if ($ShouldCorrect -or $ShouldSubtitles -or $ShouldAudit -or $ShouldQA -or $ShouldInsights) {
  if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Ollama not found. Install from https://ollama.ai" -ForegroundColor Red
    exit 1
  }
  # Test if Ollama is running
  try {
    $null = ollama list 2>&1
  }
  catch {
    Write-Host "ERROR: Ollama is not running. Start it with 'ollama serve'" -ForegroundColor Red
    exit 1
  }
}

$videos = Get-ChildItem -Path $SourceFolder -File -Recurse | Where-Object { $_.Extension -match '\.mp4$|\.mov$|\.avi$|\.mkv$|\.wmv$|\.flv$|\.webm$|\.m4v$' }

if (-not $videos) { 
  Write-Host "No video files found" -ForegroundColor Yellow
  exit 0 
}

Write-Host "Found $($videos.Count) video file(s)`n" -ForegroundColor Green

foreach ($f in $videos) {
  Write-Host "Processing: $($f.Name)" -ForegroundColor Cyan
  $name = [System.IO.Path]::GetFileNameWithoutExtension($f.Name)
  $dir = [System.IO.Path]::GetDirectoryName($f.FullName)
  $out = Join-Path $dir $name
  if (-not (Test-Path $out)) { New-Item -ItemType Directory -Path $out | Out-Null }

  $wav = Join-Path $out ($name + ".wav")
  $txt = Join-Path $out ($name + ".txt")
  $srt = Join-Path $out ($name + ".srt")
  $json = Join-Path $out ($name + ".json")

  if ($ShouldTranscribe) {
    if ($SkipExisting -and (Test-Path $txt) -and (Test-Path $srt)) {
      Write-Host "Skipping transcription (exists)"
    }
    else {
      Write-Host "Extracting audio..."
      ffmpeg -y -i $f.FullName -vn -acodec pcm_s16le -ar 16000 -ac 1 $wav 2>&1 | Out-Null
      Write-Host "Running Whisper..."
      python -m whisper $wav --model small --device cuda --output_format all --output_dir "$out"
    }
  }

  $Language = "English"
  if (Test-Path $json) {
    try {
      $j = Get-Content $json -Raw | ConvertFrom-Json
      if ($j.language -eq "de") { $Language = "German" }
    }
    catch {}
  }
  Write-Host "Language: $Language"

  if ($ShouldCorrect -and (Test-Path $txt)) {
    Invoke-TextCorrection $txt $Language "_clean" $ModelMap[$Language]["Correction"] $ModelMap[$Language]["Refinement"]
  }

  if ($ShouldSubtitles -and (Test-Path $srt)) {
    Invoke-NetflixSubtitles $srt $ModelMap[$Language]["Subtitles"]
  }

  $txtStr = [string]$txt
  $refinedTxt = $txtStr.Replace('.txt', '_refined.txt')

  if ($ShouldAudit -and (Test-Path $refinedTxt)) {
    Invoke-ContentAudit $refinedTxt $Language $ModelMap[$Language]["Audit"] $MarkdownOutput
  }

  if ($ShouldQA -and (Test-Path $refinedTxt)) {
    Invoke-QuestionGeneration $refinedTxt $Language $ModelMap[$Language]["Questions"] $HighQualityQuestions $MarkdownOutput

    # Build correct questions file path matching what Invoke-QuestionGeneration creates
    $base = [System.IO.Path]::GetFileNameWithoutExtension($refinedTxt)
    $dir = [System.IO.Path]::GetDirectoryName($refinedTxt)
    $qExt = if ($MarkdownOutput) { ".md" } else { ".txt" }
    $qFile = Join-Path $dir ($base + "_questions" + $qExt)

    # Wait for questions file to be fully written (avoid race condition)
    $maxWait = 20
    $waited = 0
    while (-not (Test-Path $qFile) -and ($waited -lt $maxWait)) {
      Start-Sleep -Milliseconds 500
      $waited++
    }

    if (Test-Path $qFile) {
      Invoke-AnswerGeneration $refinedTxt $qFile $Language $ModelMap[$Language]["Answers"] $MarkdownOutput
    }
    else {
      Write-Host "WARNING: Questions file was not created, skipping answers" -ForegroundColor Yellow
    }
  }

  if ($ShouldInsights) {
    # First, ensure we have a refined transcript
    if (Test-Path $refinedTxt) {
      Write-Host "Using existing refined transcript..."
    }
    elseif (Test-Path $txt) {
      Write-Host "No refined transcript found - creating from raw transcript..."
      Invoke-TextCorrection $txt $Language "_clean" $ModelMap[$Language]["Correction"] $ModelMap[$Language]["Refinement"]
    }
    else {
      Write-Host "WARNING: No transcript found for insights; run -OnlyTranscribe first." -ForegroundColor Yellow
      continue
    }
    
    # Now generate missing analysis components
    if (Test-Path $refinedTxt) {
      $ext = if ($MarkdownOutput) { ".md" } else { ".txt" }
      
      # Build paths with correct extensions
      $base = [System.IO.Path]::GetFileNameWithoutExtension($refinedTxt)
      $dir = [System.IO.Path]::GetDirectoryName($refinedTxt)
      $auditFile = Join-Path $dir ($base + "_audit" + $ext)
      $questionsFile = Join-Path $dir ($base + "_questions" + $ext)
      $answersFile = Join-Path $dir ($base + "_answers" + $ext)
      
      Write-Host "Checking for: $auditFile"
      Write-Host "Checking for: $questionsFile"
      Write-Host "Checking for: $answersFile"
      
      if (-not (Test-Path $auditFile)) {
        Write-Host "Generating missing audit..."
        Invoke-ContentAudit $refinedTxt $Language $ModelMap[$Language]["Audit"] $MarkdownOutput
      }
      else {
        Write-Host "Audit exists: $auditFile"
      }
      
      if (-not (Test-Path $questionsFile)) {
        Write-Host "Generating missing questions..."
        Invoke-QuestionGeneration $refinedTxt $Language $ModelMap[$Language]["Questions"] $HighQualityQuestions $MarkdownOutput
      }
      else {
        Write-Host "Questions exist: $questionsFile"
      }
      
      if (-not (Test-Path $answersFile)) {
        Write-Host "Generating missing answers..."
        Invoke-AnswerGeneration $refinedTxt $questionsFile $Language $ModelMap[$Language]["Answers"] $MarkdownOutput
      }
      else {
        Write-Host "Answers exist: $answersFile"
      }
      
      Invoke-Summarize $refinedTxt $Language $ModelMap[$Language]["Summary"]
    }
    
    Invoke-InsightComposer $out $name $MarkdownOutput
  }

  Write-Host "Finished $($f.Name)`n" -ForegroundColor Green
}

Write-Host "All stages completed!`n" -ForegroundColor Green