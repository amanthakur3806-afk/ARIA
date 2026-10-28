import { useEffect, useRef, useState } from 'react'
import { ChatComposer } from './ChatComposer'
import { WelcomePanel } from './WelcomePanel'
import { Icon } from '../../components/ui/Icon'
import { FlowchartWidget, MermaidDiagram } from './FlowchartWidget'
import { RagKnowledgeModal } from '../rag/RagKnowledgeModal'
import './ChatPage.css'

export function ChatPage({ isRagModalOpen: propIsOpen, setIsRagModalOpen: propSetIsOpen }) {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [userId, setUserId] = useState('student-1')
  const [sessionId, setSessionId] = useState('thread-1')
  const [localIsOpen, setLocalIsOpen] = useState(false)
  const [chunkCount, setChunkCount] = useState(0)
  const messagesEndRef = useRef(null)

  const isModalOpen = propIsOpen !== undefined ? propIsOpen : localIsOpen
  const setModalOpen = propSetIsOpen || setLocalIsOpen

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  async function updateChunkCount(uid = userId, sid = sessionId) {
    try {
      const res = await fetch(`/api/v1/documents/chunks?user_id=${encodeURIComponent(uid)}&session_id=${encodeURIComponent(sid)}`)
      if (res.ok) {
        const data = await res.json()
        setChunkCount(data.total_chunks || 0)
      }
    } catch (e) {
      console.warn('Failed to fetch chunks:', e)
    }
  }

  useEffect(() => {
    updateChunkCount(userId, sessionId)
  }, [userId, sessionId])

  async function handleSendMessage(text) {
    if (!text || isLoading) return
    setError(null)

    const userMessage = {
      id: `usr_${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    const assistantId = `ast_${Date.now() + 1}`
    const placeholderAssistant = {
      id: assistantId,
      role: 'assistant',
      content: '',
      intent: 'explain_and_plan',
      language: 'en',
      sources: [],
      actions: [],
      structured_data: null,
      latency_profile: null,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      isStreaming: true,
    }

    // Insert user message and assistant placeholder together upfront (immune to React StrictMode)
    setMessages((prev) => [...prev, userMessage, placeholderAssistant])
    setIsLoading(true)

    try {
      const response = await fetch(`/api/v1/chat/threads/${encodeURIComponent(sessionId)}/messages/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          user_id: userId,
          thread_id: sessionId,
          stream: true,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Server returned ${response.status}`)
      }

      const contentType = response.headers.get('content-type') || ''
      const isStream = contentType.includes('text/event-stream') && response.body

      if (isStream) {
        const reader = response.body.getReader()
        const decoder = new TextDecoder('utf-8')
        let buffer = ''
        let streamClosed = false

        // Smooth typewriter pacing queue
        const tokenQueue = []
        let displayedContent = ''
        let pendingStructured = null
        let pendingLatency = null
        let tickerId = null

        // Ticker drains words at human reading pace (25ms interval)
        const startPacer = () => {
          if (tickerId) return
          tickerId = setInterval(() => {
            if (tokenQueue.length > 0) {
              // Smooth dynamic pacing: 1 word if queue is small, scales up if queue is large
              const step = tokenQueue.length > 45 ? 4 : (tokenQueue.length > 15 ? 2 : 1)
              const nextBatch = tokenQueue.splice(0, step).join('')
              displayedContent += nextBatch

              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, content: displayedContent } : m
                )
              )
            } else if (streamClosed) {
              // Queue fully drained and server stream is closed
              clearInterval(tickerId)
              tickerId = null

              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        content: displayedContent,
                        structured_data: pendingStructured || m.structured_data,
                        latency_profile: pendingLatency || m.latency_profile,
                        isStreaming: false,
                      }
                    : m
                )
              )
              setIsLoading(false)
            }
          }, 24)
        }

        startPacer()

        while (!streamClosed) {
          const { value, done } = await reader.read()
          if (done) {
            streamClosed = true
            break
          }

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const rawLine of lines) {
            const line = rawLine.trim()
            if (!line || !line.startsWith('data:')) continue

            const payloadStr = line.replace(/^data:\s*/, '').trim()
            if (payloadStr === '[DONE]') {
              streamClosed = true
              break
            }

            try {
              const event = JSON.parse(payloadStr)
              if (event.type === 'metadata') {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? {
                          ...m,
                          intent: event.intent || m.intent,
                          language: event.language || m.language,
                          sources: event.sources || m.sources,
                        }
                      : m
                  )
                )
              } else if (event.type === 'token') {
                // Break incoming token chunk into individual words and whitespace for natural typewriter rhythm
                const words = (event.content || '').match(/\S+|\s+/g) || []
                for (const w of words) {
                  tokenQueue.push(w)
                }
              } else if (event.type === 'structured_data') {
                pendingStructured = event.structured_data || null
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? {
                          ...m,
                          actions: event.actions || m.actions,
                        }
                      : m
                  )
                )
              } else if (event.type === 'complete') {
                pendingLatency = event.latency_profile || null
              } else if (event.type === 'error') {
                throw new Error(event.message || 'Stream processing error')
              }
            } catch (err) {
              if (err.message && err.message.includes('Stream processing error')) {
                throw err
              }
            }
          }
        }

        // Flush remaining buffer into token queue if present
        if (buffer && buffer.trim().startsWith('data:')) {
          const payloadStr = buffer.trim().replace(/^data:\s*/, '').trim()
          if (payloadStr !== '[DONE]') {
            try {
              const event = JSON.parse(payloadStr)
              if (event.type === 'token') {
                const words = (event.content || '').match(/\S+|\s+/g) || []
                for (const w of words) {
                  tokenQueue.push(w)
                }
              } else if (event.type === 'complete') {
                pendingLatency = event.latency_profile || null
              }
            } catch (e) {}
          }
        }

        streamClosed = true
      } else {
        const data = await response.json()
        const assistantData = data.assistant_message || {}

        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: assistantData.content || 'I processed your request.',
                  intent: assistantData.intent,
                  language: assistantData.language,
                  sources: assistantData.sources || [],
                  actions: assistantData.actions || [],
                  structured_data: assistantData.structured_data || null,
                  latency_profile: assistantData.latency_profile || null,
                  isStreaming: false,
                }
              : m
          )
        )
        setIsLoading(false)
      }
    } catch (err) {
      console.error('Chat error:', err)
      setError(`Connection error: ${err.message}. Ensure backend is running.`)
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: `⚠️ **Unable to connect to ARIA backend.**\n\n*Error details:* ${err.message}\n\nPlease verify that the backend server is running on \`http://127.0.0.1:8000\`.`,
                isError: true,
                isStreaming: false,
              }
            : m
        )
      )
      setIsLoading(false)
    }
  }

  return (
    <section aria-label="Study chat" className="chat-page">
      {/* User & Session & RAG Knowledge Bar */}
      <div className="chat-scope-bar">
        <div className="chat-scope-bar__item">
          <span className="scope-icon">👤</span>
          <span className="scope-label">Student:</span>
          <strong className="scope-val">{userId}</strong>
        </div>
        <div className="chat-scope-bar__divider">•</div>
        <div className="chat-scope-bar__item">
          <span className="scope-icon">📁</span>
          <span className="scope-label">Session:</span>
          <strong className="scope-val">{sessionId}</strong>
        </div>
        <div className="chat-scope-bar__divider">•</div>
        <button
          className="chat-scope-rag-btn"
          onClick={() => setModalOpen(true)}
          title="Open RAG Knowledge Base and DB Chunks Explorer"
          type="button"
        >
          <span>📚 Knowledge Base:</span>
          <strong>{chunkCount} chunks in DB</strong>
          <span className="rag-btn-pill">Manage Notes</span>
        </button>
      </div>

      {messages.length === 0 ? (
        <div className="chat-page__welcome">
          <WelcomePanel
            onSelectSuggestion={handleSendMessage}
            onOpenIngest={() => setModalOpen(true)}
          />
        </div>
      ) : (
        <div className="chat-page__conversation">
          <div className="chat-page__message-list">
            {messages.map((msg) => (
              <MessageItem key={msg.id} message={msg} />
            ))}

            {isLoading && !messages.some((m) => m.isStreaming) && (
              <div className="chat-page__loading-wrap">
                <div className="assistant-avatar">A</div>
                <div className="chat-thinking">
                  <span />
                  <span />
                  <span />
                </div>
                <span className="chat-page__loading-hint">ARIA is synthesizing with RAG & FastMCP...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>
      )}

      {error && <div className="chat-page__error-toast">{error}</div>}

      <div className="chat-page__composer">
        <ChatComposer
          isLoading={isLoading}
          onSend={handleSendMessage}
          onOpenIngest={() => setModalOpen(true)}
        />
      </div>

      {/* RAG Knowledge Base Modal */}
      <RagKnowledgeModal
        isOpen={isModalOpen}
        onClose={() => setModalOpen(false)}
        userId={userId}
        sessionId={sessionId}
        onUserChange={(newUid) => {
          setUserId(newUid)
          updateChunkCount(newUid, sessionId)
        }}
        onSessionChange={(newSid) => {
          setSessionId(newSid)
          updateChunkCount(userId, newSid)
        }}
        onDocumentIngested={() => updateChunkCount(userId, sessionId)}
      />
    </section>
  )
}

function MessageItem({ message }) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="message message--user">
        <div className="message__bubble message__bubble--user">
          <p className="message__text">{message.content}</p>
          <span className="message__time">{message.timestamp}</span>
        </div>
      </div>
    )
  }

  return (
    <div className={`message message--assistant ${message.isError ? 'message--error' : ''}`}>
      <div className="assistant-avatar" aria-hidden="true">A</div>
      <div className="message__content-wrap">
        <div className="message__header">
          <span className="message__author">ARIA Study Assistant</span>
          <span className="message__time">{message.timestamp}</span>
          {message.latency_profile && (
            <span className="message__latency-pill" title="Execution latency">
              ⚡ {message.latency_profile.total_agent_turn_ms}ms · {message.language || 'en'}
            </span>
          )}
        </div>

        <div className="message__bubble message__bubble--assistant">
          {!message.content && message.isStreaming ? (
            <div className="chat-thinking chat-thinking--inline" title="ARIA is synthesizing...">
              <span />
              <span />
              <span />
            </div>
          ) : (
            <MarkdownRenderer text={message.content} />
          )}
          {message.isStreaming && message.content && (
            <span className="streaming-cursor" title="ARIA is writing...">▍</span>
          )}

          {/* Interactive Structured Widgets */}
          {message.structured_data?.flashcards && (
            <FlashcardWidget cards={message.structured_data.flashcards} />
          )}

          {message.structured_data?.questions && (
            <QuizWidget questions={message.structured_data.questions} />
          )}

          {message.structured_data?.flowchart && (
            <FlowchartWidget flowchart={message.structured_data.flowchart} />
          )}

          {message.structured_data?.study_plan && (
            <StudyPlanWidget plan={message.structured_data.study_plan} />
          )}

          {/* RAG Source Citations */}
          {message.sources && message.sources.length > 0 && (
            <SourcesAccordion sources={message.sources} />
          )}
        </div>
      </div>
    </div>
  )
}

