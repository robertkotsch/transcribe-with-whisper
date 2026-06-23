# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo contains

Two independent apps that share the same "transcribe + AI-analyze media" purpose:

1. **V2 web app (primary, actively developed)** — FastAPI backend (`backend/`) + React/Vite frontend (`frontend/`), launched with `Start-App.ps1`. Everything below refers to this unless stated otherwise.
2. **Legacy standalone** — `Transcribe-Folder.ps1`, a single PowerShell script using the `whisper-ctranslate2` CLI and the `ollama` CLI. Self-contained; documented in `README.md`. Not used by the web app.

> Note: `README.md` and `APP_DESCRIPTION.md` are partly out of date on model names (they predate the config-driven model selection). For current models, trust `backend/models.config.json`, not the docs.

This is a **Windows-first** project (PowerShell launcher, `nvidia-smi` VRAM detection). It runs 100% locally — Whisper, Ollama, and NeMo all run on the machine; no cloud calls.

## Commands

```powershell
# Run the whole app (creates .venv, installs deps, repairs CUDA torch, starts both servers)
.\Start-App.ps1                      # backend :8000, frontend :5173

# Backend only (from repo root, venv must exist)
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000

# Frontend only (uses pnpm, not npm)
cd frontend; pnpm install; pnpm run dev    # :5173
pnpm run lint                              # eslint
pnpm run build

# Python tests (stdlib unittest, NOT pytest)
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests
.\.venv\Scripts\python.exe backend/tests/test_ocr_correction.py    # single test file

# Model management (see "Model selection" below)
.\.venv\Scripts\python.exe backend/check_model_updates.py            # check registry for newer models
.\.venv\Scripts\python.exe backend/check_model_updates.py --current  # only this GPU's tier
.\Update-Models.ps1                  # pull this machine's tier models
.\Update-Models.ps1 -Prune -WhatIf   # preview pruning models no tier uses
```

External prerequisites (not pip-installable): **ffmpeg**, **Ollama** (running, with the tier's models pulled), **Node.js + pnpm**, and a CUDA GPU (optional; falls back to CPU).

## Architecture

### Request/job flow
`frontend/src/App.jsx` → `POST /analyze` (hardcoded base `http://127.0.0.1:8000`) → `backend/main.py` queues `process_media_task` as a FastAPI `BackgroundTask`. Jobs live in an **in-memory dict** (`jobs` in `main.py`) — no database; state is lost on restart. The frontend **polls** `GET /jobs` every 2s for progress and `GET /system` every 5s for the System Status header. Cancellation is cooperative: `POST /cancel/{id}` sets status `"cancelling"`, and the pipeline checks `cancel_callback()` between stages.

### The pipeline (`backend/services/pipeline.py`)
`MediaPipeline.process_full_pipeline()` is the orchestrator and the single most important file. It runs stages sequentially, calling a `progress_callback(stage, data)` after each so `main.py` can accumulate partial results into the job. Stage order:

audio extract → Whisper transcribe → **(free Whisper from VRAM)** → VLM (scene detect → keyframes → EasyOCR + VLM description → transcript enhancement → PDF/merged-json reports) → diarization → correction → refinement → subtitles → audit/summary/Q&A → insights compile.

Each stage is individually toggleable via the `options` dict from the UI (`run_transcription`, `run_correction`, `run_vlm`, `run_diarization`, `vlm_model`, etc.). VLM and diarization are the heavyweight optional stages.

### Services are module-level singletons
Each `backend/services/*.py` ends with a singleton instance (`pipeline`, `visual_analyzer`, `diarizer`, `scene_detector`, `transcript_enhancer`, `report_generator`). They are constructed at import time, so importing `pipeline` is expensive (it constructs all of them, and EasyOCR/NeMo lazy-load models on first use). `MediaPipeline.__init__` detects VRAM and resolves the model tier at construction — that's why `/system` can report the active models cheaply.

What each service does:
- `visual_analyzer.py` — EasyOCR text extraction + Ollama VLM keyframe descriptions.
- `transcript_enhancer.py` — the VGPA correction engine (fuses OCR/VLM visual terms with Double-Metaphone phonetics to fix mis-transcribed technical terms). This is what the unit tests cover.
- `diarization.py` — NVIDIA NeMo `ClusteringDiarizer` (`titanet_large`) for who-spoke-when. Optional, opt-in.
- `scene_detector.py` — PySceneDetect keyframe selection.
- `report_generator.py` — reportlab PDF + merged JSON.

### Import convention
`pipeline.py` does `sys.path.append(.../services)` and imports each service with a `try: from .x import ...  except ImportError: from x import ...` (works both as a package and when run directly). Tests instead add `backend/` to `sys.path` and import `from services.x import ...`. Match the surrounding pattern when adding imports.

### Model selection (VRAM-tiered, config-driven)
`backend/models.config.json` is the **single source of truth**: one row per VRAM tier, each specifying `whisper` / `text` / `vlm` model tags. `pipeline.py` reads it on startup via `load_tiers()` / `select_model_tier(vram)`; if the file is missing/invalid it falls back to `_DEFAULT_TIERS` (keep that fallback in sync when editing the JSON). A **single text model** is used for every LLM step (correction, refinement, audit, Q&A, summary) to avoid Ollama model-swap churn. `whisper` is an openai-whisper size (auto-downloaded); `text`/`vlm` are Ollama tags (must be `ollama pull`ed — that's what `Update-Models.ps1` does). The UI's VLM selector defaults to `"auto"`, which means "use the tier's `vlm`"; the backend only overrides when a specific model is chosen.

## Environment gotchas (Windows-specific, all learned the hard way)

- **CUDA torch gets clobbered.** Installing `backend/requirements.txt` pulls a CPU-only torch from PyPI. `Start-App.ps1` fixes this *after* requirements by reinstalling `torch==2.12.1 torchvision==0.27.1` from the **cu130** index. If you touch dependency install order, keep the CUDA repair last.
- **`PYTHONUTF8=1` is required.** EasyOCR prints Unicode progress bars that crash on the Windows cp1252 console. `Start-App.ps1` sets `PYTHONUTF8`/`PYTHONIOENCODING`; set them when running the backend manually too.
- **Antivirus (Bitdefender) quarantines dev files.** This machine runs Bitdefender Endpoint Security (Defender is passive). It has quarantined `node.exe`, PowerShell scripts that download from URLs, and project source files. Two consequences baked into the design: (1) the update checker is intentionally **Python, not a PowerShell `-Check` flag** — a PS script doing `Invoke-RestMethod` to a URL trips the malware-downloader heuristic; (2) if files vanish or "Permission denied" appears on a known-good path, suspect AV quarantine, not a code bug. Recovery is usually `git checkout HEAD -- <file>` after the quarantine lock clears (sometimes needs a reboot).
- **Launch quirks `Start-App.ps1` already handles:** `Start-Process` must call `pnpm.cmd` (not `pnpm`); it prints "All systems go!" even if Vite then dies, so verify `:5173` actually listens.

## Output layout
Per input `video.mp4`, the pipeline writes a sibling folder `video/` containing the `.wav`, raw/clean/refined transcripts, `.srt`/`.vtt`/Netflix `.srt`, `corrections.json`, `merged.json`, PDF report, audit/Q&A/summary, and speaker transcripts. See `example Output/` for a sample.
