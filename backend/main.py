import asyncio
import uuid
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import sys
import shutil

# Add services to path
sys.path.append(os.path.join(os.path.dirname(__file__), "services"))
from pipeline import pipeline

app = FastAPI(title="Media Intelligence Pipeline", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store (sufficient for local app)
jobs: Dict[str, Dict] = {}

class JobRequest(BaseModel):
    file_path: str
    options: Optional[Dict[str, Any]] = None  # Changed from Dict[str, bool] to support mixed types

class JobStatus(BaseModel):
    job_id: str
    status: str
    file_path: str
    result: Optional[Dict] = None
    partial: Optional[Dict] = None # New field for real-time updates
    error: Optional[str] = None

import time

def process_media_task(job_id: str, file_path: str, options: Dict[str, bool] = None):
    """Background task wrapper."""
    def progress_callback(stage: str, data: dict = None):
        """Update job status in real-time."""
        print(f"[Job {job_id}] Stage: {stage}")
        jobs[job_id]["partial"] = {
            "stage": stage,
            "data": data,
            "timestamp": str(time.time())
        }
        
        # Initialize result dict if needed
        if not jobs[job_id].get("result"): 
            jobs[job_id]["result"] = {}
            
        # Persist valuable data across stages
        if data:
            if "language" in data:
                jobs[job_id]["result"]["language"] = data["language"]
            if "raw_text" in data:
                jobs[job_id]["result"]["raw_text"] = data["raw_text"]
            if "refined_text" in data:
                jobs[job_id]["result"]["refined_text"] = data["refined_text"]
            if "clean_text" in data:
                jobs[job_id]["result"]["clean_text"] = data["clean_text"]
            # Also persist audit/summary if available
            if "audit" in data: jobs[job_id]["result"]["audit"] = data["audit"]
            if "summary" in data: jobs[job_id]["result"]["summary"] = data["summary"]
            if "questions" in data: jobs[job_id]["result"]["questions"] = data["questions"]
            if "answers" in data: jobs[job_id]["result"]["answers"] = data["answers"]
            
            # Additional Artifacts
            if "srt" in data: jobs[job_id]["result"]["srt"] = data["srt"]
            if "vtt" in data: jobs[job_id]["result"]["vtt"] = data["vtt"]
            if "json" in data: jobs[job_id]["result"]["json"] = data["json"]
            if "netflix_srt" in data: jobs[job_id]["result"]["netflix_srt"] = data["netflix_srt"]
            if "speaker_transcript" in data: jobs[job_id]["result"]["speaker_transcript"] = data["speaker_transcript"]
            if "num_speakers" in data: jobs[job_id]["result"]["num_speakers"] = data["num_speakers"]
            
            # VLM Visual Analysis Stats
            if "scenes_detected" in data or "keyframes_analyzed" in data or "corrections_made" in data or "visual_terms" in data:
                if "vlm_stats" not in jobs[job_id]["result"]:
                    jobs[job_id]["result"]["vlm_stats"] = {}
                if "scenes_detected" in data: jobs[job_id]["result"]["vlm_stats"]["scenes_detected"] = data["scenes_detected"]
                if "keyframes_analyzed" in data: jobs[job_id]["result"]["vlm_stats"]["keyframes_analyzed"] = data["keyframes_analyzed"]
                if "corrections_made" in data: jobs[job_id]["result"]["vlm_stats"]["corrections_made"] = data["corrections_made"]
                if "visual_terms" in data: jobs[job_id]["result"]["vlm_stats"]["visual_terms"] = data["visual_terms"]
    
    def check_cancelled():
        """Check if job has been marked for cancellation."""
        return jobs[job_id].get("status") == "cancelling"

    try:
        jobs[job_id]["status"] = "processing"
        print(f"Starting job {job_id} for {file_path}")
        
        # Call the pipeline with callback
        result = pipeline.process_full_pipeline(
            file_path, 
            progress_callback=progress_callback, 
            options=options,
            cancel_callback=check_cancelled
        )
        
        jobs[job_id]["status"] = "completed"
        # Merge final result (metadata) with accumulated partial results (content)
        if not jobs[job_id].get("result"): jobs[job_id]["result"] = {}
        jobs[job_id]["result"].update(result)
        print(f"Job {job_id} completed successfully.")
        
    except Exception as e:
        if str(e) == "Job Cancelled by User":
             print(f"Job {job_id} was cancelled.")
             jobs[job_id]["status"] = "cancelled"
             jobs[job_id]["error"] = "Cancelled by user"
        else:
             print(f"Job {job_id} failed: {e}")
             jobs[job_id]["status"] = "failed"
             jobs[job_id]["error"] = str(e)

@app.post("/analyze", response_model=JobStatus)
async def analyze_media(request: JobRequest, background_tasks: BackgroundTasks):
    """Start a media analysis job."""
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=400, detail="File not found")
        
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "job_id": job_id,
        "status": "pending", 
        "file_path": request.file_path
    }
    
    background_tasks.add_task(process_media_task, job_id, request.file_path, request.options)
    
    return jobs[job_id]

