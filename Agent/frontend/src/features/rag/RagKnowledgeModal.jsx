import { useEffect, useState } from 'react'
import './RagKnowledgeModal.css'

const SAMPLE_PRESETS = [
  {
    title: 'Operating Systems - Deadlock & Semaphores',
    session: 'session-os',
    text: `Deadlock Characterization:
A deadlock occurs when processes are unable to proceed because each is waiting on a resource held by another.
Four Coffman conditions must hold simultaneously:
1. Mutual Exclusion: At least one resource must be held in a non-shareable mode.
2. Hold and Wait: A process must be holding at least one resource and waiting to acquire additional resources.
3. No Preemption: Resources cannot be preempted; a resource can only be released voluntarily by the process holding it.
4. Circular Wait: A closed chain of processes exists such that each process holds at least one resource needed by the next process.

Semaphores:
A semaphore S is an integer variable accessed only through wait() and signal() atomic operations.
Binary semaphores act as mutex locks to protect critical sections.`
  },
  {
    title: 'Database Systems - ACID & Indexing',
    session: 'session-db',
    text: `Relational Database Core Concepts:
ACID Properties:
- Atomicity: All transactions either complete entirely or are fully rolled back.
- Consistency: State transitions preserve database integrity constraints.
- Isolation: Concurrent transactions execute independently without interference.
- Durability: Once a transaction is committed, changes survive system failure.

B-Tree Indexing:
B-Trees provide balanced O(log n) lookups, insertions, and range scans.
Clustered indexes define the physical order of rows on disk, while non-clustered indexes contain pointers to table records.`
  },
  {
    title: 'Computer Networks - TCP vs UDP',
    session: 'session-net',
    text: `Transport Layer Protocols:
TCP (Transmission Control Protocol):
- Connection-oriented with 3-way handshake (SYN, SYN-ACK, ACK).
- Guarantees ordered delivery, error checking, flow control (sliding window), and congestion control.

UDP (User Datagram Protocol):
- Connectionless and lightweight with minimal header overhead (8 bytes).
- Unreliable delivery without retransmission; ideal for real-time gaming, DNS, and video streaming.`
  }
]

