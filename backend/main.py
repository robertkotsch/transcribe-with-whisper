import asyncio
import uuid
from typing import Dict, List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import sys

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

class JobStatus(BaseModel):
    job_id: str
    status: str
    file_path: str
    result: Optional[Dict] = None
    partial: Optional[Dict] = None # New field for real-time updates
    error: Optional[str] = None

import time

def process_media_task(job_id: str, file_path: str):
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
            # Also persist audit/summary if available
            if "audit" in data: jobs[job_id]["result"]["audit"] = data["audit"]
            if "summary" in data: jobs[job_id]["result"]["summary"] = data["summary"]
            if "questions" in data: jobs[job_id]["result"]["questions"] = data["questions"]
            if "answers" in data: jobs[job_id]["result"]["answers"] = data["answers"]

    try:
        jobs[job_id]["status"] = "processing"
        print(f"Starting job {job_id} for {file_path}")
        
        # Call the pipeline with callback
        result = pipeline.process_full_pipeline(file_path, progress_callback=progress_callback)
        
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["result"] = result
        print(f"Job {job_id} completed successfully.")
        
    except Exception as e:
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
    
    background_tasks.add_task(process_media_task, job_id, request.file_path)
    
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

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