import tkinter as tk
from tkinter import filedialog
import threading

def open_file_dialog():
    """Runs the file dialog in a separate thread context."""
    # Create invisible root window
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True) # Bring to front
    
    file_path = filedialog.askopenfilename(
        title="Select Media File",
        filetypes=[("Media Files", "*.mp4 *.mp3 *.wav *.mkv *.mov *.flac *.aac"), ("All Files", "*.*")]
    )
    
    root.destroy()
    return file_path

@app.post("/pick-file")
async def pick_file(background_tasks: BackgroundTasks):
    """Triggers a native file picker on the server (user machine)."""
    # Run the blocking GUI call in a thread
    loop = asyncio.get_event_loop()
    file_path = await loop.run_in_executor(None, open_file_dialog)
    
    if not file_path:
        raise HTTPException(status_code=400, detail="No file selected")
        
    return {"file_path": file_path}


@app.post("/cancel/{job_id}", response_model=JobStatus)
async def cancel_job(job_id: str):
    """Cancel a running job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    current_status = jobs[job_id]["status"]
    if current_status in ["completed", "failed", "cancelled"]:
         return jobs[job_id] # Already done
         
    # Mark for cancellation
    jobs[job_id]["status"] = "cancelling"
    print(f"Job {job_id} marked for cancellation...")
    return jobs[job_id]

@app.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.get("/jobs", response_model=List[JobStatus])
async def list_jobs():
    return list(jobs.values())

@app.get("/")
def read_root():
    return {"status": "Media Pipeline Backend is Running"}

import importlib.util
import requests as _requests

def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False

@app.get("/system")
def system_info():
    """Live system status for the dashboard header (GPU + service health)."""
    gpu_name = None
    vram_gb = None
    cuda = False
    try:
        import torch
        cuda = torch.cuda.is_available()
        if cuda:
            gpu_name = torch.cuda.get_device_name(0).replace("NVIDIA ", "").strip()
            vram_gb = round(torch.cuda.get_device_properties(0).total_memory / (1024 ** 3), 1)
    except Exception:
        pass

    # Ollama reachability (short timeout so the header never hangs)
    ollama_up = False
    try:
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        ollama_up = _requests.get(f"{ollama_url}/api/tags", timeout=1.5).ok
    except Exception:
        ollama_up = False

    # Auto-selected model tier (scales with detected VRAM)
    try:
        models = pipeline.active_models()
    except Exception:
        models = None

    return {
        "gpu": gpu_name,
        "vram_gb": vram_gb,
        "cuda": cuda,
        "models": models,
        "services": {
            "whisper": _module_available("whisper"),
            "ollama": ollama_up,
            "nemo": _module_available("nemo"),
        },
    }

from fastapi.responses import FileResponse

@app.get("/file")
async def get_file(path: str):
    """Serve a local file."""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