export function RagKnowledgeModal({
  isOpen,
  onClose,
  userId = 'student-1',
  sessionId = 'thread-1',
  onUserChange,
  onSessionChange,
  onDocumentIngested,
}) {
  const [activeTab, setActiveTab] = useState('ingest') // 'ingest' | 'explorer'
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [sessionInput, setSessionInput] = useState(sessionId)
  const [selectedFileName, setSelectedFileName] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [statusMessage, setStatusMessage] = useState(null)

  // Explorer State
  const [chunks, setChunks] = useState([])
  const [isLoadingChunks, setIsLoadingChunks] = useState(false)
  const [filterSession, setFilterSession] = useState('')
  const [dbStats, setDbStats] = useState(null)

  useEffect(() => {
    setSessionInput(sessionId)
  }, [sessionId])

  useEffect(() => {
    if (isOpen) {
      loadChunks()
      fetchHealthStats()
    }
  }, [isOpen, userId, filterSession])

  async function fetchHealthStats() {
    try {
      const res = await fetch('/api/health')
      if (res.ok) {
        const data = await res.json()
        setDbStats(data.rag_store)
      }
    } catch (e) {
      console.warn('Failed to fetch health stats:', e)
    }
  }

  async function loadChunks() {
    setIsLoadingChunks(true)
    try {
      let url = `/api/v1/documents/chunks?user_id=${encodeURIComponent(userId)}`
      if (filterSession) {
        url += `&session_id=${encodeURIComponent(filterSession)}`
      }
      const res = await fetch(url)
      if (res.ok) {
        const data = await res.json()
        setChunks(data.chunks || [])
      }
    } catch (err) {
      console.error('Error loading chunks:', err)
    } finally {
      setIsLoadingChunks(false)
    }
  }

  function handleFileUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setSelectedFileName(file.name)
    if (!title) {
      setTitle(file.name.replace(/\.[^/.]+$/, ''))
    }
    const reader = new FileReader()
    reader.onload = (event) => {
      setText(event.target.result || '')
    }
    reader.readAsText(file)
  }

  async function handleIngest(e) {
    e.preventDefault()
    if (!text.trim()) return

    setIsSubmitting(true)
    setStatusMessage(null)

    try {
      const res = await fetch('/api/v1/documents/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: title.trim() || selectedFileName || 'Uploaded Study Notes',
          text: text.trim(),
          user_id: userId,
          session_id: sessionInput.trim() || 'thread-1',
        }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || 'Ingestion failed')
      }

      const data = await res.json()
      setStatusMessage({
        type: 'success',
        text: `Successfully indexed ${data.chunks_indexed} chunk(s) into database for student "${data.user_id}" in session "${data.session_id}". Total database chunks: ${data.user_total_chunks}. Grounded queries are now active!`,
      })

      // Clear form & refresh
      setTitle('')
      setText('')
      setSelectedFileName('')
      loadChunks()
      fetchHealthStats()
      if (onDocumentIngested) onDocumentIngested(data)
    } catch (err) {
      setStatusMessage({
        type: 'error',
        text: `Ingestion failed: ${err.message}`,
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleDeleteDocument(docId) {
    if (!confirm('Are you sure you want to remove this document and its chunks from the database?')) {
      return
    }
    try {
      const res = await fetch(`/api/v1/documents/${encodeURIComponent(docId)}?user_id=${encodeURIComponent(userId)}`, {
        method: 'DELETE',
      })
      if (res.ok) {
        loadChunks()
        fetchHealthStats()
      }
    } catch (err) {
      alert(`Delete error: ${err.message}`)
    }
  }

  function applyPreset(preset) {
    setTitle(preset.title)
    setSessionInput(preset.session)
    setText(preset.text)
    setSelectedFileName('')
    if (onSessionChange) onSessionChange(preset.session)
  }

  if (!isOpen) return null

  return (
    <div className="rag-modal-overlay" onClick={onClose}>
      <div className="rag-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="rag-modal__header">
          <div className="rag-modal__title-wrap">
            <div className="rag-modal__icon-badge">📚</div>
            <div>
              <h2 className="rag-modal__title">RAG Knowledge Base & Document Ingestion</h2>
              <p className="rag-modal__subtitle">
                Upload or paste study materials to persist chunks into your user-isolated database
              </p>
            </div>
          </div>
          <button className="rag-modal__close-btn" onClick={onClose} type="button">
            ✕
          </button>
        </div>

        {/* User & Session Scope Strip */}
        <div className="rag-modal__scope-bar">
          <div className="scope-pill-group">
            <span className="scope-pill-label">👤 Active Student:</span>
            <select
              className="scope-select"
              value={userId}
              onChange={(e) => onUserChange && onUserChange(e.target.value)}
            >
              <option value="student-1">student-1 (Primary)</option>
              <option value="student-2">student-2 (Secondary)</option>
              <option value="student_alice">student_alice</option>
              <option value="student_bob">student_bob</option>
            </select>
          </div>

          <div className="scope-pill-group">
            <span className="scope-pill-label">📁 Target Session:</span>
            <input
              className="scope-select"
              type="text"
              value={sessionInput}
              onChange={(e) => {
                setSessionInput(e.target.value)
                if (onSessionChange) onSessionChange(e.target.value)
              }}
              placeholder="e.g. session-os"
              style={{ width: '130px' }}
            />
          </div>

          <div className="scope-stat-pill">
            🗄️ {chunks.length} chunks in DB for {userId}
          </div>
        </div>

        {/* Tabs */}
        <div className="rag-modal__tabs">
          <button
            className={`rag-tab-btn ${activeTab === 'ingest' ? 'rag-tab-btn--active' : ''}`}
            onClick={() => setActiveTab('ingest')}
            type="button"
          >
            📥 Upload & Ingest Notes
          </button>
          <button
            className={`rag-tab-btn ${activeTab === 'explorer' ? 'rag-tab-btn--active' : ''}`}
            onClick={() => setActiveTab('explorer')}
            type="button"
          >
            🔍 Database Chunks Explorer ({chunks.length})
          </button>
        </div>

        {/* Body */}
        <div className="rag-modal__body">
          {activeTab === 'ingest' && (
            <form className="ingest-form" onSubmit={handleIngest}>
              {statusMessage && (
                <div className={`rag-status-alert rag-status-alert--${statusMessage.type}`}>
                  {statusMessage.type === 'success' ? '✓' : '⚠️'} {statusMessage.text}
                </div>
              )}

              {/* File Upload Box */}
              <div className="form-group">
                <label className="form-label">Upload a Data File (.txt, .md, .json)</label>
                <div className="file-drop-zone">
                  <label className="file-drop-label">
                    <span className="file-drop-icon">📁</span>
                    <div className="file-drop-text">
                      <strong>Choose a file from your computer</strong>
                      <span>Supports .txt, .md, .json notes & lecture files</span>
                    </div>
                    <input
                      type="file"
                      accept=".txt,.md,.json,.csv,.pdf"
                      onChange={handleFileUpload}
                      style={{ display: 'none' }}
                    />
                  </label>
                  {selectedFileName && (
                    <div className="selected-file-badge">
                      <span>📄 Selected: <strong>{selectedFileName}</strong></span>
                      <button
                        type="button"
                        className="file-remove-btn"
                        onClick={() => { setSelectedFileName(''); setText(''); }}
                      >
                        ✕ Remove
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Presets */}
              <div className="sample-presets">
                <span className="sample-presets-label">⚡ Or Choose a Quick Sample Preset:</span>
                {SAMPLE_PRESETS.map((p, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="sample-pill-btn"
                    onClick={() => applyPreset(p)}
                  >
                    + {p.title.split(' - ')[1] || p.title}
                  </button>
                ))}
              </div>

              <div className="form-group">
                <label className="form-label">Document Title</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Operating Systems - Virtual Memory & Page Tables"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Study Notes / Curriculum Content</label>
                <textarea
                  className="form-textarea"
                  placeholder="Paste your study notes, textbook excerpts, or lecture transcripts here. ARIA will automatically extract semantic chunks and persist them into the user-scoped SQLite database."
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  rows={8}
                  required
                />
              </div>

              {/* Prominent Ingest Button */}
              <button
                type="submit"
                className="submit-ingest-btn"
                disabled={isSubmitting || !text.trim()}
              >
                {isSubmitting ? '⏳ Indexing into Database...' : '🚀 Ingest Chunks into Database'}
              </button>
            </form>
          )}

          {activeTab === 'explorer' && (
            <div className="chunks-explorer">
              <div className="chunks-filter-bar">
                <span>
                  Showing chunks for <strong>{userId}</strong>
                  {filterSession ? ` in session "${filterSession}"` : ' across all sessions'}
                </span>
                <select
                  className="scope-select"
                  value={filterSession}
                  onChange={(e) => setFilterSession(e.target.value)}
                >
                  <option value="">All Sessions</option>
                  <option value="thread-1">thread-1</option>
                  <option value="session-os">session-os</option>
                  <option value="session-db">session-db</option>
                  <option value="session-net">session-net</option>
                </select>
              </div>

              {isLoadingChunks ? (
                <p style={{ textAlign: 'center', color: '#94a3b8' }}>Loading chunks from database...</p>
              ) : chunks.length === 0 ? (
                <div className="empty-chunks-placeholder">
                  <div className="empty-chunks-icon">📂</div>
                  <p>No study chunks stored in the database for this student & session yet.</p>
                  <p style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '4px' }}>
                    ARIA will reply with a prompt to upload data until you ingest notes here.
                  </p>
                  <button
                    className="submit-ingest-btn"
                    style={{ margin: '1rem auto 0', display: 'inline-flex' }}
                    onClick={() => setActiveTab('ingest')}
                    type="button"
                  >
                    Ingest your first document
                  </button>
                </div>
              ) : (
                <div className="chunk-card-list">
                  {chunks.map((chk) => (
                    <div key={chk.chunk_id} className="rag-chunk-card">
                      <div className="chunk-card__header">
                        <div className="chunk-badge-group">
                          <span className="chunk-title-tag">{chk.title}</span>
                          <span className="chunk-section-tag">{chk.section}</span>
                          <span className="chunk-meta-tag">session: {chk.session_id}</span>
                          <span className="chunk-meta-tag">{chk.word_count} words</span>
                          <span className="chunk-meta-tag">[{chk.chunk_id}]</span>
                        </div>
                        <button
                          className="chunk-delete-btn"
                          onClick={() => handleDeleteDocument(chk.document_id)}
                          title="Delete entire document and its chunks"
                          type="button"
                        >
                          Delete Doc
                        </button>
                      </div>
                      <p className="chunk-text-preview">{chk.text}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