// Simple safe Markdown Renderer preserving code blocks & Mermaid diagrams
function MarkdownRenderer({ text }) {
  if (!text) return null

  // Tokenize blocks into code/mermaid fences and normal text to prevent breaking multiline diagrams
  const blocks = []
  const fenceRegex = /```(mermaid|[a-z0-9_-]*)[\r\n]([\s\S]*?)```/gi
  let lastIndex = 0
  let match

  while ((match = fenceRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      blocks.push({ type: 'text', content: text.substring(lastIndex, match.index) })
    }
    const tag = (match[1] || '').toLowerCase().trim()
    blocks.push({
      type: tag === 'mermaid' ? 'mermaid' : 'code',
      lang: tag,
      content: match[2].trim()
    })
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < text.length) {
    blocks.push({ type: 'text', content: text.substring(lastIndex) })
  }

  return (
    <div className="markdown-body">
      {blocks.map((block, bIdx) => {
        if (block.type === 'mermaid') {
          return <MermaidDiagram key={bIdx} code={block.content} />
        }
        if (block.type === 'code') {
          return (
            <pre key={bIdx} className="code-block" style={{ padding: '10px 12px', background: '#1e1e1e', color: '#d4d4d4', borderRadius: '6px', overflowX: 'auto', fontSize: '12px' }}>
              <code>{block.content}</code>
            </pre>
          )
        }

        // Render normal text block split into paragraphs
        const paragraphs = block.content.split(/\r?\n\r?\n/)
        return paragraphs.map((para, pIdx) => {
          const trimmed = para.trim()
          if (!trimmed) return null
          const key = `${bIdx}_${pIdx}`

          if (trimmed.startsWith('### ')) {
            return <h3 key={key}>{trimmed.replace('### ', '')}</h3>
          }
          if (trimmed.startsWith('## ')) {
            return <h2 key={key}>{trimmed.replace('## ', '')}</h2>
          }
          if (trimmed.startsWith('# ')) {
            return <h1 key={key}>{trimmed.replace('# ', '')}</h1>
          }

          // Bullet lists
          if (trimmed.includes('\n• ') || trimmed.includes('\n- ') || trimmed.startsWith('• ') || trimmed.startsWith('- ')) {
            const items = trimmed.split(/\r?\n[•-]\s*/).map((s) => s.replace(/^[•-]\s*/, ''))
            return (
              <ul key={key}>
                {items.map((item, i) => (
                  <li key={i} dangerouslySetInnerHTML={{ __html: formatInline(item) }} />
                ))}
              </ul>
            )
          }

          return <p key={key} dangerouslySetInnerHTML={{ __html: formatInline(trimmed) }} />
        })
      })}
    </div>
  )
}

