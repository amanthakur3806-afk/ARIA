import { useEffect, useState } from 'react'
import './RagKnowledgeModal.css'

const SAMPLE_PRESETS = [
  {
    title: 'Operating Systems (OS) - Virtual Memory & Deadlocks',
    session: 'session-os',
    text: `Operating Systems Core Curriculum:
Deadlock Characterization:
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
    title: 'Database Management Systems (DBMS) - ACID & Indexing',
    session: 'session-db',
    text: `Database Management Systems (DBMS) Core Concepts:
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
    title: 'Computer Networks (CN) - TCP vs UDP',
    session: 'session-net',
    text: `Computer Networks Protocol Fundamentals:
TCP (Transmission Control Protocol):
- Connection-oriented with 3-way handshake (SYN, SYN-ACK, ACK).
- Guarantees ordered delivery, error checking, flow control (sliding window), and congestion control.

UDP (User Datagram Protocol):
- Connectionless and lightweight with minimal header overhead (8 bytes).
- Unreliable delivery without retransmission; ideal for real-time gaming, DNS, and video streaming.`
  }
]

function readTextFile(file, onLoad, onError) {
  const reader = new FileReader()
  reader.onload = (event) => {
    onLoad(typeof event.target?.result === 'string' ? event.target.result : '')
  }
  reader.onerror = onError
  reader.readAsText(file)
  return reader
}

