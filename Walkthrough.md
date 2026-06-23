# User Features Walkthrough

I have implemented two major features to give you more control over the Media Intelligence Station: granular execution options and job cancellation.

## 1. Job Cancellation
You can now cancel a running job if you change your mind or if it's taking too long.

### How to use
- When a job is in the **Processing** state, a red **"Cancel Job"** button will appear in the top-right of the report viewer.
- Clicking this button sends a signal to the backend.
- The backend will stop processing at the next safe checkpoint (e.g., between transcription and correction, or before generating questions).
- The job status will update to **CANCELLED** and the UI will reflect this.

### Implementation Details
- **Backend**: Added `/cancel/{job_id}` endpoint. The pipeline now checks for a cancellation signal before every major step (Extraction, Transcription, Correction, etc.).
- **Frontend**: Added `handleCancel` logic and the styled button.

## 2. Advanced Execution Options
Control exactly which AI agents run on your media.

### How to use
- Click **"Advanced Options"** in the control panel.
- Toggle checkboxes to enable/disable:
  - **Skip Existing**: Don't re-run steps if files exist.
  - **Transcribe**: Whisper audio-to-text.
  - **Correct & Refine**: Ollama grammar and style fixing.
  - **Subtitles**: Netflix-style SRT generation.
  - **Content Audit**: Analytic report generation.
  - **Generate Q&A**: Identifying gaps and questions.
  - **Insight Report**: Final markdown report assembly.

## Files Modified
- `backend/main.py`: Added cancel endpoint & options support.
- `backend/services/pipeline.py`: Added cancellation checkpoints & options logic.
- `frontend/src/App.jsx`: Added Options UI & Cancel Button.
- `frontend/src/App.css`: Styles for settings panel and danger button.

## 3. Model Selection & Updating

The app auto-selects Whisper + LLM + VLM models to match the machine's GPU VRAM,
so the same code runs well on an 8 GB laptop GPU and a 24 GB RTX 4090.

### Single source of truth
All model choices live in **`backend/models.config.json`**, one row per VRAM
tier. The backend reads it on startup (and falls back to built-in defaults if
the file is missing). The active tier is shown in the dashboard header and via
`GET /system`.

### Updating models (e.g. when newer ones are released)
1. Edit `backend/models.config.json` — change the `text` / `vlm` / `whisper`
   values for the relevant tier(s).
2. Run the sync script to pull the new models for **this** machine's tier:
   ```powershell
   .\Update-Models.ps1            # pull this machine's tier models
   .\Update-Models.ps1 -Prune     # also remove Ollama models no tier uses
   .\Update-Models.ps1 -VramOverrideGB 24 -WhatIf   # preview another tier
   ```
   (`whisper` sizes are downloaded automatically by openai-whisper; only the
   Ollama `text`/`vlm` models are pulled.)
