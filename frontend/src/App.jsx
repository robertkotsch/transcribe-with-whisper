import { useState, useEffect } from 'react'
import { Activity, FileVideo, CheckCircle, AlertCircle, Play, FileText, Search, Clock, Settings, FolderSearch } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import './App.css'

function App() {
  const [path, setPath] = useState('')
  const [jobs, setJobs] = useState([])
  const [selectedJob, setSelectedJob] = useState(null)

  // Options State
  const [showOptions, setShowOptions] = useState(false)
  const [options, setOptions] = useState({
    skip_existing: false,
    run_transcription: true,
    run_correction: true,
    run_subtitles: true,
    run_audit: true,
    run_qa: true,
    run_insights: true
  })

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
      const sorted = data.reverse()
      setJobs(sorted)

      // Update selected job if it exists to show latest result
      if (selectedJob) {
        const updated = sorted.find(j => j.job_id === selectedJob.job_id)
        if (updated) setSelectedJob(updated)
      } else if (sorted.length > 0) {
        // Auto-select the most recent job if nothing is selected
        setSelectedJob(sorted[0])
      }
    } catch (e) {
      console.error("Failed to fetch jobs", e)
    }
  }

  const handleBrowse = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/pick-file', { method: 'POST' })
      if (!res.ok) throw new Error('Selection cancelled or failed')
      const data = await res.json()
      setPath(data.file_path)
    } catch (e) {
      // Ignore cancellations or log if needed
      console.log("Browse cancelled", e)
    }
  }

  const handleAnalyze = async () => {
    if (!path) return
    try {
      const res = await fetch('http://127.0.0.1:8000/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: path, options: options })
      })
      const newJob = await res.json()
      setPath('')
      setShowOptions(false) // Collapse options after start
      setSelectedJob(newJob) // Auto-select the new job
      fetchJobs()
    } catch (e) {
      alert("Failed to start job: " + e)
    }
  }

  const handleCancel = async (jobId, e) => {
    e.stopPropagation() // Prevent card click
    try {
      await fetch(`http://127.0.0.1:8000/cancel/${jobId}`, {
        method: 'POST'
      })
      fetchJobs() // Refresh status immediate
    } catch (err) {
      alert("Failed to cancel job: " + err)
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
              <button onClick={handleBrowse} className="btn-secondary" title="Browse Local Files">
                <FolderSearch size={16} />
              </button>
            </div>



            <small className="hint">Enter local absolute path or browse to file</small>
            <button onClick={handleAnalyze} className="btn-primary" style={{ marginTop: '1rem', width: '100%', justifyContent: 'center' }}>
              <Play size={16} style={{ marginRight: 8 }} /> Analyze
            </button>
            {/* Options Toggle - Moved below hint */}
            <div className="settings-section">
              <button
                className={`btn-toggle ${showOptions ? 'active' : ''}`}
                onClick={() => setShowOptions(!showOptions)}
              >
                <Settings size={14} style={{ marginRight: 6 }} />
                {showOptions ? "Hide Advanced Options" : "Show Advanced Options"}
              </button>
            </div>

            {/* Options Panel */}
            {showOptions && (
              <div className="settings-panel">
                <div className="checkbox-grid">
                  <label className="checkbox-item">
                    <input type="checkbox" checked={options.skip_existing} onChange={e => setOptions({ ...options, skip_existing: e.target.checked })} />
                    Skip Existing
                  </label>
                  <label className="checkbox-item">
                    <input type="checkbox" checked={options.run_transcription} onChange={e => setOptions({ ...options, run_transcription: e.target.checked })} />
                    Transcribe
                  </label>
                  <label className="checkbox-item">
                    <input type="checkbox" checked={options.run_correction} onChange={e => setOptions({ ...options, run_correction: e.target.checked })} />
                    Correct & Refine
                  </label>
                  <label className="checkbox-item">
                    <input type="checkbox" checked={options.run_subtitles} onChange={e => setOptions({ ...options, run_subtitles: e.target.checked })} />
                    Subtitles (Netflix)
                  </label>
                  <label className="checkbox-item">
                    <input type="checkbox" checked={options.run_audit} onChange={e => setOptions({ ...options, run_audit: e.target.checked })} />
                    Content Audit
                  </label>
                  <label className="checkbox-item">
                    <input type="checkbox" checked={options.run_qa} onChange={e => setOptions({ ...options, run_qa: e.target.checked })} />
                    Generate Q&A
                  </label>
                  <label className="checkbox-item">
                    <input type="checkbox" checked={options.run_insights} onChange={e => setOptions({ ...options, run_insights: e.target.checked })} />
                    Insight Report
                  </label>
                </div>
              </div>
            )}

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
                  {job.status === 'cancelling' && <Activity className="spin" color="#f87171" />}
                  {job.status === 'completed' && <CheckCircle color="#4ade80" />}
                  {job.status === 'failed' && <AlertCircle color="#f87171" />}
                  {job.status === 'cancelled' && <AlertCircle color="#94a3b8" />}
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
                <div>
                  <h2>{selectedJob.file_path.split('\\').pop()}</h2>
                  {selectedJob.result?.language && (
                    <span className="lang-badge">{selectedJob.result.language}</span>
                  )}
                </div>
                {selectedJob.status === 'processing' && (
                  <button
                    className="btn-danger"
                    onClick={(e) => handleCancel(selectedJob.job_id, e)}
                  >
                    Cancel Job
                  </button>
                )}
              </div>

              {(selectedJob.status === 'processing' || selectedJob.status === 'cancelling') && (
                <div className="processing-state">
                  <Activity size={48} className="icon-pulse" />

                  {/* Live Stage Indicator */}
                  <h3>
                    {selectedJob.status === 'cancelling'
                      ? "Stopping..."
                      : (selectedJob.partial?.stage
                        ? `Stage: ${selectedJob.partial.stage.replace('_', ' ').toUpperCase()}`
                        : 'Initializing AI Agents...')}
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
                  <h3>{selectedJob.status === 'cancelled' ? 'Cancelled' : 'Error'}</h3>
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
