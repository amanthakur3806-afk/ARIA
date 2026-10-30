import { useEffect, useRef, useState } from 'react'

import { ChatComposer } from './ChatComposer'

import { WelcomePanel } from './WelcomePanel'

import { Icon } from '../../components/ui/Icon'

import { FlowchartWidget, MermaidDiagram } from './FlowchartWidget'

import { RagKnowledgeModal } from '../rag/RagKnowledgeModal'

import './ChatPage.css'



async function readChatStream(response, onToken, onComplete, onStructuredData) {

  if (!response.body) {

    throw new Error('The server did not provide a streaming response.')

  }



  const reader = response.body.getReader()

  const decoder = new TextDecoder()

  let buffer = ''

  let completed = false



  function dispatchEvent(rawEvent) {

    let eventName = ''

    const dataLines = []

    for (const line of rawEvent.split('\n')) {

      if (line.startsWith('event:')) eventName = line.slice(6).trim()

      if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())

    }



    if (!dataLines.length) return

    const eventData = JSON.parse(dataLines.join('\n'))

    if (eventName === 'token') onToken(eventData.content)

    if (eventName === 'structured_data' && onStructuredData) onStructuredData(eventData.structured_data)

    if (eventName === 'error') throw new Error(eventData.detail || 'The response stream failed.')

    if (eventName === 'complete') {

      completed = true

      onComplete(eventData)

    }

  }



  try {

    while (true) {

      const { value, done } = await reader.read()

      buffer += decoder.decode(value, { stream: !done })

      buffer = buffer.replace(/\r\n/g, '\n')



      let eventBoundary = buffer.indexOf('\n\n')

      while (eventBoundary !== -1) {

        dispatchEvent(buffer.slice(0, eventBoundary))

        buffer = buffer.slice(eventBoundary + 2)

        eventBoundary = buffer.indexOf('\n\n')

      }



      if (done) break

    }



    if (buffer.trim()) dispatchEvent(buffer)

    if (!completed) throw new Error('The response stream ended before completion.')

  } finally {

    reader.releaseLock()

  }

}



