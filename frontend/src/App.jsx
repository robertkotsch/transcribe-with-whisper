import { useState, useEffect } from 'react'
import { Activity, FileVideo, CheckCircle, AlertCircle, Play, FileText, Search, Clock } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import './App.css'

function App() {
  const [path, setPath] = useState('')
  const [jobs, setJobs] = useState([])
  const [selectedJob, setSelectedJob] = useState(null)

  useEffect(() => {
    const interval = setInterval(fetchJobs, 2000)
    fetchJobs()
    return () => clearInterval(interval)
  }, [])

  const fetchJobs = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/jobs')
      const data = await res.json()
      // Sort by newness (reversed)
      setJobs(data.reverse())

      // Update selected job if it exists to show latest result
      if (selectedJob) {
        const updated = data.find(j => j.job_id === selectedJob.job_id)
        if (updated) setSelectedJob(updated)
      }
    } catch (e) {
      console.error("Failed to fetch jobs", e)
    }
  }

  const handleAnalyze = async () => {
    if (!path) return
    try {
      await fetch('http://127.0.0.1:8000/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: path })
      })
      setPath('')
      fetchJobs()
    } catch (e) {
      alert("Failed to start job: " + e)
    }
  }

  return (
    <div className="container">
      <header className="header glass">
        <div className="logo-area">
          <Activity className="icon-pulse" color="#00f2ff" />
          <h1 className="heading-glow">Media Intelligence Station</h1>
        </div>
        <div className="status-badge">
          System Online
        </div>
      </header>

      <main className="dashboard-grid">

        {/* Left Panel: Controls & List */}
        <section className="control-panel glass-panel">
          <div className="input-group">
            <label>Target Media File</label>
            <div className="input-row">
              <input
                type="text"
                value={path}
                onChange={(e) => setPath(e.target.value)}
                placeholder="C:\Temp\Media\Autoupdate.mp4"
                className="glass-input"
              />
              <button onClick={handleAnalyze} className="btn-primary">
                <Play size={16} style={{ marginRight: 8 }} /> Analyze
              </button>
            </div>
            <small className="hint">Enter local absolute path to video or audio file</small>
          </div>

          <div className="job-list">
            <h3>Recent Operations</h3>
            {jobs.length === 0 && <div className="empty-state">No active jobs</div>}

            {jobs.map(job => (
              <div
                key={job.job_id}
                className={`job-card glass ${selectedJob?.job_id === job.job_id ? 'active' : ''}`}
                onClick={() => setSelectedJob(job)}
              >
                <div className="job-icon">
                  {job.status === 'processing' && <Activity className="spin" color="#fbbf24" />}
                  {job.status === 'completed' && <CheckCircle color="#4ade80" />}
                  {job.status === 'failed' && <AlertCircle color="#f87171" />}
                  {job.status === 'pending' && <Clock color="#94a3b8" />}
                </div>
                <div className="job-info">
                  <div className="job-path" title={job.file_path}>
                    {job.file_path.split('\\').pop().split('/').pop()}
                  </div>
                  <div className={`job-status status-${job.status}`}>
                    {job.status.toUpperCase()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Right Panel: Viewer */}
        <section className="viewer-panel glass-panel">
          {!selectedJob && (
            <div className="placeholder-content">
              <FileVideo size={64} color="rgba(255,255,255,0.1)" />
              <p>Select a job to view insights</p>
            </div>
          )}

          {selectedJob && (
            <div className="report-content">
              <div className="report-header">
                <h2>{selectedJob.file_path.split('\\').pop()}</h2>
                {selectedJob.result?.language && (
                  <span className="lang-badge">{selectedJob.result.language}</span>
                )}
              </div>

              {selectedJob.status === 'processing' && (
                <div className="processing-state">
                  <Activity size={48} className="icon-pulse" />

                  {/* Live Stage Indicator */}
                  <h3>
                    {selectedJob.partial?.stage
                      ? `Stage: ${selectedJob.partial.stage.replace('_', ' ').toUpperCase()}`
                      : 'Initializing AI Agents...'}
                  </h3>

                  {/* Live Language Detection */}
                  {selectedJob.result?.language && (
                    <div className="live-pill">
                      Detected: {selectedJob.result.language}
                    </div>
                  )}

                  {/* Live Text Preview (Persisted) */}
                  {(selectedJob.result?.refined_text || selectedJob.result?.raw_text) && (
                    <div className="live-preview glass">
                      <h4>
                        {selectedJob.result.refined_text ? "Refined Transcript" : "Raw Transcript"}
                      </h4>
                      <p className="preview-text">
                        {(selectedJob.result.refined_text || selectedJob.result.raw_text).substring(0, 500)}...
                      </p>
                    </div>
                  )}

                  {/* Live Analysis Preview */}
                  {selectedJob.result?.audit && (
                    <div className="live-preview glass">
                      <h4>Audit Generating...</h4>
                      <p className="preview-text">{selectedJob.result.audit.substring(0, 200)}...</p>
                    </div>
                  )}

                  <p className="sub-text">This processing happens locally on your GPU.</p>
                </div>
              )}

              {selectedJob.result?.output_dir && (
                <div className="results-container">
                  {/* Here we would fetch the actual MD content. For v1, we show path info */}
                  <div className="artifact-links">
                    <p><strong>Output Location:</strong></p>
                    <code>{selectedJob.result.output_dir}</code>
                  </div>

                  {/* Simple Markdown Preview Mock (In real app, we'd fetch the content) */}
                  <div className="markdown-preview">
                    <h3>Result Summary</h3>
                    <p>Artifacts generated successfully. Open folder to view full reports.</p>
                    {/* To make this real, we need an endpoint to Serve the file content */}
                  </div>
                </div>
              )}

              {selectedJob.error && (
                <div className="error-box">
                  <h3>Error</h3>
                  <p>{selectedJob.error}</p>
                </div>
              )}
            </div>
          )}
        </section>

      </main>
    </div>
  )
}

export default App
