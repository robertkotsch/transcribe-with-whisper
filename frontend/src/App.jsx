import { useState, useEffect } from 'react'
import { Activity, FileVideo, CheckCircle, AlertCircle, Play, FileText, Search, Clock, Settings, FolderSearch } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import './App.css'

function App() {
  const [path, setPath] = useState('')
  const [jobs, setJobs] = useState([])
  const [selectedJob, setSelectedJob] = useState(null)
  const [previewData, setPreviewData] = useState(null)

  // Options State
  const [showOptions, setShowOptions] = useState(false)
  const [options, setOptions] = useState({
    skip_existing: false,
    run_transcription: true,
    run_correction: true,
    run_subtitles: true,
    run_audit: true,
    run_qa: true,
    run_insights: true,
    run_diarization: false  // Speaker diarization (multi-speaker content)
  })

  useEffect(() => {
    const interval = setInterval(fetchJobs, 2000)
    fetchJobs()
    return () => clearInterval(interval)
  }, [])

  // Live Preview Logic
  useEffect(() => {
    if (!selectedJob || selectedJob.status !== 'processing') return

    // Auto-update preview based on latest available artifact
    // Check in reverse order of pipeline stages
    if (selectedJob.result) {
      if (selectedJob.result.srt) {
        setPreviewData({ title: "Live: Subtitles Generated", content: "```srt\n" + selectedJob.result.srt + "\n```" })
      } else if (selectedJob.result.refined_text) {
        setPreviewData({ title: "Live: Refined Text", content: selectedJob.result.refined_text })
      } else if (selectedJob.result.clean_text) {
        setPreviewData({ title: "Live: Corrected Text", content: selectedJob.result.clean_text })
      } else if (selectedJob.result.raw_text) {
        setPreviewData({ title: "Live: Raw Transcription", content: selectedJob.result.raw_text })
      }
    } else if (selectedJob.partial) {
      // If we have partial real-time updates (not currently fully implemented in backend but nice to have)
      if (selectedJob.partial.raw_text) {
        setPreviewData({ title: "Live: Transcribing...", content: selectedJob.partial.raw_text })
      }
    }
  }, [selectedJob])

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
                  <label className="checkbox-item">
                    <input type="checkbox" checked={options.run_diarization} onChange={e => setOptions({ ...options, run_diarization: e.target.checked })} />
                    Speaker Diarization
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
          {!selectedJob ? (
            <div className="placeholder-content">
              <FileVideo size={64} color="rgba(255,255,255,0.1)" />
              <p>Select a job to view insights</p>
            </div>
          ) : (
            <>
              {/* TOP: Preview Section */}
              <div className="preview-section">
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

                {/* Active Preview Content */}
                {/* Show spinner only if processing AND no preview data yet */}
                {(selectedJob.status === 'processing' || selectedJob.status === 'cancelling') && !previewData ? (
                  <div className="processing-state">
                    <Activity size={48} className="icon-pulse" />
                    <h3>
                      {selectedJob.status === 'cancelling'
                        ? "Stopping..."
                        : (selectedJob.partial?.stage
                          ? `Stage: ${selectedJob.partial.stage.replace('_', ' ').toUpperCase()}`
                          : 'Initializing AI Agents...')}
                    </h3>
                    <p className="sub-text">Processing locally on GPU...</p>
                  </div>
                ) : (
                  <div className="markdown-content">
                    {/* Default View or Selected Card Content */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <h3>{previewData?.title || "Result Preview"}</h3>
                      {/* Mini-spinner if still processing but showing data */}
                      {selectedJob.status === 'processing' && (
                        <div className="mini-status" style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#fbbf24' }}>
                          <Activity size={16} className="spin" />
                          <span style={{ fontSize: '0.8rem' }}>Processing...</span>
                        </div>
                      )}
                    </div>

                    <div className="content-box">
                      {previewData?.content ? (
                        <ReactMarkdown>{previewData.content}</ReactMarkdown>
                      ) : (
                        <div className="empty-preview">
                          <p>Select a document card below to preview its content.</p>
                        </div>
                      )}
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

              {/* BOTTOM: Documents Section */}
              <div className="documents-section">
                <h3>Result Documents</h3>
                <div className="results-grid">
                  {/* Refined Text Card */}
                  {/* Raw Transcript Card */}
                  {(selectedJob.result?.raw_text) && (
                    <ResultCard
                      title="Raw TXT"
                      description="Original whisper transcription output"
                      content={selectedJob.result.raw_text}
                      onShow={() => setPreviewData({ title: "Raw Transcript", content: selectedJob.result.raw_text })}
                    />
                  )}

                  {/* Corrected Transcript Card */}
                  {(selectedJob.result?.clean_text) && (
                    <ResultCard
                      title="Clean TXT"
                      description="Corrected grammar and punctuation"
                      content={selectedJob.result.clean_text}
                      onShow={() => setPreviewData({ title: "Corrected Transcript", content: selectedJob.result.clean_text })}
                    />
                  )}

                  {/* Refined Text Card */}
                  {selectedJob.result?.refined_text && (
                    <ResultCard
                      title="Refined TXT"
                      description="Polished for readability and flow"
                      content={selectedJob.result.refined_text}
                      onShow={() => setPreviewData({ title: "Refined Transcript", content: selectedJob.result.refined_text })}
                    />
                  )}

                  {/* Summary Card */}
                  {selectedJob.result?.summary && (
                    <ResultCard
                      title="Summary"
                      description="Executive overview of key points"
                      content={selectedJob.result.summary}
                      onShow={() => setPreviewData({ title: "Executive Summary", content: selectedJob.result.summary })}
                    />
                  )}

                  {/* Audit Card */}
                  {selectedJob.result?.audit && (
                    <ResultCard
                      title="Audit"
                      description="Content quality and accuracy report"
                      content={selectedJob.result.audit}
                      onShow={() => setPreviewData({ title: "Content Audit", content: selectedJob.result.audit })}
                    />
                  )}

                  {/* Q&A Card */}
                  {selectedJob.result?.questions && (
                    <ResultCard
                      title="QA"
                      description="Generated comprehension questions"
                      content={selectedJob.result.questions}
                      onShow={() => setPreviewData({ title: "Generated Questions", content: selectedJob.result.questions })}
                    />
                  )}

                  {selectedJob.result?.answers && (
                    <ResultCard
                      title="Answers"
                      description="AI-generated answers to questions"
                      content={selectedJob.result.answers}
                      onShow={() => setPreviewData({ title: "AI Answers", content: selectedJob.result.answers })}
                    />
                  )}

                  {/* Additional Artifacts Cards */}
                  {selectedJob.result?.json && (
                    <ResultCard
                      title="JSON"
                      description="Full analysis data structure"
                      content={selectedJob.result.json}
                      onShow={() => setPreviewData({ title: "Raw JSON Data", content: "```json\n" + selectedJob.result.json + "\n```" })}
                    />
                  )}

                  {selectedJob.result?.vtt && (
                    <ResultCard
                      title="VTT"
                      description="Web Video Text Tracks subtitles"
                      content={selectedJob.result.vtt}
                      onShow={() => setPreviewData({ title: "WebVTT Subtitles", content: "```vtt\n" + selectedJob.result.vtt + "\n```" })}
                    />
                  )}

                  {selectedJob.result?.srt && (
                    <ResultCard
                      title="SRT"
                      description="Standard SubRip subtitle file"
                      content={selectedJob.result.srt}
                      onShow={() => setPreviewData({ title: "SRT Subtitles", content: "```srt\n" + selectedJob.result.srt + "\n```" })}
                    />
                  )}

                  {selectedJob.result?.netflix_srt && (
                    <ResultCard
                      title="Netflix SRT"
                      description="Netflix-compliant subtitle format"
                      content={selectedJob.result.netflix_srt}
                      onShow={() => setPreviewData({ title: "Netflix-Compliant Subtitles", content: "```srt\n" + selectedJob.result.netflix_srt + "\n```" })}
                    />
                  )}

                  {/* Speaker Transcript Card */}
                  {selectedJob.result?.speaker_transcript && (
                    <ResultCard
                      title="Speaker Transcript"
                      description={`Multi-speaker content (${selectedJob.result?.num_speakers || 1} speakers)`}
                      content={selectedJob.result.speaker_transcript}
                      onShow={() => setPreviewData({
                        title: "Speaker-Labeled Transcript",
                        content: selectedJob.result.speaker_transcript
                      })}
                    />
                  )}
                </div>


                {selectedJob.result?.output_dir && (
                  <div className="results-container" style={{ marginTop: '2rem' }}>
                    <div className="artifact-links">
                      <p><strong>Output Location:</strong></p>
                      <code style={{ fontSize: '0.8rem', opacity: 0.7 }}>{selectedJob.result.output_dir}</code>
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
            </>
          )}
        </section>

      </main>
    </div >
  )
}

function ResultCard({ title, description, content, onShow }) {
  // Clean up content for teaser (remove markdown roughly)
  const cleanContent = content ? content.replace(/[#*`]/g, '').trim() : ""

  return (
    <div className="result-card-wrapper">
      <div className="result-card">
        <div className="card-title">{title}</div>
        {description && <div className="card-desc">{description}</div>}
        <div className="card-content-preview">
          {cleanContent}
        </div>
      </div>
      <button className="btn-show-me" onClick={onShow}>
        SHOW ME
      </button>
    </div>
  )
}

export default App
