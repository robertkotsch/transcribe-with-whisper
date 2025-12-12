# Media Intelligence Station - Application Overview

## Introduction
**Media Intelligence Station** is a sophisticated local Desktop application designed to transform raw audio and video files into actionable intelligence. By leveraging state-of-the-art AI models (OpenAI Whisper, NVIDIA NeMo, and local LLMs/VLMs via Ollama), it automates the entire lifecycle of media analysis: from high-fidelity transcription and multi-modal visual analysis to content auditing, summarization, and Netflix-compliant subtitle generation.

## Core Features

### 1. Advanced Transcription Engine
*   **Whisper Integration:** Utilizes OpenAI's Whisper model (running locally on GPU/CPU) for high-accuracy speech-to-text conversion.
*   **Multi-Format Support:** Handles various media inputs (`.mp4`, `.mp3`, `.wav`, `.mkv`, etc.) via `ffmpeg`.
*   **Metadata Extraction:** Captures comprehensive timestamped metadata in JSON format.
*   **Confidence Scoring:** Now enables `word_timestamps` to capture granular confidence scores for every transcribed word, enabling vastly smarter downstream corrections.

### 2. Multi-Modal Visual Intelligence (NEW)
*   **VLM Integration:** Uses local Vision Language Models (like `minicpm-v` or `llava` via Ollama) to analyze video keyframes, generating detailed text descriptions of slides, charts, and software UIs.
*   **OCR Engine:** Integrated `easyocr` (supporting English/German) to extract on-screen text, technical values, and labels with spatial awareness.
*   **Deep Context Extraction:** Automatically extracts technical terms, acronyms, and regulation references (e.g., "DIN 5008", "45 dB") from visual content to build a project-specific visual vocabulary.

### 3. Intelligent Text Refinement (AI Agents)
The application employs a chain of local AI agents to progressively upgrade the transcript:
*   **Visually-Grounded Phonetic Alignment ("VGPA"):** A proprietary hybrid correction engine that fuses **visual data** (OCR/VLM) with **phonetic algorithms** (Double Metaphone) to fix hallucinated terms. It features:
    *   **Dynamic Confidence-Aware Thresholding:** Uses Whisper's word-level confidence scores to dynamically adjust matching strictness. If the audio model is "unsure" (low confidence), the engine becomes more permissive, allowing visual ground truth to override even weak phonetic matches.
    *   **Heuristic Component Matching:** A specialized sub-routine that intelligently handles complex compound words (e.g., "Knowledge-Burger" vs. "Knowledgeworker") by analyzing constituent parts and creating manual phonetic bridges for known difficult pairings.
    *   **Multi-Pass Temporal Scanning:** Uses a sliding window N-gram scanner aligned with a multi-occurrence visual index to correct terms wherever they appear in the video.
*   **Correction Agent:** Fixes grammar, spelling, and punctuation errors in the raw transcript (`Llama3`/`Qwen2`).
*   **Refinement Agent:** Rewrites the text for natural flow, idiomatic expression, and readability (`Mistral`).
*   **Language Awareness:** Automatically detects language (English/German) and routes to the appropriate model/prompt chain.

### 4. Professional Subtitling
*   **Standard Formats:** Generates `.srt` and `.vtt` files for web and player compatibility.
*   **Netflix Compliance:** Includes a specialized Python-based deterministic engine that reformats subtitles to meet strict Netflix constraints:
    *   Max 42 characters per line.
    *   Max 2 lines per subtitle block.
    *   Intelligent block splitting and timing adjustments.

### 5. Speaker Diarization (NEW)
*   **NVIDIA NeMo Integration:** Identifies and labels different speakers in multi-speaker audio content.
*   **Merged Transcripts:** Speaker labels are aligned with Whisper's word-level timestamps.
*   **Output Formats:** Generates speaker-labeled plain text and SRT subtitle files.
*   **Color-Coded UI:** Each speaker displays with a distinct color badge in the frontend.