function formatInline(str) {
  return str
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
}

// Interactive Flashcard Widget
function FlashcardWidget({ cards }) {
  const [currentIdx, setCurrentIdx] = useState(0)
  const [isFlipped, setIsFlipped] = useState(false)

  if (!cards || cards.length === 0) return null
  const card = cards[currentIdx]

  return (
    <div className="flashcard-widget">
      <div className="flashcard-widget__header">
        <span className="flashcard-widget__badge">🗂️ Flashcard Deck ({currentIdx + 1}/{cards.length})</span>
        <span className={`difficulty-badge difficulty-badge--${card.difficulty || 'medium'}`}>
          {card.difficulty || 'medium'}
        </span>
      </div>

      <div
        className={`flashcard-card ${isFlipped ? 'flashcard-card--flipped' : ''}`}
        onClick={() => setIsFlipped(!isFlipped)}
        role="button"
        tabIndex={0}
      >
        <div className="flashcard-card__side flashcard-card__front">
          <span className="card-label">PROMPT / CONCEPT</span>
          <p className="card-content">{card.front}</p>
          <span className="card-hint">Click card to reveal answer 🔄</span>
        </div>
        <div className="flashcard-card__side flashcard-card__back">
          <span className="card-label">EXPLANATION</span>
          <div className="card-content" dangerouslySetInnerHTML={{ __html: formatInline(card.back) }} />
          <span className="card-hint">Click to flip back 🔄</span>
        </div>
      </div>

      <div className="flashcard-widget__controls">
        <button
          className="widget-btn"
          disabled={currentIdx === 0}
          onClick={() => { setCurrentIdx(currentIdx - 1); setIsFlipped(false) }}
          type="button"
        >
          ← Previous
        </button>
        <button
          className="widget-btn"
          disabled={currentIdx === cards.length - 1}
          onClick={() => { setCurrentIdx(currentIdx + 1); setIsFlipped(false) }}
          type="button"
        >
          Next →
        </button>
      </div>
    </div>
  )
}