export function ChatPage({

  isRagModalOpen: propIsOpen,

  setIsRagModalOpen: propSetIsOpen,

  activeSessionId,

  onRefreshThreads,

  userId: propUserId,
  initialRagTab = 'library',

}) {

  const [messages, setMessages] = useState([])

  const [isLoading, setIsLoading] = useState(false)

  const [error, setError] = useState(null)

  const userId = propUserId || 'student-1'

  const sessionId = activeSessionId || 'thread-1'

  const [currentTitle, setCurrentTitle] = useState('')

  const [localIsOpen, setLocalIsOpen] = useState(false)

  const [fileToIngest, setFileToIngest] = useState(null)

  const messagesEndRef = useRef(null)



  const isModalOpen = propIsOpen !== undefined ? propIsOpen : localIsOpen

  const setModalOpen = propSetIsOpen || setLocalIsOpen



  function handleOpenIngest(file) {

    if (file) setFileToIngest(file)

    setModalOpen(true)

  }



  function handleCloseIngest() {

    setFileToIngest(null)

    setModalOpen(false)

  }



  useEffect(() => {

    const isStreaming = messages.some((message) => message.isStreaming)

    messagesEndRef.current?.scrollIntoView({ behavior: isStreaming ? 'auto' : 'smooth' })

  }, [messages, isLoading])

  async function loadChatHistory(uid = userId, sid = sessionId) {

    try {

      const res = await fetch(`/api/v1/chat/threads/${encodeURIComponent(sid)}/messages?user_id=${encodeURIComponent(uid)}`)

      if (res.ok) {

        const data = await res.json()

        if (data.title) {

          setCurrentTitle(data.title)

        }

        if (Array.isArray(data.messages)) {

          setMessages(data.messages)

        }

      }

    } catch (e) {

      console.warn('Failed to load chat history:', e)

    }

  }



  async function handleClearChat() {

    if (!window.confirm('Are you sure you want to clear this conversation history?')) return

    try {

      const res = await fetch(`/api/v1/chat/threads/${encodeURIComponent(sessionId)}/messages?user_id=${encodeURIComponent(userId)}`, {

        method: 'DELETE',

      })

      if (res.ok) {

        setMessages([])

      }

    } catch (e) {

      console.warn('Failed to clear chat:', e)

    }

  }



  useEffect(() => {


    loadChatHistory(userId, sessionId)

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

    const assistantMessageId = `ast_${Date.now()}`



    setMessages((prev) => [...prev, userMessage, {

      id: assistantMessageId,

      role: 'assistant',

      content: '',

      isStreaming: true,

      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),

    }])

    setIsLoading(true)



    try {

      const response = await fetch(`/api/v1/chat/threads/${encodeURIComponent(sessionId)}/messages/stream`, {

        method: 'POST',

        headers: {

          'Content-Type': 'application/json',

          Accept: 'text/event-stream',

        },

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



      await readChatStream(

        response,

        (content) => {

          setMessages((prev) => prev.map((message) => (

            message.id === assistantMessageId

              ? { ...message, content: message.content + content }

              : message

          )))

        },

        (data) => {

          const assistantData = data.assistant_message || {}

          if (data.thread_title) {

            setCurrentTitle(data.thread_title)

          }

          setMessages((prev) => prev.map((message) => (

            message.id === assistantMessageId

              ? {

                  ...message,

                  ...assistantData,

                  id: assistantData.id || assistantMessageId,

                  role: 'assistant',

                  content: assistantData.content || message.content || '',

                  structured_data: assistantData.structured_data || message.structured_data,

                  isStreaming: false,

                  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),

                }

              : message

          )))

          if (onRefreshThreads) {

            onRefreshThreads()

          }

        },

        (structuredData) => {

          setMessages((prev) => prev.map((message) => (

            message.id === assistantMessageId

              ? { ...message, structured_data: structuredData }

              : message

          )))

        },

      )

    } catch (err) {

      console.error('Chat error:', err)

      setError(`Chat request failed: ${err.message}`)

      setMessages((prev) => prev.map((message) => (

        message.id === assistantMessageId

          ? {

              ...message,

              content: `⚠️ **Unable to complete this response.**\n\n*Error details:* ${err.message}`,

              isError: true,

              isStreaming: false,

            }

          : message

      )))

    } finally {

      setIsLoading(false)

    }

  }



  return (

    <section aria-label="Study chat" className="chat-page">

      {messages.length === 0 ? (

        <div className="chat-page__welcome">

          <WelcomePanel

            onSelectSuggestion={handleSendMessage}

            onOpenIngest={() => handleOpenIngest()}

          />

        </div>

      ) : (

        <div className="chat-page__conversation">

          <div className="chat-page__message-list">

            {messages.map((msg) => (

              <MessageItem key={msg.id} message={msg} />

            ))}



            {isLoading && !messages.some((message) => message.isStreaming && message.content) && (

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

          onOpenIngest={handleOpenIngest}

        />

      </div>



      {/* RAG Knowledge Base Modal */}

      <RagKnowledgeModal
        initialTab={initialRagTab}

        isOpen={isModalOpen}

        onClose={handleCloseIngest}

        userId={userId}

        sessionId={sessionId}

        fileToIngest={fileToIngest}

        onUserChange={(newUid) => {

          setUserId(newUid)


          loadChatHistory(newUid, sessionId)

        }}

        onSessionChange={(newSid) => {

          setSessionId(newSid)


          loadChatHistory(userId, newSid)

        }}

        onDocumentIngested={(data) => {

          if (data?.session_id) {

            setSessionId(data.session_id)


          } else {


          }

        }}

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

          <span className="message__author">ARIA</span>

          <span className="message__time">{message.timestamp}</span>

          {message.latency_profile && (

            <span className="message__latency-pill" title="Execution latency">

              ⚡ {message.latency_profile.total_agent_turn_ms}ms · {message.language || 'en'}

            </span>

          )}

        </div>



        <div className="message__bubble message__bubble--assistant">

          <MarkdownRenderer text={message.content} isStreaming={message.isStreaming} />



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



          {/* Render interactive study plan widget only if text doesn't already detail the phases */}

          {message.structured_data?.study_plan && !isPlanAlreadyInText(message.content) && (

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



// Helper to detect if markdown content already contains full multi-phase study plan

function isPlanAlreadyInText(content) {

  if (!content) return false

  const lower = content.toLowerCase()

  return (

    (lower.includes('phase 1') && lower.includes('phase 2')) ||

    (lower.includes('week 1') && lower.includes('week 2')) ||

    (lower.includes('stage 1') && lower.includes('stage 2'))

  )

}



function formatInline(str) {

  if (!str) return ''

  return str

    // Sanitize raw HTML tags to prevent XSS except formatting

    .replace(/&/g, '&amp;')

    .replace(/</g, '&lt;')

    .replace(/>/g, '&gt;')

    // Bracketed citations: [Source X]

    .replace(/\[Source\s+(\d+)\]/gi, '<span class="source-citation-tag" title="Verified Course Material Source">[Source $1]</span>')

    // Bold italic: ***text***

    .replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>')

    // Bold: **text**

    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')

    // Italic: *text* or _text_

    .replace(/(^|[^\*])\*([^\*\n]+)\*([^\*]|$)/g, '$1<em>$2</em>$3')

    .replace(/(^|[^_])_([^_\n]+)_([^_]|$)/g, '$1<em>$2</em>$3')

    // Inline code: `code`

    .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')

    // Strikethrough: ~~text~~

    .replace(/~~(.*?)~~/g, '<del>$1</del>')

}



function parseMarkdownSegments(rawText) {

  if (!rawText) return []

  const lines = rawText.split(/\r?\n/)

  const elements = []

  let i = 0



  while (i < lines.length) {

    const line = lines[i]

    const trimmed = line.trim()



    // 1. Skip empty lines

    if (!trimmed) {

      i++

      continue

    }



    // 2. Horizontal divider: --- or ***

    if (/^(\*{3,}|-{3,}|_{3,})$/.test(trimmed)) {

      elements.push({ type: 'hr' })

      i++

      continue

    }



    // 3. Headings: #, ##, ###, ####, #####

    const headingMatch = trimmed.match(/^(#{1,5})\s+(.*)$/)

    if (headingMatch) {

      const level = headingMatch[1].length

      elements.push({ type: `h${level}`, content: headingMatch[2] })

      i++

      continue

    }



    // 4. Blockquotes: lines starting with >

    if (trimmed.startsWith('>')) {

      const bqLines = []

      while (i < lines.length && (lines[i].trim().startsWith('>') || (bqLines.length > 0 && lines[i].trim() && !lines[i].trim().match(/^(#{1,5}\s+|[-*•+]\s+|\d+\.\s+|`{3})/)))) {

        bqLines.push(lines[i].replace(/^\s*>\s?/, ''))

        i++

      }

      elements.push({ type: 'blockquote', content: bqLines.join('\n') })

      continue

    }



    // 5. Tables: lines starting and ending with |

    if (trimmed.startsWith('|') && trimmed.endsWith('|') && i + 1 < lines.length && /\|(?:\s*:?-+:?\s*\|)+/.test(lines[i + 1].trim())) {

      const tableLines = []

      while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {

        tableLines.push(lines[i].trim())

        i++

      }

      if (tableLines.length >= 2) {

        const headerCells = tableLines[0].split('|').slice(1, -1).map(c => c.trim())

        const rowCells = tableLines.slice(2).map(r => r.split('|').slice(1, -1).map(c => c.trim()))

        elements.push({ type: 'table', headers: headerCells, rows: rowCells })

        continue

      }

    }



    // 6. Ordered list: lines starting with 1. , 2. , etc.

    if (/^\d+\.\s+/.test(trimmed)) {

      const olItems = []

      while (i < lines.length) {

        const itemTrim = lines[i].trim()

        const m = itemTrim.match(/^(\d+)\.\s+(.*)$/)

        if (m) {

          olItems.push(m[2])

          i++

        } else if (itemTrim.startsWith('   ') || itemTrim.startsWith('\t') || (itemTrim && !itemTrim.match(/^(#{1,5}\s+|[-*•+]\s+|\d+\.\s+|`{3}|>)/))) {

          if (olItems.length > 0) {

            olItems[olItems.length - 1] += ' ' + itemTrim

          }

          i++

        } else {

          break

        }

      }

      elements.push({ type: 'ol', items: olItems })

      continue

    }



    // 7. Unordered list: lines starting with - , * , • , +

    if (/^[-*•+]\s+/.test(trimmed)) {

      const ulItems = []

      while (i < lines.length) {

        const itemTrim = lines[i].trim()

        const m = itemTrim.match(/^[-*•+]\s+(.*)$/)

        if (m) {

          ulItems.push(m[1])

          i++

        } else if (itemTrim.startsWith('   ') || itemTrim.startsWith('\t') || (itemTrim && !itemTrim.match(/^(#{1,5}\s+|[-*•+]\s+|\d+\.\s+|`{3}|>)/))) {

          if (ulItems.length > 0) {

            ulItems[ulItems.length - 1] += ' ' + itemTrim

          }

          i++

        } else {

          break

        }

      }

      elements.push({ type: 'ul', items: ulItems })

      continue

    }



    // 8. Normal paragraph: gather consecutive non-empty regular lines

    const pLines = []

    while (i < lines.length) {

      const curTrim = lines[i].trim()

      if (!curTrim) break

      if (curTrim.match(/^(#{1,5}\s+|[-*•+]\s+|\d+\.\s+|`{3}|>|\||\*{3,}|-{3,})/)) break

      pLines.push(curTrim)

      i++

    }

    if (pLines.length > 0) {

      elements.push({ type: 'p', content: pLines.join(' ') })

    }

  }



  return elements

}



// Complete refined Markdown Renderer

function MarkdownRenderer({ text, isStreaming = false }) {

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

      content: match[2].trim(),

    })

    lastIndex = match.index + match[0].length

  }

  if (lastIndex < text.length) {

    blocks.push({ type: 'text', content: text.substring(lastIndex) })

  }



  return (

    <div className={`markdown-body${isStreaming ? ' markdown-body--streaming' : ''}`}>

      {blocks.map((block, bIdx) => {

        if (block.type === 'mermaid') {

          return <MermaidDiagram key={`mm_${bIdx}`} code={block.content} />

        }

        if (block.type === 'code') {

          return (

            <pre key={`code_${bIdx}`} className="code-block">

              <code>{block.content}</code>

            </pre>

          )

        }



        const segments = parseMarkdownSegments(block.content)

        return segments.map((seg, sIdx) => {

          const key = `seg_${bIdx}_${sIdx}`

          if (seg.type === 'h1') return <h1 key={key} dangerouslySetInnerHTML={{ __html: formatInline(seg.content) }} />

          if (seg.type === 'h2') return <h2 key={key} dangerouslySetInnerHTML={{ __html: formatInline(seg.content) }} />

          if (seg.type === 'h3') return <h3 key={key} dangerouslySetInnerHTML={{ __html: formatInline(seg.content) }} />

          if (seg.type === 'h4') return <h4 key={key} dangerouslySetInnerHTML={{ __html: formatInline(seg.content) }} />

          if (seg.type === 'h5') return <h5 key={key} dangerouslySetInnerHTML={{ __html: formatInline(seg.content) }} />

          if (seg.type === 'hr') return <hr key={key} className="markdown-hr" />

          if (seg.type === 'blockquote') {

            return (

              <blockquote key={key} className="markdown-blockquote">

                <p dangerouslySetInnerHTML={{ __html: formatInline(seg.content) }} />

              </blockquote>

            )

          }

          if (seg.type === 'ul') {

            return (

              <ul key={key} className="markdown-ul">

                {seg.items.map((item, i) => (

                  <li key={i} dangerouslySetInnerHTML={{ __html: formatInline(item) }} />

                ))}

              </ul>

            )

          }

          if (seg.type === 'ol') {

            return (

              <ol key={key} className="markdown-ol">

                {seg.items.map((item, i) => (

                  <li key={i} dangerouslySetInnerHTML={{ __html: formatInline(item) }} />

                ))}

              </ol>

            )

          }

          if (seg.type === 'table') {

            return (

              <div key={key} className="markdown-table-wrap">

                <table className="markdown-table">

                  <thead>

                    <tr>

                      {seg.headers.map((h, hIdx) => (

                        <th key={hIdx} dangerouslySetInnerHTML={{ __html: formatInline(h) }} />

                      ))}

                    </tr>

                  </thead>

                  <tbody>

                    {seg.rows.map((row, rIdx) => (

                      <tr key={rIdx}>

                        {row.map((cell, cIdx) => (

                          <td key={cIdx} dangerouslySetInnerHTML={{ __html: formatInline(cell) }} />

                        ))}

                      </tr>

                    ))}

                  </tbody>

                </table>

              </div>

            )

          }

          return <p key={key} dangerouslySetInnerHTML={{ __html: formatInline(seg.content) }} />

        })

      })}

    </div>

  )

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