### 6. Deep Content Analysis
*   **Visual PDF Report:** Generates a comprehensive PDF report with embedded keyframes, full scene descriptions, and synchronized transcripts, ideal for documentation and compliance.
*   **Merged Data Export:** Produces a rich `merged.json` combining the audio timeline, visual analysis, OCR data, and metadata into a single structure.
*   **Executive Summary:** Generates a concise 5-bullet point summary of the content.
*   **Content Audit:** Produces a markdown report analyzing clarity, tone, bias, and information density.
*   **Q&A Generation:** Automatically generates relevant test questions and answers based on the content.

### 7. Modern User Interface
*   **Real-Time Dashboard:** A "Glassmorphism" design React application providing live updates on job progress.
*   **Live Preview:** Watch the transcription and refinement process happen in real-time.
*   **Artifact Explorer:** Built-in viewer for all generated files (Text, JSON, Subtitles, Speaker Transcripts, Reports).
*   **Visual Verification:** View extracted "Visual Analysis" stats and details directly in the UI.
*   **Advanced Job Options:** Granular control to enable/disable specific pipeline steps (Transcription, Correction, VLM, Diarization, etc.) and select specific VLM models.

## Technology Stack

### Backend
*   **Language:** Python 3.12+
*   **Framework:** **FastAPI** (High-performance async API)
*   **AI/ML Libraries:**
    *   `openai-whisper`: Transcription core.
    *   `ollama`: Local LLM and VLM interface.
    *   `nemo_toolkit[asr]`: NVIDIA NeMo for speaker diarization.
    *   `easyocr`: OCR engine for visual text extraction.
    *   `torch`: PyTorch backend.
    *   `ffmpeg-python`: Media processing.
*   **Reporting:** `reportlab`, `Pillow` for PDF generation.
*   **Data Validation:** `pydantic` for robust schema definitions.
*   **Server:** `uvicorn` (ASGI server).

### Frontend
*   **Framework:** **React 19** (via **Vite**)
*   **Styling:** Modern CSS3 with CSS Variables, Glassmorphism effects, and neon accents.
*   **Icons:** `lucide-react`.
*   **State Management:** React Hooks with polling-based synchronization.

### Infrastructure & Orchestration
*   **OS:** Windows (Optimized via PowerShell scripts).
*   **Launcher:** `Start-App.ps1` orchestrates the environment setup, backend server, and frontend server.
*   **Local Execution:** 100% offline-capable (after model download), ensuring data privacy.

## Architecture

The application follows a **Client-Server** architecture tailored for local desktop use:

1.  **Frontend (UI Layer):** 
    *   Runs on `localhost:5173`.
    *   Communicate with Backend via REST API.
    *   Displays live progress and provides interactive result cards.

2.  **Backend (Service Layer):**
    *   Runs on `localhost:8000`.
    *   **Pipeline Service (`pipeline.py`):** Orchestrates the sequential execution of AI tasks using `BackgroundTasks`.
    *   **Specialized Services:** `VisualAnalyzer` (OCR/VLM), `TranscriptEnhancer` (Correction), `ReportGenerator` (PDF/JSON).

3.  **Data Flow:**
    *   User selects a file -> `POST /analyze`.
    *   **Audio Pipeline:** Extract Audio -> Whisper Transcribe -> Diarization (Optional).
    *   **Visual Pipeline:** Extract Keyframes -> EasyOCR -> VLM Description.
    *   **Refinement:** Audio Transcript + Visual Vocabulary -> Hybrid Correction -> LLM Refinement.
    *   **Output:** Subtitles, JSON, PDF Report, Summaries.

## Directory Structure

*   `backend/`: FastAPI application code.
    *   `services/pipeline.py`: Core orchestration.
    *   `services/visual_analyzer.py`: OCR and VLM logic.
    *   `services/transcript_enhancer.py`: Correction logic.
    *   `services/report_generator.py`: PDF generation.
    *   `main.py`: API endpoints.
*   `frontend/`: React source code.
    *   `src/App.jsx`: Main dashboard component.
*   `Start-App.ps1`: Single-click startup script.

## System Requirements
*   **OS:** Windows 10/11.
*   **GPU:** NVIDIA GPU (Recommended) with CUDA support for Whisper, NeMo, and Ollama.
*   **Tools:** Python 3.12+, Node.js, Ollama (with `llama3`, `mistral`, `minicpm-v` models pulled).
