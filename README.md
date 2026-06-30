# AI Media Intelligence Pipeline

Automated transcription and AI-powered content analysis for video files. Runs 100% locally — Whisper, Ollama, and NeMo on your own hardware, no cloud calls.

## Two Apps in This Repo

| | V2 Web App (primary) | Legacy Script |
|---|---|---|
| **Interface** | Browser UI | PowerShell CLI |
| **Entry point** | `Start-App.bat` | `Transcribe-Folder.ps1` |
| **Status** | Actively developed | Stable, not extended |

---

## V2 Web App

### Prerequisites

| Tool | Notes |
|------|-------|
| **Python 3.11** | `py install 3.11` if missing |
| **Node.js** (LTS) | Includes `corepack` (manages pnpm) |
| **ffmpeg** | `winget install ffmpeg` — must be in PATH |
| **Ollama** | Running, with tier models pulled (see below) |
| **CUDA GPU** | Recommended; falls back to CPU |

### Quick Start

```powershell
# Double-click Start-App.bat  — or from a terminal:
.\Start-App.bat
```

Opens at **http://localhost:5173**. Backend runs on **:8000**.

The launcher script will:
- Require Python 3.11 (fails fast with install instructions if missing)
- Create / repair the `.venv` automatically
- Install / sync frontend dependencies via pnpm
- Check for ffmpeg before starting anything

### GPU Tiers

Model selection is driven by `backend/models.config.json` (single source of truth). The backend reads VRAM at startup and picks the matching tier automatically:

| VRAM | Whisper | Text (LLM) | VLM |
|------|---------|------------|-----|
| ≥ 20 GB | turbo | qwen3.6:27b | qwen3-vl:8b |
| ≥ 16 GB | turbo | qwen3.5:9b  | qwen3-vl:8b |
| ≥ 12 GB | turbo | qwen3.5:9b  | qwen3-vl:4b |
| ≥ 8 GB  | turbo | qwen3.5:4b  | qwen3-vl:4b |
| ≥ 4 GB  | small | qwen3.5:2b  | qwen3-vl:2b |
| CPU     | small | qwen3.5:2b  | qwen3-vl:2b |

Pull the models for your tier before first run:

```powershell
.\Update-Models.ps1
```

### Features

- **Whisper transcription** — GPU-accelerated, auto-detects German/English
- **Visual analysis** — scene detection, keyframe extraction, EasyOCR + VLM descriptions
- **Transcript enhancement** — VGPA correction engine fuses OCR/VLM visual terms with phonetics
- **Speaker diarization** — NeMo `ClusteringDiarizer` (optional, opt-in)
- **Netflix subtitles** — 42 chars/line, 2 lines max
- **Content audit, Q&A, insights** — single LLM used for all text stages
- **PDF + JSON reports** — per-video output folder

### Pipeline Stages (all toggleable in UI)

`audio extract → Whisper → VLM (scene/OCR/description) → diarization → correction → refinement → subtitles → audit/Q&A/summary → insights`

### Output

Per input `video.mp4` the pipeline writes a sibling folder `video/` with `.wav`, raw/clean/refined transcripts, `.srt`/`.vtt`/Netflix `.srt`, `corrections.json`, `merged.json`, PDF report, audit/Q&A/summary, and speaker transcripts.

### Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ffmpeg not found` | Install ffmpeg, add to PATH |
| `Python 3.11 not found` | `py install 3.11` |
| Vite doesn't start | Check `frontend/node_modules` — run `corepack pnpm install` in `frontend/` |
| Pipeline fails mid-job | Check backend terminal for the actual error; Ollama must be running with models pulled |
| CUDA not active | Start-App.ps1 repairs the torch build automatically on first run |

---

## Legacy Script (`Transcribe-Folder.ps1`)

Self-contained PowerShell script using the `whisper-ctranslate2` CLI and `ollama` CLI directly. No server, no browser.

### Prerequisites

- `whisper-ctranslate2` (`pip install whisper-ctranslate2`)
- `ffmpeg` in PATH
- Ollama running with appropriate models

### Quick Start

```powershell
.\Transcribe-Folder.ps1 "C:\Temp\Media"
```

### Stage Flags

| Flag | Stage |
|------|-------|
| `-OnlyTranscribe` | Whisper only |
| `-OnlyCorrect` | Correction & refinement |
| `-OnlySubtitles` | Netflix subtitle formatting |
| `-OnlyAudit` | Content audit |
| `-OnlyQA` | Q&A generation |
| `-OnlyInsights` | Compile insight reports |
| `-SkipExisting` | Skip already-processed files |
| `-MarkdownOutput` | Output as `.md` instead of `.txt` |

---

## License

MIT
