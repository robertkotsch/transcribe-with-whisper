# Walkthrough: Media Intelligence Station

Congratulations! Your media pipeline has been upgraded from a PowerShell script to a modern, local Web Application.

## 🚀 How to Start

1.  **Open Terminal** in `d:\GIT\transcribe-with-whisper`.
2.  **Run the Startup Script**:
    ```powershell
    .\Start-App.ps1
    ```
    *This will launch the Python Backend and the React Frontend automatically.*

3.  **Open Browser**: Go to [http://localhost:5173](http://localhost:5173).

## 💡 How to Use

1.  **Dashboard**: You will see the "Media Intelligence Station" dashboard with a Glassmorphism design.
2.  **Analyze Media**:
    - Locate a video file (e.g., `D:\Media\meeting.mp4`) or a folder.
    - Paste the **full path** into the text box.
    - Click **ANALYZE**.
3. ### 3. Monitoring Jobs
The dashboard provides a real-time view of your media processing:
- **Status Cards**: See "Pending", "Processing", or "Completed" at a glance.
- **Live Updates**: Watch the detected language and live transcript preview as the AI works.
- **Detailed Stages**: See exactly which step is running (Transcribing, Auditing, Analyzing, etc.).

### 4. Viewing Results
Once completed, the job card will show green.
- Click a job to see the result summary.
- The output folder will contain:
    - `_clean.txt`: Grammar-corrected transcript.
    - `_netflix.srt`: Subtitles formatted for easy reading.
    - `.vtt`, `.tsv`, `.srt`, `.json`, `.txt`: Standard Whisper outputs.
    - `_insights.md`: A comprehensive report including Summary, Audit, Q&A.
    - `_refined_questions.txt`, `_refined_answers.txt`: Specific analysis artifacts.
    - `_audit.md`: AI Content Audit.
    - `_summary.txt`: Quick summary.
    - `_refined.txt`: Polished transcript.
    - `_questions.txt`: Unanswered questions.

## 🛠 Prerequisites

Ensure you have the following installed:
- **Python 3.10+** (with `pip` dependencies installed via `pip install -r backend/requirements.txt`)
- **Node.js** (for the frontend)
- **pnpm** (Install via `npm install -g pnpm`)
- **Ollama** (Running `ollama serve` in background)
- **FFmpeg** (Added to PATH)

## 📦 How to Share with Colleagues

To give this tool to a colleague, copy the entire `transcribe-with-whisper` folder to their machine.

**Their Machine Requirements:**
1.  **Install Python** (Check "Add to PATH" during install).
2.  **Install Node.js**.
3.  **Install pnpm**: Open a terminal and run `npm install -g pnpm`.
4.  **Install FFmpeg** and add it to their System PATH.
5.  **Install Ollama** and pull the models (`ollama pull llama3`, `ollama pull mistral`, `ollama pull qwen2`).

**Installation Steps for Them:**
1.  Unzip/Copy the folder.
2.  Open PowerShell in the folder.
3.  Run `.\Start-App.ps1`.
    - It will automatically create a `.venv`, install libraries, and start the app.
4.  Open `http://localhost:5173`.

## 🔄 Developer Workflow (Git)

You are managing two versions of this project:
1.  **Web App Version** (Current): On branch `feature/web-app-v2`.
2.  **Script Version** (Original): On branch `main`.

### Switching Versions
To go back to the original script to make edits:
```powershell
git checkout main
# Edit Transcribe-Folder.ps1...
git add .
git commit -m "Update script logic"
```

To return to the Web App:
```powershell
git checkout feature/web-app-v2
```

### Porting Changes
If you improve the logic in the script (`main`) and want that in the Web App:
1.  Switch to Web App: `git checkout feature/web-app-v2`
2.  Merge Script changes: `git merge main`
3.  **Note**: This only merges the file changes. You will likely need to duplicate the logic manually from `Transcribe-Folder.ps1` into `backend/services/pipeline.py` since they are different languages (PowerShell vs Python).

## 📁 Architecture Overview

- **Backend**: FastAPI app running on port `8000`. Handles heavyweight AI tasks (Whisper, Ollama).
- **Frontend**: React + Vite app running on port `5173`. Provides the UI.
- **Data**: All processing happens locally. No data leaves your machine.