export function RagKnowledgeModal({
  isOpen,
  onClose,
  initialTab = 'library',
  fileToIngest,
  userId = 'student-1',
  sessionId = 'thread-1',
  onUserChange,
  onSessionChange,
  onDocumentIngested,
}) {
  const [activeTab, setActiveTab] = useState(initialTab || 'library') // 'library' | 'ingest'
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [sessionInput, setSessionInput] = useState(sessionId)
  const [selectedFile, setSelectedFile] = useState(null)
  const [selectedFileName, setSelectedFileName] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [statusMessage, setStatusMessage] = useState(null)

  // Document Library state
  const [documents, setDocuments] = useState([])
  const [isLoadingDocs, setIsLoadingDocs] = useState(false)
  const [docFilter, setDocFilter] = useState('')

  useEffect(() => {
    setSessionInput(sessionId)
  }, [sessionId])

  useEffect(() => {
    if (isOpen) {
      setActiveTab(initialTab || 'library')
      loadDocuments()
    }
  }, [isOpen, initialTab, userId])

  useEffect(() => {
    if (!isOpen || !fileToIngest) return undefined

    setActiveTab('ingest')
    handleFileSelected(fileToIngest)
  }, [fileToIngest, isOpen])

  async function loadDocuments() {
    setIsLoadingDocs(true)
    try {
      const res = await fetch(`/api/v1/documents?user_id=${encodeURIComponent(userId)}`)
      if (res.ok) {
        const data = await res.json()
        setDocuments(data.documents || [])
      }
    } catch (err) {
      console.warn('Error loading documents:', err)
    } finally {
      setIsLoadingDocs(false)
    }
  }

  function handleFileSelected(file) {
    if (!file) return

    const MAX_SIZE = 10 * 1024 * 1024
    if (file.size > MAX_SIZE) {
      setStatusMessage({
        type: 'error',
        text: `File "${file.name}" is too large (${(file.size / (1024 * 1024)).toFixed(1)} MB). Maximum allowed size is 10 MB.`,
      })
      return
    }

    setSelectedFile(file)
    setSelectedFileName(file.name)
    setStatusMessage(null)

    if (!title.trim()) {
      setTitle(file.name.replace(/\.[^/.]+$/, ''))
    }

    const isPdf = file.name.toLowerCase().endsWith('.pdf')
    if (isPdf) {
      setText(`[PDF Document Attached: "${file.name}" (${(file.size / 1024).toFixed(1)} KB)]\n\nText will be parsed and indexed into your study library when you click Save & Index.`)
    } else {
      readTextFile(
        file,
        (cleanText) => setText(cleanText.replace(/\0/g, '')),
        () => setStatusMessage({ type: 'error', text: `Failed to read file "${file.name}".` }),
      )
    }
  }

  function handleFileInputChange(e) {
    const file = e.target.files?.[0]
    if (file) {
      handleFileSelected(file)
    }
    e.target.value = ''
  }

  function handleRemoveFile() {
    setSelectedFile(null)
    setSelectedFileName('')
    setText('')
  }

  function handleDragOver(e) {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }

  function handleDragLeave(e) {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }

  function handleDrop(e) {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
    const files = e.dataTransfer.files
    if (files && files.length > 0) {
      handleFileSelected(files[0])
    }
  }

  async function handleIngest(e) {
    e.preventDefault()

    const hasFile = Boolean(selectedFile)
    const hasText = Boolean(text.trim())

    if (!hasFile && !hasText) {
      setStatusMessage({
        type: 'error',
        text: 'Please select a document file or enter study notes before indexing.',
      })
      return
    }

    setIsSubmitting(true)
    setStatusMessage(null)

    try {
      let data
      if (hasFile) {
        const formData = new FormData()
        formData.append('file', selectedFile)
        formData.append('user_id', userId)
        formData.append('session_id', sessionInput.trim() || 'thread-1')
        if (title.trim()) {
          formData.append('title', title.trim())
        }

        const res = await fetch('/api/v1/documents/upload', {
          method: 'POST',
          body: formData,
        })

        if (!res.ok) {
          const err = await res.json().catch(() => ({}))
          throw new Error(err.detail || `Upload failed (Status ${res.status})`)
        }
        data = await res.json()
      } else {
        const res = await fetch('/api/v1/documents/ingest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: title.trim() || 'Uploaded Study Notes',
            text: text.trim(),
            user_id: userId,
            session_id: sessionInput.trim() || 'thread-1',
          }),
        })

        if (!res.ok) {
          const err = await res.json().catch(() => ({}))
          throw new Error(err.detail || `Ingestion failed (Status ${res.status})`)
        }
        data = await res.json()
      }

      setStatusMessage({
        type: 'success',
        text: `Indexed "${data.title}" successfully (${data.chunks_indexed} passage${data.chunks_indexed === 1 ? '' : 's'}). Ready for grounded study chat!`,
      })

      // Reset form and reload documents
      setTitle('')
      setText('')
      setSelectedFile(null)
      setSelectedFileName('')
      loadDocuments()

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
    if (!confirm('Are you sure you want to remove this document from your library?')) {
      return
    }
    try {
      const res = await fetch(`/api/v1/documents/${encodeURIComponent(docId)}?user_id=${encodeURIComponent(userId)}`, {
        method: 'DELETE',
      })
      if (res.ok) {
        loadDocuments()
      }
    } catch (err) {
      alert(`Delete error: ${err.message}`)
    }
  }

  function applyPreset(preset) {
    setSelectedFile(null)
    setSelectedFileName('')
    setTitle(preset.title)
    setSessionInput(preset.session)
    setText(preset.text)
    if (onSessionChange) onSessionChange(preset.session)
  }

  if (!isOpen) return null

  const filteredDocs = documents.filter((doc) => {
    if (!docFilter.trim()) return true
    const q = docFilter.toLowerCase()
    return (
      (doc.title && doc.title.toLowerCase().includes(q)) ||
      (doc.session_id && doc.session_id.toLowerCase().includes(q))
    )
  })

  return (
    <div
      className="rag-modal-overlay"
      onClick={onClose}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => e.preventDefault()}
    >
      <div className="rag-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="rag-modal__header">
          <div className="rag-modal__title-wrap">
            <div className="rag-modal__icon-badge">📚</div>
            <div>
              <h2 className="rag-modal__title">Study Library & Document Ingestion</h2>
              <p className="rag-modal__subtitle">
                Browse ingested course topics and upload materials for grounded AI answers
              </p>
            </div>
          </div>
          <button className="rag-modal__close-btn" onClick={onClose} type="button">
            ✕
          </button>
        </div>

        {/* Clean Status Strip */}
        <div className="rag-modal__scope-bar">
          <div className="scope-pill-group">
            <span className="scope-pill-label">🎓 Student Workspace:</span>
            <strong style={{ color: 'var(--color-green-dark, #345941)' }}>{userId}</strong>
          </div>
          <div className="scope-stat-pill">
            📖 {documents.length} Course Document{documents.length === 1 ? '' : 's'} Active
          </div>
        </div>

        {/* Professional Segmented Tabs */}
        <div className="rag-modal__tabs">
          <button
            className={`rag-tab-btn ${activeTab === 'library' ? 'rag-tab-btn--active' : ''}`}
            onClick={() => setActiveTab('library')}
            type="button"
          >
            <span>📚 My Library</span>
            <span className="rag-tab-count">{documents.length}</span>
          </button>
          <button
            className={`rag-tab-btn ${activeTab === 'ingest' ? 'rag-tab-btn--active' : ''}`}
            onClick={() => setActiveTab('ingest')}
            type="button"
          >
            <span>📥 Ingest New Material</span>
          </button>
        </div>

        {/* Body */}
        <div className="rag-modal__body">
          {activeTab === 'library' && (
            <div className="library-view">
              <div className="library-toolbar">
                <input
                  type="text"
                  className="library-search-input"
                  placeholder="Filter documents (e.g. OS, DBMS, Networks)..."
                  value={docFilter}
                  onChange={(e) => setDocFilter(e.target.value)}
                />
                <button
                  type="button"
                  className="library-add-btn"
                  onClick={() => setActiveTab('ingest')}
                >
                  ➕ Ingest Notes
                </button>
              </div>

              {isLoadingDocs ? (
                <p className="library-loading">Loading study library...</p>
              ) : filteredDocs.length === 0 ? (
                <div className="empty-chunks-placeholder">
                  <div className="empty-chunks-icon">📚</div>
                  <p>No documents found matching "{docFilter}".</p>
                  <button
                    className="submit-ingest-btn"
                    style={{ margin: '1rem auto 0', display: 'inline-flex' }}
                    onClick={() => setActiveTab('ingest')}
                    type="button"
                  >
                    Ingest notes now
                  </button>
                </div>
              ) : (
                <div className="doc-card-list">
                  {filteredDocs.map((doc) => {
                    const docId = doc.doc_id || doc.id
                    const isCurriculum = doc.user_id === 'default_curriculum'
                    return (
                      <div key={docId} className="doc-card">
                        <div className="doc-card__left">
                          <span className="doc-card__icon">📘</span>
                          <div className="doc-card__info">
                            <div className="doc-card__title-row">
                              <h3 className="doc-card__title">{doc.title}</h3>
                              {isCurriculum && (
                                <span className="doc-curriculum-pill">Core Curriculum</span>
                              )}
                            </div>
                            <div className="doc-card__meta">
                              <span>📁 Session: {doc.session_id || 'default'}</span>
                              <span>•</span>
                              <span>🧩 {doc.chunk_count || 10} passages indexed</span>
                              <span>•</span>
                              <span className="doc-status-active">✓ Active in RAG</span>
                            </div>
                          </div>
                        </div>

                        {!isCurriculum && (
                          <button
                            type="button"
                            className="doc-delete-btn"
                            onClick={() => handleDeleteDocument(docId)}
                            title="Delete this document and all its chunks"
                          >
                            🗑️ Delete
                          </button>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {activeTab === 'ingest' && (
            <form className="ingest-form" onSubmit={handleIngest}>
              {statusMessage && (
                <div className={`rag-status-alert rag-status-alert--${statusMessage.type}`}>
                  {statusMessage.type === 'success' ? '✓' : '⚠️'} {statusMessage.text}
                </div>
              )}

              {/* Presets at top for rapid testing */}
              <div className="sample-presets">
                <span className="sample-presets-label">⚡ Quick Presets:</span>
                {SAMPLE_PRESETS.map((p, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="sample-pill-btn"
                    onClick={() => applyPreset(p)}
                  >
                    + {p.title.split(' - ')[0] || p.title}
                  </button>
                ))}
              </div>

              {/* File Upload Box with Drag & Drop */}
              <div className="form-group">
                <label className="form-label">Upload Document File (.pdf, .txt, .md, .csv)</label>
                <div
                  className={`file-drop-zone ${isDragging ? 'file-drop-zone--dragging' : ''}`}
                  onDragOver={handleDragOver}
                  onDragEnter={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                >
                  <label className="file-drop-label">
                    <span className="file-drop-icon">📁</span>
                    <div className="file-drop-text">
                      <strong>Choose a file from your computer or drag & drop here</strong>
                      <span>Supports PDF slides, textbook chapters, and Markdown notes (up to 10 MB)</span>
                    </div>
                    <input
                      type="file"
                      accept=".pdf,.txt,.md,.json,.csv"
                      onChange={handleFileInputChange}
                      style={{ display: 'none' }}
                    />
                  </label>
                  {selectedFileName && (
                    <div className="selected-file-badge">
                      <span>📄 Selected: <strong>{selectedFileName}</strong> {selectedFile ? `(${(selectedFile.size / 1024).toFixed(1)} KB)` : ''}</span>
                      <button
                        type="button"
                        className="file-remove-btn"
                        onClick={handleRemoveFile}
                      >
                        ✕ Remove
                      </button>
                    </div>
                  )}
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Document Title (e.g. Operating Systems, DBMS)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Operating Systems (OS) or DBMS"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </div>

              <div className="form-group">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <label className="form-label">Study Notes / Curriculum Content</label>
                  {selectedFile && selectedFile.name.toLowerCase().endsWith('.pdf') && (
                    <span style={{ fontSize: '0.78rem', color: 'var(--color-green-dark, #345941)', fontWeight: 600 }}>
                      ⚡ PDF Attached: Text will be parsed and indexed on submission
                    </span>
                  )}
                </div>
                <textarea
                  className="form-textarea"
                  placeholder="Paste your study notes, lecture transcripts, or textbook excerpts here, or upload a document file above."
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  rows={7}
                  readOnly={Boolean(selectedFile && selectedFile.name.toLowerCase().endsWith('.pdf'))}
                  required={!selectedFile}
                />
              </div>

              <button
                type="submit"
                aria-busy={isSubmitting}
                className={`submit-ingest-btn${isSubmitting ? ' submit-ingest-btn--loading' : ''}`}
                disabled={isSubmitting || !text.trim()}
              >
                {isSubmitting && <span aria-hidden="true" className="submit-ingest-btn__spinner" />}
                <span>{isSubmitting ? 'Indexing notes into library...' : 'Save & Index Document into Library'}</span>
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
