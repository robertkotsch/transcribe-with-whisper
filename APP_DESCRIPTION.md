# Media Intelligence Station - Application Overview

## Introduction
**Media Intelligence Station** is a sophisticated local Desktop application designed to transform raw audio and video files into actionable intelligence. By leveraging state-of-the-art AI models (OpenAI Whisper and local LLMs via Ollama), it automates the entire lifecycle of media analysis: from high-fidelity transcription to content auditing, summarization, and Netflix-compliant subtitle generation.

## Core Features

### 1. Advanced Transcription Engine
*   **Whisper Integration:** Utilizes OpenAI's Whisper model (running locally on GPU/CPU) for high-accuracy speech-to-text conversion.
*   **Multi-Format Support:** Handles various media inputs (`.mp4`, `.mp3`, `.wav`, `.mkv`, etc.) via `ffmpeg`.
*   **Metadata Extraction:** Captures comprehensive timestamped metadata in JSON format.

### 2. Intelligent Text Refinement (AI Agents)
The application employs a chain of local LLM argents (using **Ollama**) to progressively upgrade the transcript:
*   **Correction Agent:** Fixes grammar, spelling, and punctuation errors in the raw transcript without altering the original meaning or language (`Llama3`/`Qwen2`).
*   **Refinement Agent:** Rewrites the text for natural flow, idiomatic expression, and readability (`Mistral`).
*   **Language Awareness:** Automatically detects language (English/German) and routes to the appropriate model/prompt chain.

### 3. Professional Subtitling
*   **Standard Formats:** Generates `.srt` and `.vtt` files for web and player compatibility.
*   **Netflix Compliance:** Includes a specialized Python-based deterministic engine that reformats subtitles to meet strict Netflix constraints:
    *   Max 42 characters per line.
    *   Max 2 lines per subtitle block.
    *   Intelligent block splitting and timing adjustments.

### 4. Deep Content Analysis
*   **Executive Summary:** Generates a concise 5-bullet point summary of the content.
*   **Content Audit:** Produces a markdown report analyzing clarity, tone, bias, and information density.
*   **Q&A Generation:** Automatically generates relevant questions based on the content and provides AI-generated answers, useful for educational or review purposes.
*   **Insight Report:** Aggregates all analysis (Audit, Summary, Q&A) into a single cohesive Markdown document.

### 5. Modern User Interface
*   **Real-Time Dashboard:** A "Glassmorphism" design React application providing live updates on job progress.
*   **Live Preview:** Watch the transcription and refinement process happen in real-time.
*   **Artifact Explorer:** Built-in viewer for all generated files (Raw Text, Refined Text, JSON Data, Subtitles, Reports).
*   **Native Integration:** Uses system-native file pickers for easy file selection.
*   **Job Management:** Cancel running jobs, view history, and retry tasks.

## Technology Stack

### Backend
*   **Language:** Python 3.12+
*   **Framework:** **FastAPI** (High-performance async API)
*   **AI/ML Libraries:**
    *   `openai-whisper`: Transcription core.
    *   `ollama`: Local LLM interface.
    *   `torch`: PyTorch backend for Whisper.
    *   `ffmpeg-python`: Media processing.
*   **Data Validation:** `pydantic` for robust schema definitions (esp. for Netflix subtitle validation).
*   **Server:** `uvicorn` (ASGI server).

### Frontend
*   **Framework:** **React 19** (via **Vite**)
*   **Styling:** Modern CSS3 with CSS Variables, Glassmorphism effects, and neon accents.
*   **Icons:** `lucide-react`.
*   **State Management:** React Hooks (`useState`, `useEffect`) with polling-based synchronization.

### Infrastructure & Orchestration
*   **OS:** Windows (Optimized via PowerShell scripts).
*   **Launcher:** `Start-App.ps1` orchestrates the environment setup, backend server, and frontend server in a single command.
*   **Local Execution:** 100% offline-capable (after model download), ensuring data privacy.

## Architecture

The application follows a **Client-Server** architecture tailored for local desktop use:

1.  **Frontend (UI Layer):** 
    *   Runs on `localhost:5173`.
    *   Communicate with Backend via REST API (`/analyze`, `/jobs`, `/cancel`, `/pick-file`).
    *   Polls the job status every 2 seconds to update the UI with progress bar and "Live Preview" data.

2.  **Backend (Service Layer):**
    *   Runs on `localhost:8000`.
    *   **API Controller (`main.py`):** Handles HTTP requests, manages the in-memory job queue, and serves file content.
    *   **Pipeline Service (`pipeline.py`):** The heart of the application. It orchestrates the sequential execution of AI tasks. using `BackgroundTasks` to ensure the UI remains responsive.

3.  **Data Flow:**
    *   User selects a file -> `POST /analyze`.
    *   Backend spawns a background thread.
    *   **Step 1:** `ffmpeg` extracts audio.
    *   **Step 2:** Whisper model loads into VRAM and transcribes.
    *   **Step 3:** JSON/SRT artifacts are written to disk.
    *   **Step 4:** Ollama API is called for Correction/Refinement (Text -> LLM -> Text).
    *   **Step 5:** Python logic processes subtitles (Text -> Pydantic Models -> Netflix SRT).
    *   **Feedback:** Pipeline callback updates the in-memory job state, which the Frontend polls.

## Directory Structure

*   `backend/`: FastAPI application code.
    *   `services/pipeline.py`: Core logic for AI orchestration.
    *   `main.py`: API endpoints.
*   `frontend/`: React source code.
    *   `src/App.jsx`: Main dashboard component.
*   `Start-App.ps1`: Single-click startup script.

## System Requirements
*   **OS:** Windows 10/11.
*   **GPU:** NVIDIA GPU (Recommended) with CUDA support for Whisper and Ollama acceleration.
*   **Tools:** Python 3.12+, Node.js (for frontend build), Ollama (installed and running).