// Interactive Quiz Widget
function QuizWidget({ questions }) {
  const [selectedAnswers, setSelectedAnswers] = useState({})

  if (!questions || questions.length === 0) return null

  function handleSelect(qId, optIdx) {
    setSelectedAnswers((prev) => ({ ...prev, [qId]: optIdx }))
  }

  return (
    <div className="quiz-widget">
      <div className="quiz-widget__header">
        <span>🎯 Practice Quiz ({questions.length} Questions)</span>
      </div>

      {questions.map((q, qIndex) => {
        const isAnswered = selectedAnswers[q.id] !== undefined
        const selectedOpt = selectedAnswers[q.id]
        const isCorrect = selectedOpt === q.correct_option_index

        return (
          <div key={q.id || qIndex} className="quiz-question-box">
            <p className="quiz-question-text">
              <strong>Q{q.id || qIndex + 1}:</strong> {q.question}
            </p>

            <div className="quiz-options-list">
              {q.options.map((opt, optIdx) => {
                let btnClass = 'quiz-opt-btn'
                if (isAnswered) {
                  if (optIdx === q.correct_option_index) {
                    btnClass += ' quiz-opt-btn--correct'
                  } else if (optIdx === selectedOpt) {
                    btnClass += ' quiz-opt-btn--incorrect'
                  }
                }

                return (
                  <button
                    key={optIdx}
                    className={btnClass}
                    onClick={() => handleSelect(q.id, optIdx)}
                    type="button"
                  >
                    <span className="opt-letter">{String.fromCharCode(65 + optIdx)}</span>
                    <span className="opt-text">{opt}</span>
                  </button>
                )
              })}
            </div>

            {isAnswered && (
              <div className={`quiz-feedback ${isCorrect ? 'quiz-feedback--good' : 'quiz-feedback--retry'}`}>
                <span>{isCorrect ? '✓ Correct!' : '✗ Not quite.'}</span> {q.explanation}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// Interactive Study Plan Widget
function StudyPlanWidget({ plan }) {
  if (!plan || !plan.phases) return null

  return (
    <div className="plan-widget">
      <div className="plan-widget__header">
        <span>🗓️ Revision Plan ({plan.total_duration_minutes || 45} mins total)</span>
      </div>
      <div className="plan-phases">
        {plan.phases.map((p) => (
          <div key={p.phase_number} className="plan-phase-card">
            <div className="phase-card__title-row">
              <span className="phase-badge">Phase {p.phase_number}</span>
              <strong>{p.title}</strong>
              <span className="phase-duration">{p.duration_minutes} min</span>
            </div>
            <p className="phase-desc">{p.description}</p>
            {p.action_items && (
              <ul className="phase-items">
                {p.action_items.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// Expandable RAG Sources Accordion
function SourcesAccordion({ sources }) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="sources-accordion">
      <button
        className="sources-toggle-btn"
        onClick={() => setIsOpen(!isOpen)}
        type="button"
      >
        <span>📚 Verified Course Sources ({sources.length})</span>
        <Icon name="chevron" size={13} className={isOpen ? 'icon--rotated' : ''} />
      </button>

      {isOpen && (
        <div className="sources-list">
          {sources.map((s, idx) => (
            <div key={idx} className="source-card">
              <div className="source-card__title">
                <strong>{s.title || 'Course Material'}</strong>
                {s.section && <span className="source-section"> · {s.section}</span>}
                <span className="source-cid">[{s.chunk_id}]</span>
              </div>
              <p className="source-excerpt">&ldquo;{s.excerpt}&rdquo;</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
