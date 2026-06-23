import { useState, useEffect } from 'react'
import { Activity, FileVideo, CheckCircle, AlertCircle, Play, FileText, Search, Clock, Settings, FolderSearch, Microscope, Shield } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import './App.css'

function App() {
  const [path, setPath] = useState('')
  const [jobs, setJobs] = useState([])
  const [selectedJob, setSelectedJob] = useState(null)
  const [previewData, setPreviewData] = useState(null)
  const [systemInfo, setSystemInfo] = useState(null)

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
    run_diarization: false,  // Speaker diarization (multi-speaker content)
    run_vlm: true,           // VLM visual analysis (enabled by default)
    vlm_model: 'minicpm-v'   // Ollama vision model (MiniCPM-V best for technical content)
  })

  useEffect(() => {
    const interval = setInterval(fetchJobs, 2000)
    fetchJobs()
    return () => clearInterval(interval)
  }, [])

  // Poll live system status (GPU + service health) for the header
  const fetchSystem = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/system')
      setSystemInfo(await res.json())
    } catch {
      setSystemInfo(null) // backend unreachable
    }
  }

  useEffect(() => {
    fetchSystem()
    const id = setInterval(fetchSystem, 5000)
    return () => clearInterval(id)
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


  const handleFilePreview = async (type, path, title) => {
    const backendUrl = `http://127.0.0.1:8000/file?path=${encodeURIComponent(path)}`

    if (type === 'pdf') {
      setPreviewData({ title, type: 'pdf', url: backendUrl })
    } else if (type === 'json') {
      try {
        setPreviewData({ title, content: "Loading..." })
        const res = await fetch(backendUrl)
        if (!res.ok) throw new Error("Failed to load file")
        const json = await res.json()
        setPreviewData({
          title,
          content: "```json\n" + JSON.stringify(json, null, 2) + "\n```"
        })
      } catch (e) {
        setPreviewData({ title, content: "Error loading file: " + e.message })
      }
    }
  }

  return (
    <div className="container">
      <header className="header glass" style={{ height: 'auto', padding: '1rem 2rem' }}>
        <div className="logo-area" style={{ alignItems: 'flex-start' }}>
          <Microscope className="icon-pulse" color="#00f2ff" size={48} style={{ marginTop: '5px' }} />
          <div style={{ display: 'flex', flexDirection: 'column', marginLeft: '1rem' }}>
            <h1 className="heading-glow" style={{ marginBottom: '2px', fontSize: '1.8rem' }}>Media Intelligence Station</h1>
            <span style={{ fontSize: '1rem', color: '#a5f3fc', letterSpacing: '0.5px', fontWeight: 500 }}>
              Multimodal AI That Sees & Hears
            </span>
            <span style={{ fontSize: '0.8rem', opacity: 0.5, marginTop: '4px' }}>v1.0 • Robert Kotsch</span>

            <div style={{ display: 'flex', alignItems: 'center', gap: '15px', marginTop: '12px', fontSize: '0.85rem', color: 'rgba(255,255,255,0.8)' }}>
              <span style={{ fontWeight: 600, color: 'rgba(255,255,255,0.5)' }}>System Status:</span>
              {[
                { key: 'whisper', label: 'Whisper' },
                { key: 'ollama', label: 'Ollama' },
                { key: 'nemo', label: 'NeMo' },
              ].map(({ key, label }) => {
                const state = systemInfo?.services?.[key]
                const color = state === true ? '#4ade80' : state === false ? '#f87171' : '#94a3b8'
                const desc = state === true ? 'available' : state === false ? 'unavailable' : 'unknown'
                return (
                  <span key={key} style={{ display: 'flex', alignItems: 'center', gap: '6px' }} title={`${label}: ${desc}`}>
                    <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: color, boxShadow: `0 0 8px ${color}` }}></span> {label}
                  </span>
                )
              })}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', height: '100%', paddingBottom: '5px', alignItems: 'flex-end' }}>
          <div className="status-badge" style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            color: '#4ade80',
            borderColor: 'rgba(74, 222, 128, 0.3)',
            background: 'rgba(74, 222, 128, 0.1)',
            padding: '6px 12px',
            borderRadius: '6px',
            fontSize: '0.9rem',
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
          }}>
            <span style={{ fontWeight: 600 }}>🔒 100% Local</span> • €0/min • 0 ☁️
          </div>

          {/* Advanced Status Indicators */}
          <div style={{ marginTop: '10px', display: 'flex', alignItems: 'center', gap: '15px', fontSize: '0.8rem', color: 'rgba(255,255,255,0.6)' }}>
            {/* Backend Health */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }} title="Backend API Connection">
              <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: systemInfo ? '#4ade80' : '#f87171', boxShadow: '0 0 5px currentColor' }}></div>
              <span>{systemInfo ? 'API Online' : 'API Offline'}</span>
            </div>

            <div style={{ width: '1px', height: '12px', background: 'rgba(255,255,255,0.2)' }}></div>

            {/* GPU & VRAM */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#a5f3fc' }}>
              <Activity size={12} />
              <span style={{ fontWeight: 600 }}>{systemInfo?.gpu || (systemInfo ? 'CPU' : '—')}</span>
            </div>
            <div>{systemInfo?.vram_gb ? `${systemInfo.vram_gb} GB VRAM` : (systemInfo && !systemInfo.cuda ? 'No GPU' : '—')}</div>

            <div style={{ width: '1px', height: '12px', background: 'rgba(255,255,255,0.2)' }}></div>

            {/* Queue Status */}
            {selectedJob?.status === 'processing' ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#fbbf24', fontWeight: 600 }}>
                <Activity size={12} className="spin" />
                <span>Processing...</span>
                <button
                  onClick={(e) => handleCancel(selectedJob.job_id, e)}
                  style={{
                    marginLeft: '5px',
                    background: 'rgba(248, 113, 113, 0.2)',
                    border: '1px solid rgba(248, 113, 113, 0.4)',
                    color: '#fca5a5',
                    borderRadius: '4px',
                    padding: '2px 6px',
                    fontSize: '0.7rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '2px'
                  }}
                  title="Kill Process"
                >
                  KILL TASK
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px', opacity: 0.7 }}>
                <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#94a3b8' }}></div>
                <span>System Idle</span>
              </div>
            )}
          </div>
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
            {/* Options Toggle */}
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
                  <label className="checkbox-item">
                    <input type="checkbox" checked={options.run_vlm} onChange={e => setOptions({ ...options, run_vlm: e.target.checked })} />
                    VLM Visual Analysis
                  </label>
                </div>
                {/* VLM Sub-Options (only show when VLM enabled) */}
                {options.run_vlm && (
                  <div className="vlm-options" style={{
                    marginTop: '1rem',
                    paddingTop: '1rem',
                    borderTop: '1px solid rgba(255,255,255,0.1)',
                    background: 'rgba(100, 150, 255, 0.05)',
                    padding: '1rem',
                    borderRadius: '8px'
                  }}>
                    <div style={{ marginBottom: '0.75rem' }}>
                      <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '600', fontSize: '0.9rem' }}>
                        Vision Model Selection:
                      </label>
                      <select
                        value={options.vlm_model}
                        onChange={e => setOptions({ ...options, vlm_model: e.target.value })}
                        style={{
                          width: '100%',
                          padding: '8px 12px',
                          background: 'rgba(0,0,0,0.3)',
                          border: '2px solid rgba(100, 150, 255, 0.3)',
                          borderRadius: '6px',
                          color: 'inherit',
                          fontSize: '0.9rem',
                          cursor: 'pointer'
                        }}
                      >
                        <option value="llava">LLaVA (default, balanced)</option>
                        <option value="minicpm-v">MiniCPM-V (best for dense text/OCR)</option>
                        <option value="llava:13b">LLaVA 13B (more capable, slower)</option>
                        <option value="llava-phi3">LLaVA-Phi3 (newer architecture)</option>
                        <option value="bakllava">BakLLaVA (alternative)</option>
                      </select>
                    </div>

                    <div style={{
                      fontSize: '0.75rem',
                      lineHeight: '1.4',
                      padding: '0.75rem',
                      background: 'rgba(0,0,0,0.2)',
                      borderRadius: '6px',
                      borderLeft: '3px solid rgba(100, 150, 255, 0.5)'
                    }}>
                      <div style={{ fontWeight: '600', marginBottom: '0.5rem', color: 'rgba(100, 150, 255, 1)' }}>
                        Model Guidance:
                      </div>
                      <div style={{ marginBottom: '0.4rem' }}>
                        <strong>MiniCPM-V:</strong> Use for technical UIs, dashboards, screenshots with dense text. Avoid for simple slides or talking-head videos.
                      </div>
                      <div style={{ marginBottom: '0.4rem' }}>
                        <strong>LLaVA 13B:</strong> Use when accuracy matters more than speed. Avoid if processing many long videos (slow).
                      </div>
                      <div style={{ marginBottom: '0.4rem' }}>
                        <strong>LLaVA (default):</strong> Good all-rounder for training videos, presentations. Fast and reliable.
                      </div>
                      <div style={{ fontSize: '0.7rem', marginTop: '0.5rem', opacity: 0.7 }}>
                        💡 Tip: Test different models on the same video to compare results
                      </div>
                    </div>

                    <small style={{ display: 'block', marginTop: '0.75rem', opacity: 0.6, fontSize: '0.7rem' }}>
                      Requires: ollama pull [model-name] (e.g., ollama pull minicpm-v)
                    </small>
                  </div>
                )}
              </div>
            )}

            <button onClick={handleAnalyze} className="btn-primary" style={{ marginTop: '1rem', width: '100%', justifyContent: 'center' }}>
              <Play size={16} style={{ marginRight: 8 }} /> Analyze
            </button>

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
                    <h2>{selectedJob.file_path?.split('\\').pop() || selectedJob.file_path || 'Unknown'}</h2>
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
                  <div className="preview-container" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                    {/* Default View or Selected Card Content */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                      <h3>{previewData?.title || "Result Preview"}</h3>
                      {/* Mini-spinner if still processing but showing data */}
                      {selectedJob.status === 'processing' && (
                        <div className="mini-status" style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#fbbf24' }}>
                          <Activity size={16} className="spin" />
                          <span style={{ fontSize: '0.8rem' }}>Processing...</span>
                        </div>
                      )}
                    </div>

                    {previewData?.type === 'pdf' ? (
                      <iframe src={previewData.url} className="pdf-preview" title="PDF Report" />
                    ) : (
                      <div className="markdown-content">
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

                  {/* VLM Visual Analysis Card */}
                  {selectedJob.result?.vlm_stats && (
                    <ResultCard
                      title="Visual Analysis"
                      description={`${selectedJob.result.vlm_stats.scenes_detected || 0} scenes, ${selectedJob.result.vlm_stats.corrections_made || 0} corrections`}
                      content={`Analyzed ${selectedJob.result.vlm_stats.keyframes_analyzed || 0} keyframes, extracted ${selectedJob.result.vlm_stats.visual_terms || 0} visual terms`}
                      onShow={() => setPreviewData({
                        title: "VLM Visual Analysis",
                        content: `## Visual Analysis Results\n\n- **Scenes Detected:** ${selectedJob.result.vlm_stats.scenes_detected || 0}\n- **Keyframes Analyzed:** ${selectedJob.result.vlm_stats.keyframes_analyzed || 0}\n- **Visual Terms Extracted:** ${selectedJob.result.vlm_stats.visual_terms || 0}\n- **Transcript Corrections:** ${selectedJob.result.vlm_stats.corrections_made || 0}\n\n*Check output folder for detailed visual.json and corrections.json*`
                      })}
                    />
                  )}

                  {/* Merged Data Card */}
                  {selectedJob.result?.output_dir && (
                    <ResultCard
                      title="Merged Data"
                      description="JSON with all combined data"
                      content="Extended analysis data including subtitles, visual tags, and metadata."
                      onShow={() => handleFilePreview('json', selectedJob.result.output_dir + '\\merged.json', 'Merged Data')}
                    />
                  )}

                  {/* Visual JSON Card */}
                  {selectedJob.result?.output_dir && (
                    <ResultCard
                      title="Visual Data"
                      description="Raw visual analysis JSON"
                      content="Detailed VLM analysis data including scenes, keyframes, and descriptions."
                      onShow={() => handleFilePreview('json', selectedJob.result.output_dir + '\\visual.json', 'Visual Data')}
                    />
                  )}

                  {/* PDF Report Card */}
                  {selectedJob.result?.output_dir && (
                    <ResultCard
                      title="PDF Report"
                      description="Visual summary report"
                      content="Formatted PDF report with keyframes and extracted insights."
                      onShow={() => handleFilePreview('pdf', selectedJob.result.output_dir + '\\report.pdf', 'PDF Report')}
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
